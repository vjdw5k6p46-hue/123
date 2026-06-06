import pandas as pd

from cart_autolab.simulation.experiment_designer import SimulationExperimentDesigner
from cart_autolab.simulation.physicell_adapter import PhysiCellAdapter


def test_physicell_adapter_mock_outputs_timeseries(tmp_path):
    config = {
        "candidate_interventions": ["control"],
        "replicates": 1,
        "random_seed": 1,
        "parameter_sweep": {"antigen_density": [0.2], "car_t_dose": [1.0], "tumor_burden": [1.0], "tme_severity": [0.5]},
    }
    params = [{"intervention_name": "control", "half_effective_concentration_K": 1.0, "proliferation_enhancement_aP": 1.0, "survival_enhancement_aS": 1.0, "cytotoxicity_enhancement_aC": 1.0, "exhaustion_modulation_aE": 0.0, "activation_induced_death_penalty_bD": 0.0, "ifng_effect": 0.0, "pdl1_effect": 0.0, "hypoxia_effect": 0.0, "tme_remodeling_effect": 0.0}]
    plan = SimulationExperimentDesigner().design(config, params, tmp_path)
    adapter = PhysiCellAdapter(mode="mock")
    adapter.prepare_inputs(plan, params, tmp_path)
    adapter.write_config(tmp_path)
    adapter.run(tmp_path)
    df = pd.read_csv(tmp_path / "simulation" / "timeseries.csv")
    assert {"tumor_burden", "car_t_cells", "IFN_gamma"}.issubset(df.columns)
    assert len(df) > 5


def test_mock_simulator_is_reproducible(tmp_path):
    config = {
        "candidate_interventions": ["control"],
        "replicates": 1,
        "random_seed": 7,
        "parameter_sweep": {"antigen_density": [0.2], "car_t_dose": [1.0], "tumor_burden": [1.0], "tme_severity": [0.5]},
    }
    params = [{"intervention_name": "control", "half_effective_concentration_K": 1.0, "proliferation_enhancement_aP": 1.0, "survival_enhancement_aS": 1.0, "cytotoxicity_enhancement_aC": 1.0, "exhaustion_modulation_aE": 0.0, "activation_induced_death_penalty_bD": 0.0, "ifng_effect": 0.0, "pdl1_effect": 0.0, "hypoxia_effect": 0.0, "tme_remodeling_effect": 0.0}]
    csvs = []
    for name in ["a", "b"]:
        run_dir = tmp_path / name
        plan = SimulationExperimentDesigner().design(config, params, run_dir)
        adapter = PhysiCellAdapter(mode="mock")
        adapter.prepare_inputs(plan, params, run_dir)
        adapter.write_config(run_dir)
        adapter.run(run_dir)
        csvs.append((run_dir / "simulation" / "timeseries.csv").read_text(encoding="utf-8"))
    assert csvs[0] == csvs[1]
