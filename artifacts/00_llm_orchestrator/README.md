# LLM Orchestrator Runtime Trace

This directory contains the real-time scheduling output of the LLM Orchestrator for the
gpt-4o-mini AutoResearch run. The orchestrator dispatches the seven public audit stages
in dependency order and records a runtime trace: per-stage scheduled/started/completed
runtime date/time values, durations, status, dependency resolution, dispatch events, and the LLM call
dispatched at run time.

This is a runtime dispatch trace (schema orchestrator_runtime_trace_v1), not a retrospective
artifact-mapping audit. Stage 4 and stage 6 dispatch records align with this run's recorded
llm_calls. It does not fabricate citations, LLM outputs, PhysiCell outputs, or wet-lab values.

Absolute runtime date/time values are removed or redacted in this public workflow archive; call IDs, prompt hashes, dependency order, validation status, and artifact paths are preserved.
