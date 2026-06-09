# Repository Rules for Codex Agents

This repository should be framed as an LLM-guided, schema-constrained CAR-T in silico workflow.

## Scientific Integrity

- Do not fabricate citations, LLM outputs, PhysiCell outputs, or wet-lab data.
- Do not alter wet-lab conclusions, figures, experimental data, or manuscript claims without explicit human direction.
- Mock data are software fixtures only. They must not be described as manuscript evidence or biological validation.
- If citation metadata are missing, mark them as missing, incomplete, or low-confidence rather than inventing them.
- If a task would require fabricated scientific evidence, stop and ask for human input.

## Workflow Defaults

- Preserve the deterministic reference/safe-demo workflow for CI, offline testing, and reviewer-safe smoke tests.
- Treat the public default workflow as the real AutoResearch path when configured with live LLM, online literature retrieval, and external PhysiCell execution.
- Keep executable LLM mode clearly configured and auditable; do not silently substitute fabricated LLM outputs.
- Keep external PhysiCell execution clearly configured; do not silently substitute fabricated PhysiCell outputs.
- Keep mock simulator mode labeled as CI/software testing support, not as mechanistic evidence.
- Do not require API keys, internet access, or a compiled PhysiCell executable for the test suite or safe-demo workflow.

## Code and Review Hygiene

- Do not modify unrelated files.
- Do not make one giant unreviewable change when smaller PR-sized changes are possible.
- Do not revert user changes unless explicitly requested.
- Do not commit compiled PhysiCell binaries, object files, or large simulation output files.
- Add focused tests for code changes.
- If tests would require API keys, internet access, wet-lab data, or an external PhysiCell executable, redesign them to use mock or synthetic software fixtures.

## Preferred Wording

Use:

> LLM-guided, schema-constrained CAR-T in silico workflow

Avoid overclaiming phrases such as:

- fully autonomous LLM laboratory
- fully reproducible live LLM system
- mock data validate the biology
