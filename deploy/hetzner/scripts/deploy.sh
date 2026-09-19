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
#   3. Profile bestimmen (siehe unten) und in die Compose-Aufrufe geben.
#   4. docker compose pull (Cloud: api+migrate aus GHCR, web weiterhin lokal
#      gebaut) und up -d --wait.
#   5. Status ausgeben.
#
# Profile (WHO2BE_COMPOSE_PROFILES, kommagetrennt):
#   Services hinter einem Compose-`profiles:` werden von `pull`/`up` NUR
#   angefasst, wenn ihr Profil aktiv ist. `mcp-http` (der Remote-MCP-Server
#   hinter mcp.${DOMAIN}) ist so ein Service. Ohne aktives Profil lief er
#   deshalb weiter auf dem Image, mit dem er beim Bringup von Hand gestartet
#   wurde — waehrend dieses Skript MCP_IMAGE_TAG brav hochzaehlte. Ein Deploy
#   sah gruen aus und aenderte am MCP-Server nichts (#523: der Fix war gemergt,
#   deployed und trotzdem nicht wirksam).
#   Default ist deshalb AUTO: aktiv sind die Profile, deren Container auf dem
#   Host bereits laufen. Ein Deploy aktualisiert damit genau das, was die Box
#   faehrt — er startet nichts Neues und laesst nichts zurueck. Explizit
#   setzbar:
#     WHO2BE_COMPOSE_PROFILES=mcp-http ./deploy.sh <sha>   # erzwingen
#     WHO2BE_COMPOSE_PROFILES= ./deploy.sh <sha>           # keine Profile
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
BASE_COMPOSE_CMD=(docker compose "${COMPOSE_FILES[@]}" --env-file "$ENV_FILE")

# Profile bestimmen. Gesetzte Variable gewinnt (auch leer = bewusst keine);
# ungesetzt heisst AUTO: Profile, deren Container auf dem Host laufen.
#
# Bewusst OHNE `--profile '*'` (das kann erst Compose >= 2.21 und waere auf
# einer aelteren Box ein stiller Rueckfall auf "kein Profil"): die Profile
# kommen aus `config --profiles`, und `config --services` liefert je Profil
# die Basis-Services PLUS dessen eigene — die Differenz sind die Mitglieder.
mapfile -t ALL_PROFILES < <("${BASE_COMPOSE_CMD[@]}" config --profiles 2>/dev/null || true)
mapfile -t BASE_SERVICES < <("${BASE_COMPOSE_CMD[@]}" config --services 2>/dev/null || true)

# Mitglieder eines Profils = seine Services minus die profillosen Basis-Services.
profile_members() {
    local profile="$1" svc
    while IFS= read -r svc; do
        [ -n "$svc" ] || continue
        printf '%s\n' "${BASE_SERVICES[@]}" | grep -qxF "$svc" || printf '%s\n' "$svc"
    done < <("${BASE_COMPOSE_CMD[@]}" --profile "$profile" config --services 2>/dev/null || true)
}

PROFILE_ARGS=()
SELECTED_PROFILES=""
if [ "${WHO2BE_COMPOSE_PROFILES+set}" = "set" ]; then
    SELECTED_PROFILES="$WHO2BE_COMPOSE_PROFILES"
    echo "==> Profiles (explizit): ${SELECTED_PROFILES:-<keine>}"
else
    # Alle Profile aktivieren, nur um zu SEHEN was laeuft — `ps` startet nichts.
    probe_args=()
    for profile in "${ALL_PROFILES[@]}"; do
        [ -n "$profile" ] && probe_args+=(--profile "$profile")
    done
    running="$("${BASE_COMPOSE_CMD[@]}" "${probe_args[@]+"${probe_args[@]}"}" \
        ps --services --status running 2>/dev/null || true)"
    for profile in "${ALL_PROFILES[@]}"; do
        [ -n "$profile" ] || continue
        while IFS= read -r member; do
            [ -n "$member" ] || continue
            if printf '%s\n' "$running" | grep -qxF "$member"; then
                SELECTED_PROFILES="${SELECTED_PROFILES:+${SELECTED_PROFILES},}${profile}"
                break
            fi
        done < <(profile_members "$profile")
    done
    # One-Shot-Services (`backup`, stdio-`mcp`: restart "no") laufen nie
    # dauerhaft und koennen so nicht erkannt werden — das ist richtig so, sie
    # brauchen auch kein `up`.
    echo "==> Profiles (erkannt): ${SELECTED_PROFILES:-<keine>}"
fi

# Profil-Services mit eigenem SHA-Image explizit mitziehen.
PROFILE_PULL=()
if [ -n "$SELECTED_PROFILES" ]; then
    IFS=',' read -r -a _profiles <<< "$SELECTED_PROFILES"
    for profile in "${_profiles[@]}"; do
        [ -n "$profile" ] || continue
        PROFILE_ARGS+=(--profile "$profile")
    done
    if [[ ",${SELECTED_PROFILES}," == *",mcp-http,"* ]]; then
        PROFILE_PULL+=(mcp-http)
    fi
fi

COMPOSE=("${BASE_COMPOSE_CMD[@]}" "${PROFILE_ARGS[@]+"${PROFILE_ARGS[@]}"}")

if [ "$EDITION" = "cloud" ]; then
    # api+migrate ziehen jetzt who2be-api-cloud aus GHCR (Registry-Pull statt
    # Host-Build). `web` hat weiterhin kein Cloud-Image und traegt
    # `pull_policy: build` im Overlay — der Pull-Versuch dafuer wird von
    # Compose uebersprungen/faellt weich auf den lokalen Build zurueck, der
    # anschliessende `up` baut es wie gewohnt.
    echo "==> Pulling api, migrate, web (cloud) ${PROFILE_PULL[*]:-}"
    "${COMPOSE[@]}" pull api migrate web ${PROFILE_PULL[@]+"${PROFILE_PULL[@]}"}
else
    echo "==> Pulling images ${PROFILE_PULL[*]:-}"
    "${COMPOSE[@]}" pull api web migrate ${PROFILE_PULL[@]+"${PROFILE_PULL[@]}"}
fi

echo "==> Restart stack"
"${COMPOSE[@]}" up -d --wait --remove-orphans

echo "==> Status"
"${COMPOSE[@]}" ps
