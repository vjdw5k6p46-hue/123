from cart_autolab.parameters.fingerprint_builder import FingerprintBuilder


def test_fingerprint_builder_includes_control_and_il15(tmp_path):
    config = {
        "engineering_variable": "cytokine_payload",
        "candidate_interventions": ["control", "IL-15"],
        "manual_parameter_overrides": {},
    }
    evidence = [
        {
            "intervention_name": "IL-15",
            "proliferation_effect": 0.4,
            "survival_or_persistence_effect": 0.4,
            "cytotoxicity_effect": 0.2,
            "exhaustion_effect": -0.1,
            "activation_induced_cell_death_effect": 0.0,
            "cytokine_production_effect": 0.2,
            "tme_remodeling_effect": 0.1,
            "confidence_score": 0.7,
            "supporting_citation": "mock",
            "immune_cell_function_affected": ["persistence"],
        }
    ]
    result = FingerprintBuilder().build(evidence, config, tmp_path)["parameters"]
    names = [r["intervention_name"] for r in result]
    assert names == ["control", "IL-15"]
    il15 = result[1]
    assert il15["survival_enhancement_aS"] > 1
    assert il15["confidence_score"] == 0.7
