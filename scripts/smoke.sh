#!/usr/bin/env bash
# Lokaler Smoke gegen den per `docker compose up -d --wait` gestarteten Stack.
# Faehrt die fuer Phase-0/MS-1 minimal noetigen Checks:
#   1) API /v1/health meldet db:"ok"
#   2) Web /index liefert 200 + <title>
#   3) JWT-authentifizierter API-Aufruf (gen_test_jwt.py) → 200 fuer /v1/me
#      (Top-Level-Endpunkt seit 2.1a-2; validiert Auth + DB ohne Workspace-Seed)
#   4) MCP-Tools (in-process im api-Container) zaehlen die 4 Pflicht-Tools
#   5) Same-Origin-Pfad: /config.js, /v1/health und /auth/v1/health ueber den
#      Web-Origin — das ist der Weg, den der Browser tatsaechlich geht (und der
#      einzige, der auch von einer LAN-IP aus funktioniert)
# Beendet mit Exit-Code 0 wenn alles gruen, sonst != 0.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
WEB_URL="${WEB_URL:-http://localhost:5173}"
COMPOSE="${COMPOSE:-docker compose}"

log() { printf "\033[1;34m[smoke]\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31m[smoke:FAIL]\033[0m %s\n" "$*" >&2; exit 1; }

# --- 1) API health -----------------------------------------------------------
log "API /v1/health"
HEALTH="$(curl -fsS "${API_URL}/v1/health")" || fail "API /v1/health unerreichbar"
echo "${HEALTH}"
echo "${HEALTH}" | grep -q '"db":"ok"' || fail "DB-Status nicht ok: ${HEALTH}"

# --- 2) Web index ------------------------------------------------------------
log "Web /"
WEB="$(curl -fsS "${WEB_URL}/")" || fail "Web / unerreichbar"
echo "${WEB}" | grep -qi "<title>" || fail "Web liefert keinen HTML-<title>"

# --- 3) JWT-authentifizierter API-Aufruf -------------------------------------
# Zielt auf /v1/me, weil Workspace-scoped Routen seit 2.1a-2 eine echte
# Membership erwarten. /v1/me ist Top-Level und liefert fuer einen frisch
# generierten User leere Memberships (default_workspace_id=null) — das genuegt
# als Auth+DB-Smoke ohne Org/Workspace-Seed-Setup im CI.
log "JWT-Smoke (/v1/me)"
if [[ -z "${JWT_SECRET:-}" ]]; then
  if [[ -f .env ]]; then
    JWT_SECRET="$(grep -E '^JWT_SECRET=' .env | head -n1 | cut -d= -f2-)"
  fi
fi
[[ -n "${JWT_SECRET:-}" ]] || fail "JWT_SECRET fehlt (weder env noch .env)"

TOKEN="$(JWT_SECRET="${JWT_SECRET}" python3 scripts/gen_test_jwt.py)"
HTTP_CODE="$(curl -sS -o /tmp/smoke-me.json -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  "${API_URL}/v1/me")"
[[ "${HTTP_CODE}" == "200" ]] || fail "/v1/me lieferte ${HTTP_CODE}: $(cat /tmp/smoke-me.json)"

# --- 4) MCP-Tools ------------------------------------------------------------
log "MCP-Tools (in-process)"
TOOL_COUNT="$(${COMPOSE} exec -T api python -c '
import asyncio
from who2be_mcp.server import mcp
tools = asyncio.run(mcp.list_tools())
names = sorted(t.name for t in tools)
print(",".join(names))
')"
echo "  MCP-Tools: ${TOOL_COUNT}"
for required in ping get_persona list_playbooks fetch_playbook; do
  echo "${TOOL_COUNT}" | tr ',' '\n' | grep -qx "${required}" \
    || fail "MCP-Tool fehlt: ${required} (got: ${TOOL_COUNT})"
done

# --- 5) Same-Origin-Pfad (Browser-Sicht) -------------------------------------
# Der Browser laedt die App vom Web-Origin und spricht API + Auth ueber
# denselben Origin an (apps/web/nginx.conf proxied /v1/ und /auth/v1/). Bricht
# dieser Pfad, ist die App von jeder Adresse ausser localhost:8000 tot — ohne
# dass Schritt 1-3 etwas merken.
log "Same-Origin-Pfad ueber ${WEB_URL}"
CONFIG_JS="$(curl -fsS "${WEB_URL}/config.js")" || fail "/config.js nicht ausgeliefert"
echo "${CONFIG_JS}" | grep -q "__WHO2BE_CONFIG__" \
  || fail "/config.js enthaelt keine Runtime-Config: ${CONFIG_JS}"

PROXY_HEALTH="$(curl -fsS "${WEB_URL}/v1/health")" || fail "API nicht ueber den Web-Origin erreichbar"
echo "${PROXY_HEALTH}" | grep -q '"db":"ok"' || fail "Proxy-Health nicht ok: ${PROXY_HEALTH}"

curl -fsS -o /dev/null "${WEB_URL}/auth/v1/health" \
  || fail "GoTrue nicht ueber den Web-Origin erreichbar (/auth/v1/health)"

log "alle Checks gruen ✓"
