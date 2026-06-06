from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml


REPOSITORY = "haochennan-ucla/cart-insilico-autolab"
CONFIG_PATH = Path("configs/experiment_cytokine_gpc3_liver_local_llm.yaml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a real local-LLM manuscript archive workflow.")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Local LLM manuscript archive config.")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    config_path = (repo_root / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Required config not found: {config_path}")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    llm_cfg = config.get("llm", {}) or {}
    literature_cfg = config.get("literature", {}) or {}
    base_url = str(llm_cfg.get("base_url") or "").strip()
    api_key_env = str(llm_cfg.get("api_key_env") or "LOCAL_LLM_API_KEY")
    output_dir = resolve_repo_path(repo_root, config.get("output_dir", "outputs/manuscript_local_llm"))
    curated_path = resolve_repo_path(repo_root, literature_cfg.get("curated_path", ""))

    warnings: list[str] = []
    if llm_cfg.get("provider") != "openai_compatible":
        raise SystemExit("Local LLM archive config must use llm.provider=openai_compatible.")
    if not base_url:
        raise SystemExit("Local LLM archive config requires llm.base_url.")
    if not os.getenv(api_key_env):
        raise SystemExit(f"Environment variable {api_key_env} is required. For local endpoints that accept any key, set {api_key_env}=dummy.")
    if not curated_path.exists():
        raise SystemExit(
            f"Curated manuscript literature file not found: {curated_path}. "
            "Create it from data/manuscript_literature/curated_papers.template.json with real metadata and provenance."
        )
    if llm_cfg.get("model") == "local-model-name-here":
        warnings.append("Config still uses model placeholder 'local-model-name-here'; confirm the local endpoint serves this model name.")

    check_base_url_reachable(base_url)
    command = [sys.executable, "-m", "cart_autolab.cli", "run-all", "--config", str(config_path)]
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, cwd=repo_root, check=True)

    manifest = build_manifest(repo_root, config_path, config, output_dir, warnings)
    manifest_path = output_dir / "local_llm_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "run_dir": str(output_dir)}, indent=2))
    return 0


def build_manifest(repo_root: Path, config_path: Path, config: dict, output_dir: Path, warnings: list[str] | None = None) -> dict:
    llm_cfg = config.get("llm", {}) or {}
    workflow_cfg = config.get("workflow", {}) or {}
    literature_cfg = config.get("literature", {}) or {}
    included_path = output_dir / "included_papers.json"
    included_papers = read_json(included_path, [])
    llm_calls_path = output_dir / "llm_calls.jsonl"
    llm_calls = count_jsonl(llm_calls_path)
    mock_records_used = any(str(paper.get("source_database", "")).lower() == "mock" for paper in included_papers if isinstance(paper, dict))
    extracted_candidates = [
        output_dir / "extracted_evidence_hybrid.json",
        output_dir / "extracted_evidence_llm.json",
    ]
    extracted_paths = [str(path) for path in extracted_candidates if path.exists()]
    return {
        "repository": REPOSITORY,
        "branch": git(repo_root, "branch", "--show-current"),
        "commit_hash": git(repo_root, "rev-parse", "HEAD"),
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "local_llm_provider": llm_cfg.get("provider"),
        "model_name": llm_cfg.get("model"),
        "base_url": llm_cfg.get("base_url"),
        "temperature": llm_cfg.get("temperature"),
        "seed": llm_cfg.get("seed"),
        "workflow": {
            "evidence_source": workflow_cfg.get("evidence_source"),
            "critique_source": workflow_cfg.get("critique_source"),
        },
        "literature_mode": literature_cfg.get("mode"),
        "curated_literature_file_path": literature_cfg.get("curated_path"),
        "number_of_included_papers": len(included_papers),
        "number_of_llm_calls": llm_calls,
        "llm_calls_jsonl": str(llm_calls_path) if llm_calls_path.exists() else None,
        "agent_outputs": str(output_dir / "agent_outputs") if (output_dir / "agent_outputs").exists() else None,
        "extracted_evidence_paths": extracted_paths,
        "parameter_fingerprints": str(output_dir / "parameter_fingerprints.json") if (output_dir / "parameter_fingerprints.json").exists() else None,
        "ranked_interventions": str(output_dir / "ranked_interventions.csv") if (output_dir / "ranked_interventions.csv").exists() else None,
        "final_report": str(output_dir / "final_report.md") if (output_dir / "final_report.md").exists() else None,
        "warnings": warnings or [],
        "mock_records_used": mock_records_used,
    }


def check_base_url_reachable(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit(f"Invalid llm.base_url: {base_url}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((parsed.hostname, port), timeout=5):
            return
    except OSError as exc:
        raise SystemExit(f"Local LLM endpoint is not reachable at {parsed.hostname}:{port} from {base_url}: {exc}") from exc


def resolve_repo_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True, check=True)
    return result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
