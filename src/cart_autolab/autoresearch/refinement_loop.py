from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cart_autolab.llm import AgentRunner
from cart_autolab.llm.agent_runner import InvalidLLMOutputError
from cart_autolab.llm.providers import LLMProviderError
from cart_autolab.llm.schema_validation import ValidationReport


ALLOWED_NEXT_ACTIONS = {
    "stop_and_report",
    "request_parameter_refinement",
    "request_more_literature",
    "request_additional_simulation",
    "human_review_required",
}


def write_refinement_loop_trace(config: dict[str, Any], run_dir: Path) -> Path:
    autoresearch = config.get("autoresearch") or {}
    source = str(autoresearch.get("refinement_controller_source", "deterministic")).lower()
    max_iterations = max(1, int(autoresearch.get("max_refinement_iterations", autoresearch.get("iteration_count", 1)) or 1))
    if source == "llm":
        trace = _run_llm_refinement_controller(config, run_dir, max_iterations)
    else:
        trace = _deterministic_trace(run_dir)
    path = run_dir / "refinement_loop_decisions.json"
    path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
    # Backward-compatible filename for older docs/tests.
    legacy_path = run_dir / "refinement_trace.json"
    legacy_path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _deterministic_trace(run_dir: Path) -> dict[str, Any]:
    return {
        "controller": "deterministic",
        "status": "completed",
        "iterations": [
            {
                "iteration": 1,
                "decision_source": "deterministic",
                "continue_refinement": False,
                "next_action": "stop_and_report",
                "reason": "Default AutoResearch run records one complete workflow iteration.",
                "stopping_criteria_met": True,
                "stopping_criteria": ["one deterministic reference iteration completed"],
                "input_artifacts": _decision_context_paths(run_dir),
                "output_artifacts": ["ranked_interventions.csv", "critique_report.json", "final_report.md"],
                "human_review_required": True,
            }
        ],
        "notes": [
            "Deterministic controller preserves default behavior and does not call an LLM.",
            "Missing simulation, LLM, PhysiCell, citation, or wet-lab artifacts are not fabricated.",
        ],
    }


def _run_llm_refinement_controller(config: dict[str, Any], run_dir: Path, max_iterations: int) -> dict[str, Any]:
    trace: dict[str, Any] = {
        "controller": "llm_refinement_loop_decision_agent",
        "status": "completed",
        "max_refinement_iterations": max_iterations,
        "iterations": [],
        "notes": [
            "The LLM decides whether another refinement loop is needed using schema-constrained JSON.",
            "Python validates the decision, enforces max_refinement_iterations, and executes only whitelisted actions.",
            "This controller does not fabricate missing LLM, PhysiCell, citation, or wet-lab outputs.",
        ],
    }
    if (config.get("llm") or {}).get("provider", "none") == "none":
        trace["status"] = "skipped"
        trace["notes"].append("llm.provider is none; no LLM refinement decision call was made.")
        trace["iterations"].append(_fallback_decision(1, run_dir, "LLM provider is none."))
        return trace

    try:
        runner = AgentRunner(config.get("llm", {}), run_dir)
    except LLMProviderError as exc:
        trace["status"] = "skipped"
        trace["notes"].append(f"LLM provider unavailable: {exc}")
        trace["iterations"].append(_fallback_decision(1, run_dir, str(exc)))
        return trace

    previous_decisions: list[dict[str, Any]] = []
    for iteration in range(1, max_iterations + 1):
        decision = _call_decision_agent(runner, config, run_dir, iteration, previous_decisions)
        trace["iterations"].append(decision)
        previous_decisions.append(decision)
        if not decision.get("continue_refinement"):
            break
        if iteration >= max_iterations:
            trace["status"] = "max_iterations_reached"
            decision["continue_refinement"] = False
            decision["forced_stop_reason"] = "Python max_refinement_iterations guardrail reached."
            break
        # The public package does not auto-run another external simulation unless a validated executor
        # is configured. The LLM can decide another loop is needed, but Python pauses safely here.
        if not _auto_execute_enabled(config):
            trace["status"] = "paused_for_human_or_external_executor"
            decision["execution_status"] = "not_executed"
            decision["execution_note"] = (
                "LLM requested another refinement action, but automatic refinement execution is disabled. "
                "Human review or a configured executor is required before running another loop."
            )
            break
    return trace


