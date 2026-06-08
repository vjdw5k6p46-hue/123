# LLM Agent Workflow

This workflow archive implements an LLM-guided, schema-constrained CAR-T in silico workflow with a real AutoResearch default path, deterministic reference execution for software testing, executable LLM-agent execution, hybrid validation, and external PhysiCell execution when configured.

## Reviewer Package State

The package includes executable LLM-agent infrastructure and public audit LLM audit artifacts. The default workflow path is the LLM-first AutoResearch configuration. A deterministic safe-demo configuration remains available for CI and dependency-free software testing.

Included public audit LLM artifacts include:

- `artifacts/00_llm_orchestrator/`
- `artifacts/00_llm_orchestrator/llm_calls.jsonl`
- `artifacts/00_llm_orchestrator/orchestrator_plan.json`
- `artifacts/00_llm_orchestrator/orchestrator_prompt.txt`
- `artifacts/00_llm_orchestrator/orchestrator_raw_response.txt`
- `artifacts/00_llm_orchestrator/orchestrator_validation.json`
- `artifacts/04_llm_parameter_rounds/llm_calls.jsonl`
- `artifacts/04_llm_parameter_rounds/agent_outputs/`
- `artifacts/06_refinement_loop_decision/`
- `artifacts/06_refinement_loop_decision/refinement_loop_decisions.json`
- `artifacts/06_refinement_loop_decision/llm_calls.jsonl`
- `artifacts/06_refinement_loop_decision/agent_outputs/`

The LLM Orchestrator artifact maps the package into seven public audit stages:

1. `research_goal_parsing`
2. `literature_retrieval_and_classification`
3. `central_hypothesis_generation`
4. `cytokine_fingerprint_parameterization`
5. `physicell_simulation_setup`
6. `simulation_analysis_and_refinement`
7. `final_report_generation`

## Execution Modes

Real AutoResearch mode is the default workflow path. It requires provider credentials for live LLM calls, online access for live literature retrieval/download, and `PHYSICELL_EXECUTABLE` for external PhysiCell execution.

Deterministic reference mode remains available through `configs/experiment_cytokine_gpc3_liver_safe_demo.yaml` and requires no API key, internet access, or external PhysiCell executable.

AutoResearch mode is the LLM-first workflow entry point. The default AutoResearch config uses an OpenAI-compatible provider for research-goal parsing, executable LLM agent audit steps, and refinement-loop decisions. Missing provider credentials or external PhysiCell setup should be reported as setup failures rather than replaced with fabricated output.

Executable LLM-agent mode is optional. When configured with an OpenAI-compatible provider, each LLM call records prompt text, raw response, parsed JSON, schema validation, and call metadata.

The AutoResearch layer uses `refinement_loop_decision_agent` as a schema-constrained refinement-loop decider when LLM mode is configured. The LLM reviews recorded simulation rankings, critique artifacts, and prior decisions, then returns whether refinement should continue, the next whitelisted action, stopping criteria, and the reason. The recorded decision for this package is archived under `artifacts/06_refinement_loop_decision/`. Python validates the decision, enforces `max_refinement_iterations`, and pauses when a requested next action needs human review or an external executor.

Executable LLM runs save prompt-response audit artifacts. These audit archives document completed runs; they are not a separate workflow mode.

Mock mode is for software tests only. Mock fixtures are not manuscript evidence and must not be interpreted as biological validation.

## Evidence-Grounded vs Simulation-Sensitivity Proposals

The workflow separates two proposal types and must not conflate them:

- `evidence_grounded_parameter_proposal` (round 1): LLM cytokine parameter proposals derived from supplied literature/chunk context, deterministically schema/range/provenance validated, treated as simulation hypotheses (model inputs) rather than measured biological constants.
- `simulation_sensitivity_proposal` (round 2): exploratory tuning the LLM proposes after reviewing round-1 in silico metrics (tumor-control ranking and CAR-T exhaustion trends). It is a model input, not biological evidence; it is `not_wet_lab_validation` and `not_manuscript_biological_evidence`, and it does not overwrite (`may_update_final_evidence_grounded_fingerprint: false`) the evidence-grounded fingerprint. Its role is to test whether the round-1 ranking is stable under a plausible sensitivity adjustment.

## Audit Records

Each executable LLM call should save:

- `llm_calls.jsonl`
- `agent_outputs/<agent_name>/<call_id>_prompt.txt`
- `agent_outputs/<agent_name>/<call_id>_raw_response.txt`
- `agent_outputs/<agent_name>/<call_id>_parsed.json`
- `agent_outputs/<agent_name>/<call_id>_validation.json`

The LLM layer does not replace deterministic simulation or wet-lab validation. It proposes structured hypotheses, cytokine fingerprints, or simulation-ready parameter proposals from supplied literature/chunk context. These outputs are schema/range checked before simulation.

If citation metadata are missing, the workflow should mark them as missing or low-confidence. It must not fabricate citations, LLM outputs, PhysiCell outputs, or wet-lab values.
