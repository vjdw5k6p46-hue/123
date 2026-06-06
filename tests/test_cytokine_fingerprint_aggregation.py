from cart_autolab.analysis.cytokine_fingerprint_aggregation import aggregate_cytokine_fingerprint


def test_aggregate_cytokine_fingerprint_groups_by_endpoint():
    records = [
        {
            "record_id": "r1",
            "cytokine": "IL-15",
            "endpoint": "persistence",
            "effect_direction": "increased",
            "evidence_strength": "direct",
            "model_type": "in_vivo",
            "confidence": 0.8,
            "citation_provenance_complete": True,
            "low_confidence_flags": [],
            "chunk_id": "c1",
            "title": "A",
            "doi": "10.1/a",
            "pmid": "1",
        },
        {
            "record_id": "r2",
            "cytokine": "IL-15",
            "endpoint": "persistence",
            "effect_direction": "increased",
            "evidence_strength": "review",
            "model_type": "review",
            "confidence": 0.6,
            "citation_provenance_complete": False,
            "low_confidence_flags": ["review"],
            "chunk_id": "c2",
            "title": "B",
        },
    ]
    out = aggregate_cytokine_fingerprint(records, model_name="m")
    endpoint = out["cytokines"]["IL-15"]["endpoints"]["persistence"]
    assert endpoint["number_of_supporting_records"] == 2
    assert endpoint["direct_record_count"] == 1
    assert endpoint["review_record_count"] == 1
    assert endpoint["citation_traceability_fraction"] == 0.5
    assert out["cytokine_ranking"][0]["cytokine"] == "IL-15"
