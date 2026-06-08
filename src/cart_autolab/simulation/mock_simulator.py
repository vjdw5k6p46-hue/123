from __future__ import annotations

import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .base import SimulatorAdapter


class MockSimulatorAdapter(SimulatorAdapter):
    """Deterministic test simulator matching the PhysiCell adapter output shape."""

    def prepare_inputs(self, plan: list[dict], parameters: list[dict], run_dir: Path) -> None:
        sim_dir = run_dir / "simulation"
        sim_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        (sim_dir / "parameters.json").write_text(json.dumps(parameters, indent=2), encoding="utf-8")

    def write_config(self, run_dir: Path) -> Path:
        config = {"engine": "mock", "max_time": 240, "time_step": 12}
        path = run_dir / "simulation" / "mock_simulator_config.json"
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return path

    def run(self, run_dir: Path) -> None:
        sim_dir = run_dir / "simulation"
        plan = json.loads((sim_dir / "plan.json").read_text(encoding="utf-8"))
        params = {p["intervention_name"]: p for p in json.loads((sim_dir / "parameters.json").read_text(encoding="utf-8"))}
        rows = []
        for condition in plan:
            p = params[condition["intervention_name"]]
            condition_offset = int(hashlib.sha256(condition["condition_id"].encode("utf-8")).hexdigest()[:8], 16) % 997
            rng = np.random.default_rng(condition["random_seed"] + condition_offset)
            tumor = 1000.0 * condition["initial_tumor_burden"]
            cart = 100.0 * condition["car_t_dose"]
            exhaustion = 0.12 + 0.3 * condition["tme_severity"]
            hypoxia = 0.25 + 0.3 * condition["tme_severity"]
            pdl1 = 0.2 + 0.25 * condition["tme_severity"]
            for time in range(0, 241, 12):
                activation = condition["antigen_density"] / (condition["antigen_density"] + p.get("half_effective_concentration_K", 0.5))
                expansion = 0.018 * p.get("proliferation_enhancement_aP", 1.0) * activation
                persistence = 0.01 * p.get("survival_enhancement_aS", 1.0)
                killing = 0.00032 * p.get("cytotoxicity_enhancement_aC", 1.0) * activation * max(0.1, 1 - exhaustion)
                death = 0.008 + p.get("activation_induced_death_penalty_bD", 0.0) * 0.012
                tumor_growth = 0.025 * (1 + condition["tme_severity"] * 0.2)
                ifng = max(0, cart * (0.02 + 0.04 * p.get("ifng_effect", 0)))
                tme = float(np.clip(condition["tme_severity"] - p.get("tme_remodeling_effect", 0) * 0.15 + hypoxia * 0.2 + pdl1 * 0.2, 0, 1))
                rows.append({**condition, "time": time, "tumor_burden": tumor, "car_t_cells": cart, "exhaustion_fraction": exhaustion, "cytotoxicity": killing * cart, "IFN_gamma": ifng, "hypoxia": hypoxia, "PD_L1_signal": pdl1, "tme_suppression": tme})
                if time == 240:
                    continue
                tumor = max(0, tumor + tumor * tumor_growth - killing * cart * tumor + rng.normal(0, 5))
                cart = max(0, cart + cart * (expansion + persistence - death - 0.004 * exhaustion) + rng.normal(0, 1))
                exhaustion = float(np.clip(exhaustion + 0.012 * condition["tme_severity"] + p.get("exhaustion_modulation_aE", 0) * 0.02, 0, 0.95))
                hypoxia = float(np.clip(hypoxia + tumor / 200000 - 0.01 * cart / 1000 + p.get("hypoxia_effect", 0) * 0.01, 0, 1))
                pdl1 = float(np.clip(pdl1 + p.get("pdl1_effect", 0) * 0.01 + ifng / 100000, 0, 1))
        pd.DataFrame(rows).to_csv(sim_dir / "timeseries.csv", index=False)

    def parse_outputs(self, run_dir: Path) -> list[dict]:
        return pd.read_csv(run_dir / "simulation" / "timeseries.csv").to_dict(orient="records")

    def summarize_results(self, run_dir: Path) -> dict:
        df = pd.read_csv(run_dir / "simulation" / "timeseries.csv")
        summary = {"rows": len(df), "conditions": int(df["condition_id"].nunique()), "interventions": sorted(df["intervention_name"].unique().tolist())}
        (run_dir / "simulation" / "simulation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary
