#!/usr/bin/env bash
# Wird vom CI/CD-Workflow (.github/workflows/deploy.yml) via SSH aufgerufen.
# Argument: ein Commit-SHA, dessen Images bereits auf GHCR liegen.
#
# Edition (Env WHO2BE_EDITION, Default `onprem`):
#   - onprem: ein Compose-File (docker-compose.yml). Zieht who2be-{api,web,mcp}
#     vom SHA und faehrt sie hoch.
#   - cloud:  Basis + Overlay (docker-compose.yml + docker-compose.cloud.yml).
#     Das Overlay zieht api+migrate als fertiges Image aus GHCR
#     (`ghcr.io/luetzey/who2be-api-cloud:<sha>`, Target `runtime-cloud`,
#     Billing-Paket im Artefakt) statt sie auf dem Host zu bauen — Prod laeuft
#     damit auf demselben Artefakt, das CI gebaut und geprueft hat
#     (Entscheidung 2026-09-05, siehe .claude/context/DECISIONS.md). Nur `web`
#     hat keine Cloud-Variante (kein `web-cloud`-Image in der Build-Matrix,
#     ADR-0029) und baut weiterhin lokal (`pull_policy: build` im Overlay).
#     Ist GHCR beim Deploy nicht erreichbar: RUNBOOK.md
#     "Notfallpfad: Registry nicht erreichbar" (Host-Build von Hand).
#
# Schritte:
#   1. Repo auf den uebergebenen SHA wechseln (damit Compose-Files und
#      .env zu den gepullten/gebauten Images passen).
#   2. Image-Tags in deploy/hetzner/.env auf den SHA setzen.
#   3. docker compose pull (Cloud: api+migrate aus GHCR, web weiterhin lokal
#      gebaut) und up -d --wait.
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
    # api+migrate ziehen jetzt who2be-api-cloud aus GHCR (Registry-Pull statt
    # Host-Build). `web` hat weiterhin kein Cloud-Image und traegt
    # `pull_policy: build` im Overlay — der Pull-Versuch dafuer wird von
    # Compose uebersprungen/faellt weich auf den lokalen Build zurueck, der
    # anschliessende `up` baut es wie gewohnt.
    echo "==> Pulling api, migrate, web (cloud)"
    "${COMPOSE[@]}" pull api migrate web
else
    echo "==> Pulling images"
    "${COMPOSE[@]}" pull api web migrate
fi

echo "==> Restart stack"
"${COMPOSE[@]}" up -d --wait --remove-orphans

echo "==> Status"
"${COMPOSE[@]}" ps
