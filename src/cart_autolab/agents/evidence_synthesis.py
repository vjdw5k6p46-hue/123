from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cart_autolab.llm import AgentRunner


class EvidenceSynthesisAgent:
    def synthesize(self, evidence_records: list[dict[str, Any]], config: dict[str, Any], run_dir: Path, source: str = "deterministic") -> dict[str, Any]:
        if source == "deterministic":
            return {"merged_evidence": evidence_records, "conflicts": [], "low_confidence_assumptions": [], "citation_trace": []}
        result = AgentRunner(config.get("llm", {}), run_dir).run(
            "evidence_synthesis_agent",
            {"chunk_evidence_records": json.dumps(evidence_records, indent=2), "experiment_config": json.dumps(config, indent=2)},
            schema={"required": ["merged_evidence"]},
            input_artifacts=[run_dir / "extracted_evidence_llm.json"],
        )
        return result["parsed"]
