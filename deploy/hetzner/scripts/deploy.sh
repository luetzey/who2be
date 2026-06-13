#!/usr/bin/env bash
# Wird vom CI/CD-Workflow (.github/workflows/deploy.yml) via SSH aufgerufen.
# Argument: ein Commit-SHA, dessen Images bereits auf GHCR liegen.
#
# Edition (Env WHO2BE_EDITION, Default `onprem`):
#   - onprem: ein Compose-File (docker-compose.yml). Zieht who2be-{api,web,mcp}
#     vom SHA und faehrt sie hoch.
#   - cloud:  Basis + Overlay (docker-compose.yml + docker-compose.cloud.yml).
#     Das Overlay (PR #181) pinnt `pull_policy: build` + `target: runtime-cloud`
#     fuer api+migrate — der Cloud-API-Build entsteht also auf dem Host aus dem
#     ausgecheckten SHA (das in CI gepushte `who2be-api-cloud:<sha>` dient der
#     Paritaet/Verifikation; das On-Prem-`who2be-api` bleibt unangetastet). `web`
#     hat keine Cloud-Variante und wird wie gewohnt aus GHCR gezogen.
#
# Schritte:
#   1. Repo auf den uebergebenen SHA wechseln (damit Compose-Files und
#      .env zu den gepullten/gebauten Images passen).
#   2. Image-Tags in deploy/hetzner/.env auf den SHA setzen.
#   3. docker compose pull (+ Cloud: lokaler runtime-cloud-Build) und up -d --wait.
#   4. Status ausgeben.
#
# Lokal manuell aufrufbar fuer Rollback:
#   ./deploy.sh <alter-sha>                 # On-Prem
#   WHO2BE_EDITION=cloud ./deploy.sh <sha>  # Cloud
set -euo pipefail

SHA="${1:?Usage: deploy.sh <commit-sha>}"
PROJECT_DIR="${PROJECT_DIR:-/opt/who2be}"
EDITION="${WHO2BE_EDITION:-onprem}"
ENV_FILE="${PROJECT_DIR}/deploy/hetzner/.env"
COMPOSE_DIR="${PROJECT_DIR}/deploy/hetzner/who2be"
BASE_COMPOSE="${COMPOSE_DIR}/docker-compose.yml"
CLOUD_COMPOSE="${COMPOSE_DIR}/docker-compose.cloud.yml"

cd "$PROJECT_DIR"

echo "==> Checkout ${SHA} (edition=${EDITION})"
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

# Compose-Files je Edition zusammenstellen. Cloud zieht das Overlay zusaetzlich.
COMPOSE_FILES=(-f "$BASE_COMPOSE")
if [ "$EDITION" = "cloud" ]; then
    COMPOSE_FILES+=(-f "$CLOUD_COMPOSE")
fi
COMPOSE=(docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE")

if [ "$EDITION" = "cloud" ]; then
    # api+migrate baut das Overlay lokal (pull_policy: build, runtime-cloud).
    # Nur `web` aus GHCR ziehen — es hat keine Cloud-Variante.
    echo "==> Pulling web (cloud)"
    "${COMPOSE[@]}" pull web
else
    echo "==> Pulling images"
    "${COMPOSE[@]}" pull api web migrate
fi

echo "==> Restart stack"
"${COMPOSE[@]}" up -d --wait --remove-orphans

echo "==> Status"
"${COMPOSE[@]}" ps
