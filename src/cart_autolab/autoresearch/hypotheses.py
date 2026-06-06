from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def write_ranked_hypotheses(run_dir: Path) -> dict[str, Path]:
    ranked = _read_csv(run_dir / "ranked_interventions.csv")
    params = _load_json(run_dir / "parameter_fingerprints.json", [])
    llm_hypotheses = _load_json(run_dir / "hypotheses_llm.json", None)
    confidence_by_intervention = {
        row.get("intervention_name"): row.get("confidence_score", row.get("confidence", 0.0))
        for row in params
        if isinstance(row, dict)
    }
    hypotheses = []
    for rank_index, row in enumerate(ranked, start=1):
        intervention = row.get("intervention_name")
        hypotheses.append(
            {
                "rank": rank_index,
                "intervention_name": intervention,
                "hypothesis": _hypothesis_text(intervention),
                "ranked_intervention_score": _as_float(row.get("ranked_intervention_score")),
                "parameter_confidence": _as_float(confidence_by_intervention.get(intervention, 0.0)),
                "source": "llm_agent" if llm_hypotheses else "workflow_artifact_summary",
                "validation_status": "hypothesis_for_prioritization_not_biological_proof",
            }
        )
    json_path = run_dir / "ranked_hypotheses.json"
    csv_path = run_dir / "ranked_hypotheses.csv"
    json_path.write_text(json.dumps({"hypotheses": hypotheses, "llm_hypotheses": llm_hypotheses}, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(hypotheses[0]) if hypotheses else ["rank", "intervention_name"])
        writer.writeheader()
        writer.writerows(hypotheses)
    return {"json": json_path, "csv": csv_path}


def _hypothesis_text(intervention: str | None) -> str:
    if not intervention or intervention == "control":
        return "Control condition provides a reference for comparing engineered cytokine interventions."
    return f"{intervention} engineering may alter CAR-T function under low-antigen GPC3 liver cancer conditions and should be evaluated as a model-supported hypothesis."


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
