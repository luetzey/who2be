"""Persistenz fuer `GET /v1/me` (TASK-301).

Aggregiert alle Organizations + Workspaces, in denen der User Member ist,
plus die jeweilige Rolle. Default-Workspace = aelteste Membership des Users
(stabile Reihenfolge nach `workspace_member.joined_at` und Tie-Breaker
`workspace_id`).
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import MeOrganization, MeRead, MeWorkspace


class MeRepository(Protocol):
    """Service-seitige Abstraktion fuer den `/v1/me`-Read."""

    async def fetch(self, user_id: UUID) -> MeRead: ...


class PgMeRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def fetch(self, user_id: UUID) -> MeRead:
        rows = await self._pool.fetch(
            "SELECT o.id AS org_id, o.name AS org_name, o.slug AS org_slug, "
            "o.kind AS org_kind, o.created_at AS org_created_at, "
            "w.id AS workspace_id, w.name AS workspace_name, w.slug AS workspace_slug, "
            "m.role AS workspace_role, m.joined_at AS workspace_joined_at "
            "FROM workspace_member m "
            "JOIN workspace w ON w.id = m.workspace_id "
            "JOIN organization o ON o.id = w.org_id "
            "WHERE m.user_id = $1 "
            "ORDER BY o.created_at ASC, o.id ASC, m.joined_at ASC, w.id ASC",
            user_id,
        )
        orgs: dict[UUID, MeOrganization] = {}
        default_workspace_id: UUID | None = None
        for row in rows:
            org_id = row["org_id"]
            if org_id not in orgs:
                orgs[org_id] = MeOrganization(
                    id=org_id,
                    name=row["org_name"],
                    slug=row["org_slug"],
                    kind=row["org_kind"],
                    workspaces=[],
                )
            orgs[org_id].workspaces.append(
                MeWorkspace(
                    id=row["workspace_id"],
                    name=row["workspace_name"],
                    slug=row["workspace_slug"],
                    role=row["workspace_role"],
                )
            )
            if default_workspace_id is None:
                default_workspace_id = row["workspace_id"]
        return MeRead(
            user_id=user_id,
            default_workspace_id=default_workspace_id,
            organizations=list(orgs.values()),
            has_password=await self._has_password(user_id),
        )

    async def _has_password(self, user_id: UUID) -> bool:
        """`auth.users.encrypted_password IS NOT NULL` — frisch eingeladene
        Magic-Link-User haben `NULL`, bis sie auf `/onboarding/set-password`
        ein Passwort setzen. Wenn das `auth`-Schema (noch) nicht existiert
        — z. B. in einer reinen API-Test-DB ohne GoTrue — gilt `False`."""
        try:
            value = await self._pool.fetchval(
                "SELECT encrypted_password IS NOT NULL "
                "FROM auth.users WHERE id = $1",
                user_id,
            )
        except asyncpg.PostgresError:
            return False
        return bool(value)
