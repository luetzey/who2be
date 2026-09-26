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
# Warum ein Wegwerf-Container und kein Compose-Eintrag: geprueft wird die
# ANTWORT VON CADDY. Alles, was dieser Test assertiert, entsteht in der
# Caddyfile selbst — die Header-Bloecke und `respond @internal … 403`. Dafuer
# braucht es weder API noch Datenbank, nur Caddy und irgendeinen Upstream, der
# antwortet. Ein Caddy im Smoke-Stack waere dauerhafte Stack-Komplexitaet fuer
# einen Test, der zehn Sekunden dauert.
#
# Was hier NICHT geprueft wird: `/docs`. Dieser Fall prueft die App (FastAPI
# mit `docs_url=None`), nicht Caddy; gegen den Platzhalter-Upstream unten waere
# er scheingruen. Er ist deshalb ausdruecklich uebersprungen (`HEADERS_SKIP_DOCS`)
# und bleibt Handlauf im Prod-Smoke. Die Zusage selbst deckt
# `apps/api/tests/test_docs_toggle.py` ab.
#
# Aufruf:
#   bash deploy/hetzner/tests/test_headers_ci.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CADDYFILE="${SCRIPT_DIR}/../Caddyfile"
HEADERS_SH="${SCRIPT_DIR}/test_headers.sh"
CADDY_IMAGE="${CADDY_IMAGE:-docker.io/library/caddy:2.8-alpine}"
HOST_PORT="${HEADERS_HOST_PORT:-18443}"

log()  { printf '\033[1;34m[headers-ci]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[headers-ci:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

[[ -r "${CADDYFILE}" ]]  || fail "Caddyfile nicht gefunden: ${CADDYFILE}"
[[ -r "${HEADERS_SH}" ]] || fail "test_headers.sh nicht gefunden: ${HEADERS_SH}"

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
PROXY="who2be-headers-caddy-${SUFFIX}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/who2be-headers.XXXXXX")"

cleanup() {
  local status=$?
  if ((status != 0)); then
    printf '\n--- caddy log ---\n' >&2
    "${RUNTIME}" logs "${PROXY}" >&2 2>&1 || true
  fi
  "${RUNTIME}" rm -f "${PROXY}" "${STUB}" >/dev/null 2>&1 || true
  "${RUNTIME}" network rm "${NET}" >/dev/null 2>&1 || true
  rm -rf "${WORK}" 2>/dev/null || true
  exit "${status}"
}
trap cleanup EXIT

# Platzhalter-Upstream. Er steht nur da, damit Caddy jemanden zum Weiterreichen
# hat; geprueft wird ausschliesslich, was Caddy der Antwort hinzufuegt.
cat >"${WORK}/stub.Caddyfile" <<'STUB_CFG'
{
	admin off
	auto_https off
}
:8000 {
	respond "stub" 200
}
STUB_CFG

log "Laufzeit: ${RUNTIME}, Image: ${CADDY_IMAGE}"
"${RUNTIME}" pull "${CADDY_IMAGE}" >/dev/null || fail "Image nicht ladbar: ${CADDY_IMAGE}"
"${RUNTIME}" network create "${NET}" >/dev/null

"${RUNTIME}" run -d --name "${STUB}" --network "${NET}" --network-alias api \
  -v "${WORK}/stub.Caddyfile:/etc/caddy/Caddyfile:ro" \
  "${CADDY_IMAGE}" >/dev/null || fail "Platzhalter-Upstream startet nicht"

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
HEADERS_RESOLVE=127.0.0.1 HEADERS_SKIP_DOCS=1 bash "${HEADERS_SH}" "${BASE}"
