# Reviewer Reproducibility Audit

This audit documents the integrated reviewer-response branch. It clarifies why the original release could appear deterministic and how the integrated branch now supports the revised framing: an LLM-guided, schema-constrained CAR-T in silico workflow with deterministic reference mode, optional executable LLM-agent mode, archived/replay mode, hybrid mode, and optional external PhysiCell execution.

No scientific results, LLM outputs, PhysiCell outputs, citations, or wet-lab data are fabricated by this audit.

## 1. Executable Deterministic Pipeline

The command below remains the default deterministic reference workflow:

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver.yaml
```

This path runs without API keys, live internet access, or a compiled PhysiCell executable. It implements:

- configuration and software-version recording
- deterministic query generation
- mock literature loading by default
- deterministic metadata screening
- deterministic evidence extraction
- bounded cytokine fingerprint construction
- mock simulator execution through the PhysiCell adapter by default
- analysis, ranking, critique, memory, and report generation

## 2. Executable and Specification-Level Agents

The prompt registry in `src/cart_autolab/prompts.py` defines the full agent interface. In this integrated branch, selected prompt-defined agents are executable through `AgentRunner`:

- search planning
- literature screening
- chunk evidence extraction
- evidence synthesis
- hypothesis generation
- critique

Other prompts remain registry specifications or deterministic workflow roles unless explicitly wired into execution. Public audit claims should not state that every prompt in the registry is a live LLM agent.

## 3. LLM-Derived Output Boundaries

LLM-derived artifacts enter the downstream pipeline only at explicit schema-constrained boundaries:

- `workflow.evidence_source: llm`
- `workflow.evidence_source: hybrid`

LLM outputs are parsed, validated, audited, and written as artifacts before they can affect cytokine fingerprints. Deterministic mode remains independent of live, mock, or replay LLM artifacts.

## 4. Why the Original Release Looked Deterministic

The original default code path used deterministic implementations for query generation, evidence extraction, fingerprint construction, and mock simulation. The prompt registry documented intended LLM-agent interfaces, but most prompts were not executable LLM calls in the default path.

The integrated branch keeps the deterministic reference mode but adds optional executable LLM, replay, hybrid, ablation, and artifact-audit paths.

## 5. Evidence of LLM Contribution

The integrated branch supports reviewer inspection of software-level LLM contribution through:

- exact prompt files
- raw response files
- parsed JSON files
- validation reports
- run-level `llm_calls.jsonl`
- deterministic, LLM, and hybrid evidence artifacts
- parameter fingerprints with evidence provenance
- ablation summaries comparing deterministic, LLM, and hybrid modes
- `outputs/reviewer_demo/llm_contribution_summary.csv` after running the reproducibility demo

Mock and replay rows demonstrate software routing and provenance only. They are not biological validation.

## 6. External PhysiCell Reproducibility

PhysiCell/BioFVM is treated as an external third-party simulator. The integrated branch provides adapter inputs, optional external execution, execution logging, and output conversion. It does not vendor PhysiCell source, compiled binaries, or large generated outputs.

External mode requires a local executable configured through `PHYSICELL_EXECUTABLE` or simulator config. If outputs are insufficient for conversion, the workflow writes a conversion report and does not fabricate missing time series.

## 7. Expected Artifacts by Mode

### Deterministic Reference Mode

- `search_queries.json`
- `included_papers.json`
- `extracted_evidence.json`
- `extracted_evidence_deterministic.json`
- `parameter_fingerprints.json`
- `parameter_transformation_rules.json`
- `simulation/plan.json`
- `simulation/cell_rules.json`
- `simulation/parameters.json`
- `simulation/timeseries.csv` in mock simulator mode
- `analysis_metrics.csv`
- `ranked_interventions.csv`
- `critique_report.json`
- `memory.jsonl`
- `final_report.md`
- `final_report.html`

### Executable LLM-Agent Mode

- `llm_calls.jsonl`
- `agent_outputs/<agent_name>/<call_id>_prompt.txt`
- `agent_outputs/<agent_name>/<call_id>_raw_response.txt`
- `agent_outputs/<agent_name>/<call_id>_parsed.json`
- `agent_outputs/<agent_name>/<call_id>_validation.json`
- `extracted_evidence_llm.json`
- `hypotheses_llm.json`

### Archived/Replay Mode

Replay mode uses archived prompt-response fixture artifacts and writes the same audit artifacts as executable LLM mode. It does not require live LLM credentials.

### Hybrid Mode

- `extracted_evidence_deterministic.json`
- `extracted_evidence_llm.json`
- `extracted_evidence_hybrid.json`
- `parameter_fingerprints.json` with deterministic and LLM provenance fields
- `parameter_transformation_rules.json`

### Optional External PhysiCell Mode

- `simulation/physicell_config.xml`
- `simulation/cell_rules.json`
- `simulation/parameters.json`
- `simulation/physicell_execution_log.json`
- `simulation/conversion_report.json`
- `simulation/timeseries.csv` only if external outputs contain sufficient data

External PhysiCell mode must not fabricate missing time-series data.
