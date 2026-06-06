#!/usr/bin/env bash
set -euo pipefail

PHYSICELL_DIR="${PHYSICELL_DIR:-third_party/PhysiCell}"
PROJECT_DIR="${PROJECT_DIR:-physicell_project}"

if [[ ! -d "${PHYSICELL_DIR}" ]]; then
  echo "PhysiCell source directory not found: ${PHYSICELL_DIR}" >&2
  echo "Run scripts/setup_physicell_submodule.sh with a pinned PHYSICELL_COMMIT first." >&2
  exit 1
fi

if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "Project template directory not found: ${PROJECT_DIR}" >&2
  exit 1
fi

echo "Copy or integrate ${PROJECT_DIR}/custom_modules into your local PhysiCell project, then build with your platform-specific PhysiCell make command."
echo "This script intentionally does not commit or copy compiled binaries into the repository."
