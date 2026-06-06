from __future__ import annotations

import json
from pathlib import Path

from .crossref_client import CrossrefClient
from .curated_loader import load_curated_papers
from .deduplication import deduplicate_papers
from .openalex_client import OpenAlexClient
from .pubmed_client import PubMedClient
from .semantic_scholar_client import SemanticScholarClient


class LiteratureSearchAgent:
    def __init__(self, mode: str = "mock", mock_path: Path | None = None):
        self.mode = mode
        self.mock_path = mock_path
        self.clients = [PubMedClient(), SemanticScholarClient(), OpenAlexClient(), CrossrefClient()]

    def generate_queries(self, config: dict) -> list[str]:
        target = config["car_target_antigen"]
        tumor = config["tumor_type"]
        density = config["antigen_density_condition"]
        interventions = " ".join(i for i in config["candidate_interventions"] if i.lower() != "control")
        variable = config["engineering_variable"].replace("_", " ")
        return [
            f"{target} CAR T {interventions} {tumor} {density} antigen density",
            f"cytokine armored CAR T {interventions}" if "cytokine" in variable else f"CAR T {variable} engineering",
            "CAR T cytokine engineering persistence exhaustion cytotoxicity",
            "IL-15 armored CAR T solid tumor",
            "agent-based model CAR T tumor microenvironment PhysiCell",
            "PhysiCell CAR T simulation tumor microenvironment",
            "single-cell foundation model CAR T scGPT perturbation validation",
        ]

    def search(self, config: dict, output_dir: Path) -> dict:
        queries = self.generate_queries(config)
        max_results = int(config.get("literature", {}).get("max_results_per_query", 8))
        raw: list[dict] = []
        curated_rejected: list[dict] = []
        if self.mode == "mock":
            raw = self._load_mock()
        elif self.mode == "curated":
            curated_path = config.get("literature", {}).get("curated_path")
            if not curated_path:
                raise ValueError("literature.mode=curated requires literature.curated_path.")
            curated_accepted, curated_rejected = load_curated_papers(curated_path)
            raw = curated_accepted + curated_rejected
        else:
            for query in queries:
                for client in self.clients:
                    try:
                        for record in client.search(query, max_results=max_results):
                            record["query"] = query
                            raw.append(record)
                    except Exception as exc:
                        raw.append({"paper_id": f"error:{client.__class__.__name__}:{query}", "title": "", "abstract": "", "source_database": client.__class__.__name__, "error": str(exc), "query": query})
        deduped = deduplicate_papers([r for r in raw if r.get("title") and r.get("curated_validation_status") != "rejected"])
        included, excluded = self._screen(deduped, config)
        excluded = curated_rejected + excluded
        payload = {"queries": queries, "raw_results": raw, "deduplicated_papers": deduped, "included_papers": included, "excluded_papers": excluded}
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, data in [("search_queries.json", queries), ("raw_literature_results.json", raw), ("deduplicated_papers.json", deduped), ("included_papers.json", included), ("excluded_papers.json", excluded)]:
            (output_dir / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return payload

    def _load_mock(self) -> list[dict]:
        path = self.mock_path or Path(__file__).resolve().parents[3] / "data" / "mock_literature" / "mock_papers.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _screen(self, papers: list[dict], config: dict) -> tuple[list[dict], list[dict]]:
        include_terms = [config["car_target_antigen"].lower(), "car", "cytokine", "physicell", "agent-based", "il-15", "il-12", "il-7", "il-18", "il-2"]
        included, excluded = [], []
        for paper in papers:
            text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
            hits = sum(term in text for term in include_terms)
            paper["relevance_score"] = min(1.0, hits / 4)
            if hits >= 1:
                paper["inclusion_reason"] = "Matches CAR-T, cytokine engineering, target biology, or PhysiCell simulation context."
                included.append(paper)
            else:
                paper["exclusion_reason"] = "No direct CAR-T, cytokine, target, or simulation relevance in available metadata."
                excluded.append(paper)
        return included, excluded
