from __future__ import annotations

from pydantic import BaseModel, Field


class CytokineFingerprint(BaseModel):
    intervention_name: str
    half_effective_concentration_K: float = Field(ge=0.0)
    proliferation_enhancement_aP: float = Field(ge=0.0, le=2.0)
    survival_enhancement_aS: float = Field(ge=0.0, le=2.0)
    cytotoxicity_enhancement_aC: float = Field(ge=0.0, le=2.0)
    exhaustion_modulation_aE: float = Field(ge=-1.0, le=1.0)
    activation_induced_death_penalty_bD: float = Field(ge=0.0, le=1.0)
    ifng_effect: float = Field(ge=-1.0, le=1.0)
    pdl1_effect: float = Field(ge=-1.0, le=1.0)
    hypoxia_effect: float = Field(ge=-1.0, le=1.0)
    tme_remodeling_effect: float = Field(ge=-1.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    evidence_summary: str
    supporting_references: list[str]
    evidence_source: str = "deterministic"
    evidence_record_ids: list[str] = Field(default_factory=list)
    llm_call_ids: list[str] = Field(default_factory=list)
    prompt_hashes: list[str] = Field(default_factory=list)
    parameter_derivation_notes: str = ""
    low_confidence_flags: list[str] = Field(default_factory=list)


class GenericInterventionParameters(BaseModel):
    intervention_name: str
    car_affinity: float = 0.5
    antigen_threshold: float = 0.5
    co_stimulatory_strength: float = 0.5
    killing_rate: float = 0.5
    exhaustion_rate: float = 0.5
    proliferation_rate: float = 0.5
    migration_infiltration: float = 0.5
    suppressive_tme_resistance: float = 0.5
    persistence_memory: float = 0.5
    safety_toxicity_flags: list[str] = Field(default_factory=list)
    confidence_score: float = 0.35
    uncertainty: float = 0.65
    evidence_summary: str = ""
    supporting_references: list[str] = Field(default_factory=list)
    evidence_source: str = "deterministic"
    evidence_record_ids: list[str] = Field(default_factory=list)
    llm_call_ids: list[str] = Field(default_factory=list)
    prompt_hashes: list[str] = Field(default_factory=list)
    parameter_derivation_notes: str = ""
    low_confidence_flags: list[str] = Field(default_factory=list)
