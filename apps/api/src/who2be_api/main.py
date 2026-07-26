"""Application entrypoint for the Who2Be REST API.

Routen-Layout nach Phase 2:
- Top-Level (ohne Workspace-Prefix): `/v1/health`, `/v1/me`, `/v1/organizations`,
  `/v1/invitations/{token}/accept`.
- Workspace-scoped (Prefix `/v1/workspaces/{workspace_id}`): Personas, Playbooks,
  Resources, Tokens, Members, Invitations (Verwaltung), Persona-Playbook-Links,
  Playbook-Resource-Links, Dashboard. Membership wird über
  `get_current_workspace` durchgesetzt (siehe `core/security.py`).
"""

import importlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import asyncpg
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from slowapi.middleware import SlowAPIMiddleware

from who2be_api import __version__
from who2be_api.core.chunk_backfill import backfill_chunks
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.db import database
from who2be_api.core.db import lifespan as db_lifespan
from who2be_api.core.errors import ApiGateError
from who2be_api.core.logging import configure_logging
from who2be_api.core.middleware import AccessLogMiddleware, RequestIDMiddleware
from who2be_api.core.rate_limit import (
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
)
from who2be_api.licensing.edition import is_cloud, is_onprem
from who2be_api.repositories.workspace_repository import sync_managed_builder_content
from who2be_api.routers import (
    agents,
    dashboard,
    entitlement,
    external_tools,
    feedback,
    gdpr,
    invitations,
    me,
    members,
    memory,
    oauth,
    organizations,
    persona_playbooks,
    personas,
    placeholders,
    playbook_composition,
    playbook_resources,
    playbooks,
    resource_composition,
    resources,
    search,
    system_prompts,
    tokens,
    usages,
    whoami,
    workspaces,
)
from who2be_api.services.bootstrap_service import bootstrap_admin_if_needed
from who2be_api.services.promote_validation import PromoteValidationError
from who2be_models import ApiProblem

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
        # Zentrale Verteilung: managed Builder-Aggregate mit veraltetem
        # Content-Stempel auf den kanonischen Stand heben. Braucht eine
        # privilegierte (Owner-)Verbindung — der RLS-gescopte App-Pool saehe ohne
        # Tenant keine Zeilen. Fail-open: ein Sync-Fehler darf den Start nie
        # verhindern.
        try:
            sync_conn = await asyncpg.connect(settings.database_url)
            try:
                count = await sync_managed_builder_content(sync_conn)
                if count:
                    logger.info("Builder-Content-Sync: %d Aggregate aktualisiert.", count)
                    # Der Sync ersetzt aktive Versions-Inhalte in-place, also an
                    # `version_status._transition` vorbei — die Passagen (ADR-0046)
                    # zeigten sonst weiter auf den alten Text. Der Rebuild laeuft
                    # nur nach einem Content-Bump, nicht bei jedem Start. Vektoren
                    # bleiben dem CLI-Backfill vorbehalten: ein Embedding-Lauf
                    # gehoert nicht in den Startpfad.
                    _, chunks, _ = await backfill_chunks(sync_conn)
                    logger.info("Passagen nach Content-Sync neu gebaut: %d.", chunks)
            finally:
                await sync_conn.close()
        except Exception:  # noqa: BLE001 — Boot darf nie am Sync scheitern
            logger.exception("Builder-Content-Sync uebersprungen.")
        yield


_WORKSPACE_PREFIX = "/v1/workspaces/{workspace_id}"

# Menschenlesbarer Titel je Taxonomie-`reason` (RFC-7807 `title`). Zentral
# gehalten, damit Call-Sites nur den maschinenlesbaren `reason` liefern (D2).
_PROBLEM_TITLES: dict[str, str] = {
    "missing_capability": "Aktion nicht erlaubt: fehlende Berechtigung",
    "approval_pending": "Aktion blockiert: Freigabe ausstehend",
    "domain_disabled": "Bereich deaktiviert",
    "forbidden_transition": "Unzulaessiger Status-Uebergang",
    "insufficient_role": "Aktion nicht erlaubt: Rolle zu niedrig",
    "mfa_required": "Zwei-Faktor-Authentifizierung erforderlich",
    "concurrent_conflict": "Konflikt durch parallele Aenderung",
    "composite_child_inactive": "Composite nicht aktivierbar: Sub-Playbook nicht aktiv",
    "managed_aggregate": "Aktion nicht erlaubt: vom System verwaltet",
}


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


