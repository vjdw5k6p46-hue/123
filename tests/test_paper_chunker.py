import json

from cart_autolab.literature.paper_chunker import PaperChunker


def test_chunker_chunks_text_artifact(tmp_path):
    paper_dir = tmp_path / "papers" / "text"
    paper_dir.mkdir(parents=True)
    text_path = paper_dir / "paper.txt"
    text_path.write_text(("First paragraph about CAR T.\n\nSecond paragraph about IL-15. " * 30), encoding="utf-8")
    manifest = {
        "records": [
            {
                "paper_id": "p1",
                "title": "Paper",
                "doi": "10.test/x",
                "pmid": "1",
                "artifacts": [str(text_path)],
            }
        ]
    }
    (tmp_path / "downloaded_papers_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = PaperChunker(chunk_chars=500, overlap_chars=50).chunk_downloaded_papers(tmp_path)
    assert result["chunk_count"] > 1
    chunks_path = tmp_path / "paper_chunks" / "paper_chunks.jsonl"
    first = json.loads(chunks_path.read_text(encoding="utf-8").splitlines()[0])
    assert first["paper_id"] == "p1"
    assert "CAR T" in first["text"]
