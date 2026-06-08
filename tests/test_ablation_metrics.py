import json
from pathlib import Path

import yaml

from cart_autolab.analysis.ablation import run_ablation
from cart_autolab.analysis.evidence_metrics import citation_traceability, evidence_coverage_matrix, low_confidence_fraction


def test_ablation_evidence_metrics():
    evidence = [
        {
            "intervention_name": "IL-15",
            "proliferation_effect": 0.4,
            "survival_or_persistence_effect": 0.4,
            "cytotoxicity_effect": 0.2,
            "exhaustion_effect": -0.2,
            "cytokine_production_effect": 0.3,
            "tme_remodeling_effect": 0.0,
            "activation_induced_cell_death_effect": 0.0,
            "supporting_citation": "Fixture title doi:10.fixture",
            "source_paper_id": "fixture-paper",
            "confidence_score": 0.6,
        },
        {
            "intervention_name": "IL-12",
            "supporting_citation": "",
            "confidence_score": 0.2,
            "low_confidence_flags": ["missing_supporting_citation"],
        },
    ]

    coverage = evidence_coverage_matrix(evidence, "llm")

    assert int(coverage[(coverage["cytokine"] == "IL-15") & (coverage["endpoint"] == "persistence")]["covered"].iloc[0]) == 1
    assert citation_traceability(evidence) == 0.5
    assert low_confidence_fraction(evidence) == 0.5


def test_ablation_runs_without_api_key_or_physicell(tmp_path):
    config = yaml.safe_load(Path("configs/experiment_cytokine_gpc3_liver_ablation.yaml").read_text(encoding="utf-8"))
    config["ablation"]["output_dir"] = str(tmp_path / "ablation")
    config_path = tmp_path / "ablation.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    result = run_ablation(config_path)
    output_dir = Path(result["output_dir"])

    assert (output_dir / "ablation_summary.csv").exists()
    assert (output_dir / "ablation_summary.json").exists()
    assert (output_dir / "evidence_coverage_matrix.csv").exists()
    assert (output_dir / "ranking_comparison.csv").exists()
    assert (output_dir / "README.md").exists()
    for mode in ["deterministic", "llm", "hybrid"]:
        assert (output_dir / mode / "simulation" / "timeseries.csv").exists()
        assert (output_dir / mode / "ranked_interventions.csv").exists()
    summary = json.loads((output_dir / "ablation_summary.json").read_text(encoding="utf-8"))
    assert {row["mode"] for row in summary} == {"deterministic", "llm", "hybrid"}
    assert all(row["top_ranked_intervention"] != "not available" for row in summary)
    deterministic_config = yaml.safe_load((output_dir / "deterministic_config.yaml").read_text(encoding="utf-8"))
    assert "control" not in {item.lower() for item in deterministic_config["candidate_interventions"]}
    deterministic_params = json.loads((output_dir / "deterministic" / "parameter_fingerprints.json").read_text(encoding="utf-8"))
    assert "control" not in {row["intervention_name"].lower() for row in deterministic_params}
    assert all(row["experimental_concordance"] == "not evaluated; user-supplied validation table required" for row in summary)
    assert "software fixtures only" in (output_dir / "README.md").read_text(encoding="utf-8")
