# Remaining Limitations

This file distinguishes fully executable software workflows from optional external setup and scientific interpretation limits.

## Fully Executable Without External Services

- Deterministic reference mode on `main`.
- Mock literature loading and deterministic evidence extraction.
- Parameter fingerprint construction from deterministic evidence.
- Mock simulator mode for CI/software testing.
- Report generation from deterministic outputs.
- Draft mock LLM provider tests and mock LLM workflow paths.
- Draft ablation workflow using mock software fixtures.
- Draft external PhysiCell error handling and output-conversion tests using synthetic local files.

## Requires Optional External Setup

- External PhysiCell execution requires a local PhysiCell build and `PHYSICELL_EXECUTABLE`.
- External PhysiCell output conversion requires actual external output files with sufficient fields.
- Online literature search requires internet access and may depend on public API availability.

## Requires Live LLM Credentials

- `openai_compatible` live LLM mode requires an API key environment variable and model configuration.
- Live LLM mode is intentionally not required for tests.
- Live LLM outputs must be saved and reviewed; they should not be fabricated or substituted with mock outputs.

## Mock Only

- Mock literature records are software fixtures only.
- Mock LLM responses are software fixtures only.
- Ablation rows using mock data demonstrate software routing and provenance, not biological validation.

## Not Scientific Evidence

The following must not be interpreted as scientific evidence:

- mock literature records
- mock LLM outputs
- mock simulator outputs
- ablation metrics computed from fixture data
- conversion reports generated from insufficient PhysiCell outputs

The workflow supports hypothesis prioritization and reproducibility auditing. It does not replace wet-lab validation.
