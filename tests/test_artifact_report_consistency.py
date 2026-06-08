from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_final_report_ranking_matches_manifest_listed_artifacts():
    report = (ROOT / "artifacts" / "07_final_report" / "final_report.md").read_text(encoding="utf-8")
    round1 = pd.read_csv(
        ROOT
        / "artifacts"
        / "06_physicell_low_antigen_results"
        / "round1_pre_refine_replicates3"
        / "replicate_ranking.csv"
    )
    round2 = pd.read_csv(
        ROOT
        / "artifacts"
        / "06_physicell_low_antigen_results"
        / "round2_post_refine_replicates3"
        / "replicate_ranking.csv"
    )

    expected_round1 = [condition.upper().replace("IL_", "IL-") for condition in round1.sort_values("rank")["condition"].tolist()]
    expected_round2 = [condition.upper().replace("IL_", "IL-") for condition in round2.sort_values("rank")["condition"].tolist()]

    assert expected_round1 == ["IL-15", "IL-18", "IL-12", "IL-7", "IL-2"]
    assert expected_round2 == ["IL-15", "IL-18", "IL-12", "IL-7", "IL-2"]
    assert "IL-15, IL-18, IL-12, IL-7, and IL-2" in report
    assert "score approximately 85" not in report
    assert "score approximately 76" not in report
    assert "persist_avg_life_min" in report
    assert "final claim is intentionally tied to the manifest-listed tumor-count ranking CSVs" in report
