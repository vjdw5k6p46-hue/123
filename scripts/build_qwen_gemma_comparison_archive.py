from __future__ import annotations

import hashlib
import shutil
import subprocess
import zipfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True, capture_output=True, check=True).stdout.strip()
    required = [
        root / "outputs/model_comparison_qwen_vs_gemma",
        root / "docs/local_llm_model_comparison.md",
        root / "configs/local_llm_qwen.yaml",
        root / "configs/local_llm_gemma.yaml",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing archive inputs: " + ", ".join(missing))
    package = root / "reviewer_release" / "qwen_gemma_chunk_comparison"
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)
    for source in required:
        target = package / source.relative_to(root)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    zip_path = dist / f"qwen_gemma_chunk_comparison_{commit}.zip"
    sha_path = dist / f"qwen_gemma_chunk_comparison_{commit}.sha256"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(package.parent))
    digest = sha256(zip_path)
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    print(f"ZIP: {zip_path}")
    print(f"SHA256: {sha_path}")
    return 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
