import importlib.util
import sys
from pathlib import Path


SCRIPTS_DIR = Path.cwd() / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_relevance_gate_penalizes_offtopic_infection_chunk():
    relevance = load_script("filter_autoresearch_relevant_chunks")
    off_topic = {
        "chunk_id": "fixture-covid",
        "title": "Transgenic expression of IL-7 regulates CAR-T cell metabolism",
        "text": "COVID-19 SARS-CoV-2 acute respiratory distress syndrome peripheral monocytes.",
        "word_count": 20,
    }
    on_topic = {
        "chunk_id": "fixture-cart",
        "title": "IL-7 armored CAR-T cells",
        "text": "Engineered CAR-T cells secrete IL-7 and improve T cell proliferation persistence and exhaustion resistance.",
        "word_count": 20,
    }

    off_score, _ = relevance.score_cytokine_chunk(off_topic, "IL-7")
    on_score, _ = relevance.score_cytokine_chunk(on_topic, "IL-7")

    assert off_score == 0
    assert on_score > off_score


def test_effective_fingerprint_audit_detects_base_value_reuse():
    per_cytokine = load_script("run_autoresearch_per_cytokine_fingerprints")
    base_defaults = {"carT_prolif_rate": 0.002, "k_exh": 0.006}
    designs = [
        {
            "cytokine": "IL-15",
            "parameters_to_change": [
                {"physicell_user_parameter": "carT_prolif_rate", "proposed_value": 0.002},
                {"physicell_user_parameter": "k_exh", "proposed_value": 0.003},
            ],
        }
    ]

    audit = per_cytokine._effective_fingerprint_audit("IL-15", designs, base_defaults)

    assert audit["proposed_fingerprint_parameters"] == ["carT_prolif_rate", "k_exh"]
    assert audit["effective_changed_fingerprint_parameters"] == ["k_exh"]


def test_refinement_validator_rejects_unknown_parameter():
    refinement = load_script("run_autoresearch_simulation_refinement")
    parsed = {
        "next_round_parameter_recommendations": [
            {
                "cytokine": "IL-15",
                "physicell_user_parameter": "not_a_parameter",
                "recommended_value": 0.1,
                "confidence": 0.5,
            }
        ]
    }

    validation = refinement.validate_refinement(parsed)

    assert validation["status"] == "failed"
    assert "unsupported parameter" in validation["errors"][0]
