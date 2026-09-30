#!/usr/bin/env bash
# Smoke fuer H5 Caddy-Hardening (F-12):
#   1) Security-Header auf /v1/health (HSTS, XCTO, XFO, Referrer, Permissions,
#      COOP, CSP inkl. object-src/form-action)
#   2) /v1/internal/* → 403 (extern blockt Caddy direkt)
#   3) /docs → 404 wenn WHO2BE_DOCS_PUBLIC=false (Default), sonst 200
#   4) Crawler-Signal + Cache-Control auf allen vier Hosts (api./app./mcp./
#      supabase.), ausdruecklich auch auf 401- und 404-Antworten:
#      X-Robots-Tag noindex ueberall; `Cache-Control: no-store` auf api./mcp.,
#      ohne einen von der App gesetzten Wert zu ueberschreiben; CSP auf den
#      drei uebrigen Vhosts
#   5) Web-Inhalt: /robots.txt ist eine echte Textdatei (kein SPA-HTML) und
#      sperrt nichts; index.html traegt <meta name="robots" content="noindex">
#
# Die Hosts app./mcp./supabase. werden aus der api.-Adresse abgeleitet — die
# Adresse MUSS deshalb mit `api.` beginnen.
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
#   HEADERS_SKIP_WEB_CONTENT=1  Abschnitt 5 ueberspringen (Upstream ist kein
#                               echter Web-Container, sondern ein Platzhalter)
#   HEADERS_APP_CACHE_PROBE=/p  Pfad, auf dem der Upstream selbst
#                               `Cache-Control: private, max-age=60` setzt
#                               (nur Platzhalter-Lauf, s. test_headers_ci.sh)
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

CURL_BASE_OPTS=(-sS -k)
CURL_OPTS=("${CURL_BASE_OPTS[@]}")
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

# --- 4) Crawler-Signal + Cache-Control auf allen Hosts ----------------------
# Die Nachbar-Hosts entstehen aus der api.-Adresse durch Tausch des ersten
# Labels. Ohne `api.` am Anfang gaebe es nichts zu tauschen — dann lieber laut
# scheitern als still nur einen Host pruefen.
[[ "${HOST}" == api.* ]] || fail "Adresse muss mit api. beginnen (ist: ${HOST}),
sonst lassen sich app./mcp./supabase. nicht ableiten"
DOMAIN_PART="${HOST#api.}"

# host_url <label> <pfad> → volle URL auf dem Nachbar-Host (gleicher Port).
host_url() { printf '%s://%s.%s:%s%s' "${_scheme}" "$1" "${DOMAIN_PART}" "${PORT}" "$2"; }

# host_curl <label> <curl-args…> — mit passendem --resolve je Host.
host_curl() {
  local label="$1"; shift
  local opts=("${CURL_BASE_OPTS[@]}")
  if [[ -n "${HEADERS_RESOLVE:-}" ]]; then
    opts+=(--resolve "${label}.${DOMAIN_PART}:${PORT}:${HEADERS_RESOLVE}")
  fi
  curl "${opts[@]}" "$@"
}

# Header per GET holen (nicht -I): HEAD beantworten manche Upstreams anders,
# und geprueft werden soll die Antwort, die ein Crawler bekommt.
host_headers() { host_curl "$1" -o /dev/null -D - "$(host_url "$1" "$2")"; }

# expect_response <label> <pfad> <status> <cache: no-store|not-no-store|any>
expect_response() {
  local label="$1" path="$2" want_status="$3" cache="$4"
  local what="${label}.${DOMAIN_PART}${path}"
  local h
  h="$(host_headers "${label}" "${path}")" || fail "${what} unerreichbar"
  local status
  status="$(printf '%s' "${h}" | head -n 1 | awk '{print $2}')"
  [[ "${status}" == "${want_status}" ]] \
    || fail "${what} → ${status}, erwartet ${want_status} (Testaufbau pruefen)"
  printf '%s' "${h}" | grep -i '^x-robots-tag:' | grep -qi 'noindex' \
    || fail "${what} (${status}): X-Robots-Tag mit noindex fehlt"
  local cc
  cc="$(printf '%s' "${h}" | grep -i '^cache-control:' | tr -d '\r' || true)"
  case "${cache}" in
    no-store)
      printf '%s' "${cc}" | grep -qi 'no-store' \
        || fail "${what} (${status}): Cache-Control no-store fehlt (ist: '${cc}')"
      ;;
    not-no-store)
      if printf '%s' "${cc}" | grep -qi 'no-store'; then
        fail "${what}: oeffentliche Metadaten tragen no-store (ist: '${cc}')"
      fi
      ;;
  esac
  ok "${what} → ${status}, X-Robots-Tag noindex${cc:+, ${cc}}"
}

log "CSP auf app./mcp./supabase. (api. oben)"
for vhost in app mcp supabase; do
  csp="$(host_headers "${vhost}" / | grep -i '^content-security-policy:' | tr -d '\r' || true)"
  [[ -n "${csp}" ]] || fail "${vhost}-Vhost liefert keinen CSP-Header"
  ok "${vhost}: ${csp#*: }"
