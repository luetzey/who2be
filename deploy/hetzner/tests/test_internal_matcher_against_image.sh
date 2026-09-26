#!/usr/bin/env bash
# Gegenprobe zur Zugriffsregel des api-Vhosts: stellt das UNVERAENDERTE
# Caddyfile in einem echten Caddy-Container auf und prueft, dass der interne
# Bereich `/v1/internal` gesperrt bleibt — auch bei abweichender Schreibweise.
#
#   bash deploy/hetzner/tests/test_internal_matcher_against_image.sh              # Pin aus dem Compose
#   bash deploy/hetzner/tests/test_internal_matcher_against_image.sh 2.8-alpine   # Vergleichsversion
#
# WOZU
# `test_headers_against_image.sh` beantwortet „kommen die Header noch an?".
# Dieses Skript beantwortet die andere Frage: „haelt die Zugriffsentscheidung
# noch?" — und zwar nicht nur fuer die eine Schreibweise, in der ein Pfad
# ueblicherweise notiert wird. Ein Pfad-Matcher vergleicht Zeichenfolgen, nicht
# Absichten; wie ein Proxy eine Anfrage vor dem Vergleich normalisiert, ist
# Verhalten, das sich zwischen Versionen aendern darf. Damit haengt die
# Wirksamkeit einer path-basierten Regel an Implementierungsdetails — deshalb
# wird sie hier ausgefahren statt angenommen, bei jedem Versionssprung neu.
#
# DAS FAKE-BACKEND IST TEIL DES BEWEISES
# `reverse_proxy api:8000` braucht ein Gegenueber. Der Mini-Caddy hier antwortet
# auf `/v1/internal*` absichtlich mit 200 — kaeme eine Anfrage durch, waere das
# an der Antwort zu sehen. Dass der Test 403 sieht, beweist damit, dass CADDY
# blockt, und nicht das Backend zufaellig nichts anbietet. Die beiden
# Sanity-Zeilen am Ende (`/v1/health`, `/other`) belegen im selben Lauf, dass
# das Backend ueberhaupt antwortet; ohne sie koennte ein kaputter Aufbau
# durchgehend 403 oder 502 liefern und wie ein gruener Test aussehen.
#
# NEGATIVFAELLE GEHOEREN DAZU
# Eine Regel, die zu viel sperrt, ist genauso falsch wie eine, die zu wenig
# sperrt — `/v1/internalize` ist ein anderer Pfad und muss durchkommen.
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

HOSTPORT="${HOSTPORT:-18444}"
W="$(mktemp -d)"
SUFFIX="$$"
NET="caddyint-$SUFFIX"
API="caddyint-api-$SUFFIX"
PROXY="caddyint-proxy-$SUFFIX"

cleanup() {
  "$CT" rm -f "$API" "$PROXY" >/dev/null 2>&1 || true
  "$CT" network rm -f "$NET" >/dev/null 2>&1 || true
  [[ -f "$W/fake-api.Caddyfile" ]] && rm -f "$W/fake-api.Caddyfile"
  rmdir "$W" 2>/dev/null || true
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
	handle /v1/internal* {
		respond "BACKEND-REACHED" 200
	}
	handle {
		respond "ok" 200
	}
}
EOF

echo "[internal-matcher] Container-Tool: $CT, Caddy-Tag: $TAG, Port: $HOSTPORT"

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
  echo "[internal-matcher:FAIL] Caddy startet nicht. Logs:" >&2
  "$CT" logs "$PROXY" >&2 || true
  exit 1
fi
echo "[internal-matcher] laufende Version: $("$CT" exec "$PROXY" caddy version | head -1)"

BASE="https://api.localhost:${HOSTPORT}"
for _ in $(seq 1 40); do
  curl -sS -k -o /dev/null "${BASE}/v1/health" 2>/dev/null && break
  sleep 0.5
done

rc=0

# `--path-as-is`: curl soll den Pfad NICHT vorher aufraeumen, sonst prueft der
# Test die Normalisierung von curl statt die von Caddy.
probe() {
  curl -sS -k --path-as-is -o /dev/null -w '%{http_code}' "${BASE}$1" 2>/dev/null
}

echo "[internal-matcher] gesperrt erwartet (403):"
while IFS= read -r p; do
  [[ -z "$p" ]] && continue
  code="$(probe "$p")"
  if [[ "$code" == "403" ]]; then
    printf '  ✓ %-30s 403\n' "$p"
  else
    printf '  ✗ %-30s %s (erwartet 403)\n' "$p" "$code" >&2
    rc=1
  fi
done <<'BLOCKED'
/v1/internal/foo
/v1/internal
/V1/INTERNAL/foo
/v1/INTERNAL
/v1/internal%2ffoo
/v1/internal%252ffoo
/v1/internal\foo
/v1/internal%5cfoo
/v1/Internal%5CFoo
/v1%2finternal/foo
/v1%5cinternal/foo
/v1/internal/./foo
/v1/public/../internal/foo
/v1/internal//foo
/v1//internal/foo
/v1/internal;a=b/foo
/v1/internal%00/foo
/v1/internal./foo
/v1/internal?x=1
BLOCKED

# Die Regel darf nicht zu weit greifen: das sind andere Pfade.
echo "[internal-matcher] durchgelassen erwartet (nicht 403):"
while IFS= read -r p; do
  [[ -z "$p" ]] && continue
  code="$(probe "$p")"
  if [[ "$code" != "403" ]]; then
    printf '  ✓ %-30s %s\n' "$p" "$code"
  else
    printf '  ✗ %-30s 403 (erwartet Durchgang)\n' "$p" >&2
    rc=1
  fi
done <<'ALLOWED'
/v1/health
/other
/v1/internalize
/v1/internalize/foo
ALLOWED

# Sanity: das Backend antwortet in diesem Lauf wirklich. Ohne diese Zeile
# koennte ein kaputter Aufbau (502 ueberall) als gruen durchgehen.
health="$(probe /v1/health)"
if [[ "$health" != "200" ]]; then
  echo "[internal-matcher:FAIL] Fake-Backend antwortet nicht (/v1/health -> $health)" >&2
  rc=1
fi

if [[ "$rc" == "0" ]]; then
  echo "[internal-matcher] caddy:$TAG — Zugriffsregel haelt in allen geprueften Schreibweisen ✓"
else
  echo "[internal-matcher:FAIL] caddy:$TAG — siehe oben" >&2
fi
exit "$rc"
