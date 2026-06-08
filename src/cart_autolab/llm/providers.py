from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import requests

from .client import LLMConfig


class LLMProviderError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    raw_text: str
    provider: str
    model: str | None
    temperature: float
    seed: int | None = None
    warnings: list[str] = field(default_factory=list)


class LLMProvider(Protocol):
    name: str

    def generate(self, *, agent_name: str, prompt: str, prompt_hash: str, call_id: str) -> LLMResponse:
        ...


class NoneProvider:
    name = "none"

    def __init__(self, config: LLMConfig, run_dir: Path):
        self.config = config

    def generate(self, *, agent_name: str, prompt: str, prompt_hash: str, call_id: str) -> LLMResponse:
        raise LLMProviderError("LLM provider is 'none'; no LLM call was made. Use deterministic workflow or configure mock or openai_compatible.")


class MockProvider:
    name = "mock"

    def __init__(self, config: LLMConfig, run_dir: Path):
        self.config = config

    def generate(self, *, agent_name: str, prompt: str, prompt_hash: str, call_id: str) -> LLMResponse:
        configured = self.config.mock_responses.get(agent_name)
        if isinstance(configured, list):
            payload = configured[0] if configured else {}
        elif configured is not None:
            payload = configured
        else:
            payload = {
                "fixture_type": "software_test_fixture",
                "agent_name": agent_name,
                "message": "Mock LLM provider response for software tests only; not manuscript evidence.",
            }
        raw = configured if isinstance(configured, str) else json.dumps(payload)
        return LLMResponse(
            raw_text=raw,
            provider=self.name,
            model=self.config.model or "mock-fixture",
            temperature=self.config.temperature,
            seed=self.config.seed,
            warnings=["Mock provider output is a software fixture only, not scientific evidence."],
        )


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, config: LLMConfig, run_dir: Path):
        self.config = config
        self.api_key_env = config.api_key_env or "OPENAI_API_KEY"
        self.api_key = os.getenv(self.api_key_env)
        self.base_url = (config.base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        if not self.api_key:
            raise LLMProviderError(f"OpenAI-compatible provider requires API key env var {self.api_key_env}.")
        if not config.model:
            raise LLMProviderError("OpenAI-compatible provider requires llm.model.")

    def generate(self, *, agent_name: str, prompt: str, prompt_hash: str, call_id: str) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.temperature,
        }
        if self.config.seed is not None and not self.config.omit_seed:
            payload["seed"] = self.config.seed
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=int(self.config.timeout_seconds or 60),
        )
        response.raise_for_status()
        data = response.json()
        raw = data["choices"][0]["message"]["content"]
        return LLMResponse(
            raw_text=raw,
            provider=self.name,
            model=self.config.model,
            temperature=self.config.temperature,
            seed=self.config.seed,
            warnings=[],
        )


def build_provider(config: LLMConfig, run_dir: Path) -> LLMProvider:
    provider = (config.provider or "none").lower()
    if provider == "none":
        return NoneProvider(config, run_dir)
    if provider == "mock":
        return MockProvider(config, run_dir)
    if provider == "openai_compatible":
        return OpenAICompatibleProvider(config, run_dir)
    raise LLMProviderError(f"Unsupported LLM provider '{config.provider}'. Allowed values: none, mock, openai_compatible.")
