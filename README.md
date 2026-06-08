# CAR-T In Silico Autolab

Runnable, modular Python project for an LLM-guided, schema-constrained CAR-T in silico workflow. The first demonstration is cytokine payload prioritization for GPC3 CAR-T cells in liver cancer with low antigen density, but the schemas and simulator adapter layer support broader CAR-T engineering questions.

The researcher defines the biological goal. The workflow operationalizes that goal into literature search, evidence extraction, parameter construction, PhysiCell/BioFVM simulation preparation or optional execution, analysis, critique, memory, and reports. It is for hypothesis prioritization and in silico planning. It does not replace wet-lab validation.

## Workflow Modes

This workflow archive provides a real AutoResearch default path plus deterministic reference execution, executable LLM-agent, hybrid, ablation, and external PhysiCell support. Executable LLM runs save audit artifacts that can be inspected after the run.

- Real AutoResearch mode: default mode; uses online literature retrieval/download, executable LLM agents, hybrid evidence use, and external PhysiCell execution when configured.
- Deterministic reference mode: available as a safe software demo; no API key, internet access, or external PhysiCell executable required.
- Executable LLM-agent mode: records prompt, raw response, parsed JSON, schema validation, and audit metadata.
- Hybrid mode: uses validated LLM evidence while retaining schema checks, confidence bounds, and parameter checks.

Simulator modes:

- External PhysiCell mode: default for the real workflow; requires a local PhysiCell build and `PHYSICELL_EXECUTABLE`.
- Mock simulator mode: for CI and software testing only.

## Install

```bash
cd cart_insilico_autolab
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

## Run the Real Workflow

```bash
set OPENAI_API_KEY=your_key
set PHYSICELL_EXECUTABLE=C:\path\to\cancer_immune.exe
cart-autolab autoresearch-run --config configs/experiment_cytokine_gpc3_liver_autoresearch.yaml
```

The default experiment config, `configs/experiment_cytokine_gpc3_liver.yaml`, is also configured for the real path:

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver.yaml
```

It uses online literature mode, paper download/chunking, hybrid LLM evidence extraction, LLM critique, and external PhysiCell mode. If `OPENAI_API_KEY` or `PHYSICELL_EXECUTABLE` is missing, the run should fail clearly rather than silently substituting mock scientific outputs.

## Safe Software Demo

The dependency-free demo is retained for CI and software smoke testing:

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver_safe_demo.yaml
```

Public audit safe demo bundle:

```bash
bash scripts/run_reviewer_reproducibility_demo.sh
```

This writes deterministic, LLM mock, and ablation artifacts under `outputs/reviewer_demo/` without requiring API keys, internet access, or a compiled PhysiCell executable.

Real workflow outputs are written to `outputs/real_autoresearch_run` or `outputs/autoresearch_real`, depending on the entry point. Safe-demo outputs are written to `outputs/example_run`.

Safe demo mode uses `data/mock_literature/mock_papers.json`. Those records are explicitly labeled mock test records and are not real scholarly citations. The default real config uses `literature.mode: online`. The clients support PubMed/NCBI E-utilities, Semantic Scholar, OpenAlex, and Crossref. Semantic Scholar can use `SEMANTIC_SCHOLAR_API_KEY`.

Reviewer reproducibility commands:

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver_safe_demo.yaml
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver_llm_mock.yaml
cart-autolab ablation --config configs/experiment_cytokine_gpc3_liver_ablation.yaml
cart-autolab simulate --config configs/experiment_cytokine_gpc3_liver_physicell.yaml
```

LLM mock and ablation commands use software fixtures by default and do not require API keys. External PhysiCell execution requires local setup.

Automatic paper acquisition is available with `cart-autolab download-papers` or `literature.download_papers: true`. It only downloads open-access or directly available artifacts from sources such as PMC, Europe PMC, bioRxiv/medRxiv, Unpaywall OA links, or publisher-provided OA URLs. It writes `downloaded_papers_manifest.json` with every attempted URL and saved artifact path.

Downloaded PDFs/XML/text can be converted into LLM-ready chunks with `cart-autolab chunk-papers`. The chunker writes `paper_chunks/paper_chunks.jsonl` and `paper_chunks/paper_chunk_index.json`, preserving paper IDs, DOI/PMID, title, artifact path, chunk index, and text.

