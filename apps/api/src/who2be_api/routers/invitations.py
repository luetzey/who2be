"""REST-Endpunkte fuer Workspace-Invitations.

Zwei Router:
- `router` (Workspace-scoped, admin-only): erstellen/listen/widerrufen.
  Der 201-Response traegt den Klartext-Token genau einmal — der Caller
  verschickt den Mail-Link (best-effort) bzw. teilt ihn manuell.
- `accept_router` (top-level, **anonym authentifiziert**): ein anderer User
  akzeptiert die Einladung per Klartext-Token und wird Mitglied.
  Single-use; akzeptiert/widerrufen/abgelaufen → 410 Gone.

Der Token reist im Request-Body (`POST /v1/invitations/accept`), nicht im
Pfad: ein Pfad landet in jedem Access-Log zwischen Browser und API, ein Body
nicht. Der alte Pfad `POST /v1/invitations/{token}/accept` bleibt fuer bereits
verschickte Links uebergangsweise erreichbar (siehe `_LEGACY_SUNSET`).
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import (
    CurrentPrincipal,
    WorkspaceContext,
    deny_agent_bound_workspace_admin,
    get_current_human_principal,
    get_current_workspace,
    require_role,
)
from who2be_api.repositories.audit_log_repository import PgAuditLogRepository
from who2be_api.repositories.invitation_repository import PgInvitationRepository
from who2be_api.services.audit_service import AuditService
from who2be_api.services.invitation_service import InvitationService
from who2be_models import (
    InvitationAccept,
    InvitationCreate,
    InvitationCreated,
    InvitationRead,
    WorkspaceRole,
)

router = APIRouter(prefix="/invitations", tags=["invitations"])
accept_router = APIRouter(prefix="/v1/invitations", tags=["invitations"])

# Ablaufdatum des Legacy-Pfads `POST /v1/invitations/{token}/accept`.
# Bis dahin sind alle Links aus der Zeit vor dem Body-Endpunkt laengst
# abgelaufen (Einladungen gelten sieben Tage, `invitation_service._EXPIRY`),
# und die Web-App ruft nur noch den Body-Endpunkt. Danach wird die Route
# entfernt. Format: HTTP-date, wie RFC 8594 es fuer den `Sunset`-Header
# vorschreibt.
_LEGACY_SUNSET = "Thu, 31 Dec 2026 23:59:59 GMT"


def get_invitation_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> InvitationService:
    return InvitationService(
        PgInvitationRepository(pool),
        audit_service=AuditService(PgAuditLogRepository()),
        pool=pool,
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Principal = Annotated[CurrentPrincipal, Depends(get_current_human_principal)]
Service = Annotated[InvitationService, Depends(get_invitation_service)]


class InvitationAcceptResult(BaseModel):
    """Antwort auf einen erfolgreichen Accept — der beigetretene Workspace."""

    workspace_id: UUID


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_invitation(
    request: Request, data: InvitationCreate, ctx: Ctx, service: Service
) -> InvitationCreated:
    require_role(ctx, WorkspaceRole.admin)
    # Zusaetzlich zum Rollen-Gate: ein agent-gebundener Token mit
    # Rollen-Snapshot `admin` koennte sich hier sonst eine Admin-Einladung
    # (samt Klartext-Token im 201-Body) ausstellen und damit seine
    # Pro-Agent-Policy umgehen.
    deny_agent_bound_workspace_admin(ctx)
    return await service.create(ctx, data)


@router.get("")
async def list_invitations(ctx: Ctx, service: Service) -> list[InvitationRead]:
    require_role(ctx, WorkspaceRole.admin)
    deny_agent_bound_workspace_admin(ctx)
    return await service.list_pending(ctx)


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def revoke_invitation(
    request: Request, invitation_id: UUID, ctx: Ctx, service: Service
) -> None:
    require_role(ctx, WorkspaceRole.admin)
    deny_agent_bound_workspace_admin(ctx)
    await service.revoke(ctx, invitation_id)


@accept_router.post("/accept")
@limiter.limit(write_limit)
async def accept_invitation_by_body(
    request: Request, data: InvitationAccept, principal: Principal, service: Service
) -> InvitationAcceptResult:
    """Nimmt eine Einladung an; der Klartext-Token steht im Body.

    Der Aufrufer muss eine Email-Adresse im Login tragen, die zur Einladung
    passt — sonst 403 (`invitation_email_required` bzw.
    `invitation_email_mismatch`).
    """
    workspace_id = await service.accept(data.token, principal.user_id, principal.email)
    return InvitationAcceptResult(workspace_id=workspace_id)


@accept_router.post("/{token}/accept", deprecated=True)
@limiter.limit(write_limit)
async def accept_invitation(
    request: Request, response: Response, token: str, principal: Principal, service: Service
) -> InvitationAcceptResult:
    """Veraltet: Token im Pfad. Nachfolger ist `POST /v1/invitations/accept`.

    Bleibt bis zum Datum im `Sunset`-Header erreichbar, damit bereits
    verschickte Einladungslinks weiter funktionieren; es gelten dieselben
    Pruefungen wie beim Body-Endpunkt.
    """
    response.headers["Sunset"] = _LEGACY_SUNSET
    response.headers["Link"] = '</v1/invitations/accept>; rel="successor-version"'
    workspace_id = await service.accept(token, principal.user_id, principal.email)
    return InvitationAcceptResult(workspace_id=workspace_id)
