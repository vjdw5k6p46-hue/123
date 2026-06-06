from __future__ import annotations

import xml.etree.ElementTree as ET

import requests


class PubMedClient:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        ids_resp = requests.get(
            f"{self.base}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
            timeout=20,
        )
        ids_resp.raise_for_status()
        ids = ids_resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        fetch_resp = requests.get(
            f"{self.base}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
            timeout=30,
        )
        fetch_resp.raise_for_status()
        return [self._parse_article(a) for a in ET.fromstring(fetch_resp.text).findall(".//PubmedArticle")]

    def _parse_article(self, article: ET.Element) -> dict:
        medline = article.find("MedlineCitation")
        pmid = medline.findtext("PMID") if medline is not None else None
        title = article.findtext(".//ArticleTitle") or ""
        abstract = " ".join(t.text or "" for t in article.findall(".//AbstractText"))
        journal = article.findtext(".//Journal/Title") or ""
        year = article.findtext(".//PubDate/Year") or ""
        doi = None
        for aid in article.findall(".//ArticleId"):
            if aid.attrib.get("IdType") == "doi":
                doi = aid.text
        authors = []
        for author in article.findall(".//Author"):
            last = author.findtext("LastName")
            initials = author.findtext("Initials")
            if last:
                authors.append(f"{last} {initials or ''}".strip())
        return {
            "paper_id": f"pmid:{pmid}" if pmid else title.lower(),
            "title": title,
            "authors": authors,
            "year": int(year) if year.isdigit() else None,
            "journal": journal,
            "doi": doi,
            "pmid": pmid,
            "abstract": abstract,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            "source_database": "PubMed",
        }
