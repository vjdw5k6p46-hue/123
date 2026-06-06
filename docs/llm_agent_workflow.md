# LLM Agent Workflow

This workflow archive implements an LLM-guided, schema-constrained CAR-T in silico workflow with deterministic reference execution, optional executable LLM-agent execution, archived/replay execution, and optional external PhysiCell execution.

## Reviewer Package State

The package includes executable LLM-agent infrastructure and public audit LLM audit artifacts. The default reproducible command remains deterministic, but LLM-backed runs can be executed when provider credentials are configured.

Included public audit LLM artifacts include:

- `artifacts/00_llm_orchestrator/`
- `artifacts/00_llm_orchestrator/llm_calls.jsonl`
- `artifacts/00_llm_orchestrator/orchestrator_plan.json`
- `artifacts/00_llm_orchestrator/orchestrator_prompt.txt`
- `artifacts/00_llm_orchestrator/orchestrator_raw_response.txt`
- `artifacts/00_llm_orchestrator/orchestrator_validation.json`
- `artifacts/04_llm_parameter_rounds/llm_calls.jsonl`
- `artifacts/04_llm_parameter_rounds/agent_outputs/`

The LLM Orchestrator artifact maps the package into seven public audit stages:

1. `research_goal_parsing`
2. `literature_retrieval_and_classification`
3. `central_hypothesis_generation`
4. `cytokine_fingerprint_parameterization`
5. `physicell_simulation_setup`
6. `simulation_analysis_and_refinement`
7. `final_report_generation`

## Execution Modes

Deterministic reference mode remains the default and requires no API key, internet access, or external PhysiCell executable.

Executable LLM-agent mode is optional. When configured with an OpenAI-compatible provider, each LLM call records prompt text, raw response, parsed JSON, schema validation, and call metadata.

Archived/replay mode is optional and reuses archived prompt-response artifacts without making live LLM calls.

Mock mode is for software tests only. Mock and replay fixtures are not manuscript evidence and must not be interpreted as biological validation.

## Audit Records

Each executable LLM call should save:

- `llm_calls.jsonl`
- `agent_outputs/<agent_name>/<call_id>_prompt.txt`
- `agent_outputs/<agent_name>/<call_id>_raw_response.txt`
- `agent_outputs/<agent_name>/<call_id>_parsed.json`
- `agent_outputs/<agent_name>/<call_id>_validation.json`

The LLM layer does not replace deterministic simulation or wet-lab validation. It proposes structured hypotheses, cytokine fingerprints, or simulation-ready parameter proposals from supplied literature/chunk context. These outputs are schema/range checked before simulation.

If citation metadata are missing, the workflow should mark them as missing or low-confidence. It must not fabricate citations, LLM outputs, PhysiCell outputs, or wet-lab values.
