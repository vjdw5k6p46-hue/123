from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cart_autolab.llm import AgentRunner
from cart_autolab.llm.agent_runner import InvalidLLMOutputError
from cart_autolab.llm.providers import LLMProviderError
from cart_autolab.llm.schema_validation import ValidationReport


def build_research_goal(config: dict[str, Any]) -> dict[str, Any]:
    autoresearch = config.get("autoresearch", {}) or {}
    goal = {
        "workflow_name": "LLM-guided, schema-constrained CAR-T in silico workflow",
        "objective": autoresearch.get(
            "objective",
            "Prioritize cytokine-armored CAR-T hypotheses and PhysiCell-ready model inputs for low-antigen liver cancer.",
        ),
        "disease_context": config.get("disease_context"),
        "tumor_type": config.get("tumor_type"),
        "car_target_antigen": config.get("car_target_antigen"),
        "antigen_density_condition": config.get("antigen_density_condition"),
        "engineering_variable": config.get("engineering_variable"),
        "candidate_interventions": config.get("candidate_interventions", []),
        "biological_endpoints": config.get("biological_endpoints", []),
        "simulator_choice": config.get("simulator_choice", "physicell"),
        "llm_role": (
            "Optional LLM agents synthesize supplied literature/chunk evidence into structured hypotheses, "
            "evidence records, critique, or direct parameter proposals when explicitly configured."
        ),
        "guardrails": [
            "Do not fabricate citations, LLM outputs, PhysiCell outputs, or wet-lab values.",
            "Mock records are software fixtures only.",
            "External PhysiCell execution is optional and requires a local executable.",
            "Generated model inputs require human scientific review before manuscript use.",
        ],
        "goal_source": "deterministic_config",
    }
    return goal


def write_research_goal(config: dict[str, Any], run_dir: Path) -> Path:
    if _goal_source(config) == "llm":
        return write_llm_research_goal(config, run_dir)
    path = run_dir / "research_goal.json"
    path.write_text(json.dumps(build_research_goal(config), indent=2), encoding="utf-8")
    return path


def write_llm_research_goal(config: dict[str, Any], run_dir: Path) -> Path:
    path = run_dir / "research_goal.json"
    fallback = build_research_goal(config)
    status = {
        "goal_source_requested": "llm",
        "status": "not_run",
        "notes": [
            "Step 1 asks an LLM to parse the researcher question and bound the search scope.",
            "This step does not generate tumor parameters or fabricate literature evidence.",
        ],
    }
    if (config.get("llm") or {}).get("provider", "none") == "none":
        fallback["goal_source"] = "deterministic_fallback_provider_none"
        status.update({"status": "skipped", "reason": "llm.provider is none"})
        _write_goal_status(run_dir, status)
        path.write_text(json.dumps(fallback, indent=2), encoding="utf-8")
        return path

    try:
        runner = AgentRunner(config.get("llm", {}), run_dir)
        result = runner.run(
            "research_goal_parser_agent",
            {
                "experiment_config": json.dumps(config, indent=2),
                "research_question": _research_question(config),
            },
            schema={"required": ["research_question", "tumor_context", "cell_therapy", "search_scope", "simulation_outputs_needed"]},
            validator=validate_research_goal_parse,
        )
        goal = _merge_llm_goal(fallback, result["parsed"], result["call_id"])
        status.update(
            {
                "status": "completed",
                "call_id": result["call_id"],
                "prompt_hash": result["prompt_hash"],
                "validation": result["validation"],
                "warnings": result["warnings"],
            }
        )
        _write_goal_status(run_dir, status)
        path.write_text(json.dumps(goal, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
    except (InvalidLLMOutputError, LLMProviderError, ValueError) as exc:
        fallback["goal_source"] = "deterministic_fallback_llm_failed"
        status.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        _write_goal_status(run_dir, status)
        path.write_text(json.dumps(fallback, indent=2), encoding="utf-8")
        return path


def validate_research_goal_parse(parsed: Any) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(parsed, dict):
        return ValidationReport(status="failed", errors=["Research goal parse must be a JSON object."])
    tumor = parsed.get("tumor_context")
    therapy = parsed.get("cell_therapy")
    scope = parsed.get("search_scope")
    if not isinstance(tumor, dict):
        errors.append("tumor_context must be an object.")
    if not isinstance(therapy, dict):
        errors.append("cell_therapy must be an object.")
    if not isinstance(scope, dict):
        errors.append("search_scope must be an object.")
    if isinstance(tumor, dict):
        role = str(tumor.get("role") or "").lower()
        if "fixed" not in role:
            warnings.append("tumor_context.role should describe low antigen as a fixed simulation scenario unless explicitly optimized.")
    if isinstance(therapy, dict) and not (therapy.get("candidate_interventions") or therapy.get("candidate_cytokines")):
        errors.append("cell_therapy must list candidate_interventions or candidate_cytokines.")
    for key in ["must_include", "exclude", "retrieval_queries"]:
        if isinstance(scope, dict) and key in scope and not isinstance(scope.get(key), list):
            errors.append(f"search_scope.{key} must be a list.")
    return ValidationReport(status="failed" if errors else "passed", errors=errors, warnings=warnings)


def _merge_llm_goal(fallback: dict[str, Any], parsed: dict[str, Any], call_id: str) -> dict[str, Any]:
    merged = dict(fallback)
    merged.update(
        {
            "objective": parsed.get("research_question") or fallback.get("objective"),
            "goal_source": "llm_research_goal_parser",
            "llm_call_id": call_id,
            "parsed_research_goal": parsed,
            "search_scope": parsed.get("search_scope") or {},
            "fixed_scenario_constraints": parsed.get("fixed_scenario_constraints") or [],
            "intervention_variables": parsed.get("intervention_variables") or fallback.get("candidate_interventions", []),
            "simulation_outputs_needed": parsed.get("simulation_outputs_needed") or [],
        }
    )
    tumor = parsed.get("tumor_context") or {}
    therapy = parsed.get("cell_therapy") or {}
    if tumor.get("antigen_density_condition"):
        merged["antigen_density_condition"] = tumor["antigen_density_condition"]
    if tumor.get("target_antigen"):
        merged["car_target_antigen"] = tumor["target_antigen"]
    candidates = therapy.get("candidate_interventions") or therapy.get("candidate_cytokines")
    if candidates:
        merged["candidate_interventions"] = ["control", *[str(item) for item in candidates if str(item) != "control"]]
    return merged


def _research_question(config: dict[str, Any]) -> str:
    return str(
        (config.get("autoresearch") or {}).get("research_question")
        or (config.get("autoresearch") or {}).get("objective")
        or "Which self-secreting cytokine CAR-T design is best for low-antigen GPC3 liver cancer?"
    )


def _goal_source(config: dict[str, Any]) -> str:
    return str((config.get("autoresearch") or {}).get("goal_source") or "deterministic").lower()


def _write_goal_status(run_dir: Path, status: dict[str, Any]) -> Path:
    path = run_dir / "research_goal_parse_status.json"
    path.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return path
