from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def write_autoresearch_report(run_dir: Path, config: dict[str, Any]) -> dict[str, str]:
    goal = _load_json(run_dir / "research_goal.json", {})
    kb = _load_json(run_dir / "knowledge_base" / "index.json", {})
    hypotheses = _load_json(run_dir / "ranked_hypotheses.json", {}).get("hypotheses", [])
    design = _load_json(run_dir / "simulation_design_plan.json", {})
    manifest = _load_json(run_dir / "artifact_manifest.json", {})
    md = _markdown(goal, kb, hypotheses, design, manifest, config)
    md_path = run_dir / "autoresearch_final_report.md"
    html_path = run_dir / "autoresearch_final_report.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(_html(md), encoding="utf-8")
    return {"markdown": str(md_path), "html": str(html_path)}


def _markdown(goal: dict[str, Any], kb: dict[str, Any], hypotheses: list[dict[str, Any]], design: dict[str, Any], manifest: dict[str, Any], config: dict[str, Any]) -> str:
    hypothesis_lines = "\n".join(
        f"- Rank {row.get('rank')}: {row.get('intervention_name')} - {row.get('hypothesis')}"
        for row in hypotheses[:10]
    )
    return f"""# AutoResearch Workflow Report

## Workflow

{goal.get('workflow_name', 'LLM-guided, schema-constrained CAR-T in silico workflow')}

Objective: {goal.get('objective', config.get('experiment_id'))}

This report summarizes an AutoResearch orchestration layer built on the repository's existing literature, agent, memory, simulation, analysis, critique, and reporting modules.

## Research Goal

- Disease context: {goal.get('disease_context')}
- Tumor type: {goal.get('tumor_type')}
- CAR target antigen: {goal.get('car_target_antigen')}
- Antigen density condition: {goal.get('antigen_density_condition')}
- Candidate interventions: {', '.join(goal.get('candidate_interventions') or [])}

## Knowledge Base

- Indexed artifacts: {kb.get('artifact_count', 0)}
- Memory records: {kb.get('memory_record_count', 0)}
- LLM calls recorded: {kb.get('llm_call_count', 0)}
- Included papers: {kb.get('paper_count', 0)}

## Ranked Hypotheses

{hypothesis_lines or 'No ranked hypotheses were generated.'}

## In-Silico Setup

- Simulator choice: {design.get('simulator_choice')}
- External PhysiCell executed: {design.get('external_physicell_executed')}
- Replicates: {design.get('replicates')}
- Parameter sets: {len(design.get('parameter_sets') or [])}

## Iterative Refinement

This minimal local implementation records a single iteration. Additional iterations should be run only after human review of evidence provenance, proposed parameters, and simulation outputs.

## Guardrails

- No fabricated citations, LLM outputs, PhysiCell outputs, or wet-lab values are introduced by this report.
- Mock records are software fixtures only.
- Generated PhysiCell XML/config files are model inputs, not external simulation outputs.
- Wet-lab validation is not evaluated unless a user-supplied validation table is provided.

## Artifact Manifest

Manifest path: `{manifest.get('path', 'artifact_manifest.json')}`
"""


def _html(markdown: str) -> str:
    body = "\n".join(f"<p>{html.escape(line)}</p>" if line and not line.startswith("#") else f"<h{min(line.count('#'), 6)}>{html.escape(line.lstrip('# ').strip())}</h{min(line.count('#'), 6)}>" for line in markdown.splitlines())
    return f"<!doctype html><html><head><meta charset='utf-8'><title>AutoResearch Workflow Report</title></head><body>{body}</body></html>"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
