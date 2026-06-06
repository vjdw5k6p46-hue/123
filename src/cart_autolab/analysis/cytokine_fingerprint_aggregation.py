from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EFFICACY_ENDPOINTS = ["proliferation", "persistence", "cytotoxicity", "exhaustion", "IFN_gamma", "TME_remodeling", "AICD", "toxicity", "safety"]


def aggregate_cytokine_fingerprint(records: list[dict[str, Any]], model_name: str | None = None) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        cytokine = record.get("cytokine") or "not_reported"
        endpoint = record.get("endpoint") or "not_reported"
        if cytokine in {"not_reported", "other"} or endpoint == "not_reported":
            continue
        grouped[(cytokine, endpoint)].append(record)

    cytokines: dict[str, dict[str, Any]] = defaultdict(lambda: {"endpoints": {}})
    for (cytokine, endpoint), rows in sorted(grouped.items()):
        direction_counts = Counter(row.get("effect_direction", "not_reported") for row in rows)
        total = len(rows)
        consensus, consensus_count = direction_counts.most_common(1)[0]
        traceable = sum(1 for row in rows if row.get("citation_provenance_complete"))
        low_conf = sum(1 for row in rows if row.get("low_confidence_flags"))
        confidence_values = [float(row.get("confidence", 0.0) or 0.0) for row in rows]
        endpoint_payload = {
            "number_of_supporting_records": total,
            "direct_record_count": sum(1 for row in rows if row.get("evidence_strength") == "direct"),
            "review_record_count": sum(1 for row in rows if row.get("evidence_strength") == "review"),
            "in_vitro_count": sum(1 for row in rows if row.get("model_type") == "in_vitro"),
            "in_vivo_count": sum(1 for row in rows if row.get("model_type") == "in_vivo"),
            "clinical_count": sum(1 for row in rows if row.get("model_type") == "clinical"),
            "computational_count": sum(1 for row in rows if row.get("model_type") == "computational"),
            "mean_confidence": round(sum(confidence_values) / total, 4) if total else 0.0,
            "citation_traceability_fraction": round(traceable / total, 4) if total else 0.0,
            "consensus_effect_direction": consensus,
            "disagreement_fraction": round(1.0 - (consensus_count / total), 4) if total else 0.0,
            "low_confidence_fraction": round(low_conf / total, 4) if total else 0.0,
            "representative_citations": _representative_citations(rows),
            "representative_chunk_ids": _unique([row.get("chunk_id") for row in rows], limit=10),
            "supporting_record_ids": _unique([row.get("record_id") for row in rows], limit=50),
        }
        cytokines[cytokine]["endpoints"][endpoint] = endpoint_payload

    ranked = []
    for cytokine, payload in cytokines.items():
        score = _fingerprint_score(payload["endpoints"])
        ranked.append({"cytokine": cytokine, "proposal_score": round(score, 4)})
    ranked.sort(key=lambda row: row["proposal_score"], reverse=True)

    return {
        "model_name": model_name,
        "record_count": len(records),
        "cytokines": dict(cytokines),
        "cytokine_ranking": ranked,
        "endpoint_mapping": {
            "proliferation": "proliferation_enhancement evidence",
            "persistence": "survival/persistence evidence",
            "cytotoxicity": "cytotoxicity evidence",
            "exhaustion": "exhaustion modulation evidence",
            "IFN_gamma": "ifng evidence",
            "TME_remodeling": "tme_remodeling evidence",
            "AICD": "activation_induced_death_penalty evidence",
            "toxicity": "safety warning, not efficacy boost",
            "safety": "safety warning, not efficacy boost",
        },
    }


def aggregate_jsonl(validated_jsonl: str | Path, output_path: str | Path, model_name: str | None = None) -> dict[str, Any]:
    records = _read_jsonl(validated_jsonl)
    payload = aggregate_cytokine_fingerprint(records, model_name=model_name)
    Path(output_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _fingerprint_score(endpoints: dict[str, dict[str, Any]]) -> float:
    weights = {
        "proliferation": 0.9,
        "persistence": 1.2,
        "cytotoxicity": 1.2,
        "IFN_gamma": 0.6,
        "TME_remodeling": 0.7,
        "exhaustion": 0.6,
        "AICD": -0.7,
        "toxicity": -0.8,
        "safety": -0.8,
    }
    score = 0.0
    for endpoint, payload in endpoints.items():
        direction = payload.get("consensus_effect_direction")
        sign = 1.0 if direction == "increased" else -1.0 if direction == "decreased" else 0.0
        if endpoint == "exhaustion":
            sign *= -1.0
        base = weights.get(endpoint, 0.0) * sign
        quality = payload.get("mean_confidence", 0.0) * payload.get("citation_traceability_fraction", 0.0)
        penalty = 1.0 - max(payload.get("disagreement_fraction", 0.0), payload.get("low_confidence_fraction", 0.0))
        score += base * quality * max(0.0, penalty)
    return score


def _representative_citations(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    citations = []
    seen = set()
    for row in rows:
        key = (row.get("pmid"), row.get("doi"), row.get("title"))
        if key in seen:
            continue
        seen.add(key)
        citations.append({"title": row.get("title"), "doi": row.get("doi"), "pmid": row.get("pmid"), "pmcid": row.get("pmcid")})
        if len(citations) >= limit:
            break
    return citations


def _unique(values: list[Any], limit: int) -> list[Any]:
    out = []
    for value in values:
        if value in {None, ""} or value in out:
            continue
        out.append(value)
        if len(out) >= limit:
            break
    return out


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
