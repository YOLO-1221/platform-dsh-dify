#!/usr/bin/env bash
# Local AI stack:
#   Harness bridge   :3081  (platform chat SSE; true `dsh web` keeps :3080)
# Official Dify (docker compose) owns :5001. Set PLATFORM2_START_DIFY_LOCAL=1
# only when that stack is stopped and you want the in-process stub.
# Unmatched chat goes to DeepSeek (no local-llm fallback).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/server/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "missing $PY — create server/.venv and pip install -r server/requirements.txt" >&2
  exit 1
fi
export PLATFORM2_API_BASE="${PLATFORM2_API_BASE:-http://127.0.0.1:8000}"
export PLATFORM2_SERVICE_TOKEN="${PLATFORM2_SERVICE_TOKEN:-platform2-dify-local}"
export PLATFORM2_DIFY_BASE="${PLATFORM2_DIFY_BASE:-http://127.0.0.1:5001}"

DIFY_PID=""
if [[ "${PLATFORM2_START_DIFY_LOCAL:-0}" == "1" ]]; then
  "$PY" -m uvicorn app:app --app-dir "$ROOT/services/dify_local" --host 127.0.0.1 --port 5001 &
  DIFY_PID=$!
fi
"$PY" -m uvicorn app:app --app-dir "$ROOT/services/harness_bridge" --host 127.0.0.1 --port 3081 &
HARNESS_PID=$!
trap 'kill ${DIFY_PID:-} $HARNESS_PID 2>/dev/null || true' INT TERM
if [[ -n "$DIFY_PID" ]]; then
  echo "dify-local pid=$DIFY_PID :5001"
else
  echo "dify: official stack expected at $PLATFORM2_DIFY_BASE (scripts/start-dify.sh)"
fi
echo "harness-bridge pid=$HARNESS_PID :3081 (platform chat; dsh web stays on :3080)"
wait
