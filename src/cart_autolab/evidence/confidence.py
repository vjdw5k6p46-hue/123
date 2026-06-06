from __future__ import annotations


def evidence_confidence(text: str, direct_target: bool = False) -> float:
    lowered = text.lower()
    score = 0.25
    if "car t" in lowered or "car-t" in lowered:
        score += 0.2
    if any(term in lowered for term in ["in vivo", "preclinical", "clinical", "solid tumor"]):
        score += 0.15
    if any(term in lowered for term in ["gpc3", "hepatocellular", "liver"]):
        score += 0.15
    if direct_target:
        score += 0.15
    if any(term in lowered for term in ["limited", "uncertain", "risk", "toxicity"]):
        score -= 0.05
    return max(0.05, min(0.9, score))
