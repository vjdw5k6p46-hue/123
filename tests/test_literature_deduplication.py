from cart_autolab.literature.deduplication import deduplicate_papers


def test_deduplicate_by_doi():
    records = [
        {"title": "A", "doi": "10.1/a", "source_database": "PubMed", "abstract": ""},
        {"title": "A duplicate", "doi": "10.1/a", "source_database": "OpenAlex", "abstract": "abstract"},
    ]
    out = deduplicate_papers(records)
    assert len(out) == 1
    assert set(out[0]["source_databases"]) == {"PubMed", "OpenAlex"}
    assert out[0]["abstract"] == "abstract"
