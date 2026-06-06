from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cart_autolab.literature.search_agent import LiteratureSearchAgent
from cart_autolab.llm import AgentRunner


class LiteratureScreeningAgent:
    def screen(self, papers: list[dict[str, Any]], config: dict[str, Any], run_dir: Path, source: str = "deterministic") -> dict[str, Any]:
        if source == "deterministic":
            included, excluded = LiteratureSearchAgent(mode=config.get("literature", {}).get("mode", "mock"))._screen(papers, config)
            return {"included": included, "excluded": excluded}
        result = AgentRunner(config.get("llm", {}), run_dir).run(
            "literature_screening_agent",
            {"experiment_config": json.dumps(config, indent=2), "paper_metadata": json.dumps(papers, indent=2)},
            schema={"required": ["included", "excluded"]},
            input_artifacts=[run_dir / "raw_literature_results.json"],
        )
        return result["parsed"]
