from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import filter_autoresearch_relevant_chunks as relevance  # noqa: E402

spec = importlib.util.spec_from_file_location("reasoning", SCRIPTS_DIR / "run_autoresearch_reasoning_first.py")
reasoning = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(reasoning)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run per-cytokine AutoResearch LLM fingerprint extraction.")
    parser.add_argument("--config", default="configs/autoresearch_reasoning_gemini.yaml")
    parser.add_argument("--cytokine-chunks", default=str(reasoning.CYTOKINE_CHUNKS))
    parser.add_argument("--tumor-chunks", default=str(reasoning.TUMOR_CHUNKS))
    parser.add_argument("--base-physicell-config", default=str(reasoning.BASE_PHYSICELL_CONFIG))
    parser.add_argument("--output", default="outputs/autoresearch_per_cytokine_fingerprints")
    parser.add_argument("--max-cytokine-chunks", type=int, default=30)
    parser.add_argument("--retry-cytokine-chunks", type=int, default=55)
    parser.add_argument("--max-tumor-chunks", type=int, default=15)
    parser.add_argument("--min-effective-fingerprint-params", type=int, default=2)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    output = Path(args.output)
    if output.exists() and args.force:
        shutil.rmtree(output)
    if output.exists():
        raise SystemExit(f"Output already exists: {output}. Use --force to overwrite.")
    output.mkdir(parents=True)
    agent_dir = output / "agent_outputs" / "autoresearch_reasoning_agent"
    agent_dir.mkdir(parents=True)

    cfg = reasoning._load_yaml(Path(args.config))
    base_config = Path(args.base_physicell_config)
    parameter_dictionary = reasoning._load_parameter_dictionary(base_config)
    base_defaults = _base_defaults(parameter_dictionary)
    cytokine_rows = relevance.read_jsonl(Path(args.cytokine_chunks))
    tumor_rows = relevance.read_jsonl(Path(args.tumor_chunks))
    tumor_chunks = _select_tumor_chunks(tumor_rows, args.max_tumor_chunks)

    combined_designs = []
    combined_rejected = []
    per_cytokine_calls = []
    effective_audit = []

    for cytokine in relevance.CYTOKINES:
        selected = _select_cytokine_chunks(cytokine_rows, cytokine, args.max_cytokine_chunks) + tumor_chunks
        result = _run_one_cytokine(
            cytokine=cytokine,
            selected_chunks=selected,
            cfg=cfg,
            parameter_dictionary=parameter_dictionary,
            base_defaults=base_defaults,
            agent_dir=agent_dir,
            min_effective=args.min_effective_fingerprint_params,
            attempt_label="primary",
        )
        if result["effective_fingerprint_parameter_count"] < args.min_effective_fingerprint_params:
            retry_selected = _select_cytokine_chunks(cytokine_rows, cytokine, args.retry_cytokine_chunks) + tumor_chunks
            retry = _run_one_cytokine(
                cytokine=cytokine,
                selected_chunks=retry_selected,
                cfg=cfg,
                parameter_dictionary=parameter_dictionary,
                base_defaults=base_defaults,
                agent_dir=agent_dir,
                min_effective=args.min_effective_fingerprint_params,
                attempt_label="retry",
            )
            if retry["effective_fingerprint_parameter_count"] >= result["effective_fingerprint_parameter_count"]:
                result = retry
        combined_designs.extend(result["designs"])
        combined_rejected.extend(result["rejected"])
        per_cytokine_calls.append(result["call_summary"])
        effective_audit.append(result["effective_audit"])
        print(
            f"[{cytokine}] attempt={result['call_summary']['attempt_label']} "
            f"valid_params={result['call_summary']['valid_params']} "
            f"effective_fingerprint={result['effective_fingerprint_parameter_count']} "
            f"rejected={result['call_summary']['rejected_params']}",
            flush=True,
        )

    order = {cytokine: index for index, cytokine in enumerate(relevance.CYTOKINES)}
    combined_designs.sort(key=lambda design: order.get(design.get("cytokine"), 99))
    validated_output = {
        "research_question": reasoning.RESEARCH_QUESTION,
        "cytokine_designs": combined_designs,
        "cross_cytokine_comparison": [],
        "research_gaps": [],
    }
    export = reasoning.export_reasoned_configs(validated_output, base_config, output)
    total_valid = sum(len(design.get("parameters_to_change") or []) for design in combined_designs)
    report = {
        "status": "validated" if combined_designs else "no_valid_designs",
        "valid_design_count": len(combined_designs),
        "valid_changed_parameter_count": total_valid,
        "rejected_changed_parameter_count": len(combined_rejected),
        "rejected_changed_parameters": combined_rejected,
        "effective_cytokine_fingerprint_audit": effective_audit,
        "per_cytokine_calls": per_cytokine_calls,
        "warnings": [
            "Per-cytokine LLM AutoResearch run; output parameters passed range and provenance validation.",
            "Effective fingerprint audit compares proposed values to the base PhysiCell user_parameter defaults.",
            "These are model inputs, not wet-lab validation or real PhysiCell outputs until a simulator run is executed.",
        ],
    }
    manifest = {
        "mode": "per_cytokine_reasoning_first_with_effective_fingerprint_audit",
        "model": cfg.get("model"),
        "valid_design_count": len(combined_designs),
        "valid_changed_parameter_count": total_valid,
        "rejected_changed_parameter_count": len(combined_rejected),
        "exported_configs": len(export.get("interventions", [])),
        "output": str(output),
        "min_effective_fingerprint_params": args.min_effective_fingerprint_params,
        "per_cytokine_calls": per_cytokine_calls,
    }
    (output / "autoresearch_reasoning_validated.json").write_text(json.dumps(validated_output, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "reasoning_validation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "physicell_ready_parameters.json").write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "autoresearch_reasoning_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_parameter_table(output, export)
    print(json.dumps(manifest, indent=2))
    return 0


def _run_one_cytokine(
    *,
    cytokine: str,
    selected_chunks: list[dict[str, Any]],
    cfg: dict[str, Any],
    parameter_dictionary: dict[str, Any],
    base_defaults: dict[str, Any],
    agent_dir: Path,
    min_effective: int,
    attempt_label: str,
) -> dict[str, Any]:
    research_question = (
        reasoning.RESEARCH_QUESTION
        + f" Focus only on {cytokine}. Return exactly one cytokine_design for {cytokine}; do not return other cytokines or control. "
        + "For T-cell fingerprint parameters, if expected_effect_direction is increase or decrease, proposed_value must differ from the base default in the PhysiCell dictionary. "
        + f"At least {min_effective} T-cell fingerprint parameters should have effective cytokine-specific values when evidence is directional. "
        + "Do not use a base default value as evidence of change. Use low confidence if quantitative evidence is weak, but choose a bounded directional value. "
        + "Every parameter must cite supplied chunk_ids."
    )
    prompt = reasoning._build_reasoning_prompt(research_question, selected_chunks, parameter_dictionary)
    call_id = f"autoresearch_reasoning_{cytokine.lower().replace('-', '')}_{attempt_label}_{reasoning._short_hash(prompt)}"
    (agent_dir / f"{call_id}_prompt.txt").write_text(prompt, encoding="utf-8")
    raw = reasoning._generate(cfg, prompt)
    (agent_dir / f"{call_id}_raw_response.txt").write_text(raw, encoding="utf-8")
    parsed = json.loads(reasoning._clean_json(raw))
    (agent_dir / f"{call_id}_parsed.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    validated = reasoning.validate_reasoning_output(parsed, selected_chunks, parameter_dictionary, call_id)
    (agent_dir / f"{call_id}_validation.json").write_text(json.dumps(validated["validation_report"], indent=2, ensure_ascii=False), encoding="utf-8")
    designs = [design for design in validated["validated_output"]["cytokine_designs"] if design.get("cytokine") == cytokine]
    effective = _effective_fingerprint_audit(cytokine, designs, base_defaults)
    return {
        "designs": designs,
        "rejected": validated["validation_report"].get("rejected_changed_parameters", []),
        "effective_audit": effective,
        "effective_fingerprint_parameter_count": len(effective["effective_changed_fingerprint_parameters"]),
        "call_summary": {
            "cytokine": cytokine,
            "attempt_label": attempt_label,
            "call_id": call_id,
            "selected_chunks": len(selected_chunks),
            "valid_designs": len(designs),
            "valid_params": sum(len(design.get("parameters_to_change") or []) for design in designs),
            "rejected_params": validated["validation_report"].get("rejected_changed_parameter_count", 0),
            "effective_fingerprint_parameter_count": len(effective["effective_changed_fingerprint_parameters"]),
        },
    }


def _select_cytokine_chunks(rows: list[dict[str, Any]], cytokine: str, limit: int) -> list[dict[str, Any]]:
    scored = []
    for row in rows:
        score, reasons = relevance.score_cytokine_chunk(row, cytokine)
        if score > 0:
            scored.append((score, int(row.get("word_count") or 0), reasons, row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [
        dict(row, autoresearch_topic="cytokine", target_cytokine=cytokine, relevance_score=score, relevance_reasons=reasons)
        for score, _words, reasons, row in scored[:limit]
    ]


def _select_tumor_chunks(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    scored = []
    for row in rows:
        score, reasons = relevance.score_tumor_chunk(row)
        if score > 0:
            scored.append((score, int(row.get("word_count") or 0), reasons, row))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [dict(row, autoresearch_topic="tumor", relevance_score=score, relevance_reasons=reasons) for score, _words, reasons, row in scored[:limit]]


def _base_defaults(parameter_dictionary: dict[str, Any]) -> dict[str, Any]:
    return {row["name"]: row.get("value") for row in parameter_dictionary.get("parameters", [])}


def _effective_fingerprint_audit(cytokine: str, designs: list[dict[str, Any]], base_defaults: dict[str, Any]) -> dict[str, Any]:
    effective = []
    proposed = []
    for design in designs:
        for row in design.get("parameters_to_change") or []:
            name = row.get("physicell_user_parameter")
            if name not in reasoning.CYTOKINE_FINGERPRINT_PARAMETERS:
                continue
            proposed.append(name)
            if _value_differs(row.get("proposed_value"), base_defaults.get(name)):
                effective.append(name)
    return {
        "cytokine": cytokine,
        "proposed_fingerprint_parameters": sorted(set(proposed)),
        "effective_changed_fingerprint_parameters": sorted(set(effective)),
        "effective_changed_fingerprint_parameter_count": len(set(effective)),
    }


def _value_differs(left: Any, right: Any) -> bool:
    try:
        return abs(float(left) - float(right)) > 1e-12
    except (TypeError, ValueError):
        return str(left) != str(right)


def _write_parameter_table(output: Path, export: dict[str, Any]) -> None:
    keys = [
        "aux_cytokine_name",
        "aux_mode",
        "qmax_aux_engineered",
        "alpha_IFNg_aux",
        "p_kill_CAR_T",
        "carT_prolif_rate",
        "k_exh",
        "lambda_AICD",
        "carT_exhaustion_per_kill",
        "carT_exhaustion_rate_when_attached",
        "qIFNg_max",
        "tumor_antigen_density",
        "k_PDL1_up",
    ]
    rows = []
    for item in export.get("interventions", []):
        params = item.get("changed_user_parameters", {})
        rows.append({"intervention": item.get("intervention_name"), **{key: params.get(key, "") for key in keys}})
    with (output / "cytokine_parameter_table.csv").open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(handle, fieldnames=["intervention"] + keys)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
