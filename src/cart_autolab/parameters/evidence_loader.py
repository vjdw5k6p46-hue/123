from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cart_autolab.evidence.schemas import BiologicalEvidence


EVIDENCE_FILES = {
    "deterministic": "extracted_evidence_deterministic.json",
    "llm": "extracted_evidence_llm.json",
    "hybrid": "extracted_evidence_hybrid.json",
}


class EvidenceLoader:
    def load(self, run_dir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
        source = config.get("workflow", {}).get("evidence_source", "deterministic")
        if source not in EVIDENCE_FILES:
            raise ValueError("workflow.evidence_source must be deterministic, llm, or hybrid.")
        path = run_dir / EVIDENCE_FILES[source]
        if not path.exists() and source == "deterministic":
            path = run_dir / "extracted_evidence.json"
        if not path.exists():
            raise FileNotFoundError(f"Configured evidence_source '{source}' requires {run_dir / EVIDENCE_FILES[source]}.")
        records = json.loads(path.read_text(encoding="utf-8"))
        return self.validate(records, source)

    def validate(self, records: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
        validated = []
        for index, row in enumerate(records):
            clean = dict(row)
            flags = list(clean.get("low_confidence_flags", []))
            try:
                BiologicalEvidence.model_validate(clean)
            except Exception as exc:
                if source == "llm":
                    raise ValueError(f"Invalid LLM evidence record at index {index}: {exc}") from exc
                flags.append(f"schema_validation_warning:{exc}")
            if source in {"llm", "hybrid"} and clean.get("evidence_source") == "llm":
                if not clean.get("supporting_citation"):
                    flags.append("missing_supporting_citation")
                    clean["supporting_citation"] = "[MISSING CITATION METADATA]"
                if not clean.get("llm_call_ids"):
                    flags.append("missing_llm_call_id")
                if not clean.get("prompt_hashes"):
                    flags.append("missing_prompt_hash")
            if clean.get("supporting_citation", "").strip() == "":
                flags.append("missing_supporting_citation")
                clean["supporting_citation"] = "[MISSING CITATION METADATA]"
            clean["evidence_record_id"] = clean.get("evidence_record_id") or f"{source}:{index}:{clean.get('source_paper_id', 'unknown')}"
            clean["evidence_source"] = clean.get("evidence_source") or source
            clean["low_confidence_flags"] = sorted(set(flags))
            if flags:
                clean["confidence_score"] = min(float(clean.get("confidence_score", 0.2) or 0.2), 0.4)
            validated.append(clean)
        return validated
