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
#   8) Billing-Route existiert nur in der Cloud-Edition (Issue #451): dieselbe
#      Route antwortet in Cloud, in On-Prem 404 — ohne DB-/Mollie-Kontakt, also
#      auch ohne gesetzten MOLLIE_API_KEY nicht falsch rot
# Beendet mit Exit-Code 0 wenn alles gruen, sonst != 0.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
WEB_URL="${WEB_URL:-http://localhost:5173}"
MCP_URL="${MCP_URL:-http://localhost:8765}"
COMPOSE="${COMPOSE:-docker compose}"
# Steuert Check 7 (Billing-Route): welches Deployment laeuft gerade (spiegelt
# den Compose-Default aus `docker-compose.yml`, WHO2BE_EDITION: ${...:-onprem}).
WHO2BE_EDITION="${WHO2BE_EDITION:-onprem}"

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

# --- 8) Billing-Route: existiert nur in der Cloud-Edition (Issue #451) -------
# Das optionale Cloud-Billing-Paket wird nur gemountet, wenn `WHO2BE_EDITION=
# cloud` UND das Paket installiert ist (`_register_billing_if_present`,
# apps/api/.../main.py) — On-Prem hat die Route schlicht nicht (404). Der
# generische Provider-Webhook (`/v1/billing/webhook`, NICHT der Mollie-
# spezifische Pull-Endpunkt) ist dafuer der richtige Check: ohne Signatur-
# Header schlaegt die Verifikation *fail-closed* fehl, BEVOR ueberhaupt DB
# oder Mollie beruehrt werden (`verify_webhook_signature` — leeres Secret oder
# fehlender Header ⇒ False) — der Check prueft also ausschliesslich, ob die
# Route existiert, nie ob Mollie erreichbar ist; er braucht dafuer weder einen
# gesetzten MOLLIE_API_KEY noch WHO2BE_BILLING_WEBHOOK_SECRET (AC5).
log "Billing-Route (Edition-Gate, WHO2BE_EDITION=${WHO2BE_EDITION})"
BILLING_CODE="$(curl -s -o /dev/null -w '%{http_code}' -X POST "${API_URL}/v1/billing/webhook")"
if [[ "${WHO2BE_EDITION}" == "cloud" ]]; then
  [[ "${BILLING_CODE}" == "400" ]] \
    || fail "Cloud: /v1/billing/webhook sollte 400 sein (fail-closed ohne Signatur), bekam ${BILLING_CODE}"
else
  [[ "${BILLING_CODE}" == "404" ]] \
    || fail "On-Prem: /v1/billing/webhook sollte 404 sein (Billing-Paket nicht gemountet), bekam ${BILLING_CODE}"
fi

# --- 9) GoTrue-Pin + Migrationen (Issue #499, AK 4) --------------------------
# Der Sprung von v2.158.1 auf v2.196.0 zieht 18 Migrationen nach. `compose up
# --wait` scheitert nur, wenn der Stack GAR NICHT hochkommt — eine Migration,
# die warnt statt zu brechen, kaeme durch, und seit v2.190.0 warnt GoTrue auch
# bei unvollstaendiger WebAuthn-Konfiguration, statt abzubrechen. Dieser Check
# macht daraus eine Assertion: das LAUFENDE auth-Image traegt exakt den Tag aus
# `docker-compose.yml`, das Log zeigt den Start und keinen Fatal-/Migrations-
# Fehler. Ohne ihn waere AK 4 ein Log-Blick, den niemand wiederholt.
log "GoTrue-Pin + Migrations-Log"
PINNED_TAG="$(grep -oE 'supabase/gotrue:v[0-9]+\.[0-9]+\.[0-9]+' docker-compose.yml 2>/dev/null | head -n1 || true)"
AUTH_CID="$(${COMPOSE} ps -q auth | head -n1)"
[[ -n "${AUTH_CID}" ]] || fail "Kein laufender auth-Container (docker compose ps -q auth war leer)"
# `docker inspect --format` statt `compose ps --format`: die Go-Template-
# Unterstuetzung von `compose ps` hat sich zwischen Compose-Versionen bewegt,
# `docker inspect` ist stabil.
RUNNING_IMAGE="$(docker inspect --format '{{.Config.Image}}' "${AUTH_CID}")"
echo "  auth-Image: ${RUNNING_IMAGE}"
if [[ -n "${PINNED_TAG}" ]]; then
  [[ "${RUNNING_IMAGE}" == "${PINNED_TAG}" ]] \
    || fail "auth laeuft auf '${RUNNING_IMAGE}', gepinnt ist '${PINNED_TAG}'"
else
  # Kein Root-Compose im aktuellen Verzeichnis (z.B. Smoke gegen einen
  # Deploy-Stack): dann gibt es nichts gegenzuhalten, das Log genuegt.
  log "  kein docker-compose.yml im CWD — Pin-Vergleich uebersprungen"
fi

AUTH_LOG="$(${COMPOSE} logs --no-color auth 2>&1)"
echo "${AUTH_LOG}" | grep -q "GoTrue API started on" \
  || fail "auth-Log zeigt keinen erfolgreichen Start (GoTrue API started on): ${AUTH_LOG}"
# `fatal` ist GoTrues Abbruch-Level; "error running migrations" ist die
# Meldung des Migrations-Runners. Beides darf im Log nicht vorkommen.
if echo "${AUTH_LOG}" | grep -qiE '"level":"fatal"|error running migrations|migration failed'; then
  fail "auth-Log enthaelt einen Fatal-/Migrationsfehler:
$(echo "${AUTH_LOG}" | grep -iE '"level":"fatal"|error running migrations|migration failed')"
fi
# Seit v2.190.0 warnt GoTrue bei unvollstaendiger WebAuthn-RP-Konfiguration nur,
# statt den Start abzubrechen (internal/conf/configuration.go:1328-1331). Der
# Stack kaeme dann healthy und korrekt gepinnt hoch — und der WebAuthn-Faktor
# waere still weg. Kein anderer Job faengt das: `compose up --wait` nicht
# (Container ist gesund), e2e nicht (faehrt TOTP). Deshalb hier.
if echo "${AUTH_LOG}" | grep -qi 'WebAuthn configuration is invalid'; then
  fail "auth-Log meldet eine ungueltige WebAuthn-Konfiguration — der Faktor ist
serverseitig nicht verfuegbar (GOTRUE_WEBAUTHN_RP_ID / _RP_DISPLAY_NAME /
_RP_ORIGINS pruefen):
$(echo "${AUTH_LOG}" | grep -i 'WebAuthn configuration is invalid')"
fi

log "alle Checks gruen ✓"
