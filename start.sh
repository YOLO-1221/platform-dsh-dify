#!/usr/bin/env bash
# One-shot start for platform2.
#   ./start.sh          start API, web, harness-bridge, dsh web, and Dify
#   ./stop.sh           stop those processes and Dify compose
#   ./start.sh status   show listeners
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN="$ROOT/.run"
mkdir -p "$RUN"

# Optional local LLM overrides; .run is gitignored.
if [[ -f "$RUN/llm.env" ]]; then
  set -a
  source "$RUN/llm.env"
  set +a
fi

API_PORT="${PLATFORM2_API_PORT:-8000}"
WEB_PORT=5173
DIFY_PORT=5001
BRIDGE_PORT=3081
DSH_PORT=3080

PY="$ROOT/server/.venv/bin/python"
CMD="${1:-start}"

log() { printf '%s\n' "$*"; }
die() { printf 'start.sh: %s\n' "$*" >&2; exit 1; }

port_listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

kill_tree() {
  local pid="$1"
  local child
  [[ -n "$pid" ]] || return 0
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

stop_pidfile() {
  local name="$1"
  local file="$RUN/${name}.pid"
  if [[ ! -f "$file" ]]; then
    log "$name: no pid file"
    return 0
  fi
  local pid
  pid="$(cat "$file")"
  kill_tree "$pid"
  rm -f "$file"
  log "stopped $name (pid $pid)"
}

wait_http() {
  local url="$1"
  local label="$2"
  local i
  for i in $(seq 1 60); do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "$label ready: $url"
      return 0
    fi
    sleep 1
  done
  log "$label did not become ready: $url (see $RUN)"
  return 1
}

ensure_backend_venv() {
  if [[ ! -x "$PY" ]]; then
    log "creating server/.venv and installing requirements"
    python3 -m venv "$ROOT/server/.venv"
    "$PY" -m pip install -r "$ROOT/server/requirements.txt"
  fi
}

ensure_postgres() {
  if "$PY" - <<'PY'
import sys
import psycopg
try:
    psycopg.connect("postgresql://platform2@127.0.0.1:5432/platform2", connect_timeout=3).close()
except Exception as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
PY
  then
    return 0
  fi
  die "PostgreSQL 不可用。需要本机库 platform2、用户 platform2：postgresql://platform2@127.0.0.1:5432/platform2"
}

ensure_web_deps() {
  if [[ ! -d "$ROOT/web/node_modules" ]]; then
    log "pnpm install (web)"
    (cd "$ROOT/web" && pnpm install)
  fi
}

ensure_harness_deps() {
  if [[ ! -f "$ROOT/deepseek-harness/package.json" ]]; then
    die "缺少 deepseek-harness/"
  fi
  if [[ ! -d "$ROOT/deepseek-harness/node_modules" ]]; then
    log "pnpm install (deepseek-harness)"
    (cd "$ROOT/deepseek-harness" && pnpm install)
  fi
}

start_bg() {
  local name="$1"
  local port="$2"
  shift 2
  if port_listening "$port"; then
    log "$name already listening on :$port"
    return 0
  fi
  if [[ -f "$RUN/${name}.pid" ]]; then
    local old
    old="$(cat "$RUN/${name}.pid")"
    if kill -0 "$old" 2>/dev/null; then
      kill_tree "$old"
    fi
    rm -f "$RUN/${name}.pid"
  fi
  log "starting $name on :$port"
  : >"$RUN/${name}.log"
  nohup "$@" >>"$RUN/${name}.log" 2>&1 &
  echo $! >"$RUN/${name}.pid"
  disown || true
  wait_port "$name" "$port" || true
}

wait_port() {
  local name="$1"
  local port="$2"
  local i pid
  for i in $(seq 1 30); do
    if port_listening "$port"; then
      log "$name ready on :$port"
      return 0
    fi
    if [[ -f "$RUN/${name}.pid" ]]; then
      pid="$(cat "$RUN/${name}.pid")"
      if ! kill -0 "$pid" 2>/dev/null; then
        log "$name 进程已退出。最近日志："
        tail -n 40 "$RUN/${name}.log" >&2 || true
        return 1
      fi
    fi
    sleep 1
  done
  log "$name 尚未监听 :$port。最近日志："
  tail -n 40 "$RUN/${name}.log" >&2 || true
  return 1
}

prepare_docker() {
  local docker_bin="/Applications/Docker.app/Contents/Resources/bin"
  if [[ -d "$docker_bin" ]]; then
    export PATH="$docker_bin:$PATH"
  fi
  command -v docker >/dev/null 2>&1
}

docker_ready() {
  prepare_docker || return 1
  docker info >/dev/null 2>&1
}

start_dify() {
  if port_listening "$DIFY_PORT"; then
    log "dify already listening on :$DIFY_PORT"
    return 0
  fi
  if ! prepare_docker; then
    log "跳过 Dify：未找到 docker。安装并打开 Docker Desktop 后重新执行 ./start.sh"
    return 0
  fi
  if ! docker_ready; then
    if [[ -d /Applications/Docker.app ]]; then
      log "Docker 引擎未运行，正在打开 Docker Desktop…"
      open -a Docker || true
      local i
      for i in $(seq 1 60); do
        if docker_ready; then
          break
        fi
        sleep 2
      done
    fi
  fi
  if ! docker_ready; then
    log "跳过 Dify：Docker 引擎仍未就绪。打开 Docker Desktop 后重新执行 ./start.sh"
    return 0
  fi
  log "starting official Dify (docker compose) on :$DIFY_PORT"
  if ! "$ROOT/scripts/start-dify.sh"; then
    log "Dify 启动失败，其余服务不受影响。确认 Docker Desktop 已运行后重新执行 ./start.sh"
  fi
}

start_all() {
  command -v python3 >/dev/null 2>&1 || die "需要 python3"
  command -v pnpm >/dev/null 2>&1 || die "需要 pnpm"
  command -v curl >/dev/null 2>&1 || die "需要 curl"
  command -v lsof >/dev/null 2>&1 || die "需要 lsof"

  ensure_backend_venv
  ensure_postgres
  ensure_web_deps
  ensure_harness_deps

  start_bg backend "$API_PORT" \
    "$PY" -m uvicorn app.main:app --app-dir "$ROOT/server" --host 127.0.0.1 --port "$API_PORT" --reload
  wait_http "http://127.0.0.1:${API_PORT}/health" "backend" || true

  start_bg web "$WEB_PORT" \
    pnpm --dir "$ROOT/web" exec vite --host 127.0.0.1 --port "$WEB_PORT"
  start_bg harness-bridge "$BRIDGE_PORT" \
    env PLATFORM2_API_BASE="http://127.0.0.1:${API_PORT}" \
        PLATFORM2_SERVICE_TOKEN="${PLATFORM2_SERVICE_TOKEN:-platform2-dify-local}" \
        PLATFORM2_DIFY_BASE="${PLATFORM2_DIFY_BASE:-http://127.0.0.1:${DIFY_PORT}}" \
        DSH_HOME="${DSH_HOME:-$ROOT/.dsh-home}" \
    "$PY" -m uvicorn app:app --app-dir "$ROOT/services/harness_bridge" --host 127.0.0.1 --port "$BRIDGE_PORT"
  start_bg dsh "$DSH_PORT" \
    env DSH_HOME="${DSH_HOME:-$ROOT/.dsh-home}" \
    pnpm --dir "$ROOT/deepseek-harness" dsh web

  start_dify

  log ""
  log "前端     http://127.0.0.1:${WEB_PORT}    账号 operator/operator 或 admin/admin"
  log "后端     http://127.0.0.1:${API_PORT}/health"
  log "Dify     http://127.0.0.1:${DIFY_PORT}/install"
  log "对话桥   http://127.0.0.1:${BRIDGE_PORT}  （平台面板 SSE）"
  log "dsh web  http://127.0.0.1:${DSH_PORT}"
  log "日志目录 $RUN"
  log "停止     ./stop.sh"
}

stop_dify() {
  if ! docker_ready; then
    log "跳过 Dify 停止：Docker 引擎未运行"
    return 0
  fi
  if [[ -f "$ROOT/dify/docker/docker-compose.yaml" || -f "$ROOT/dify/docker/docker-compose.yml" ]]; then
    log "stopping Dify compose"
    (cd "$ROOT/dify/docker" && docker compose stop) || log "Dify compose stop failed"
  else
    log "跳过 Dify 停止：compose 文件不存在"
  fi
}

stop_all() {
  stop_pidfile dsh
  stop_pidfile harness-bridge
  stop_pidfile web
  stop_pidfile backend
  stop_dify
}

status_all() {
  local name port
  for pair in "backend:$API_PORT" "web:$WEB_PORT" "dify:$DIFY_PORT" "harness-bridge:$BRIDGE_PORT" "dsh:$DSH_PORT"; do
    name="${pair%%:*}"
    port="${pair##*:}"
    if port_listening "$port"; then
      log "$name :$port listening"
    else
      log "$name :$port down"
    fi
  done
}

case "$CMD" in
  start) start_all ;;
  stop) stop_all ;;
  status) status_all ;;
  *) die "用法: ./start.sh [start|stop|status]" ;;
esac
