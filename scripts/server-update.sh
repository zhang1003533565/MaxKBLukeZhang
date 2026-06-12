#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DEPLOY_MODE="${DEPLOY_MODE:-pull}"

exec "$ROOT_DIR/scripts/server-deploy.sh" "$@"
