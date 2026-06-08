from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def generate_figures(run_dir: Path) -> list[str]:
    fig_dir = run_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(run_dir / "simulation" / "timeseries.csv")
    ranked = pd.read_csv(run_dir / "ranked_interventions.csv")
    paths = []
    paths.append(_line(df, "tumor_burden", "Tumor burden", fig_dir / "tumor_burden_curves.png"))
    paths.append(_line(df, "car_t_cells", "CAR-T population", fig_dir / "cart_population_curves.png"))
    paths.append(_line(df, "exhaustion_fraction", "Exhaustion fraction", fig_dir / "exhaustion_dynamics.png"))
    paths.append(_line(df, "IFN_gamma", "IFN-gamma", fig_dir / "ifng_dynamics.png"))
    paths.append(_line(df, "hypoxia", "Hypoxia", fig_dir / "hypoxia_dynamics.png"))
    paths.append(_bar(ranked, "ranked_intervention_score", "Cytokine priority score", fig_dir / "ranking_bar_plot.png"))
    paths.append(_heatmap(ranked, fig_dir / "intervention_performance_heatmap.png"))
    paths.append(_bar(ranked, "tme_suppression_score", "TME suppression score", fig_dir / "parameter_sensitivity_proxy.png"))
    return [str(p) for p in paths]


def _line(df: pd.DataFrame, value: str, title: str, path: Path) -> Path:
    plt.figure(figsize=(7, 4))
    for name, group in df.groupby("intervention_name"):
        mean = group.groupby("time")[value].mean()
        plt.plot(mean.index, mean.values, label=name)
    plt.xlabel("time")
    plt.ylabel(value)
    plt.title(title)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path


def _bar(df: pd.DataFrame, value: str, title: str, path: Path) -> Path:
    plt.figure(figsize=(7, 4))
    plt.bar(df["intervention_name"], df[value])
    plt.ylabel(value)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path


def _heatmap(df: pd.DataFrame, path: Path) -> Path:
    cols = ["K_score", "P_score", "E_score", "R_score"]
    matrix = df.set_index("intervention_name")[cols]
    plt.figure(figsize=(8, 4))
    plt.imshow(matrix.values, aspect="auto", cmap="viridis")
    plt.xticks(range(len(cols)), cols, rotation=35, ha="right", fontsize=7)
    plt.yticks(range(len(matrix.index)), matrix.index)
    plt.colorbar(label="score component")
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    return path
