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

import asyncpg
from fastapi import APIRouter, Depends

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.licensing.service import build_entitlement_port
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository, resolve_org_id
from who2be_models import DEFAULT_LOCALE, WhoAmIRead

router = APIRouter(prefix="/whoami", tags=["whoami"])

Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Pool = Annotated[asyncpg.Pool, Depends(get_pool)]


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

    `content_locale` (ADR-0045/WP-D, #361) ist die Content-Sprache DIESES
    Workspaces — der Default fuer neue Elemente, wenn ein `create_*`-Aufruf
    `locale` weglaesst. So kann ein Agent die Workspace-Sprache direkt
    erfragen, statt sie aus bestehenden Elementen zu erschliessen.
    """
    policy = ctx.tool_policy
    unrestricted = policy is None

    org_id = await resolve_org_id(pool, ctx.workspace_id)
    entitlement = await build_entitlement_port(pool, get_settings()).resolve(org_id)
    # Leitplanke: kein SQL in Services/Routern — der Lookup laeuft ueber das
    # Workspace-Repository (spiegelt `resolve_content_locale`). Ein fehlender
    # Workspace waere hier defensiv (Membership-Check in `get_current_workspace`
    # hat den Zugriff bereits validiert) und faellt auf `DEFAULT_LOCALE` zurueck.
    workspace = await PgWorkspaceRepository(pool).fetch(ctx.workspace_id)
    content_locale = workspace.content_locale if workspace is not None else DEFAULT_LOCALE

    return WhoAmIRead(
        user_id=ctx.user_id,
        workspace_id=ctx.workspace_id,
        role=ctx.role,
        is_api_token=ctx.is_api_token,
        agent_id=ctx.agent_id,
        unrestricted=unrestricted,
        capabilities=None if policy is None else policy.granted_capabilities(),
        read_scopes=None if policy is None else policy.read_scopes(),
        transition_grants=None if policy is None else policy.transition_grants,
        write_tags=None if policy is None else policy.write_tags,
        write_rate_limit=None if policy is None else policy.write_rate_limit,
        memory_mode=None if policy is None else policy.memory_mode,
        memory_directive=None if policy is None else policy.memory_directive,
        features=sorted(entitlement.features),
        content_locale=content_locale,
    )
