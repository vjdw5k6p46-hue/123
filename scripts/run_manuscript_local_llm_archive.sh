#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python scripts/run_manuscript_local_llm_archive.py "$@"
