# Build-Context muss das Repo-Root sein, weil der uv-Workspace
# packages/models + apps/mcp als editable-Member braucht.
# Aufruf via docker compose:
#   build:
#     context: .
#     dockerfile: apps/api/Dockerfile
#     target: runtime          # On-Prem (Default) — KEIN Billing/Mollie im Image
#     # target: runtime-cloud  # Cloud — installiert das who2be-billing-Paket
#
# Build-Zeit-Isolation (ADR-0029): Der On-Prem-Build kopiert `packages/billing`
# bewusst NICHT in den Context und synct die `billing`-Gruppe nicht — das
# Mollie-SDK + die Billing-Schreibseite sind im On-Prem-Artefakt physisch nicht
# vorhanden. Nur der Cloud-Build zieht sie ueber `--group billing`.
FROM python:3.14-slim AS base

# uv (nur Build-Zeit) via PyPI statt per `COPY --from=ghcr.io/astral-sh/uv`:
# der Cross-Registry-Pull bricht auf Hosts mit (abgelaufener) ghcr-Anmeldung —
# buildkit faellt dann nicht auf anonym zurueck. PyPI-Wheel ist ghcr-unabhaengig.
RUN pip install --no-cache-dir uv==0.4.27

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
# Nur der Kern-Workspace — packages/billing wird hier absichtlich NICHT kopiert.
COPY packages/models packages/models
COPY apps/api apps/api
COPY apps/mcp apps/mcp

# --- On-Prem-Build: Kern ohne Billing -------------------------------------------
FROM base AS builder

# Workspace-Members (who2be-api/mcp/models) sind in der `dev`-Group gelistet
# (Root ist `package = false`). Daher kein `--no-dev` — sonst landet kein
# uvicorn/who2be-migrate im venv. Die `billing`-Group ist NICHT default → das
# Mollie-SDK + who2be-billing werden nicht installiert.
RUN uv sync --frozen

# --- Cloud-Build: Kern + Billing-Paket ------------------------------------------
FROM base AS builder-cloud

# Cloud zieht zusaetzlich das Billing-Paket (inkl. Mollie-SDK) in den Context
# und synct die `billing`-Gruppe.
COPY packages/billing packages/billing
RUN uv sync --frozen --group billing

# --- Gemeinsame Runtime-Basis ---------------------------------------------------
FROM python:3.14-slim AS runtime-base

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --no-create-home --uid 1000 who2be

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

# --- Cloud-Runtime (mit Billing) ------------------------------------------------
FROM runtime-base AS runtime-cloud
COPY --from=builder-cloud /app /app
RUN chown -R who2be:who2be /app
USER who2be

# --- On-Prem-Runtime (Default, OHNE Billing) ------------------------------------
# Bewusst die LETZTE Stage: `docker compose build` ohne `target:` baut On-Prem.
FROM runtime-base AS runtime
COPY --from=builder /app /app
RUN chown -R who2be:who2be /app
USER who2be
