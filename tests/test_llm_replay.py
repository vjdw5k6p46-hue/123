import json

from cart_autolab.llm import AgentRunner


def test_replay_provider_loads_archived_response(tmp_path):
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    archived = {
        "queries": [{"source": "PubMed", "query": "GPC3 CAR T IL-15", "rationale": "archived fixture"}],
        "must_include_terms": ["GPC3"],
        "optional_terms": ["IL-15"],
        "exclusion_terms": [],
        "fixture_type": "archived_software_fixture",
    }
    (replay_dir / "search_planner_agent.json").write_text(json.dumps(archived), encoding="utf-8")

    runner = AgentRunner({"provider": "replay", "replay_dir": str(replay_dir), "model": "archived"}, tmp_path / "run")
    result = runner.run(
        "search_planner_agent",
        {"experiment_config": "{}"},
        schema={"required": ["queries", "fixture_type"]},
    )

    assert result["parsed"]["fixture_type"] == "archived_software_fixture"
    record = json.loads((tmp_path / "run" / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert record["provider"] == "replay"
    assert record["schema_validation_status"] == "passed"
    assert "archived response" in " ".join(record["warnings"])
