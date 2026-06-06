from __future__ import annotations

import re


def normalize_title(title: str) -> str:
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


def deduplicate_papers(records: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for record in records:
        key = (record.get("doi") or record.get("pmid") or normalize_title(record.get("title", ""))).lower()
        if not key:
            key = record.get("paper_id", "")
        if key not in seen:
            seen[key] = record
            seen[key]["source_databases"] = [record.get("source_database", "unknown")]
        else:
            sources = seen[key].setdefault("source_databases", [])
            source = record.get("source_database", "unknown")
            if source not in sources:
                sources.append(source)
            if not seen[key].get("abstract") and record.get("abstract"):
                seen[key]["abstract"] = record["abstract"]
    return list(seen.values())
