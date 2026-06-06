# Reproducibility Artifacts

Reviewers should expect artifacts to differ by mode.

## Deterministic Reference Mode

- `search_queries.json`
- `included_papers.json`
- `extracted_evidence.json`
- `parameter_fingerprints.json`
- `parameter_transformation_rules.json`
- `simulation/plan.json`
- `simulation/cell_rules.json`
- `simulation/timeseries.csv`
- `analysis_metrics.csv`
- `ranked_interventions.csv`
- `critique_report.json`
- `final_report.md`
- `final_report.html`

## Draft LLM-Agent and Replay Modes

- `llm_calls.jsonl`
- `agent_outputs/`
- `extracted_evidence_llm.json`
- `hypotheses_llm.json`
- `critique_report_llm.json`

## Draft Hybrid Mode

- `extracted_evidence_deterministic.json`
- `extracted_evidence_llm.json`
- `extracted_evidence_hybrid.json`
- `parameter_fingerprints.json`
- `parameter_transformation_rules.json`

## Optional External PhysiCell Mode

- `simulation/plan.json`
- `simulation/cell_rules.json`
- `simulation/physicell_config.xml`
- `simulation/physicell_execution_log.json`
- `simulation/conversion_report.json`
- `simulation/timeseries.csv` only if external outputs contain sufficient data

Missing external PhysiCell time series must be reported, not fabricated.
