"""Geschaeftslogik fuer das Organization-Aggregat (TASK-301).

Listet eigene Orgs, legt Company-Orgs an. Anlage erzeugt atomar einen
Default-Workspace + Admin-Membership, damit die Org nach POST sofort
bedienbar ist.
"""

from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.repositories.organization_repository import OrganizationRepository
from who2be_models import OrganizationCreate, OrganizationRead


class OrganizationService:
    """CRUD-Adapter um das Organization-Repository."""

    def __init__(self, org_repo: OrganizationRepository) -> None:
        self._repo = org_repo

    async def list_for_user(self, user_id: UUID) -> list[OrganizationRead]:
        return await self._repo.list_by_user(user_id)

    async def create(
        self, user_id: UUID, data: OrganizationCreate
    ) -> OrganizationRead:
        try:
            org, _workspace_id = await self._repo.create_company(
                user_id, data.name, data.slug, default_workspace_name="Default"
            )
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization-Slug ist bereits vergeben.",
            ) from exc
        return org
