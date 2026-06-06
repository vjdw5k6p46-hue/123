from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def compute_metrics(run_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "simulation" / "timeseries.csv")
    rows = []
    for (intervention, condition), group in df.groupby(["intervention_name", "condition_id"]):
        group = group.sort_values("time")
        baseline_tumor = group["tumor_burden"].iloc[0]
        final_tumor = group["tumor_burden"].iloc[-1]
        control_times = group.loc[group["tumor_burden"] < baseline_tumor * 0.5, "time"]
        rows.append(
            {
                "intervention_name": intervention,
                "condition_id": condition,
                "replicate": int(group["replicate"].iloc[0]),
                "final_tumor_burden": final_tumor,
                "tumor_killing_rate": max(0.0, (baseline_tumor - final_tumor) / max(group["time"].iloc[-1], 1)),
                "time_to_tumor_control": float(control_times.iloc[0]) if not control_times.empty else np.nan,
                "car_t_expansion_auc": float(np.trapezoid(group["car_t_cells"], group["time"])),
                "car_t_persistence": float(group["car_t_cells"].tail(3).mean()),
                "exhaustion_fraction": float(group["exhaustion_fraction"].tail(3).mean()),
                "cytotoxicity_score": float(group["cytotoxicity"].mean()),
                "tme_suppression_score": float(group["tme_suppression"].mean()),
            }
        )
    metrics = pd.DataFrame(rows)
    metrics.to_csv(run_dir / "analysis_metrics.csv", index=False)
    numeric_cols = metrics.select_dtypes(include="number").columns.drop("replicate")
    summary = metrics.groupby("intervention_name")[numeric_cols].agg(["mean", "std"]).reset_index()
    summary.columns = ["_".join(c).strip("_") for c in summary.columns.to_flat_index()]
    summary.to_csv(run_dir / "analysis_summary.csv", index=False)
    (run_dir / "analysis_summary.json").write_text(json.dumps(summary.to_dict(orient="records"), indent=2), encoding="utf-8")
    return metrics
