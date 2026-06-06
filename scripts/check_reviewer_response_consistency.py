from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RISKY_PATTERNS = [
    re.compile(r"fully autonomous LLM laboratory", re.IGNORECASE),
    re.compile(r"mock data validate", re.IGNORECASE),
    re.compile(r"mock citations", re.IGNORECASE),
    re.compile(r"PhysiCell outputs generated", re.IGNORECASE),
    re.compile(r"LLM proved", re.IGNORECASE),
    re.compile(r"LLM discovered", re.IGNORECASE),
    re.compile(r"mock.{0,40}(are|as|=)\s+real scholarly citation", re.IGNORECASE | re.DOTALL),
    re.compile(r"fully reproducible live LLM", re.IGNORECASE),
]

REQUIRED_PHRASES = [
    "mock records are software fixtures",
    "not real scholarly citations",
    "LLM-guided, schema-constrained",
    "external PhysiCell",
    "schema validation",
    "prompt-response artifacts",
    "deterministic reference mode",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check reviewer-response docs and demo outputs for risky wording.")
    parser.add_argument("--include-outputs", action="store_true", help="Also scan outputs/reviewer_demo if it exists.")
    args = parser.parse_args(argv)

    files = _candidate_files(include_outputs=args.include_outputs)
    warnings = _risky_phrase_warnings(files)
    missing = _missing_required_phrases(files)

    print("Reviewer response consistency check")
    print(f"Scanned files: {len(files)}")
    print("")

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("Warnings: none")

    print("")
    if missing:
        print("Missing required phrases:")
        for phrase in missing:
            print(f"- {phrase}")
    else:
        print("Missing required phrases: none")

    print("")
    print("This checker reports wording risks only. It does not modify files, manuscript text, outputs, or scientific data.")
    return 0


def _candidate_files(include_outputs: bool) -> list[Path]:
    roots = [ROOT / "README.md", ROOT / "docs", ROOT / "configs"]
    if include_outputs:
        roots.append(ROOT / "outputs" / "reviewer_demo")
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.exists():
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".md", ".txt", ".yaml", ".yml", ".json", ".csv"}:
                    files.append(path)
    return sorted(files)


def _risky_phrase_warnings(files: list[Path]) -> list[str]:
    warnings: list[str] = []
    external_log_exists = (ROOT / "outputs" / "reviewer_demo" / "physicell_external" / "simulation" / "physicell_execution_log.json").exists()
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in RISKY_PATTERNS:
            if pattern.pattern.lower().startswith("physicell outputs generated") and external_log_exists:
                continue
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                warnings.append(f"{path.relative_to(ROOT)}:{line}: risky phrase '{match.group(0)[:80]}'")
    return warnings


def _missing_required_phrases(files: list[Path]) -> list[str]:
    corpus = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in files).lower()
    return [phrase for phrase in REQUIRED_PHRASES if phrase.lower() not in corpus]


if __name__ == "__main__":
    raise SystemExit(main())
