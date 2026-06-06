import json
from pathlib import Path

import pytest

from cart_autolab.llm import AgentRunner, InvalidLLMOutputError


def _search_inputs():
    return {
        "experiment_config": json.dumps(
            {
                "car_target_antigen": "GPC3",
                "tumor_type": "liver cancer",
                "candidate_interventions": ["IL-15"],
            }
        )
    }


def test_mock_agent_runner_writes_artifacts(tmp_path):
    config = {
        "provider": "mock",
        "mode": "llm",
        "model": "mock-fixture",
        "temperature": 0,
        "seed": 1729,
        "mock_responses": {
            "search_planner_agent": {
                "queries": [{"source": "PubMed", "query": "GPC3 CAR T IL-15", "rationale": "software fixture"}],
                "must_include_terms": ["GPC3"],
                "optional_terms": ["IL-15"],
                "exclusion_terms": [],
                "fixture_type": "software_test_fixture",
            }
        },
    }
    runner = AgentRunner(config, tmp_path)

    result = runner.run(
        "search_planner_agent",
        _search_inputs(),
        schema={"required": ["queries", "fixture_type"]},
        input_artifacts=[tmp_path / "experiment_config.yaml"],
    )

    assert result["parsed"]["fixture_type"] == "software_test_fixture"
    assert Path(result["raw_response_path"]).exists()
    assert Path(result["parsed_json_path"]).exists()
    assert Path(result["validation_path"]).exists()
    assert (tmp_path / "agent_outputs" / "search_planner_agent").exists()

    records = [json.loads(line) for line in (tmp_path / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["agent_name"] == "search_planner_agent"
    assert records[0]["provider"] == "mock"
    assert records[0]["schema_validation_status"] == "passed"
    assert records[0]["prompt_hash"]
    assert "software fixture" in " ".join(records[0]["warnings"]).lower()


def test_agent_runner_rejects_invalid_json_after_saving_artifacts(tmp_path):
    runner = AgentRunner(
        {
            "provider": "mock",
            "mode": "llm",
            "max_retries": 0,
            "mock_responses": {"search_planner_agent": "not json"},
        },
        tmp_path,
    )

    with pytest.raises(InvalidLLMOutputError):
        runner.run("search_planner_agent", _search_inputs(), schema={"required": ["queries"]})

    records = [json.loads(line) for line in (tmp_path / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert records[0]["schema_validation_status"] == "invalid_json"
    assert Path(records[0]["raw_response_path"]).read_text(encoding="utf-8") == "not json"
    validation = json.loads(Path(records[0]["parsed_json_path"]).read_text(encoding="utf-8"))
    assert "parse_error" in validation


def test_provider_none_fails_clearly_when_runner_is_called(tmp_path):
    runner = AgentRunner({"provider": "none"}, tmp_path)
    with pytest.raises(InvalidLLMOutputError, match="provider is 'none'"):
        runner.run("search_planner_agent", _search_inputs())
