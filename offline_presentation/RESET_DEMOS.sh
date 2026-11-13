#!/usr/bin/env bash
set -eu
DEMO_ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
if [ -n "${PRESENTATION_PYTHON:-}" ]; then
  DEMO_PYTHON="$PRESENTATION_PYTHON"
elif [ -x "$DEMO_ROOT/.venv/bin/python" ]; then
  DEMO_PYTHON="$DEMO_ROOT/.venv/bin/python"
else
  DEMO_PYTHON="$(command -v python3 || command -v python)"
fi
exec "$DEMO_PYTHON" "$DEMO_ROOT/manage.py" reset
