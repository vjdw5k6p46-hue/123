# Local LLM Manuscript Archive

This document describes how to generate a real executable local-LLM archive for the LLM-guided, schema-constrained CAR-T in silico workflow.

The archive is optional. It is not required for deterministic mode, CI, mock tests, replay tests, or external PhysiCell documentation.

## Requirements

- A local OpenAI-compatible chat-completions endpoint.
- A configured model name in `configs/experiment_cytokine_gpc3_liver_local_llm.yaml`.
- `LOCAL_LLM_API_KEY` set in the environment. For local endpoints that accept any bearer token, use `dummy`.
- A real curated literature file at `data/manuscript_literature/curated_papers.json`.

The curated literature file must contain real paper metadata and provenance. Do not use `data/mock_literature/` as manuscript evidence. Mock records are software fixtures only and are not real scholarly citations or manuscript evidence.

## Local Endpoint

Start a local OpenAI-compatible server using the backend available on your machine. The repository does not include model weights or prescribe a backend. Configure the server to expose:

```text
http://127.0.0.1:8000/v1/chat/completions
```

Then update the config if needed:

```yaml
llm:
  provider: openai_compatible
  model: local-model-name-here
  base_url: http://127.0.0.1:8000/v1
  api_key_env: LOCAL_LLM_API_KEY
```

## Curated Literature

Create the curated manuscript literature file:

```bash
cp data/manuscript_literature/curated_papers.template.json data/manuscript_literature/curated_papers.json
```

Replace the template with a JSON list of real paper records. Each record must include `title` and at least one provenance field: `doi`, `pmid`, `pmcid`, `url`, or `source_paper_id`.

Do not paste copyrighted full paper chunks unless the papers are open-access and provenance is documented. Prefer metadata, abstracts, or rights-compatible excerpts.

## Run Command

Do not run this command unless the local endpoint and curated literature file are ready:

```bash
export LOCAL_LLM_API_KEY=dummy
bash scripts/run_manuscript_local_llm_archive.sh
python scripts/build_manuscript_local_llm_archive.py
```

The runner checks that the configured endpoint is reachable and that `LOCAL_LLM_API_KEY` is set. If either condition is missing, it fails clearly before invoking the workflow.

## Produced Artifacts

The run writes artifacts under:

```text
outputs/manuscript_local_llm/
```

Expected audit and downstream artifacts include:

- `llm_calls.jsonl`
- `agent_outputs/`
- `extracted_evidence_llm.json`
- `extracted_evidence_hybrid.json`
- `parameter_fingerprints.json`
- `ranked_interventions.csv`
- `final_report.md`
- `local_llm_run_manifest.json`

The archive builder packages these outputs with selected reviewer docs and config files into:

```text
dist/cart_autolab_manuscript_local_llm_archive_<commit_short>.zip
dist/cart_autolab_manuscript_local_llm_archive_<commit_short>.sha256
```

The ZIP is a generated artifact and should not be committed.

## Interpreting LLM Audit Artifacts

`llm_calls.jsonl` records each executable LLM call, including agent name, provider, model, prompt hash, response artifact paths, schema validation status, retry count, and warnings.

`agent_outputs/` contains prompt text, raw local-LLM responses, parsed JSON, and validation reports. These artifacts are archived for auditability and replay comparison.

Local LLM outputs may vary by model, backend, quantization, prompt handling, and runtime settings. The archive records model name, base URL, temperature, seed, workflow settings, curated literature path, included-paper count, LLM call count, and downstream artifact locations.

## Separation From Fixtures

Mock and replay fixtures are separate from manuscript local-LLM evidence. They are used for offline software tests and CI only. Do not describe mock/replay outputs as real LLM evidence, scholarly citations, wet-lab data, or PhysiCell outputs.

The local LLM archive must use curated real paper metadata with provenance. The workflow still does not fabricate citations, LLM outputs, PhysiCell outputs, or wet-lab values.
