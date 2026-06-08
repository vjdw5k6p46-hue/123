import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

from cart_autolab.orchestrator import AutolabOrchestrator
from cart_autolab.simulation.physicell_output_converter import PhysiCellOutputConverter


ROOT = Path(__file__).resolve().parents[1]


def _write_tmp_config(tmp_path: Path, source_config: str, output_name: str) -> Path:
    config = yaml.safe_load((ROOT / source_config).read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / output_name)
    if "ablation" in config:
        config["ablation"]["output_dir"] = str(tmp_path / output_name)
    path = tmp_path / f"{output_name}.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def _run_cli(config_path: Path, command: str = "run-all") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cart_autolab.cli", command, "--config", str(config_path)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        check=True,
        capture_output=True,
        text=True,
    )


def test_deterministic_run_all_reviewer_artifacts(tmp_path):
    config_path = _write_tmp_config(tmp_path, "configs/experiment_cytokine_gpc3_liver.yaml", "deterministic")
    _run_cli(config_path)
    run_dir = tmp_path / "deterministic"

    expected = [
        "search_queries.json",
        "included_papers.json",
        "extracted_evidence.json",
        "extracted_evidence_deterministic.json",
        "parameter_fingerprints.json",
        "parameter_transformation_rules.json",
        "simulation/plan.json",
        "simulation/parameters.json",
        "simulation/timeseries.csv",
        "analysis_metrics.csv",
        "ranked_interventions.csv",
        "critique_report.json",
        "final_report.md",
        "final_report.html",
        "memory.jsonl",
    ]
    for rel_path in expected:
        assert (run_dir / rel_path).exists(), rel_path
    assert not (run_dir / "llm_calls.jsonl").exists()
    params = json.loads((run_dir / "parameter_fingerprints.json").read_text(encoding="utf-8"))
    assert "control" not in {row["intervention_name"].lower() for row in params}
    ranking = pd.read_csv(run_dir / "ranked_interventions.csv")
    assert "control" not in set(ranking["intervention_name"].str.lower())
    assert {"K_score", "P_score", "E_score", "R_score", "ranked_intervention_score"}.issubset(ranking.columns)
    assert ranking["ranked_intervention_score"].between(0, 100).all()
    assert "Mock test records are not real scholarly citations" in (run_dir / "final_report.md").read_text(encoding="utf-8")


def test_llm_mock_run_all_reviewer_artifacts(tmp_path):
    config_path = _write_tmp_config(tmp_path, "configs/experiment_cytokine_gpc3_liver_llm_mock.yaml", "llm_mock")
    _run_cli(config_path)
    run_dir = tmp_path / "llm_mock"

    assert (run_dir / "llm_calls.jsonl").exists()
    assert (run_dir / "agent_outputs").exists()
    assert (run_dir / "extracted_evidence_llm.json").exists()
    assert (run_dir / "parameter_fingerprints.json").exists()
    assert (run_dir / "final_report.md").exists()
    parsed = list((run_dir / "agent_outputs").glob("*/*_parsed.json"))
    validations = list((run_dir / "agent_outputs").glob("*/*_validation.json"))
    assert parsed
    assert validations
    params = json.loads((run_dir / "parameter_fingerprints.json").read_text(encoding="utf-8"))
    il15 = [row for row in params if row["intervention_name"] == "IL-15"][0]
    assert il15["evidence_source"] == "llm"
    assert il15["llm_call_ids"]
    records = [json.loads(line) for line in (run_dir / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any("software fixture" in " ".join(record["warnings"]).lower() for record in records)
    assert "Fixture metadata only" in (run_dir / "final_report.md").read_text(encoding="utf-8")


def test_ablation_reviewer_artifacts_without_wet_lab_fabrication(tmp_path):
    config_path = _write_tmp_config(tmp_path, "configs/experiment_cytokine_gpc3_liver_ablation.yaml", "ablation")
    _run_cli(config_path, command="ablation")
    out_dir = tmp_path / "ablation"

    for rel_path in ["ablation_summary.csv", "ablation_summary.json", "evidence_coverage_matrix.csv", "ranking_comparison.csv"]:
        assert (out_dir / rel_path).exists(), rel_path
    summary = json.loads((out_dir / "ablation_summary.json").read_text(encoding="utf-8"))
    assert {row["mode"] for row in summary} == {"deterministic", "llm", "hybrid"}
    by_mode = {row["mode"]: row for row in summary}
    assert by_mode["deterministic"]["top_ranked_intervention"] != "not available"
    assert by_mode["llm"]["top_ranked_intervention"] == "not available"
    assert by_mode["hybrid"]["top_ranked_intervention"] == "not available"
    assert by_mode["llm"]["status_label"] == "skipped; no live LLM provider configured"
    assert by_mode["hybrid"]["status_label"] == "skipped; no live LLM provider configured"
    assert not (out_dir / "llm").exists()
    assert not (out_dir / "hybrid").exists()
    deterministic_config = yaml.safe_load((out_dir / "deterministic_config.yaml").read_text(encoding="utf-8"))
    assert "control" not in {item.lower() for item in deterministic_config["candidate_interventions"]}
    deterministic_params = json.loads((out_dir / "deterministic" / "parameter_fingerprints.json").read_text(encoding="utf-8"))
    assert "control" not in {row["intervention_name"].lower() for row in deterministic_params}
    assert all(row["experimental_concordance"] == "not evaluated; user-supplied validation table required" for row in summary)


def test_physicell_external_mode_missing_executable_is_clear_and_nonfabricating(tmp_path, monkeypatch):
    monkeypatch.delenv("PHYSICELL_EXECUTABLE", raising=False)
    config_path = _write_tmp_config(tmp_path, "configs/experiment_cytokine_gpc3_liver_physicell.yaml", "physicell_external")
    orch = AutolabOrchestrator(config_path)
    search = orch.search()
    evidence = orch.extract_evidence(search["included_papers"])
    built = orch.build_parameters(evidence)

    with pytest.raises(RuntimeError, match="PHYSICELL_EXECUTABLE"):
        orch.simulate(built["parameters"])

    sim_dir = tmp_path / "physicell_external" / "simulation"
    assert (sim_dir / "physicell_execution_log.json").exists()
    assert not (sim_dir / "timeseries.csv").exists()
    report = PhysiCellOutputConverter().convert(tmp_path / "physicell_external")
    assert report["converted"] is False
    assert (sim_dir / "conversion_report.json").exists()
    assert "not fabricated" in (sim_dir / "conversion_report.json").read_text(encoding="utf-8")


def test_output_converter_dry_run_reports_insufficient_external_outputs(tmp_path):
    sim_dir = tmp_path / "simulation"
    sim_dir.mkdir()
    pd.DataFrame([{"time": 0, "tumor_burden": 1000}]).to_csv(sim_dir / "physicell_summary.csv", index=False)

    report = PhysiCellOutputConverter().convert(tmp_path)

    assert report["converted"] is False
    assert not (sim_dir / "timeseries.csv").exists()
    assert "physicell_summary.csv" in report["missing_columns"]
