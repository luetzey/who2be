"""Aggregations-Service fuer `GET /v1/me` (TASK-301)."""

from uuid import UUID

from who2be_api.repositories.me_repository import MeRepository
from who2be_models import MeRead


class MeService:
    """Liefert dem aktuellen User Organizations + Workspaces + Default-WS."""

    def __init__(self, me_repo: MeRepository) -> None:
        self._repo = me_repo

    async def fetch(self, user_id: UUID) -> MeRead:
        return await self._repo.fetch(user_id)
