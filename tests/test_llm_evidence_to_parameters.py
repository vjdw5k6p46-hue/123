import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

from cart_autolab.orchestrator import AutolabOrchestrator
from cart_autolab.parameters.evidence_loader import EvidenceLoader
from cart_autolab.parameters.fingerprint_builder import FingerprintBuilder


def test_deterministic_mode_does_not_require_llm(tmp_path):
    config = {
        "workflow": {"evidence_source": "deterministic"},
        "engineering_variable": "cytokine_payload",
        "candidate_interventions": ["control", "IL-15"],
        "manual_parameter_overrides": {},
    }
    evidence = [
        {
            "intervention_name": "IL-15",
            "proliferation_effect": 0.2,
            "survival_or_persistence_effect": 0.3,
            "cytotoxicity_effect": 0.1,
            "exhaustion_effect": -0.1,
            "activation_induced_cell_death_effect": 0.0,
            "cytokine_production_effect": 0.1,
            "tme_remodeling_effect": 0.0,
            "confidence_score": 0.7,
            "supporting_citation": "deterministic citation",
            "source_paper_id": "paper-1",
            "immune_cell_function_affected": ["persistence"],
        }
    ]
    result = FingerprintBuilder().build(evidence, config, tmp_path)
    il15 = [row for row in result["parameters"] if row["intervention_name"] == "IL-15"][0]

    assert il15["evidence_source"] == "deterministic"
    assert il15["llm_call_ids"] == []
    assert result["rules"]["llm_evidence_used"] is False
    assert result["rules"]["no_fabricated_citations"] is True


def test_mock_llm_evidence_changes_parameter_provenance(tmp_path):
    config = {
        "workflow": {"evidence_source": "llm"},
        "engineering_variable": "cytokine_payload",
        "candidate_interventions": ["control", "IL-15"],
        "manual_parameter_overrides": {},
    }
    evidence = [
        {
            "intervention_name": "IL-15",
            "proliferation_effect": 0.45,
            "survival_or_persistence_effect": 0.45,
            "cytotoxicity_effect": 0.45,
            "exhaustion_effect": -0.45,
            "activation_induced_cell_death_effect": 0.0,
            "cytokine_production_effect": 0.45,
            "tme_remodeling_effect": 0.0,
            "confidence_score": 0.6,
            "supporting_citation": "[MOCK TEST RECORD] Fixture metadata only",
            "source_paper_id": "fixture-paper",
            "immune_cell_function_affected": ["persistence", "cytotoxicity"],
            "evidence_source": "llm",
            "evidence_record_id": "llm:0:fixture-paper",
            "llm_call_ids": ["call-1"],
            "prompt_hashes": ["hash-1"],
        }
    ]
    result = FingerprintBuilder().build(evidence, config, tmp_path)
    il15 = [row for row in result["parameters"] if row["intervention_name"] == "IL-15"][0]

    assert il15["evidence_source"] == "llm"
    assert il15["llm_call_ids"] == ["call-1"]
    assert il15["prompt_hashes"] == ["hash-1"]
    assert "llm:0:fixture-paper" in il15["evidence_record_ids"]
    assert result["rules"]["llm_evidence_used"] is True
    assert il15["supporting_references"] == ["[MOCK TEST RECORD] Fixture metadata only"]


def test_invalid_llm_evidence_is_rejected_or_marked_low_confidence(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    evidence = [
        {
            "intervention_name": "IL-15",
            "confidence_score": 0.9,
            "supporting_citation": "",
            "source_paper_id": "fixture-paper",
            "evidence_source": "llm",
        }
    ]
    (run_dir / "extracted_evidence_llm.json").write_text(json.dumps(evidence), encoding="utf-8")
    config = {"workflow": {"evidence_source": "llm"}}

    loaded = EvidenceLoader().load(run_dir, config)

    assert loaded[0]["confidence_score"] <= 0.4
    assert "missing_supporting_citation" in loaded[0]["low_confidence_flags"]
    assert loaded[0]["supporting_citation"] == "[MISSING CITATION METADATA]"


def test_build_parameters_cli_still_works_with_default_config(tmp_path):
    config = yaml.safe_load(Path("configs/experiment_cytokine_gpc3_liver.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / "run")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "cart_autolab.cli", "build-parameters", "--config", str(config_path)],
        check=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": str(Path.cwd() / "src")},
        text=True,
    )

    assert '"parameters"' in result.stdout
    params = json.loads((tmp_path / "run" / "parameter_fingerprints.json").read_text(encoding="utf-8"))
    assert all("evidence_source" in row for row in params)


def test_mock_llm_config_creates_parameter_fingerprints_with_llm_provenance(tmp_path):
    config = yaml.safe_load(Path("configs/experiment_cytokine_gpc3_liver.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / "run")
    config["workflow"]["evidence_source"] = "llm"
    config["workflow"]["critique_source"] = "deterministic"
    config["llm"] = {
        "provider": "mock",
        "mode": "llm",
        "max_retries": 0,
        "mock_responses": {
            "chunk_evidence_extraction_agent": {
                "evidence": [
                    {
                        "intervention_name": "IL-15",
                        "car_target": "GPC3",
                        "tumor_model": "liver cancer",
                        "disease_context": "hepatocellular carcinoma",
                        "immune_cell_function_affected": ["persistence"],
                        "proliferation_effect": "increased",
                        "survival_or_persistence_effect": "increased",
                        "cytotoxicity_effect": "increased",
                        "exhaustion_effect": "decreased",
                        "activation_induced_cell_death_effect": "not reported",
                        "cytokine_production_effect": "increased",
                        "tme_remodeling_effect": "not reported",
                        "antigen_density_relevance": "software fixture only",
                        "experimental_model_type": "unknown",
                        "confidence_score": 0.6,
                        "supporting_text": "fixture",
                        "citation": {"title": "Fixture metadata only"},
                    }
                ]
            },
            "hypothesis_generation_agent": {
                "hypotheses": [{"hypothesis_type": "central", "hypothesis": "software fixture", "candidate_intervention_arms": []}],
                "ranked_candidate_interventions_for_followup": [],
                "papers_to_download_before_parameterization": [],
            },
        },
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    orch = AutolabOrchestrator(config_path)
    search = orch.search()
    evidence = orch.extract_evidence(search["included_papers"])
    built = orch.build_parameters(evidence)

    il15 = [row for row in built["parameters"] if row["intervention_name"] == "IL-15"][0]
    assert il15["evidence_source"] == "llm"
    assert il15["llm_call_ids"]
    assert il15["prompt_hashes"]
    assert built["rules"]["llm_evidence_used"] is True
