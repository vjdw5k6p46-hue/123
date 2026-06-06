from __future__ import annotations

from pydantic import BaseModel


class MemoryRecord(BaseModel):
    experiment_id: str
    stage: str
    path: str
    summary: str
    created_at: str
