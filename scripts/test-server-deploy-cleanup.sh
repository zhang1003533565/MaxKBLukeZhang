#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

BIN_DIR="$TMP_DIR/bin"
CALLS_FILE="$TMP_DIR/docker-calls.log"
mkdir -p "$BIN_DIR"
touch "$CALLS_FILE"

cat >"$BIN_DIR/docker" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$DOCKER_CALLS_FILE"
EOF
chmod +x "$BIN_DIR/docker"

export DOCKER_CALLS_FILE="$CALLS_FILE"
export LIUGUANG_KB_DOCKER_PRUNE_UNTIL=72h
export PATH="$BIN_DIR:$PATH"

"$ROOT_DIR/scripts/server-deploy.sh" --cleanup

grep -Fx 'image prune -af --filter until=72h' "$CALLS_FILE" >/dev/null
grep -Fx 'builder prune -af --filter until=72h' "$CALLS_FILE" >/dev/null
if grep -F -- '--volumes' "$CALLS_FILE" >/dev/null; then
  echo "cleanup must not prune Docker volumes" >&2
  exit 1
fi

HELP_OUTPUT="$("$ROOT_DIR/scripts/server-deploy.sh" --help)"
grep -F -- '--cleanup' <<<"$HELP_OUTPUT" >/dev/null
