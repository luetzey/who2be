#!/usr/bin/env bash
# Gegenprobe zum Caddy-Versionssprung: setzt das UNVERAENDERTE Caddyfile in
# einem echten Caddy-Container auf und faehrt `test_headers.sh` dagegen.
#
#   bash deploy/hetzner/tests/test_headers_against_image.sh                 # Pin aus dem Compose
#   bash deploy/hetzner/tests/test_headers_against_image.sh 2.8-alpine      # Vergleichsversion
#
# WOZU
# Der eigentliche Nachweis bei einem Versionssprung des Reverse-Proxy ist
# nicht „validate ist gruen", sondern: kommen die Security-Header und die vier
# differenzierten CSPs danach noch genau so an? `test_headers.sh` prueft das,
# braucht dafuer aber einen laufenden Stack. Dieses Skript stellt den her —
# gegen JEDEN Image-Tag, sodass sich alte und neue Version direkt vergleichen
# lassen. So war der Sprung 2.8.4 -> 2.11.4 belegt, und so ist der naechste
# Sprung belegbar, ohne dass jemand den Aufbau neu erfinden muss.
#
# WARUM DAS OHNE AENDERUNG AM CADDYFILE GEHT
# `DOMAIN=localhost` macht aus den vier Vhosts api./app./supabase./mcp.localhost.
# Fuer `localhost` und `*.localhost` nimmt Caddys Auto-HTTPS die INTERNE CA —
# kein ACME, kein Netz, keine Let's-Encrypt-Rate-Limits. Der Prod-Pfad laeuft
# also inklusive TLS, und `test_headers.sh` toleriert das Selbstsignierte
# bereits per `-k`. Kein Overlay, keine Zeile Unterschied: geprueft wird
# woertlich die Datei, die auf dem Server liegt.
#
# DAS FAKE-BACKEND IST TEIL DES BEWEISES
# `reverse_proxy api:8000` braucht ein Gegenueber. Der Mini-Caddy hier
# antwortet auf `/v1/internal/*` absichtlich mit 200 — wuerde Caddy die Route
# durchlassen, kaeme diese Antwort durch. Dass der Test 403 sieht, beweist
# damit, dass CADDY blockt und nicht das Backend zufaellig nichts anbietet.
#
# Voraussetzung: docker oder podman. Kein Netz ausser dem Image-Pull.
set -uo pipefail

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

CT="${CONTAINER_TOOL:-}"
if [[ -z "$CT" ]]; then
  if command -v docker >/dev/null 2>&1; then CT=docker
  elif command -v podman >/dev/null 2>&1; then CT=podman
  else echo "FEHLER: weder docker noch podman gefunden" >&2; exit 1; fi
fi

HOSTPORT="${HOSTPORT:-18443}"
W="$(mktemp -d)"
SUFFIX="$$"
NET="caddyhdr-$SUFFIX"
API="caddyhdr-api-$SUFFIX"
PROXY="caddyhdr-proxy-$SUFFIX"

cleanup() {
  "$CT" rm -f "$API" "$PROXY" >/dev/null 2>&1 || true
  "$CT" network rm -f "$NET" >/dev/null 2>&1 || true
  rm -rf "$W"
}
trap cleanup EXIT

cat > "$W/fake-api.Caddyfile" <<'EOF'
{
	auto_https off
	admin off
}
:8000 {
	handle /v1/health {
		respond `{"status":"ok"}` 200
	}
	handle /docs* {
		respond "not found" 404
	}
	handle /v1/internal* {
		respond "BACKEND-REACHED" 200
	}
	handle {
		respond "ok" 200
	}
}
EOF

echo "[headers-image] Container-Tool: $CT, Caddy-Tag: $TAG, Port: $HOSTPORT"

"$CT" network create "$NET" >/dev/null
"$CT" run -d --name "$API" --network "$NET" --network-alias api \
  -v "$W/fake-api.Caddyfile":/etc/caddy/Caddyfile:ro,Z \
  "docker.io/library/caddy:$TAG" >/dev/null
"$CT" run -d --name "$PROXY" --network "$NET" \
  -e DOMAIN=localhost -e ACME_EMAIL=ops@example.test \
  -e VITE_SUPABASE_URL=https://supabase.example.test \
  -p "${HOSTPORT}:443" \
  -v "$REPO/deploy/hetzner/Caddyfile":/etc/caddy/Caddyfile:ro,Z \
  "docker.io/library/caddy:$TAG" >/dev/null

sleep 3
if [[ "$("$CT" inspect -f '{{.State.Running}}' "$PROXY" 2>/dev/null)" != "true" ]]; then
  echo "[headers-image:FAIL] Caddy startet nicht. Logs:" >&2
  "$CT" logs "$PROXY" >&2 || true
  exit 1
fi
echo "[headers-image] laufende Version: $("$CT" exec "$PROXY" caddy version | head -1)"

BASE="https://api.localhost:${HOSTPORT}"
for _ in $(seq 1 40); do
  curl -sS -k -o /dev/null "${BASE}/v1/health" 2>/dev/null && break
  sleep 0.5
done

DOMAIN=localhost WHO2BE_DOCS_PUBLIC=false bash "$HERE/test_headers.sh" "$BASE"
rc=$?

# Die CSPs der drei uebrigen Vhosts sieht `test_headers.sh` nicht — es faehrt
# nur den api-Vhost. Genau sie sind aber das, was ein Versionssprung still
# verschieben koennte, also hier mitgenommen.
echo "[headers-image] CSP der uebrigen Vhosts:"
for vhost in app supabase mcp; do
  csp="$(curl -sSI -k "https://${vhost}.localhost:${HOSTPORT}/" 2>/dev/null \
    | grep -i '^content-security-policy:' || true)"
  if [[ -z "$csp" ]]; then
    echo "[headers-image:FAIL] ${vhost}-Vhost liefert keinen CSP-Header" >&2
    rc=1
  else
    printf '  ✓ %-9s %s\n' "$vhost" "${csp#*: }"
  fi
done

if [[ "$rc" == "0" ]]; then
  echo "[headers-image] caddy:$TAG — alle Header-Checks gruen ✓"
else
  echo "[headers-image:FAIL] caddy:$TAG — siehe oben" >&2
fi
exit "$rc"
