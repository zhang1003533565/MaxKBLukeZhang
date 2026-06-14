#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_DIR="$ROOT_DIR/.local/maxkb"
UI_DIR="$ROOT_DIR/ui"
PIDS=()

log() {
  printf '[dev-all] %s\n' "$*"
}

cleanup() {
  local status=$?

  trap - INT TERM EXIT

  if [ "${#PIDS[@]}" -gt 0 ]; then
    log "Stopping backend, celery, and frontend..."
    for pid in "${PIDS[@]}"; do
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" >/dev/null 2>&1 || true
      fi
    done
    for pid in "${PIDS[@]}"; do
      wait "$pid" >/dev/null 2>&1 || true
    done
  fi

  if [ "${MAXKB_DEV_STOP_DEPS_ON_EXIT:-false}" = "true" ]; then
    log "Stopping Docker dependencies..."
    (cd "$ROOT_DIR" && docker compose -f docker-compose.dev.yml down)
  fi

  exit "$status"
}

wait_for_tcp() {
  local name="$1"
  local host="$2"
  local port="$3"
  local max_attempts="${4:-60}"

  for ((attempt = 1; attempt <= max_attempts; attempt++)); do
    if python3 - "$host" "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
with socket.create_connection((host, port), timeout=1):
    pass
PY
    then
      return 0
    fi
    sleep 1
  done

  echo "$name is not reachable at $host:$port."
  echo "Check container status with:"
  echo "  docker compose -f docker-compose.dev.yml ps"
  echo "  docker logs maxkb-dev-redis"
  echo "  docker logs maxkb-dev-postgres"
  return 1
}

start_process() {
  local name="$1"
  shift

  (
    cd "$ROOT_DIR"
    "$@"
  ) > >(sed -u "s/^/[$name] /") 2>&1 &
  PIDS+=("$!")
}

wait_for_processes() {
  local pid
  local status

  while true; do
    for pid in "${PIDS[@]}"; do
      if ! kill -0 "$pid" >/dev/null 2>&1; then
        status=0
        wait "$pid" || status=$?
        log "A development process exited with code $status."
        return "$status"
      fi
    done
    sleep 1
  done
}

mkdir -p \
  "$LOCAL_DIR/logs" \
  "$LOCAL_DIR/tmp" \
  "$LOCAL_DIR/model/base" \
  "$LOCAL_DIR/model/embedding" \
  "$LOCAL_DIR/sandbox/python-packages"

export MAXKB_CONFIG=ENV
export MAXKB_CONFIG_TYPE=ENV
export MAXKB_VERSION="${MAXKB_VERSION:-dev-source}"
export MAXKB_DEFAULT_PASSWORD="${MAXKB_DEFAULT_PASSWORD:-LiuguangKB@123..}"
export MAXKB_DEBUG="${MAXKB_DEBUG:-true}"
export MAXKB_LOG_LEVEL="${MAXKB_LOG_LEVEL:-DEBUG}"
export MAXKB_KNOWLEDGE_ONLY="${MAXKB_KNOWLEDGE_ONLY:-true}"
export MAXKB_LOG_DIR="${MAXKB_LOG_DIR:-$LOCAL_DIR/logs}"
export MAXKB_TMP_DIR="${MAXKB_TMP_DIR:-$LOCAL_DIR/tmp}"
export HF_HOME="${HF_HOME:-$LOCAL_DIR/model/base}"
export TMPDIR="${TMPDIR:-$LOCAL_DIR/tmp}"

export MAXKB_DB_NAME="${MAXKB_DB_NAME:-maxkb}"
export MAXKB_DB_HOST="${MAXKB_DB_HOST:-127.0.0.1}"
export MAXKB_DB_PORT="${MAXKB_DB_PORT:-5432}"
export MAXKB_DB_USER="${MAXKB_DB_USER:-root}"
export MAXKB_DB_PASSWORD="${MAXKB_DB_PASSWORD:-Password123@postgres}"
export MAXKB_DB_MAX_OVERFLOW="${MAXKB_DB_MAX_OVERFLOW:-80}"

export MAXKB_REDIS_HOST="${MAXKB_REDIS_HOST:-127.0.0.1}"
export MAXKB_REDIS_PORT="${MAXKB_REDIS_PORT:-6379}"
export MAXKB_REDIS_PASSWORD="${MAXKB_REDIS_PASSWORD:-Password123@redis}"
export MAXKB_REDIS_DB="${MAXKB_REDIS_DB:-0}"
export MAXKB_REDIS_MAX_CONNECTIONS="${MAXKB_REDIS_MAX_CONNECTIONS:-100}"

export MAXKB_EMBEDDING_MODEL_PATH="${MAXKB_EMBEDDING_MODEL_PATH:-$LOCAL_DIR/model/embedding}"
export MAXKB_EMBEDDING_MODEL_NAME="${MAXKB_EMBEDDING_MODEL_NAME:-$LOCAL_DIR/model/embedding/disabled-local-embedding}"
export MAXKB_SANDBOX_PYTHON_PACKAGE_PATHS="${MAXKB_SANDBOX_PYTHON_PACKAGE_PATHS:-$ROOT_DIR/.venv/lib/python3.11/site-packages,$LOCAL_DIR/sandbox/python-packages}"

cd "$ROOT_DIR"

log "Starting PostgreSQL and Redis..."
docker compose -f docker-compose.dev.yml up -d --wait

wait_for_tcp "PostgreSQL" "$MAXKB_DB_HOST" "$MAXKB_DB_PORT"
wait_for_tcp "Redis" "$MAXKB_REDIS_HOST" "$MAXKB_REDIS_PORT"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first, then rerun this script."
  echo "Recommended: python3 -m pip install uv"
  exit 1
fi

if [ ! -d "$ROOT_DIR/.venv" ]; then
  log "Creating Python virtual environment..."
  uv venv "$ROOT_DIR/.venv" --python 3.11
fi

source "$ROOT_DIR/.venv/bin/activate"

if [ "${MAXKB_DEV_SKIP_PY_DEPS:-false}" != "true" ]; then
  log "Checking Python dependencies..."
  uv pip install -r pyproject.toml
fi

if [ ! -f "$UI_DIR/env/.env" ]; then
  cp "$UI_DIR/env/.env.example" "$UI_DIR/env/.env"
fi

if [ ! -d "$UI_DIR/node_modules" ]; then
  log "Installing frontend dependencies..."
  (cd "$UI_DIR" && npm install)
fi

trap cleanup INT TERM EXIT

log "Starting backend, celery, and frontend..."
start_process backend python main.py dev web
start_process celery python main.py dev celery
start_process frontend bash -lc 'cd ui && npm run dev'

log "Ready:"
log "  Frontend: http://localhost:3000/admin"
log "  Backend:  http://localhost:8080"
log "Press Ctrl+C to stop app processes."
log "Docker dependencies stay running by default. Use MAXKB_DEV_STOP_DEPS_ON_EXIT=true to stop them on exit."

wait_for_processes
