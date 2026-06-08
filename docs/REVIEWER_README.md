# Reviewer README

This workflow archive provides the reproducibility-ready LLM-guided, schema-constrained CAR-T in silico workflow package.

## Install

```bash
pip install -e .[dev]
```

## Deterministic Mode

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver.yaml
```

This is the default reference workflow. It requires no API key, no internet access, and no external PhysiCell executable.

## LLM-First AutoResearch Mode

```bash
cart-autolab autoresearch-run --config configs/experiment_cytokine_gpc3_liver_autoresearch.yaml
```

This is the primary AutoResearch workflow. With provider credentials configured, the LLM parses the research goal, records executable agent audit steps, and decides whether refinement should continue. Without credentials, the run records deterministic fallback or skipped LLM steps rather than fabricating outputs.

## Reviewer-Safe Demo

```bash
bash scripts/run_reviewer_reproducibility_demo.sh --force
```

This writes:

```text
outputs/reviewer_demo/
```

The demo runs deterministic, LLM mock, and ablation modes without API keys, internet access, or a compiled PhysiCell executable.

## LLM Audit Artifacts

Inspect these files after the reviewer-safe demo:

```text
outputs/reviewer_demo/llm_mock/llm_calls.jsonl
outputs/reviewer_demo/llm_mock/agent_outputs/
```

Each LLM call records prompt, raw response, parsed JSON, validation report, provider metadata, and warnings.

The recorded refinement-loop decision for this package is archived at `artifacts/06_refinement_loop_decision/refinement_loop_decisions.json` (with prompt/response audit under `artifacts/06_refinement_loop_decision/agent_outputs/`). Optional AutoResearch refinement-loop decisions are saved as `refinement_loop_decisions.json` when `autoresearch.refinement_controller_source: llm` is enabled. The LLM can request another refinement loop or stop, but Python validates the decision and enforces max-iteration and executor guardrails.

## Contribution Summary

```text
outputs/reviewer_demo/llm_contribution_summary.csv
```

This table compares deterministic, LLM mock, and hybrid software workflows. Mock rows are software-fixture demonstrations only.

## Ablation Outputs

```text
outputs/reviewer_demo/ablation/ablation_summary.csv
outputs/reviewer_demo/ablation/ablation_summary.json
outputs/reviewer_demo/ablation/evidence_coverage_matrix.csv
outputs/reviewer_demo/ablation/ranking_comparison.csv
```

If no user-supplied validation CSV is provided, wet-lab concordance is reported as not evaluated.

## External PhysiCell

PhysiCell/BioFVM is an external third-party simulator. Mock simulator mode is for CI and software testing only.

To run external PhysiCell locally:

```bash
export PHYSICELL_EXECUTABLE=/path/to/local/PhysiCell/project_executable
cart-autolab simulate --config configs/experiment_cytokine_gpc3_liver_physicell.yaml
```

External mode writes `simulation/physicell_execution_log.json`. If available outputs cannot be converted to the common schema, the converter writes `simulation/conversion_report.json` and does not fabricate missing time series.
