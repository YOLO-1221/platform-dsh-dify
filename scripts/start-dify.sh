#!/usr/bin/env bash
# Start official Dify (v1.17.1 tree under platform2/dify) via Docker Desktop.
# Console: http://127.0.0.1:5001/install
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKER_BIN="/Applications/Docker.app/Contents/Resources/bin"
if [[ -d "$DOCKER_BIN" ]]; then
  export PATH="$DOCKER_BIN:$PATH"
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found — open Docker Desktop until the engine is running" >&2
  exit 1
fi
cd "$ROOT/dify/docker"
test -f .env || cp .env.example .env
exec docker compose up -d
