from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY = "haochennan-ucla/cart-insilico-autolab"
BRANCH = "integration/reviewer-response-stack"
PACKAGE_NAME = "cart_autolab_reviewer_response"
KEY_CHECKSUMS = [
    "logs/pytest.log",
    "logs/reviewer_demo.log",
    "logs/consistency_checker.log",
    "outputs/reviewer_demo/llm_contribution_summary.csv",
    "outputs/reviewer_demo/ablation/ablation_summary.csv",
    "outputs/reviewer_demo/llm_mock/llm_calls.jsonl",
    "outputs/reviewer_demo/replay/llm_calls.jsonl",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the offline reviewer-response release package.")
    parser.add_argument(
        "--github-actions-status",
        choices=["success", "failing", "unknown"],
        default="unknown",
        help="Known GitHub Actions status for the current PR head.",
    )
    parser.add_argument(
        "--github-actions-note",
        default="GitHub Actions status was not checked by this packaging script.",
        help="Human-readable note about GitHub Actions status.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    branch = git(repo_root, "branch", "--show-current")
    if branch != BRANCH:
        raise SystemExit(f"Expected branch {BRANCH}, found {branch!r}.")

    commit = git(repo_root, "rev-parse", "HEAD")
    commit_short = git(repo_root, "rev-parse", "--short", "HEAD")
    generated_at = datetime.now(timezone.utc).isoformat()

    release_root = repo_root / "reviewer_release"
    logs_dir = release_root / "logs"
    package_dir = release_root / PACKAGE_NAME
    dist_dir = repo_root / "dist"
    logs_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    commands = [
        {
            "name": "install",
            "command": [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
            "log": logs_dir / "install.log",
        },
        {
            "name": "pytest",
            "command": [sys.executable, "-m", "pytest"],
            "log": logs_dir / "pytest.log",
        },
        {
            "name": "reviewer_demo",
            "command": ["bash", "scripts/run_reviewer_reproducibility_demo.sh", "--force"],
            "log": logs_dir / "reviewer_demo.log",
        },
        {
            "name": "consistency_checker",
            "command": [sys.executable, "scripts/check_reviewer_response_consistency.py", "--include-outputs"],
            "log": logs_dir / "consistency_checker.log",
        },
    ]

    command_results = []
    for item in commands:
        result = run_logged(repo_root, item["command"], item["log"])
        command_results.append(
            {
                "name": item["name"],
                "command": printable_command(item["command"]),
                "exit_code": result,
                "log": str(item["log"].relative_to(release_root)).replace("\\", "/"),
            }
        )

    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    copy_snapshot(repo_root, package_dir)
    copy_tree(repo_root / "outputs" / "reviewer_demo", package_dir / "outputs" / "reviewer_demo")
    copy_tree(logs_dir, package_dir / "logs")

    local_pytest_passed = exit_code(command_results, "pytest") == 0
    reviewer_demo_passed = exit_code(command_results, "reviewer_demo") == 0
    consistency_checker_passed = exit_code(command_results, "consistency_checker") == 0

    write_package_readme(
        package_dir / "REVIEWER_PACKAGE_README.md",
        commit=commit,
        github_actions_status=args.github_actions_status,
        github_actions_note=args.github_actions_note,
    )
    known_issues = build_known_issues(
        command_results,
        github_actions_status=args.github_actions_status,
        github_actions_note=args.github_actions_note,
    )
    (package_dir / "KNOWN_ISSUES.md").write_text(known_issues, encoding="utf-8")
    (release_root / "KNOWN_ISSUES.md").write_text(known_issues, encoding="utf-8")

    manifest = {
        "repository": REPOSITORY,
        "branch": BRANCH,
        "commit_hash": commit,
        "generated_timestamp": generated_at,
        "commands_run": command_results,
        "pytest_passed_locally": local_pytest_passed,
        "reviewer_demo_passed_locally": reviewer_demo_passed,
        "consistency_checker_passed_locally": consistency_checker_passed,
        "github_actions_status": args.github_actions_status,
        "github_actions_status_known_failing": args.github_actions_status == "failing",
        "github_actions_note": args.github_actions_note,
        "included_outputs": list_included_outputs(package_dir / "outputs" / "reviewer_demo"),
        "checksums_sha256": checksums(package_dir, KEY_CHECKSUMS),
    }
    (package_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    zip_path = dist_dir / f"cart_autolab_reviewer_response_offline_{commit_short}.zip"
    sha_path = dist_dir / f"cart_autolab_reviewer_response_offline_{commit_short}.sha256"
    if zip_path.exists():
        zip_path.unlink()
    if sha_path.exists():
        sha_path.unlink()
    create_zip(package_dir, zip_path)
    digest = sha256(zip_path)
    sha_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")

    print("\nOffline reviewer package created")
    print(f"ZIP: {zip_path}")
    print(f"SHA256: {sha_path}")
    print(f"Package size bytes: {zip_path.stat().st_size}")
    print(
        "Release command to run manually:\n"
        f"gh release create v0.2-reviewer-response-offline {zip_path} "
        "--notes-file docs/reviewer_offline_release_notes.md "
        f"--target {BRANCH}"
    )

    return 0 if all(result["exit_code"] == 0 for result in command_results) else 1


def git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def run_logged(repo_root: Path, command: list[str], log_path: Path) -> int:
    print(f"\nRunning: {printable_command(command)}")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            command,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log.write(line)
    return int(process.wait())


def printable_command(command: list[str]) -> str:
    return " ".join(command)


def exit_code(command_results: list[dict[str, object]], name: str) -> int | None:
    for item in command_results:
        if item["name"] == name:
            return int(item["exit_code"])
    return None


def copy_snapshot(repo_root: Path, package_dir: Path) -> None:
    dirs = [
        "src",
        "configs",
        "scripts",
        "tests",
        "docs",
        ".github",
    ]
    data_subdirs = [
        Path("data") / "mock_literature",
        Path("data") / "llm_replay_example",
    ]
    files = [
        "README.md",
        "pyproject.toml",
        "AGENTS.md",
        "LICENSE",
        ".gitattributes",
    ]
    for directory in dirs:
        source = repo_root / directory
        if source.exists():
            copy_tree(source, package_dir / directory)
    for data_dir in data_subdirs:
        source = repo_root / data_dir
        if source.exists():
            copy_tree(source, package_dir / data_dir)
    for filename in files:
        source = repo_root / filename
        if source.exists():
            target = package_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    shutil.copytree(source, target, ignore=ignore_generated, dirs_exist_ok=True)


def ignore_generated(_directory: str, names: list[str]) -> set[str]:
    ignored = {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
    }
    suffixes = (".pyc", ".pyo", ".pyd", ".exe", ".dll", ".so", ".dylib")
    return {name for name in names if name in ignored or name.endswith(suffixes)}


def write_package_readme(path: Path, *, commit: str, github_actions_status: str, github_actions_note: str) -> None:
    path.write_text(
        f"""# Offline Reviewer Package

This is an offline reviewer package generated from `{BRANCH}` at commit `{commit}`.

Deterministic mode requires no API key. The reviewer-safe demo runs deterministic, LLM mock, replay, and ablation modes without internet access, live LLM credentials, or a compiled PhysiCell executable.

LLM mock and replay artifacts are software fixtures only. Mock records are not real scholarly citations, not wet-lab data, and not manuscript evidence. They exist to exercise the LLM-guided, schema-constrained CAR-T in silico workflow code path offline.

External PhysiCell mode is optional and requires a locally compiled executable configured through `PHYSICELL_EXECUTABLE`. Local PhysiCell cytokine-arm summary artifacts may be included when explicitly present in this package; compiled binaries and large raw output folders are not included.

Real OpenAI-compatible LLM audit artifacts may be included when explicitly present in this package. Mock/replay fixtures remain labeled as software fixtures and are not manuscript evidence.

GitHub Actions status recorded for this package: `{github_actions_status}`.

{github_actions_note}

See `KNOWN_ISSUES.md` for local verification status and remaining limitations. See `MANIFEST.json` for command exit codes and SHA256 checksums.
""",
        encoding="utf-8",
    )


def build_known_issues(
    command_results: list[dict[str, object]],
    *,
    github_actions_status: str,
    github_actions_note: str,
) -> str:
    failures = [item for item in command_results if int(item["exit_code"]) != 0]
    lines = [
        "# Known Issues",
        "",
        f"- GitHub Actions status for the current PR head: `{github_actions_status}`.",
        f"- GitHub Actions note: {github_actions_note}",
        f"- Local pytest status from this package run: {'passed' if exit_code(command_results, 'pytest') == 0 else 'failed'}.",
        f"- Reviewer demo status from this package run: {'passed' if exit_code(command_results, 'reviewer_demo') == 0 else 'failed'}.",
        f"- Consistency checker status from this package run: {'passed' if exit_code(command_results, 'consistency_checker') == 0 else 'failed'}.",
        "- Live LLM execution requires provider credentials and is not required for the offline reviewer package.",
        "- External PhysiCell mode requires a local compiled executable configured through `PHYSICELL_EXECUTABLE`.",
        "- Mock and replay outputs are software fixtures only, not real scholarly citations, manuscript evidence, PhysiCell outputs, or wet-lab data.",
        "- Wet-lab concordance is not evaluated unless the user supplies a validation table.",
    ]
    if failures:
        lines.extend(["", "## Failed Local Commands", ""])
        for item in failures:
            lines.append(f"- `{item['name']}` exited with code `{item['exit_code']}`; see `{item['log']}`.")
    return "\n".join(lines) + "\n"


def list_included_outputs(output_root: Path) -> list[str]:
    if not output_root.exists():
        return []
    return sorted(str(path.relative_to(output_root.parent)).replace("\\", "/") for path in output_root.rglob("*") if path.is_file())


def checksums(package_dir: Path, relative_paths: list[str]) -> dict[str, dict[str, object]]:
    result = {}
    for rel in relative_paths:
        path = package_dir / rel
        result[rel] = {
            "exists": path.exists(),
            "sha256": sha256(path) if path.exists() else None,
        }
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def create_zip(package_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(package_dir.parent))


if __name__ == "__main__":
    raise SystemExit(main())
