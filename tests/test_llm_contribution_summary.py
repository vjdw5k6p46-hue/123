from pathlib import Path

import pandas as pd
import yaml

from cart_autolab.analysis.llm_contribution import write_llm_contribution_summary
from cart_autolab.analysis.ablation import run_ablation
from cart_autolab.orchestrator import AutolabOrchestrator


def _run_config(tmp_path, source_config, output_name):
    config = yaml.safe_load(Path(source_config).read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / output_name)
    path = tmp_path / f"{output_name}.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    AutolabOrchestrator(path).run_all()


def test_llm_contribution_summary_labels_fixture_modes(tmp_path):
    _run_config(tmp_path, "configs/experiment_cytokine_gpc3_liver.yaml", "deterministic")
    _run_config(tmp_path, "configs/experiment_cytokine_gpc3_liver_llm_mock.yaml", "llm_mock")

    ablation_config = yaml.safe_load(Path("configs/experiment_cytokine_gpc3_liver_ablation.yaml").read_text(encoding="utf-8"))
    ablation_config["ablation"]["output_dir"] = str(tmp_path / "ablation")
    ablation_path = tmp_path / "ablation.yaml"
    ablation_path.write_text(yaml.safe_dump(ablation_config), encoding="utf-8")
    run_ablation(ablation_path)

    out = write_llm_contribution_summary(tmp_path)
    df = pd.read_csv(out)

    assert set(df["workflow_mode"]) == {"deterministic", "llm_mock", "hybrid"}
    assert "software-fixture demonstration" in df.loc[df["workflow_mode"] == "llm_mock", "notes"].iloc[0]
    assert "user-supplied validation table required" in df["notes"].iloc[0]
    assert "IL15_rank" in df.columns
    assert df.loc[df["workflow_mode"] == "deterministic", "evidence_source"].iloc[0] == "deterministic"
    assert df.loc[df["workflow_mode"] == "hybrid", "evidence_source"].iloc[0] == "deterministic+llm"
