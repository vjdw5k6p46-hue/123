import importlib.util
import sys
from pathlib import Path


SCRIPTS_DIR = Path.cwd() / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
spec = importlib.util.spec_from_file_location("run_autoresearch_reasoning_first", SCRIPTS_DIR / "run_autoresearch_reasoning_first.py")
reasoning = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(reasoning)


def test_reasoning_first_validates_selected_changes_without_forcing_complete_table(tmp_path):
    base_config = Path("physicell_project/config/PhysiCell_settings.template.xml")
    parameter_dictionary = reasoning._load_parameter_dictionary(base_config)
    chunks = [
        {
            "chunk_id": "chunk-1",
            "title": "Synthetic fixture metadata for software test",
            "doi": "not-real-test-fixture",
            "pmid": "",
            "text": "Synthetic fixture chunk. Not manuscript evidence.",
        }
    ]
    parsed = {
        "research_question": "Which self-secreting cytokine is best?",
        "cytokine_designs": [
            {
                "cytokine": "IL-15",
                "mechanistic_hypothesis": "IL-15 supports persistence.",
                "mechanisms_considered": ["persistence"],
                "parameters_to_change": [
                    {
                        "physicell_user_parameter": "aux_mode",
                        "proposed_value": "armored",
                        "unit": "dimensionless",
                        "expected_effect_direction": "set_mode",
                        "evidence_chunk_ids": ["chunk-1"],
                        "supporting_citations": [{"title": "Synthetic fixture metadata for software test"}],
                        "rationale": "Software fixture rationale.",
                        "confidence": 0.5,
                        "assumptions": ["fixture only"],
                    },
                    {
                        "physicell_user_parameter": "carT_prolif_rate",
                        "proposed_value": 0.1,
                        "unit": "1/min",
                        "expected_effect_direction": "increase",
                        "evidence_chunk_ids": ["chunk-1"],
                        "supporting_citations": [{"title": "Synthetic fixture metadata for software test"}],
                        "rationale": "Software fixture rationale.",
                        "confidence": 0.5,
                    },
                ],
                "parameters_intentionally_inherited": [
                    {
                        "physicell_user_parameter": "p_kill_CAR_T",
                        "reason": "No direct evidence in this fixture.",
                        "confidence": 0.4,
                    }
                ],
                "unsupported_parameters_not_changed": [
                    {
                        "physicell_user_parameter": "lambda_AICD",
                        "reason": "No direct fixture support.",
                    }
                ],
                "simulation_expectation": "Persistence may improve.",
                "evidence_trace": [{"chunk_id": "chunk-1", "point": "fixture"}],
            }
        ],
    }

    result = reasoning.validate_reasoning_output(parsed, chunks, parameter_dictionary, "call-fixture")
    assert result["validation_report"]["valid_changed_parameter_count"] == 2
    design = result["validated_output"]["cytokine_designs"][0]
    assert {row["physicell_user_parameter"] for row in design["parameters_to_change"]} == {"aux_mode", "carT_prolif_rate"}
    assert design["parameters_intentionally_inherited"][0]["physicell_user_parameter"] == "p_kill_CAR_T"

    export = reasoning.export_reasoned_configs(result["validated_output"], base_config, tmp_path)
    assert len(export["interventions"]) == 1
    config_text = Path(export["interventions"][0]["config_path"]).read_text(encoding="utf-8")
    assert "<aux_mode" in config_text
    assert "armored" in config_text
    assert "<carT_prolif_rate" in config_text
