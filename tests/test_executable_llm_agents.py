import json
from pathlib import Path

import yaml

from cart_autolab.orchestrator import AutolabOrchestrator


def _base_config(tmp_path):
    config = yaml.safe_load(Path("configs/experiment_cytokine_gpc3_liver.yaml").read_text(encoding="utf-8"))
    config["output_dir"] = str(tmp_path / "run")
    return config


def _llm_mock_config(tmp_path, evidence_source="llm"):
    config = _base_config(tmp_path)
    config["workflow"]["evidence_source"] = evidence_source
    config["workflow"]["critique_source"] = "deterministic"
    config["llm"] = {
        "provider": "mock",
        "mode": "llm",
        "model": "mock-fixture",
        "temperature": 0,
        "seed": 1729,
        "max_retries": 0,
        "mock_responses": {
            "chunk_evidence_extraction_agent": {
                "paper_id": "fixture-paper",
                "chunk_index": 0,
                "evidence": [
                    {
                        "intervention_name": "IL-15",
                        "car_target": "GPC3",
                        "tumor_model": "liver cancer",
                        "disease_context": "hepatocellular carcinoma",
                        "immune_cell_function_affected": ["persistence", "cytotoxicity"],
                        "proliferation_effect": "increased",
                        "survival_or_persistence_effect": "increased",
                        "cytotoxicity_effect": "increased",
                        "exhaustion_effect": "decreased",
                        "activation_induced_cell_death_effect": "not reported",
                        "cytokine_production_effect": "increased",
                        "tme_remodeling_effect": "mixed",
                        "antigen_density_relevance": "reported in software fixture only",
                        "experimental_model_type": "unknown",
                        "confidence_score": 0.61,
                        "supporting_text": "software fixture span",
                        "citation": {"title": "Fixture metadata only", "doi": "", "pmid": ""},
                    }
                ],
            },
            "hypothesis_generation_agent": {
                "hypotheses": [
                    {
                        "hypothesis_type": "central",
                        "hypothesis": "Software fixture hypothesis for testing artifact routing only.",
                        "candidate_intervention_arms": [
                            {
                                "intervention": "IL-15",
                                "expected_mechanism": "fixture",
                                "supporting_evidence": ["fixture-paper"],
                                "confidence": 0.5,
                                "uncertainty": ["fixture"],
                            }
                        ],
                    }
                ],
                "ranked_candidate_interventions_for_followup": ["IL-15"],
                "papers_to_download_before_parameterization": [],
            },
        },
    }
    return config


def _write_config(tmp_path, config):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def test_default_deterministic_mode_does_not_create_llm_artifacts(tmp_path):
    config_path = _write_config(tmp_path, _base_config(tmp_path))
    orch = AutolabOrchestrator(config_path)
    search = orch.search()
    evidence = orch.extract_evidence(search["included_papers"])

    assert evidence
    assert (orch.run_dir / "extracted_evidence.json").exists()
    assert (orch.run_dir / "extracted_evidence_deterministic.json").exists()
    assert not (orch.run_dir / "extracted_evidence_llm.json").exists()
    assert not (orch.run_dir / "llm_calls.jsonl").exists()


def test_llm_mock_mode_creates_llm_evidence_and_hypothesis_artifacts(tmp_path):
    config_path = _write_config(tmp_path, _llm_mock_config(tmp_path, evidence_source="llm"))
    orch = AutolabOrchestrator(config_path)
    search = orch.search()
    evidence = orch.extract_evidence(search["included_papers"])

    assert evidence
    assert all(row.get("evidence_source") == "llm" for row in evidence)
    assert (orch.run_dir / "extracted_evidence_llm.json").exists()
    assert (orch.run_dir / "hypotheses_llm.json").exists()
    records = [json.loads(line) for line in (orch.run_dir / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {record["agent_name"] for record in records} >= {"chunk_evidence_extraction_agent", "hypothesis_generation_agent"}


def test_hybrid_mode_combines_deterministic_and_llm_evidence(tmp_path):
    config_path = _write_config(tmp_path, _llm_mock_config(tmp_path, evidence_source="hybrid"))
    orch = AutolabOrchestrator(config_path)
    search = orch.search()
    evidence = orch.extract_evidence(search["included_papers"])

    deterministic = json.loads((orch.run_dir / "extracted_evidence_deterministic.json").read_text(encoding="utf-8"))
    llm = json.loads((orch.run_dir / "extracted_evidence_llm.json").read_text(encoding="utf-8"))
    hybrid = json.loads((orch.run_dir / "extracted_evidence_hybrid.json").read_text(encoding="utf-8"))
    assert len(hybrid) == len(deterministic) + len(llm)
    assert evidence == hybrid
    assert any(row.get("evidence_source") == "llm" for row in hybrid)
