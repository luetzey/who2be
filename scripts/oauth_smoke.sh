#!/usr/bin/env bash
# OAuth-Remote-MCP-Connector — lokaler End-to-End-Smoke für BEIDE Editionen.
#
#   scripts/oauth_smoke.sh onprem   # API als Owner-DB → RLS umgangen
#   scripts/oauth_smoke.sh cloud    # API als who2be_app (NOBYPASSRLS) → RLS aktiv
#
# Hermetisch + nicht-destruktiv: startet eine EIGENE Wegwerf-Postgres (Port 5433,
# Container who2be-oauth-smoke-db), migriert sie frisch, startet API + MCP-HTTP
# via `uv run` in der gewählten Edition und treibt den vollen OAuth-Flow durch
# (scripts/oauth_smoke.py). Räumt Prozesse UND Container beim Beenden auf — die
# lokale Dev-DB (docker compose) bleibt unberührt. Kein GoTrue nötig (JWT direkt
# gemintet).
set -euo pipefail

EDITION="${1:-}"
if [[ "$EDITION" != "onprem" && "$EDITION" != "cloud" ]]; then
  echo "Usage: $0 onprem|cloud" >&2
  exit 2
fi

cd "$(dirname "$0")/.."
DB_CONTAINER="who2be-oauth-smoke-db"
# Ports überschreibbar, damit ein parallel laufender lokaler Stack (z. B.
# mcp-http auf 8765) nicht kollidiert. Defaults meiden 8765 bewusst.
DB_PORT="${SMOKE_DB_PORT:-5433}"
API_PORT="${SMOKE_API_PORT:-8000}"
MCP_PORT="${SMOKE_MCP_PORT:-8766}"
OWNER_DB="postgresql://postgres:postgres@localhost:${DB_PORT}/who2be"
JWT_SECRET="dev-jwt-secret-change-me-32chars-min"
API_LOG="/tmp/who2be-oauth-smoke-api.log"
MCP_LOG="/tmp/who2be-oauth-smoke-mcp.log"
API_PID="" ; MCP_PID=""

cleanup() {
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "$MCP_PID" ]] && kill "$MCP_PID" 2>/dev/null || true
  docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> [1/5] Wegwerf-Postgres starten (:$DB_PORT, $DB_CONTAINER)"
docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$DB_CONTAINER" \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=who2be \
  -p "${DB_PORT}:5432" postgres:16 >/dev/null
for _ in $(seq 1 30); do
  docker exec "$DB_CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done

echo "==> [2/5] Schema migrieren (frisch)"
env DATABASE_URL="$OWNER_DB" uv run who2be-migrate >/dev/null

# --- Edition-spezifische API-Env -------------------------------------------
API_ENV=(
  "DATABASE_URL=$OWNER_DB"
  "JWT_SECRET=$JWT_SECRET"
  "OAUTH_ISSUER_URL=http://localhost:${API_PORT}"
  "OAUTH_CONSENT_URL=http://localhost:5173/oauth/consent"
  "MCP_RESOURCE_URL=http://localhost:${MCP_PORT}/mcp"
  "CORS_ORIGINS=http://localhost:5173"
)
if [[ "$EDITION" == "cloud" ]]; then
  echo "==> [3/5] Cloud: who2be_app-Passwort setzen → API verbindet mit RLS-Rolle"
  docker exec "$DB_CONTAINER" psql -U postgres -d who2be \
    -c "ALTER ROLE who2be_app WITH PASSWORD 'app'" >/dev/null
  API_ENV+=(
    "APP_DATABASE_URL=postgresql://who2be_app:app@localhost:${DB_PORT}/who2be"
    "WHO2BE_EDITION=cloud"
  )
else
  echo "==> [3/5] On-Prem: API verbindet als Owner (RLS umgangen)"
  API_ENV+=("WHO2BE_EDITION=onprem")
fi

echo "==> [4/5] API (:${API_PORT}) + MCP-HTTP (:${MCP_PORT}) starten via uv"
env "${API_ENV[@]}" uv run uvicorn who2be_api.main:app --host 127.0.0.1 --port "$API_PORT" \
  >"$API_LOG" 2>&1 &
API_PID=$!
env \
  WHO2BE_TRANSPORT=http \
  WHO2BE_HTTP_HOST=127.0.0.1 \
  WHO2BE_HTTP_PORT="$MCP_PORT" \
  WHO2BE_API_BASE_URL=http://localhost:${API_PORT} \
  WHO2BE_OAUTH_ISSUER_URL=http://localhost:${API_PORT} \
  WHO2BE_MCP_PUBLIC_URL=http://localhost:${MCP_PORT} \
  uv run python -m who2be_mcp.server >"$MCP_LOG" 2>&1 &
MCP_PID=$!

echo -n "    warte auf API-Health"
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:${API_PORT}/v1/health" >/dev/null 2>&1; then echo " ok"; break; fi
  if ! kill -0 "$API_PID" 2>/dev/null; then echo; echo "--- API-Log ---"; cat "$API_LOG"; exit 1; fi
  echo -n "." ; sleep 0.5
done

echo "==> [5/5] OAuth-Flow durchspielen"
env \
  API_BASE="http://localhost:${API_PORT}" \
  MCP_BASE="http://localhost:${MCP_PORT}" \
  MCP_RESOURCE="http://localhost:${MCP_PORT}/mcp" \
  DATABASE_URL="$OWNER_DB" \
  JWT_SECRET="$JWT_SECRET" \
  EDITION_LABEL="$EDITION" \
  uv run python scripts/oauth_smoke.py
