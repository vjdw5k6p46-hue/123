from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd


class ReportGenerator:
    def generate(self, run_dir: Path, config: dict) -> dict:
        ranked = pd.read_csv(run_dir / "ranked_interventions.csv")
        evidence = json.loads((run_dir / "extracted_evidence.json").read_text(encoding="utf-8"))
        params = json.loads((run_dir / "parameter_fingerprints.json").read_text(encoding="utf-8"))
        critique = json.loads((run_dir / "critique_report.json").read_text(encoding="utf-8"))
        queries = json.loads((run_dir / "search_queries.json").read_text(encoding="utf-8"))
        included = json.loads((run_dir / "included_papers.json").read_text(encoding="utf-8"))
        literature_mode = "mock" if included and all(p.get("source_database") == "Mock" for p in included) else "online/retrieved"
        top = ranked.iloc[0]
        md = self._markdown(config, queries, evidence, params, ranked, critique, top, literature_mode)
        md_path = run_dir / "final_report.md"
        html_path = run_dir / "final_report.html"
        md_path.write_text(md, encoding="utf-8")
        html_path.write_text(self._html(md), encoding="utf-8")
        return {"markdown": str(md_path), "html": str(html_path)}

    def _markdown(self, config: dict, queries: list[str], evidence: list[dict], params: list[dict], ranked: pd.DataFrame, critique: dict, top: pd.Series, literature_mode: str) -> str:
        rank_table = self._markdown_table(ranked[["intervention_name", "ranked_intervention_score", "final_tumor_burden", "car_t_persistence", "exhaustion_fraction"]])
        param_lines = "\n".join(f"- {p['intervention_name']}: confidence {p['confidence_score']:.2f}, uncertainty {p['uncertainty']:.2f}. {p['evidence_summary']}" for p in params)
        evidence_lines = "\n".join(f"- {e['intervention_name']}: {e['supporting_citation']} Confidence {e['confidence_score']:.2f}." for e in evidence[:20])
        query_lines = "\n".join(f"- {q}" for q in queries)
        limitations = "\n".join(f"- {x}" for x in critique["limitations"])
        validation = "\n".join(f"- {x}" for x in critique["recommended_validation_experiments_high_level"])
        return f"""# CAR-T In Silico Autonomous Lab Report

## Researcher-defined biological goal

Disease context: {config['disease_context']}

Tumor type: {config['tumor_type']}

CAR target antigen: {config['car_target_antigen']}

Antigen density condition: {config['antigen_density_condition']}

Engineering variable: {config['engineering_variable']}

Candidate interventions: {', '.join(config['candidate_interventions'])}

This platform operationalizes a researcher-defined research goal into literature search, evidence extraction, parameter construction, simulation planning, analysis, critique, and reporting. It is for hypothesis prioritization and in silico experimental planning. It does not replace wet-lab validation.

## Search strategy

Literature mode: {literature_mode}. Mock test records are not real scholarly citations and are only used for offline software testing.

{query_lines}

## Included evidence and extracted effects

{evidence_lines or 'No direct evidence extracted. Assumptions are low-confidence.'}

## Simulation parameter sets

The cytokine functional fingerprint is a simulation-ready parameter vector, not an omics signature.

{param_lines}

## Simulator and conditions

Primary simulator: PhysiCell/BioFVM adapter.

Execution mode: mock if no PhysiCell executable was configured; external PhysiCell can be connected through `PHYSICELL_EXECUTABLE`.

Replicates: {config['replicates']}

Parameter sweep: `{json.dumps(config.get('parameter_sweep', {}))}`

## Ranked interventions

{rank_table}

Top ranked intervention in this run: **{top['intervention_name']}**.

For the demonstration, IL-15 may be prioritized when it combines persistence, cytotoxicity, and lower exhaustion penalties under low antigen density. This is a model-supported hypothesis, not a claim of biological proof.

## Mechanistic interpretation

{critique['biological_interpretation']}

Confidence level: {critique['confidence_level']}

## Uncertainty and limitations

{limitations}

## Recommended wet-lab validation direction

{validation}

## Reproducibility information

Saved artifacts include the original experiment config, search queries, raw and deduplicated literature records, extracted evidence, parameter transformation rules, simulation plan, random seeds, simulation outputs, metrics, figures, critique, memory JSONL, and this report.
"""

    def _html(self, markdown: str) -> str:
        body = "\n".join(f"<p>{html.escape(line)}</p>" if line and not line.startswith("#") else f"<h{min(line.count('#'), 6)}>{html.escape(line.lstrip('# ').strip())}</h{min(line.count('#'), 6)}>" for line in markdown.splitlines())
        return f"<!doctype html><html><head><meta charset='utf-8'><title>CAR-T Autolab Report</title><style>body{{font-family:Arial,sans-serif;max-width:980px;margin:40px auto;line-height:1.5}} table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:4px 8px}}</style></head><body>{body}</body></html>"

    def _markdown_table(self, df: pd.DataFrame) -> str:
        headers = list(df.columns)
        rows = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
        for _, row in df.iterrows():
            values = []
            for value in row:
                values.append(f"{value:.4g}" if isinstance(value, float) else str(value))
            rows.append("| " + " | ".join(values) + " |")
        return "\n".join(rows)
