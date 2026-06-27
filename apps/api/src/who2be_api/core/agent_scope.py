"""Berechnet die „zugewiesenen" Lese-Mengen eines Agenten (Read-Scoping).

Wenn die Tool-Policy eines Agenten `playbook_read`/`resource_read` auf
``assigned`` setzt, darf der Agent nur die ueber seine Persona zugewiesenen
Playbooks und die daraus erreichbaren Resources sehen — nicht den ganzen
Workspace. Diese Modul-Funktionen liefern die erlaubten ID-Mengen, die die
Read-Services dann als `restrict_ids`-Filter an die Repositories durchreichen.

Erreichbarkeit (transitiv, damit Composite-Playbooks/Sub-Resources nutzbar
bleiben):
- **Playbooks**: die der Persona direkt verknuepften Playbooks plus deren
  Composition-Closure (`playbook_composition`).
- **Resources**: alle Resources, die von einem zugewiesenen Playbook verlinkt
  sind (`playbook_resource_link`), plus deren Sub-Resource-Closure
  (`resource_composition`).
"""

from __future__ import annotations

from typing import TypeAlias
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext
from who2be_models import ReadScope

# Persona → direkt verknuepfte Playbooks + transitive Composition-Kinder.
_ASSIGNED_PLAYBOOKS_SQL = """
WITH RECURSIVE seed(id) AS (
    SELECT pp.playbook_id
    FROM agent a
    JOIN persona_playbook pp ON pp.persona_id = a.persona_id
    WHERE a.id = $1 AND a.workspace_id = $2
),
closure(id) AS (
    SELECT id FROM seed
    UNION
    SELECT pc.child_id
    FROM playbook_composition pc
    JOIN closure c ON pc.parent_id = c.id
    WHERE pc.workspace_id = $2
)
SELECT id FROM closure
"""

# Zugewiesene Playbooks → verlinkte Resources + transitive Sub-Resource-Kinder.
_ASSIGNED_RESOURCES_SQL = """
WITH RECURSIVE pb(id) AS (
    SELECT pp.playbook_id
    FROM agent a
    JOIN persona_playbook pp ON pp.persona_id = a.persona_id
    WHERE a.id = $1 AND a.workspace_id = $2
    UNION
    SELECT pc.child_id
    FROM playbook_composition pc
    JOIN pb ON pc.parent_id = pb.id
    WHERE pc.workspace_id = $2
),
seed(id) AS (
    SELECT prl.resource_id
    FROM playbook_resource_link prl
    WHERE prl.workspace_id = $2 AND prl.playbook_id IN (SELECT id FROM pb)
),
closure(id) AS (
    SELECT id FROM seed
    UNION
    SELECT rc.child_id
    FROM resource_composition rc
    JOIN closure c ON rc.parent_id = c.id
    WHERE rc.workspace_id = $2
)
SELECT id FROM closure
"""


# `Pool | Connection`: die REST-Services reichen den Pool durch, der Render-Pfad
# (Placeholder-Resolver) eine bereits acquirte Single-Connection — beide haben
# `.fetch` mit identischer Signatur.
_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection


async def assigned_playbook_ids(pool: _Fetcher, workspace_id: UUID, agent_id: UUID) -> set[UUID]:
    """IDs der dem Agenten (ueber seine Persona) zugewiesenen Playbooks."""
    rows = await pool.fetch(_ASSIGNED_PLAYBOOKS_SQL, agent_id, workspace_id)
    return {row["id"] for row in rows}


async def assigned_resource_ids(pool: _Fetcher, workspace_id: UUID, agent_id: UUID) -> set[UUID]:
    """IDs der aus den zugewiesenen Playbooks erreichbaren Resources."""
    rows = await pool.fetch(_ASSIGNED_RESOURCES_SQL, agent_id, workspace_id)
    return {row["id"] for row in rows}


