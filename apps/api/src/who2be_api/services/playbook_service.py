"""Geschaeftslogik fuer das Playbook-Aggregat.

Owner-Pruefung liegt im SQL der Repository-Schicht; der Service uebersetzt
ein fehlendes Ergebnis (`None`) in ein `HTTPException 404`.
"""

from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.repositories.playbook_repository import PlaybookRepository
from who2be_models import (
    PlaybookCreate,
    PlaybookRead,
    PlaybookUpdate,
    PlaybookVersionRead,
)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Playbook nicht gefunden."
    )


class PlaybookService:
    """Legt Playbooks an, liest, listet (mit Filtern), aktualisiert sie."""

    def __init__(self, playbook_repo: PlaybookRepository) -> None:
        self._repo = playbook_repo

    async def create(self, owner_id: UUID, data: PlaybookCreate) -> PlaybookRead:
        return await self._repo.insert(owner_id, data.name, data.content)

    async def list_all(
        self, owner_id: UUID, tag: str | None, trigger: str | None
    ) -> list[PlaybookRead]:
        return await self._repo.list_by_owner(owner_id, tag, trigger)

    async def get(self, owner_id: UUID, playbook_id: UUID) -> PlaybookRead:
        playbook = await self._repo.fetch(owner_id, playbook_id)
        if playbook is None:
            raise _not_found()
        return playbook

    async def update(
        self, owner_id: UUID, playbook_id: UUID, data: PlaybookUpdate
    ) -> PlaybookRead:
        """Erzeugt eine neue Version des Playbooks."""
        playbook = await self._repo.update(
            owner_id, playbook_id, data.name, data.content
        )
        if playbook is None:
            raise _not_found()
        return playbook

    async def list_versions(
        self, owner_id: UUID, playbook_id: UUID
    ) -> list[PlaybookVersionRead]:
        versions = await self._repo.list_versions(owner_id, playbook_id)
        if versions is None:
            raise _not_found()
        return versions

    async def get_version(
        self, owner_id: UUID, playbook_id: UUID, version: int
    ) -> PlaybookVersionRead:
        found = await self._repo.fetch_version(owner_id, playbook_id, version)
        if found is None:
            raise _not_found()
        return found
