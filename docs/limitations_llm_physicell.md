# Limitations: LLM and PhysiCell Modes

## LLM Mode

Executable LLM-agent mode is optional. It should be used only when provider configuration is supplied or archived replay artifacts are available.

Live LLM outputs can vary by model and provider. Therefore, prompt-response artifacts, parsed JSON, schema validation reports, model metadata, prompt hashes, warnings, and run-level audit logs should be archived for review.

The LLM layer is a biological knowledge synthesis component. It does not prove biological efficacy, discover a validated therapy, or replace wet-lab validation.

## Replay Mode

Replay mode is useful for reviewing archived prompt-response behavior without making live LLM calls. Replay fixtures must be labeled. They should not be treated as newly generated live LLM outputs.

## PhysiCell Mode

PhysiCell/BioFVM is an external third-party simulator. The repository provides an adapter and optional setup instructions, not the full simulator distribution.

External PhysiCell execution requires a local executable. If no executable is configured, the workflow should fail with a clear error. If external outputs are missing or insufficient, the converter should write a report and must not fabricate missing time series.

## Mock Mode

Mock simulator outputs, mock literature records, and mock LLM responses are for CI and software testing. They are not scientific evidence.
