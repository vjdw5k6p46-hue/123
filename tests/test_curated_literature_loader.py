import json

from cart_autolab.literature.curated_loader import load_curated_papers
from cart_autolab.literature.search_agent import LiteratureSearchAgent


def test_curated_loader_accepts_only_records_with_title_and_provenance(tmp_path):
    curated = tmp_path / "curated_papers.json"
    curated.write_text(
        json.dumps(
            [
                {
                    "title": "CAR-T cytokine engineering in GPC3 liver cancer",
                    "abstract": "CAR-T cytokine engineering metadata for a synthetic loader test.",
                    "doi": "10.1234/synthetic-loader-test",
                },
                {
                    "title": "Missing provenance record",
                    "abstract": "This record should be rejected because provenance is absent.",
                },
                {
                    "abstract": "This record should be rejected because title is absent.",
                    "pmid": "12345678",
                },
            ]
        ),
        encoding="utf-8",
    )

    accepted, rejected = load_curated_papers(curated)

    assert len(accepted) == 1
    assert accepted[0]["curated_validation_status"] == "passed"
    assert accepted[0]["source_database"] == "Curated"
    assert accepted[0]["paper_id"] == "doi:10.1234/synthetic-loader-test"
    assert len(rejected) == 2
    assert all(record["curated_validation_status"] == "rejected" for record in rejected)
    assert any("missing provenance" in " ".join(record["curated_validation_errors"]) for record in rejected)
    assert any("missing required title" in " ".join(record["curated_validation_errors"]) for record in rejected)


def test_curated_search_mode_writes_rejected_records_without_including_them(tmp_path):
    curated = tmp_path / "curated_papers.json"
    curated.write_text(
        json.dumps(
            [
                {
                    "title": "GPC3 CAR-T cytokine engineering for liver cancer",
                    "abstract": "CAR-T cytokine evidence metadata for a synthetic curated-mode test.",
                    "pmid": "23456789",
                },
                {
                    "title": "No provenance",
                    "abstract": "CAR-T cytokine metadata but no provenance.",
                },
            ]
        ),
        encoding="utf-8",
    )
    config = {
        "car_target_antigen": "GPC3",
        "tumor_type": "liver cancer",
        "antigen_density_condition": "low",
        "candidate_interventions": ["control", "IL-15"],
        "engineering_variable": "cytokine_payload",
        "literature": {"mode": "curated", "curated_path": str(curated)},
    }

    result = LiteratureSearchAgent(mode="curated").search(config, tmp_path / "run")

    assert len(result["included_papers"]) == 1
    assert result["included_papers"][0]["source_database"] == "Curated"
    assert result["included_papers"][0]["curated_validation_status"] == "passed"
    assert len(result["excluded_papers"]) == 1
    assert result["excluded_papers"][0]["curated_validation_status"] == "rejected"
