# Reviewer Offline Release Notes

This offline package supports review of the integrated reviewer-response branch:

`integration/reviewer-response-stack`

It packages the LLM-guided, schema-constrained CAR-T in silico workflow as a local, reviewer-safe snapshot. It is intended for offline inspection and reproduction of deterministic, mock LLM, and ablation software paths.

## What Is Included

- Integrated source snapshot from `integration/reviewer-response-stack`.
- Reviewer commands and documentation.
- Local verification logs for installation, pytest, and reproducibility demo generation.
- Reproducibility demo artifacts under `outputs/reviewer_demo/`.
- Mock LLM audit artifacts, including `llm_calls.jsonl`, prompt files, raw response fixture files, parsed JSON, and validation reports.
- Ablation outputs and `llm_contribution_summary.csv`.
- Limitations, mock-data policy, external PhysiCell notes, rebuttal wording, and manuscript revision snippets.
- `MANIFEST.json` with commit hash, command exit codes, included outputs, and SHA256 checksums for key files.

## Reviewer Commands

From the unpacked package directory:

```bash
python -m pip install -e .[dev]
pytest
bash scripts/run_reviewer_reproducibility_demo.sh --force
```

Shortest reviewer entry points:

```bash
python -m cart_autolab.cli run-all --config configs/experiment_cytokine_gpc3_liver.yaml
bash scripts/run_reviewer_reproducibility_demo.sh --force
```

## Key Artifact Locations

- Deterministic report: `outputs/reviewer_demo/deterministic/final_report.md`
- LLM mock audit log: `outputs/reviewer_demo/llm_mock/llm_calls.jsonl`
- LLM mock agent artifacts: `outputs/reviewer_demo/llm_mock/agent_outputs/`
- Ablation summary: `outputs/reviewer_demo/ablation/ablation_summary.csv`
- Ranking comparison: `outputs/reviewer_demo/ablation/ranking_comparison.csv`
- LLM contribution summary: `outputs/reviewer_demo/llm_contribution_summary.csv`
- Package manifest: `MANIFEST.json`
- Local run logs: `logs/`

## Limitations

- Mock outputs are software fixtures only.
- Mock records are not real scholarly citations, not manuscript evidence, and not substitutes for wet-lab validation.
- The package does not fabricate citations, LLM outputs, PhysiCell outputs, or wet-lab values.
- Real OpenAI-compatible LLM audit artifacts are included for the public audit AutoResearch package.
- Local PhysiCell cytokine-arm simulation summary artifacts are included for the low-antigen runs; large raw output folders and compiled binaries are not included.
- Live LLM execution requires provider credentials and is optional.
- External PhysiCell execution requires a locally compiled executable configured through `PHYSICELL_EXECUTABLE`.
- Wet-lab concordance is not evaluated unless the user supplies a validation table.

## Citation-Safe Wording

The repository implements an LLM-guided, schema-constrained CAR-T in silico workflow with deterministic reference mode, optional executable LLM-agent mode, hybrid validation, and optional external PhysiCell execution. Mock records demonstrate software behavior only and must not be described as biological validation or manuscript evidence.

## Regenerating Reviewer Demo Outputs

The reviewer-safe demo can be regenerated locally:

```bash
bash scripts/run_reviewer_reproducibility_demo.sh --force
```

This command does not require an API key, internet access, or a compiled PhysiCell executable. It writes deterministic, mock, and ablation artifacts under `outputs/reviewer_demo/`.

## Release Asset Command

After the ZIP is generated, a maintainer can upload it manually. If GitHub CLI is available, the command format is:

```bash
gh release create v0.2-reviewer-response-offline dist/cart_autolab_reviewer_response_offline_<commit_short>.zip --notes-file docs/reviewer_offline_release_notes.md --target integration/reviewer-response-stack
```

Do not use this command until the generated ZIP path and target commit have been reviewed.
