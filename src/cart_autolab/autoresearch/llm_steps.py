from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cart_autolab.llm import AgentRunner
from cart_autolab.llm.agent_runner import InvalidLLMOutputError
from cart_autolab.llm.providers import LLMProviderError


STEP_TO_AGENT = {
    "orchestrator": "orchestrator_agent",
    "search_planning": "search_planner_agent",
    "hypothesis_generation": "hypothesis_generation_agent",
    "parameter_building": "parameter_builder_agent",
    "simulation_design": "simulation_design_agent",
    "analysis": "analysis_agent",
    "critique": "critique_agent",
    "report": "report_agent",
}

DEFAULT_LLM_STEPS = [
    "orchestrator",
    "search_planning",
    "hypothesis_generation",
    "parameter_building",
    "simulation_design",
    "analysis",
    "critique",
    "report",
]


def run_configured_llm_steps(config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    requested = _requested_steps(config)
    status = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "requested_steps": requested,
        "provider": (config.get("llm") or {}).get("provider", "none"),
        "steps": [],
        "notes": [
            "LLM steps are optional audit artifacts. They do not overwrite deterministic workflow outputs.",
            "Invalid or missing LLM outputs are recorded rather than fabricated.",
        ],
    }
    if not requested:
        status["notes"].append("No AutoResearch LLM steps requested.")
        return _write_status(run_dir, status)
    if (config.get("llm") or {}).get("provider", "none") == "none":
        status["notes"].append("LLM provider is none; no LLM calls were made.")
        for step in requested:
            status["steps"].append({"step": step, "status": "skipped", "reason": "llm.provider is none"})
        return _write_status(run_dir, status)

    try:
        runner = AgentRunner(config.get("llm", {}), run_dir)
    except LLMProviderError as exc:
        status["notes"].append(f"LLM provider unavailable: {exc}")
        for step in requested:
            status["steps"].append({"step": step, "status": "skipped", "reason": str(exc)})
        return _write_status(run_dir, status)

    context = _load_context(config, run_dir)
    for step in requested:
        agent_name = STEP_TO_AGENT.get(step)
        if not agent_name:
            status["steps"].append({"step": step, "status": "skipped", "reason": "unknown AutoResearch LLM step"})
            continue
        result = _run_step(runner, step, agent_name, context, run_dir)
        status["steps"].append(result)
    return _write_status(run_dir, status)


def _requested_steps(config: dict[str, Any]) -> list[str]:
    raw = (config.get("autoresearch") or {}).get("llm_steps", [])
    if raw == "all" or raw == ["all"]:
        return list(DEFAULT_LLM_STEPS)
    return [str(step) for step in raw if str(step) in STEP_TO_AGENT]


def _run_step(
    runner: AgentRunner,
    step: str,
    agent_name: str,
    context: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    variables = _variables_for_step(step, context)
    output_path = run_dir / f"autoresearch_{step}_llm.json"
    schema = _schema_for_step(step)
    try:
        result = runner.run(agent_name, variables, schema=schema, input_artifacts=_input_artifacts_for_step(step, run_dir))
        output_path.write_text(json.dumps(result["parsed"], indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "step": step,
            "agent_name": agent_name,
            "status": "completed",
            "call_id": result["call_id"],
            "output_path": str(output_path),
            "validation": result["validation"],
            "warnings": result["warnings"],
        }
    except (InvalidLLMOutputError, LLMProviderError, ValueError) as exc:
        failure_path = run_dir / f"autoresearch_{step}_llm_failure.json"
        failure = {
            "step": step,
            "agent_name": agent_name,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        failure_path.write_text(json.dumps(failure, indent=2), encoding="utf-8")
        return {**failure, "failure_path": str(failure_path)}


def _variables_for_step(step: str, context: dict[str, Any]) -> dict[str, Any]:
    experiment_config = context["experiment_config"]
    if step == "orchestrator":
        return {"experiment_config": experiment_config, "artifact_index": context["artifact_index"]}
    if step == "search_planning":
        return {"experiment_config": experiment_config}
    if step == "hypothesis_generation":
        return {"experiment_config": experiment_config, "evidence_records": context["evidence_records"]}
    if step == "parameter_building":
        return {
            "experiment_config": experiment_config,
            "evidence_records": context["evidence_records"],
            "parameter_schema": context["parameter_schema"],
        }
    if step == "simulation_design":
        return {"experiment_config": experiment_config, "parameter_sets": context["parameter_sets"]}
    if step == "analysis":
        return {"simulation_outputs": context["simulation_outputs"], "analysis_config": experiment_config}
    if step == "critique":
        return {
            "experiment_config": experiment_config,
            "evidence_records": context["evidence_records"],
            "parameter_sets": context["parameter_sets"],
            "analysis_results": context["analysis_results"],
        }
    if step == "report":
        return {
            "experiment_config": experiment_config,
            "search_strategy": context["search_strategy"],
            "evidence_records": context["evidence_records"],
            "parameter_sets": context["parameter_sets"],
            "analysis_results": context["analysis_results"],
            "critique": context["critique"],
        }
    raise ValueError(f"Unknown AutoResearch LLM step: {step}")


def _schema_for_step(step: str) -> dict[str, Any]:
    required = {
        "orchestrator": ["workflow_steps"],
        "search_planning": ["queries"],
        "hypothesis_generation": ["hypotheses"],
        "parameter_building": ["parameter_sets"],
        "simulation_design": ["simulation_plan"],
        "analysis": ["metrics"],
        "critique": ["biological_interpretation", "limitations"],
        "report": ["markdown_report"],
    }
    return {"required": required[step]}


def _input_artifacts_for_step(step: str, run_dir: Path) -> list[Path]:
    mapping = {
        "orchestrator": [run_dir / "knowledge_base" / "index.json"],
        "search_planning": [run_dir / "research_goal.json"],
        "hypothesis_generation": [run_dir / "extracted_evidence.json"],
        "parameter_building": [run_dir / "extracted_evidence.json"],
        "simulation_design": [run_dir / "parameter_fingerprints.json"],
        "analysis": [run_dir / "simulation" / "timeseries.csv", run_dir / "analysis_metrics.csv"],
        "critique": [run_dir / "ranked_interventions.csv", run_dir / "parameter_fingerprints.json"],
        "report": [run_dir / "ranked_interventions.csv", run_dir / "critique_report.json"],
    }
    return [path for path in mapping[step] if path.exists()]


def _load_context(config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    return {
        "experiment_config": _compact(json.dumps(config, indent=2)),
        "artifact_index": _compact(_read_text(run_dir / "knowledge_base" / "index.json")),
        "search_strategy": _compact(_read_text(run_dir / "search_queries.json")),
        "evidence_records": _compact(_read_text(run_dir / "extracted_evidence.json")),
        "parameter_sets": _compact(_read_text(run_dir / "parameter_fingerprints.json")),
        "parameter_schema": _compact(_read_text(run_dir / "parameter_transformation_rules.json")),
        "simulation_outputs": _compact(_read_text(run_dir / "simulation" / "timeseries.csv")),
        "analysis_results": _compact(_read_text(run_dir / "analysis_metrics.csv") + "\n" + _read_text(run_dir / "ranked_interventions.csv")),
        "critique": _compact(_read_text(run_dir / "critique_report.json")),
    }


def _write_status(run_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
    path = run_dir / "autoresearch_llm_step_status.json"
    status["status_path"] = str(path)
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    return status


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _compact(text: str, limit: int = 30000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated for LLM context budget]..."
