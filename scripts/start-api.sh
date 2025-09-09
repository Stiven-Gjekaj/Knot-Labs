#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$SCRIPT_DIR/../.venv/Scripts/python.exe"
if [[ ! -x "$VENV_PY" ]]; then
  VENV_PY="$SCRIPT_DIR/../.venv/bin/python"
fi
if [[ ! -x "$VENV_PY" ]]; then
  echo ".venv python not found at $VENV_PY" >&2
  exit 1
fi
ENV_FILE="$SCRIPT_DIR/../.env"
"$VENV_PY" -m uvicorn --env-file "$ENV_FILE" api.main:app --reload "$@"

