from __future__ import annotations

import requests


class CrossrefClient:
    endpoint = "https://api.crossref.org/works"

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        resp = requests.get(self.endpoint, params={"query": query, "rows": max_results}, timeout=20)
        resp.raise_for_status()
        records = []
        for item in resp.json().get("message", {}).get("items", []):
            records.append(
                {
                    "paper_id": f"doi:{item.get('DOI')}" if item.get("DOI") else item.get("URL"),
                    "title": " ".join(item.get("title") or []),
                    "authors": [
                        f"{a.get('family', '')} {a.get('given', '')}".strip()
                        for a in item.get("author", [])
                    ],
                    "year": ((item.get("published-print") or item.get("published-online") or {}).get("date-parts") or [[None]])[0][0],
                    "journal": " ".join(item.get("container-title") or []),
                    "doi": item.get("DOI"),
                    "pmid": None,
                    "abstract": item.get("abstract") or "",
                    "url": item.get("URL"),
                    "source_database": "Crossref",
                }
            )
        return records
