from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BiologicalEvidence(BaseModel):
    intervention_name: str
    car_target: str | None = None
    tumor_model: str | None = None
    disease_context: str | None = None
    immune_cell_function_affected: list[str] = Field(default_factory=list)
    proliferation_effect: float = 0.0
    survival_or_persistence_effect: float = 0.0
    cytotoxicity_effect: float = 0.0
    exhaustion_effect: float = 0.0
    activation_induced_cell_death_effect: float = 0.0
    cytokine_production_effect: float = 0.0
    tme_remodeling_effect: float = 0.0
    antigen_density_relevance: str = "not reported"
    experimental_model_type: Literal["in vitro", "in vivo", "clinical", "computational", "review", "unknown"] = "unknown"
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.35)
    supporting_citation: str
    source_paper_id: str
    notes: str = ""
