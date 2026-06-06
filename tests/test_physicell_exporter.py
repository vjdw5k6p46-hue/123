import json
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from cart_autolab.parameters.physicell_exporter import PhysiCellParameterExporter


def test_physicell_exporter_writes_ready_xml(tmp_path):
    base = Path("C:/code/PhysiCell/sample_projects/cancer_immune/config/PhysiCell_settings.xml")
    if not base.exists():
        return
    config = yaml.safe_load(Path("configs/experiment_cytokine_gpc3_liver.yaml").read_text(encoding="utf-8"))
    fingerprints = [
        {
            "intervention_name": "IL-15",
            "half_effective_concentration_K": 0.4,
            "proliferation_enhancement_aP": 1.48,
            "survival_enhancement_aS": 1.54,
            "cytotoxicity_enhancement_aC": 1.42,
            "exhaustion_modulation_aE": -0.25,
            "activation_induced_death_penalty_bD": 0.0,
            "ifng_effect": 0.15,
            "pdl1_effect": 0.0,
            "hypoxia_effect": -0.05,
            "tme_remodeling_effect": 0.1,
        }
    ]
    exported = PhysiCellParameterExporter().export(fingerprints, config, tmp_path, base)
    xml_path = Path(exported["interventions"][0]["config_path"])
    assert xml_path.exists()
    root = ET.parse(xml_path).getroot()
    user = {child.tag: child.text for child in root.find("user_parameters")}
    assert user["aux_cytokine_name"] == "IL15"
    assert user["aux_mode"] == "armored"
    assert float(user["tumor_antigen_density"]) == 0.2
    assert float(user["k0_attack"]) > 0.2
    assert float(user["k_exh"]) < 0.006
    payload = json.loads((tmp_path / "physicell_ready_parameters.json").read_text(encoding="utf-8"))
    assert payload["interventions"][0]["physicell_cytokine_name"] == "IL15"
