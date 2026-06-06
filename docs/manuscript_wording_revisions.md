# Manuscript Wording Revisions

These are conservative replacement phrases. They should be adapted by the authors and checked against the manuscript before use.

## Abstract

Replace overbroad autonomous-lab wording with:

> We developed an LLM-guided, schema-constrained CAR-T in silico workflow that maps literature-derived evidence into bounded cytokine functional fingerprints for simulation-based hypothesis prioritization.

## Introduction / To the Editor

> The workflow combines deterministic reference steps with optional LLM-assisted evidence synthesis. LLM-derived outputs are parsed into structured schemas, checked for citation provenance and low-confidence assumptions, and bounded before entering parameter construction.

## Figure 1 Legend

> Figure 1. Overview of the LLM-guided, schema-constrained CAR-T in silico workflow. Deterministic reference mode runs without live LLM calls. Optional executable LLM-agent and archived/replay modes record prompt-response artifacts and schema validation reports before evidence enters cytokine fingerprint construction.

## Limitations

> The workflow is intended for hypothesis prioritization and does not replace wet-lab validation. Mock records are software fixtures only. External PhysiCell execution requires a separately installed and compiled PhysiCell project. Missing citations, unsupported claims, and insufficient simulator outputs are marked rather than fabricated.

## Code Availability

> The code provides a deterministic reference mode and optional modes for executable LLM-agent execution, archived/replay artifacts, hybrid schema-constrained evidence use, and external PhysiCell execution. The repository does not include compiled PhysiCell binaries or large simulation outputs.
