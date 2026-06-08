import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_physicell_autoresearch_replicates", ROOT / "scripts" / "run_physicell_autoresearch_replicates.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
strict_persist_avg_life_min = MODULE.strict_persist_avg_life_min
cytokine_priority_score_from_summary = MODULE.cytokine_priority_score_from_summary


def test_strict_persist_avg_life_min_uses_time_series_auc(tmp_path: Path):
    path = tmp_path / "time_series.csv"
    path.write_text(
        "\n".join(
            [
                "time_min,CAR_T_count",
                "0,100",
                "60,80",
                "120,40",
            ]
        ),
        encoding="utf-8",
    )

    # AUC = 60*(100+80)/2 + 60*(80+40)/2 = 9000; divided by initial 100.
    assert strict_persist_avg_life_min(path) == 90.0


def test_strict_persist_avg_life_min_does_not_fabricate_missing_data(tmp_path: Path):
    assert strict_persist_avg_life_min(tmp_path / "missing_time_series.csv") is None

    path = tmp_path / "time_series.csv"
    path.write_text("time_min,CAR_T_count\n0,0\n60,10\n", encoding="utf-8")
    assert strict_persist_avg_life_min(path) is None


def test_external_runner_priority_score_uses_requested_formula():
    score = cytokine_priority_score_from_summary(
        {
            "tumor_remaining_fraction_mean": 0.30,
            "persist_avg_life_min_mean": 1200,
            "mean_cart_exhaustion_mean": 0.15,
            "mean_tumor_PDL1_mean": 0.03,
        }
    )

    assert score["K_score"] == 1.0
    assert score["P_score"] == 1.0
    assert score["E_score"] == 1.0
    assert score["R_score"] == 1.0
    assert score["ranked_intervention_score"] == 100.0


def test_external_runner_priority_score_clamps_bounds():
    score = cytokine_priority_score_from_summary(
        {
            "tumor_remaining_fraction_mean": 1.20,
            "persist_avg_life_min_mean": 300,
            "mean_cart_exhaustion_mean": 0.50,
            "mean_tumor_PDL1_mean": 0.25,
        }
    )

    assert score["K_score"] == 0.0
    assert score["P_score"] == 0.0
    assert score["E_score"] == 0.0
    assert score["R_score"] == 0.0
    assert score["ranked_intervention_score"] == 0.0
