from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path


class PhysiCellParameterExporter:
    """Convert normalized intervention fingerprints into this PhysiCell model's XML knobs.

    This exporter targets a cancer_immune PhysiCell project, where CAR-T
    cytokine behavior is controlled through <user_parameters>. It does not edit
    the source PhysiCell project; it writes ready-to-run XML copies into the
    autolab run directory.
    """

    def export(
        self,
        fingerprints: list[dict],
        config: dict,
        run_dir: Path,
        base_config: str | Path | None = None,
    ) -> dict:
        base_xml = Path(base_config or self._default_base_config())
        if not base_xml.exists():
            raise FileNotFoundError(f"PhysiCell base config not found: {base_xml}")

        out_dir = run_dir / "physicell_ready_configs"
        out_dir.mkdir(parents=True, exist_ok=True)
        antigen_density = self._first_sweep_value(config, "antigen_density", default=1.0)

        exported = []
        for fp in fingerprints:
            tree = ET.parse(base_xml)
            root = tree.getroot()
            base_values = self._read_user_parameter_values(root)
            ready = self._map_fingerprint(fp, base_values, antigen_density)
            self._apply_user_parameters(root, ready["user_parameters"])
            name = self._safe_name(fp["intervention_name"])
            xml_path = out_dir / f"PhysiCell_settings_{name}.xml"
            tree.write(xml_path, encoding="utf-8", xml_declaration=True)
            ready["config_path"] = str(xml_path)
            exported.append(ready)

        payload = {
            "base_config": str(base_xml),
            "output_dir": str(out_dir),
            "note": "These are PhysiCell-ready XML user_parameters generated from normalized literature/LLM fingerprints. They are model inputs, not wet-lab estimates.",
            "interventions": exported,
        }
        (run_dir / "physicell_ready_parameters.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _default_base_config(self) -> Path:
        return Path("C:/code/PhysiCell/sample_projects/cancer_immune/config/PhysiCell_settings.xml")

    def _map_fingerprint(self, fp: dict, base: dict[str, str], antigen_density: float) -> dict:
        name = fp["intervention_name"]
        cytokine_name = self._physicell_cytokine_name(name)
        aP = float(fp.get("proliferation_enhancement_aP", 1.0))
        aS = float(fp.get("survival_enhancement_aS", 1.0))
        aC = float(fp.get("cytotoxicity_enhancement_aC", 1.0))
        aE = float(fp.get("exhaustion_modulation_aE", 0.0))
        bD = float(fp.get("activation_induced_death_penalty_bD", 0.0))
        ifng = float(fp.get("ifng_effect", 0.0))
        pdl1 = float(fp.get("pdl1_effect", 0.0))
        hypoxia = float(fp.get("hypoxia_effect", 0.0))
        tme = float(fp.get("tme_remodeling_effect", 0.0))

        exh_scale = self._clamp(1.0 + aE, 0.1, 2.0)
        hypoxia_scale = self._clamp(1.0 + hypoxia, 0.1, 2.0)
        tme_exhaust_scale = self._clamp(1.0 - 0.5 * tme, 0.1, 2.0)
        is_control = name.lower() == "control"

        user_parameters = {
            "aux_cytokine_name": "none" if is_control else cytokine_name,
            "aux_mode": "bath" if is_control else "armored",
            "aux_bath_dose": 0.0,
            "qmax_aux_engineered": 0.0 if is_control else self._base_float(base, "qmax_aux_engineered") * max(0.25, (aP + aS + aC) / 3.0),
            "tumor_antigen_density": antigen_density,
            "K_A": float(fp.get("half_effective_concentration_K", self._base_float(base, "K_A"))),
            "r0_cart": self._base_float(base, "r0_cart") * aP,
            "carT_prolif_rate": self._base_float(base, "carT_prolif_rate") * aP,
            "lambda0_cart": self._base_float(base, "lambda0_cart") / max(aS, 0.1),
            "k0_attack": self._base_float(base, "k0_attack") * aC,
            "dmg0": self._base_float(base, "dmg0") * aC,
            "p_kill_CAR_T": min(1.0, self._base_float(base, "p_kill_CAR_T") * aC),
            "k_exh": self._base_float(base, "k_exh") * exh_scale,
            "carT_exhaustion_per_kill": self._base_float(base, "carT_exhaustion_per_kill") * exh_scale,
            "carT_exhaustion_rate_when_attached": self._base_float(base, "carT_exhaustion_rate_when_attached") * exh_scale,
            "lambda_AICD": self._base_float(base, "lambda_AICD") * (1.0 + bD),
            "qIFNg_max": self._base_float(base, "qIFNg_max") * self._clamp(1.0 + ifng, 0.1, 3.0),
            "alpha_IFNg_aux": self._base_float(base, "alpha_IFNg_aux") * self._clamp(1.0 + max(ifng, 0.0), 0.1, 3.0),
            "k_PDL1_up": self._base_float(base, "k_PDL1_up") * self._clamp(1.0 + pdl1, 0.1, 3.0),
            "hypoxia_exhaust_mult": self._base_float(base, "hypoxia_exhaust_mult") * hypoxia_scale,
            "M2_present_exhaust_rate": self._base_float(base, "M2_present_exhaust_rate") * tme_exhaust_scale,
            "p_M0_to_M1": self._base_float(base, "p_M0_to_M1") * self._clamp(1.0 + tme, 0.1, 3.0),
            "p_M0_to_M2": self._base_float(base, "p_M0_to_M2") * self._clamp(1.0 - 0.5 * tme, 0.1, 3.0),
        }
        return {
            "intervention_name": name,
            "physicell_cytokine_name": cytokine_name,
            "source_fingerprint": deepcopy(fp),
            "mapping_rules": {
                "multipliers": "aP/aS/aC scale CAR-T proliferation, survival, and killing rates; aE scales exhaustion rates; bD scales AICD; IFNg/PDL1/hypoxia/TME terms scale matching PhysiCell user_parameters.",
                "cytokine_names": "Hyphenated cytokine names are converted to the cancer_immune code names, e.g. IL-15 -> IL15.",
                "limitation": "The cancer_immune C++ code also has internal get_aux_params() cytokine amplitudes that are not XML-editable without changing C++.",
            },
            "user_parameters": user_parameters,
        }

    def _read_user_parameter_values(self, root: ET.Element) -> dict[str, str]:
        user = root.find("user_parameters")
        if user is None:
            return {}
        return {child.tag: (child.text or "") for child in list(user)}

    def _apply_user_parameters(self, root: ET.Element, values: dict) -> None:
        user = root.find("user_parameters")
        if user is None:
            raise ValueError("Base PhysiCell XML has no <user_parameters> block.")
        existing = {child.tag: child for child in list(user)}
        for key, value in values.items():
            node = existing.get(key)
            if node is None:
                node = ET.SubElement(user, key)
                node.set("type", "string" if isinstance(value, str) else "double")
                node.set("units", "dimensionless")
            node.text = self._format_value(value)

    def _base_float(self, base: dict[str, str], key: str) -> float:
        return float(base.get(key, "0") or 0)

    def _physicell_cytokine_name(self, name: str) -> str:
        return name.replace("-", "")

    def _safe_name(self, name: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_").lower() or "control"

    def _first_sweep_value(self, config: dict, key: str, default: float) -> float:
        values = config.get("parameter_sweep", {}).get(key, [default])
        return float(values[0] if values else default)

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _format_value(self, value) -> str:
        if isinstance(value, str):
            return value
        return f"{float(value):.12g}"
