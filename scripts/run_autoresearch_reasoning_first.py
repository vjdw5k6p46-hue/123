from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from run_autoresearch_parameter_proposal import (  # noqa: E402
    ALLOWED_STRING_PARAMETERS,
    ALLOWED_USER_PARAMETER_RANGES,
    BASE_PHYSICELL_CONFIG,
    CYTOKINE_CHUNKS,
    INTERVENTIONS,
    TUMOR_CHUNKS,
    _call_llm,
    _clean_json,
    _git,
    _load_ranked_chunks,
    _load_yaml,
)


RESEARCH_QUESTION = (
    "Which self-secreting cytokine CAR-T design is best for low-antigen GPC3 liver cancer, "
    "and which cancer_immune PhysiCell user_parameters should change for each cytokine?"
)

CYTOKINE_FINGERPRINT_PARAMETERS = [
    "carT_prolif_rate",
    "p_kill_CAR_T",
    "k_exh",
    "lambda_AICD",
    "carT_exhaustion_per_kill",
    "carT_exhaustion_rate_when_attached",
    "qIFNg_max",
    "alpha_IFNg_aux",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reasoning-first AutoResearch cytokine-to-PhysiCell workflow.")
    parser.add_argument("--config", default="configs/autoresearch_reasoning_gemini.yaml")
    parser.add_argument("--output", default="outputs/autoresearch_reasoning_first_gemini")
    parser.add_argument("--cytokine-chunks", default=str(CYTOKINE_CHUNKS))
    parser.add_argument("--tumor-chunks", default=str(TUMOR_CHUNKS))
    parser.add_argument("--max-cytokine-chunks", type=int, default=80)
    parser.add_argument("--max-tumor-chunks", type=int, default=80)
    parser.add_argument("--base-physicell-config", default=str(BASE_PHYSICELL_CONFIG))
    parser.add_argument("--research-question", default=RESEARCH_QUESTION)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    cfg = _load_yaml(Path(args.config))
    output = Path(args.output)
    if output.exists() and args.force:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    agent_dir = output / "agent_outputs" / "autoresearch_reasoning_agent"
    agent_dir.mkdir(parents=True, exist_ok=True)

    base_config = Path(args.base_physicell_config)
    parameter_dictionary = _load_parameter_dictionary(base_config)
    cytokine_chunks = _load_ranked_chunks(Path(args.cytokine_chunks), max_chunks=args.max_cytokine_chunks, topic="cytokine")
    tumor_chunks = _load_ranked_chunks(Path(args.tumor_chunks), max_chunks=args.max_tumor_chunks, topic="tumor")
    selected_chunks = cytokine_chunks + tumor_chunks
    if not selected_chunks:
        raise SystemExit("No chunks selected for reasoning-first AutoResearch.")

    start = time.time()
    prompt = _build_reasoning_prompt(args.research_question, selected_chunks, parameter_dictionary)
    prompt_hash = _short_hash(prompt)
    call_id = f"autoresearch_reasoning_{prompt_hash}"
    prompt_path = agent_dir / f"{call_id}_prompt.txt"
    raw_path = agent_dir / f"{call_id}_raw_response.txt"
    parsed_path = agent_dir / f"{call_id}_parsed.json"
    validation_path = agent_dir / f"{call_id}_validation.json"
    prompt_path.write_text(prompt, encoding="utf-8")

    raw = _generate(cfg, prompt)
    raw_path.write_text(raw, encoding="utf-8")
    parsed = json.loads(_clean_json(raw))
    parsed_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    validation = validate_reasoning_output(parsed, selected_chunks, parameter_dictionary, call_id)
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")

    (output / "autoresearch_reasoning_output.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "autoresearch_reasoning_validated.json").write_text(json.dumps(validation["validated_output"], indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "reasoning_validation_report.json").write_text(json.dumps(validation["validation_report"], indent=2, ensure_ascii=False), encoding="utf-8")

    export = export_reasoned_configs(validation["validated_output"], base_config, output)
    (output / "physicell_ready_parameters.json").write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path = _write_reasoning_report(output, cfg, args.research_question, validation, export)
    _write_llm_call(output, cfg, call_id, prompt_hash, prompt_path, raw_path, parsed_path, validation_path, validation)
    manifest = {
        "repository": "vjdw5k6p46-hue/123",
        "branch": _git(["branch", "--show-current"]),
        "commit_hash": _git(["rev-parse", "HEAD"]),
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "autoresearch_reasoning_first_parameter_selection",
        "research_question": args.research_question,
        "llm_config": args.config,
        "model": cfg.get("model"),
        "selected_cytokine_chunks": len(cytokine_chunks),
        "selected_tumor_chunks": len(tumor_chunks),
        "valid_changed_parameters": validation["validation_report"]["valid_changed_parameter_count"],
        "rejected_changed_parameters": validation["validation_report"]["rejected_changed_parameter_count"],
        "exported_configs": len(export["interventions"]),
        "external_physicell_executed": False,
        "report": str(report_path),
        "elapsed_seconds": round(time.time() - start, 2),
        "warnings": [
            "Reasoning-first AutoResearch lets the LLM decide which parameters to change or inherit.",
            "Code validates changed parameters for allowed names, ranges, and provenance before XML export.",
            "Generated XML files are PhysiCell model inputs, not simulation outputs or wet-lab validation.",
        ],
    }
    (output / "autoresearch_reasoning_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


def _generate(cfg: dict[str, Any], prompt: str) -> str:
    if cfg.get("provider") == "mock":
        response = (cfg.get("mock_responses") or {}).get("autoresearch_reasoning_agent")
        if response is None:
            raise RuntimeError("Mock provider requires mock_responses.autoresearch_reasoning_agent.")
        return response if isinstance(response, str) else json.dumps(response)
    env_name = str(cfg.get("api_key_env") or "GEMINI_API_KEY")
    if not os.getenv(env_name):
        raise SystemExit(f"Missing API key env var {env_name}.")
    return _call_llm(cfg, prompt)


def _load_parameter_dictionary(base_config: Path) -> dict[str, Any]:
    if not base_config.exists():
        raise FileNotFoundError(f"PhysiCell base config not found: {base_config}")
    root = ET.parse(base_config).getroot()
    user = root.find("user_parameters")
    if user is None:
        raise ValueError("Base PhysiCell XML has no <user_parameters> block.")
    parameters = []
    for child in list(user):
        name = child.tag
        parameters.append(
            {
                "name": name,
                "type": child.attrib.get("type", "double"),
                "units": child.attrib.get("units", "dimensionless"),
                "default_value": (child.text or "").strip(),
                "allowed_for_llm_change": name in ALLOWED_USER_PARAMETER_RANGES or name in ALLOWED_STRING_PARAMETERS,
                "allowed_range": ALLOWED_USER_PARAMETER_RANGES.get(name),
                "allowed_values": sorted(ALLOWED_STRING_PARAMETERS.get(name, [])),
            }
        )
    return {
        "base_config": str(base_config),
        "parameters": parameters,
        "llm_changeable_numeric": sorted(ALLOWED_USER_PARAMETER_RANGES),
        "llm_changeable_string": {key: sorted(values) for key, values in ALLOWED_STRING_PARAMETERS.items()},
    }


def _build_reasoning_prompt(research_question: str, chunks: list[dict[str, Any]], parameter_dictionary: dict[str, Any]) -> str:
    compact_chunks = []
    for chunk in chunks:
        compact_chunks.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "topic": chunk.get("autoresearch_topic"),
                "title": chunk.get("title"),
                "doi": chunk.get("doi"),
                "pmid": chunk.get("pmid"),
                "section": chunk.get("section"),
                "text": str(chunk.get("text") or "")[:1800],
            }
        )
    schema = {
        "research_question": research_question,
        "cytokine_designs": [
            {
                "cytokine": "one of exactly: control, IL-2, IL-7, IL-12, IL-15, IL-18",
                "mechanistic_hypothesis": "evidence-linked hypothesis",
                "mechanisms_considered": [],
                "functional_fingerprint": {
                    "proliferation": "increase|decrease|no_change plus evidence-linked rationale",
                    "persistence_or_exhaustion": "increase|decrease|no_change plus evidence-linked rationale",
                    "cytotoxicity": "increase|decrease|no_change plus evidence-linked rationale",
                    "IFNg_axis": "increase|decrease|no_change plus evidence-linked rationale",
                    "AICD_or_toxicity": "increase|decrease|no_change plus evidence-linked rationale",
                    "confidence": 0.0,
                },
                "parameters_to_change": [
                    {
                        "physicell_user_parameter": "allowed user parameter name",
                        "proposed_value": "number or allowed string",
                        "unit": "reported unit or dimensionless",
                        "expected_effect_direction": "increase|decrease|set_mode|other",
                        "evidence_chunk_ids": [],
                        "supporting_citations": [{"title": "from supplied metadata", "doi": "if supplied", "pmid": "if supplied"}],
                        "rationale": "why this parameter should change for this cytokine",
                        "confidence": 0.0,
                        "assumptions": [],
                    }
                ],
                "parameters_intentionally_inherited": [
                    {
                        "physicell_user_parameter": "base parameter name",
                        "reason": "why no cytokine-specific change is warranted",
                        "confidence": 0.0,
                    }
                ],
                "unsupported_parameters_not_changed": [
                    {
                        "physicell_user_parameter": "base parameter name",
                        "reason": "why evidence is insufficient",
                    }
                ],
                "simulation_expectation": "expected qualitative simulation behavior",
                "evidence_trace": [{"chunk_id": "supplied chunk id", "point": "short point"}],
            }
        ],
        "cross_cytokine_comparison": [],
        "research_gaps": [],
    }
    parameter_context = {
        "base_config": parameter_dictionary["base_config"],
        "llm_changeable_numeric": parameter_dictionary["llm_changeable_numeric"],
        "llm_changeable_string": parameter_dictionary["llm_changeable_string"],
        "cytokine_fingerprint_parameters_that_should_differ_when_supported": CYTOKINE_FINGERPRINT_PARAMETERS,
        "base_defaults_for_changeable_parameters": [
            row
            for row in parameter_dictionary["parameters"]
            if row["allowed_for_llm_change"]
        ],
    }
    return (
        "You are a reasoning-first AutoResearch agent for a CAR-T cancer_immune PhysiCell model.\n"
        "Answer the user research question by reasoning from supplied paper chunks and the actual PhysiCell user_parameter dictionary.\n"
        "Each cytokine has a distinct biological effect on T cells. For every non-control cytokine, first build a cytokine-specific T-cell functional fingerprint covering proliferation, persistence/exhaustion, cytotoxicity, IFNg axis, and AICD/toxicity.\n"
        "Then translate that fingerprint into PhysiCell user_parameters. Do not leave all T-cell functional parameters inherited for a cytokine unless the supplied evidence truly gives no support; if evidence is directional but not quantitative, propose a bounded low-confidence value and state the assumption.\n"
        "For each non-control cytokine, parameters_to_change should normally include aux_cytokine_name, aux_mode, qmax_aux_engineered, and at least two cytokine_fingerprint_parameters_that_should_differ_when_supported.\n"
        "Do NOT force every cytokine to use the same values. Different cytokines should have different T-cell fingerprint values when their mechanisms differ.\n"
        "Return one separate cytokine_design object per cytokine. Do not combine cytokines with pipe-separated labels such as IL-12|IL-15.\n"
        "For unchanged parameters, explicitly separate intentional inheritance from unsupported/no-evidence changes.\n"
        "Use only supplied chunks. Do not invent citations, DOI, PMID, wet-lab values, LLM outputs, PhysiCell outputs, or papers.\n"
        "Low antigen means tumor/cancer cell surface antigen expression or density, especially GPC3/glypican-3 on HCC/liver cancer cells.\n"
        "This task is specifically about transfected/engineered CAR-T cells that secrete IL-2, IL-7, IL-12, IL-15, or IL-18 themselves. Therefore every non-control cytokine design must set aux_mode='armored' and the matching aux_cytokine_name. Do not use aux_mode='bath' for these self-secreting designs.\n"
        "Return strict JSON only. No markdown.\n"
        f"Research question:\n{research_question}\n"
        "Allowed output schema shape:\n"
        + json.dumps(schema, ensure_ascii=False)
        + "\nPhysiCell parameter dictionary:\n"
        + json.dumps(parameter_context, ensure_ascii=False)
        + "\nEvidence chunks:\n"
        + json.dumps(compact_chunks, ensure_ascii=False)
    )


def validate_reasoning_output(
    parsed: dict[str, Any],
    chunks: list[dict[str, Any]],
    parameter_dictionary: dict[str, Any],
    call_id: str,
) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        raise TypeError(f"Reasoning response must be JSON object, got {type(parsed).__name__}")
    chunk_map = {str(chunk.get("chunk_id")): chunk for chunk in chunks}
    base_parameter_names = {row["name"] for row in parameter_dictionary["parameters"]}
    validated_designs = []
    rejected_parameters = []
    fingerprint_audit = []
    valid_count = 0
    for design_index, design in enumerate(parsed.get("cytokine_designs") or []):
        cytokine = str(design.get("cytokine") or "").strip()
        if cytokine not in INTERVENTIONS:
            rejected_parameters.append({"design": cytokine, "errors": [f"unsupported cytokine/intervention: {cytokine}"]})
            continue
        valid_changes = []
        for param_index, proposal in enumerate(design.get("parameters_to_change") or []):
            normalized, errors = _validate_changed_parameter(proposal, chunk_map, cytokine, call_id, design_index, param_index)
            if (
                not errors
                and cytokine != "control"
                and normalized
                and normalized["physicell_user_parameter"] == "aux_mode"
                and normalized["proposed_value"] != "armored"
            ):
                errors.append("self-secreting cytokine CAR-T designs must use aux_mode='armored'")
            if errors:
                rejected_parameters.append({"cytokine": cytokine, "proposal": proposal, "errors": errors})
            else:
                valid_changes.append(normalized)
                valid_count += 1
        inherited = _validate_name_reason_list(design.get("parameters_intentionally_inherited") or [], base_parameter_names)
        unsupported = _validate_name_reason_list(design.get("unsupported_parameters_not_changed") or [], base_parameter_names)
        fingerprint_params = sorted(
            {
                row["physicell_user_parameter"]
                for row in valid_changes
                if row["physicell_user_parameter"] in CYTOKINE_FINGERPRINT_PARAMETERS
            }
        )
        fingerprint_audit.append(
            {
                "cytokine": cytokine,
                "changed_fingerprint_parameters": fingerprint_params,
                "changed_fingerprint_parameter_count": len(fingerprint_params),
                "functional_fingerprint": design.get("functional_fingerprint") or {},
            }
        )
        validated_designs.append(
            {
                "cytokine": cytokine,
                "mechanistic_hypothesis": str(design.get("mechanistic_hypothesis") or ""),
                "mechanisms_considered": design.get("mechanisms_considered") or [],
                "functional_fingerprint": design.get("functional_fingerprint") or {},
                "parameters_to_change": valid_changes,
                "parameters_intentionally_inherited": inherited,
                "unsupported_parameters_not_changed": unsupported,
                "simulation_expectation": str(design.get("simulation_expectation") or ""),
                "evidence_trace": design.get("evidence_trace") or [],
                "llm_call_id": call_id,
            }
        )
    validated_output = {
        "research_question": parsed.get("research_question"),
        "cytokine_designs": validated_designs,
        "cross_cytokine_comparison": parsed.get("cross_cytokine_comparison") or [],
        "research_gaps": parsed.get("research_gaps") or [],
    }
    report = {
        "status": "validated" if validated_designs else "no_valid_designs",
        "valid_design_count": len(validated_designs),
        "valid_changed_parameter_count": valid_count,
        "rejected_changed_parameter_count": len(rejected_parameters),
        "rejected_changed_parameters": rejected_parameters,
        "cytokine_fingerprint_audit": fingerprint_audit,
        "warnings": [
            "Only parameters_to_change are exported to XML; inherited and unsupported parameters are audit annotations.",
            "Validation checks parameter names, ranges, and provenance. It does not prove biological correctness.",
        ],
    }
    return {"validated_output": validated_output, "validation_report": report}


def _validate_changed_parameter(
    proposal: dict[str, Any],
    chunks: dict[str, dict[str, Any]],
    cytokine: str,
    call_id: str,
    design_index: int,
    param_index: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors = []
    parameter = str(proposal.get("physicell_user_parameter") or "").strip()
    if parameter not in ALLOWED_USER_PARAMETER_RANGES and parameter not in ALLOWED_STRING_PARAMETERS:
        errors.append(f"unsupported physicell_user_parameter: {parameter}")
    chunk_ids = [str(value) for value in proposal.get("evidence_chunk_ids") or [] if value]
    if not chunk_ids:
        errors.append("missing evidence_chunk_ids")
    missing_chunks = [chunk_id for chunk_id in chunk_ids if chunk_id not in chunks]
    if missing_chunks:
        errors.append(f"evidence_chunk_ids not in supplied context: {missing_chunks[:5]}")
    confidence = _as_float(proposal.get("confidence"))
    if confidence is None or not 0 <= confidence <= 1:
        errors.append("confidence must be numeric between 0 and 1")
    value = proposal.get("proposed_value")
    if parameter in ALLOWED_USER_PARAMETER_RANGES:
        numeric = _as_float(value)
        if numeric is None:
            errors.append("proposed_value must be numeric")
        else:
            low, high = ALLOWED_USER_PARAMETER_RANGES[parameter]
            if numeric < low or numeric > high:
                errors.append(f"proposed_value {numeric} outside allowed range [{low}, {high}]")
            value = numeric
    if parameter in ALLOWED_STRING_PARAMETERS:
        text = str(value)
        if text not in ALLOWED_STRING_PARAMETERS[parameter]:
            errors.append(f"proposed_value {text!r} is not allowed for {parameter}")
        value = text
    citations = proposal.get("supporting_citations") or []
    if not citations:
        citations = _citations_from_chunks(chunk_ids, chunks)
    if not citations:
        errors.append("missing supporting_citations")
    else:
        for citation in citations:
            if not isinstance(citation, dict) or not any(citation.get(key) for key in ["title", "doi", "pmid", "source_paper_id"]):
                errors.append("supporting_citations must include title, DOI, PMID, or source_paper_id from supplied metadata")
                break
    if errors:
        return None, errors
    return {
        "proposal_id": f"{call_id}_design_{design_index:02d}_parameter_{param_index:02d}",
        "cytokine": cytokine,
        "physicell_user_parameter": parameter,
        "proposed_value": value,
        "unit": proposal.get("unit") or "not_reported",
        "expected_effect_direction": proposal.get("expected_effect_direction") or "not_reported",
        "evidence_chunk_ids": chunk_ids,
        "supporting_citations": citations,
        "rationale": str(proposal.get("rationale") or ""),
        "confidence": round(float(confidence), 4),
        "assumptions": proposal.get("assumptions") or [],
        "llm_call_id": call_id,
        "validation_status": "passed",
    }, []


def _citations_from_chunks(chunk_ids: list[str], chunks: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    citations = []
    seen = set()
    for chunk_id in chunk_ids:
        chunk = chunks.get(chunk_id)
        if not chunk:
            continue
        citation = {
            key: str(chunk.get(key) or "").strip()
            for key in ["title", "doi", "pmid", "source_paper_id"]
            if str(chunk.get(key) or "").strip()
        }
        if not citation:
            continue
        marker = tuple(sorted(citation.items()))
        if marker in seen:
            continue
        seen.add(marker)
        citations.append(citation)
    return citations


def _validate_name_reason_list(rows: list[dict[str, Any]], base_parameter_names: set[str]) -> list[dict[str, Any]]:
    valid = []
    for row in rows:
        name = str(row.get("physicell_user_parameter") or "").strip()
        if name in base_parameter_names:
            valid.append(
                {
                    "physicell_user_parameter": name,
                    "reason": str(row.get("reason") or ""),
                    "confidence": _as_float(row.get("confidence")),
                }
            )
    return valid


def export_reasoned_configs(validated_output: dict[str, Any], base_config: Path, output: Path) -> dict[str, Any]:
    out_dir = output / "physicell_ready_configs"
    out_dir.mkdir(parents=True, exist_ok=True)
    interventions = []
    for design in validated_output.get("cytokine_designs") or []:
        cytokine = design["cytokine"]
        params = {row["physicell_user_parameter"]: row["proposed_value"] for row in design.get("parameters_to_change") or []}
        if not params:
            continue
        tree = ET.parse(base_config)
        root = tree.getroot()
        _apply_user_parameters(root, params)
        name = re.sub(r"[^A-Za-z0-9_]+", "_", cytokine.lower()).strip("_")
        xml_path = out_dir / f"PhysiCell_settings_reasoned_{name}.xml"
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)
        interventions.append(
            {
                "intervention_name": cytokine,
                "config_path": str(xml_path),
                "changed_user_parameters": params,
                "mechanistic_hypothesis": design.get("mechanistic_hypothesis"),
                "parameters_intentionally_inherited": design.get("parameters_intentionally_inherited", []),
                "unsupported_parameters_not_changed": design.get("unsupported_parameters_not_changed", []),
                "source_design": design,
            }
        )
    return {
        "base_config": str(base_config),
        "output_dir": str(out_dir),
        "note": "Reasoning-first LLM-selected PhysiCell user_parameter changes. Inherited parameters remain at base config values.",
        "interventions": interventions,
    }


def _apply_user_parameters(root: ET.Element, values: dict[str, Any]) -> None:
    user = root.find("user_parameters")
    if user is None:
        raise ValueError("Base PhysiCell XML has no <user_parameters> block.")
    existing = {child.tag: child for child in list(user)}
    for key, value in values.items():
        node = existing.get(key)
        if node is None:
            node = ET.SubElement(user, key)
            node.set("type", "string" if isinstance(value, str) else "double")
            node.set("units", "dimensionless")
        node.text = str(value) if isinstance(value, str) else f"{float(value):.12g}"


def _write_llm_call(
    output: Path,
    cfg: dict[str, Any],
    call_id: str,
    prompt_hash: str,
    prompt_path: Path,
    raw_path: Path,
    parsed_path: Path,
    validation_path: Path,
    validation: dict[str, Any],
) -> None:
    record = {
        "call_id": call_id,
        "agent_name": "autoresearch_reasoning_agent",
        "provider": cfg.get("provider"),
        "model": cfg.get("model"),
        "base_url": cfg.get("base_url"),
        "temperature": cfg.get("temperature", 0),
        "prompt_hash": prompt_hash,
        "input_artifacts": [],
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "parsed_json_path": str(parsed_path),
        "validation_path": str(validation_path),
        "schema_validation_status": validation["validation_report"]["status"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "warnings": validation["validation_report"]["warnings"],
    }
    with (output / "llm_calls.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_reasoning_report(
    output: Path,
    cfg: dict[str, Any],
    research_question: str,
    validation: dict[str, Any],
    export: dict[str, Any],
) -> Path:
    path = output / "autoresearch_reasoning_report.md"
    lines = [
        "# Reasoning-First AutoResearch Report",
        "",
        f"Model: `{cfg.get('model')}`",
        f"Research question: {research_question}",
        "",
        "The LLM first reasoned about mechanisms and then selected which PhysiCell user_parameters should change.",
        "Code validated only changed parameters for allowed names, ranges, and supplied-chunk provenance before XML export.",
        "",
        "These artifacts are model inputs and audit records, not wet-lab validation or PhysiCell simulation outputs.",
        "",
        "## Validation",
        "",
        f"- Valid designs: `{validation['validation_report']['valid_design_count']}`",
        f"- Valid changed parameters: `{validation['validation_report']['valid_changed_parameter_count']}`",
        f"- Rejected changed parameters: `{validation['validation_report']['rejected_changed_parameter_count']}`",
        "",
        "## Cytokine Designs",
    ]
    for item in export.get("interventions", []):
        changed = ", ".join(sorted(item.get("changed_user_parameters", {})))
        lines.extend(
            [
                f"### {item['intervention_name']}",
                "",
                f"Config: `{item['config_path']}`",
                f"Changed parameters: {changed or 'none'}",
                f"Hypothesis: {item.get('mechanistic_hypothesis') or 'not reported'}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _short_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    raise SystemExit(main())
