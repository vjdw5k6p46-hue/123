#!/usr/bin/env bash
set -euo pipefail

if command -v python.exe >/dev/null 2>&1; then
  python.exe scripts/run_reviewer_reproducibility_demo.py "$@"
elif command -v py.exe >/dev/null 2>&1; then
  py.exe -3 scripts/run_reviewer_reproducibility_demo.py "$@"
elif command -v python3 >/dev/null 2>&1; then
  python3 scripts/run_reviewer_reproducibility_demo.py "$@"
elif command -v python >/dev/null 2>&1; then
  python scripts/run_reviewer_reproducibility_demo.py "$@"
elif command -v py >/dev/null 2>&1; then
  py -3 scripts/run_reviewer_reproducibility_demo.py "$@"
else
  echo "No Python interpreter found. Install Python or run scripts/run_reviewer_reproducibility_demo.py directly." >&2
  exit 1
fi
