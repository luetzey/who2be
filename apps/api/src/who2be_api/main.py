"""Application entrypoint for the Who2Be REST API.

Routen-Layout nach Phase 2:
- Top-Level (ohne Workspace-Prefix): `/v1/health`, `/v1/me`, `/v1/organizations`,
  `/v1/invitations/{token}/accept`.
- Workspace-scoped (Prefix `/v1/workspaces/{workspace_id}`): Personas, Playbooks,
  Resources, Tokens, Members, Invitations (Verwaltung), Persona-Playbook-Links,
  Playbook-Resource-Links, Dashboard. Membership wird über
  `get_current_workspace` durchgesetzt (siehe `core/security.py`).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from slowapi.middleware import SlowAPIMiddleware

from who2be_api import __version__
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.db import database
from who2be_api.core.db import lifespan as db_lifespan
from who2be_api.core.logging import configure_logging
from who2be_api.core.middleware import AccessLogMiddleware, RequestIDMiddleware
from who2be_api.core.rate_limit import (
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
)
from who2be_api.licensing.edition import is_onprem
from who2be_api.routers import (
    agents,
    billing,
    dashboard,
    invitations,
    me,
    members,
    organizations,
    persona_playbooks,
    personas,
    placeholders,
    playbook_composition,
    playbook_resources,
    playbooks,
    resources,
    system_prompts,
    tokens,
    usages,
    workspaces,
)
from who2be_api.services.bootstrap_service import bootstrap_admin_if_needed
from who2be_api.services.promote_validation import PromoteValidationError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App-Lifespan: DB-Lifecycle + On-Prem-Admin-Bootstrap (Track D).

    Wrappt den DB-Lifespan und seedet danach — nur On-Prem, nur wenn ein Pool
    verfuegbar ist und `WHO2BE_BOOTSTRAP_ADMIN_EMAIL` gesetzt ist — den Admin.
    Ein Bootstrap-Fehler darf den Start nie verhindern (fail open beim Boot).
    """
    async with db_lifespan(app):
        settings = get_settings()
        if is_onprem(settings) and settings.bootstrap_admin_email.strip():
            try:
                await bootstrap_admin_if_needed(database.pool, settings)
            except (RuntimeError, OSError) as exc:
                logger.warning("On-Prem-Bootstrap uebersprungen: %s", type(exc).__name__)
            except Exception:  # noqa: BLE001 — Boot darf nie an Bootstrap scheitern
                logger.exception("On-Prem-Bootstrap fehlgeschlagen.")
        yield


_WORKSPACE_PREFIX = "/v1/workspaces/{workspace_id}"


class Health(BaseModel):
    status: str
    version: str
    db: str


def _on_rate_limit(request: Request, exc: Exception) -> Response:
    # slowapi's Handler ist auf `RateLimitExceeded` typisiert; Starlette erwartet
    # `Exception`. Duenner Adapter haelt mypy strict, ohne `type: ignore`.
    return _rate_limit_exceeded_handler(request, cast(RateLimitExceeded, exc))


def _on_promote_validation_error(request: Request, exc: Exception) -> Response:
    """application/problem+json-Handler fuer `PromoteValidationError` (Welle 4).

    HTTP 409 (Status-Konflikt, nicht 422 syntaktischer Fehler). Der Frontend-
    Agent erwartet exakt dieses Shape um die fehlenden Feldnamen anzuzeigen.
    """
    err = cast(PromoteValidationError, exc)
    body = {
        "type": "https://who2be.dev/errors/promote-validation-failed",
        "title": "Promote nicht moeglich: Pflichtfelder fehlen",
        "status": 409,
        "detail": "Pflichtfelder muessen vor Promote ausgefuellt sein.",
        "missing": err.missing,
    }
    return JSONResponse(
        status_code=409,
        content=body,
        media_type="application/problem+json",
    )


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
    app.add_exception_handler(PromoteValidationError, _on_promote_validation_error)
    # SlowAPIMiddleware vor CORSMiddleware adden: Starlette stacked LIFO, dann liegt
    # CORS aussen und Preflight-OPTIONS triggert das Limit nicht.
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
    app.include_router(placeholders.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(persona_playbooks.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(playbook_composition.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(resources.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(playbook_resources.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(usages.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(system_prompts.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(agents.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(dashboard.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(members.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(invitations.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(billing.router, prefix=_WORKSPACE_PREFIX)
    # Top-Level-Endpunkte: `/v1/me`, `/v1/organizations`, `/v1/workspaces/{id}`.
    # Der anonyme Invitation-Accept haengt direkt unter `/v1/invitations`.
    app.include_router(me.router)
    app.include_router(organizations.router)
    app.include_router(workspaces.router)
    app.include_router(invitations.accept_router)
    # Cloud-Billing-Webhook (anonym, signaturgeprueft) — top-level, kein Workspace-Prefix.
    app.include_router(billing.webhook_router)

    @app.get("/v1/health", response_model=Health)
    async def health() -> Health:
        db_status = "ok" if await database.ping() else "unavailable"
        return Health(status="ok", version=__version__, db=db_status)

    return app


configure_logging(get_settings().log_format)
app = create_app()
