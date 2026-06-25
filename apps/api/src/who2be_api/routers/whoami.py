"""Identitaets-/Capability-Introspektion (`whoami`, #253).

Pfad: `GET /v1/workspaces/{workspace_id}/whoami` (Prefix kommt aus `main.py`).
Reiner Read, **bewusst ohne** `require_role`/`require_capability`-Gate — jeder
Aufrufer mit Workspace-Zugriff (Viewer aufwaerts) darf seine *eigene* Identitaet
abfragen. Die Membership-/Token-Autorisierung uebernimmt `get_current_workspace`.

Liefert genug, damit ein Agent (oder die Web-UI) ohne Raten weiss, wer er ist
und was er darf: Rolle, Agent-Bindung, gewaehrte Write-Capabilities, Read-Scopes
und die org-weiten Entitlement-Features.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.licensing.service import build_entitlement_port
from who2be_models import WhoAmIRead

router = APIRouter(prefix="/whoami", tags=["whoami"])

Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Pool = Annotated[asyncpg.Pool, Depends(get_pool)]


async def _resolve_org_id(pool: asyncpg.Pool, workspace_id: UUID) -> UUID:
    """Org des Workspace fuer die org-scoped Entitlement-Aufloesung (Muster
    `routers/entitlement.py`). Ein Workspace ohne Org ist ein inkonsistenter
    Zustand → 403 statt stiller Voll-/Null-Annahme."""
    org_id = await pool.fetchval("SELECT org_id FROM workspace WHERE id = $1", workspace_id)
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace ohne Organisation.",
        )
    assert isinstance(org_id, UUID)
    return org_id


@router.get("")
async def whoami(ctx: Ctx, pool: Pool) -> WhoAmIRead:
    """Identitaet + effektive Berechtigungen des aufrufenden Principals.

    `tool_policy is None` (Mensch/JWT oder ungebundener API-Token) bedeutet
    **"keine Pro-Agent-Restriktion"**, NICHT "nichts erlaubt" — dann gilt allein
    das Rollen-Gate. Wir bilden das explizit als `unrestricted=True` mit
    `capabilities=None`/`read_scopes=None` ab, damit `whoami` nicht faelschlich
    "0 Capabilities" fuer einen Menschen meldet. Nur ein agent-gebundener Token
    traegt eine konkrete Policy → dann werden die gewaehrten Capabilities und
    Read-Scopes ausgegeben.

    `features` sind die org-weiten Entitlement-Features (org-scoped) — orthogonal
    zur Pro-Agent-Policy und auch fuer ungated Aufrufer relevant.
    """
    policy = ctx.tool_policy
    unrestricted = policy is None

    org_id = await _resolve_org_id(pool, ctx.workspace_id)
    entitlement = await build_entitlement_port(pool, get_settings()).resolve(org_id)

    return WhoAmIRead(
        user_id=ctx.user_id,
        workspace_id=ctx.workspace_id,
        role=ctx.role,
        is_api_token=ctx.is_api_token,
        agent_id=ctx.agent_id,
        unrestricted=unrestricted,
        capabilities=None if policy is None else policy.granted_capabilities(),
        read_scopes=None if policy is None else policy.read_scopes(),
        features=sorted(entitlement.features),
    )
