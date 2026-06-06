# Local LLM Model Comparison

This workflow compares Qwen and Gemma/Gamma 4 on the same self-secreting cytokine CAR-T paper chunks.

Input chunk file:

```text
outputs/manuscript_self_secreting_selected_download/paper_chunks/paper_chunks.jsonl
```

The current input set contains 30 downloaded open-access papers and 520 chunks generated with `chunk_chars=3500` and `overlap_chars=350`.

## Purpose

The comparison asks whether two optional local LLM backends extract similar structured evidence from the same chunks. The LLMs do not generate final PhysiCell parameters. They only extract chunk-level evidence with citation provenance. Deterministic code then validates records, aggregates cytokine endpoint fingerprints, and creates bounded parameter proposals requiring human review.

## Models

Configs:

```text
configs/local_llm_qwen.yaml
configs/local_llm_gemma.yaml
```

If the user says "Gamma 4" but the local model identifier is Gemma, preserve the local model name exactly in configs and manifests.

## Smoke Test

```bash
export LOCAL_LLM_API_KEY=dummy
python scripts/smoke_test_local_llm_models.py \
  --qwen-config configs/local_llm_qwen.yaml \
  --gemma-config configs/local_llm_gemma.yaml
```

The smoke test sends a minimal JSON-only prompt to both endpoints and writes:

```text
outputs/model_comparison_qwen_vs_gemma/comparison/smoke_test_results.json
```

## Subset Test

Run a small subset before the full 520 chunks:

```bash
export LOCAL_LLM_API_KEY=dummy
bash scripts/run_qwen_gemma_chunk_comparison.sh \
  --chunks outputs/manuscript_self_secreting_selected_download/paper_chunks/paper_chunks.jsonl \
  --qwen-config configs/local_llm_qwen.yaml \
  --gemma-config configs/local_llm_gemma.yaml \
  --output outputs/model_comparison_qwen_vs_gemma \
  --max-chunks 5 \
  --force \
  --save-raw-responses
```

## Full Comparison

```bash
export LOCAL_LLM_API_KEY=dummy
bash scripts/run_qwen_gemma_chunk_comparison.sh \
  --chunks outputs/manuscript_self_secreting_selected_download/paper_chunks/paper_chunks.jsonl \
  --qwen-config configs/local_llm_qwen.yaml \
  --gemma-config configs/local_llm_gemma.yaml \
  --output outputs/model_comparison_qwen_vs_gemma \
  --max-chunks 520 \
  --resume \
  --save-raw-responses
```

Use `--no-raw-prompts` if the public archive should avoid saving raw chunk text in prompt files.

## Outputs

Per model:

- `llm_calls.jsonl`
- `agent_outputs/`
- `extracted_chunk_evidence.jsonl`
- `extracted_chunk_evidence_validated.jsonl`
- `extraction_failures.jsonl`
- `cytokine_fingerprint_aggregated.json`
- `physicell_parameter_proposals.json`
- `model_run_manifest.json`
- `README.txt`

Comparison outputs:

- `model_comparison_summary.csv`
- `model_comparison_summary.json`
- `cytokine_endpoint_agreement_matrix.csv`
- `cytokine_rank_comparison.csv`
- `evidence_coverage_by_model.csv`
- `citation_traceability_by_model.csv`
- `schema_validity_by_model.csv`
- `disagreement_cases.jsonl`
- `reviewer_interpretation.md`

## Interpretation Rules

- LLM outputs are structured extraction candidates, not biological proof.
- Missing DOI, PMID, PMCID, title, or chunk IDs are marked missing; they are not invented.
- Review-derived statements are marked as review evidence, not direct experimental evidence.
- Parameter proposals are bounded, provenance-linked, and require human review.
- Raw LLM output is not directly fed to PhysiCell.
- No PhysiCell run is performed by this comparison.
- Mock and replay fixtures are separate software fixtures and are not manuscript local-LLM evidence.

## Archive

After a comparison run:

```bash
python scripts/build_qwen_gemma_comparison_archive.py
```

This creates:

```text
dist/qwen_gemma_chunk_comparison_<commit_short>.zip
dist/qwen_gemma_chunk_comparison_<commit_short>.sha256
```

Do not commit the ZIP.

## Optional External PhysiCell

External PhysiCell execution is separate from this comparison and requires a local compiled executable:

```bash
export PHYSICELL_EXECUTABLE=/path/to/executable
cart-autolab simulate --config configs/experiment_cytokine_gpc3_liver_physicell.yaml
```

Human review is required before using parameter proposals for external PhysiCell simulation.
