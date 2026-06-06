# Historical PR Split Plan

This historical plan records how the reviewer-response work was originally divided into reviewable branches before this integration branch was assembled. The integrated branch contains the implemented stack described in the README, reviewer audit, smoke tests, and reviewer demo docs.

## PR 0: Audit Reviewer Reproducibility Gaps

- Branch: `audit/reviewer-reproducibility`
- Scope: Documentation only. Add repository rules and a reviewer reproducibility audit.
- Files likely touched: `AGENTS.md`, `docs/reviewer_reproducibility_audit.md`, `docs/pr_split_plan.md`
- Explicit non-goals: No source code changes, no simulation changes, no LLM execution, no manuscript wet-lab changes.
- Acceptance criteria: Only documentation and `AGENTS.md` are added or updated; no fabricated results; branch is committed; PR opened if possible.
- Tests to run: `pytest` is optional because this branch does not modify source code; run `git diff --check`.
- Dependency order: First.

## PR 1: Add Optional Executable LLM Agent Infrastructure

- Branch: `feature/llm-agent-runner`
- Scope: Add optional LLM provider, runner, replay, audit, and schema-validation infrastructure without changing deterministic defaults.
- Files likely touched: `src/cart_autolab/llm/`, configuration loading, focused tests under `tests/`.
- Explicit non-goals: Do not change simulation logic, PhysiCell adapter behavior, wet-lab data, or default deterministic run behavior.
- Acceptance criteria: `pytest` passes; default deterministic config runs without API keys; mock LLM provider creates `llm_calls.jsonl` and `agent_outputs/`; no fake scientific evidence is generated.
- Tests to run: `pytest`, plus targeted tests such as `pytest tests/test_llm_agent_runner.py tests/test_llm_replay.py tests/test_llm_audit_artifacts.py`.
- Dependency order: After PR 0.

## PR 2: Turn Prompt Definitions Into Executable LLM Agents

- Branch: `feature/executable-llm-agents`
- Scope: Add optional executable agents that call `AgentRunner` while preserving deterministic fallbacks.
- Files likely touched: `src/cart_autolab/agents/`, orchestrator or workflow configuration boundaries, related schemas, focused tests.
- Explicit non-goals: Do not require live API access; do not make LLM mode default; do not fabricate citations; do not change wet-lab claims.
- Acceptance criteria: Default config produces deterministic outputs as before; mock LLM config produces LLM artifact files; hybrid mode consumes validated LLM evidence; tests confirm LLM outputs affect downstream files only when enabled.
- Tests to run: `pytest`, plus new tests for executable agents and workflow mode routing.
- Dependency order: After PR 1, or based on `feature/llm-agent-runner` while the stack is being assembled.

## PR 3: Connect LLM-Derived Evidence to Cytokine Fingerprints

- Branch: `feature/llm-evidence-to-parameters`
- Scope: Load deterministic, LLM, or hybrid evidence and propagate validated LLM provenance into parameter fingerprints.
- Files likely touched: `src/cart_autolab/parameters/evidence_loader.py`, `src/cart_autolab/parameters/fingerprint_builder.py`, related schemas, `parameter_transformation_rules.json` generation, focused tests.
- Explicit non-goals: Do not break downstream analysis; do not require LLM for deterministic mode; do not create fake citations or biological validation.
- Acceptance criteria: `cart-autolab build-parameters --config configs/experiment_cytokine_gpc3_liver.yaml` still works; mock LLM config creates parameter fingerprints with LLM provenance; default deterministic behavior is preserved.
- Tests to run: `pytest`, targeted `pytest tests/test_llm_evidence_to_parameters.py`.
- Dependency order: After PR 1 and PR 2, or based on the feature stack with dependency stated clearly.

## PR 4: Add Deterministic Versus LLM Ablation Analysis

- Branch: `analysis/llm-ablation`
- Scope: Add ablation metrics and CLI support comparing deterministic-only, LLM-agent, and hybrid modes.
- Files likely touched: `src/cart_autolab/analysis/ablation.py`, `src/cart_autolab/analysis/evidence_metrics.py`, `src/cart_autolab/analysis/ranking_stability.py`, `src/cart_autolab/cli.py`, ablation config, focused tests.
- Explicit non-goals: No API key requirement; no PhysiCell executable requirement; no fabricated wet-lab validation values.
- Acceptance criteria: Ablation runs with deterministic and mock/replay modes; outputs clearly label mock/replay/demo status; wet-lab concordance is marked not evaluated unless a user-supplied validation table is provided.
- Tests to run: `pytest`, targeted `pytest tests/test_ablation_metrics.py`.
- Dependency order: After PR 1, PR 2, and PR 3, or based on the feature stack with dependency stated clearly.

## PR 5: Clarify External PhysiCell Execution Path

- Branch: `feature/physicell-external-mode`
- Scope: Improve external PhysiCell documentation, setup scripts, explicit external mode errors, execution logging, and non-fabricating output conversion.
- Files likely touched: `docs/physicell_external_mode.md`, `docs/third_party_dependencies.md`, `scripts/`, `configs/experiment_cytokine_gpc3_liver_physicell.yaml`, `src/cart_autolab/simulation/physicell_adapter.py`, `src/cart_autolab/simulation/physicell_output_converter.py`, focused tests.
- Explicit non-goals: Do not vendor the full PhysiCell source tree; do not commit binaries; do not commit large local outputs; do not fabricate timeseries data.
- Acceptance criteria: Default mock mode passes; external mode fails clearly when no executable is configured; converter does not fabricate missing values; documentation provides reproducible commands.
- Tests to run: `pytest`, targeted `pytest tests/test_physicell_output_converter.py tests/test_physicell_external_mode_errors.py`.
- Dependency order: Can proceed after PR 0; coordinate with other implementation PRs to avoid conflicts in simulator config and docs.

## PR 6: Update Reviewer-Facing Documentation and Rebuttal Wording

- Branch: `docs/reviewer-response`
- Scope: Update README and reviewer-facing documentation after implementation PRs, labeling unavailable features conservatively.
- Files likely touched: `README.md`, `docs/reviewer_response_implementation.md`, `docs/mock_data_policy.md`, `docs/llm_agent_workflow.md`, `docs/reproducibility_artifacts.md`, `docs/rebuttal_to_reviewer_llm_workflow.md`, `docs/manuscript_wording_revisions.md`.
- Explicit non-goals: Do not sound defensive; do not say mock data are scientific evidence; do not imply PhysiCell is authored by this project; do not overclaim autonomous operation.
- Acceptance criteria: Documentation matches implemented code; unavailable features are labeled conservatively; mock data are described as test fixtures; reviewer concern is addressed directly.
- Tests to run: `git diff --check`; optionally `pytest` if README-linked commands or config paths changed.
- Dependency order: After implementation PRs if possible.

## Final Self-Review Checklist

- Branch: Prefer a documentation branch after all prior branches, or include in PR 6 if that is the active reviewer-facing documentation branch.
- Scope: Create `docs/final_reviewer_response_checklist.md`.
- Files likely touched: `docs/final_reviewer_response_checklist.md`.
- Explicit non-goals: Do not claim incomplete features are implemented; do not fabricate test results.
- Acceptance criteria: Checklist reports branch names, changed files, tests run, test outcomes, remaining limitations, and human-review requirements.
- Tests to run: `git diff --check`; `pytest` if code changed in the same branch.
- Dependency order: Last.
