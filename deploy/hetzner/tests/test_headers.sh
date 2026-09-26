#!/usr/bin/env bash
# Smoke fuer H5 Caddy-Hardening (F-12):
#   1) Security-Header auf /v1/health (HSTS, XCTO, XFO, Referrer, Permissions,
#      COOP, CSP inkl. object-src/form-action)
#   2) /v1/internal/* → 403 (extern blockt Caddy direkt)
#   3) /docs → 404 wenn WHO2BE_DOCS_PUBLIC=false (Default), sonst 200
#
# Aufruf:
#   bash deploy/hetzner/tests/test_headers.sh https://api.<DOMAIN>
#   DOMAIN=<DOMAIN> bash deploy/hetzner/tests/test_headers.sh
#
# WARUM DIE ADRESSE VOLLSTAENDIG SEIN MUSS (gemessen):
# Geprueft wird die Antwort des Endpunkts selbst, nicht der Weg dorthin.
#   * Auf eine Klartext-Anfrage antwortet Caddy mit einer Weiterleitung. Eine
#     Weiterleitung traegt keine Security-Header — sie ist also keine Antwort,
#     an der sich irgendetwas pruefen liesse. Der Test weist sie ausdruecklich
#     ab, statt sie fuer ein Ergebnis zu halten.
#   * Ein `Host:`-Header setzt keine TLS-SNI. Ohne SNI findet Caddy keinen
#     Site-Block und bricht die Verbindung auf TLS-Ebene ab.
# Deshalb laeuft der Test gegen den echten Hostnamen in der URL. Wo der Name
# nicht im DNS steht (CI, lokaler Wegwerf-Stack), loest `HEADERS_RESOLVE` ihn
# auf — SNI und `Host` bleiben korrekt.
#
# Steuerung ueber Env:
#   HEADERS_RESOLVE=127.0.0.1   curl --resolve <host>:<port>:<addr>
#   HEADERS_SKIP_DOCS=1         /docs-Fall ueberspringen (s. u.)
#   WHO2BE_DOCS_PUBLIC=true     /docs-Fall erwartet 200 statt 404
#
# `-k` toleriert das selbstsignierte Zertifikat lokaler Setups; in Prod hat
# Caddy ein gueltiges LE-Cert.
set -euo pipefail

