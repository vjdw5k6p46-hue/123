# Integration Status

## Branches Integrated

The `integration/reviewer-response-stack` branch integrates:

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
- `python scripts/check_reviewer_response_consistency.py --include-outputs`

## Tests Passed / Failed

- `pytest`: passed
- reviewer reproducibility demo: passed
- reviewer-response consistency checker: passed
- Failed tests remaining: none

## Remaining Limitations

- Live LLM execution is optional and requires provider credentials.
- The reviewer-safe LLM mock and replay demos use software fixtures only.
- Mock and replay outputs are not manuscript evidence and do not validate the biology.
- Wet-lab concordance is not evaluated unless a user supplies a validation table.
- External PhysiCell execution requires a local compiled executable.
- Mock simulator outputs are software testing artifacts and are not external PhysiCell outputs.

## Real LLM Manuscript Artifacts

Real OpenAI-compatible LLM audit artifacts are included for the reviewer-facing AutoResearch package, including the LLM Orchestrator output, prompt/response records, parsed JSON, and validation files. Mock and replay software fixtures remain clearly labeled as offline testing artifacts and are not manuscript evidence.

## Real External PhysiCell Output Artifacts

Local PhysiCell cytokine-arm simulation summary artifacts are included for the low-antigen runs, including summary/ranking outputs used by the final report. Large raw PhysiCell output folders, compiled binaries, and control-arm XML files are not included.

## Reviewer-Safe Outputs

Generated reviewer demo outputs are intentionally ignored by Git under `outputs/` and are not committed.
