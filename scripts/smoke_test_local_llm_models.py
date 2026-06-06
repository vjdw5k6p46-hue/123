from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test local Qwen and Gemma/Gamma OpenAI-compatible endpoints.")
    parser.add_argument("--qwen-config", default="configs/local_llm_qwen.yaml")
    parser.add_argument("--gemma-config", default="configs/local_llm_gemma.yaml")
    parser.add_argument("--output", default="outputs/model_comparison_qwen_vs_gemma/comparison/smoke_test_results.json")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models": {
            "qwen": smoke_one(Path(args.qwen_config)),
            "gemma": smoke_one(Path(args.gemma_config)),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [label for label, result in results["models"].items() if not result.get("passed")]
    print(json.dumps(results, indent=2))
    if failed and not args.allow_partial:
        raise SystemExit(f"Smoke test failed for: {', '.join(failed)}")
    return 0


def smoke_one(config_path: Path) -> dict:
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    api_key_env = cfg.get("api_key_env") or "LOCAL_LLM_API_KEY"
    api_key = os.getenv(api_key_env, "dummy")
    base_url = str(cfg.get("base_url") or "").rstrip("/")
    model = cfg.get("model")
    prompt = (
        "Return strict JSON only. Extract this tiny evidence record. "
        "Input: title='IL-15-armored CAR T cells improve persistence'; pmid='123'. "
        "Schema: {\"records\":[{\"cytokine\":\"IL-15\",\"endpoint\":\"persistence\",\"effect_direction\":\"increased\"}]}"
    )
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": cfg.get("temperature", 0)},
            timeout=int(cfg.get("timeout_seconds", 120)),
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(clean_json(raw))
        passed = isinstance(parsed, dict) and isinstance(parsed.get("records"), list)
        return {"config": str(config_path), "model": model, "base_url": base_url, "passed": passed, "raw_preview": raw[:200]}
    except Exception as exc:
        return {"config": str(config_path), "model": model, "base_url": base_url, "passed": False, "error": f"{type(exc).__name__}: {exc}"}


def clean_json(raw: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", raw.strip(), flags=re.S).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return text


if __name__ == "__main__":
    raise SystemExit(main())
