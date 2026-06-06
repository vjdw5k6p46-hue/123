from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class LLMCallRecord:
    call_id: str
    agent_name: str
    provider: str
    model: str | None
    temperature: float
    seed: int | None
    prompt_hash: str
    input_artifacts: list[str] = field(default_factory=list)
    raw_response_path: str | None = None
    parsed_json_path: str | None = None
    schema_validation_status: str = "not_run"
    retry_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    warnings: list[str] = field(default_factory=list)


def append_llm_call(run_dir: Path, record: LLMCallRecord) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "llm_calls.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
    return path


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
