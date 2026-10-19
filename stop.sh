#!/usr/bin/env bash
# One-shot stop for platform2: API, web, harness-bridge, dsh web, and Dify compose.
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$ROOT/start.sh" stop
