#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if git rev-parse --git-dir >/dev/null 2>&1; then
  STAGED_FILES="$(git diff --cached --name-only --diff-filter=ACMR)"
  WORKTREE_FILES="$(git diff --name-only --diff-filter=ACMR)"
  UNTRACKED_FILES="$(git ls-files --others --exclude-standard)"
  CHANGED_FILES="$(printf '%s\n%s\n%s\n' "$STAGED_FILES" "$WORKTREE_FILES" "$UNTRACKED_FILES" | sed '/^$/d' | sort -u)"
else
  CHANGED_FILES="$(find apps ui scripts -type f 2>/dev/null || true)"
fi

if [ -z "$CHANGED_FILES" ]; then
  echo "[code-rules] No changed files to validate."
  exit 0
fi

run_shell_checks() {
  local files
  files="$(printf '%s\n' "$CHANGED_FILES" | grep -E '\.sh$' || true)"
  if [ -z "$files" ]; then
    return
  fi

  echo "[code-rules] Checking shell scripts..."
  while IFS= read -r file; do
    if [ -f "$file" ]; then
      bash -n "$file"
    fi
  done <<< "$files"
}

run_powershell_checks() {
  local files pwsh_cmd
  files="$(printf '%s\n' "$CHANGED_FILES" | grep -E '\.ps1$' || true)"
  if [ -z "$files" ]; then
    return
  fi

  if command -v pwsh >/dev/null 2>&1; then
    pwsh_cmd="pwsh"
  elif command -v powershell >/dev/null 2>&1; then
    pwsh_cmd="powershell"
  else
    echo "[code-rules] Skip PowerShell syntax checks: pwsh/powershell not found."
    return
  fi

  echo "[code-rules] Checking PowerShell scripts..."
  while IFS= read -r file; do
    if [ -f "$file" ]; then
      "$pwsh_cmd" -NoProfile -NonInteractive -Command \
        '$path = $args[0]; [scriptblock]::Create((Get-Content -Raw -LiteralPath $path)) | Out-Null' \
        "$file"
    fi
  done <<< "$files"
}

run_python_checks() {
  local files
  files="$(printf '%s\n' "$CHANGED_FILES" | grep -E '\.py$' || true)"
  if [ -z "$files" ]; then
    return
  fi

  if [ -x .venv/bin/ruff ]; then
    echo "[code-rules] Checking Python with Ruff..."
    # shellcheck disable=SC2086
    .venv/bin/ruff check $files
  else
    echo "[code-rules] Skip Ruff: .venv/bin/ruff not found."
  fi

  if [ -x .venv/bin/python ]; then
    echo "[code-rules] Checking Django settings..."
    export PYTHONPATH="$ROOT_DIR/apps"
    export MAXKB_CONFIG="${MAXKB_CONFIG:-ENV}"
    export MAXKB_CONFIG_TYPE="${MAXKB_CONFIG_TYPE:-ENV}"
    export MAXKB_KNOWLEDGE_ONLY="${MAXKB_KNOWLEDGE_ONLY:-true}"
    export MAXKB_LOG_DIR="${MAXKB_LOG_DIR:-$ROOT_DIR/.local/maxkb/logs}"
    export MAXKB_TMP_DIR="${MAXKB_TMP_DIR:-$ROOT_DIR/.local/maxkb/tmp}"
    export MAXKB_LOCAL_MODEL_PATH="${MAXKB_LOCAL_MODEL_PATH:-$ROOT_DIR/.local/maxkb/model}"
    export GLOBAL_DB_HOST="${GLOBAL_DB_HOST:-127.0.0.1}"
    export GLOBAL_DB_PORT="${GLOBAL_DB_PORT:-5432}"
    export GLOBAL_DB_NAME="${GLOBAL_DB_NAME:-maxkb}"
    export GLOBAL_DB_USER="${GLOBAL_DB_USER:-root}"
    export GLOBAL_DB_PASSWORD="${GLOBAL_DB_PASSWORD:-Password123@postgres}"
    export GLOBAL_REDIS_HOST="${GLOBAL_REDIS_HOST:-127.0.0.1}"
    export GLOBAL_REDIS_PORT="${GLOBAL_REDIS_PORT:-6380}"
    export GLOBAL_REDIS_PASSWORD="${GLOBAL_REDIS_PASSWORD:-Password123@redis}"
    .venv/bin/python apps/manage.py check
  else
    echo "[code-rules] Skip Django check: .venv/bin/python not found."
  fi
}

run_frontend_checks() {
  local ui_files lint_files
  ui_files="$(printf '%s\n' "$CHANGED_FILES" | grep -E '^ui/' || true)"
  if [ -z "$ui_files" ]; then
    return
  fi

  if [ ! -d ui/node_modules ]; then
    echo "[code-rules] Skip frontend checks: ui/node_modules not found."
    return
  fi

  echo "[code-rules] Checking frontend types..."
  (cd ui && npm run type-check)

  lint_files="$(printf '%s\n' "$ui_files" | grep -E '^ui/src/.*\.(ts|tsx|vue)$' | sed 's#^ui/##' || true)"
  if [ -n "$lint_files" ] && [ -x ui/node_modules/.bin/eslint ]; then
    echo "[code-rules] Checking changed frontend files with ESLint..."
    (cd ui && printf '%s\n' "$lint_files" | xargs ./node_modules/.bin/eslint --max-warnings=0)
  fi
}

run_shell_checks
run_powershell_checks
run_python_checks
run_frontend_checks

echo "[code-rules] Validation finished."
