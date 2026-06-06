from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .schemas import MemoryRecord


class MemoryStore:
    def __init__(self, run_dir: Path, experiment_id: str):
        self.run_dir = run_dir
        self.experiment_id = experiment_id
        self.path = run_dir / "memory.jsonl"

    def add(self, stage: str, artifact: Path, summary: str) -> None:
        record = MemoryRecord(
            experiment_id=self.experiment_id,
            stage=stage,
            path=str(artifact),
            summary=summary,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
