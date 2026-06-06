from __future__ import annotations

import hashlib
import shutil
import subprocess
import zipfile
from pathlib import Path


INCLUDE_PATHS = [
    "outputs/manuscript_local_llm",
    "docs/REVIEWER_README.md",
    "docs/llm_agent_workflow.md",
    "docs/rebuttal_to_reviewer_llm_workflow.md",
    "configs/experiment_cytokine_gpc3_liver_local_llm.yaml",
]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    commit_short = git(repo_root, "rev-parse", "--short", "HEAD")
    output_dir = repo_root / "outputs" / "manuscript_local_llm"
    manifest = output_dir / "local_llm_run_manifest.json"
    if not output_dir.exists() or not manifest.exists():
        raise SystemExit(
            "Local LLM manuscript output is missing. Run "
            "`export LOCAL_LLM_API_KEY=dummy && bash scripts/run_manuscript_local_llm_archive.sh` first."
        )

    package_root = repo_root / "reviewer_release" / "cart_autolab_manuscript_local_llm_archive"
    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)
    for rel in INCLUDE_PATHS:
        source = repo_root / rel
        target = package_root / rel
        if source.is_dir():
            shutil.copytree(source, target, ignore=ignore_generated, dirs_exist_ok=True)
        elif source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            raise SystemExit(f"Required archive input missing: {source}")

    dist_dir = repo_root / "dist"
    dist_dir.mkdir(exist_ok=True)
    zip_path = dist_dir / f"cart_autolab_manuscript_local_llm_archive_{commit_short}.zip"
    sha_path = dist_dir / f"cart_autolab_manuscript_local_llm_archive_{commit_short}.sha256"
    if zip_path.exists():
        zip_path.unlink()
    if sha_path.exists():
        sha_path.unlink()
    create_zip(package_root, zip_path)
    digest = sha256(zip_path)
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    print(f"ZIP: {zip_path}")
    print(f"SHA256: {sha_path}")
    return 0


def ignore_generated(_directory: str, names: list[str]) -> set[str]:
    ignored = {"__pycache__", ".pytest_cache"}
    suffixes = (".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".dylib")
    return {name for name in names if name in ignored or name.endswith(suffixes)}


def create_zip(package_root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(package_root.parent))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True, check=True)
    return result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
