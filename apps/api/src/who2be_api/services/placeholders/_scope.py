"""Read-Scoping fuer die Placeholder-Expansion (Render-Pfad).

Anders als die REST-Services arbeiten die Resolver mit `RenderContext` (kein
`WorkspaceContext`) und einer bereits acquirten `asyncpg.Connection`. Diese
Helfer liefern die fuer den gerenderten Agenten sichtbare ID-Menge, damit
eingebettete Inhalts-Pills (`{{playbook:id}}`/`{{resource:id}}`) und der
Resource-Katalog nicht ueber den `assigned`-Scope hinaus expandieren.

Rueckgabe:
- ``None``  = keine Einschraenkung (kein Agent-Render / Scope ``all`` / Mensch-
  Preview) — Verhalten unveraendert.
- ``set()`` = nichts sichtbar (Scope ``none``): Katalog/Pill bleiben leer (kein
  403 — der eigene System-Prompt soll trotzdem rendern, nur ohne fremde Inhalte).
- sonst die zugewiesene ID-Menge.
"""

from __future__ import annotations

from typing import TypeAlias
from uuid import UUID

import asyncpg

from who2be_api.core.agent_scope import assigned_playbook_ids, assigned_resource_ids
from who2be_api.services.placeholders._core import RenderContext
from who2be_models import ReadScope

_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection


async def render_visible_playbook_ids(db: _Fetcher, ctx: RenderContext) -> set[UUID] | None:
    policy = ctx.tool_policy
    if policy is None or ctx.agent_id is None or policy.playbook_read == ReadScope.all:
        return None
    if policy.playbook_read == ReadScope.none:
        return set()
    return await assigned_playbook_ids(db, ctx.workspace_id, ctx.agent_id)


async def render_visible_resource_ids(db: _Fetcher, ctx: RenderContext) -> set[UUID] | None:
    policy = ctx.tool_policy
    if policy is None or ctx.agent_id is None or policy.resource_read == ReadScope.all:
        return None
    if policy.resource_read == ReadScope.none:
        return set()
    return await assigned_resource_ids(db, ctx.workspace_id, ctx.agent_id)
