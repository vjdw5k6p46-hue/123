from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cart_autolab.llm import AgentRunner


class HypothesisGenerationAgent:
    def generate(self, evidence_records: list[dict[str, Any]], config: dict[str, Any], run_dir: Path, source: str = "deterministic") -> dict[str, Any]:
        if source == "deterministic":
            hypotheses = [
                {
                    "intervention_name": row.get("intervention_name"),
                    "hypothesis": f"{row.get('intervention_name')} may affect configured CAR-T endpoints based on deterministic evidence extraction.",
                    "evidence_source": "deterministic",
                    "confidence": row.get("confidence_score", 0.2),
                }
                for row in evidence_records
            ]
            return {"hypotheses": hypotheses, "intervention_comparisons": [], "expected_direction_by_endpoint": []}
        result = AgentRunner(config.get("llm", {}), run_dir).run(
            "hypothesis_generation_agent",
            {"experiment_config": json.dumps(config, indent=2), "evidence_records": json.dumps(evidence_records, indent=2)},
            schema={"required": ["hypotheses"]},
            input_artifacts=[run_dir / "extracted_evidence_llm.json"],
        )
        (run_dir / "hypotheses_llm.json").write_text(json.dumps(result["parsed"], indent=2), encoding="utf-8")
        return result["parsed"]
