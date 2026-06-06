from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cart_autolab.evidence.extractor import EvidenceExtractor
from cart_autolab.evidence.schemas import BiologicalEvidence
from cart_autolab.llm import AgentRunner


EFFECT_MAP = {
    "increased": 0.45,
    "decreased": -0.45,
    "mixed": 0.0,
    "not reported": 0.0,
    None: 0.0,
}


class ChunkEvidenceExtractionAgent:
    def extract(self, papers: list[dict[str, Any]], config: dict[str, Any], run_dir: Path, source: str = "deterministic") -> list[dict[str, Any]]:
        if source == "deterministic":
            records = EvidenceExtractor().extract(papers, config, run_dir)
            (run_dir / "extracted_evidence_deterministic.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
            return records

        records: list[dict[str, Any]] = []
        runner = AgentRunner(config.get("llm", {}), run_dir)
        for chunk_index, paper in enumerate(papers):
            result = runner.run(
                "chunk_evidence_extraction_agent",
                {
                    "paper_id": paper.get("paper_id", ""),
                    "title": paper.get("title", ""),
                    "doi": paper.get("doi", ""),
                    "pmid": paper.get("pmid", ""),
                    "chunk_index": chunk_index,
                    "experiment_config": json.dumps(config, indent=2),
                    "chunk_text": paper.get("abstract", "") or paper.get("title", ""),
                },
                schema={"required": ["evidence"]},
                input_artifacts=[run_dir / "included_papers.json"],
            )
            for item in result["parsed"].get("evidence", []):
                records.append(self._normalize_record(item, paper, result["call_id"], result["prompt_hash"]))
        path = run_dir / "extracted_evidence_llm.json"
        path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        return records

    def _normalize_record(self, item: dict[str, Any], paper: dict[str, Any], call_id: str, prompt_hash: str) -> dict[str, Any]:
        citation = item.get("citation") or {}
        supporting_citation = self._supporting_citation(citation, paper)
        record = BiologicalEvidence(
            intervention_name=item.get("intervention_name") or "not reported",
            car_target=_none_if_not_reported(item.get("car_target")),
            tumor_model=_none_if_not_reported(item.get("tumor_model")),
            disease_context=_none_if_not_reported(item.get("disease_context")),
            immune_cell_function_affected=item.get("immune_cell_function_affected") or [],
            proliferation_effect=_effect_value(item.get("proliferation_effect")),
            survival_or_persistence_effect=_effect_value(item.get("survival_or_persistence_effect")),
            cytotoxicity_effect=_effect_value(item.get("cytotoxicity_effect")),
            exhaustion_effect=_effect_value(item.get("exhaustion_effect")),
            activation_induced_cell_death_effect=_effect_value(item.get("activation_induced_cell_death_effect")),
            cytokine_production_effect=_effect_value(item.get("cytokine_production_effect")),
            tme_remodeling_effect=_effect_value(item.get("tme_remodeling_effect")),
            antigen_density_relevance=item.get("antigen_density_relevance") or "not reported",
            experimental_model_type=_model_type(item.get("experimental_model_type")),
            confidence_score=float(item.get("confidence_score", 0.2) or 0.2),
            supporting_citation=supporting_citation,
            source_paper_id=paper.get("paper_id", item.get("paper_id", "")),
            notes="LLM-derived evidence normalized from schema-validated output; verify citation provenance before scientific use.",
        ).model_dump()
        record["evidence_source"] = "llm"
        record["llm_call_ids"] = [call_id]
        record["prompt_hashes"] = [prompt_hash]
        record["supporting_text"] = item.get("supporting_text", "")
        return record

    def _supporting_citation(self, citation: dict[str, Any], paper: dict[str, Any]) -> str:
        title = citation.get("title") or paper.get("title")
        doi = citation.get("doi") or paper.get("doi")
        pmid = citation.get("pmid") or paper.get("pmid")
        if not any([title, doi, pmid, paper.get("paper_id")]):
            return "[MISSING CITATION METADATA]"
        parts = [str(title or "missing title")]
        if doi:
            parts.append(f"doi:{doi}")
        if pmid:
            parts.append(f"pmid:{pmid}")
        if paper.get("source_database") == "Mock":
            parts.insert(0, "[MOCK TEST RECORD]")
        return " ".join(parts)


def _none_if_not_reported(value: Any) -> str | None:
    if value in {None, "", "not reported"}:
        return None
    return str(value)


def _effect_value(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    return EFFECT_MAP.get(str(value).lower() if value is not None else None, 0.0)


def _model_type(value: Any) -> str:
    value = str(value or "unknown").lower()
    allowed = {"in vitro", "in vivo", "clinical", "computational", "review", "unknown"}
    return value if value in allowed else "unknown"
