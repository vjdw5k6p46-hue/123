from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .normalization import clamp, qualitative_to_multiplier, signed_clamp
from .schemas import CytokineFingerprint, GenericInterventionParameters


class FingerprintBuilder:
    def build(self, evidence: list[dict], config: dict, output_dir: Path) -> dict:
        evidence_source = config.get("workflow", {}).get("evidence_source", "deterministic")
        if "cytokine" in config.get("engineering_variable", ""):
            parameters = self._build_cytokine(evidence, config)
        else:
            parameters = self._build_generic(evidence, config)
        rules = {
            "description": "Qualitative evidence effects are averaged by intervention, converted to bounded simulation multipliers, and uncertainty is 1-confidence.",
            "deterministic_rules_applied": True,
            "llm_evidence_used": any(row.get("evidence_source") == "llm" for row in evidence),
            "schema_validation_required": evidence_source in {"llm", "hybrid"},
            "cytokine_fingerprint_is_not_omics": True,
            "manual_overrides_applied": bool(config.get("manual_parameter_overrides")),
            "low_confidence_assumptions": sorted({flag for row in evidence for flag in row.get("low_confidence_flags", [])}),
            "no_fabricated_citations": True,
        }
        self._apply_overrides(parameters, config.get("manual_parameter_overrides", {}))
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "parameter_fingerprints.json").write_text(json.dumps(parameters, indent=2), encoding="utf-8")
        (output_dir / "parameter_transformation_rules.json").write_text(json.dumps(rules, indent=2), encoding="utf-8")
        return {"parameters": parameters, "rules": rules}

    def _build_cytokine(self, evidence: list[dict], config: dict) -> list[dict]:
        evidence_source = config.get("workflow", {}).get("evidence_source", "deterministic")
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in evidence:
            grouped[row["intervention_name"]].append(row)
        outputs = []
        for intervention in config.get("candidate_interventions", []):
            if intervention.lower() == "control":
                outputs.append(self._control().model_dump())
                continue
            rows = grouped.get(intervention, [])
            avg = lambda key: sum(r.get(key, 0.0) for r in rows) / len(rows) if rows else 0.0
            conf = sum(r.get("confidence_score", 0.2) for r in rows) / len(rows) if rows else 0.2
            refs = sorted({r["supporting_citation"] for r in rows})
            provenance = self._provenance(evidence_source, rows)
            heuristic = self._cytokine_prior(intervention)
            fp = CytokineFingerprint(
                intervention_name=intervention,
                half_effective_concentration_K=heuristic["K"],
                proliferation_enhancement_aP=qualitative_to_multiplier(avg("proliferation_effect") + heuristic["proliferation"]),
                survival_enhancement_aS=qualitative_to_multiplier(avg("survival_or_persistence_effect") + heuristic["survival"]),
                cytotoxicity_enhancement_aC=qualitative_to_multiplier(avg("cytotoxicity_effect") + heuristic["cytotoxicity"]),
                exhaustion_modulation_aE=signed_clamp(avg("exhaustion_effect") + heuristic["exhaustion"]),
                activation_induced_death_penalty_bD=clamp(avg("activation_induced_cell_death_effect") + heuristic["aicd"]),
                ifng_effect=signed_clamp(avg("cytokine_production_effect") + heuristic["ifng"]),
                pdl1_effect=signed_clamp(0.15 if intervention in {"IL-12", "IL-18"} else 0.0),
                hypoxia_effect=signed_clamp(-0.05 if intervention in {"IL-12", "IL-15"} else 0.0),
                tme_remodeling_effect=signed_clamp(avg("tme_remodeling_effect") + heuristic["tme"]),
                confidence_score=clamp(conf),
                uncertainty=clamp(1.0 - conf),
                evidence_summary=self._summary(intervention, rows),
                supporting_references=refs,
                **provenance,
            )
            outputs.append(fp.model_dump())
        return outputs

    def _build_generic(self, evidence: list[dict], config: dict) -> list[dict]:
        rows = []
        for intervention in config.get("candidate_interventions", []):
            ev = [r for r in evidence if r["intervention_name"] == intervention]
            conf = sum(r.get("confidence_score", 0.2) for r in ev) / len(ev) if ev else 0.2
            provenance = self._provenance(config.get("workflow", {}).get("evidence_source", "deterministic"), ev)
            rows.append(GenericInterventionParameters(intervention_name=intervention, confidence_score=conf, uncertainty=1 - conf, evidence_summary=self._summary(intervention, ev), supporting_references=[r["supporting_citation"] for r in ev], **provenance).model_dump())
        return rows

    def _control(self) -> CytokineFingerprint:
        return CytokineFingerprint(
            intervention_name="control",
            half_effective_concentration_K=1.0,
            proliferation_enhancement_aP=1.0,
            survival_enhancement_aS=1.0,
            cytotoxicity_enhancement_aC=1.0,
            exhaustion_modulation_aE=0.0,
            activation_induced_death_penalty_bD=0.0,
            ifng_effect=0.0,
            pdl1_effect=0.0,
            hypoxia_effect=0.0,
            tme_remodeling_effect=0.0,
            confidence_score=0.5,
            uncertainty=0.5,
            evidence_summary="No cytokine payload control baseline.",
            supporting_references=[],
            parameter_derivation_notes="Control baseline uses deterministic neutral parameter values.",
        )

    def _cytokine_prior(self, intervention: str) -> dict:
        priors = {
            "IL-2": {"K": 0.45, "proliferation": 0.45, "survival": 0.05, "cytotoxicity": 0.1, "exhaustion": 0.15, "aicd": 0.25, "ifng": 0.1, "tme": 0.0},
            "IL-7": {"K": 0.55, "proliferation": 0.15, "survival": 0.35, "cytotoxicity": 0.05, "exhaustion": -0.15, "aicd": 0.0, "ifng": 0.0, "tme": 0.0},
            "IL-12": {"K": 0.35, "proliferation": 0.1, "survival": 0.05, "cytotoxicity": 0.3, "exhaustion": 0.05, "aicd": 0.05, "ifng": 0.45, "tme": 0.45},
            "IL-15": {"K": 0.40, "proliferation": 0.35, "survival": 0.45, "cytotoxicity": 0.25, "exhaustion": -0.25, "aicd": 0.0, "ifng": 0.15, "tme": 0.10},
            "IL-18": {"K": 0.50, "proliferation": 0.1, "survival": 0.05, "cytotoxicity": 0.2, "exhaustion": 0.05, "aicd": 0.05, "ifng": 0.4, "tme": 0.25},
        }
        return priors.get(intervention, {"K": 0.5, "proliferation": 0, "survival": 0, "cytotoxicity": 0, "exhaustion": 0, "aicd": 0, "ifng": 0, "tme": 0})

    def _summary(self, intervention: str, rows: list[dict]) -> str:
        if not rows:
            return f"No retrieved direct evidence for {intervention}; parameters are low-confidence defaults or researcher overrides."
        functions = sorted({f for r in rows for f in r.get("immune_cell_function_affected", [])})
        return f"{intervention}: retrieved evidence mentions {', '.join(functions) or 'general CAR-T biology'} across {len(rows)} record(s)."

    def _provenance(self, evidence_source: str, rows: list[dict]) -> dict:
        sources = sorted({row.get("evidence_source", evidence_source) for row in rows}) or [evidence_source]
        llm_call_ids = sorted({call_id for row in rows for call_id in row.get("llm_call_ids", [])})
        prompt_hashes = sorted({prompt_hash for row in rows for prompt_hash in row.get("prompt_hashes", [])})
        flags = sorted({flag for row in rows for flag in row.get("low_confidence_flags", [])})
        return {
            "evidence_source": "+".join(sources),
            "evidence_record_ids": [row.get("evidence_record_id", row.get("source_paper_id", "")) for row in rows if row.get("evidence_record_id") or row.get("source_paper_id")],
            "llm_call_ids": llm_call_ids,
            "prompt_hashes": prompt_hashes,
            "parameter_derivation_notes": "Generated from validated evidence records with deterministic bounded transformations and cytokine priors.",
            "low_confidence_flags": flags,
        }

    def _apply_overrides(self, parameters: list[dict], overrides: dict) -> None:
        for row in parameters:
            for key, value in overrides.get(row["intervention_name"], {}).items():
                row[key] = value