done

log "Crawler-Signal + Cache-Control auf api./app./mcp./supabase."
# api.: Inhalt, 401 ohne Anmeldung, 404, Caddy-eigenes 403.
expect_response api      /v1/health          200 no-store
expect_response api      /v1/me              401 no-store
expect_response api      /robots.txt         404 no-store
expect_response api      /v1/internal/foo    403 no-store
# Oeffentliche Protokoll-Metadaten bleiben cachebar.
expect_response api      /.well-known/oauth-authorization-server 200 not-no-store
# Setzt die App selbst ein Cache-Control, bleibt es stehen. Den Pfad bedient
# nur der Platzhalter aus test_headers_ci.sh — gegen einen echten Stack
# (HEADERS_APP_CACHE_PROBE unset) entfaellt die Probe.
if [[ -n "${HEADERS_APP_CACHE_PROBE:-}" ]]; then
  expect_response api    "${HEADERS_APP_CACHE_PROBE}" 200 any
  ah="$(host_headers api "${HEADERS_APP_CACHE_PROBE}")"
  printf '%s' "${ah}" | grep -i '^cache-control:' | grep -qi 'private, max-age=60' \
    || fail "App-eigenes Cache-Control wurde ueberschrieben: $(printf '%s' "${ah}" | grep -i '^cache-control:')"
  ok "App-eigenes Cache-Control bleibt unangetastet"
fi
# mcp.: 401 ohne Token; die RFC-9728-Metadaten behalten den App-Wert.
expect_response mcp      /mcp                401 no-store
expect_response mcp      /.well-known/oauth-protected-resource/mcp 200 not-no-store
# supabase.: 404 fuer unbekannte Pfade — auch Fehlerseiten tragen das Signal.
expect_response supabase /robots.txt         404 any
# app.: die App-Shell. Cache-Control setzt dort der Web-Container (no-cache
# fuer index.html, Deploy-Frische), nicht Caddy — hier nicht geprueft.
expect_response app      /                   200 any
expect_response app      /robots.txt         200 any

# --- 5) Web-Inhalt: robots.txt + meta robots ---------------------------------
# Prueft den Web-Container, nicht Caddy — gegen einen Platzhalter-Upstream
# waere das bedeutungslos, deshalb abschaltbar.
if [[ "${HEADERS_SKIP_WEB_CONTENT:-0}" == "1" ]]; then
  skip "robots.txt/meta robots — Upstream ist kein Web-Container"
else
  log "GET $(host_url app /robots.txt) (echte Textdatei, sperrt nichts)"
  rh="$(host_headers app /robots.txt)"
  printf '%s' "${rh}" | grep -i '^content-type:' | grep -qi 'text/plain' \
    || fail "/robots.txt ist nicht text/plain: $(printf '%s' "${rh}" | grep -i '^content-type:')"
  ok "/robots.txt Content-Type text/plain"
  rbody="$(host_curl app "$(host_url app /robots.txt)")"
  if printf '%s' "${rbody}" | grep -qi '<html'; then
    fail "/robots.txt liefert HTML (SPA-Fallback statt Datei)"
  fi
  ok "/robots.txt ist kein SPA-HTML"
  # `Disallow: /` wuerde Crawler aussperren — dann saehen sie das noindex nie.
  if printf '%s' "${rbody}" | grep -Eqi '^[[:space:]]*disallow:[[:space:]]*/[[:space:]]*$'; then
    fail "/robots.txt sperrt die Seite (Disallow: /) — das noindex waere unsichtbar"
  fi
  ok "/robots.txt sperrt nichts"

  log "GET $(host_url app /) (meta robots)"
  ibody="$(host_curl app "$(host_url app /)")"
  printf '%s' "${ibody}" | grep -Eqi '<meta[^>]+name="robots"[^>]+content="[^"]*noindex' \
    || fail "index.html ohne <meta name=\"robots\" content=\"noindex…\">"
  ok "index.html: meta robots noindex"
fi

# --- Bilanz / Nulldurchlauf-Sicherung ------------------------------------
# Ein Test, der bei falscher Verwendung schweigend nichts prueft, ist schlimmer
# als ein fehlender: er erzeugt Vertrauen, das er nicht deckt. Deshalb ist die
# Zahl der ausgefuehrten Pruefungen Teil des Ergebnisses.
printf 'CHECKS_RUN=%d CHECKS_SKIPPED=%d\n' "${CHECKS_RUN}" "${CHECKS_SKIPPED}"
((CHECKS_RUN > 0)) || fail "keine einzige Pruefung ausgefuehrt — ein solcher Lauf
gilt als Fehlschlag, nie als Erfolg"

log "alle Header-Checks gruen ✓ (${CHECKS_RUN} geprueft, ${CHECKS_SKIPPED} uebersprungen)"
