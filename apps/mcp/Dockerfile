# Build-Context = Repo-Root, weil der uv-Workspace alle Member auflisten muss.
# Aufruf via docker compose:
#   build:
#     context: .
#     dockerfile: apps/mcp/Dockerfile
# Transport: Default stdio (Claude Desktop / Cursor local). Mit
# `WHO2BE_TRANSPORT=http` exponiert der Server Streamable-HTTP auf 0.0.0.0:8765
# — geeignet als Long-Running-Service hinter Caddy (`mcp.${DOMAIN}`). ADR-0034.
FROM python:3.14-slim AS builder

# uv (nur Build-Zeit) via PyPI statt per `COPY --from=ghcr.io/astral-sh/uv`:
# der Cross-Registry-Pull bricht auf Hosts mit (abgelaufener) ghcr-Anmeldung.
RUN pip install --no-cache-dir uv==0.4.27

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
# Nur der Kern-Workspace — packages/billing wird absichtlich NICHT kopiert
# (ADR-0029: das On-Prem-Artefakt enthaelt keinen Billing-Quellcode; das
# `packages/*`-Member-Glob matcht nur, was im Build-Context liegt — gleiches
# Muster wie apps/api/Dockerfile).
COPY packages/models packages/models
COPY apps/api apps/api
COPY apps/mcp apps/mcp

# Gleicher Workspace-Sync wie API — uv-Workspace verlangt alle Member;
# fuer Prod-Slim spaeter eigene runtime-Group (offener Followup, siehe
# apps/api/Dockerfile Kommentar).
RUN uv sync --frozen

FROM python:3.14-slim AS runtime

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /app /app

RUN useradd --system --no-create-home --uid 1000 who2be \
    && chown -R who2be:who2be /app
USER who2be

# HTTP-Transport (WHO2BE_TRANSPORT=http) bindet auf 0.0.0.0:8765/mcp; stdio
# ignoriert das. EXPOSE ist deklarativ — Compose darf den Port veroeffentlichen.
EXPOSE 8765

# Python-basierter Healthcheck (kein curl-Apt-Layer noetig). Reiner TCP-Connect
# — Streamable-HTTP-Endpunkt antwortet ohne Mcp-Session-Id mit 400 (das ist die
# spezifikationskonforme Antwort), und ein vollstaendiger `initialize`-Handshake
# im Healthcheck ist Overkill. Socket-Connect prueft, dass uvicorn bindet.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket,sys; \
s=socket.socket(); s.settimeout(3); s.connect(('127.0.0.1',8765)); s.close()" \
    2>/dev/null || exit 1

CMD ["python", "-m", "who2be_mcp.server"]
