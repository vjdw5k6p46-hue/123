# Local AutoResearch Workflow

This repository includes an optional local AutoResearch workflow for the
LLM-guided, schema-constrained CAR-T in silico workflow. The workflow is
intended to generate audit-ready model inputs, not wet-lab evidence.

## Scope

The local AutoResearch workflow can:

- optionally ask an LLM to parse the research question into a bounded
  `research_goal.json` and literature search scope;
- filter CAR-T cytokine and tumor-antigen literature chunks;
- ask an OpenAI-compatible LLM to reason per cytokine;
- validate cytokine-specific T-cell functional fingerprints;
- export PhysiCell-ready XML inputs;
- run optional local PhysiCell replicates;
- ask an LLM critique/refinement agent to propose a next parameter round.

The workflow does not fabricate citations, LLM outputs, PhysiCell outputs, or
wet-lab values. Mock or replay outputs are software fixtures only.

## Safe Git Policy

Generated outputs under `outputs/` are ignored by git and should not be
committed. In silico simulation outputs should be shared separately only when
explicitly requested, with clear labels that they are not wet-lab validation.

## Example Commands

Optional Step 1 LLM goal parsing is enabled by setting:

```yaml
autoresearch:
  goal_source: llm
  research_question: Which self-secreting cytokine CAR-T design is best for low-antigen GPC3 liver cancer?
```

This step parses the research question, inclusion/exclusion scope, and fixed
scenario constraints. It does not generate tumor parameters. In the current
workflow, low antigen remains a fixed simulation scenario while later LLM calls
focus on cytokine-armored CAR-T hypotheses and intervention parameters.

Filter literature chunks:

```powershell
python scripts\filter_autoresearch_relevant_chunks.py `
  --cytokine-chunks outputs\manuscript_self_secreting_combined_pdf_archive\paper_chunks_grobid_tei\paper_chunks.jsonl `
  --tumor-chunks outputs\liver_antigen_density_literature\paper_chunks_grobid_tei\paper_chunks.jsonl `
  --output outputs\autoresearch_relevance_filtered_chunks `
  --force
```

Run per-cytokine LLM fingerprint extraction:

```powershell
python scripts\run_autoresearch_per_cytokine_fingerprints.py `
  --config configs\openai_api.yaml `
  --cytokine-chunks outputs\manuscript_self_secreting_combined_pdf_archive\paper_chunks_grobid_tei\paper_chunks.jsonl `
  --tumor-chunks outputs\liver_antigen_density_literature\paper_chunks_grobid_tei\paper_chunks.jsonl `
  --output outputs\autoresearch_per_cytokine_fingerprints `
  --force
```

Run optional local PhysiCell replicates:

```powershell
python scripts\run_physicell_autoresearch_replicates.py `
  --configs-dir outputs\autoresearch_per_cytokine_fingerprints\physicell_ready_configs `
  --output outputs\physicell_autoresearch_replicates `
  --replicates 3 `
  --max-time 1440 `
  --workers 1 `
  --omp-threads 4 `
  --force
```

Run LLM simulation critique/refinement:

```powershell
python scripts\run_autoresearch_simulation_refinement.py `
  --config configs\openai_api.yaml `
  --simulation-summary outputs\physicell_autoresearch_replicates\replicate_summary.csv `
  --parameter-table outputs\autoresearch_per_cytokine_fingerprints\cytokine_parameter_table.csv `
  --reasoning-json outputs\autoresearch_per_cytokine_fingerprints\autoresearch_reasoning_validated.json `
  --output outputs\autoresearch_simulation_refinement `
  --force
```

## Required External Setup

Live LLM execution requires an API key configured through the environment
variable named in the selected config, such as `OPENAI_API_KEY` or
`GEMINI_API_KEY`.

External PhysiCell execution requires a local compiled PhysiCell executable.
The repository does not commit compiled PhysiCell binaries.
