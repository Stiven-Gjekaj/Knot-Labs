#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "Creating .venv"
  python -m venv "$ROOT/.venv"
fi

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$ROOT/.venv/Scripts/python.exe"
fi

"$PY" -m pip install --upgrade pip
if [[ -f "$ROOT/requirements.txt" ]]; then
  "$PY" -m pip install -r "$ROOT/requirements.txt"
fi
echo "Venv ready at .venv"

