from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cart_autolab.analysis.llm_contribution import write_llm_contribution_summary

OUTPUT_ROOT = ROOT / "outputs" / "reviewer_demo"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run safe reviewer reproducibility demos.")
    parser.add_argument("--force", action="store_true", help="Delete an existing outputs/reviewer_demo directory before running.")
    args = parser.parse_args(argv)

    if OUTPUT_ROOT.exists() and any(OUTPUT_ROOT.iterdir()):
        if not args.force:
            print(f"Refusing to overwrite existing {OUTPUT_ROOT}. Re-run with --force to replace it.", file=sys.stderr)
            return 2
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    runs = [
        ("deterministic", "configs/experiment_cytokine_gpc3_liver_safe_demo.yaml", "run-all", "Deterministic reference mode. No LLM call and no external PhysiCell executable."),
        ("llm_mock", "configs/experiment_cytokine_gpc3_liver_llm_mock.yaml", "run-all", "LLM mock mode using software fixture responses only. Not manuscript evidence."),
        ("ablation", "configs/experiment_cytokine_gpc3_liver_ablation.yaml", "ablation", "Ablation mode comparing deterministic, LLM mock, and hybrid software workflows."),
    ]

    for name, config_rel, command, readme in runs:
        run_dir = OUTPUT_ROOT / name
        config_path = _write_config(config_rel, run_dir, name)
        _run(command, config_path)
        _write_readme(run_dir, readme)

    contribution_summary = write_llm_contribution_summary(OUTPUT_ROOT)
    checklist = _artifact_checklist()
    print("\nReviewer demo artifact checklist:")
    for label, path, exists in checklist:
        status = "OK" if exists else "MISSING"
        print(f"- {status}: {label}: {path}")
    return 0 if all(exists for _, _, exists in checklist) else 1


def _write_config(config_rel: str, run_dir: Path, name: str) -> Path:
    config_path = ROOT / config_rel
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if name == "ablation":
        config.setdefault("ablation", {})["output_dir"] = str(run_dir)
        config["output_dir"] = str(run_dir)
    else:
        config["output_dir"] = str(run_dir)
    out = OUTPUT_ROOT / f"{name}_config.yaml"
    out.write_text(yaml.safe_dump(config), encoding="utf-8")
    return out


def _run(command: str, config_path: Path) -> None:
    cmd = [sys.executable, "-m", "cart_autolab.cli", command, "--config", str(config_path)]
    print("Running:", " ".join(cmd))
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def _write_readme(run_dir: Path, text: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "README.txt").write_text(
        text
        + "\n\nMock records are software fixtures only. They are not real scholarly citations, manuscript evidence, PhysiCell outputs, or wet-lab validation.\n",
        encoding="utf-8",
    )


def _artifact_checklist() -> list[tuple[str, Path, bool]]:
    items = [
        ("deterministic final_report.md", OUTPUT_ROOT / "deterministic" / "final_report.md"),
        ("llm_mock llm_calls.jsonl", OUTPUT_ROOT / "llm_mock" / "llm_calls.jsonl"),
        ("llm_mock agent_outputs", OUTPUT_ROOT / "llm_mock" / "agent_outputs"),
        ("ablation ablation_summary.csv", OUTPUT_ROOT / "ablation" / "ablation_summary.csv"),
        ("ablation ranking_comparison.csv", OUTPUT_ROOT / "ablation" / "ranking_comparison.csv"),
        ("LLM contribution summary", OUTPUT_ROOT / "llm_contribution_summary.csv"),
    ]
    return [(label, path, path.exists()) for label, path in items]


if __name__ == "__main__":
    raise SystemExit(main())
