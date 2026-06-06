# Rebuttal to Reviewer Concern About the LLM Workflow

This document provides two non-defensive response options. The strong version matches this workflow archive. The conservative version can be used if the authors decide to describe only deterministic reference mode, prompt specifications, mock/replay fixtures, and clearer documentation.

## A. Strong Version

We agree that the initial public release made the deterministic reference pipeline more visible than the optional LLM-agent execution path. We revised the repository to distinguish deterministic reference mode, executable LLM-agent mode, archived/replay mode, hybrid mode, and optional external PhysiCell execution.

The deterministic reference mode remains the default for portability, reproducibility, and testing. It requires no API key, no internet access, and no compiled PhysiCell executable. This mode provides a stable baseline for reviewers to reproduce the evidence-to-parameter-to-simulation path.

To address the concern that prompt definitions appeared to be placeholders, selected agents are now executable components. The revised implementation records prompt-response artifacts, raw responses, parsed JSON, schema validation reports, provider metadata, prompt hashes, and run-level `llm_calls.jsonl` audit records. Invalid JSON is saved and rejected rather than silently accepted. Archived/replay mode allows the same code path to be reviewed without live LLM calls.

The substantive LLM contribution is biological knowledge synthesis rather than autonomous experimentation. The LLM layer converts dispersed CAR-T/cytokine evidence into structured, machine-readable cytokine functional evidence. Deterministic schema validation, citation checks, confidence bounds, parameter clamping, and manual override reporting then constrain how those records enter cytokine functional fingerprints. Downstream simulation and ranking consume those fingerprints, while wet-lab validation remains the scientific validation step.

We also added ablation outputs comparing deterministic, LLM-agent, and hybrid modes. These outputs are intended to show software-level contribution and provenance, not to claim biological superiority from mock or replay fixtures.

PhysiCell is treated as an external third-party simulator. The repository provides an adapter and optional external execution path, but it does not include compiled PhysiCell binaries or large generated outputs. Mock simulator mode is retained for CI and software testing only. External mode requires a local executable and reports missing or insufficient outputs without fabricating time series.

Mock records and mock LLM responses are offline software fixtures. They are not real scholarly citations, manuscript evidence, PhysiCell outputs, or wet-lab validation.

## B. Conservative Version

We agree that the initial public release is best characterized as a deterministic reference implementation with explicit prompt specifications, rather than a fully demonstrated live LLM workflow. We revised the repository documentation to make this distinction clear.

The deterministic reference mode is retained intentionally because it is portable and reproducible without API keys, internet access, or a compiled PhysiCell executable. It demonstrates the evidence-to-parameter-to-simulation path in a controlled software setting.

The prompt registry documents the intended LLM-agent interfaces and schemas. If any agents remain specification-only, public audit text should list them honestly rather than claiming they are executable. Mock and replay fixtures are used only to exercise software paths and artifact generation.

The intended LLM role is biological knowledge synthesis: converting dispersed CAR-T/cytokine evidence into structured cytokine functional fingerprints that can be bounded and checked before simulation. The deterministic pipeline, schema constraints, simulation adapter, and wet-lab validation form the reproducibility and validation harness.

PhysiCell is an external third-party simulator. The current repository provides adapter inputs and documentation for optional external execution, while mock mode is for CI and testing only.

Mock records are offline software fixtures, not real scholarly citations and not manuscript evidence. We do not use mock data to validate the biology.

## Agents Implemented Versus Specification-Only

When the implementation PR stack is used, selected executable agents include:

- search planning
- literature screening
- chunk evidence extraction
- evidence synthesis
- hypothesis generation
- critique

Other prompts may remain specifications or reproducibility templates unless explicitly wired into the workflow. Public audit text should not claim that every prompt in the registry is an executable live LLM agent.

## PhysiCell Wording

PhysiCell/BioFVM should be described as an external simulator dependency. The repository contribution is the evidence-to-parameter-to-simulation workflow and adapter. Mock mode should be described as CI/software testing support only.

## Mock Data Wording

Use:

> Mock records are offline software fixtures used to test code paths and artifact generation. They are not real scholarly citations, manuscript evidence, PhysiCell outputs, or wet-lab validation.

Do not use:

> Fixture records establish biological validation.
