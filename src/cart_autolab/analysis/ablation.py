from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from cart_autolab.analysis.evidence_metrics import citation_traceability, evidence_coverage_matrix, load_evidence, low_confidence_fraction, schema_valid_rate
from cart_autolab.analysis.ranking_stability import compare_rankings
from cart_autolab.orchestrator import AutolabOrchestrator


def run_ablation(config_path: str | Path) -> dict[str, Any]:
    config_path = Path(config_path)
    base_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    output_root = _resolve_output_root(config_path, base_config)
    output_root.mkdir(parents=True, exist_ok=True)
    run_dirs = {
        "deterministic": output_root / "deterministic",
        "llm": output_root / "llm",
        "hybrid": output_root / "hybrid",
    }

    for mode, run_dir in run_dirs.items():
        mode_config = _mode_config(base_config, mode, run_dir)
        mode_config_path = output_root / f"{mode}_config.yaml"
        mode_config_path.write_text(yaml.safe_dump(mode_config), encoding="utf-8")
        AutolabOrchestrator(mode_config_path).run_all()

    coverage_frames = []
    summary_rows = []
    for mode, run_dir in run_dirs.items():
        evidence = load_evidence(run_dir)
        coverage = evidence_coverage_matrix(evidence, mode)
        coverage_frames.append(coverage)
        summary_rows.append(
            {
                "mode": mode,
                "evidence_coverage": float(coverage["covered"].mean()) if not coverage.empty else 0.0,
                "citation_traceability": citation_traceability(evidence),
                "schema_valid_rate": schema_valid_rate(run_dir),
                "low_confidence_fraction": low_confidence_fraction(evidence),
                "experimental_concordance": _experimental_concordance(base_config),
                "status_label": _status_label(base_config, mode),
            }
        )

    ranking = compare_rankings(run_dirs)
    summary = pd.DataFrame(summary_rows).merge(ranking, on="mode", how="left")
    coverage_matrix = pd.concat(coverage_frames, ignore_index=True)
    summary.to_csv(output_root / "ablation_summary.csv", index=False)
    (output_root / "ablation_summary.json").write_text(json.dumps(summary.to_dict(orient="records"), indent=2), encoding="utf-8")
    coverage_matrix.to_csv(output_root / "evidence_coverage_matrix.csv", index=False)
    ranking.to_csv(output_root / "ranking_comparison.csv", index=False)
    _write_readme(output_root, summary, base_config)
    return {
        "output_dir": str(output_root),
        "summary_csv": str(output_root / "ablation_summary.csv"),
        "summary_json": str(output_root / "ablation_summary.json"),
        "evidence_coverage_matrix": str(output_root / "evidence_coverage_matrix.csv"),
        "ranking_comparison": str(output_root / "ranking_comparison.csv"),
    }


def _resolve_output_root(config_path: Path, config: dict[str, Any]) -> Path:
    configured = Path(config.get("ablation", {}).get("output_dir", "outputs/ablation"))
    if configured.is_absolute():
        return configured
    return config_path.parent.parent / configured


def _mode_config(base_config: dict[str, Any], mode: str, run_dir: Path) -> dict[str, Any]:
    config = copy.deepcopy(base_config)
    config["output_dir"] = str(run_dir)
    config.setdefault("workflow", {})
    config["workflow"]["evidence_source"] = mode
    config["workflow"]["critique_source"] = "deterministic"
    if mode == "deterministic":
        config.setdefault("llm", {})["provider"] = "none"
    else:
        config["llm"] = copy.deepcopy(base_config.get("llm", {}))
        if config["llm"].get("provider") == "none":
            config["llm"]["provider"] = "mock"
        config["llm"].setdefault("mode", "llm")
        config["llm"].setdefault("max_retries", 0)
    return config


def _experimental_concordance(config: dict[str, Any]) -> str:
    validation_csv = config.get("ablation", {}).get("validation_csv")
    if not validation_csv:
        return "not evaluated; user-supplied validation table required"
    return "not evaluated; validation table loading is reserved for user-supplied data review"


def _status_label(config: dict[str, Any], mode: str) -> str:
    if mode == "deterministic":
        return "deterministic reference"
    provider = config.get("llm", {}).get("provider", "mock")
    if provider == "mock":
        return "mock software fixture"
    return "optional live LLM"


def _write_readme(output_root: Path, summary: pd.DataFrame, config: dict[str, Any]) -> None:
    lines = [
        "# LLM Ablation Outputs",
        "",
        "This ablation compares deterministic reference, LLM-agent, and hybrid LLM plus deterministic validation modes.",
        "",
        "Mock records or mock LLM outputs are software fixtures only. They are not manuscript evidence and do not validate the biology.",
        "",
        f"Experimental concordance: {_experimental_concordance(config)}.",
        "",
        "Generated files:",
        "",
        "- `ablation_summary.csv`",
        "- `ablation_summary.json`",
        "- `evidence_coverage_matrix.csv`",
        "- `ranking_comparison.csv`",
        "",
        "Summary:",
        "",
        summary.to_csv(index=False),
    ]
    (output_root / "README.md").write_text("\n".join(lines), encoding="utf-8")
