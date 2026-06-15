"""Geschaeftslogik fuer die Reverse-Lookups (Phase 3-A).

Mappt fehlende Playbook-/Resource-IDs auf 404. Workspace-Check liegt in der
Repo-Schicht; der Service liest nur und braucht keinen Role-Gate (alle
Mitglieder duerfen Backlinks sehen). Agent-Tokens mit `assigned`-Read-Scope
sehen Backlinks aber nur fuer ihnen zugewiesene Entitaeten (sonst 404).
"""

from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.agent_scope import visible_playbook_ids, visible_resource_ids
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.usage_repository import UsageRepository
from who2be_models import PlaybookUsage, ResourceUsage


def _playbook_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden.")


def _resource_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource nicht gefunden.")


class UsageService:
    """Liest die Backlinks fuer ein Playbook bzw. eine Resource."""

    def __init__(self, repo: UsageRepository, pool: asyncpg.Pool | None = None) -> None:
        self._repo = repo
        self._pool = pool

    async def list_playbook_usages(
        self, ctx: WorkspaceContext, playbook_id: UUID
    ) -> list[PlaybookUsage]:
        if not await self._repo.playbook_belongs_to(ctx.workspace_id, playbook_id):
            raise _playbook_not_found()
        # Read-Scoping: ein `assigned`-Agent darf Backlinks nur fuer ihm
        # sichtbare Playbooks abfragen — sonst 404 (kein Workspace-Enumerieren).
        scope = await visible_playbook_ids(self._pool, ctx)
        if scope is not None and playbook_id not in scope:
            raise _playbook_not_found()
        usages = await self._repo.list_playbook_usages(ctx.workspace_id, playbook_id)
        # Die Items sind Personas (persona_id/-name) — eine andere Sicht-Achse als
        # `assigned`. Darf der Agent gar keine Personas lesen, leaken wir auch
        # ueber den Backlink keine Persona-Namen.
        policy = ctx.tool_policy
        if policy is not None and not policy.persona_read:
            return []
        return usages

    async def list_resource_usages(
        self, ctx: WorkspaceContext, resource_id: UUID
    ) -> list[ResourceUsage]:
        if not await self._repo.resource_belongs_to(ctx.workspace_id, resource_id):
            raise _resource_not_found()
        scope = await visible_resource_ids(self._pool, ctx)
        if scope is not None and resource_id not in scope:
            raise _resource_not_found()
        usages = await self._repo.list_resource_usages(ctx.workspace_id, resource_id)
        # Items sind referenzierende Playbooks — auf die sichtbare Playbook-Menge
        # filtern, sonst leaken fremde `playbook_name`/`block_count`.
        pb_scope = await visible_playbook_ids(self._pool, ctx)
        if pb_scope is not None:
            usages = [u for u in usages if u.playbook_id in pb_scope]
        return usages
