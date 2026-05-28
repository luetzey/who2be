"""Geschaeftslogik fuer das Persona-Aggregat.

Workspace-Pruefung liegt im SQL der Repository-Schicht; der Service
uebersetzt ein fehlendes Ergebnis (`None`) in ein `HTTPException 404`.
"""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.persona_repository import PersonaRepository
from who2be_models import (
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaVersionRead,
    encode_cursor,
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona nicht gefunden.")


class PersonaService:
    """Legt Personae an, liest, listet, aktualisiert und versioniert sie."""

    def __init__(self, persona_repo: PersonaRepository) -> None:
        self._repo = persona_repo

    async def create(self, ctx: WorkspaceContext, data: PersonaCreate) -> PersonaRead:
        return await self._repo.insert(ctx.workspace_id, ctx.user_id, data.name, data.content)

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[PersonaRead], str | None]:
        # `limit + 1`-Peek: gibt es eine Folge-Zeile, codieren wir den
        # Cursor aus der letzten Zeile der Seite — sonst `None` (Ende).
        rows = await self._repo.list_by_workspace(ctx.workspace_id, limit + 1, cursor)
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(self, ctx: WorkspaceContext, persona_id: UUID) -> PersonaRead:
        persona = await self._repo.fetch(ctx.workspace_id, persona_id)
        if persona is None:
            raise _not_found()
        return persona

    async def update(
        self, ctx: WorkspaceContext, persona_id: UUID, data: PersonaUpdate
    ) -> PersonaRead:
        """Erzeugt eine neue Version der Persona."""
        persona = await self._repo.update(
            ctx.workspace_id, ctx.user_id, persona_id, data.name, data.content
        )
        if persona is None:
            raise _not_found()
        return persona

    async def list_versions(
        self, ctx: WorkspaceContext, persona_id: UUID
    ) -> list[PersonaVersionRead]:
        versions = await self._repo.list_versions(ctx.workspace_id, persona_id)
        if versions is None:
            raise _not_found()
        return versions

    async def get_version(
        self, ctx: WorkspaceContext, persona_id: UUID, version: int
    ) -> PersonaVersionRead:
        found = await self._repo.fetch_version(ctx.workspace_id, persona_id, version)
        if found is None:
            raise _not_found()
        return found
