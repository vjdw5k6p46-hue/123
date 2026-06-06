from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


TIMESERIES_COLUMNS = [
    "condition_id",
    "intervention_name",
    "replicate",
    "time",
    "tumor_burden",
    "car_t_cells",
    "exhaustion_fraction",
    "cytotoxicity",
    "IFN_gamma",
    "hypoxia",
    "PD_L1_signal",
    "tme_suppression",
]


class PhysiCellOutputConverter:
    def convert(self, run_dir: Path) -> dict[str, Any]:
        sim_dir = run_dir / "simulation"
        sim_dir.mkdir(parents=True, exist_ok=True)
        candidates = self._candidate_tables(sim_dir)
        report: dict[str, Any] = {
            "converted": False,
            "candidate_files": [path.name for path in candidates],
            "required_columns": TIMESERIES_COLUMNS,
            "missing_columns": {},
            "timeseries_path": None,
            "note": "",
        }
        for path in candidates:
            try:
                df = pd.read_csv(path)
            except Exception as exc:
                report["missing_columns"][path.name] = [f"could_not_read:{exc}"]
                continue
            missing = [column for column in TIMESERIES_COLUMNS if column not in df.columns]
            if missing:
                report["missing_columns"][path.name] = missing
                continue
            out = sim_dir / "timeseries.csv"
            df[TIMESERIES_COLUMNS].to_csv(out, index=False)
            report.update({"converted": True, "timeseries_path": str(out), "note": f"Converted {path.name} to common timeseries schema."})
            self._write_report(sim_dir, report)
            return report
        found = sorted(path.name for path in sim_dir.glob("*") if path.is_file())
        report["found_files"] = found
        report["note"] = "No sufficient PhysiCell summary table found; timeseries.csv was not fabricated."
        self._write_report(sim_dir, report)
        return report

    def _candidate_tables(self, sim_dir: Path) -> list[Path]:
        names = [
            "timeseries.csv",
            "physicell_timeseries.csv",
            "physicell_summary.csv",
            "summary.csv",
            "output_summary.csv",
        ]
        candidates = [sim_dir / name for name in names if (sim_dir / name).exists() and name != "timeseries.csv"]
        candidates.extend(path for path in sorted(sim_dir.glob("*.csv")) if path.name not in names)
        if (sim_dir / "timeseries.csv").exists():
            candidates.insert(0, sim_dir / "timeseries.csv")
        return candidates

    def _write_report(self, sim_dir: Path, report: dict[str, Any]) -> None:
        (sim_dir / "conversion_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
