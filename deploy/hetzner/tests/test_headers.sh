#!/usr/bin/env bash
# Smoke fuer H5 Caddy-Hardening (F-12):
#   1) Security-Header auf /v1/health (HSTS, XCTO, XFO, Referrer, Permissions,
#      COOP, CSP inkl. object-src/form-action)
#   2) /v1/internal/* → 403 (extern blockt Caddy direkt)
#   3) /docs → 404 wenn WHO2BE_DOCS_PUBLIC=false (Default), sonst 200
#
# Aufruf:
#   bash deploy/hetzner/tests/test_headers.sh                    # localhost (Compose)
#   bash deploy/hetzner/tests/test_headers.sh https://api.<DOMAIN>
#
# Im Compose laeuft Caddy ohne TLS auf Port 80 (kein DOMAIN gesetzt); `-k` toleriert
# self-signed in lokalen Setups, in Prod hat Caddy ein gueltiges LE-Cert.
set -euo pipefail

BASE="${1:-http://localhost}"

log()  { printf '\033[1;34m[headers]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[headers:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

curl_h() {
  curl -sSI -k -H "Host: api.${DOMAIN:-localhost}" "${BASE}$1"
}

# --- 1) Security-Header --------------------------------------------------
log "GET ${BASE}/v1/health (Security-Header)"
hdrs="$(curl_h /v1/health)" || fail "/v1/health unerreichbar (${BASE})"

assert_header() {
  local name="$1"
  local pattern="$2"
  echo "${hdrs}" | grep -i "^${name}:" | grep -qi "${pattern}" \
    || fail "Header fehlt oder falsch: ${name} (erwarte: ${pattern})"
  printf '  ✓ %s\n' "${name}"
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
code="$(curl -sS -o /dev/null -w '%{http_code}' -k \
  -H "Host: api.${DOMAIN:-localhost}" \
  "${BASE}/v1/internal/foo")"
[[ "${code}" == "403" ]] || fail "/v1/internal/foo → ${code}, erwartet 403"
printf '  ✓ 403\n'

# --- 3) Docs-Toggle ------------------------------------------------------
docs_public="${WHO2BE_DOCS_PUBLIC:-false}"
log "GET ${BASE}/docs (WHO2BE_DOCS_PUBLIC=${docs_public})"
code="$(curl -sS -o /dev/null -w '%{http_code}' -k \
  -H "Host: api.${DOMAIN:-localhost}" \
  "${BASE}/docs")"
if [[ "${docs_public}" == "true" ]]; then
  [[ "${code}" == "200" ]] || fail "/docs → ${code}, erwartet 200 (DOCS_PUBLIC=true)"
  printf '  ✓ 200\n'
else
  # FastAPI mit docs_url=None liefert 404 (Route existiert nicht).
  [[ "${code}" == "404" ]] || fail "/docs → ${code}, erwartet 404 (DOCS_PUBLIC=false)"
  printf '  ✓ 404\n'
fi

log "alle Header-Checks gruen ✓"
