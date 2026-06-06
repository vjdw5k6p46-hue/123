#!/usr/bin/env bash
set -euo pipefail

PHYSICELL_REPO="${PHYSICELL_REPO:-https://github.com/MathCancer/PhysiCell.git}"
PHYSICELL_COMMIT="${PHYSICELL_COMMIT:-pinned-commit-required}"
PHYSICELL_DIR="${PHYSICELL_DIR:-third_party/PhysiCell}"

if [[ "${PHYSICELL_COMMIT}" == "pinned-commit-required" ]]; then
  echo "Set PHYSICELL_COMMIT to a reviewed upstream PhysiCell commit before setup." >&2
  exit 1
fi

mkdir -p "$(dirname "${PHYSICELL_DIR}")"
if [[ ! -d "${PHYSICELL_DIR}/.git" ]]; then
  git clone "${PHYSICELL_REPO}" "${PHYSICELL_DIR}"
fi

git -C "${PHYSICELL_DIR}" fetch --tags origin
git -C "${PHYSICELL_DIR}" checkout "${PHYSICELL_COMMIT}"

echo "PhysiCell source checked out at ${PHYSICELL_DIR} (${PHYSICELL_COMMIT})."
echo "Do not commit the PhysiCell source tree, compiled binaries, or generated outputs unless explicitly requested."
