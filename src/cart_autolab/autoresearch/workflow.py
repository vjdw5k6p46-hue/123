from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cart_autolab.orchestrator import AutolabOrchestrator

from .design import write_simulation_design_plan
from .goal import write_research_goal
from .hypotheses import write_ranked_hypotheses
from .knowledge_base import write_knowledge_index
from .llm_steps import run_configured_llm_steps
from .report import write_autoresearch_report


class AutoResearchWorkflow:
    """Reviewer-facing AutoResearch orchestration layer built on AutolabOrchestrator."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        self.base = AutolabOrchestrator(self.config_path)
        self.run_dir = self.base.run_dir

    def run(self, *, skip_base_run: bool = False) -> dict[str, Any]:
        started = datetime.now(timezone.utc).isoformat()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        goal_path = write_research_goal(self.config, self.run_dir)
        self.base.memory.add("autoresearch_goal", goal_path, "Structured AutoResearch goal saved.")

        base_result: dict[str, Any] | None = None
        if not skip_base_run:
            base_result = self.base.run_all()

        hypothesis_paths = write_ranked_hypotheses(self.run_dir)
        self.base.memory.add("autoresearch_hypotheses", hypothesis_paths["json"], "Ranked hypotheses generated from workflow artifacts.")
        design_path = write_simulation_design_plan(self.config, self.run_dir)
        self.base.memory.add("autoresearch_design", design_path, "AutoResearch simulation design plan saved.")
        refinement_path = self._write_refinement_trace()
        self.base.memory.add("autoresearch_refinement", refinement_path, "Single-iteration refinement trace saved.")
        kb_path = write_knowledge_index(self.run_dir)
        self.base.memory.add("autoresearch_knowledge_base", kb_path, "Knowledge base artifact index saved.")
        llm_status = run_configured_llm_steps(self.config, self.run_dir)
        self.base.memory.add("autoresearch_llm_steps", Path(llm_status["status_path"]), "Configured AutoResearch LLM step status saved.")
        kb_path = write_knowledge_index(self.run_dir)
        manifest_path = self._write_manifest(started, base_result)
        self.base.memory.add("autoresearch_manifest", manifest_path, "AutoResearch artifact manifest saved.")
        report = write_autoresearch_report(self.run_dir, self.config)
        self.base.memory.add("autoresearch_report", Path(report["markdown"]), "AutoResearch final report saved.")
        return {
            "run_dir": str(self.run_dir),
            "research_goal": str(goal_path),
            "knowledge_base": str(kb_path),
            "ranked_hypotheses": {key: str(value) for key, value in hypothesis_paths.items()},
            "simulation_design_plan": str(design_path),
            "refinement_trace": str(refinement_path),
            "artifact_manifest": str(manifest_path),
            "autoresearch_report": report,
        }

    def _write_refinement_trace(self) -> Path:
        trace = {
            "iterations": [
                {
                    "iteration": 1,
                    "status": "completed",
                    "inputs": ["research_goal.json", "included_papers.json", "extracted_evidence.json", "parameter_fingerprints.json"],
                    "outputs": ["ranked_interventions.csv", "critique_report.json", "final_report.md"],
                    "next_step": "Human review before optional external PhysiCell execution or another LLM-guided refinement iteration.",
                }
            ],
            "notes": [
                "This local implementation records one complete workflow iteration.",
                "Future iterations must use real generated artifacts; missing simulation or wet-lab outputs must not be fabricated.",
            ],
        }
        path = self.run_dir / "refinement_trace.json"
        path.write_text(json.dumps(trace, indent=2), encoding="utf-8")
        return path

    def _write_manifest(self, started: str, base_result: dict[str, Any] | None) -> Path:
        artifacts = []
        for path in sorted(self.run_dir.rglob("*")):
            if path.is_file():
                artifacts.append(str(path.relative_to(self.run_dir)))
        manifest = {
            "path": "artifact_manifest.json",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": started,
            "workflow": "autoresearch",
            "base_orchestrator_result": base_result,
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "real_external_physicell_outputs_included": (self.run_dir / "simulation" / "physicell_execution_log.json").exists(),
            "notes": [
                "Mock/replay fixtures are not manuscript evidence.",
                "Real LLM outputs are included only if live or archived provider artifacts exist in llm_calls.jsonl and agent_outputs.",
            ],
        }
        path = self.run_dir / "artifact_manifest.json"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return path
