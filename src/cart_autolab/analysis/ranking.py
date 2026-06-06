from __future__ import annotations

from pathlib import Path

import pandas as pd


def rank_interventions(run_dir: Path) -> pd.DataFrame:
    metrics = pd.read_csv(run_dir / "analysis_metrics.csv")
    grouped = metrics.groupby("intervention_name").agg(
        final_tumor_burden=("final_tumor_burden", "mean"),
        tumor_killing_rate=("tumor_killing_rate", "mean"),
        car_t_expansion_auc=("car_t_expansion_auc", "mean"),
        car_t_persistence=("car_t_persistence", "mean"),
        exhaustion_fraction=("exhaustion_fraction", "mean"),
        cytotoxicity_score=("cytotoxicity_score", "mean"),
        tme_suppression_score=("tme_suppression_score", "mean"),
        robustness=("final_tumor_burden", lambda x: 1 / (1 + x.std(ddof=0))),
    ).reset_index()
    for col, invert in [("final_tumor_burden", True), ("exhaustion_fraction", True), ("tme_suppression_score", True), ("tumor_killing_rate", False), ("car_t_persistence", False), ("cytotoxicity_score", False), ("robustness", False)]:
        vals = grouped[col]
        denom = max(vals.max() - vals.min(), 1e-9)
        score = (vals - vals.min()) / denom
        grouped[f"{col}_score"] = 1 - score if invert else score
    grouped["ranked_intervention_score"] = (
        0.25 * grouped["final_tumor_burden_score"]
        + 0.15 * grouped["tumor_killing_rate_score"]
        + 0.15 * grouped["car_t_persistence_score"]
        + 0.15 * grouped["exhaustion_fraction_score"]
        + 0.10 * grouped["cytotoxicity_score_score"]
        + 0.10 * grouped["tme_suppression_score_score"]
        + 0.10 * grouped["robustness_score"]
    )
    ranked = grouped.sort_values("ranked_intervention_score", ascending=False)
    ranked.to_csv(run_dir / "ranked_interventions.csv", index=False)
    return ranked
