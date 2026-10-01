#!/usr/bin/env bash
# Gegenprobe zum Caddy-Versionssprung: setzt das UNVERAENDERTE Caddyfile in
# einem echten Caddy-Container auf und faehrt `test_headers.sh` dagegen.
#
#   bash deploy/hetzner/tests/test_headers_against_image.sh                 # Pin aus dem Compose
#   bash deploy/hetzner/tests/test_headers_against_image.sh 2.8-alpine      # Vergleichsversion
#
# WOZU
# Der eigentliche Nachweis bei einem Versionssprung des Reverse-Proxy ist
# nicht „validate ist gruen", sondern: kommen die Security-Header, das
# Crawler-Signal, Cache-Control und die vier differenzierten CSPs danach noch
# genau so an? Dieses Skript beantwortet das gegen JEDEN Image-Tag, sodass
# sich alte und neue Version direkt vergleichen lassen. So war der Sprung
# 2.8.4 -> 2.11.4 belegt, und so ist der naechste Sprung belegbar.
#
# WIE
# Der Aufbau (Platzhalter-Upstreams fuer api/auth-gateway/mcp-http, echter
# nginx mit apps/web/nginx.conf fuer web, Caddy mit `DOMAIN=localhost` und
# interner CA) ist derselbe wie im CI-Lauf und steht deshalb nur EINMAL:
# in `test_headers_ci.sh`. Dieses Skript bestimmt nur den Tag und reicht ihn
# weiter — zwei Kopien desselben Aufbaus liefen sonst auseinander, und die
# Handprobe wuerde etwas anderes messen als CI.
#
# Voraussetzung: docker oder podman. Kein Netz ausser dem Image-Pull.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
COMPOSE="$REPO/deploy/hetzner/who2be/docker-compose.yml"

# Ohne Argument: genau den Tag pruefen, der im Compose steht. Ein Skript, das
# hier eine eigene Version raet, wuerde etwas anderes messen als das, was laeuft.
if [[ $# -ge 1 ]]; then
  TAG="$1"
else
  TAG="$(sed -n 's/^[[:space:]]*image:[[:space:]]*caddy:\(.*\)$/\1/p' "$COMPOSE" | head -1)"
  [[ -n "$TAG" ]] || { echo "FEHLER: kein caddy-Pin in $COMPOSE gefunden" >&2; exit 1; }
fi

echo "[headers-image] Caddy-Tag: $TAG"
if CADDY_IMAGE="docker.io/library/caddy:$TAG" bash "$HERE/test_headers_ci.sh"; then
  echo "[headers-image] caddy:$TAG — alle Header-Checks gruen ✓"
else
  rc=$?
  echo "[headers-image:FAIL] caddy:$TAG — siehe oben" >&2
  exit "$rc"
fi
