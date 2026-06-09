# Workflow Audit Summary

This directory contains a public, post-processed workflow audit summary. It maps recorded artifacts into reviewer-facing stages, but it is not a real-time scheduler trace and it did not drive workflow execution.

The actual workflow control flow is executed by Python (`AutolabOrchestrator.run_all` and the AutoResearch workflow wrapper). LLM agents contribute to selected steps such as goal parsing, hypothesis generation, parameter proposal, simulation-sensitivity refinement, and refinement-loop decision.

This summary intentionally does not report `duration_seconds`, `wall_clock_seconds`, `scheduled_at`, `started_at`, or `completed_at`, because this public artifact was assembled after execution and does not contain independently measured timing markers.

Use `workflow_audit_summary.json` as an artifact dependency map, not as evidence that an LLM dispatched stages live.
