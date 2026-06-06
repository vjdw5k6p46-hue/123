from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

spec = importlib.util.spec_from_file_location("reasoning", SCRIPTS_DIR / "run_autoresearch_reasoning_first.py")
reasoning = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(reasoning)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ask an LLM to critique PhysiCell AutoResearch results and propose a next refinement round.")
    parser.add_argument("--config", default="configs/autoresearch_reasoning_gemini.yaml")
    parser.add_argument("--simulation-summary", required=True)
    parser.add_argument("--parameter-table", required=True)
    parser.add_argument("--reasoning-json", required=True)
    parser.add_argument("--output", default="outputs/autoresearch_simulation_refinement")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    output = Path(args.output)
    if output.exists() and args.force:
        shutil.rmtree(output)
    if output.exists():
        raise SystemExit(f"Output already exists: {output}. Use --force to overwrite.")
    output.mkdir(parents=True)
    agent_dir = output / "agent_outputs" / "simulation_refinement_agent"
    agent_dir.mkdir(parents=True)

    cfg = reasoning._load_yaml(Path(args.config))
    simulation_rows = read_csv(Path(args.simulation_summary))
    parameter_rows = read_csv(Path(args.parameter_table))
    source_reasoning = json.loads(Path(args.reasoning_json).read_text(encoding="utf-8"))
    prompt = build_prompt(simulation_rows, parameter_rows, source_reasoning)
    call_id = f"simulation_refinement_{reasoning._short_hash(prompt)}"
    (agent_dir / f"{call_id}_prompt.txt").write_text(prompt, encoding="utf-8")
    raw = reasoning._generate(cfg, prompt)
    (agent_dir / f"{call_id}_raw_response.txt").write_text(raw, encoding="utf-8")
    parsed = json.loads(reasoning._clean_json(raw))
    (agent_dir / f"{call_id}_parsed.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    validation = validate_refinement(parsed)
    (agent_dir / f"{call_id}_validation.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "simulation_refinement_recommendations.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "simulation_refinement_validation.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(output / "simulation_refinement_report.md", parsed, validation, args)
    manifest = {
        "mode": "simulation_critique_and_refinement",
        "model": cfg.get("model"),
        "call_id": call_id,
        "simulation_summary": args.simulation_summary,
        "parameter_table": args.parameter_table,
        "reasoning_json": args.reasoning_json,
        "recommendations": str(output / "simulation_refinement_recommendations.json"),
        "validation": str(output / "simulation_refinement_validation.json"),
        "warnings": [
            "Refinement recommendations are LLM critique of in silico outputs.",
            "This script does not fabricate wet-lab validation and does not execute PhysiCell.",
            "Human review is required before accepting revised parameters as manuscript evidence.",
        ],
    }
    (output / "simulation_refinement_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)
    return 0


def build_prompt(simulation_rows: list[dict[str, str]], parameter_rows: list[dict[str, str]], source_reasoning: dict[str, Any]) -> str:
    schema = {
        "result_interpretation": [],
        "ranking": [{"rank": 1, "cytokine": "IL-15", "reason": "based only on supplied simulation metrics"}],
        "unexpected_findings": [],
        "parameter_sensitivity_hypotheses": [],
        "next_round_parameter_recommendations": [
            {
                "cytokine": "IL-2|IL-7|IL-12|IL-15|IL-18",
                "physicell_user_parameter": "allowed parameter name from current table",
                "current_value": "from current parameter table",
                "recommended_value": "bounded numeric or allowed string",
                "direction": "increase|decrease|keep|uncertain",
                "basis": "simulation_result|literature_reasoning|both",
                "rationale": "explain using supplied metrics and prior reasoning only",
                "confidence": 0.0,
                "requires_new_literature_review": False,
            }
        ],
        "do_not_change": [],
        "recommended_next_experiment": [],
        "limitations": [],
    }
    return (
        "You are the critique/refinement agent in an AutoResearch loop for a CAR-T PhysiCell model.\n"
        "Critique the supplied in silico simulation results and current cytokine fingerprints. Propose a next refinement round only from supplied metrics, current parameters, and prior LLM reasoning.\n"
        "Do not invent citations, wet-lab values, PhysiCell outputs, LLM outputs, or papers. Do not claim biological validation.\n"
        "If a finding may be a simulator artifact or single-run instability, say so and recommend replicate/sensitivity testing.\n"
        "Return strict JSON only. No markdown.\n"
        "Output schema shape:\n"
        + json.dumps(schema, ensure_ascii=False)
        + "\nSimulation metrics:\n"
        + json.dumps(simulation_rows, ensure_ascii=False)
        + "\nCurrent cytokine parameter table:\n"
        + json.dumps(parameter_rows, ensure_ascii=False)
        + "\nPrior reasoning summary:\n"
        + json.dumps(source_reasoning, ensure_ascii=False)[:50000]
    )


def validate_refinement(parsed: dict[str, Any]) -> dict[str, Any]:
    allowed_params = set(reasoning.ALLOWED_USER_PARAMETER_RANGES) | set(reasoning.ALLOWED_STRING_PARAMETERS)
    allowed_cytokines = {"IL-2", "IL-7", "IL-12", "IL-15", "IL-18"}
    errors = []
    recommendations = parsed.get("next_round_parameter_recommendations") or []
    for index, item in enumerate(recommendations):
        cytokine = str(item.get("cytokine") or "")
        parameter = str(item.get("physicell_user_parameter") or "")
        if cytokine not in allowed_cytokines:
            errors.append(f"recommendation {index}: unsupported cytokine {cytokine!r}")
        if parameter not in allowed_params:
            errors.append(f"recommendation {index}: unsupported parameter {parameter!r}")
        confidence = as_float(item.get("confidence"))
        if confidence is None or not 0 <= confidence <= 1:
            errors.append(f"recommendation {index}: confidence must be 0..1")
        value = item.get("recommended_value")
        if parameter in reasoning.ALLOWED_USER_PARAMETER_RANGES:
            numeric = as_float(value)
            if numeric is None:
                errors.append(f"recommendation {index}: recommended_value must be numeric for {parameter}")
            else:
                low, high = reasoning.ALLOWED_USER_PARAMETER_RANGES[parameter]
                if numeric < low or numeric > high:
                    errors.append(f"recommendation {index}: value {numeric} outside range [{low}, {high}]")
        if parameter in reasoning.ALLOWED_STRING_PARAMETERS and str(value) not in reasoning.ALLOWED_STRING_PARAMETERS[parameter]:
            errors.append(f"recommendation {index}: value {value!r} not allowed for {parameter}")
    return {
        "status": "passed" if not errors else "failed",
        "recommendation_count": len(recommendations),
        "errors": errors,
        "warnings": [
            "Validation checks schema/range only; it does not prove biological correctness.",
            "Recommendations are not automatically applied to XML configs.",
        ],
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_report(path: Path, parsed: dict[str, Any], validation: dict[str, Any], args: argparse.Namespace) -> None:
    lines = [
        "# AutoResearch Simulation Refinement",
        "",
        "This report is an LLM critique of supplied in silico PhysiCell metrics. It is not wet-lab validation.",
        "",
        f"- Simulation summary: `{args.simulation_summary}`",
        f"- Parameter table: `{args.parameter_table}`",
        f"- Validation status: `{validation['status']}`",
        f"- Recommendation count: `{validation['recommendation_count']}`",
        "",
        "## Ranking",
    ]
    for row in parsed.get("ranking") or []:
        lines.append(f"- `{row.get('rank')}` `{row.get('cytokine')}`: {row.get('reason')}")
    lines.extend(["", "## Recommendations"])
    for item in parsed.get("next_round_parameter_recommendations") or []:
        lines.append(
            f"- `{item.get('cytokine')}` `{item.get('physicell_user_parameter')}`: "
            f"{item.get('current_value')} -> {item.get('recommended_value')} "
            f"({item.get('direction')}, confidence={item.get('confidence')})"
        )
    lines.extend(["", "## Limitations"])
    for item in parsed.get("limitations") or []:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
