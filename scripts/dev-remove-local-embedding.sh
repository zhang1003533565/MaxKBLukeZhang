#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_ID="42f63a3d-427e-11ef-b3ec-a8a1595801ab"

cd "$ROOT_DIR"

docker compose -f docker-compose.dev.yml exec -T postgres psql -U root -d maxkb <<SQL
UPDATE knowledge
SET embedding_model_id = NULL
WHERE embedding_model_id = '${MODEL_ID}';

DELETE FROM workspace_user_resource_permission
WHERE auth_target_type = 'MODEL'
  AND target::text = '${MODEL_ID}';

DELETE FROM resource_mapping
WHERE target_type = 'MODEL'
  AND target_id = '${MODEL_ID}';

DELETE FROM model
WHERE id = '${MODEL_ID}'
  AND provider = 'model_local_provider';
SQL

echo "Removed the default local embedding model from the development database."
echo "Add an online embedding model in the admin UI before creating or vectorizing knowledge bases."
