from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml


CYTOKINE_CHUNKS = Path("outputs/manuscript_self_secreting_combined_pdf_archive/paper_chunks_grobid_tei/paper_chunks.jsonl")
TUMOR_CHUNKS = Path("outputs/liver_antigen_density_literature/paper_chunks_grobid_tei/paper_chunks.jsonl")
BASE_PHYSICELL_CONFIG = Path(os.environ.get("PHYSICELL_BASE_CONFIG", "physicell_project/config/PhysiCell_settings.template.xml"))
INTERVENTIONS = ["control", "IL-2", "IL-7", "IL-12", "IL-15", "IL-18"]

ALLOWED_USER_PARAMETER_RANGES: dict[str, tuple[float, float]] = {
    "aux_bath_dose": (0.0, 1.0e9),
    "qmax_aux_engineered": (0.0, 1.0e9),
    "tumor_antigen_density": (0.0, 1.0),
    "K_A": (0.01, 100.0),
    "r0_cart": (0.0, 1.0),
    "carT_prolif_rate": (0.0, 1.0),
    "lambda0_cart": (0.0, 1.0),
    "k0_attack": (0.0, 10.0),
    "dmg0": (0.0, 10.0),
    "p_kill_CAR_T": (0.0, 1.0),
    "k_exh": (0.0, 1.0),
    "carT_exhaustion_per_kill": (0.0, 1.0),
    "carT_exhaustion_rate_when_attached": (0.0, 1.0),
    "lambda_AICD": (0.0, 1.0),
    "qIFNg_max": (0.0, 1.0e9),
    "alpha_IFNg_aux": (0.0, 1.0e9),
    "k_PDL1_up": (0.0, 1.0),
    "hypoxia_exhaust_mult": (0.0, 10.0),
    "M2_present_exhaust_rate": (0.0, 1.0),
    "p_M0_to_M1": (0.0, 1.0),
    "p_M0_to_M2": (0.0, 1.0),
    "tumor_O2_uptake_rate": (0.0, 10.0),
    "tumor_necrosis_rate": (0.0, 1.0),
    "tumor_necrosis_O2_half_max": (0.0, 100.0),
    "tumor_prolif_O2_half_max": (0.0, 100.0),
    "tumor_prolif_min_multiplier": (0.0, 1.0),
    "tumor_damage_per_contact": (0.0, 10.0),
    "tumor_damage_threshold": (0.0, 10.0),
}
ALLOWED_STRING_PARAMETERS = {
    "aux_cytokine_name": {"none", "IL2", "IL7", "IL12", "IL15", "IL18"},
    "aux_mode": {"none", "bath", "armored"},
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM AutoResearch parameter proposal workflow.")
    parser.add_argument("--config", default="configs/autoresearch_gemini.yaml")
    parser.add_argument("--output", default="outputs/autoresearch_llm_parameters")
    parser.add_argument("--cytokine-chunks", default=str(CYTOKINE_CHUNKS))
    parser.add_argument("--tumor-chunks", default=str(TUMOR_CHUNKS))
    parser.add_argument("--max-cytokine-chunks", type=int, default=120)
    parser.add_argument("--max-tumor-chunks", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--workers", type=int, default=1, help="Number of concurrent LLM batch requests.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--base-physicell-config", default=str(BASE_PHYSICELL_CONFIG))
    args = parser.parse_args(argv)

    cfg = _load_yaml(Path(args.config))
    _require_api_key(cfg)
    output = Path(args.output)
    if output.exists() and args.force:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    cytokine_chunks = _load_ranked_chunks(Path(args.cytokine_chunks), max_chunks=args.max_cytokine_chunks, topic="cytokine")
    tumor_chunks = _load_ranked_chunks(Path(args.tumor_chunks), max_chunks=args.max_tumor_chunks, topic="tumor")
    selected_chunks = cytokine_chunks + tumor_chunks
    if not selected_chunks:
        raise SystemExit("No chunks selected for AutoResearch.")

    batches = [selected_chunks[i : i + args.batch_size] for i in range(0, len(selected_chunks), args.batch_size)]
    calls_dir = output / "agent_outputs" / "autoresearch_parameter_agent"
    calls_dir.mkdir(parents=True, exist_ok=True)
    calls_jsonl = output / "llm_calls.jsonl"
    failures_jsonl = output / "llm_call_failures.jsonl"
    proposal_records: list[dict[str, Any]] = []
    batch_reports: list[dict[str, Any]] = []
    start = time.time()

    workers = max(1, int(args.workers or 1))
    print(f"[autoresearch] selected_chunks={len(selected_chunks)} batches={len(batches)} workers={workers}", flush=True)
    with calls_jsonl.open("w", encoding="utf-8") as calls_handle, failures_jsonl.open("w", encoding="utf-8") as failures_handle:
        if workers == 1:
            results = [_process_batch(batch_index, len(batches), batch, cfg, calls_dir) for batch_index, batch in enumerate(batches, start=1)]
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [
                    executor.submit(_process_batch, batch_index, len(batches), batch, cfg, calls_dir)
                    for batch_index, batch in enumerate(batches, start=1)
                ]
                results = []
                completed = 0
                for future in as_completed(futures):
                    completed += 1
                    result = future.result()
                    results.append(result)
                    status = result["status"]
                    if status == "ok":
                        print(
                            f"[autoresearch] progress {completed}/{len(batches)} complete | batch={result['batch_index']}/{len(batches)} valid={len(result['validation']['valid_parameter_proposals'])}",
                            flush=True,
                        )
                    else:
                        print(
                            f"[autoresearch] progress {completed}/{len(batches)} complete | batch={result['batch_index']}/{len(batches)} failed {result['failure']['error_type']}: {result['failure']['error']}",
                            flush=True,
                        )
        for result in sorted(results, key=lambda item: item["batch_index"]):
            if result["status"] == "ok":
                validation = result["validation"]
                proposal_records.extend(validation["valid_parameter_proposals"])
                batch_reports.append(validation)
                calls_handle.write(json.dumps(result["call_record"], ensure_ascii=False) + "\n")
                calls_handle.flush()
                if workers == 1:
                    print(f"[autoresearch] batch {result['batch_index']}/{len(batches)} valid={len(validation['valid_parameter_proposals'])}", flush=True)
            else:
                failures_handle.write(json.dumps(result["failure"], ensure_ascii=False) + "\n")
                failures_handle.flush()
                if workers == 1:
                    failure = result["failure"]
                    print(f"[autoresearch] batch {result['batch_index']}/{len(batches)} failed {failure['error_type']}: {failure['error']}", flush=True)

    merged = _merge_parameter_proposals(proposal_records)
    (output / "autoresearch_parameter_proposals_llm.json").write_text(json.dumps(proposal_records, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "parameter_fingerprints_llm.json").write_text(json.dumps(merged["fingerprints"], indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "tumor_cell_parameter_proposals_llm.json").write_text(json.dumps(merged["tumor_cell_parameters"], indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "validation_report.json").write_text(json.dumps({"batches": batch_reports, "merge": merged["validation"]}, indent=2, ensure_ascii=False), encoding="utf-8")

    physicell_payload = _export_direct_physicell_xml(
        merged["fingerprints"],
        merged["tumor_cell_parameters"],
        Path(args.base_physicell_config),
        output,
    )
    (output / "physicell_ready_parameters.json").write_text(json.dumps(physicell_payload, indent=2), encoding="utf-8")
    report = _write_report(output, cfg, selected_chunks, proposal_records, merged, physicell_payload)
    manifest = {
        "repository": "vjdw5k6p46-hue/123",
        "branch": _git(["branch", "--show-current"]),
        "commit_hash": _git(["rev-parse", "HEAD"]),
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "autoresearch_llm_direct_parameter_proposal",
        "llm_config": args.config,
        "model": cfg.get("model"),
        "selected_cytokine_chunks": len(cytokine_chunks),
        "selected_tumor_chunks": len(tumor_chunks),
        "batches": len(batches),
        "valid_parameter_proposals": len(proposal_records),
        "fingerprints": len(merged["fingerprints"]),
        "tumor_cell_parameters": len(merged["tumor_cell_parameters"]),
        "external_physicell_executed": False,
        "report": str(report),
        "elapsed_seconds": round(time.time() - start, 2),
        "warnings": [
            "AutoResearch mode lets the LLM directly propose PhysiCell user_parameters, but code rejects unsupported/out-of-range/provenance-free proposals.",
            "Generated XML files are model inputs only, not PhysiCell simulation outputs or wet-lab validation.",
            "Mock fixtures are not used unless supplied in the chunk inputs.",
        ],
    }
    (output / "autoresearch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


def _process_batch(
    batch_index: int,
    total_batches: int,
    batch: list[dict[str, Any]],
    cfg: dict[str, Any],
    calls_dir: Path,
) -> dict[str, Any]:
    prompt = _build_prompt(batch)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
    call_id = f"autoresearch_batch_{batch_index:03d}_{prompt_hash}"
    prompt_path = calls_dir / f"{call_id}_prompt.txt"
    raw_path = calls_dir / f"{call_id}_raw_response.txt"
    parsed_path = calls_dir / f"{call_id}_parsed.json"
    validation_path = calls_dir / f"{call_id}_validation.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    try:
        raw = _call_llm(cfg, prompt)
        raw_path.write_text(raw, encoding="utf-8")
        parsed = json.loads(_clean_json(raw))
        parsed_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
        validation = _validate_batch(parsed, batch, call_id)
        validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "status": "ok",
            "batch_index": batch_index,
            "validation": validation,
            "call_record": {
                "call_id": call_id,
                "agent_name": "autoresearch_parameter_agent",
                "provider": cfg.get("provider"),
                "model": cfg.get("model"),
                "base_url": cfg.get("base_url"),
                "temperature": cfg.get("temperature", 0),
                "prompt_hash": prompt_hash,
                "input_chunk_ids": [chunk["chunk_id"] for chunk in batch],
                "raw_response_path": str(raw_path),
                "parsed_json_path": str(parsed_path),
                "schema_validation_status": "passed" if validation["valid_parameter_proposals"] else "no_valid_parameter_proposals",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "warnings": validation["warnings"],
            },
        }
    except Exception as exc:
        failure = {
            "call_id": call_id,
            "batch_index": batch_index,
            "total_batches": total_batches,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "input_chunk_ids": [chunk["chunk_id"] for chunk in batch],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        validation_path.write_text(json.dumps({"status": "failed", "failure": failure}, indent=2), encoding="utf-8")
        return {"status": "failed", "batch_index": batch_index, "failure": failure}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing config: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _require_api_key(cfg: dict[str, Any]) -> None:
    env_name = str(cfg.get("api_key_env") or "GEMINI_API_KEY")
    if not os.getenv(env_name):
        raise SystemExit(f"Missing API key env var {env_name}.")


def _load_ranked_chunks(path: Path, *, max_chunks: int, topic: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Missing {topic} chunks: {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    keywords = _topic_keywords(topic)
    scored = []
    for row in rows:
        text = " ".join(str(row.get(key) or "") for key in ["title", "section", "text"])
        score = sum(1 for pattern in keywords if re.search(pattern, text, re.I))
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: (item[0], int(item[1].get("word_count") or 0)), reverse=True)
    selected = [dict(row, autoresearch_topic=topic, autoresearch_keyword_score=score) for score, row in scored[:max_chunks]]
    return selected


def _topic_keywords(topic: str) -> list[str]:
    if topic == "tumor":
        return [
            r"GPC3|glypican[- ]?3",
            r"hepatocellular|HCC|liver cancer",
            r"antigen density|antigen expression|low antigen|heterogeneous antigen|antigen loss",
            r"PD[- ]?L1|hypoxia|necrosis|proliferation|oxygen",
            r"tumou?r cell|cancer cell",
        ]
    return [
        r"IL[- ]?(2|7|12|15|18)\b",
        r"CAR[- ]?T|chimeric antigen receptor",
        r"persistence|cytotoxicity|exhaustion|IFN|AICD|proliferation",
        r"armou?red|engineered|secret",
    ]


def _build_prompt(chunks: list[dict[str, Any]]) -> str:
    schema = {
        "parameter_proposals": [
            {
                "intervention_name": "control|IL-2|IL-7|IL-12|IL-15|IL-18|tumor_cell_global",
                "physicell_user_parameter": "one allowed user parameter name",
                "proposed_value": "number or allowed string",
                "unit": "dimensionless or source unit",
                "allowed_range_considered": [0, 1],
                "evidence_chunk_ids": ["chunk id from supplied chunks"],
                "supporting_citations": [{"title": "from chunk metadata", "doi": "if supplied", "pmid": "if supplied"}],
                "rationale": "short evidence-linked rationale",
                "confidence": 0.0,
                "assumptions": [],
                "requires_cpp_support": False,
            }
        ],
        "research_gaps": [],
    }
    allowed = {
        "numeric_user_parameters": sorted(ALLOWED_USER_PARAMETER_RANGES),
        "string_user_parameters": {key: sorted(values) for key, values in ALLOWED_STRING_PARAMETERS.items()},
        "interventions": INTERVENTIONS + ["tumor_cell_global"],
    }
    compact_chunks = []
    for chunk in chunks:
        compact_chunks.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "topic": chunk.get("autoresearch_topic"),
                "title": chunk.get("title"),
                "doi": chunk.get("doi"),
                "pmid": chunk.get("pmid"),
                "section": chunk.get("section"),
                "text": str(chunk.get("text") or "")[:2600],
            }
        )
    return (
        "You are an AutoResearch parameter proposal agent for a CAR-T PhysiCell model.\n"
        "Use only supplied chunks. Do not invent citations, papers, DOI, PMID, LLM outputs, PhysiCell outputs, wet-lab values, or unsupported numeric values.\n"
        "Your task is to directly propose PhysiCell user_parameters from evidence. The code will only validate range/provenance and export XML.\n"
        "Low antigen means tumor/cancer cell surface antigen expression or density, especially GPC3/glypican-3 on HCC/liver cancer cells.\n"
        "If evidence is weak, either omit the parameter or mark low confidence and assumptions. Every proposal must cite supplied chunk_ids.\n"
        "Return strict JSON only. No markdown.\n"
        "Allowed parameters and interventions:\n"
        + json.dumps(allowed, ensure_ascii=False)
        + "\nOutput schema shape:\n"
        + json.dumps(schema, ensure_ascii=False)
        + "\nChunks:\n"
        + json.dumps(compact_chunks, ensure_ascii=False)
    )


def _call_llm(cfg: dict[str, Any], prompt: str) -> str:
    payload: dict[str, Any] = {
        "model": cfg.get("model"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": cfg.get("temperature", 0),
    }
    if not cfg.get("omit_seed"):
        payload["seed"] = cfg.get("seed", 1729)
    response = requests.post(
        f"{str(cfg.get('base_url')).rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {os.environ[cfg.get('api_key_env') or 'GEMINI_API_KEY']}", "Content-Type": "application/json"},
        json=payload,
        timeout=int(cfg.get("timeout_seconds", 240)),
    )
    if not response.ok:
        raise requests.HTTPError(f"{response.status_code} {response.reason}: {response.text[:1000]}", response=response)
    return response.json()["choices"][0]["message"]["content"]


def _clean_json(raw: str) -> str:
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


def _validate_batch(parsed: dict[str, Any], chunks: list[dict[str, Any]], call_id: str) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        raise TypeError(f"AutoResearch response must be a JSON object, got {type(parsed).__name__}")
    available_chunks = {str(chunk.get("chunk_id")): chunk for chunk in chunks}
    valid = []
    rejected = []
    warnings = []
    for index, proposal in enumerate(parsed.get("parameter_proposals") or []):
        normalized, errors = _validate_proposal(proposal, available_chunks, call_id, index)
        if errors:
            rejected.append({"proposal": proposal, "errors": errors})
        else:
            valid.append(normalized)
    if not valid:
        warnings.append("No valid parameter proposals passed schema/range/provenance validation for this batch.")
    return {
        "status": "validated",
        "input_chunk_ids": sorted(available_chunks),
        "valid_parameter_proposals": valid,
        "rejected_parameter_proposals": rejected,
        "research_gaps": parsed.get("research_gaps") or [],
        "warnings": warnings,
    }


def _validate_proposal(proposal: dict[str, Any], chunks: dict[str, dict[str, Any]], call_id: str, index: int) -> tuple[dict[str, Any] | None, list[str]]:
    errors = []
    intervention = str(proposal.get("intervention_name") or "").strip()
    parameter = str(proposal.get("physicell_user_parameter") or "").strip()
    if intervention not in set(INTERVENTIONS + ["tumor_cell_global"]):
        errors.append(f"unsupported intervention_name: {intervention}")
    if parameter not in ALLOWED_USER_PARAMETER_RANGES and parameter not in ALLOWED_STRING_PARAMETERS:
        errors.append(f"unsupported physicell_user_parameter: {parameter}")
    chunk_ids = [str(value) for value in proposal.get("evidence_chunk_ids") or [] if value]
    if not chunk_ids:
        errors.append("missing evidence_chunk_ids")
    missing_chunks = [chunk_id for chunk_id in chunk_ids if chunk_id not in chunks]
    if missing_chunks:
        errors.append(f"evidence_chunk_ids not in supplied batch: {missing_chunks[:5]}")
    confidence = _as_float(proposal.get("confidence"))
    if confidence is None or not 0 <= confidence <= 1:
        errors.append("confidence must be numeric between 0 and 1")
    value = proposal.get("proposed_value")
    if parameter in ALLOWED_USER_PARAMETER_RANGES:
        numeric = _as_float(value)
        if numeric is None:
            errors.append("proposed_value must be numeric")
        else:
            low, high = ALLOWED_USER_PARAMETER_RANGES[parameter]
            if numeric < low or numeric > high:
                errors.append(f"proposed_value {numeric} outside allowed range [{low}, {high}]")
            value = numeric
    if parameter in ALLOWED_STRING_PARAMETERS:
        text = str(value)
        if text not in ALLOWED_STRING_PARAMETERS[parameter]:
            errors.append(f"proposed_value {text!r} is not allowed for {parameter}")
        value = text
    citations = proposal.get("supporting_citations") or []
    if not citations:
        errors.append("missing supporting_citations")
    else:
        for citation in citations:
            if not isinstance(citation, dict) or not any(citation.get(key) for key in ["title", "doi", "pmid", "source_paper_id"]):
                errors.append("supporting_citations must include title, DOI, PMID, or source_paper_id from supplied metadata")
                break
    if errors:
        return None, errors
    normalized = {
        "proposal_id": f"{call_id}_proposal_{index:02d}",
        "intervention_name": intervention,
        "physicell_user_parameter": parameter,
        "proposed_value": value,
        "unit": proposal.get("unit") or "not_reported",
        "evidence_chunk_ids": chunk_ids,
        "supporting_citations": citations,
        "rationale": str(proposal.get("rationale") or ""),
        "confidence": round(float(confidence), 4),
        "assumptions": proposal.get("assumptions") or [],
        "requires_cpp_support": bool(proposal.get("requires_cpp_support", False)),
        "llm_call_id": call_id,
        "validation_status": "passed",
    }
    return normalized, []


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _merge_parameter_proposals(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for proposal in proposals:
        key = (proposal["intervention_name"], proposal["physicell_user_parameter"])
        grouped.setdefault(key, []).append(proposal)
    merged_values = []
    validation = {"merged_parameter_count": 0, "notes": []}
    for (intervention, parameter), rows in sorted(grouped.items()):
        rows.sort(key=lambda row: row.get("confidence", 0.0), reverse=True)
        winner = rows[0]
        merged_values.append({**winner, "supporting_proposal_count": len(rows)})
    fingerprints = []
    tumor_cell_parameters = []
    for intervention in INTERVENTIONS:
        params = {row["physicell_user_parameter"]: row["proposed_value"] for row in merged_values if row["intervention_name"] == intervention}
        if params:
            fingerprints.append(
                {
                    "intervention_name": intervention,
                    "physicell_user_parameters": params,
                    "evidence_source": "llm_autoresearch_direct_parameter_proposal",
                    "parameter_derivation_notes": "Direct LLM AutoResearch parameter proposal; code performed schema/range/provenance validation only.",
                    "supporting_proposals": [row for row in merged_values if row["intervention_name"] == intervention],
                }
            )
    for row in merged_values:
        if row["intervention_name"] == "tumor_cell_global":
            tumor_cell_parameters.append(row)
    validation["merged_parameter_count"] = len(merged_values)
    if not fingerprints:
        validation["notes"].append("No intervention-specific fingerprints were proposed; XML export will include control/global tumor parameters only if available.")
    return {"fingerprints": fingerprints, "tumor_cell_parameters": tumor_cell_parameters, "validation": validation}


def _export_direct_physicell_xml(fingerprints: list[dict[str, Any]], tumor_cell_parameters: list[dict[str, Any]], base_config: Path, output: Path) -> dict[str, Any]:
    if not base_config.exists():
        raise FileNotFoundError(f"PhysiCell base config not found: {base_config}")
    out_dir = output / "physicell_ready_configs"
    out_dir.mkdir(parents=True, exist_ok=True)
    global_params = {row["physicell_user_parameter"]: row["proposed_value"] for row in tumor_cell_parameters if not row.get("requires_cpp_support")}
    exported = []
    for fp in fingerprints or [{"intervention_name": "autoresearch_global", "physicell_user_parameters": {}}]:
        tree = ET.parse(base_config)
        root = tree.getroot()
        user_parameters = {**global_params, **fp.get("physicell_user_parameters", {})}
        _apply_user_parameters(root, user_parameters)
        name = re.sub(r"[^A-Za-z0-9_]+", "_", fp["intervention_name"].lower()).strip("_") or "autoresearch"
        xml_path = out_dir / f"PhysiCell_settings_autoresearch_{name}.xml"
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)
        exported.append(
            {
                "intervention_name": fp["intervention_name"],
                "config_path": str(xml_path),
                "user_parameters": user_parameters,
                "source_fingerprint": fp,
            }
        )
    return {
        "base_config": str(base_config),
        "output_dir": str(out_dir),
        "note": "AutoResearch direct LLM parameter proposals exported after schema/range/provenance validation. These are model inputs, not simulation outputs or wet-lab values.",
        "interventions": exported,
        "tumor_cell_global_parameters": tumor_cell_parameters,
    }


def _apply_user_parameters(root: ET.Element, values: dict[str, Any]) -> None:
    user = root.find("user_parameters")
    if user is None:
        raise ValueError("Base PhysiCell XML has no <user_parameters> block.")
    existing = {child.tag: child for child in list(user)}
    for key, value in values.items():
        if key not in ALLOWED_USER_PARAMETER_RANGES and key not in ALLOWED_STRING_PARAMETERS:
            continue
        node = existing.get(key)
        if node is None:
            node = ET.SubElement(user, key)
            node.set("type", "string" if isinstance(value, str) else "double")
            node.set("units", "dimensionless")
        node.text = str(value) if isinstance(value, str) else f"{float(value):.12g}"


def _write_report(output: Path, cfg: dict[str, Any], chunks: list[dict[str, Any]], proposals: list[dict[str, Any]], merged: dict[str, Any], physicell_payload: dict[str, Any]) -> Path:
    path = output / "autoresearch_report.md"
    lines = [
        "# AutoResearch Parameter Proposal Report",
        "",
        f"Model: `{cfg.get('model')}`",
        f"Selected chunks: `{len(chunks)}`",
        f"Valid direct LLM parameter proposals: `{len(proposals)}`",
        f"Intervention fingerprints: `{len(merged['fingerprints'])}`",
        f"Tumor-cell global parameters: `{len(merged['tumor_cell_parameters'])}`",
        "",
        "This workflow lets the LLM directly propose PhysiCell user_parameters from supplied evidence chunks. Code only validates schema, allowed parameter names, value ranges, and provenance before exporting XML.",
        "",
        "These artifacts are not wet-lab validation and not PhysiCell simulation outputs.",
        "",
        "## Exported Configs",
    ]
    for item in physicell_payload.get("interventions", []):
        lines.append(f"- `{item['intervention_name']}`: `{item['config_path']}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _git(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