if [[ $# -ge 1 ]]; then
  BASE="$1"
elif [[ -n "${DOMAIN:-}" ]]; then
  BASE="https://api.${DOMAIN}"
else
  BASE="https://api.localhost"
fi

# Bilanz. Ein Lauf ohne eine einzige ausgefuehrte Pruefung ist ein Fehlschlag,
# kein Erfolg — siehe Schlussblock. Genau dieser Fall lag vor, solange der
# Default in die Weiterleitung lief.
CHECKS_RUN=0
CHECKS_SKIPPED=0

log()  { printf '\033[1;34m[headers]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[headers:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }
ok()   { CHECKS_RUN=$((CHECKS_RUN + 1)); printf '  ✓ %s\n' "$*"; }
skip() { CHECKS_SKIPPED=$((CHECKS_SKIPPED + 1)); printf '  ~ SKIP %s\n' "$*"; }

# Host und Port aus BASE ziehen, damit --resolve das richtige Paar bekommt.
_rest="${BASE#*://}"
_scheme="${BASE%%://*}"
HOSTPORT="${_rest%%/*}"
HOST="${HOSTPORT%%:*}"
if [[ "${HOSTPORT}" == *:* ]]; then
  PORT="${HOSTPORT##*:}"
elif [[ "${_scheme}" == "http" ]]; then
  PORT=80
else
  PORT=443
fi

CURL_OPTS=(-sS -k)
if [[ -n "${HEADERS_RESOLVE:-}" ]]; then
  CURL_OPTS+=(--resolve "${HOST}:${PORT}:${HEADERS_RESOLVE}")
fi

curl_h()    { curl "${CURL_OPTS[@]}" -I "${BASE}$1"; }
curl_code() { curl "${CURL_OPTS[@]}" -o /dev/null -w '%{http_code}' "${BASE}$1"; }

# --- 1) Security-Header --------------------------------------------------
log "GET ${BASE}/v1/health (Security-Header)"
hdrs="$(curl_h /v1/health)" || fail "/v1/health unerreichbar (${BASE})"

# Eine Weiterleitung ist keine Antwort: sie traegt keine Security-Header, und
# ein Test, der sie stillschweigend annimmt, prueft nichts. Deshalb hier hart.
status_line="$(printf '%s' "${hdrs}" | head -n 1)"
if [[ "${status_line}" =~ [[:space:]]3[0-9][0-9][[:space:]] ]]; then
  fail "Antwort ist eine Weiterleitung (${status_line%$'\r'}) — eine Weiterleitung
traegt keine Security-Header. Die Adresse muss den Endpunkt direkt treffen
(https + echter Hostname), nicht dessen Klartext-Vorstufe."
fi

assert_header() {
  local name="$1"
  local pattern="$2"
  echo "${hdrs}" | grep -i "^${name}:" | grep -qi "${pattern}" \
    || fail "Header fehlt oder falsch: ${name} (erwarte: ${pattern})"
  ok "${name}: ${pattern}"
}

assert_header "Strict-Transport-Security" "max-age=31536000"
assert_header "X-Content-Type-Options"    "nosniff"
assert_header "X-Frame-Options"           "DENY"
assert_header "Referrer-Policy"           "no-referrer"
assert_header "Permissions-Policy"        "accelerometer"
assert_header "Cross-Origin-Opener-Policy" "same-origin"
assert_header "Content-Security-Policy"   "default-src"
assert_header "Content-Security-Policy"   "object-src 'none'"
assert_header "Content-Security-Policy"   "form-action"

# --- 2) /v1/internal/* Block ---------------------------------------------
log "GET ${BASE}/v1/internal/foo (erwartet 403)"
code="$(curl_code /v1/internal/foo)"
[[ "${code}" == "403" ]] || fail "/v1/internal/foo → ${code}, erwartet 403"
ok "403 auf /v1/internal/*"

# --- 3) Docs-Toggle ------------------------------------------------------
# Dieser Fall prueft NICHT Caddy, sondern die App dahinter (FastAPI mit
# docs_url=None). Gegen einen Platzhalter-Upstream — wie im CI-Lauf, der nur
# Caddy hochzieht — waere er scheingruen: er wuerde ein 404 des Platzhalters
# fuer das 404 der App halten. Deshalb ist er dort ausdruecklich uebersprungen
# und bleibt Handlauf im Prod-Smoke (docs/cloud-prod-smoke.md). Die Zusage
# selbst deckt unabhaengig davon apps/api/tests/test_docs_toggle.py ab.
if [[ "${HEADERS_SKIP_DOCS:-0}" == "1" ]]; then
  skip "/docs — prueft die App, nicht Caddy (Handlauf im Prod-Smoke)"
else
  docs_public="${WHO2BE_DOCS_PUBLIC:-false}"
  log "GET ${BASE}/docs (WHO2BE_DOCS_PUBLIC=${docs_public})"
  code="$(curl_code /docs)"
  if [[ "${docs_public}" == "true" ]]; then
    [[ "${code}" == "200" ]] || fail "/docs → ${code}, erwartet 200 (DOCS_PUBLIC=true)"
    ok "/docs → 200"
  else
    # FastAPI mit docs_url=None liefert 404 (Route existiert nicht).
    [[ "${code}" == "404" ]] || fail "/docs → ${code}, erwartet 404 (DOCS_PUBLIC=false)"
    ok "/docs → 404"
  fi
fi

# --- Bilanz / Nulldurchlauf-Sicherung ------------------------------------
# Ein Test, der bei falscher Verwendung schweigend nichts prueft, ist schlimmer
# als ein fehlender: er erzeugt Vertrauen, das er nicht deckt. Deshalb ist die
# Zahl der ausgefuehrten Pruefungen Teil des Ergebnisses.
printf 'CHECKS_RUN=%d CHECKS_SKIPPED=%d\n' "${CHECKS_RUN}" "${CHECKS_SKIPPED}"
((CHECKS_RUN > 0)) || fail "keine einzige Pruefung ausgefuehrt — ein solcher Lauf
gilt als Fehlschlag, nie als Erfolg"

log "alle Header-Checks gruen ✓ (${CHECKS_RUN} geprueft, ${CHECKS_SKIPPED} uebersprungen)"
