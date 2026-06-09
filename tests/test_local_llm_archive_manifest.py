import json
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("run_manuscript_local_llm_archive", ROOT / "scripts" / "run_manuscript_local_llm_archive.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_manifest = MODULE.build_manifest


def test_local_llm_archive_manifest_uses_existing_artifacts_without_endpoint_calls(tmp_path):
    output_dir = tmp_path / "manuscript_local_llm"
    output_dir.mkdir()
    (output_dir / "included_papers.json").write_text(
        json.dumps(
            [
                {
                    "title": "Synthetic metadata record for manifest test",
                    "source_database": "Curated",
                    "doi": "10.1234/synthetic-manifest-test",
                }
            ]
        ),
        encoding="utf-8",
    )
    (output_dir / "llm_calls.jsonl").write_text('{"call_id": "call-1"}\n{"call_id": "call-2"}\n', encoding="utf-8")
    (output_dir / "agent_outputs").mkdir()
    for name in [
        "extracted_evidence_hybrid.json",
        "parameter_fingerprints.json",
        "ranked_interventions.csv",
        "final_report.md",
    ]:
        (output_dir / name).write_text("[]", encoding="utf-8")

    config = {
        "output_dir": str(output_dir),
        "workflow": {"evidence_source": "hybrid", "critique_source": "llm"},
        "literature": {"mode": "curated", "curated_path": "data/manuscript_literature/curated_papers.json"},
        "llm": {
            "provider": "openai_compatible",
            "model": "local-test-model",
            "base_url": "http://127.0.0.1:8000/v1",
            "temperature": 0,
            "seed": 1729,
        },
    }

    manifest = build_manifest(ROOT, ROOT / "configs/experiment_cytokine_gpc3_liver_local_llm.yaml", config, output_dir, ["test warning"])

    assert manifest["repository"] == "vjdw5k6p46-hue/123"
    assert manifest["workflow"]["evidence_source"] == "hybrid"
    assert manifest["workflow"]["critique_source"] == "llm"
    assert manifest["literature_mode"] == "curated"
    assert manifest["number_of_included_papers"] == 1
    assert manifest["number_of_llm_calls"] == 2
    assert manifest["mock_records_used"] is False
    assert manifest["agent_outputs"] is not None
    assert manifest["parameter_fingerprints"] is not None
    assert manifest["warnings"] == ["test warning"]
