# Repository Rules for Codex Agents

This repository should be framed as an LLM-guided, schema-constrained CAR-T in silico workflow.

## Scientific Integrity

- Do not fabricate citations, LLM outputs, PhysiCell outputs, or wet-lab data.
- Do not alter wet-lab conclusions, figures, experimental data, or manuscript claims without explicit human direction.
- Mock data are software fixtures only. They must not be described as manuscript evidence or biological validation.
- If citation metadata are missing, mark them as missing, incomplete, or low-confidence rather than inventing them.
- If a task would require fabricated scientific evidence, stop and ask for human input.

## Workflow Defaults

- Preserve the default deterministic workflow unless the task explicitly changes it.
- Keep executable LLM mode optional and clearly configured.
- Keep external PhysiCell mode optional unless explicitly configured.
- Keep mock simulator mode labeled as CI/software testing support, not as mechanistic evidence.
- Do not require API keys, internet access, or a compiled PhysiCell executable for default tests.

## Code and Review Hygiene

- Do not modify unrelated files.
- Do not make one giant unreviewable change when smaller PR-sized changes are possible.
- Do not modify `main` directly.
- Do not merge to `main`.
- Do not revert user changes unless explicitly requested.
- Do not commit compiled PhysiCell binaries, object files, or large simulation output files.
- Add focused tests for code changes.
- If tests would require API keys, internet access, wet-lab data, or an external PhysiCell executable, redesign them to use mock, replay, or synthetic software fixtures.

## Preferred Wording

Use:

> LLM-guided, schema-constrained CAR-T in silico workflow

Avoid overclaiming phrases such as:

- fully autonomous LLM laboratory
- fully reproducible live LLM system
- mock data validate the biology
