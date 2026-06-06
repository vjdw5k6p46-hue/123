from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Callable

from cart_autolab.prompts import get_agent_prompt

from .audit import LLMCallRecord, append_llm_call, write_json
from .client import LLMConfig, load_llm_config
from .providers import LLMProviderError, build_provider
from .schema_validation import ValidationReport, validate_output


class InvalidLLMOutputError(RuntimeError):
    pass


class AgentRunner:
    def __init__(self, llm_config: LLMConfig | dict[str, Any] | None, run_dir: str | Path):
        self.config = llm_config if isinstance(llm_config, LLMConfig) else load_llm_config(llm_config)
        self.run_dir = Path(run_dir)
        self.provider = build_provider(self.config, self.run_dir)

    def run(
        self,
        agent_name: str,
        input_variables: dict[str, Any],
        *,
        schema: Any = None,
        validator: Callable[[Any], Any] | None = None,
        input_artifacts: list[str | Path] | None = None,
        parse_json: bool = True,
    ) -> dict[str, Any]:
        prompt = self._render_prompt(agent_name, input_variables)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        call_id = f"{agent_name}-{uuid.uuid4().hex[:12]}"
        agent_dir = self.run_dir / "agent_outputs" / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = agent_dir / f"{call_id}_prompt.txt"
        raw_path = agent_dir / f"{call_id}_raw_response.txt"
        parsed_path = agent_dir / f"{call_id}_parsed.json"
        validation_path = agent_dir / f"{call_id}_validation.json"
        prompt_path.write_text(prompt, encoding="utf-8")

        retry_count = 0
        raw_text = ""
        parsed: Any = None
        validation = ValidationReport(status="not_run")
        warnings: list[str] = []
        error: Exception | None = None
        max_attempts = max(1, int(self.config.max_retries) + 1)

        for attempt in range(max_attempts):
            retry_count = attempt
            try:
                response = self.provider.generate(agent_name=agent_name, prompt=prompt, prompt_hash=prompt_hash, call_id=call_id)
                raw_text = response.raw_text
                warnings = list(response.warnings)
                raw_path.write_text(raw_text, encoding="utf-8")
                if parse_json:
                    parsed = self._parse_json(raw_text)
                else:
                    parsed = {"raw_text": raw_text}
                write_json(parsed_path, parsed)
                if self.config.schema_validation:
                    validation = validate_output(parsed, schema=schema, validator=validator)
                else:
                    validation = ValidationReport(status="disabled")
                warnings.extend(validation.warnings)
                write_json(validation_path, validation.model_dump())
                if validation.status == "passed" or validation.status == "disabled":
                    self._append_record(call_id, agent_name, prompt_hash, input_artifacts, raw_path, parsed_path, validation.status, retry_count, warnings)
                    return {
                        "call_id": call_id,
                        "agent_name": agent_name,
                        "prompt_hash": prompt_hash,
                        "raw_response_path": str(raw_path),
                        "parsed_json_path": str(parsed_path),
                        "validation_path": str(validation_path),
                        "parsed": parsed,
                        "validation": validation.model_dump(),
                        "warnings": warnings,
                    }
                error = InvalidLLMOutputError(f"LLM output failed schema validation: {validation.errors}")
            except (json.JSONDecodeError, LLMProviderError, InvalidLLMOutputError) as exc:
                error = exc
                if not raw_path.exists():
                    raw_path.write_text(raw_text, encoding="utf-8")
                write_json(parsed_path, {"parse_error": str(exc), "raw_response_path": str(raw_path)})
                validation = ValidationReport(status="invalid_json" if isinstance(exc, json.JSONDecodeError) else "failed", errors=[str(exc)])
                write_json(validation_path, validation.model_dump())
                if isinstance(exc, LLMProviderError):
                    break

        status = validation.status
        self._append_record(call_id, agent_name, prompt_hash, input_artifacts, raw_path, parsed_path, status, retry_count, warnings)
        raise InvalidLLMOutputError(f"Invalid LLM output for {agent_name}: {error}")

    def _render_prompt(self, agent_name: str, input_variables: dict[str, Any]) -> str:
        prompt_def = get_agent_prompt(agent_name)
        system_prompt = prompt_def["system_prompt"].strip()
        try:
            user_prompt = prompt_def["user_prompt_template"].format(**input_variables).strip()
        except KeyError as exc:
            raise ValueError(f"Missing input variable for {agent_name}: {exc.args[0]}") from exc
        return f"System:\n{system_prompt}\n\nUser:\n{user_prompt}\n"

    def _parse_json(self, raw_text: str) -> Any:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return json.loads(text)

    def _append_record(
        self,
        call_id: str,
        agent_name: str,
        prompt_hash: str,
        input_artifacts: list[str | Path] | None,
        raw_path: Path,
        parsed_path: Path,
        validation_status: str,
        retry_count: int,
        warnings: list[str],
    ) -> None:
        append_llm_call(
            self.run_dir,
            LLMCallRecord(
                call_id=call_id,
                agent_name=agent_name,
                provider=self.config.provider,
                model=self.config.model,
                temperature=float(self.config.temperature),
                seed=self.config.seed,
                prompt_hash=prompt_hash,
                input_artifacts=[str(path) for path in input_artifacts or []],
                raw_response_path=str(raw_path),
                parsed_json_path=str(parsed_path),
                schema_validation_status=validation_status,
                retry_count=retry_count,
                warnings=warnings,
            ),
        )
