"""Application entrypoint for the Who2Be REST API.

Phase 1: Health-Endpoint, Infrastruktur-Fundament (zentrale Settings,
asyncpg-Pool), Auth (`/v1/tokens`), Persona- und Playbook-CRUD inklusive
Persona-Playbook-Verknuepfung.
"""

from typing import cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from slowapi.middleware import SlowAPIMiddleware

from who2be_api import __version__
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.db import database, lifespan
from who2be_api.core.logging import configure_logging
from who2be_api.core.middleware import AccessLogMiddleware, RequestIDMiddleware
from who2be_api.core.rate_limit import (
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
)
from who2be_api.routers import (
    dashboard,
    invitations,
    me,
    members,
    organizations,
    persona_playbooks,
    personas,
    playbook_resources,
    playbooks,
    resources,
    tokens,
    workspaces,
)

_WORKSPACE_PREFIX = "/v1/workspaces/{workspace_id}"


class Health(BaseModel):
    status: str
    version: str
    db: str


def _on_rate_limit(request: Request, exc: Exception) -> Response:
    # slowapi's Handler ist auf `RateLimitExceeded` typisiert; Starlette erwartet
    # `Exception`. Duenner Adapter haelt mypy strict, ohne `type: ignore`.
    return _rate_limit_exceeded_handler(request, cast(RateLimitExceeded, exc))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Konstruiert die FastAPI-App. Default-Settings via `get_settings()`.

    Tests koennen einen `Settings`-Override uebergeben, um alternative Configs
    (z.B. `docs_public=True`) ohne Env-Monkeypatch + Modul-Reload zu pruefen.
    """
    if settings is None:
        settings = get_settings()

    # H5 / F-13: /docs, /redoc, /openapi.json sind Default aus.
    docs_url = "/docs" if settings.docs_public else None
    redoc_url = "/redoc" if settings.docs_public else None
    openapi_url = "/openapi.json" if settings.docs_public else None

    app = FastAPI(
        title="Who2Be API",
        version=__version__,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _on_rate_limit)
    # SlowAPIMiddleware vor CORSMiddleware adden: Starlette stacked LIFO, dann liegt
    # CORS aussen und Preflight-OPTIONS triggert das Limit nicht.
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Next-Cursor"],
        allow_credentials=False,
    )
    # Observability-Stack: AccessLog innen, RequestID aussen — Starlette stacked LIFO,
    # also wird RequestID zuerst aufgerufen, bindet die ID, und der AccessLog-Logger
    # kann sie ueber `structlog.contextvars` lesen, bevor er die Zeile emittiert.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    # Workspace-scoped Router unter `/v1/workspaces/{workspace_id}/...` —
    # die Path-Variable wird von `get_current_workspace` als Dependency gelesen.
    app.include_router(tokens.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(personas.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(playbooks.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(persona_playbooks.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(resources.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(playbook_resources.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(dashboard.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(members.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(invitations.router, prefix=_WORKSPACE_PREFIX)
    # Top-Level-Endpunkte: `/v1/me`, `/v1/organizations`, `/v1/workspaces/{id}`.
    # Der anonyme Invitation-Accept haengt direkt unter `/v1/invitations`.
    app.include_router(me.router)
    app.include_router(organizations.router)
    app.include_router(workspaces.router)
    app.include_router(invitations.accept_router)

    @app.get("/v1/health", response_model=Health)
    async def health() -> Health:
        db_status = "ok" if await database.ping() else "unavailable"
        return Health(status="ok", version=__version__, db=db_status)

    return app


configure_logging(get_settings().log_format)
app = create_app()
