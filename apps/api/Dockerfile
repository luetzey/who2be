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

# Non-root-User fuer Prod-Container — minimiert Container-Escape-Schaden.
RUN useradd --system --no-create-home --uid 1000 who2be \
    && chown -R who2be:who2be /app
USER who2be

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/v1/health || exit 1
# `--proxy-headers` + `--forwarded-allow-ips *` adressieren F-02 aus
# docs/security-findings.md: Hinter Caddy laeuft der Container nur im
# internen Netzwerk, daher ist `*` mit Network-Isolation akzeptabel.
CMD ["uvicorn", "who2be_api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
