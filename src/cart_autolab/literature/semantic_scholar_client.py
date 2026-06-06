from __future__ import annotations

import os

import requests


class SemanticScholarClient:
    endpoint = "https://api.semanticscholar.org/graph/v1/paper/search"

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        headers = {}
        if os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
            headers["x-api-key"] = os.environ["SEMANTIC_SCHOLAR_API_KEY"]
        resp = requests.get(
            self.endpoint,
            params={"query": query, "limit": max_results, "fields": "title,authors,year,venue,abstract,externalIds,url"},
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        records = []
        for item in resp.json().get("data", []):
            ext = item.get("externalIds") or {}
            records.append(
                {
                    "paper_id": f"semanticscholar:{item.get('paperId')}",
                    "title": item.get("title") or "",
                    "authors": [a.get("name", "") for a in item.get("authors", [])],
                    "year": item.get("year"),
                    "journal": item.get("venue"),
                    "doi": ext.get("DOI"),
                    "pmid": ext.get("PubMed"),
                    "abstract": item.get("abstract") or "",
                    "url": item.get("url"),
                    "source_database": "Semantic Scholar",
                }
            )
        return records
