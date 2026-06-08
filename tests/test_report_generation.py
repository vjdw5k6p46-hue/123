from pathlib import Path

import yaml

from cart_autolab.orchestrator import AutolabOrchestrator


def test_report_generation_end_to_end(tmp_path):
    root = Path.cwd()
    config = yaml.safe_load((root / "configs" / "experiment_cytokine_gpc3_liver_safe_demo.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / "run")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    result = AutolabOrchestrator(config_path).run_all()
    assert Path(result["report"]["markdown"]).exists()
    text = Path(result["report"]["markdown"]).read_text(encoding="utf-8")
    assert "does not replace wet-lab validation" in text
    assert "PhysiCell" in text
    assert "Mock test records are not real scholarly citations" in text
    assert "doi:10.0000" not in text
