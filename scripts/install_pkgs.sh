#!/bin/bash
# SessionStart-Hook: installiert Projekt-Dependencies beim Sessionstart.
# Laeuft nur in der Cloud-VM; lokal No-op, damit lokale Sessions nichts anfassen.
if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then exit 0; fi
set -u

# Python — uv-Workspace im Repo-Root (apps/api, apps/mcp, packages/models).
# `--group billing` synct wie CI (.github/workflows/ci.yml:104) und
# CLAUDE.md §Befehle — sonst fehlt who2be_billing und dessen Tests werden
# still nicht gesammelt.
if [ -f "uv.lock" ] || [ -f "pyproject.toml" ]; then
  if command -v uv >/dev/null 2>&1; then uv sync --group billing || true; fi
fi

# DB-Erreichbarkeitspruefung (nur Hinweis, kein Abbruch — der Hook traegt
# bewusst `|| true`/keinen `set -e`-Effekt, siehe Issue #495).
if ! (exec 3<>/dev/tcp/127.0.0.1/5432) 2>/dev/null; then
  echo "Hinweis: Keine Postgres-Instanz auf 127.0.0.1:5432 erreichbar." >&2
  echo "  -> Integrationstests werden dadurch STILL uebersprungen (bis zu 481 Tests)." >&2
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "  -> Docker laeuft: 'WHO2BE_TEST_TESTCONTAINERS=1' vor dem Testlauf setzen," >&2
    echo "     dann startet conftest.py automatisch pgvector/pgvector:pg16." >&2
  else
    echo "  -> Docker-Daemon ist nicht erreichbar. Sobald er laeuft: 'WHO2BE_TEST_TESTCONTAINERS=1'" >&2
    echo "     vor dem Testlauf setzen (conftest.py startet dann pgvector/pgvector:pg16)." >&2
  fi
  # Bewusst NICHT 'pg_ctlcluster 16 main start' empfehlen: dem lokalen
  # Cluster fehlt die 'vector'-Extension (/usr/share/postgresql/16/extension/
  # fuehrt sie nicht) — Migration 0071 (ADR-0046) braucht sie, ein
  # gestarteter Cluster braeche also an der Migration statt an der Verbindung.
fi

# React-Web unter apps/web.
if [ -d "apps/web" ]; then
  (
    cd apps/web || exit 0
    if [ -f "pnpm-lock.yaml" ] && command -v pnpm >/dev/null 2>&1; then
      pnpm install --frozen-lockfile || pnpm install || true
    elif [ -f "yarn.lock" ] && command -v yarn >/dev/null 2>&1; then
      yarn install --frozen-lockfile || yarn install || true
    elif [ -f "package-lock.json" ]; then
      npm ci || npm install || true
    elif [ -f "package.json" ]; then
      npm install || true
    fi
  )
fi

exit 0
