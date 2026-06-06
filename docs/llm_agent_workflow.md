# LLM Agent Workflow

The intended framing is an LLM-guided, schema-constrained CAR-T in silico workflow.

## Current Main Branch

The current `main` branch exports prompt definitions in `cart_autolab.prompts`, but the default executable workflow is deterministic. The deterministic workflow performs query generation, metadata screening, evidence extraction, parameter construction, mock simulation, analysis, critique, and reporting without live LLM calls.

## Draft Implementation Branches

Draft PRs add optional executable LLM-agent mode and archived/replay mode. These modes are optional and are not the default.

In executable LLM-agent mode, each LLM call should save:

- `llm_calls.jsonl`
- `agent_outputs/<agent_name>/<call_id>_prompt.txt`
- `agent_outputs/<agent_name>/<call_id>_raw_response.txt`
- `agent_outputs/<agent_name>/<call_id>_parsed.json`
- `agent_outputs/<agent_name>/<call_id>_validation.json`

The LLM layer does not replace deterministic simulation or wet-lab validation. It performs biological knowledge synthesis by converting dispersed CAR-T/cytokine evidence into structured, machine-readable cytokine functional fingerprints, which are then bounded and validated by deterministic schemas before simulation.

If citation metadata are missing, the workflow should mark them as missing or low-confidence. It must not fabricate citations.
