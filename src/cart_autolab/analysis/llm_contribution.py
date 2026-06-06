from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pandas as pd

from cart_autolab.analysis.evidence_metrics import ENDPOINT_FIELDS, citation_traceability, load_evidence, low_confidence_fraction, schema_valid_rate


def write_llm_contribution_summary(reviewer_demo_dir: str | Path) -> Path:
    reviewer_demo_dir = Path(reviewer_demo_dir)
    rows = [
        _summarize_mode("deterministic", reviewer_demo_dir / "deterministic", "deterministic reference mode"),
        _summarize_mode("llm_mock", reviewer_demo_dir / "llm_mock", "software-fixture demonstration; not biological validation"),
        _summarize_mode("llm_replay", reviewer_demo_dir / "replay", "archived replay software fixture; no live LLM call"),
        _summarize_mode("hybrid", reviewer_demo_dir / "ablation" / "hybrid", "hybrid software-fixture demonstration; not biological validation"),
    ]
    out = reviewer_demo_dir / "llm_contribution_summary.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return out


def _summarize_mode(workflow_mode: str, run_dir: Path, notes: str) -> dict[str, Any]:
    evidence = load_evidence(run_dir)
    cytokines = sorted({row.get("intervention_name") for row in evidence if row.get("intervention_name") and row.get("intervention_name") != "control"})
    endpoints = _covered_endpoints(evidence)
    ranking = _ranking(run_dir)
    evidence_source = _evidence_source(evidence, workflow_mode)
    if not run_dir.exists():
        notes = f"not available; run {run_dir} first"
    return {
        "workflow_mode": workflow_mode,
        "evidence_source": evidence_source,
        "number_of_evidence_records": len(evidence),
        "number_of_cytokines_covered": len(cytokines),
        "endpoints_covered": ";".join(endpoints) if endpoints else "none",
        "citation_traceability_fraction": f"{citation_traceability(evidence):.4f}",
        "schema_valid_fraction": f"{schema_valid_rate(run_dir):.4f}",
        "low_confidence_fraction": f"{low_confidence_fraction(evidence):.4f}",
        "IL15_rank": ranking["IL15_rank"],
        "top_ranked_intervention": ranking["top_ranked_intervention"],
        "notes": notes + "; experimental concordance not evaluated; user-supplied validation table required",
    }


def _covered_endpoints(evidence: list[dict[str, Any]]) -> list[str]:
    covered = []
    for endpoint, field in ENDPOINT_FIELDS.items():
        if any(abs(float(row.get(field, 0.0) or 0.0)) > 0 for row in evidence):
            covered.append(endpoint)
    return covered


def _ranking(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "ranked_interventions.csv"
    if not path.exists():
        return {"IL15_rank": "not available", "top_ranked_intervention": "not available"}
    df = pd.read_csv(path)
    if df.empty:
        return {"IL15_rank": "not available", "top_ranked_intervention": "not available"}
    matches = df.index[df["intervention_name"] == "IL-15"].tolist()
    return {
        "IL15_rank": str(int(matches[0] + 1)) if matches else "not available",
        "top_ranked_intervention": str(df.iloc[0]["intervention_name"]),
    }


def _evidence_source(evidence: list[dict[str, Any]], fallback: str) -> str:
    sources = sorted({str(row.get("evidence_source")) for row in evidence if row.get("evidence_source")})
    if fallback == "hybrid" and any(not row.get("evidence_source") for row in evidence):
        sources = sorted(set(sources) | {"deterministic"})
    if sources:
        return "+".join(sources)
    return "deterministic" if fallback == "deterministic" else fallback
