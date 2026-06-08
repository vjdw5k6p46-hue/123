import json
import re
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_mock_records_do_not_contain_fake_doi_or_pmid_values():
    paths = [
        ROOT / "data" / "mock_literature" / "mock_papers.json",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "10.0000" not in text
        assert "fake doi" not in text.lower()
        assert "fake pmid" not in text.lower()

    mock_records = json.loads((ROOT / "data" / "mock_literature" / "mock_papers.json").read_text(encoding="utf-8"))
    assert all(record["source_database"] == "Mock" for record in mock_records)
    assert all(record.get("doi") is None for record in mock_records)
    assert all(record.get("pmid") is None for record in mock_records)


def test_reviewer_configs_label_fixtures_and_do_not_require_secrets():
    mock_text = (ROOT / "configs/experiment_cytokine_gpc3_liver_llm_mock.yaml").read_text(encoding="utf-8").lower()
    assert "fixture" in mock_text
    assert "api_key" not in mock_text
    assert "10.0000" not in mock_text

    ablation_text = (ROOT / "configs/experiment_cytokine_gpc3_liver_ablation.yaml").read_text(encoding="utf-8")
    ablation = yaml.safe_load(ablation_text)
    assert ablation["llm"]["provider"] == "none"
    assert "mock-fixture" not in ablation_text


def test_no_large_outputs_or_binaries_are_committed():
    forbidden_suffixes = {".exe", ".dll", ".so", ".o", ".obj"}
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    for rel_text in tracked:
        rel = Path(rel_text)
        path = ROOT / rel
        assert not rel.as_posix().startswith("outputs/") or rel.as_posix() == "outputs/.gitkeep"
        assert path.suffix.lower() not in forbidden_suffixes
        assert path.stat().st_size < 5_000_000


def test_docs_and_configs_avoid_unqualified_overclaiming():
    risky = [
        re.compile(r"fully autonomous LLM laboratory", re.IGNORECASE),
        re.compile(r"mock data validate", re.IGNORECASE),
        re.compile(r"LLM proved", re.IGNORECASE),
        re.compile(r"LLM discovered", re.IGNORECASE),
    ]
    for root_name in ["docs", "configs", "data"]:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in risky:
                assert not pattern.search(text), f"{pattern.pattern} found in {path}"
