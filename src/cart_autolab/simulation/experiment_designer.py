from __future__ import annotations

import json
from pathlib import Path


class SimulationExperimentDesigner:
    def design(self, config: dict, parameters: list[dict], output_dir: Path) -> list[dict]:
        sweep = config.get("parameter_sweep", {})
        seeds = [int(config.get("random_seed", 1)) + i for i in range(int(config.get("replicates", 1)))]
        plan = []
        for intervention in config.get("candidate_interventions", []):
            for antigen_density in sweep.get("antigen_density", [1.0]):
                for dose in sweep.get("car_t_dose", [1.0]):
                    for tumor_burden in sweep.get("tumor_burden", [1.0]):
                        for tme in sweep.get("tme_severity", [0.5]):
                            for replicate, seed in enumerate(seeds):
                                plan.append(
                                    {
                                        "condition_id": f"{intervention}_rep{replicate}_ag{antigen_density}_dose{dose}_tme{tme}",
                                        "intervention_name": intervention,
                                        "replicate": replicate,
                                        "random_seed": seed,
                                        "antigen_density": antigen_density,
                                        "car_t_dose": dose,
                                        "initial_tumor_burden": tumor_burden,
                                        "tme_severity": tme,
                                    }
                                )
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "simulation_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return plan
