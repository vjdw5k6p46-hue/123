import json

from cart_autolab.analysis.compare_local_llm_models import compare_model_outputs


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _model_dir(root, name, cytokine):
    path = root / name
    record = {"record_id": f"{name}-r1", "cytokine": cytokine, "endpoint": "persistence", "citation_provenance_complete": True}
    _write_jsonl(path / "extracted_chunk_evidence.jsonl", [record])
    _write_jsonl(path / "extracted_chunk_evidence_validated.jsonl", [record])
    _write_jsonl(path / "extraction_failures.jsonl", [])
    (path / "cytokine_fingerprint_aggregated.json").write_text(
        json.dumps({"model_name": name, "cytokines": {cytokine: {"endpoints": {"persistence": {"consensus_effect_direction": "increased"}}}}}),
        encoding="utf-8",
    )
    (path / "physicell_parameter_proposals.json").write_text(
        json.dumps(
            {
                "proposals": [
                    {
                        "cytokine": cytokine,
                        "proposal_status": "supported",
                        "proposed_parameter_changes": {"survival_enhancement_aS": 0.5},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (path / "model_run_manifest.json").write_text(json.dumps({"model_name": name}), encoding="utf-8")
    return path


def test_compare_model_outputs_writes_summary_files(tmp_path):
    qwen = _model_dir(tmp_path, "qwen", "IL-15")
    gemma = _model_dir(tmp_path, "gemma", "IL-12")
    out = compare_model_outputs(qwen, gemma, tmp_path / "comparison")
    assert out["disagreement_case_count"] == 2
    assert (tmp_path / "comparison" / "model_comparison_summary.csv").exists()
    assert (tmp_path / "comparison" / "reviewer_interpretation.md").exists()