Agent prompts are explicit and versioned in `cart_autolab.prompts`. Use `cart-autolab prompts` to list agents, `cart-autolab prompts --agent <name>` to inspect one prompt, or `cart-autolab prompts --export outputs/agent_prompts.json` to save the registry. `run-all` also saves `agent_prompts.json` in the run directory.

`cart-autolab autoresearch-run` is the LLM-first workflow entry point. Its default AutoResearch config uses an OpenAI-compatible provider for research-goal parsing, LLM agent audit steps, and refinement-loop decisions. If provider credentials are unavailable, the run records a deterministic fallback instead of fabricating LLM output.

AutoResearch refinement control uses a schema-constrained LLM decision agent when `autoresearch.refinement_controller_source: llm`. The LLM decides whether another refinement loop is needed; Python validates the decision, enforces `max_refinement_iterations`, and executes only whitelisted actions. Requested actions that need human review or an external executor are recorded rather than fabricated.

## CLI

```bash
cart-autolab init --template cytokine_gpc3_liver
cart-autolab prompts
cart-autolab prompts --agent chunk_evidence_extraction_agent
cart-autolab prompts --export outputs/agent_prompts.json
cart-autolab search --config configs/experiment_cytokine_gpc3_liver.yaml
cart-autolab download-papers --config configs/experiment_cytokine_gpc3_liver.yaml
cart-autolab chunk-papers --config configs/experiment_cytokine_gpc3_liver.yaml
cart-autolab build-parameters --config configs/experiment_cytokine_gpc3_liver.yaml
cart-autolab simulate --config configs/experiment_cytokine_gpc3_liver.yaml --simulator physicell
cart-autolab analyze --run outputs/example_run
cart-autolab report --run outputs/example_run
cart-autolab autoresearch-run --config configs/experiment_cytokine_gpc3_liver_autoresearch.yaml
```

## PhysiCell integration

Python handles orchestration, parameter processing, simulation configuration, batch execution, output parsing, statistical analysis, plotting, critique, memory, and reporting. The core multicellular agent-based simulation is intended to be performed by PhysiCell/BioFVM when a compiled PhysiCell executable is available.

This repository includes only the CAR-T PhysiCell project template files under `physicell_project/`:

- `physicell_project/config/PhysiCell_settings.template.xml`
- `physicell_project/custom_modules/cancer_immune_3D.cpp`
- `physicell_project/custom_modules/cancer_immune_3D.h`

It does not vendor the full PhysiCell source tree, compiled executables, object files, local outputs, or local sweep artifacts.

The `PhysiCellAdapter` writes:

- `simulation/physicell_config.xml`
- `simulation/cell_rules.json`
- `simulation/plan.json`
- `simulation/parameters.json`

To connect a real executable:

```bash
set PHYSICELL_EXECUTABLE=/path/to/PhysiCell/your_project/project_executable
```

Then instantiate `PhysiCellAdapter(mode="external")` or adapt `orchestrator.py` to read `configs/simulator_physicell.yaml` with `mode: external`. The adapter maps tumor antigen density and cytokine functional fingerprints into CAR-T activation, proliferation, killing, exhaustion, death, IFN-gamma, hypoxia, PD-L1, and suppressive TME fields. The mock mode is only for testability and demonstration.

## Add a new simulator

Implement `cart_autolab.simulation.base.SimulatorAdapter`:

- `prepare_inputs()`
- `write_config()`
- `run()`
- `parse_outputs()`
- `summarize_results()`

`VitruCellAdapter` is intentionally a placeholder. Alternative compatible multicellular simulation engines can be substituted through the same adapter interface when installation and API details are supplied.

## Add a new experiment type

Edit or add a YAML config with a different `engineering_variable` and `candidate_interventions`. Cytokine experiments use `CytokineFingerprint`. Other variables use `GenericInterventionParameters`, which can represent CAR affinity, antigen threshold, co-stimulatory strength, killing rate, exhaustion rate, proliferation rate, migration/infiltration, suppressive TME resistance, persistence or memory phenotype, and safety/toxicity flags.

Researcher parameter overrides are supported under `manual_parameter_overrides` and are recorded in transformation rules. Low-confidence assumptions are not hidden.

## Tests

```bash
pytest
```

## License

MIT License. See `LICENSE`.

## Scientific constraints

- No fabricated citations.
- Weak, indirect, or missing evidence is marked low-confidence.
- The cytokine functional fingerprint is a simulation-ready parameter vector, not an omics signature.
- Reports provide high-level validation direction, not detailed wet-lab protocols.
- Results do not guarantee discovery or efficacy.
