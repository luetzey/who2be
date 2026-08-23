"""Aggregations-Service fuer `GET /v1/me` (TASK-301)."""

from uuid import UUID

from who2be_api.repositories.me_repository import MeRepository
from who2be_models import MeRead


class MeService:
    """Liefert dem aktuellen User Organizations + Workspaces + Default-WS."""

    def __init__(self, me_repo: MeRepository) -> None:
        self._repo = me_repo

    async def fetch(self, user_id: UUID, token_workspace_id: UUID | None = None) -> MeRead:
        """Memberships des Users plus die Workspace-Bindung des Tokens.

        `token_workspace_id` stammt aus dem Principal (nur API-Token-Pfad) und
        wird durchgereicht statt im Repository ermittelt: es ist eine Eigenschaft
        der *Credential*, keine der Membership-Abfrage.
        """
        me = await self._repo.fetch(user_id)
        if token_workspace_id is None:
            return me
        return me.model_copy(update={"token_workspace_id": token_workspace_id})
