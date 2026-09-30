#!/usr/bin/env bash
# Faehrt `test_headers.sh` gegen die ECHTE `deploy/hetzner/Caddyfile` — ohne den
# App-Stack und ohne Eingriff in ein Compose-File.
#
# Warum ueberhaupt: die Security-Header aus F-12 (security-findings.md) waren
# bis hierher nur von Hand belegt. Ein als *Closed* gefuehrter Befund, dessen
# Beleg niemand ausfuehrt, ist derselbe Zustand, den schon die Access-Log-Frist
# hatte. Gleiches Vorbild, gleicher Ort: `test_access_log_rotation.sh` im
# `compose-smoke`-Job, dem einzigen Job mit Docker-Daemon.
#
# Warum Wegwerf-Container und kein Compose-Eintrag: geprueft wird die ANTWORT
# VON CADDY. Alles, was dieser Test auf api./mcp./supabase. assertiert, entsteht
# in der Caddyfile selbst — die Header-Bloecke und `respond @internal … 403`.
# Dafuer braucht es weder API noch Datenbank, nur Caddy und Upstreams, die
# antworten. Ein Caddy im Smoke-Stack waere dauerhafte Stack-Komplexitaet fuer
# einen Test, der zehn Sekunden dauert.
#
# Die Upstreams:
#   * api / auth-gateway / mcp-http — EIN Platzhalter-Caddy mit drei Ports. Er
#     bildet nur die Statuscodes und App-eigenen Header nach, an denen der Test
#     etwas ueber Caddy lernt (401 ohne Anmeldung, 404, ein von der App
#     gesetztes Cache-Control, das Caddy NICHT ueberschreiben darf).
#     `/v1/internal*` beantwortet er absichtlich mit 200 — kommt beim Test 403
#     an, hat CADDY geblockt und nicht das Backend zufaellig nichts angeboten.
#   * web — ein echter nginx mit der echten `apps/web/nginx.conf`, der echten
#     `index.html` und `public/robots.txt`. So prueft der Lauf auch, dass
#     `/robots.txt` als Datei ausgeliefert wird und nicht in den SPA-Fallback
#     faellt. Das nginx-Image steht im Web-Dockerfile (`AS runtime`) und wird
#     dort gelesen, nicht hier geraten.
#
# Was hier NICHT geprueft wird: `/docs`. Dieser Fall prueft die App (FastAPI
# mit `docs_url=None`), nicht Caddy; gegen den Platzhalter waere er
# scheingruen. Er ist deshalb ausdruecklich uebersprungen (`HEADERS_SKIP_DOCS`)
# und bleibt Handlauf im Prod-Smoke. Die Zusage selbst deckt
# `apps/api/tests/test_docs_toggle.py` ab.
#
# Aufruf:
#   bash deploy/hetzner/tests/test_headers_ci.sh
#   CADDY_IMAGE=docker.io/library/caddy:2.11.4-alpine bash deploy/hetzner/tests/test_headers_ci.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CADDYFILE="${SCRIPT_DIR}/../Caddyfile"
HEADERS_SH="${SCRIPT_DIR}/test_headers.sh"
WEB_DIR="${REPO}/apps/web"
CADDY_IMAGE="${CADDY_IMAGE:-docker.io/library/caddy:2.8-alpine}"
HOST_PORT="${HEADERS_HOST_PORT:-18443}"

log()  { printf '\033[1;34m[headers-ci]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[headers-ci:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

[[ -r "${CADDYFILE}" ]]  || fail "Caddyfile nicht gefunden: ${CADDYFILE}"
[[ -r "${HEADERS_SH}" ]] || fail "test_headers.sh nicht gefunden: ${HEADERS_SH}"
for f in nginx.conf index.html public/robots.txt Dockerfile; do
  [[ -r "${WEB_DIR}/${f}" ]] || fail "apps/web/${f} nicht gefunden"
done

NGINX_TAG="$(sed -n 's/^FROM nginx:\([^[:space:]]*\)[[:space:]].*AS runtime.*$/\1/p' "${WEB_DIR}/Dockerfile" | head -1)"
[[ -n "${NGINX_TAG}" ]] || fail "kein nginx-Runtime-Image in apps/web/Dockerfile gefunden"
NGINX_IMAGE="${NGINX_IMAGE:-docker.io/library/nginx:${NGINX_TAG}}"

RUNTIME=""
for candidate in docker podman; do
  command -v "${candidate}" >/dev/null 2>&1 && { RUNTIME="${candidate}"; break; }
done
# Bewusst kein stiller Ruecksprung auf „uebersprungen\": dieser Test existiert,
# WEIL die Header bisher ungeprueft blieben. Ohne Container-Laufzeit hat er
# nichts zu sagen und sagt das laut.
[[ -n "${RUNTIME}" ]] || fail "weder docker noch podman verfuegbar — dieser Test
braucht eine Container-Laufzeit und meldet ihr Fehlen als Fehlschlag, nicht als
stilles Ueberspringen"

SUFFIX="$$"
NET="who2be-headers-${SUFFIX}"
STUB="who2be-headers-stub-${SUFFIX}"
WEB="who2be-headers-web-${SUFFIX}"
PROXY="who2be-headers-caddy-${SUFFIX}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/who2be-headers.XXXXXX")"

