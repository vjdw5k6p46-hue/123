from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ALLOWED_CYTOKINES = {"IL-2", "IL-7", "IL-12", "IL-15", "IL-18", "other", "not reported", "not_reported"}
ALLOWED_ENDPOINTS = {
    "proliferation",
    "persistence",
    "cytotoxicity",
    "exhaustion",
    "IFN_gamma",
    "TME_remodeling",
    "AICD",
    "toxicity",
    "safety",
    "not_reported",
}
ALLOWED_DIRECTIONS = {"increased", "decreased", "mixed", "no_change", "not_reported"}
ALLOWED_STRENGTHS = {"direct", "indirect", "review", "computational", "not_reported"}
ALLOWED_MODEL_TYPES = {"in_vitro", "in_vivo", "clinical", "computational", "review", "unknown"}

REQUIRED_FIELDS = {
    "record_id",
    "model_name",
    "paper_id",
    "chunk_id",
    "chunk_index",
    "title",
    "cytokine",
    "is_t_cell_self_secreting_or_engineered_secretion",
    "endpoint",
    "effect_direction",
    "evidence_strength",
    "model_type",
    "supporting_text",
    "confidence",
    "low_confidence_flags",
    "citation_provenance_complete",
}


def validate_record(record: dict[str, Any], chunk_metadata: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    missing = sorted(field for field in REQUIRED_FIELDS if field not in record)
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")

    cytokine = _normalize_not_reported(record.get("cytokine"))
    endpoint = _normalize_not_reported(record.get("endpoint"))
    direction = _normalize_not_reported(record.get("effect_direction"))
    strength = _normalize_not_reported(record.get("evidence_strength"))
    model_type = record.get("model_type") or "unknown"

    if cytokine not in ALLOWED_CYTOKINES:
        errors.append(f"invalid cytokine: {cytokine}")
    if endpoint not in ALLOWED_ENDPOINTS:
        errors.append(f"invalid endpoint: {endpoint}")
    if direction not in ALLOWED_DIRECTIONS:
        errors.append(f"invalid effect_direction: {direction}")
    if strength not in ALLOWED_STRENGTHS:
        errors.append(f"invalid evidence_strength: {strength}")
    if model_type not in ALLOWED_MODEL_TYPES:
        errors.append(f"invalid model_type: {model_type}")

    try:
        confidence = float(record.get("confidence"))
    except (TypeError, ValueError):
        confidence = -1.0
        errors.append("confidence is not numeric")
    if confidence < 0.0 or confidence > 1.0:
        errors.append("confidence must be between 0 and 1")

    supporting_text = str(record.get("supporting_text") or "")
    if len(supporting_text) > 600:
        errors.append("supporting_text exceeds 600 characters")
    if not isinstance(record.get("low_confidence_flags"), list):
        errors.append("low_confidence_flags must be a list")
    if not isinstance(record.get("citation_provenance_complete"), bool):
        errors.append("citation_provenance_complete must be boolean")
    if not record.get("chunk_id") and record.get("chunk_index") is None:
        errors.append("chunk_id or chunk_index is required")
    if not record.get("paper_id"):
        errors.append("paper_id is required if available")

    if chunk_metadata:
        for field in ["doi", "pmid", "pmcid", "title", "chunk_id", "paper_id"]:
            if field in record and field in chunk_metadata and record.get(field) not in {None, "", chunk_metadata.get(field)}:
                errors.append(f"{field} differs from supplied chunk metadata")

    if errors:
        return None, errors

    normalized = dict(record)
    normalized["cytokine"] = "not_reported" if cytokine == "not reported" else cytokine
    normalized["endpoint"] = endpoint
    normalized["effect_direction"] = direction
    normalized["evidence_strength"] = strength
    normalized["model_type"] = model_type
    normalized["confidence"] = max(0.0, min(1.0, confidence))
    normalized["supporting_text"] = supporting_text
    return normalized, []


def validate_records(records: list[dict[str, Any]], chunk_metadata_by_id: dict[str, dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    chunk_metadata_by_id = chunk_metadata_by_id or {}
    for index, record in enumerate(records):
        metadata = chunk_metadata_by_id.get(str(record.get("chunk_id"))) or chunk_metadata_by_id.get(str(record.get("paper_id")))
        normalized, errors = validate_record(record, metadata)
        if normalized is None:
            failures.append({"record_index": index, "record": record, "failure_reasons": errors})
        else:
            valid.append(normalized)
    return valid, failures


def validate_jsonl(input_path: str | Path, valid_path: str | Path, failures_path: str | Path, chunk_metadata_by_id: dict[str, dict[str, Any]] | None = None) -> dict[str, int]:
    records = _read_jsonl(input_path)
    valid, failures = validate_records(records, chunk_metadata_by_id)
    _write_jsonl(valid_path, valid)
    _write_jsonl(failures_path, failures)
    return {"input_records": len(records), "valid_records": len(valid), "failed_records": len(failures)}


def _normalize_not_reported(value: Any) -> str:
    text = str(value or "not_reported").strip()
    return "not_reported" if text in {"not reported", "not_reported"} else text


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    p = Path(path)
    if not p.exists():
        return records
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _write_jsonl(path: str | Path, records: list[dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
