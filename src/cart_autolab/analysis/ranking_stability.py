from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def load_ranking(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "ranked_interventions.csv"
    if not path.exists():
        return pd.DataFrame(columns=["intervention_name", "ranked_intervention_score"])
    return pd.read_csv(path)


def compare_rankings(run_dirs: dict[str, Path]) -> pd.DataFrame:
    rankings = {mode: load_ranking(path) for mode, path in run_dirs.items()}
    rows: list[dict[str, Any]] = []
    deterministic = rankings.get("deterministic", pd.DataFrame())
    det_scores = _score_series(deterministic)
    for mode, ranking in rankings.items():
        scores = _score_series(ranking)
        rows.append(
            {
                "mode": mode,
                "top_ranked_intervention": ranking.iloc[0]["intervention_name"] if not ranking.empty else "not available",
                "IL-15_rank": _rank_of(ranking, "IL-15"),
                "rank_correlation_vs_deterministic": _rank_corr(det_scores, scores) if mode != "deterministic" else 1.0,
            }
        )
    return pd.DataFrame(rows)


def _score_series(df: pd.DataFrame) -> pd.Series:
    if df.empty or "ranked_intervention_score" not in df:
        return pd.Series(dtype=float)
    return df.set_index("intervention_name")["ranked_intervention_score"]


def _rank_of(df: pd.DataFrame, intervention: str) -> int | None:
    if df.empty:
        return None
    matches = df.index[df["intervention_name"] == intervention].tolist()
    return int(matches[0] + 1) if matches else None


def _rank_corr(a: pd.Series, b: pd.Series) -> float | None:
    shared = sorted(set(a.index) & set(b.index))
    if len(shared) < 2:
        return None
    ranked_a = a.loc[shared].rank(method="average")
    ranked_b = b.loc[shared].rank(method="average")
    corr = ranked_a.corr(ranked_b)
    if pd.isna(corr):
        return None
    return float(corr)
