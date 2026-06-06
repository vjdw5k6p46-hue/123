from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .parameter_proposal_from_fingerprint import proposal_score


def compare_model_outputs(qwen_dir: str | Path, gemma_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    qwen_dir = Path(qwen_dir)
    gemma_dir = Path(gemma_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    models = {"qwen": _load_model(qwen_dir), "gemma": _load_model(gemma_dir)}

    summary_rows = [_summary_row(label, data) for label, data in models.items()]
    _write_csv(output_dir / "model_comparison_summary.csv", summary_rows)

    coverage_rows = _coverage_rows(models)
    traceability_rows = _traceability_rows(models)
    validity_rows = _validity_rows(models)
    agreement_rows, disagreement_cases = _agreement_rows(models)
    ranking_rows = _ranking_rows(models)

    _write_csv(output_dir / "evidence_coverage_by_model.csv", coverage_rows)
    _write_csv(output_dir / "citation_traceability_by_model.csv", traceability_rows)
    _write_csv(output_dir / "schema_validity_by_model.csv", validity_rows)
    _write_csv(output_dir / "cytokine_endpoint_agreement_matrix.csv", agreement_rows)
    _write_csv(output_dir / "cytokine_rank_comparison.csv", ranking_rows)
    _write_jsonl(output_dir / "disagreement_cases.jsonl", disagreement_cases)

    payload = {
        "models": summary_rows,
        "ranking": ranking_rows,
        "disagreement_case_count": len(disagreement_cases),
        "interpretation": "Software-level local LLM comparison only; parameter proposals require human review before external PhysiCell simulation.",
    }
    (output_dir / "model_comparison_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (output_dir / "reviewer_interpretation.md").write_text(_reviewer_interpretation(summary_rows, ranking_rows, len(disagreement_cases)), encoding="utf-8")
    return payload


def _load_model(path: Path) -> dict[str, Any]:
    return {
        "dir": path,
        "valid": _read_jsonl(path / "extracted_chunk_evidence_validated.jsonl"),
        "failures": _read_jsonl(path / "extraction_failures.jsonl"),
        "raw": _read_jsonl(path / "extracted_chunk_evidence.jsonl"),
        "fingerprint": _read_json(path / "cytokine_fingerprint_aggregated.json", {}),
        "proposals": _read_json(path / "physicell_parameter_proposals.json", {"proposals": []}),
        "manifest": _read_json(path / "model_run_manifest.json", {}),
    }


def _summary_row(label: str, data: dict[str, Any]) -> dict[str, Any]:
    valid = data["valid"]
    failures = data["failures"]
    raw_count = len(data["raw"])
    valid_rate = len(valid) / raw_count if raw_count else 0.0
    proposals = data["proposals"].get("proposals", [])
    top = max(proposals, key=proposal_score) if proposals else {}
    il15_rank = _rank_for(proposals, "IL-15")
    return {
        "model_label": label,
        "model_name": data["manifest"].get("model_name") or data["fingerprint"].get("model_name"),
        "raw_record_count": raw_count,
        "valid_record_count": len(valid),
        "failure_count": len(failures),
        "schema_valid_rate": round(valid_rate, 4),
        "cytokine_coverage": len({row.get("cytokine") for row in valid if row.get("cytokine") not in {None, "not_reported", "other"}}),
        "endpoint_coverage": len({row.get("endpoint") for row in valid if row.get("endpoint") not in {None, "not_reported"}}),
        "citation_traceability_fraction": round(sum(1 for row in valid if row.get("citation_provenance_complete")) / len(valid), 4) if valid else 0.0,
        "top_ranked_cytokine": top.get("cytokine"),
        "IL-15_rank": il15_rank,
    }


def _coverage_rows(models: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for label, data in models.items():
        for row in data["valid"]:
            rows.append({"model_label": label, "cytokine": row.get("cytokine"), "endpoint": row.get("endpoint"), "record_id": row.get("record_id")})
    return rows


def _traceability_rows(models: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for label, data in models.items():
        valid = data["valid"]
        by_cytokine: dict[str, list[dict[str, Any]]] = {}
        for row in valid:
            by_cytokine.setdefault(row.get("cytokine", "not_reported"), []).append(row)
        for cytokine, records in by_cytokine.items():
            rows.append({"model_label": label, "cytokine": cytokine, "records": len(records), "citation_traceability_fraction": round(sum(1 for row in records if row.get("citation_provenance_complete")) / len(records), 4)})
    return rows


def _validity_rows(models: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"model_label": label, "raw_records": len(data["raw"]), "valid_records": len(data["valid"]), "failed_records": len(data["failures"])} for label, data in models.items()]


def _agreement_rows(models: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fingerprints = {label: data["fingerprint"].get("cytokines", {}) for label, data in models.items()}
    keys = set()
    for cytokines in fingerprints.values():
        for cytokine, payload in cytokines.items():
            for endpoint in (payload.get("endpoints") or {}):
                keys.add((cytokine, endpoint))
    rows = []
    disagreements = []
    for cytokine, endpoint in sorted(keys):
        q = fingerprints.get("qwen", {}).get(cytokine, {}).get("endpoints", {}).get(endpoint)
        g = fingerprints.get("gemma", {}).get(cytokine, {}).get("endpoints", {}).get(endpoint)
        q_dir = q.get("consensus_effect_direction") if q else "missing"
        g_dir = g.get("consensus_effect_direction") if g else "missing"
        agree = q_dir == g_dir and q_dir != "missing"
        row = {"cytokine": cytokine, "endpoint": endpoint, "qwen_direction": q_dir, "gemma_direction": g_dir, "agreement": agree}
        rows.append(row)
        if not agree:
            disagreements.append(row)
    return rows, disagreements


def _ranking_rows(models: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for label, data in models.items():
        proposals = sorted(data["proposals"].get("proposals", []), key=proposal_score, reverse=True)
        for rank, proposal in enumerate(proposals, start=1):
            rows.append({"model_label": label, "rank": rank, "cytokine": proposal.get("cytokine"), "proposal_score": round(proposal_score(proposal), 4), "proposal_status": proposal.get("proposal_status")})
    return rows


def _rank_for(proposals: list[dict[str, Any]], cytokine: str) -> int | None:
    ranked = sorted(proposals, key=proposal_score, reverse=True)
    for idx, proposal in enumerate(ranked, start=1):
        if proposal.get("cytokine") == cytokine:
            return idx
    return None


def _reviewer_interpretation(summary_rows: list[dict[str, Any]], ranking_rows: list[dict[str, Any]], disagreement_count: int) -> str:
    top_by_model = {row["model_label"]: row.get("top_ranked_cytokine") for row in summary_rows}
    il15 = {row["model_label"]: row.get("IL-15_rank") for row in summary_rows}
    return f"""# Qwen vs Gemma Local LLM Model Comparison

This is a software-level comparison of two optional local LLM backends on the same self-secreting cytokine CAR-T paper chunks.

Top-ranked cytokines by deterministic proposal score: {top_by_model}

IL-15 ranks: {il15}

Disagreement cases: {disagreement_count}

The extracted records are prompt-response artifacts and schema-validated structured evidence candidates. They do not prove biological efficacy. The deterministic parameter proposal layer preserves provenance, applies bounds, and flags low confidence, but the proposals require human review before any external PhysiCell simulation.

No direct PhysiCell run was performed by this comparison. Mock/replay fixtures are not treated as manuscript evidence.
"""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row}) if rows else ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