cleanup() {
  local status=$?
  if ((status != 0)); then
    printf '\n--- caddy log ---\n' >&2
    "${RUNTIME}" logs "${PROXY}" >&2 2>&1 || true
    printf '\n--- web log ---\n' >&2
    "${RUNTIME}" logs "${WEB}" >&2 2>&1 || true
  fi
  "${RUNTIME}" rm -f "${PROXY}" "${WEB}" "${STUB}" >/dev/null 2>&1 || true
  "${RUNTIME}" network rm "${NET}" >/dev/null 2>&1 || true
  rm -rf "${WORK}" 2>/dev/null || true
  exit "${status}"
}
trap cleanup EXIT

# Platzhalter fuer api:8000, auth-gateway:9999, mcp-http:8765.
cat >"${WORK}/stub.Caddyfile" <<'STUB_CFG'
{
	admin off
	auto_https off
}
:8000 {
	handle /v1/health {
		respond `{"status":"ok"}` 200
	}
	handle /v1/internal* {
		respond "BACKEND-REACHED" 200
	}
	handle /v1/me {
		respond `{"detail":"not authenticated"}` 401
	}
	handle /.well-known/oauth-authorization-server {
		respond `{"issuer":"stub"}` 200
	}
	# Eine Antwort, deren Cache-Control die App SELBST setzt — Caddy darf sie
	# nicht ueberschreiben (`?` im no_store-Snippet).
	handle /v1/stub-app-cache {
		header Cache-Control "private, max-age=60"
		respond `{"ok":true}` 200
	}
	handle {
		respond "not found" 404
	}
}
:9999 {
	respond "not found" 404
}
:8765 {
	handle /.well-known/oauth-protected-resource* {
		header Cache-Control "public, max-age=3600"
		respond `{"resource":"stub"}` 200
	}
	handle /mcp* {
		respond "unauthorized" 401
	}
	handle {
		respond "not found" 404
	}
}
STUB_CFG

# Die nginx.conf includiert die Resolver-Datei, die im echten Image ein
# Entrypoint-Skript schreibt. Hier genuegt eine feste Zeile: der Test loest
# keinen Proxy-Upstream auf, nginx braucht die Datei nur zum Starten.
printf 'resolver 127.0.0.11 valid=10s;\n' >"${WORK}/resolver.conf"
# Im Build-Ergebnis stuende an dieser Stelle das Vite-Bundle; fuer den Test
# reicht ein leerer Platzhalter, damit index.html keinen 404 nachlaedt.
printf '/* test */\n' >"${WORK}/config.js"

log "Laufzeit: ${RUNTIME}, Caddy: ${CADDY_IMAGE}, nginx: ${NGINX_IMAGE}"
"${RUNTIME}" pull "${CADDY_IMAGE}" >/dev/null || fail "Image nicht ladbar: ${CADDY_IMAGE}"
"${RUNTIME}" pull "${NGINX_IMAGE}" >/dev/null || fail "Image nicht ladbar: ${NGINX_IMAGE}"
"${RUNTIME}" network create "${NET}" >/dev/null

"${RUNTIME}" run -d --name "${STUB}" --network "${NET}" \
  --network-alias api --network-alias auth-gateway --network-alias mcp-http \
  -v "${WORK}/stub.Caddyfile:/etc/caddy/Caddyfile:ro" \
  "${CADDY_IMAGE}" >/dev/null || fail "Platzhalter-Upstream startet nicht"

"${RUNTIME}" run -d --name "${WEB}" --network "${NET}" --network-alias web \
  -v "${WEB_DIR}/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "${WORK}/resolver.conf:/etc/nginx/resolver.conf:ro" \
  -v "${WEB_DIR}/index.html:/usr/share/nginx/html/index.html:ro" \
  -v "${WEB_DIR}/public/robots.txt:/usr/share/nginx/html/robots.txt:ro" \
  -v "${WORK}/config.js:/usr/share/nginx/html/config.js:ro" \
  "${NGINX_IMAGE}" >/dev/null || fail "Web-Upstream (nginx) startet nicht"

# DOMAIN=localhost: fuer `*.localhost` stellt Caddy selbstsignierte Zertifikate
# aus dem internen CA aus — kein ACME, kein Netz. Die Caddyfile bleibt dabei
# unveraendert; gesetzt werden nur die Env-Vars, die sie ohnehin erwartet.
"${RUNTIME}" run -d --name "${PROXY}" --network "${NET}" \
  -p "127.0.0.1:${HOST_PORT}:443" \
  --tmpfs /var/log/caddy \
  -e DOMAIN=localhost \
  -e ACME_EMAIL=ci@example.invalid \
  -e VITE_SUPABASE_URL=https://supabase.localhost \
  -v "${CADDYFILE}:/etc/caddy/Caddyfile:ro" \
  "${CADDY_IMAGE}" >/dev/null || fail "Caddy startet nicht"

BASE="https://api.localhost:${HOST_PORT}"
log "warte auf ${BASE}/v1/health"
for _ in $(seq 1 60); do
  if curl -sS -k --resolve "api.localhost:${HOST_PORT}:127.0.0.1" \
      -o /dev/null "${BASE}/v1/health" 2>/dev/null; then
    break
  fi
  sleep 1
done
curl -sS -k --resolve "api.localhost:${HOST_PORT}:127.0.0.1" \
  -o /dev/null "${BASE}/v1/health" \
  || fail "Caddy antwortet nach 60s nicht auf ${BASE}/v1/health"

log "test_headers.sh gegen die echte Caddyfile"
HEADERS_RESOLVE=127.0.0.1 HEADERS_SKIP_DOCS=1 HEADERS_APP_CACHE_PROBE=/v1/stub-app-cache \
  bash "${HEADERS_SH}" "${BASE}"
