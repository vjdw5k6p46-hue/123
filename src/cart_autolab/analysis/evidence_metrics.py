from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


CYTOKINES = ["IL-2", "IL-7", "IL-12", "IL-15", "IL-18"]
ENDPOINTS = ["proliferation", "persistence", "cytotoxicity", "exhaustion", "IFN_gamma", "TME remodeling", "AICD"]
ENDPOINT_FIELDS = {
    "proliferation": "proliferation_effect",
    "persistence": "survival_or_persistence_effect",
    "cytotoxicity": "cytotoxicity_effect",
    "exhaustion": "exhaustion_effect",
    "IFN_gamma": "cytokine_production_effect",
    "TME remodeling": "tme_remodeling_effect",
    "AICD": "activation_induced_cell_death_effect",
}


def load_evidence(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "extracted_evidence.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def evidence_coverage_matrix(evidence: list[dict[str, Any]], mode: str) -> pd.DataFrame:
    rows = []
    for cytokine in CYTOKINES:
        cytokine_rows = [row for row in evidence if row.get("intervention_name") == cytokine]
        for endpoint in ENDPOINTS:
            field = ENDPOINT_FIELDS[endpoint]
            covered = any(abs(float(row.get(field, 0.0) or 0.0)) > 0 for row in cytokine_rows)
            rows.append({"mode": mode, "cytokine": cytokine, "endpoint": endpoint, "covered": int(covered)})
    return pd.DataFrame(rows)


def citation_traceability(evidence: list[dict[str, Any]]) -> float:
    if not evidence:
        return 0.0
    traceable = 0
    for row in evidence:
        citation = str(row.get("supporting_citation", ""))
        if any(token in citation.lower() for token in ["doi:", "pmid:", "missing title"]) or row.get("source_paper_id"):
            traceable += 1
    return traceable / len(evidence)


def low_confidence_fraction(evidence: list[dict[str, Any]]) -> float:
    if not evidence:
        return 0.0
    low = [row for row in evidence if row.get("low_confidence_flags") or float(row.get("confidence_score", 0.0) or 0.0) < 0.45]
    return len(low) / len(evidence)


def schema_valid_rate(run_dir: Path) -> float:
    path = run_dir / "llm_calls.jsonl"
    if not path.exists():
        return 1.0
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        return 1.0
    valid = [record for record in records if record.get("schema_validation_status") == "passed"]
    return len(valid) / len(records)