def _call_decision_agent(
    runner: AgentRunner,
    config: dict[str, Any],
    run_dir: Path,
    iteration: int,
    previous_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        result = runner.run(
            "refinement_loop_decision_agent",
            {
                "iteration": iteration,
                "max_iterations": (config.get("autoresearch") or {}).get("max_refinement_iterations", 1),
                "experiment_config": _compact(json.dumps(config, indent=2)),
                "artifact_summary": _compact(_artifact_summary(run_dir)),
                "simulation_summary": _compact(_read_text(run_dir / "ranked_interventions.csv")),
                "critique_report": _compact(_read_text(run_dir / "critique_report.json")),
                "previous_decisions": json.dumps(previous_decisions, indent=2),
            },
            schema={"required": ["iteration", "continue_refinement", "next_action", "reason", "stopping_criteria_met"]},
            validator=_validate_decision,
            input_artifacts=[path for path in _decision_context_paths(run_dir) if (run_dir / path).exists()],
        )
        parsed = dict(result["parsed"])
        parsed["decision_source"] = "llm"
        parsed["call_id"] = result["call_id"]
        parsed["validation"] = result["validation"]
        parsed["warnings"] = result["warnings"]
        return parsed
    except (InvalidLLMOutputError, LLMProviderError, ValueError) as exc:
        return _fallback_decision(iteration, run_dir, f"LLM refinement decision failed: {exc}")


def _validate_decision(parsed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(parsed.get("continue_refinement"), bool):
        errors.append("continue_refinement must be boolean")
    next_action = str(parsed.get("next_action") or "")
    if next_action not in ALLOWED_NEXT_ACTIONS:
        errors.append(f"next_action must be one of {sorted(ALLOWED_NEXT_ACTIONS)}")
    if not isinstance(parsed.get("stopping_criteria_met"), bool):
        errors.append("stopping_criteria_met must be boolean")
    if parsed.get("continue_refinement") and next_action == "stop_and_report":
        errors.append("continue_refinement cannot be true when next_action is stop_and_report")
    if parsed.get("stopping_criteria_met") and parsed.get("continue_refinement"):
        errors.append("stopping_criteria_met cannot be true while continue_refinement is true")
    confidence = parsed.get("confidence")
    if confidence is not None:
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            errors.append("confidence must be numeric between 0 and 1")
        else:
            if not 0 <= value <= 1:
                errors.append("confidence must be between 0 and 1")
    return ValidationReport(status="failed" if errors else "passed", errors=errors)


def _fallback_decision(iteration: int, run_dir: Path, reason: str) -> dict[str, Any]:
    return {
        "iteration": iteration,
        "decision_source": "python_fallback",
        "continue_refinement": False,
        "next_action": "human_review_required",
        "reason": reason,
        "stopping_criteria_met": False,
        "stopping_criteria": [],
        "input_artifacts": _decision_context_paths(run_dir),
        "human_review_required": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _decision_context_paths(run_dir: Path) -> list[str]:
    candidates = [
        "research_goal.json",
        "ranked_interventions.csv",
        "critique_report.json",
        "parameter_fingerprints.json",
        "physicell_ready_parameters.json",
        "physicell_ready_parameters_refined.json",
        "simulation/parameters.json",
        "simulation/timeseries.csv",
    ]
    return [rel for rel in candidates if (run_dir / rel).exists()]


def _artifact_summary(run_dir: Path) -> str:
    rows = []
    for rel in _decision_context_paths(run_dir):
        path = run_dir / rel
        rows.append({"path": rel, "bytes": path.stat().st_size})
    return json.dumps(rows, indent=2)


def _auto_execute_enabled(config: dict[str, Any]) -> bool:
    return bool((config.get("autoresearch") or {}).get("auto_execute_refinement_actions", False))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _compact(text: str, limit: int = 30000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated for LLM context budget]..."
