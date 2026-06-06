from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PARAMETER_DEFAULTS = {
    "half_effective_concentration_K": 1.0,
    "proliferation_enhancement_aP": 0.0,
    "survival_enhancement_aS": 0.0,
    "cytotoxicity_enhancement_aC": 0.0,
    "exhaustion_modulation_aE": 0.0,
    "activation_induced_death_penalty_bD": 0.0,
    "ifng_effect": 0.0,
    "pdl1_effect": 0.0,
    "hypoxia_effect": 0.0,
    "tme_remodeling_effect": 0.0,
}


def proposals_from_fingerprint(fingerprint: dict[str, Any]) -> dict[str, Any]:
    proposals = []
    for cytokine, payload in sorted((fingerprint.get("cytokines") or {}).items()):
        endpoints = payload.get("endpoints", {})
        quality = _overall_quality(endpoints)
        changes = dict(PARAMETER_DEFAULTS)
        warnings: list[str] = []
        flags: list[str] = []

        changes["proliferation_enhancement_aP"] = _endpoint_value(endpoints.get("proliferation"), positive=True) * 0.45
        changes["survival_enhancement_aS"] = _endpoint_value(endpoints.get("persistence"), positive=True) * 0.55
        changes["cytotoxicity_enhancement_aC"] = _endpoint_value(endpoints.get("cytotoxicity"), positive=True) * 0.55
        changes["exhaustion_modulation_aE"] = _endpoint_value(endpoints.get("exhaustion"), positive=False) * 0.35
        changes["activation_induced_death_penalty_bD"] = max(0.0, _endpoint_value(endpoints.get("AICD"), positive=True) * 0.35)
        changes["ifng_effect"] = _endpoint_value(endpoints.get("IFN_gamma"), positive=True) * 0.45
        changes["tme_remodeling_effect"] = _endpoint_value(endpoints.get("TME_remodeling"), positive=True) * 0.45
        toxicity = max(_endpoint_value(endpoints.get("toxicity"), positive=True), _endpoint_value(endpoints.get("safety"), positive=True))
        if toxicity > 0:
            warnings.append("toxicity or safety signal detected; do not treat as efficacy boost")
            changes["pdl1_effect"] = min(0.35, toxicity * 0.25)
        if changes["activation_induced_death_penalty_bD"] > 0:
            warnings.append("AICD risk signal detected")

        if quality < 0.25:
            status = "insufficient_evidence"
        elif quality < 0.55:
            status = "low_confidence"
        else:
            status = "supported"
        if any((ep.get("review_record_count", 0) >= ep.get("number_of_supporting_records", 0)) for ep in endpoints.values() if ep.get("number_of_supporting_records", 0)):
            flags.append("review_only_or_review_dominant_evidence")
        if any(ep.get("citation_traceability_fraction", 0.0) < 0.7 for ep in endpoints.values()):
            flags.append("low_citation_traceability")
        if any(ep.get("disagreement_fraction", 0.0) > 0.35 for ep in endpoints.values()):
            flags.append("high_direction_disagreement")

        proposals.append(
            {
                "model_name": fingerprint.get("model_name"),
                "cytokine": cytokine,
                "proposal_status": status,
                "proposed_parameter_changes": {key: _clamp_value(key, value * quality) for key, value in changes.items()},
                "bounds_applied": True,
                "supporting_record_ids": _collect(endpoints, "supporting_record_ids"),
                "supporting_citations": _collect(endpoints, "representative_citations"),
                "warnings": warnings + ["These are provenance-linked parameter proposals requiring human review before external PhysiCell simulation."],
                "low_confidence_flags": sorted(set(flags)),
                "proposal_quality_score": round(quality, 4),
            }
        )
    return {"model_name": fingerprint.get("model_name"), "proposals": proposals, "note": "These are provenance-linked parameter proposals requiring human review before external PhysiCell simulation."}


def write_parameter_proposals(fingerprint_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    fingerprint = json.loads(Path(fingerprint_path).read_text(encoding="utf-8"))
    payload = proposals_from_fingerprint(fingerprint)
    Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def proposal_score(proposal: dict[str, Any]) -> float:
    changes = proposal.get("proposed_parameter_changes") or {}
    positive = (
        changes.get("proliferation_enhancement_aP", 0.0)
        + changes.get("survival_enhancement_aS", 0.0)
        + changes.get("cytotoxicity_enhancement_aC", 0.0)
        + changes.get("ifng_effect", 0.0)
        + changes.get("tme_remodeling_effect", 0.0)
    )
    penalty = changes.get("activation_induced_death_penalty_bD", 0.0) + abs(changes.get("pdl1_effect", 0.0))
    return float(positive - penalty)


def _overall_quality(endpoints: dict[str, dict[str, Any]]) -> float:
    if not endpoints:
        return 0.0
    qualities = []
    for ep in endpoints.values():
        confidence = ep.get("mean_confidence", 0.0)
        traceability = ep.get("citation_traceability_fraction", 0.0)
        disagreement = ep.get("disagreement_fraction", 0.0)
        low_conf = ep.get("low_confidence_fraction", 0.0)
        review_penalty = 0.6 if ep.get("review_record_count", 0) and ep.get("direct_record_count", 0) == 0 else 1.0
        qualities.append(confidence * traceability * max(0.0, 1.0 - disagreement) * max(0.0, 1.0 - low_conf) * review_penalty)
    return max(0.0, min(1.0, sum(qualities) / len(qualities)))


def _endpoint_value(endpoint: dict[str, Any] | None, *, positive: bool) -> float:
    if not endpoint:
        return 0.0
    direction = endpoint.get("consensus_effect_direction")
    sign = 1.0 if direction == "increased" else -1.0 if direction == "decreased" else 0.0
    if not positive:
        sign *= -1.0
    quality = endpoint.get("mean_confidence", 0.0) * endpoint.get("citation_traceability_fraction", 0.0)
    quality *= max(0.0, 1.0 - endpoint.get("disagreement_fraction", 0.0))
    return sign * quality


def _clamp_value(key: str, value: float) -> float:
    if key == "half_effective_concentration_K":
        return round(max(0.1, min(10.0, value or 1.0)), 4)
    return round(max(-1.0, min(1.0, float(value))), 4)


def _collect(endpoints: dict[str, dict[str, Any]], field: str) -> list[Any]:
    out = []
    for ep in endpoints.values():
        values = ep.get(field) or []
        for value in values:
            marker = json.dumps(value, sort_keys=True) if isinstance(value, dict) else str(value)
            if marker not in {json.dumps(v, sort_keys=True) if isinstance(v, dict) else str(v) for v in out}:
                out.append(value)
    return out[:50]
