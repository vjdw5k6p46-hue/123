from __future__ import annotations

import requests


class OpenAlexClient:
    endpoint = "https://api.openalex.org/works"

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        resp = requests.get(self.endpoint, params={"search": query, "per-page": max_results}, timeout=20)
        resp.raise_for_status()
        records = []
        for item in resp.json().get("results", []):
            abstract = ""
            inverted = item.get("abstract_inverted_index") or {}
            if inverted:
                words = sorted(((pos, word) for word, positions in inverted.items() for pos in positions))
                abstract = " ".join(word for _, word in words)
            records.append(
                {
                    "paper_id": item.get("id"),
                    "title": item.get("title") or "",
                    "authors": [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])],
                    "year": item.get("publication_year"),
                    "journal": (item.get("primary_location") or {}).get("source", {}).get("display_name"),
                    "doi": (item.get("doi") or "").replace("https://doi.org/", "") or None,
                    "pmid": None,
                    "abstract": abstract,
                    "url": item.get("doi") or item.get("id"),
                    "source_database": "OpenAlex",
                }
            )
        return records
