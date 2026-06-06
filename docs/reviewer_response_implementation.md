# Reviewer Response Implementation Status

This workflow archive supports the framing: LLM-guided, schema-constrained CAR-T in silico workflow with deterministic reference mode, optional executable LLM-agent mode, archived/replay mode, and optional external PhysiCell execution.

## Integrated Capabilities

- Deterministic reference workflow.
- Prompt registry exported for reproducibility.
- Mock literature fixtures labeled as mock test records.
- Mock simulator mode for CI/software testing.
- PhysiCell adapter input generation.
- Optional executable LLM runner and audit artifacts.
- Optional executable agent wrappers for prompt-defined agents.
- LLM/hybrid evidence routing into parameter fingerprints.
- Deterministic versus LLM versus hybrid ablation.
- External PhysiCell mode documentation, execution logging, and non-fabricating output conversion.

Live LLM execution and external PhysiCell execution remain optional because they require external credentials or a local simulator build.
