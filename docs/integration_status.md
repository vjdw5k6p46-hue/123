# Integration Status

## Source Stack

This workflow archive was assembled from the reviewer-response stack, including:

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

## Tests Run

- `pytest`
- `bash scripts/run_reviewer_reproducibility_demo.sh --force`

## Tests Passed / Failed

- `pytest`: passed
- reviewer reproducibility demo: passed
- Failed tests remaining: none

## Remaining Limitations

- Live LLM execution is optional and requires provider credentials.
- The reviewer-safe LLM mock demo uses software fixtures only.
- Mock outputs are not manuscript evidence and do not validate the biology.
- Wet-lab concordance is not evaluated unless a user supplies a validation table.
- External PhysiCell execution requires a local compiled executable.
- Mock simulator outputs are software testing artifacts and are not external PhysiCell outputs.

## Real LLM Manuscript Artifacts

Real OpenAI-compatible LLM audit artifacts are included for the public audit AutoResearch package, including the LLM Orchestrator output, prompt/response records, parsed JSON, and validation files. Mock software fixtures remain clearly labeled as offline testing artifacts and are not manuscript evidence.

## Real External PhysiCell Output Artifacts

Local PhysiCell cytokine-arm simulation summary artifacts are included for the low-antigen runs, including summary/ranking outputs used by the final report. Large raw PhysiCell output folders and compiled binaries are not included.

## Reviewer-Safe Outputs

Generated reproducibility demo outputs are intentionally ignored by Git under `outputs/` and are not committed.
