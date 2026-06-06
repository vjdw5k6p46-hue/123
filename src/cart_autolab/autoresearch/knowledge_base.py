from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ARTIFACT_PATTERNS = [
    "research_goal.json",
    "search_queries.json",
    "included_papers.json",
    "downloaded_papers_manifest.json",
    "paper_chunks/paper_chunks.jsonl",
    "llm_calls.jsonl",
    "agent_outputs/**/*.json",
    "extracted_evidence*.json",
    "hypotheses*.json",
    "parameter_fingerprints*.json",
    "physicell_ready_parameters.json",
    "simulation/plan.json",
    "simulation/parameters.json",
    "simulation/timeseries.csv",
    "simulation/conversion_report.json",
    "analysis_metrics.csv",
    "ranked_interventions.csv",
    "critique_report*.json",
    "final_report.md",
    "final_report.html",
    "autoresearch_final_report.md",
]


def build_knowledge_index(run_dir: Path) -> dict[str, Any]:
    artifacts = []
    seen: set[Path] = set()
    for pattern in ARTIFACT_PATTERNS:
        for path in run_dir.glob(pattern):
            if path.is_file() and path not in seen:
                seen.add(path)
                artifacts.append(_artifact_record(run_dir, path))
    memory_records = _load_jsonl(run_dir / "memory.jsonl")
    llm_calls = _load_jsonl(run_dir / "llm_calls.jsonl")
    included = _load_json(run_dir / "included_papers.json", [])
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "artifact_count": len(artifacts),
        "artifacts": sorted(artifacts, key=lambda row: row["path"]),
        "memory_record_count": len(memory_records),
        "memory_records": memory_records,
        "llm_call_count": len(llm_calls),
        "paper_count": len(included) if isinstance(included, list) else 0,
        "notes": [
            "This is an artifact index for auditability, not a scientific database.",
            "Mock/replay records remain software fixtures only.",
        ],
    }


def write_knowledge_index(run_dir: Path) -> Path:
    kb_dir = run_dir / "knowledge_base"
    kb_dir.mkdir(parents=True, exist_ok=True)
    path = kb_dir / "index.json"
    path.write_text(json.dumps(build_knowledge_index(run_dir), indent=2), encoding="utf-8")
    return path


def _artifact_record(run_dir: Path, path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(run_dir)),
        "bytes": path.stat().st_size,
        "stage": _infer_stage(path),
    }


def _infer_stage(path: Path) -> str:
    text = path.as_posix()
    if "search" in text or "included_papers" in text:
        return "knowledge_retrieval"
    if "llm_calls" in text or "agent_outputs" in text:
        return "llm_audit"
    if "hypotheses" in text:
        return "hypothesis_generation"
    if "parameter" in text or "physicell_ready" in text:
        return "experimental_design_in_silico_setup"
    if "simulation" in text:
        return "simulation"
    if "analysis" in text or "ranked" in text or "critique" in text:
        return "analysis_critique"
    if "report" in text:
        return "report"
    return "workflow"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
