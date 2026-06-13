#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${LIUGUANG_KB_ENV_FILE:-$ROOT_DIR/deploy/.env}"
ENV_EXAMPLE="$ROOT_DIR/deploy/.env.example"
COMPOSE_FILE="$ROOT_DIR/deploy/docker-compose.prod.yml"
DEPLOY_MODE="${DEPLOY_MODE:-local}"

log() {
  printf '[liuguang-kb-deploy] %s\n' "$*"
}

usage() {
  cat <<'EOF'
Usage:
  ./scripts/server-deploy.sh [--local|--pull|--restart|--status]

Modes:
  --local    Build image from the current server source, then start services.
  --pull     Pull LIUGUANG_KB_IMAGE from registry, then start services.
  --restart  Restart existing services.
  --status   Show service status.

Environment:
  LIUGUANG_KB_ENV_FILE  Override deploy env file path. Default: deploy/.env
  DEPLOY_MODE       local | pull | restart | status
EOF
}

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 36 | tr -d '\n' | tr '/+' '_-'
  else
    LC_ALL=C tr -dc 'A-Za-z0-9_-' </dev/urandom | head -c 48
  fi
}

set_env_value() {
  local key="$1"
  local value="$2"
  local tmp
  tmp="$(mktemp)"
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    $0 ~ "^" key "=" {
      print key "=" value
      found = 1
      next
    }
    { print }
    END {
      if (found == 0) {
        print key "=" value
      }
    }
  ' "$ENV_FILE" >"$tmp"
  mv "$tmp" "$ENV_FILE"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "$1 is required. Please install it first." >&2
    exit 1
  fi
}

case "${1:-}" in
  --local)
    DEPLOY_MODE=local
    ;;
  --pull)
    DEPLOY_MODE=pull
    ;;
  --restart)
    DEPLOY_MODE=restart
    ;;
  --status)
    DEPLOY_MODE=status
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  "")
    ;;
  *)
    usage
    exit 1
    ;;
esac

require_command docker

mkdir -p "$(dirname "$ENV_FILE")"
if [ ! -f "$ENV_FILE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  log "Created $ENV_FILE."
fi

if grep -q '^POSTGRES_PASSWORD=change-me-postgres$' "$ENV_FILE"; then
  set_env_value POSTGRES_PASSWORD "$(generate_secret)"
fi
if grep -q '^REDIS_PASSWORD=change-me-redis$' "$ENV_FILE"; then
  set_env_value REDIS_PASSWORD "$(generate_secret)"
fi
if grep -q '^MAXKB_SECRET_KEY=change-me-django-secret$' "$ENV_FILE"; then
  set_env_value MAXKB_SECRET_KEY "$(generate_secret)"
fi
if grep -q 'change-me-' "$ENV_FILE"; then
  echo "Please replace all change-me-* values in $ENV_FILE before deploying." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

PROJECT="${LIUGUANG_KB_PROJECT:-liuguang-kb}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -p "$PROJECT")

case "$DEPLOY_MODE" in
  local)
    log "Building image from current source..."
    "${COMPOSE[@]}" build app
    log "Starting services..."
    "${COMPOSE[@]}" up -d --remove-orphans
    ;;
  pull)
    log "Pulling image ${LIUGUANG_KB_IMAGE:-ghcr.io/zhang1003533565/liuguang-kb:latest}..."
    "${COMPOSE[@]}" pull app
    log "Starting services..."
    "${COMPOSE[@]}" up -d --remove-orphans
    ;;
  restart)
    log "Restarting services..."
    "${COMPOSE[@]}" restart
    ;;
  status)
    "${COMPOSE[@]}" ps
    exit 0
    ;;
  *)
    usage
    exit 1
    ;;
esac

log "Deployment finished."
log "Admin URL: http://<server-ip>:${LIUGUANG_KB_PORT:-8080}/admin"
log "Default login: admin / ${MAXKB_DEFAULT_PASSWORD:-LiuguangKB@123..}"
