#!/usr/bin/env bash
# Wird vom CI/CD-Workflow (.github/workflows/deploy.yml) via SSH aufgerufen.
# Argument: ein Commit-SHA, dessen Images bereits auf GHCR liegen.
#
# Schritte:
#   1. Repo auf den uebergebenen SHA wechseln (damit Compose-Files und
#      .env zu den gepullten Images passen).
#   2. Image-Tags in deploy/hetzner/.env auf den SHA setzen.
#   3. docker compose pull + up -d --wait fuer api, web, migrate.
#   4. Status ausgeben.
#
# Lokal manuell aufrufbar fuer Rollback:
#   ./deploy.sh <alter-sha>
set -euo pipefail

SHA="${1:?Usage: deploy.sh <commit-sha>}"
PROJECT_DIR="${PROJECT_DIR:-/opt/who2be}"
ENV_FILE="${PROJECT_DIR}/deploy/hetzner/.env"
COMPOSE_FILE="${PROJECT_DIR}/deploy/hetzner/who2be/docker-compose.yml"

cd "$PROJECT_DIR"

echo "==> Checkout ${SHA}"
git fetch --quiet origin main
git checkout --quiet "$SHA"

echo "==> Update image tags in ${ENV_FILE}"
for var in API_IMAGE_TAG WEB_IMAGE_TAG MCP_IMAGE_TAG; do
    if grep -q "^${var}=" "$ENV_FILE"; then
        sed -i "s|^${var}=.*|${var}=${SHA}|" "$ENV_FILE"
    else
        echo "${var}=${SHA}" >> "$ENV_FILE"
    fi
done

COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")

echo "==> Pulling images"
"${COMPOSE[@]}" pull api web migrate

echo "==> Restart stack"
"${COMPOSE[@]}" up -d --wait --remove-orphans

echo "==> Status"
"${COMPOSE[@]}" ps
