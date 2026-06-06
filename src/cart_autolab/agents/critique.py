from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cart_autolab.critique.critique_agent import CritiqueAgent
from cart_autolab.llm import AgentRunner


class ExecutableCritiqueAgent:
    def critique(self, config: dict[str, Any], run_dir: Path, source: str = "deterministic") -> dict[str, Any]:
        deterministic = CritiqueAgent().critique(run_dir)
        if source == "deterministic":
            return deterministic
        evidence = _read_json(run_dir / "extracted_evidence.json", [])
        params = _read_json(run_dir / "parameter_fingerprints.json", [])
        analysis_results = {
            "ranked_interventions": _read_text(run_dir / "ranked_interventions.csv"),
            "analysis_metrics": _read_text(run_dir / "analysis_metrics.csv"),
        }
        result = AgentRunner(config.get("llm", {}), run_dir).run(
            "critique_agent",
            {
                "experiment_config": json.dumps(config, indent=2),
                "evidence_records": json.dumps(evidence, indent=2),
                "parameter_sets": json.dumps(params, indent=2),
                "analysis_results": json.dumps(analysis_results, indent=2),
            },
            schema={"required": ["biological_interpretation", "limitations", "recommended_validation_experiments_high_level"]},
            input_artifacts=[run_dir / "ranked_interventions.csv", run_dir / "parameter_fingerprints.json"],
        )
        llm_report = result["parsed"]
        (run_dir / "critique_report_llm.json").write_text(json.dumps(llm_report, indent=2), encoding="utf-8")
        if source == "llm":
            (run_dir / "critique_report.json").write_text(json.dumps(llm_report, indent=2), encoding="utf-8")
            return llm_report
        return deterministic


def _read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""