def require_read_flag(ctx: WorkspaceContext, flag: str, domain: str) -> None:
    """An/Aus-Lesegate (No-Op fuer ungebundene Tokens).

    Fuer Reads ohne Scope-Abstufung (`persona_read`): ist der Token an einen
    Agenten gebunden und das Flag aus, wirft das ein 403.
    """
    policy = ctx.tool_policy
    if policy is None:
        return
    if not getattr(policy, flag):
        raise _tool_unavailable(domain)


def agent_read_restrict(ctx: WorkspaceContext) -> set[UUID] | None:
    """`restrict_ids` fuer Agent-Reads gemaess `agent_read`-Scope (DB-frei).

    `None` = keine Einschraenkung (ungebundener Token/Mensch oder Scope `all`).
    Bei `assigned` die Menge ``{ctx.agent_id}`` — der Agent sieht nur sich selbst.
    Bei `none` ein 403, weil das Tool fuer den Agenten gar nicht verfuegbar ist.
    """
    policy = ctx.tool_policy
    if policy is None or ctx.agent_id is None:
        return None
    if policy.agent_read == ReadScope.all:
        return None
    if policy.agent_read == ReadScope.none:
        raise _tool_unavailable("Agenten")
    return {ctx.agent_id}


def _tool_unavailable(domain: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Dieser Agent darf keine {domain} lesen. "
            "Der Workspace-Besitzer kann den Lesezugriff in der Agent-Konfiguration freischalten."
        ),
    )


async def playbook_read_restrict(pool: asyncpg.Pool, ctx: WorkspaceContext) -> list[UUID] | None:
    """`restrict_ids` fuer Playbook-Reads gemaess Policy.

    `None` = keine Einschraenkung (ungebundener Token oder Scope `all`). Bei
    `assigned` die sortierte Liste der zugewiesenen Playbook-IDs (ggf. leer);
    bei `none` ein 403, weil das Tool fuer den Agenten gar nicht verfuegbar ist.
    """
    policy = ctx.tool_policy
    if policy is None or ctx.agent_id is None:
        return None
    if policy.playbook_read == ReadScope.all:
        return None
    if policy.playbook_read == ReadScope.none:
        raise _tool_unavailable("Playbooks")
    return sorted(await assigned_playbook_ids(pool, ctx.workspace_id, ctx.agent_id))


async def resource_read_restrict(pool: asyncpg.Pool, ctx: WorkspaceContext) -> list[UUID] | None:
    """`restrict_ids` fuer Resource-Reads gemaess Policy (siehe playbook-Variante)."""
    policy = ctx.tool_policy
    if policy is None or ctx.agent_id is None:
        return None
    if policy.resource_read == ReadScope.all:
        return None
    if policy.resource_read == ReadScope.none:
        raise _tool_unavailable("Resources")
    return sorted(await assigned_resource_ids(pool, ctx.workspace_id, ctx.agent_id))


async def visible_playbook_ids(
    pool: asyncpg.Pool | None, ctx: WorkspaceContext
) -> set[UUID] | None:
    """Sichtbare Playbook-IDs fuer Sekundaer-Reads (Composition/Links/Usages).

    Diese Reads laufen nicht ueber die `restrict_ids`-Repos der Haupt-Lesepfade
    und brauchen daher denselben `assigned`-Scope explizit: Gate die per-ID
    abgefragte Entitaet bzw. filtere zurueckgegebene Listen gegen diese Menge.

    `None` = keine Einschraenkung (ungebundener Token oder Scope `all`; oder
    Test-Fake ohne Pool). Sonst die Menge der zugewiesenen Playbook-IDs. Bei
    Scope `none` wirft `playbook_read_restrict` ein 403.
    """
    if pool is None:
        return None
    restrict = await playbook_read_restrict(pool, ctx)
    return None if restrict is None else set(restrict)


async def visible_resource_ids(
    pool: asyncpg.Pool | None, ctx: WorkspaceContext
) -> set[UUID] | None:
    """Sichtbare Resource-IDs fuer Sekundaer-Reads (siehe `visible_playbook_ids`)."""
    if pool is None:
        return None
    restrict = await resource_read_restrict(pool, ctx)
    return None if restrict is None else set(restrict)
