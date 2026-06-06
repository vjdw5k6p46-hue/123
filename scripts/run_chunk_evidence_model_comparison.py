from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import requests
import yaml

from cart_autolab.analysis.compare_local_llm_models import compare_model_outputs
from cart_autolab.analysis.cytokine_fingerprint_aggregation import aggregate_jsonl
from cart_autolab.analysis.model_comparison_validation import validate_jsonl
from cart_autolab.analysis.parameter_proposal_from_fingerprint import write_parameter_proposals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Qwen vs Gemma local LLM comparison on paper chunks.")
    parser.add_argument("--chunks", default="outputs/manuscript_self_secreting_selected_download/paper_chunks/paper_chunks.jsonl")
    parser.add_argument("--qwen-config", default="configs/local_llm_qwen.yaml")
    parser.add_argument("--gemma-config", default="configs/local_llm_gemma.yaml")
    parser.add_argument("--output", default="outputs/model_comparison_qwen_vs_gemma")
    parser.add_argument("--max-chunks", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--no-raw-prompts", action="store_true")
    parser.add_argument("--save-raw-responses", action="store_true")
    parser.add_argument("--rate-limit-seconds", type=float, default=0.0)
    parser.add_argument("--workers", type=int, default=1, help="Parallel LLM calls per model. Use carefully with local servers.")
    args = parser.parse_args(argv)

    output = Path(args.output)
    if output.exists() and args.force:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    chunks = read_jsonl(args.chunks)
    if args.max_chunks:
        chunks = chunks[: args.max_chunks]
    if not chunks:
        raise SystemExit(f"No chunks found at {args.chunks}")

    smoke = run_smoke(args.qwen_config, args.gemma_config, output / "comparison", args.allow_partial)
    labels = []
    if smoke["models"]["qwen"]["passed"]:
        labels.append(("qwen", Path(args.qwen_config)))
    if smoke["models"]["gemma"]["passed"]:
        labels.append(("gemma", Path(args.gemma_config)))
    if len(labels) < 2 and not args.allow_partial:
        raise SystemExit("Both models must pass smoke test unless --allow-partial is set.")

    for label, config_path in labels:
        run_model(label, config_path, chunks, output / label, resume=args.resume, no_raw_prompts=args.no_raw_prompts, save_raw_responses=args.save_raw_responses, rate_limit_seconds=args.rate_limit_seconds, workers=args.workers)
    if (output / "qwen").exists() and (output / "gemma").exists():
        compare_model_outputs(output / "qwen", output / "gemma", output / "comparison")

    checklist = {
        "output": str(output),
        "qwen_llm_calls": str(output / "qwen" / "llm_calls.jsonl"),
        "gemma_llm_calls": str(output / "gemma" / "llm_calls.jsonl"),
        "comparison_summary": str(output / "comparison" / "model_comparison_summary.csv"),
        "reviewer_interpretation": str(output / "comparison" / "reviewer_interpretation.md"),
    }
    print(json.dumps({"artifact_checklist": checklist}, indent=2))
    return 0


def run_smoke(qwen_config: str, gemma_config: str, comparison_dir: Path, allow_partial: bool) -> dict[str, Any]:
    smoke_module_path = Path(__file__).resolve().parent / "smoke_test_local_llm_models.py"
    spec = importlib.util.spec_from_file_location("smoke_test_local_llm_models", smoke_module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load smoke test module: {smoke_module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    comparison_dir.mkdir(parents=True, exist_ok=True)
    results = {"timestamp": datetime.now(timezone.utc).isoformat(), "models": {"qwen": module.smoke_one(Path(qwen_config)), "gemma": module.smoke_one(Path(gemma_config))}}
    (comparison_dir / "smoke_test_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [label for label, result in results["models"].items() if not result.get("passed")]
    print(json.dumps(results, indent=2))
    if failed and not allow_partial:
        raise SystemExit(f"Smoke test failed for: {', '.join(failed)}")
    return results


def run_model(label: str, config_path: Path, chunks: list[dict[str, Any]], out_dir: Path, *, resume: bool, no_raw_prompts: bool, save_raw_responses: bool, rate_limit_seconds: float, workers: int = 1) -> None:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    out_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = out_dir / "agent_outputs" / "chunk_evidence_extraction"
    agent_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "extracted_chunk_evidence.jsonl"
    calls_path = out_dir / "llm_calls.jsonl"
    failures_path = out_dir / "llm_call_failures.jsonl"
    done = existing_done(raw_path) if resume else set()
    if not resume:
        for path in [raw_path, calls_path, failures_path]:
            if path.exists():
                path.unlink()

    start = time.time()
    pending = [(index, chunk) for index, chunk in enumerate(chunks, start=1) if str(chunk.get("chunk_id") or f"chunk:{index}") not in done]
    for index, chunk in enumerate(chunks, start=1):
        chunk_id = str(chunk.get("chunk_id") or f"chunk:{index}")
        if chunk_id in done:
            print(f"[{label}] skip {index}/{len(chunks)} {chunk_id}", flush=True)
    write_lock = Lock()

    def run_one(item: tuple[int, dict[str, Any]]) -> dict[str, Any]:
        index, chunk = item
        chunk_id = str(chunk.get("chunk_id") or f"chunk:{index}")
        print(f"[{label}] extract {index}/{len(chunks)} {chunk_id}", flush=True)
        prompt = build_prompt(label, cfg.get("model"), chunk)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        call_id = f"{label}_chunk_{index:04d}_{prompt_hash}"
        prompt_file = agent_dir / f"{call_id}_prompt.txt"
        raw_file = agent_dir / f"{call_id}_raw_response.txt"
        parsed_file = agent_dir / f"{call_id}_parsed.json"
        validation_file = agent_dir / f"{call_id}_validation.json"
        if not no_raw_prompts:
            prompt_file.write_text(prompt, encoding="utf-8")
        try:
            response_text = call_llm(cfg, prompt)
            if save_raw_responses or cfg.get("save_raw_responses", True):
                raw_file.write_text(response_text, encoding="utf-8")
            parsed = json.loads(clean_json(response_text))
            if isinstance(parsed, list):
                parsed = {"records": parsed}
            if not isinstance(parsed, dict):
                raise TypeError(f"Expected JSON object or record list, got {type(parsed).__name__}")
            parsed_file.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
            records = normalize_records(parsed.get("records", []), label, cfg.get("model"), chunk, call_id)
            validation_file.write_text(json.dumps({"status": "not_run_until_batch_validation", "record_count": len(records)}, indent=2), encoding="utf-8")
            if rate_limit_seconds:
                time.sleep(rate_limit_seconds)
            result = {
                "index": index,
                "chunk_id": chunk_id,
                "records": records,
                "call": {"call_id": call_id, "model_label": label, "model": cfg.get("model"), "base_url": cfg.get("base_url"), "chunk_id": chunk_id, "prompt_hash": prompt_hash, "parsed_json_path": str(parsed_file), "raw_response_path": str(raw_file), "timestamp": datetime.now(timezone.utc).isoformat()},
            }
            write_result(result, raw_path, calls_path, write_lock)
            return {"index": index, "chunk_id": chunk_id, "record_count": len(records), "status": "ok"}
        except Exception as exc:
            failure = {
                "call_id": call_id,
                "model_label": label,
                "model": cfg.get("model"),
                "chunk_id": chunk_id,
                "prompt_hash": prompt_hash,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            validation_file.write_text(json.dumps({"status": "failed_before_batch_validation", "error": failure}, indent=2), encoding="utf-8")
            write_failure(failure, failures_path, write_lock)
            return {"index": index, "chunk_id": chunk_id, "record_count": 0, "status": "failed"}

    completed = 0
    if workers <= 1:
        for item in pending:
            result = run_one(item)
            completed += 1
            print(f"[{label}] progress {completed}/{len(pending)} pending complete | chunk={result['chunk_id']}", flush=True)
    else:
        print(f"[{label}] parallel workers={workers} pending_chunks={len(pending)}", flush=True)
        with cf.ThreadPoolExecutor(max_workers=workers) as executor:
            pending_iter = iter(pending)
            futures: set[cf.Future] = set()
            for _ in range(min(workers, len(pending))):
                futures.add(executor.submit(run_one, next(pending_iter)))
            while futures:
                done_futures, futures = cf.wait(futures, return_when=cf.FIRST_COMPLETED)
                for future in done_futures:
                    result = future.result()
                    completed += 1
                    print(f"[{label}] progress {completed}/{len(pending)} pending complete | chunk={result['chunk_id']} status={result['status']}", flush=True)
                    try:
                        item = next(pending_iter)
                    except StopIteration:
                        continue
                    futures.add(executor.submit(run_one, item))

    chunk_meta = {str(chunk.get("chunk_id")): chunk for chunk in chunks}
    validation_summary = validate_jsonl(raw_path, out_dir / "extracted_chunk_evidence_validated.jsonl", out_dir / "extraction_failures.jsonl", chunk_meta)
    fingerprint = aggregate_jsonl(out_dir / "extracted_chunk_evidence_validated.jsonl", out_dir / "cytokine_fingerprint_aggregated.json", model_name=cfg.get("model"))
    proposals = write_parameter_proposals(out_dir / "cytokine_fingerprint_aggregated.json", out_dir / "physicell_parameter_proposals.json")
    manifest = {"model_label": label, "model_name": cfg.get("model"), "base_url": cfg.get("base_url"), "chunks_requested": len(chunks), "validation_summary": validation_summary, "fingerprint_cytokines": sorted((fingerprint.get("cytokines") or {}).keys()), "proposal_count": len(proposals.get("proposals", [])), "elapsed_seconds": round(time.time() - start, 2), "warnings": ["Raw LLM outputs are evidence extraction candidates only; parameter proposals require human review before external PhysiCell simulation."]}
    (out_dir / "model_run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "README.txt").write_text("Local LLM chunk evidence extraction artifacts. These are not final PhysiCell parameters and require human review.\n", encoding="utf-8")


def build_prompt(label: str, model_name: str | None, chunk: dict[str, Any]) -> str:
    metadata = {key: chunk.get(key) for key in ["paper_id", "chunk_id", "chunk_index", "title", "doi", "pmid", "pmcid"]}
    schema = {
        "records": [
            {
                "cytokine": "IL-2|IL-7|IL-12|IL-15|IL-18|other|not_reported",
                "is_t_cell_self_secreting_or_engineered_secretion": True,
                "endpoint": "proliferation|persistence|cytotoxicity|exhaustion|IFN_gamma|TME_remodeling|AICD|toxicity|safety|not_reported",
                "effect_direction": "increased|decreased|mixed|no_change|not_reported",
                "evidence_strength": "direct|indirect|review|computational|not_reported",
                "model_type": "in_vitro|in_vivo|clinical|computational|review|unknown",
                "supporting_text": "short span only",
                "confidence": 0.0,
                "low_confidence_flags": [],
            }
        ]
    }
    return (
        "Extract structured evidence relevant to self-secreting or cytokine-armored CAR-T engineering.\n"
        "Use only the supplied chunk text and metadata. Do not invent citations, DOI, PMID, PMCID, title, chunk IDs, LLM outputs, PhysiCell outputs, wet-lab values, or claims.\n"
        "If cytokine or endpoint is not explicitly supported, write not_reported. Mark review-derived evidence as evidence_strength=review. Supporting text must be short.\n"
        "Return strict JSON only matching this schema shape:\n"
        + json.dumps(schema, ensure_ascii=False)
        + "\nMetadata:\n"
        + json.dumps(metadata, ensure_ascii=False)
        + "\nChunk text:\n"
        + str(chunk.get("text") or "")
    )


def call_llm(cfg: dict[str, Any], prompt: str) -> str:
    api_key = os.getenv(cfg.get("api_key_env") or "LOCAL_LLM_API_KEY", "dummy")
    payload = {"model": cfg.get("model"), "messages": [{"role": "user", "content": prompt}], "temperature": cfg.get("temperature", 0)}
    if not cfg.get("omit_seed"):
        payload["seed"] = cfg.get("seed", 1729)
    response = requests.post(
        f"{str(cfg.get('base_url')).rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=int(cfg.get("timeout_seconds", 120)),
    )
    if not response.ok:
        raise requests.HTTPError(f"{response.status_code} {response.reason}: {response.text[:1000]}", response=response)
    return response.json()["choices"][0]["message"]["content"]


def clean_json(raw: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", raw.strip(), flags=re.S).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return text


def normalize_records(records: list[dict[str, Any]], label: str, model_name: str | None, chunk: dict[str, Any], call_id: str) -> list[dict[str, Any]]:
    normalized = []
    for idx, record in enumerate(records):
        row = dict(record)
        row["record_id"] = row.get("record_id") or f"{call_id}_record_{idx:02d}"
        row["model_name"] = model_name or label
        for field in ["paper_id", "chunk_id", "chunk_index", "title", "doi", "pmid", "pmcid"]:
            row[field] = chunk.get(field) if row.get(field) in {None, ""} else row.get(field)
        row.setdefault("car_target", "not_reported")
        row.setdefault("tumor_context", "not_reported")
        row.setdefault("secretion_context", "not_reported")
        row["citation_provenance_complete"] = bool(row.get("title") and (row.get("doi") or row.get("pmid") or row.get("pmcid")))
        normalized.append(row)
    return normalized


def existing_done(path: Path) -> set[str]:
    return {str(row.get("chunk_id")) for row in read_jsonl(path)}


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_result(result: dict[str, Any], raw_path: Path, calls_path: Path, lock: Lock) -> None:
    with lock:
        with raw_path.open("a", encoding="utf-8") as handle:
            for record in result["records"]:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        append_jsonl(calls_path, result["call"])


def write_failure(failure: dict[str, Any], failures_path: Path, lock: Lock) -> None:
    with lock:
        append_jsonl(failures_path, failure)


if __name__ == "__main__":
    raise SystemExit(main())
