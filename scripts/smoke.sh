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
#   6) MCP-HTTP-Server: 401 + WWW-Authenticate direkt auf :8765 und ueber den
#      Web-Origin, plus die Protected-Resource-Metadata
#   7) Launch-Modus-Konsistenz (Issue #429): mit WHO2BE_LAUNCH_MODE=coming_soon
#      muss GoTrue POST /signup ohnehin mit 422 ablehnen (GOTRUE_DISABLE_SIGNUP)
#      — sonst waere die Hinweisseite nur UI-Kosmetik ohne echte Sperre. Im
#      "open"-Modus (Default) wird NICHT geprobt (kein Probe-User-Anlegen).
# Beendet mit Exit-Code 0 wenn alles gruen, sonst != 0.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
WEB_URL="${WEB_URL:-http://localhost:5173}"
MCP_URL="${MCP_URL:-http://localhost:8765}"
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

# --- 6) MCP-HTTP-Server ------------------------------------------------------
# Der MCP-Server ist der eigentliche Zweck von Who2Be — er muss lokal ohne
# Python-Toolchain laufen. Ohne Bearer antwortet der Streamable-HTTP-Endpunkt
# mit 401 + `WWW-Authenticate` (verifiziert gegen apps/mcp/.../auth.py); genau
# das pruefen wir. Ueber den Web-Origin ist der 401 zugleich der Beweis, dass
# der `^~ /mcp`-Block greift und NICHT der SPA-Fallback (der lieferte 200+HTML).
log "MCP-HTTP direkt (${MCP_URL}/mcp)"
MCP_HEADERS="$(curl -s -D - -o /dev/null "${MCP_URL}/mcp")" || fail "MCP-Server nicht erreichbar"
echo "${MCP_HEADERS}" | grep -q "401" || fail "MCP-Direktaufruf ohne Token lieferte keinen 401: ${MCP_HEADERS}"
echo "${MCP_HEADERS}" | grep -qi "www-authenticate: Bearer" \
  || fail "MCP-401 ohne WWW-Authenticate-Header: ${MCP_HEADERS}"

log "MCP-HTTP ueber den Web-Origin (${WEB_URL}/mcp)"
MCP_CODE="$(curl -s -o /tmp/smoke-mcp.txt -w '%{http_code}' "${WEB_URL}/mcp")"
grep -qi "<title>" /tmp/smoke-mcp.txt \
  && fail "SPA-Fallback statt MCP-Server unter ${WEB_URL}/mcp — der ^~ /mcp-Block fehlt"
[[ "${MCP_CODE}" == "401" ]] || fail "${WEB_URL}/mcp lieferte ${MCP_CODE} statt 401"

PRM="$(curl -fsS "${WEB_URL}/.well-known/oauth-protected-resource/mcp")" \
  || fail "Protected-Resource-Metadata nicht erreichbar"
echo "${PRM}" | grep -q "authorization_servers" || fail "PRM ohne authorization_servers: ${PRM}"

# --- 7) Launch-Modus-Konsistenz (Issue #429) ---------------------------------
# WHO2BE_LAUNCH_MODE=coming_soon schaltet nur die UI ab (/signup zeigt die
# Hinweisseite). Die echte Sperre bleibt GOTRUE_DISABLE_SIGNUP — widersprechen
# sich beide (Modus an, GoTrue-Schalter versehentlich aus), koennte ein
# direkter API-Aufruf trotzdem ein Konto anlegen. Im "open"-Modus (Default)
# wird bewusst uebersprungen: kein Probe-User in einer produktiv laufenden,
# offenen Instanz.
if [[ "${WHO2BE_LAUNCH_MODE:-open}" == "coming_soon" ]]; then
  log "Launch-Modus-Konsistenz (coming_soon ⇒ GoTrue muss signUp mit 422 ablehnen)"
  SIGNUP_HTTP_CODE="$(curl -sS -o /tmp/smoke-signup.json -w '%{http_code}' \
    -X POST "${WEB_URL}/auth/v1/signup" \
    -H "Content-Type: application/json" \
    -d '{"email":"launch-mode-smoke@who2be.invalid","password":"launch-mode-smoke-pw"}')"
  [[ "${SIGNUP_HTTP_CODE}" == "422" ]] \
    || fail "Launch-Modus und GoTrue-Schalter widersprechen sich (POST /signup lieferte ${SIGNUP_HTTP_CODE} statt 422: $(cat /tmp/smoke-signup.json))"
else
  log "Launch-Modus 'open' — Signup-Konsistenz-Probe uebersprungen"
fi

log "alle Checks gruen ✓"
