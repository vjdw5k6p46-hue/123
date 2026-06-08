from __future__ import annotations

from pathlib import Path

import pandas as pd


def clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def cytokine_priority_score(
    *,
    tumor_remaining_fraction: float,
    persist_avg_life_min: float,
    mean_cart_exhaustion: float,
    mean_tumor_PDL1: float,
) -> dict[str, float]:
    k_score = 1.0 - clamp01((tumor_remaining_fraction - 0.30) / (1.00 - 0.30))
    p_score = clamp01((persist_avg_life_min - 600.0) / (1200.0 - 600.0))
    e_score = 1.0 - clamp01((mean_cart_exhaustion - 0.15) / (0.35 - 0.15))
    r_score = 1.0 - clamp01((mean_tumor_PDL1 - 0.03) / (0.18 - 0.03))
    score = 100.0 * clamp01(0.40 * k_score + 0.30 * p_score + 0.20 * e_score + 0.10 * r_score)
    return {
        "K_score": k_score,
        "P_score": p_score,
        "E_score": e_score,
        "R_score": r_score,
        "ranked_intervention_score": score,
    }


def rank_interventions(run_dir: Path) -> pd.DataFrame:
    metrics = pd.read_csv(run_dir / "analysis_metrics.csv")
    grouped = metrics.groupby("intervention_name").agg(
        final_tumor_burden=("final_tumor_burden", "mean"),
        tumor_killing_rate=("tumor_killing_rate", "mean"),
        tumor_remaining_fraction=("tumor_remaining_fraction", "mean"),
        persist_avg_life_min=("persist_avg_life_min", "mean"),
        car_t_expansion_auc=("car_t_expansion_auc", "mean"),
        car_t_persistence=("car_t_persistence", "mean"),
        exhaustion_fraction=("exhaustion_fraction", "mean"),
        mean_cart_exhaustion=("mean_cart_exhaustion", "mean"),
        mean_tumor_PDL1=("mean_tumor_PDL1", "mean"),
        cytotoxicity_score=("cytotoxicity_score", "mean"),
        tme_suppression_score=("tme_suppression_score", "mean"),
        robustness=("final_tumor_burden", lambda x: 1 / (1 + x.std(ddof=0))),
    ).reset_index()
    components = [
        cytokine_priority_score(
            tumor_remaining_fraction=row.tumor_remaining_fraction,
            persist_avg_life_min=row.persist_avg_life_min,
            mean_cart_exhaustion=row.mean_cart_exhaustion,
            mean_tumor_PDL1=row.mean_tumor_PDL1,
        )
        for row in grouped.itertuples(index=False)
    ]
    grouped = pd.concat([grouped, pd.DataFrame(components)], axis=1)
    ranked = grouped.sort_values("ranked_intervention_score", ascending=False)
    ranked.to_csv(run_dir / "ranked_interventions.csv", index=False)
    return ranked
