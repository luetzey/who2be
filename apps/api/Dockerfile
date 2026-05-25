# Build-Context muss das Repo-Root sein, weil der uv-Workspace
# packages/models + apps/mcp als editable-Member braucht.
# Aufruf via docker compose:
#   build:
#     context: .
#     dockerfile: apps/api/Dockerfile
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.4.27 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
COPY packages packages
COPY apps/api apps/api
COPY apps/mcp apps/mcp

# Workspace-Members (who2be-api/mcp/models) sind in der `dev`-Group gelistet
# (Root ist `package = false`). Daher kein `--no-dev` — sonst landet kein
# uvicorn/who2be-migrate im venv. pytest/mypy/ruff sind dadurch mit drin;
# fuer Smoke OK, fuer Prod-Image spaeter eigene `runtime`-Group anlegen.
RUN uv sync --frozen

FROM python:3.11-slim AS runtime

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

EXPOSE 8000
CMD ["uvicorn", "who2be_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
