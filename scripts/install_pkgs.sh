#!/bin/bash
# SessionStart-Hook: installiert Projekt-Dependencies beim Sessionstart.
# Laeuft nur in der Cloud-VM; lokal No-op, damit lokale Sessions nichts anfassen.
if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then exit 0; fi
set -u

# Python — uv-Workspace im Repo-Root (apps/api, apps/mcp, packages/models).
if [ -f "uv.lock" ] || [ -f "pyproject.toml" ]; then
  if command -v uv >/dev/null 2>&1; then uv sync || true; fi
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
