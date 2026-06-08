from pathlib import Path

import yaml

from cart_autolab.autoresearch import AutoResearchWorkflow


def test_autoresearch_workflow_builds_on_existing_orchestrator(tmp_path):
    root = Path.cwd()
    config = yaml.safe_load((root / "configs" / "experiment_cytokine_gpc3_liver_autoresearch.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / "autoresearch")
    config["llm"] = {"provider": "none", "mode": "deterministic"}
    config["autoresearch"]["goal_source"] = "deterministic"
    config["autoresearch"]["refinement_controller_source"] = "deterministic"
    config_path = tmp_path / "autoresearch.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = AutoResearchWorkflow(config_path).run()
    run_dir = Path(result["run_dir"])

    expected = [
        "research_goal.json",
        "knowledge_base/index.json",
        "ranked_hypotheses.json",
        "ranked_hypotheses.csv",
        "simulation_design_plan.json",
        "refinement_loop_decisions.json",
        "refinement_trace.json",
        "artifact_manifest.json",
        "autoresearch_final_report.md",
        "autoresearch_final_report.html",
        "final_report.md",
        "memory.jsonl",
    ]
    for rel in expected:
        assert (run_dir / rel).exists(), rel

    report = (run_dir / "autoresearch_final_report.md").read_text(encoding="utf-8")
    assert "LLM-guided, schema-constrained CAR-T in silico workflow" in report
    assert "Mock records are software fixtures only" in report
    assert "No fabricated citations" in report
    assert "External PhysiCell executed: False" in report


def test_autoresearch_skip_base_run_summarizes_existing_artifacts(tmp_path):
    run_dir = tmp_path / "existing"
    run_dir.mkdir()
    (run_dir / "ranked_interventions.csv").write_text("intervention_name,ranked_intervention_score\nIL-15,0.9\n", encoding="utf-8")
    (run_dir / "parameter_fingerprints.json").write_text(
        '[{"intervention_name":"IL-15","confidence_score":0.7,"uncertainty":0.2}]',
        encoding="utf-8",
    )
    config = yaml.safe_load((Path.cwd() / "configs" / "experiment_cytokine_gpc3_liver_autoresearch.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(run_dir)
    config["llm"] = {"provider": "none", "mode": "deterministic"}
    config["autoresearch"]["goal_source"] = "deterministic"
    config["autoresearch"]["refinement_controller_source"] = "deterministic"
    config_path = tmp_path / "autoresearch.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = AutoResearchWorkflow(config_path).run(skip_base_run=True)
    assert Path(result["ranked_hypotheses"]["json"]).exists()
    assert (run_dir / "knowledge_base" / "index.json").exists()


def test_autoresearch_optional_llm_steps_use_agent_runner_with_mock_provider(tmp_path):
    config = yaml.safe_load((Path.cwd() / "configs" / "experiment_cytokine_gpc3_liver_autoresearch.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / "autoresearch_llm")
    config["llm"] = {
        "provider": "mock",
        "mode": "llm",
        "model": "mock-fixture",
        "temperature": 0,
        "schema_validation": True,
        "max_retries": 0,
        "mock_responses": {
            "orchestrator_agent": {"workflow_steps": [], "required_inputs": [], "expected_outputs": []},
            "search_planner_agent": {"queries": [], "must_include_terms": [], "optional_terms": [], "exclusion_terms": []},
            "hypothesis_generation_agent": {
                "hypotheses": [{"hypothesis_type": "central", "hypothesis": "software fixture", "candidate_intervention_arms": []}],
                "ranked_candidate_interventions_for_followup": [],
                "papers_to_download_before_parameterization": [],
            },
            "parameter_builder_agent": {"parameter_sets": [], "transformation_rules": [], "uncertainty": [], "low_confidence_flags": []},
            "simulation_design_agent": {"simulation_plan": {}, "random_seeds": [], "parameter_sweeps": [], "controls": []},
            "analysis_agent": {"metrics": [], "uncertainty_intervals": [], "ranked_interventions": []},
            "critique_agent": {"biological_interpretation": "software fixture", "limitations": [], "recommended_validation_experiments_high_level": []},
            "report_agent": {"markdown_report": "software fixture", "html_report": ""},
        },
    }
    config_path = tmp_path / "autoresearch_mock_llm.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = AutoResearchWorkflow(config_path).run()
    run_dir = Path(result["run_dir"])
    status = yaml.safe_load((run_dir / "autoresearch_llm_step_status.json").read_text(encoding="utf-8"))

    assert len(status["steps"]) == 8
    assert all(step["status"] == "completed" for step in status["steps"])
    assert (run_dir / "llm_calls.jsonl").exists()
    assert (run_dir / "agent_outputs" / "orchestrator_agent").exists()
    assert (run_dir / "autoresearch_report_llm.json").exists()


def test_autoresearch_step1_can_parse_research_goal_with_mock_llm(tmp_path):
    run_dir = tmp_path / "autoresearch_goal_llm"
    run_dir.mkdir()
    (run_dir / "ranked_interventions.csv").write_text("intervention_name,ranked_intervention_score\nIL-15,0.9\n", encoding="utf-8")
    (run_dir / "parameter_fingerprints.json").write_text(
        '[{"intervention_name":"IL-15","confidence_score":0.7,"uncertainty":0.2}]',
        encoding="utf-8",
    )
    config = yaml.safe_load((Path.cwd() / "configs" / "experiment_cytokine_gpc3_liver_autoresearch.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(run_dir)
    config["autoresearch"]["goal_source"] = "llm"
    config["autoresearch"]["research_question"] = "Which self-secreting cytokine CAR-T is best for low-antigen GPC3 liver cancer?"
    config["autoresearch"]["llm_steps"] = []
    config["llm"] = {
        "provider": "mock",
        "mode": "llm",
        "model": "mock-fixture",
        "temperature": 0,
        "schema_validation": True,
        "max_retries": 0,
        "mock_responses": {
            "research_goal_parser_agent": {
                "research_question": "Which self-secreting cytokine CAR-T is best for low-antigen GPC3 liver cancer?",
                "disease_context": "GPC3-positive liver cancer",
                "tumor_context": {
                    "target_antigen": "GPC3",
                    "antigen_density_condition": "low",
                    "role": "fixed simulation scenario, not an LLM-optimized tumor parameter",
                    "background_terms": ["low antigen", "GPC3", "hepatocellular carcinoma"],
                },
                "cell_therapy": {
                    "therapy_type": "CAR-T",
                    "engineering_mode": "self-secreting/armored cytokine CAR-T",
                    "candidate_interventions": ["IL-2", "IL-7", "IL-12", "IL-15", "IL-18"],
                },
                "search_scope": {
                    "must_include": ["engineered T cells", "self-secreting cytokine"],
                    "should_include": ["CAR-T persistence", "cytotoxicity", "exhaustion"],
                    "exclude": ["external cytokine bath only"],
                    "retrieval_queries": ["GPC3 CAR-T low antigen self secreting IL-15"],
                },
                "intervention_variables": ["cytokine payload"],
                "fixed_scenario_constraints": ["low-antigen tumor background"],
                "simulation_outputs_needed": ["PhysiCell-ready cytokine CAR-T configs", "ranked cytokine interventions"],
                "guardrails": ["Do not fabricate citations."],
            }
        },
    }
    config_path = tmp_path / "autoresearch_goal_llm.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = AutoResearchWorkflow(config_path).run(skip_base_run=True)
    output_dir = Path(result["run_dir"])
    goal = yaml.safe_load((output_dir / "research_goal.json").read_text(encoding="utf-8"))
    status = yaml.safe_load((output_dir / "research_goal_parse_status.json").read_text(encoding="utf-8"))

    assert goal["goal_source"] == "llm_research_goal_parser"
    assert goal["parsed_research_goal"]["search_scope"]["exclude"] == ["external cytokine bath only"]
    assert goal["candidate_interventions"] == ["control", "IL-2", "IL-7", "IL-12", "IL-15", "IL-18"]
    assert status["status"] == "completed"
    assert (output_dir / "llm_calls.jsonl").exists()
    assert (output_dir / "agent_outputs" / "research_goal_parser_agent").exists()


def test_autoresearch_llm_can_decide_refinement_loop_continuation(tmp_path):
    run_dir = tmp_path / "autoresearch_refinement_llm"
    run_dir.mkdir()
    (run_dir / "ranked_interventions.csv").write_text(
        "intervention_name,ranked_intervention_score\nIL-15,0.9\nIL-12,0.7\n",
        encoding="utf-8",
    )
    (run_dir / "critique_report.json").write_text(
        '{"limitations":["single simulation pass"],"biological_interpretation":"software fixture"}',
        encoding="utf-8",
    )
    (run_dir / "parameter_fingerprints.json").write_text(
        '[{"intervention_name":"IL-15","confidence_score":0.7,"uncertainty":0.2}]',
        encoding="utf-8",
    )
    config = yaml.safe_load((Path.cwd() / "configs" / "experiment_cytokine_gpc3_liver_autoresearch.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(run_dir)
    config["autoresearch"]["llm_steps"] = []
    config["autoresearch"]["refinement_controller_source"] = "llm"
    config["autoresearch"]["max_refinement_iterations"] = 2
    config["autoresearch"]["auto_execute_refinement_actions"] = False
    config["llm"] = {
        "provider": "mock",
        "mode": "llm",
        "model": "mock-fixture",
        "temperature": 0,
        "schema_validation": True,
        "max_retries": 0,
        "mock_responses": {
            "refinement_loop_decision_agent": {
                "iteration": 1,
                "continue_refinement": True,
                "next_action": "request_parameter_refinement",
                "reason": "Software fixture asks for one more bounded parameter refinement before report.",
                "stopping_criteria_met": False,
                "stopping_criteria": ["ranking stable", "toxicity bounded"],
                "requested_inputs_for_next_loop": ["refined parameter proposal"],
                "parameter_or_simulation_focus": ["IL-12 toxicity", "IL-15 persistence"],
                "confidence": 0.6,
                "human_review_required": True,
                "do_not_overinterpret": ["mock fixture decision"],
            }
        },
    }
    config_path = tmp_path / "autoresearch_refinement_llm.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = AutoResearchWorkflow(config_path).run(skip_base_run=True)
    output_dir = Path(result["run_dir"])
    trace = yaml.safe_load((output_dir / "refinement_loop_decisions.json").read_text(encoding="utf-8"))

    assert trace["controller"] == "llm_refinement_loop_decision_agent"
    assert trace["status"] == "paused_for_human_or_external_executor"
    assert trace["iterations"][0]["decision_source"] == "llm"
    assert trace["iterations"][0]["continue_refinement"] is True
    assert trace["iterations"][0]["next_action"] == "request_parameter_refinement"
    assert trace["iterations"][0]["execution_status"] == "not_executed"
    assert (output_dir / "agent_outputs" / "refinement_loop_decision_agent").exists()
