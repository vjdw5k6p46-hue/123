import json

import pytest

from cart_autolab.simulation.physicell_adapter import PhysiCellAdapter


def test_external_mode_errors_clearly_without_executable(tmp_path):
    adapter = PhysiCellAdapter(executable=None, mode="external")
    (tmp_path / "simulation").mkdir()

    with pytest.raises(RuntimeError, match="PHYSICELL_EXECUTABLE"):
        adapter.run(tmp_path)

    log = json.loads((tmp_path / "simulation" / "physicell_execution_log.json").read_text(encoding="utf-8"))
    assert log["status"] == "error"
    assert "PHYSICELL_EXECUTABLE" in log["error"]


def test_external_mode_errors_clearly_for_missing_path(tmp_path):
    adapter = PhysiCellAdapter(executable=str(tmp_path / "missing_physicell"), mode="external")
    (tmp_path / "simulation").mkdir()

    with pytest.raises(RuntimeError, match="does not exist"):
        adapter.run(tmp_path)

    log = json.loads((tmp_path / "simulation" / "physicell_execution_log.json").read_text(encoding="utf-8"))
    assert log["status"] == "error"
    assert "does not exist" in log["error"]
