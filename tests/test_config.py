from pathlib import Path

import yaml


def test_example_config_loads():
    config = yaml.safe_load(Path("configs/experiment_cytokine_gpc3_liver_safe_demo.yaml").read_text(encoding="utf-8"))
    assert config["car_target_antigen"] == "GPC3"
    assert "IL-15" in config["candidate_interventions"]
    assert config["simulator_choice"] == "physicell"
