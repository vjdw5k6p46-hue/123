# Final Reviewer Response Checklist

This checklist summarizes stabilization work for the LLM-guided, schema-constrained CAR-T in silico workflow. It should be reviewed before merging any reviewer-facing branch.

## Required Wording Present

- Deterministic reference mode is distinguished from optional LLM execution.
- Prompt-response artifacts are documented for executable LLM-agent and replay modes.
- Schema validation is documented as software validation, not biological validation.
- Mock records are software fixtures.
- Mock records are not real scholarly citations.
- External PhysiCell mode is optional and requires local setup.

## Tests Run

- `pytest tests/test_reviewer_smoke_matrix.py tests/test_no_fabricated_artifacts.py`
- `pytest tests/test_llm_contribution_summary.py`
- `pytest`
- `python scripts/run_reviewer_reproducibility_demo.py --force`
- `bash scripts/run_reviewer_reproducibility_demo.sh --force`
- `python scripts/check_reviewer_response_consistency.py --include-outputs`

## Commands Run

Reviewer-safe commands:

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver.yaml
bash scripts/run_reviewer_reproducibility_demo.sh --force
cart-autolab ablation --config configs/experiment_cytokine_gpc3_liver_ablation.yaml
python scripts/check_reviewer_response_consistency.py --include-outputs
```

Optional external PhysiCell command:

```bash
export PHYSICELL_EXECUTABLE=/path/to/local/PhysiCell/project_executable
cart-autolab simulate --config configs/experiment_cytokine_gpc3_liver_physicell.yaml
```

## Passing / Failing Status

- Smoke matrix passed for the reviewer package.
- Full pytest passed for the reviewer package after reviewer artifact and contribution-summary additions.
- Demo runner produced all expected artifacts under `outputs/reviewer_demo/`.
- Consistency checker runs without external services and prints warnings rather than modifying files.
- Live LLM execution was not tested because tests must not require API keys.
- External PhysiCell execution was not run because tests must not require a compiled executable.

## Branches / PRs Created

- `audit/post-implementation-review`
- `test/full-workflow-smoke-tests`
- `feature/reviewer-artifact-runner`
- `analysis/llm-contribution-verification`
- `docs/manuscript-rebuttal-package`
- `qa/final-consistency-check`

Earlier implementation branches:

- `audit/reviewer-reproducibility`
- `feature/llm-agent-runner`
- `feature/executable-llm-agents`
- `feature/llm-evidence-to-parameters`
- `analysis/llm-ablation`
- `feature/physicell-external-mode`
- `docs/reviewer-response`
- `docs/final-reviewer-checklist`

## Remaining Limitations

- Mock and replay rows demonstrate software routing, provenance, and artifact generation only.
- Mock records are software fixtures and not real scholarly citations.
- Mock simulator outputs are not PhysiCell evidence.
- Wet-lab concordance is not evaluated unless a user-supplied validation table is provided.
- Live LLM runs require provider credentials and human review of generated outputs.
- External PhysiCell runs require a local build and human review of simulator outputs.

## Human Review Required Before Merge

- Scientific wording in rebuttal and manuscript snippets.
- Whether any prompt-defined agents should remain specification-only.
- Whether the optional LLM provider behavior is acceptable for the manuscript claims.
- Whether external PhysiCell setup instructions should pin a specific upstream commit.
- Whether reviewer demo artifacts are sufficient for the response package.

## Recommended Merge Order

1. `audit/reviewer-reproducibility`
2. `feature/llm-agent-runner`
3. `feature/executable-llm-agents`
4. `feature/llm-evidence-to-parameters`
5. `analysis/llm-ablation`
6. `feature/physicell-external-mode`
7. `test/full-workflow-smoke-tests`
8. `feature/reviewer-artifact-runner`
9. `analysis/llm-contribution-verification`
10. `docs/reviewer-response`
11. `docs/manuscript-rebuttal-package`
12. `audit/post-implementation-review`
13. `qa/final-consistency-check`

Documentation should be reviewed again if this reviewer package is split, rebased, or only partially merged.
