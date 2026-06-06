from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_simulation_design_plan(config: dict[str, Any], run_dir: Path) -> Path:
    parameters = _load_json(run_dir / "parameter_fingerprints.json", [])
    plan = {
        "stage": "experimental_design_and_in_silico_setup",
        "simulator_choice": config.get("simulator_choice", "physicell"),
        "external_physicell_required": bool(config.get("simulator", {}).get("require_external_executable", False)),
        "external_physicell_executed": False,
        "candidate_interventions": config.get("candidate_interventions", []),
        "replicates": config.get("replicates"),
        "random_seed": config.get("random_seed"),
        "parameter_sweep": config.get("parameter_sweep", {}),
        "parameter_sets": [
            {
                "intervention_name": row.get("intervention_name"),
                "evidence_source": row.get("evidence_source", "not_reported"),
                "confidence_score": row.get("confidence_score"),
                "uncertainty": row.get("uncertainty"),
                "llm_call_ids": row.get("llm_call_ids", []),
                "low_confidence_flags": row.get("low_confidence_flags", []),
            }
            for row in parameters
            if isinstance(row, dict)
        ],
        "notes": [
            "This plan describes model inputs and conditions. It is not a wet-lab protocol.",
            "External PhysiCell output is not claimed unless execution logs and sufficient converted outputs exist.",
        ],
    }
    execution_log = run_dir / "simulation" / "physicell_execution_log.json"
    if execution_log.exists():
        try:
            log = json.loads(execution_log.read_text(encoding="utf-8"))
            plan["external_physicell_executed"] = bool(log.get("returncode") == 0 or log.get("status") == "completed")
        except json.JSONDecodeError:
            plan["notes"].append("Could not parse external PhysiCell execution log.")
    path = run_dir / "simulation_design_plan.json"
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return path


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
