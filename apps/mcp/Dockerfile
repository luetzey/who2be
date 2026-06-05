# Build-Context = Repo-Root, weil der uv-Workspace alle Member auflisten muss.
# Aufruf via docker compose:
#   build:
#     context: .
#     dockerfile: apps/mcp/Dockerfile
# Hinweis: Der MCP-Server nutzt per Default stdio-Transport. Der Container ist
# daher kein Long-Running-Service hinter Caddy, sondern ein "internal API
# consumer / smoke harness" — im Hetzner-Compose unter `profiles: ["mcp"]`,
# aufrufbar via `docker compose run --rm mcp ...`. Bei Bedarf kann spaeter
# auf HTTP-Transport umgestellt werden, dann kippt das Profil auf default.
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.4.27 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
COPY packages packages
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

CMD ["python", "-m", "who2be_mcp.server"]
