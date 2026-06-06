import json

import pandas as pd

from cart_autolab.simulation.physicell_output_converter import TIMESERIES_COLUMNS, PhysiCellOutputConverter


def test_converter_does_not_fabricate_missing_timeseries(tmp_path):
    sim_dir = tmp_path / "simulation"
    sim_dir.mkdir()
    (sim_dir / "output00000000.xml").write_text("<PhysiCell></PhysiCell>", encoding="utf-8")

    report = PhysiCellOutputConverter().convert(tmp_path)

    assert report["converted"] is False
    assert not (sim_dir / "timeseries.csv").exists()
    saved = json.loads((sim_dir / "conversion_report.json").read_text(encoding="utf-8"))
    assert "not fabricated" in saved["note"]
    assert "output00000000.xml" in saved["found_files"]


def test_converter_writes_common_schema_when_summary_is_sufficient(tmp_path):
    sim_dir = tmp_path / "simulation"
    sim_dir.mkdir()
    row = {column: 0 for column in TIMESERIES_COLUMNS}
    row.update({"condition_id": "cond-1", "intervention_name": "IL-15", "replicate": 1, "time": 0})
    pd.DataFrame([row]).to_csv(sim_dir / "physicell_summary.csv", index=False)

    report = PhysiCellOutputConverter().convert(tmp_path)

    assert report["converted"] is True
    out = pd.read_csv(sim_dir / "timeseries.csv")
    assert list(out.columns) == TIMESERIES_COLUMNS
    assert out.iloc[0]["intervention_name"] == "IL-15"
