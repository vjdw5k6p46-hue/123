# Post-Implementation Audit

This audit reviews the integrated reviewer-response branch created after the reviewer concern. The default workflow remains deterministic, while optional LLM, replay, hybrid, ablation, and external PhysiCell modes are available in this branch.

## Branches Reviewed

- `audit/reviewer-reproducibility`
- `feature/llm-agent-runner`
- `feature/executable-llm-agents`
- `feature/llm-evidence-to-parameters`
- `analysis/llm-ablation`
- `feature/physicell-external-mode`
- `docs/reviewer-response`
- `docs/final-reviewer-checklist`

## 1. Implemented Reviewer-Response Tasks

Implemented in this integration branch:

- Repository guardrails in `AGENTS.md`, including no fabricated citations, LLM outputs, PhysiCell outputs, or wet-lab data.
- Documentation audit and PR split plan.
- Optional LLM runner infrastructure with providers `none`, `mock`, `replay`, and `openai_compatible`.
- LLM audit logging to `outputs/<run>/llm_calls.jsonl`.
- Per-call prompt, raw response, parsed JSON, and validation artifacts under `outputs/<run>/agent_outputs/<agent_name>/`.
- JSON parsing and schema/custom validation checks for LLM outputs.
- Executable wrappers for selected prompt-defined agents.
- Optional routing for deterministic, LLM, and hybrid evidence modes.
- Evidence loader and parameter fingerprint provenance fields.
- Ablation analysis comparing deterministic, LLM, and hybrid modes.
- External PhysiCell documentation, explicit external-mode error handling, execution logs, and output conversion reports.
- Reviewer-facing documentation and conservative rebuttal wording.

## 2. Partially Implemented Tasks

- Executable LLM mode is implemented for selected agents, not every prompt in `cart_autolab.prompts`.
- The LLM provider stack is executable for mock and replay modes without credentials. Live `openai_compatible` mode is implemented but intentionally untested in CI because it requires API credentials.
- Ablation demonstrates software-level differences between deterministic, mock/replay LLM, and hybrid paths. It does not demonstrate biological superiority from mock data.
- External PhysiCell mode validates configuration and can call a local executable, but tests do not run a compiled PhysiCell binary.

## 3. Documented but Not Fully Executable Without External Setup

Executable LLM-agent mode, replay mode, hybrid evidence-to-parameter provenance, ablation, and external PhysiCell conversion are present in this integration branch. Live LLM calls require provider credentials, and real external PhysiCell simulation requires a local compiled executable.

## 4. Default Deterministic Pipeline

The default deterministic pipeline still runs. Previous full-suite results from the component branches and this integration branch are documented in PR descriptions and the final checklist.

- PR 1 branch: `pytest` passed with 18 tests.
- PR 2 branch: `pytest` passed with 21 tests.
- PR 3 branch: `pytest` passed with 26 tests.
- PR 4 branch: `pytest` passed with 28 tests.
- PR 5 branch: `pytest` passed with 17 tests.

The deterministic command remains:

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver.yaml
```

## 5. Executable LLM Mode

Executable LLM mode is more than configuration. `AgentRunner` loads a prompt template, renders inputs, calls the configured provider, parses JSON, validates the output, writes artifacts, and appends an audit record.

Implemented providers:

- `none`: default-safe mode; no LLM call.
- `mock`: deterministic software fixture provider for tests.
- `replay`: reads archived prompt-response artifacts from disk.
- `openai_compatible`: optional live provider; requires API configuration and fails clearly without it.

The mode remains optional and is not the default.

## 6. LLM Call Audit Log

Each LLM call appends a JSONL record to:

```text
outputs/<run>/llm_calls.jsonl
```

Records include call ID, agent name, provider, model, temperature, seed, prompt hash, artifact paths, validation status, retry count, timestamp, and warnings.

## 7. Prompt, Raw, Parsed, and Validation Artifacts

Each call writes:

```text
outputs/<run>/agent_outputs/<agent_name>/<call_id>_prompt.txt
outputs/<run>/agent_outputs/<agent_name>/<call_id>_raw_response.txt
outputs/<run>/agent_outputs/<agent_name>/<call_id>_parsed.json
outputs/<run>/agent_outputs/<agent_name>/<call_id>_validation.json
```

Invalid JSON is not silently accepted; it is saved and rejected.

## 8. Schema Validation

LLM outputs are schema/custom validated. Validation status is written to the per-call validation artifact and to `llm_calls.jsonl`.

This is schema-constrained software validation, not biological validation.

## 9. LLM Evidence to Parameter Fingerprints

LLM-derived evidence affects `parameter_fingerprints.json` only when:

```yaml
workflow:
  evidence_source: llm
```

or:

```yaml
workflow:
  evidence_source: hybrid
```

Parameter rows include provenance fields such as:

- `evidence_source`
- `evidence_record_ids`
- `llm_call_ids`
- `prompt_hashes`
- `parameter_derivation_notes`
- `low_confidence_flags`

Deterministic mode does not require LLM artifacts.

## 10. Ablation

The ablation command compares:

- deterministic mode
- LLM mode
- hybrid mode

It writes:

- `ablation_summary.csv`
- `ablation_summary.json`
- `evidence_coverage_matrix.csv`
- `ranking_comparison.csv`
- `README.md`

If no wet-lab validation CSV is supplied, the output states:

```text
not evaluated; user-supplied validation table required
```

## 11. Mock Data Labels

Mock literature records are labeled with `source_database: Mock`, and the deterministic extractor prefixes fixture-derived reference strings with `[MOCK TEST RECORD]`. Documentation states that mock records are software fixtures only, not manuscript evidence.

Mock LLM provider warnings state that mock provider output is a software fixture only and not scientific evidence.

## 12. External PhysiCell Mode

External PhysiCell mode:

- requires `PHYSICELL_EXECUTABLE` or a configured executable path
- fails clearly if the executable is missing
- writes `simulation/physicell_execution_log.json`
- attempts output conversion only when files are present
- writes `simulation/conversion_report.json` if outputs are insufficient
- does not fabricate missing `timeseries.csv`

Tests cover missing executable errors and insufficient output conversion reports without running PhysiCell.

## 13. Documentation Overclaiming

The reviewer-facing docs use the phrase:

```text
LLM-guided, schema-constrained CAR-T in silico workflow
```

Autonomous-lab overclaiming language appears only in `AGENTS.md` as avoided wording. It should not be used in reviewer-facing claims.

## 14. Fake Artifacts

No fabricated wet-lab values, PhysiCell outputs, or live LLM outputs were committed.

The existing mock literature data use `doi: null` and `pmid: null`, not fake DOI/PMID values. Some tests and configs use fixture text such as "Fixture metadata only"; these should remain clearly labeled as software fixtures and not manuscript evidence.

No compiled PhysiCell binaries or large simulation outputs were committed.

## 15. Reviewer Commands

### Deterministic Demo

```bash
pip install -e .[dev]
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver.yaml
pytest
```

### LLM, Replay, and Ablation Modes

```bash
pytest
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver.yaml
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver_llm_mock.yaml
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver_replay.yaml
cart-autolab ablation --config configs/experiment_cytokine_gpc3_liver_ablation.yaml
```

### External PhysiCell Dry-Run Tests

```bash
pytest tests/test_physicell_output_converter.py tests/test_physicell_external_mode_errors.py
```

For a real external run, users must provide a local executable:

```bash
export PHYSICELL_EXECUTABLE=/path/to/local/PhysiCell/project_executable
cart-autolab simulate --config configs/experiment_cytokine_gpc3_liver_physicell.yaml
```

This external command should not be used as a CI requirement.
