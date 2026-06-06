from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cart_autolab.literature.search_agent import LiteratureSearchAgent
from cart_autolab.llm import AgentRunner


class SearchPlannerAgent:
    def plan(self, config: dict[str, Any], run_dir: Path, source: str = "deterministic") -> dict[str, Any]:
        if source == "deterministic":
            queries = LiteratureSearchAgent(mode=config.get("literature", {}).get("mode", "mock")).generate_queries(config)
            return {"queries": [{"source": "deterministic", "query": query, "rationale": "deterministic query template"} for query in queries]}
        result = AgentRunner(config.get("llm", {}), run_dir).run(
            "search_planner_agent",
            {"experiment_config": json.dumps(config, indent=2)},
            schema={"required": ["queries"]},
            input_artifacts=[run_dir / "experiment_config.yaml"],
        )
        return result["parsed"]
