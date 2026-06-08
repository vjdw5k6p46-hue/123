from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMConfig:
    provider: str = "none"
    mode: str = "deterministic"
    model: str | None = None
    temperature: float = 0.0
    seed: int | None = 1729
    save_raw_responses: bool = True
    schema_validation: bool = True
    max_retries: int = 2
    api_key_env: str | None = None
    base_url: str | None = None
    omit_seed: bool = False
    timeout_seconds: int = 60
    mock_responses: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LLMConfig":
        data = data or {}
        defaults = cls()
        payload = {field_name: getattr(defaults, field_name) for field_name in cls.__dataclass_fields__}
        payload.update({k: v for k, v in data.items() if k in payload})
        return cls(**payload)


def load_llm_config(config: dict[str, Any] | None) -> LLMConfig:
    return LLMConfig.from_dict((config or {}).get("llm", config if config else {}))
