from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


class PaperChunker:
    """Extract downloaded paper artifacts and create LLM-ready chunks."""

    def __init__(self, chunk_chars: int = 3500, overlap_chars: int = 350):
        if overlap_chars >= chunk_chars:
            raise ValueError("overlap_chars must be smaller than chunk_chars")
        self.chunk_chars = chunk_chars
        self.overlap_chars = overlap_chars

    def chunk_downloaded_papers(self, run_dir: Path) -> dict:
        manifest_path = run_dir / "downloaded_papers_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing download manifest: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = []
        chunks = []
        for record in manifest.get("records", []):
            paper_chunks = []
            for artifact in record.get("artifacts", []):
                path = Path(artifact)
                if not path.is_absolute():
                    path = Path.cwd() / path
                text = self._extract_text(path)
                if not text:
                    continue
                for idx, chunk in enumerate(self._split_text(text)):
                    row = {
                        "chunk_id": f"{record.get('paper_id') or self._slug(record.get('title', 'paper'))}:{idx}",
                        "paper_id": record.get("paper_id"),
                        "title": record.get("title"),
                        "doi": record.get("doi"),
                        "pmid": record.get("pmid"),
                        "artifact_path": str(path),
                        "chunk_index": idx,
                        "text": chunk,
                        "char_count": len(chunk),
                    }
                    chunks.append(row)
                    paper_chunks.append(row["chunk_id"])
            records.append({**record, "chunk_ids": paper_chunks, "chunk_count": len(paper_chunks)})
        output_dir = run_dir / "paper_chunks"
        output_dir.mkdir(parents=True, exist_ok=True)
        chunks_path = output_dir / "paper_chunks.jsonl"
        with chunks_path.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        index = {
            "chunk_chars": self.chunk_chars,
            "overlap_chars": self.overlap_chars,
            "chunk_count": len(chunks),
            "papers": records,
            "chunks_path": str(chunks_path),
        }
        (output_dir / "paper_chunk_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
        return index

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf(path)
        if suffix == ".xml":
            return self._extract_xml(path)
        if suffix in {".txt", ".md"}:
            return self._clean(path.read_text(encoding="utf-8", errors="replace"))
        return ""

    def _extract_pdf(self, path: Path) -> str:
        try:
            import fitz  # type: ignore
        except Exception as exc:
            raise RuntimeError("PDF chunking requires PyMuPDF. Install with `pip install pymupdf`.") from exc
        pages = []
        with fitz.open(str(path)) as doc:
            for i in range(doc.page_count):
                pages.append(doc.load_page(i).get_text("text") or "")
        return self._clean("\n\n".join(pages))

    def _extract_xml(self, path: Path) -> str:
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            root = ET.fromstring(text)
            parts = []
            for elem in root.iter():
                if elem.text and elem.text.strip():
                    parts.append(elem.text.strip())
            return self._clean("\n".join(parts))
        except ET.ParseError:
            return self._clean(re.sub(r"<[^>]+>", " ", text))

    def _split_text(self, text: str) -> list[str]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= self.chunk_chars:
                current = f"{current}\n\n{para}".strip()
                continue
            if current:
                chunks.append(current)
            if len(para) <= self.chunk_chars:
                current = para
            else:
                chunks.extend(self._split_long_text(para))
                current = ""
        if current:
            chunks.append(current)
        if self.overlap_chars <= 0 or len(chunks) <= 1:
            return chunks
        overlapped = []
        previous_tail = ""
        for chunk in chunks:
            combined = f"{previous_tail}\n\n{chunk}".strip() if previous_tail else chunk
            overlapped.append(combined[: self.chunk_chars + self.overlap_chars])
            previous_tail = chunk[-self.overlap_chars:]
        return overlapped

    def _split_long_text(self, text: str) -> list[str]:
        chunks = []
        step = self.chunk_chars - self.overlap_chars
        for start in range(0, len(text), step):
            chunks.append(text[start : start + self.chunk_chars])
        return chunks

    def _clean(self, text: str) -> str:
        text = text.replace("\x00", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _slug(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", value.lower()).strip("_")[:80] or "paper"