def _current_request_id(request: Request) -> str | None:
    """Korrelations-ID fuer den Fehler-Body.

    Primaerquelle ist die von `RequestIDMiddleware` an `structlog.contextvars`
    gebundene `request_id` (identisch mit dem `X-Request-ID`-Response-Header).
    Faellt sie aus (z. B. Handler ohne Middleware), wird der eingehende
    `X-Request-ID`-Header gespiegelt; sonst `None`.
    """
    bound = structlog.contextvars.get_contextvars().get("request_id")
    if isinstance(bound, str) and bound:
        return bound
    incoming = request.headers.get("x-request-id")
    return incoming or None


def _on_api_gate_error(request: Request, exc: Exception) -> Response:
    """application/problem+json-Handler fuer `ApiGateError` (WP-2 / #254).

    Setzt `type`/`title`/`request_id` zentral; Call-Sites liefern nur
    `(status, reason, actionable_by, detail)`. RFC-7807-Body via `ApiProblem`.
    """
    err = cast(ApiGateError, exc)
    problem = ApiProblem(
        type=f"https://who2be.dev/errors/{err.reason.replace('_', '-')}",
        title=_PROBLEM_TITLES[err.reason],
        status=err.status,
        detail=err.detail,
        actionable_by=err.actionable_by,
        reason=err.reason,
        request_id=_current_request_id(request),
    )
    return JSONResponse(
        status_code=err.status,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


def _register_billing_if_present(app: FastAPI, settings: Settings) -> None:
    """Bindet das optionale Cloud-Billing-Paket ein — nur Cloud UND installiert.

    Dynamischer Import (kein statisches ``import who2be_billing``): der Kern haengt
    nicht von der Schreibseite ab (ADR-0029). Im On-Prem-Artefakt ist das Paket
    physisch nicht installiert → ``ImportError`` → still uebersprungen.
    """
    if not is_cloud(settings):
        return
    try:
        billing = importlib.import_module("who2be_billing")
    except ImportError:
        logger.info("who2be-billing nicht installiert — Billing-Schreibrouten ausgelassen.")
        return
    billing.include_routers(app, workspace_prefix=_WORKSPACE_PREFIX)


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
    app.add_exception_handler(ApiGateError, _on_api_gate_error)
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
    app.include_router(external_tools.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(resource_composition.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(playbook_resources.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(usages.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(feedback.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(memory.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(search.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(system_prompts.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(agents.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(dashboard.router, prefix=_WORKSPACE_PREFIX)
    # Identitaets-/Capability-Introspektion (#253) — ungated Read, Viewer-offen.
    app.include_router(whoami.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(members.router, prefix=_WORKSPACE_PREFIX)
    app.include_router(invitations.router, prefix=_WORKSPACE_PREFIX)
    # Entitlement-READ (editionsunabhaengig, reiner Read auf die Org-SSoT).
    app.include_router(entitlement.router, prefix=_WORKSPACE_PREFIX)
    # Top-Level-Endpunkte: `/v1/me`, `/v1/organizations`, `/v1/workspaces/{id}`.
    # Der anonyme Invitation-Accept haengt direkt unter `/v1/invitations`.
    app.include_router(me.router)
    app.include_router(organizations.router)
    app.include_router(workspaces.router)
    app.include_router(gdpr.router)
    app.include_router(invitations.accept_router)
    # OAuth-2.1-Authorization-Server (Remote-MCP-Connector): top-level, anonym
    # erreichbar (`/oauth/*`), plus RFC-8414-Metadaten unter `/.well-known`.
    app.include_router(oauth.router)
    app.include_router(oauth.metadata_router)
    # Billing-SCHREIBSEITE (Webhooks/Checkout) lebt im optionalen `who2be-billing`-
    # Paket (ADR-0029). Build-Zeit-isoliert: On-Prem hat es nicht installiert →
    # der Import schlaegt fehl und es wird nichts registriert. Der Kern kennt das
    # Paket NIE statisch.
    _register_billing_if_present(app, settings)

    @app.get("/v1/health", response_model=Health)
    async def health() -> Health:
        db_status = "ok" if await database.ping() else "unavailable"
        return Health(status="ok", version=__version__, db=db_status)

    return app


configure_logging(get_settings().log_format)
app = create_app()
