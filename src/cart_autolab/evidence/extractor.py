from __future__ import annotations

import json
from pathlib import Path

from .confidence import evidence_confidence
from .schemas import BiologicalEvidence


class EvidenceExtractor:
    """Grounded deterministic extractor with optional LLM extension point.

    This implementation never creates citations outside retrieved paper records.
    LLM-assisted deployments can replace `_extract_from_paper` while preserving
    the same schema and citation constraints.
    """

    cytokines = ["IL-2", "IL-7", "IL-12", "IL-15", "IL-18"]

    def extract(self, papers: list[dict], config: dict, output_dir: Path) -> list[dict]:
        records: list[BiologicalEvidence] = []
        for paper in papers:
            records.extend(self._extract_from_paper(paper, config))
        output = [r.model_dump() for r in records]
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "extracted_evidence.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        return output

    def _extract_from_paper(self, paper: dict, config: dict) -> list[BiologicalEvidence]:
        text = f"{paper.get('title', '')}. {paper.get('abstract', '')}"
        upper = text.upper()
        records = []
        interventions = config.get("candidate_interventions", [])
        for intervention in interventions:
            if intervention.lower() == "control":
                continue
            if intervention.upper() not in upper:
                continue
            lower = text.lower()
            citation = self._citation(paper)
            confidence = evidence_confidence(text, direct_target=config["car_target_antigen"].lower() in lower)
            records.append(
                BiologicalEvidence(
                    intervention_name=intervention,
                    car_target=config.get("car_target_antigen") if config.get("car_target_antigen", "").lower() in lower else None,
                    tumor_model=config.get("tumor_type") if config.get("tumor_type", "").split()[0].lower() in lower else None,
                    disease_context=config.get("disease_context") if any(t in lower for t in ["hepatocellular", "liver", "solid tumor"]) else None,
                    immune_cell_function_affected=self._functions(lower),
                    proliferation_effect=self._effect(lower, ["proliferation", "expand"]),
                    survival_or_persistence_effect=self._effect(lower, ["survival", "persistence", "memory"]),
                    cytotoxicity_effect=self._effect(lower, ["cytotoxic", "killing", "antitumor"]),
                    exhaustion_effect=-0.25 if "exhaustion" in lower and intervention in {"IL-7", "IL-15"} else (0.25 if "exhaustion" in lower else 0.0),
                    activation_induced_cell_death_effect=0.3 if "activation-induced cell death" in lower and intervention == "IL-2" else 0.0,
                    cytokine_production_effect=self._effect(lower, ["ifn-gamma", "cytokine production", "inflammatory cytokine"]),
                    tme_remodeling_effect=self._effect(lower, ["remodel", "microenvironment", "suppressive"]),
                    antigen_density_relevance="low antigen density challenge mentioned" if "low antigen" in lower else "not reported",
                    experimental_model_type=self._model_type(lower),
                    confidence_score=confidence,
                    supporting_citation=citation,
                    source_paper_id=paper.get("paper_id", ""),
                    notes="Direct citation from retrieved metadata; effect magnitudes are normalized qualitative encodings.",
                )
            )
        return records

    def _functions(self, lower: str) -> list[str]:
        labels = []
        for term, label in [("proliferation", "proliferation"), ("survival", "survival"), ("persistence", "persistence"), ("cytotoxic", "cytotoxicity"), ("exhaustion", "exhaustion"), ("microenvironment", "TME remodeling")]:
            if term in lower:
                labels.append(label)
        return labels

    def _effect(self, lower: str, terms: list[str]) -> float:
        return 0.45 if any(t in lower for t in terms) and any(t in lower for t in ["enhance", "improve", "promote", "increase", "support"]) else 0.0

    def _model_type(self, lower: str) -> str:
        if "clinical" in lower:
            return "clinical"
        if "in vivo" in lower or "preclinical" in lower:
            return "in vivo"
        if "in vitro" in lower:
            return "in vitro"
        if "physicell" in lower or "modeling" in lower:
            return "computational"
        if "review" in lower:
            return "review"
        return "unknown"

    def _citation(self, paper: dict) -> str:
        year = paper.get("year") or "n.d."
        doi = paper.get("doi")
        suffix = f" doi:{doi}" if doi else ""
        prefix = "[MOCK TEST RECORD] " if paper.get("source_database") == "Mock" else ""
        return f"{prefix}{paper.get('title', 'Untitled')} ({year}).{suffix}"
