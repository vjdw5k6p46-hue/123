# Manuscript Revision Snippets

These snippets should be adapted by the authors before insertion into the manuscript. They do not edit the manuscript DOCX directly.

## Abstract

> We developed an LLM-guided, schema-constrained CAR-T in silico workflow for cytokine payload prioritization in low-antigen liver cancer. The workflow distinguishes deterministic reference execution from optional executable LLM-agent and archived/replay modes. LLM-derived evidence is parsed into structured records, checked for citation provenance and schema validity, and converted into bounded cytokine functional fingerprints for downstream simulation-based ranking. The workflow is intended for hypothesis prioritization and does not replace wet-lab validation.

## To the Editor / Introduction

> The workflow was designed to separate portable deterministic execution from optional LLM-guided evidence synthesis. In deterministic reference mode, the code can be run without live LLM calls, API keys, internet access, or a compiled external simulator. In optional LLM-agent and replay modes, prompt-response artifacts are archived, parsed, and schema-validated before downstream use. The LLM layer contributes by synthesizing dispersed CAR-T/cytokine evidence into structured cytokine functional fingerprints, while deterministic constraints bound and validate the resulting simulation inputs.

## Figure 1 Legend

> Figure 1. Overview of the LLM-guided, schema-constrained CAR-T in silico workflow. Deterministic reference mode provides a portable baseline. Optional executable LLM-agent and archived/replay modes generate prompt-response artifacts, parsed JSON, schema validation reports, and audit logs. Validated LLM-derived evidence can enter cytokine functional fingerprint construction in LLM or hybrid mode before simulation planning, ranking, critique, and reporting. Mock records are software fixtures only and are not manuscript evidence.

## Limitations

> This workflow supports in silico hypothesis prioritization and does not replace wet-lab validation. Mock literature records, mock LLM responses, and replay fixtures are software testing artifacts only. PhysiCell/BioFVM is an external third-party simulator; external execution requires a local build and configured executable. Missing citations, invalid LLM outputs, and insufficient simulator outputs are reported rather than fabricated. Live LLM execution is optional and may vary by model, provider, and configuration.

## Code Availability

> The repository provides a deterministic reference workflow and optional modes for executable LLM-agent execution, archived/replay execution, hybrid schema-constrained evidence use, ablation analysis, and external PhysiCell execution. The repository does not include compiled PhysiCell binaries or large generated simulation outputs. Mock records are software fixtures only and are not real scholarly citations or manuscript evidence.

## Optional Local LLM Archive Addendum

> If a real local LLM archive is generated and included, the response can state that selected agents were executed using a local OpenAI-compatible LLM backend and that complete prompt-response artifacts, schema validation logs, and downstream parameter/ranking artifacts are archived. This statement should be used only when the archive is actually generated from curated real literature metadata with provenance, not from mock or replay fixtures.
