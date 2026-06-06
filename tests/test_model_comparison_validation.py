from cart_autolab.analysis.model_comparison_validation import validate_record, validate_records


def _record():
    return {
        "record_id": "r1",
        "model_name": "test-model",
        "paper_id": "pmid:1",
        "chunk_id": "pmid:1:0",
        "chunk_index": 0,
        "title": "IL-15 armored CAR T",
        "doi": "10.1/test",
        "pmid": "1",
        "pmcid": None,
        "cytokine": "IL-15",
        "is_t_cell_self_secreting_or_engineered_secretion": True,
        "secretion_context": "engineered expression",
        "car_target": "GPC3",
        "tumor_context": "liver cancer",
        "endpoint": "persistence",
        "effect_direction": "increased",
        "evidence_strength": "direct",
        "model_type": "in_vivo",
        "supporting_text": "short span",
        "confidence": 0.8,
        "low_confidence_flags": [],
        "citation_provenance_complete": True,
    }


def test_validate_record_accepts_valid_record():
    valid, errors = validate_record(_record())
    assert errors == []
    assert valid["confidence"] == 0.8


def test_validate_record_rejects_invalid_values():
    record = _record()
    record["cytokine"] = "IL-99"
    record["supporting_text"] = "x" * 700
    valid, errors = validate_record(record)
    assert valid is None
    assert any("invalid cytokine" in error for error in errors)
    assert any("supporting_text" in error for error in errors)


def test_validate_records_keeps_failures():
    valid, failures = validate_records([_record(), {"record_id": "bad"}])
    assert len(valid) == 1
    assert len(failures) == 1
