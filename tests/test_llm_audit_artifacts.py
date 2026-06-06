import json
from pathlib import Path

from cart_autolab.llm import AgentRunner


def test_llm_audit_record_contains_required_fields(tmp_path):
    runner = AgentRunner({"provider": "mock", "model": "mock-fixture", "temperature": 0, "seed": 1729}, tmp_path)
    runner.run("hypothesis_generation_agent", {"experiment_config": "{}", "evidence_records": "[]"})

    audit_path = tmp_path / "llm_calls.jsonl"
    assert audit_path.exists()
    record = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    for key in [
        "call_id",
        "agent_name",
        "provider",
        "model",
        "temperature",
        "seed",
        "prompt_hash",
        "input_artifacts",
        "raw_response_path",
        "parsed_json_path",
        "schema_validation_status",
        "retry_count",
        "timestamp",
        "warnings",
    ]:
        assert key in record
    assert Path(record["raw_response_path"]).exists()
    assert Path(record["parsed_json_path"]).exists()
    assert "fixture" in Path(record["raw_response_path"]).read_text(encoding="utf-8")
