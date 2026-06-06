from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROVENANCE_FIELDS = ("doi", "pmid", "pmcid", "url", "source_paper_id")


class CuratedLiteratureError(ValueError):
    pass


def load_curated_papers(path: str | Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    curated_path = _resolve_path(path)
    if not curated_path.exists():
        raise CuratedLiteratureError(
            f"Curated literature file not found: {curated_path}. "
            "Create it from data/manuscript_literature/curated_papers.template.json with real paper metadata and provenance."
        )
    payload = json.loads(curated_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise CuratedLiteratureError("Curated literature file must contain a JSON list of paper records.")

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, record in enumerate(payload):
        if not isinstance(record, dict):
            rejected.append(
                {
                    "curated_record_index": index,
                    "curated_validation_status": "rejected",
                    "curated_validation_errors": ["record is not a JSON object"],
                }
            )
            continue
        normalized = dict(record)
        errors = _validation_errors(normalized)
        normalized["curated_record_index"] = index
        normalized["curated_path"] = str(curated_path)
        if errors:
            normalized["curated_validation_status"] = "rejected"
            normalized["curated_validation_errors"] = errors
            rejected.append(normalized)
            continue
        normalized["curated_validation_status"] = "passed"
        normalized["curated_validation_errors"] = []
        normalized.setdefault("source_database", "Curated")
        normalized.setdefault("paper_id", _paper_id_from_provenance(normalized))
        accepted.append(normalized)
    return accepted, rejected


def _validation_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(record.get("title") or "").strip():
        errors.append("missing required title")
    if not any(str(record.get(field) or "").strip() for field in PROVENANCE_FIELDS):
        errors.append("missing provenance; provide at least one of DOI, PMID, PMCID, URL, or source_paper_id")
    return errors


def _paper_id_from_provenance(record: dict[str, Any]) -> str:
    for field in PROVENANCE_FIELDS:
        value = str(record.get(field) or "").strip()
        if value:
            return f"{field}:{value}"
    return ""


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / candidate
