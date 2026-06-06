from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import requests


class PaperDownloader:
    """Download open-access paper artifacts with provenance.

    This class intentionally avoids paywalled bypasses. It tries PMC/Europe PMC,
    bioRxiv/medRxiv, Unpaywall OA locations when an email is configured, and
    direct URLs that return PDF/XML/text content.
    """

    def __init__(
        self,
        email: str | None = None,
        max_papers: int = 20,
        timeout: int = 30,
        user_agent: str = "cart-autolab/0.1 (open-access paper downloader)",
    ):
        self.email = email
        self.max_papers = max_papers
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def download(self, papers: list[dict], output_dir: Path) -> dict:
        paper_dir = output_dir / "papers"
        for child in ["pdf", "xml", "text"]:
            (paper_dir / child).mkdir(parents=True, exist_ok=True)
        records = []
        for paper in papers[: self.max_papers]:
            records.append(self._download_one(paper, paper_dir))
        payload = {
            "policy": "Only open-access or directly available artifacts are downloaded. Paywalled access is not bypassed.",
            "paper_dir": str(paper_dir),
            "records": records,
        }
        (output_dir / "downloaded_papers_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _download_one(self, paper: dict, paper_dir: Path) -> dict:
        title = paper.get("title") or paper.get("paper_id") or "untitled"
        slug = self._slug(title)
        result = {
            "paper_id": paper.get("paper_id"),
            "title": title,
            "doi": paper.get("doi"),
            "pmid": paper.get("pmid"),
            "status": "not_downloaded",
            "attempts": [],
            "artifacts": [],
        }
        if paper.get("source_database") == "Mock":
            result["status"] = "skipped_mock_record"
            return result

        candidates = self._candidate_urls(paper)
        seen = set()
        for label, url in candidates:
            if not url or url in seen:
                continue
            seen.add(url)
            attempt = {"source": label, "url": url}
            try:
                response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                attempt["status_code"] = response.status_code
                ctype = response.headers.get("content-type", "").lower()
                if response.status_code >= 400:
                    result["attempts"].append(attempt)
                    continue
                artifact = self._save_response(response, paper_dir, slug, label, ctype)
                if artifact:
                    attempt["saved"] = artifact
                    result["artifacts"].append(artifact)
                    result["status"] = "downloaded"
                    result["attempts"].append(attempt)
                    break
                attempt["reason"] = f"unsupported_content_type:{ctype}"
            except Exception as exc:
                attempt["error"] = f"{type(exc).__name__}: {exc}"
            result["attempts"].append(attempt)
        return result

    def _candidate_urls(self, paper: dict) -> list[tuple[str, str | None]]:
        doi = self._clean_doi(paper.get("doi"))
        pmid = str(paper.get("pmid") or "").strip() or None
        urls: list[tuple[str, str | None]] = []

        pmcid = self._pmcid_from_idconv(doi=doi, pmid=pmid)
        if pmcid:
            urls.append(("pmc_pdf", f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/"))
            urls.append(("pmc_xml", f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/?report=xml"))
            urls.append(("europe_pmc_pdf", f"https://europepmc.org/articles/{pmcid}?pdf=render"))

        epmc = self._europe_pmc_lookup(doi=doi, pmid=pmid)
        if epmc:
            if epmc.get("pmcid") and epmc["pmcid"] != pmcid:
                urls.append(("europe_pmc_pdf", f"https://europepmc.org/articles/{epmc['pmcid']}?pdf=render"))
            for item in epmc.get("fullTextUrlList", {}).get("fullTextUrl", []) or []:
                urls.append((f"europe_pmc_{item.get('availabilityCode', 'fulltext')}", item.get("url")))

        if doi and doi.startswith("10.1101/"):
            urls.append(("biorxiv_pdf", f"https://www.biorxiv.org/content/{doi}.full.pdf"))
            urls.append(("medrxiv_pdf", f"https://www.medrxiv.org/content/{doi}.full.pdf"))

        if doi and self.email:
            urls.extend(self._unpaywall_urls(doi))

        direct_url = paper.get("url")
        if direct_url:
            urls.append(("record_url", direct_url))
        return urls

    def _pmcid_from_idconv(self, doi: str | None, pmid: str | None) -> str | None:
        ids = doi or pmid
        if not ids:
            return None
        params = {"ids": ids, "format": "json", "tool": "cart_autolab"}
        if self.email:
            params["email"] = self.email
        try:
            response = self.session.get("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/", params=params, timeout=self.timeout)
            response.raise_for_status()
            records = response.json().get("records", [])
            if records:
                return records[0].get("pmcid")
        except Exception:
            return None
        return None

    def _europe_pmc_lookup(self, doi: str | None, pmid: str | None) -> dict | None:
        if doi:
            query = f'DOI:"{doi}"'
        elif pmid:
            query = f"EXT_ID:{pmid}"
        else:
            return None
        try:
            response = self.session.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                params={"query": query, "format": "json", "resultType": "core", "pageSize": 1},
                timeout=self.timeout,
            )
            response.raise_for_status()
            results = response.json().get("resultList", {}).get("result", [])
            return results[0] if results else None
        except Exception:
            return None

    def _unpaywall_urls(self, doi: str) -> list[tuple[str, str | None]]:
        try:
            response = self.session.get(f"https://api.unpaywall.org/v2/{quote(doi)}", params={"email": self.email}, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []
        urls = []
        for loc in [data.get("best_oa_location")] + (data.get("oa_locations") or []):
            if not loc:
                continue
            urls.append(("unpaywall_pdf", loc.get("url_for_pdf")))
            urls.append(("unpaywall_landing", loc.get("url")))
        return urls

    def _save_response(self, response: requests.Response, paper_dir: Path, slug: str, label: str, content_type: str) -> str | None:
        body = response.content
        if body.startswith(b"%PDF") or "application/pdf" in content_type or response.url.lower().endswith(".pdf"):
            path = paper_dir / "pdf" / f"{slug}.pdf"
            path.write_bytes(body)
            return str(path)
        text = response.text
        stripped = text.lstrip()
        if stripped.startswith("<?xml") or stripped.startswith("<article") or "xml" in content_type:
            path = paper_dir / "xml" / f"{slug}_{self._slug(label)}.xml"
            path.write_text(text, encoding="utf-8")
            return str(path)
        if "text/html" in content_type or self._looks_like_html(stripped):
            return None
        if "text/plain" in content_type or len(text) > 1000:
            path = paper_dir / "text" / f"{slug}_{self._slug(label)}.txt"
            path.write_text(text, encoding="utf-8")
            return str(path)
        return None

    def _clean_doi(self, doi: str | None) -> str | None:
        if not doi:
            return None
        doi = doi.strip()
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        return doi.lower()

    def _slug(self, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme and parsed.path:
            value = parsed.path
        slug = re.sub(r"[^A-Za-z0-9]+", "_", value.lower()).strip("_")
        return slug[:120] or "paper"

    def _looks_like_html(self, text: str) -> bool:
        lowered = text[:200].lower()
        return lowered.startswith("<!doctype html") or lowered.startswith("<html") or "<head" in lowered
