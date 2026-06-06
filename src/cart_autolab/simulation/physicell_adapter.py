from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from .base import SimulatorAdapter
from .mock_simulator import MockSimulatorAdapter
from .physicell_output_converter import PhysiCellOutputConverter


class PhysiCellAdapter(SimulatorAdapter):
    """PhysiCell/BioFVM primary adapter.

    In external mode this writes a compact PhysiCell-style XML configuration and
    invokes an externally supplied executable. In mock mode it writes the same inputs
    and uses MockSimulatorAdapter so CI and examples remain runnable.
    """

    def __init__(self, executable: str | None = None, mode: str = "mock"):
        self.executable = executable or os.getenv("PHYSICELL_EXECUTABLE")
        self.mode = mode
        self.mock = MockSimulatorAdapter()

    def prepare_inputs(self, plan: list[dict], parameters: list[dict], run_dir: Path) -> None:
        sim_dir = run_dir / "simulation"
        sim_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        (sim_dir / "parameters.json").write_text(json.dumps(parameters, indent=2), encoding="utf-8")
        self._write_cell_rules(parameters, sim_dir / "cell_rules.json")

    def write_config(self, run_dir: Path) -> Path:
        sim_dir = run_dir / "simulation"
        root = ET.Element("PhysiCell_settings")
        ET.SubElement(root, "max_time").text = "240"
        ET.SubElement(root, "dt_intracellular").text = "12"
        micro = ET.SubElement(root, "microenvironment_setup")
        for name in ["cytokine", "IFN_gamma", "oxygen", "hypoxia", "PD_L1_signal", "suppressive_TME"]:
            var = ET.SubElement(micro, "variable", {"name": name, "units": "dimensionless"})
            ET.SubElement(var, "physical_parameter_set").text = "BioFVM diffusion-decay field placeholder"
        cells = ET.SubElement(root, "cell_definitions")
        ET.SubElement(cells, "cell_definition", {"name": "tumor_cell"}).text = "antigen_density custom data controls CAR-T activation"
        ET.SubElement(cells, "cell_definition", {"name": "CAR_T_cell"}).text = "activation, proliferation, killing, exhaustion, and death rules loaded from cell_rules.json"
        path = sim_dir / "physicell_config.xml"
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return path

    def run(self, run_dir: Path) -> None:
        if self.mode == "external":
            log = self._execution_log(run_dir, "started")
            if not self.executable:
                log["status"] = "error"
                log["error"] = "PhysiCell external mode requires PHYSICELL_EXECUTABLE or simulator config executable path."
                self._write_execution_log(run_dir, log)
                raise RuntimeError(log["error"])
            executable = Path(self.executable)
            if not executable.exists():
                log["status"] = "error"
                log["error"] = f"PHYSICELL_EXECUTABLE does not exist: {executable}"
                self._write_execution_log(run_dir, log)
                raise RuntimeError(log["error"])
            command = [str(executable), str(run_dir / "simulation" / "physicell_config.xml")]
            log["command"] = command
            self._write_execution_log(run_dir, log)
            try:
                completed = subprocess.run(command, cwd=run_dir / "simulation", check=True, capture_output=True, text=True)
                log["status"] = "completed"
                log["returncode"] = completed.returncode
                log["stdout"] = completed.stdout
                log["stderr"] = completed.stderr
                PhysiCellOutputConverter().convert(run_dir)
            except subprocess.CalledProcessError as exc:
                log["status"] = "error"
                log["returncode"] = exc.returncode
                log["stdout"] = exc.stdout
                log["stderr"] = exc.stderr
                log["error"] = "External PhysiCell execution failed."
                raise
            finally:
                self._write_execution_log(run_dir, log)
        else:
            self.mock.run(run_dir)

    def parse_outputs(self, run_dir: Path) -> list[dict]:
        timeseries = run_dir / "simulation" / "timeseries.csv"
        if timeseries.exists():
            return pd.read_csv(timeseries).to_dict(orient="records")
        PhysiCellOutputConverter().convert(run_dir)
        if timeseries.exists():
            return pd.read_csv(timeseries).to_dict(orient="records")
        outputs = sorted(p.name for p in (run_dir / "simulation").glob("*") if p.is_file())
        return [{"artifact": name, "note": "External PhysiCell output was not converted to autolab timeseries format."} for name in outputs]

    def summarize_results(self, run_dir: Path) -> dict:
        timeseries = run_dir / "simulation" / "timeseries.csv"
        if timeseries.exists():
            summary = self.mock.summarize_results(run_dir)
        else:
            summary = {
                "rows": 0,
                "conditions": 0,
                "interventions": [],
                "output_files": sorted(p.name for p in (run_dir / "simulation").glob("*") if p.is_file()),
                "note": "External PhysiCell completed, but no autolab timeseries.csv was found. Add a PhysiCell output converter before analysis.",
            }
            (run_dir / "simulation" / "simulation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["engine"] = "PhysiCell external" if self.mode == "external" else "PhysiCell adapter mock execution"
        return summary

    def _write_cell_rules(self, parameters: list[dict], path: Path) -> None:
        rules = {
            "mapping": {
                "tumor_cell.custom_data.antigen_density": "simulation_plan.antigen_density",
                "CAR_T.proliferation_rate": "proliferation_enhancement_aP",
                "CAR_T.apoptosis_resistance": "survival_enhancement_aS",
                "CAR_T.killing_rate": "cytotoxicity_enhancement_aC",
                "CAR_T.exhaustion_update": "exhaustion_modulation_aE",
                "CAR_T.death_penalty": "activation_induced_death_penalty_bD",
                "BioFVM.IFN_gamma.secretion": "ifng_effect",
                "BioFVM.PD_L1_signal.source": "pdl1_effect",
                "BioFVM.hypoxia.modulation": "hypoxia_effect",
                "BioFVM.suppressive_TME.modulation": "tme_remodeling_effect",
            },
            "intervention_rules": parameters,
        }
        path.write_text(json.dumps(rules, indent=2), encoding="utf-8")

    def _execution_log(self, run_dir: Path, status: str) -> dict:
        return {
            "engine": "PhysiCell",
            "mode": self.mode,
            "status": status,
            "executable": self.executable,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_dir": str(run_dir),
        }

    def _write_execution_log(self, run_dir: Path, log: dict) -> None:
        sim_dir = run_dir / "simulation"
        sim_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "physicell_execution_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
