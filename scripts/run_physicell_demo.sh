#!/usr/bin/env bash
set -euo pipefail

CONFIG="${CONFIG:-configs/experiment_cytokine_gpc3_liver_physicell.yaml}"

if [[ -z "${PHYSICELL_EXECUTABLE:-}" ]]; then
  echo "PHYSICELL_EXECUTABLE is not set. Build PhysiCell locally and export PHYSICELL_EXECUTABLE=/path/to/executable." >&2
  exit 1
fi

if [[ ! -x "${PHYSICELL_EXECUTABLE}" ]]; then
  echo "PHYSICELL_EXECUTABLE is not executable: ${PHYSICELL_EXECUTABLE}" >&2
  exit 1
fi

cart-autolab simulate --config "${CONFIG}" --simulator physicell
