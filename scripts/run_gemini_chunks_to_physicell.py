from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_chunk_evidence_model_comparison import read_jsonl, run_model  # noqa: E402

from cart_autolab.analysis.parameter_proposal_from_fingerprint import proposal_score  # noqa: E402
from cart_autolab.parameters.physicell_exporter import PhysiCellParameterExporter  # noqa: E402


CYTOKINE_ORDER = ["IL-2", "IL-7", "IL-12", "IL-15", "IL-18"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run an OpenAI-compatible LLM over GROBID paper chunks and export PhysiCell-ready parameter XML inputs."
    )
    parser.add_argument(
        "--chunks",
        default="outputs/manuscript_self_secreting_combined_pdf_archive/paper_chunks_grobid_tei/paper_chunks.jsonl",
        help="JSONL chunks produced by the GROBID chunker.",
    )
    parser.add_argument("--config", default="configs/gemini_api.yaml", help="OpenAI-compatible API config.")
    parser.add_argument("--output", default="outputs/gemini_combined_chunks_to_physicell")
    parser.add_argument("--label", default="gemini", help="Output/model label, e.g. gemini or openai.")
    parser.add_argument("--max-chunks", type=int, default=None, help="Optional pilot limit before running the full corpus.")
    parser.add_argument("--resume", action="store_true", help="Skip chunks already present in extracted_chunk_evidence.jsonl.")
    parser.add_argument("--workers", type=int, default=2, help="Parallel Gemini API calls. Keep low if rate limits appear.")
    parser.add_argument("--rate-limit-seconds", type=float, default=0.0)
    parser.add_argument(
        "--base-physicell-config",
        default="C:/code/PhysiCell/sample_projects/cancer_immune/config/PhysiCell_settings.xml",
        help="Existing PhysiCell XML config to copy and edit. The script does not run PhysiCell.",
    )
    parser.add_argument("--force", action="store_true", help="Remove existing output directory before running.")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    chunks_path = Path(args.chunks)
    out_root = Path(args.output)
    base_physicell_config = Path(args.base_physicell_config)

    cfg = _load_yaml(config_path)
    label = _safe_label(args.label)
    _require_api_key(cfg, label)
    _require_file(chunks_path, "chunk JSONL")
    _require_file(base_physicell_config, "PhysiCell base XML config")

    if out_root.exists() and args.force:
        import shutil

        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    chunks = read_jsonl(chunks_path)
    if args.max_chunks is not None:
        chunks = chunks[: args.max_chunks]
    if not chunks:
        raise SystemExit(f"No chunks found at {chunks_path}")

    model_dir = out_root / label
    start = time.time()
    warnings = [
        f"{label} outputs are live LLM extraction artifacts, not wet-lab validation.",
        "The generated PhysiCell XML files are model inputs only; this script does not execute external PhysiCell.",
        "All citation metadata comes from supplied chunk metadata and LLM-supported evidence records; missing citations are not invented.",
        "Some automatically downloaded PDFs may require human relevance/title verification before manuscript use.",
    ]

    run_model(
        label,
        config_path,
        chunks,
        model_dir,
        resume=args.resume,
        no_raw_prompts=False,
        save_raw_responses=True,
        rate_limit_seconds=args.rate_limit_seconds,
        workers=max(1, args.workers),
    )
    successful_calls = _count_jsonl(model_dir / "llm_calls.jsonl")
    failed_calls = _count_jsonl(model_dir / "llm_call_failures.jsonl")
    if successful_calls == 0 and chunks:
        raise SystemExit(
            f"{label} extraction produced zero successful LLM calls. "
            f"See {model_dir / 'llm_call_failures.jsonl'} for API errors."
        )

    proposals_path = model_dir / "physicell_parameter_proposals.json"
    proposals = _read_json(proposals_path)
    fingerprints = _fingerprints_from_proposals(proposals)
    fingerprints_path = model_dir / "parameter_fingerprints.json"
    fingerprints_path.write_text(json.dumps(fingerprints, indent=2), encoding="utf-8")

    rules = _transformation_rules(proposals, cfg, chunks_path, label)
    (model_dir / "parameter_transformation_rules.json").write_text(json.dumps(rules, indent=2), encoding="utf-8")
    _write_ranking_csv(proposals, model_dir / "ranked_interventions.csv")

    export_config = {
        "experiment_id": "gemini_chunk_to_physicell",
        "candidate_interventions": ["control"] + CYTOKINE_ORDER,
        "parameter_sweep": {"antigen_density": [0.2]},
    }
    physicell_payload = PhysiCellParameterExporter().export(
        fingerprints,
        export_config,
        model_dir,
        base_config=base_physicell_config,
    )

    manifest = {
        "repository": "haochennan-ucla/cart-insilico-autolab",
        "branch": _git(["branch", "--show-current"]),
        "commit_hash": _git(["rev-parse", "HEAD"]),
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "chunks_path": str(chunks_path),
        "chunks_requested": len(chunks),
        "llm_successful_calls": successful_calls,
        "llm_failed_calls": failed_calls,
        "llm_config": str(config_path),
        "model_label": label,
        "provider": cfg.get("provider"),
        "model": cfg.get("model"),
        "base_url": cfg.get("base_url"),
        "temperature": cfg.get("temperature", 0),
        "seed": cfg.get("seed", 1729),
        "llm_calls_jsonl": str(model_dir / "llm_calls.jsonl"),
        "agent_outputs": str(model_dir / "agent_outputs"),
        "validated_evidence": str(model_dir / "extracted_chunk_evidence_validated.jsonl"),
        "cytokine_fingerprint_aggregated": str(model_dir / "cytokine_fingerprint_aggregated.json"),
        "parameter_proposals": str(proposals_path),
        "parameter_fingerprints": str(fingerprints_path),
        "ranked_interventions": str(model_dir / "ranked_interventions.csv"),
        "physicell_ready_parameters": str(model_dir / "physicell_ready_parameters.json"),
        "physicell_ready_config_dir": str(model_dir / "physicell_ready_configs"),
        "external_physicell_executed": False,
        "physicell_exported_config_count": len(physicell_payload.get("interventions", [])),
        "mock_records_used": False,
        "elapsed_seconds": round(time.time() - start, 2),
        "warnings": warnings,
    }
    (out_root / f"{label}_to_physicell_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_root / "README.txt").write_text(_readme_text(manifest), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


def _load_yaml(path: Path) -> dict[str, Any]:
    _require_file(path, "YAML config")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")


def _require_api_key(cfg: dict[str, Any], label: str) -> None:
    env_name = str(cfg.get("api_key_env") or f"{label.upper()}_API_KEY")
    if not os.getenv(env_name):
        raise SystemExit(
            f"{label} API key environment variable {env_name} is not set. "
            f"In PowerShell, run: $env:{env_name}=\"YOUR_API_KEY\""
        )


def _read_json(path: Path) -> dict[str, Any]:
    _require_file(path, "JSON artifact")
    return json.loads(path.read_text(encoding="utf-8"))


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _fingerprints_from_proposals(proposals: dict[str, Any]) -> list[dict[str, Any]]:
    fingerprints = [_control_fingerprint()]
    by_cytokine = {p.get("cytokine"): p for p in proposals.get("proposals", []) if p.get("cytokine") in CYTOKINE_ORDER}
    for cytokine in CYTOKINE_ORDER:
        proposal = by_cytokine.get(cytokine)
        fingerprints.append(_fingerprint_from_proposal(cytokine, proposal))
    return fingerprints


def _control_fingerprint() -> dict[str, Any]:
    return {
        "intervention_name": "control",
        "half_effective_concentration_K": 1.0,
        "proliferation_enhancement_aP": 1.0,
        "survival_enhancement_aS": 1.0,
        "cytotoxicity_enhancement_aC": 1.0,
        "exhaustion_modulation_aE": 0.0,
        "activation_induced_death_penalty_bD": 0.0,
        "ifng_effect": 0.0,
        "pdl1_effect": 0.0,
        "hypoxia_effect": 0.0,
        "tme_remodeling_effect": 0.0,
        "evidence_source": "control",
        "evidence_record_ids": [],
        "llm_call_ids": [],
        "prompt_hashes": [],
        "parameter_derivation_notes": "Baseline control; no LLM evidence applied.",
        "confidence_score": 1.0,
        "uncertainty": 0.0,
        "low_confidence_flags": [],
        "supporting_references": [],
    }


def _fingerprint_from_proposal(cytokine: str, proposal: dict[str, Any] | None) -> dict[str, Any]:
    if not proposal:
        return {
            **_control_fingerprint(),
            "intervention_name": cytokine,
            "evidence_source": "gemini",
            "confidence_score": 0.0,
            "uncertainty": 1.0,
            "low_confidence_flags": ["no_validated_gemini_evidence_for_cytokine"],
            "parameter_derivation_notes": "No validated Gemini evidence was available; neutral parameters exported for review.",
        }

    changes = proposal.get("proposed_parameter_changes") or {}
    quality = float(proposal.get("proposal_quality_score") or 0.0)
    refs = proposal.get("supporting_citations") or []
    record_ids = proposal.get("supporting_record_ids") or []
    return {
        "intervention_name": cytokine,
        "half_effective_concentration_K": _clamp(float(changes.get("half_effective_concentration_K", 1.0) or 1.0), 0.1, 10.0),
        "proliferation_enhancement_aP": _clamp(1.0 + float(changes.get("proliferation_enhancement_aP", 0.0) or 0.0), 0.1, 2.0),
        "survival_enhancement_aS": _clamp(1.0 + float(changes.get("survival_enhancement_aS", 0.0) or 0.0), 0.1, 2.0),
        "cytotoxicity_enhancement_aC": _clamp(1.0 + float(changes.get("cytotoxicity_enhancement_aC", 0.0) or 0.0), 0.1, 2.0),
        "exhaustion_modulation_aE": _clamp(float(changes.get("exhaustion_modulation_aE", 0.0) or 0.0), -1.0, 1.0),
        "activation_induced_death_penalty_bD": _clamp(float(changes.get("activation_induced_death_penalty_bD", 0.0) or 0.0), 0.0, 1.0),
        "ifng_effect": _clamp(float(changes.get("ifng_effect", 0.0) or 0.0), -1.0, 1.0),
        "pdl1_effect": _clamp(float(changes.get("pdl1_effect", 0.0) or 0.0), -1.0, 1.0),
        "hypoxia_effect": _clamp(float(changes.get("hypoxia_effect", 0.0) or 0.0), -1.0, 1.0),
        "tme_remodeling_effect": _clamp(float(changes.get("tme_remodeling_effect", 0.0) or 0.0), -1.0, 1.0),
        "evidence_source": "gemini",
        "evidence_record_ids": record_ids,
        "llm_call_ids": _extract_call_ids(record_ids),
        "prompt_hashes": [],
        "parameter_derivation_notes": "Converted from schema-validated Gemini chunk evidence using deterministic bounded proposal rules; requires human review before external PhysiCell execution.",
        "confidence_score": round(quality, 4),
        "uncertainty": round(1.0 - quality, 4),
        "low_confidence_flags": sorted(set(proposal.get("low_confidence_flags") or [])),
        "supporting_references": refs,
        "proposal_status": proposal.get("proposal_status"),
        "warnings": proposal.get("warnings") or [],
    }


def _extract_call_ids(record_ids: list[Any]) -> list[str]:
    out: list[str] = []
    for record_id in record_ids:
        text = str(record_id)
        marker = "_record_"
        if marker in text:
            call_id = text.split(marker, 1)[0]
            if call_id not in out:
                out.append(call_id)
    return out


def _transformation_rules(proposals: dict[str, Any], cfg: dict[str, Any], chunks_path: Path, label: str) -> dict[str, Any]:
    return {
        "source": f"{label} API chunk evidence extraction",
        "chunks_path": str(chunks_path),
        "model": cfg.get("model"),
        "deterministic_rules_applied": True,
        "llm_evidence_used": True,
        "schema_validation_required": True,
        "manual_overrides_applied": False,
        "low_confidence_assumptions": [
            "LLM extracted evidence is treated as candidate evidence and bounded by deterministic transformation rules.",
            "Missing citation metadata remains missing; citations are not invented.",
            "External PhysiCell simulation is not executed by this script.",
        ],
        "no_fabricated_citations": True,
        "proposal_note": proposals.get("note"),
    }


def _write_ranking_csv(proposals: dict[str, Any], output_path: Path) -> None:
    rows = []
    for proposal in proposals.get("proposals", []):
        rows.append(
            {
                "intervention_name": proposal.get("cytokine"),
                "proposal_status": proposal.get("proposal_status"),
                "proposal_quality_score": proposal.get("proposal_quality_score"),
                "ranking_score": round(proposal_score(proposal), 6),
                "low_confidence_flags": ";".join(proposal.get("low_confidence_flags") or []),
            }
        )
    rows.sort(key=lambda row: float(row["ranking_score"] or 0.0), reverse=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "intervention_name",
                "proposal_status",
                "proposal_quality_score",
                "ranking_score",
                "low_confidence_flags",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _readme_text(manifest: dict[str, Any]) -> str:
    label = manifest.get("model_label") or "LLM"
    return (
        f"{label} chunk-to-PhysiCell artifact directory.\n\n"
        f"These outputs come from live {label} API calls over supplied GROBID chunks. They are candidate extraction artifacts and model-input proposals, not wet-lab evidence.\n"
        "Mock/replay fixtures are not used in this run. Missing citations are not fabricated.\n"
        "External PhysiCell was not executed; the XML files under physicell_ready_configs/ are ready-to-review input configs.\n\n"
        f"Manifest: {manifest}\n"
    )


def _git(args: list[str]) -> str | None:
    import subprocess

    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return round(max(low, min(high, value)), 6)


def _safe_label(label: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in label.strip().lower())
    return cleaned or "llm"


if __name__ == "__main__":
    raise SystemExit(main())
