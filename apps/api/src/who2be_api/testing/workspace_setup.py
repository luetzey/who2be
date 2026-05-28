"""Test-Helper: Personal-Org/Workspace fuer eine Test-owner_id seeden.

Die Integration-Tests in `test_personas.py`/`test_playbooks.py`/`test_tokens.py`
brauchen pro Test-User einen passenden Workspace (Phase 2.1a-2 Schema-Lock:
`persona.workspace_id NOT NULL`). Statt das Setup-Boilerplate dreimal zu
duplizieren, lebt es hier zentral.
"""

import asyncio
import secrets
from uuid import UUID

import asyncpg

from who2be_api.core.config import get_settings


async def _ensure_workspace(conn: asyncpg.Connection, user_id: UUID) -> UUID:
    """Legt — falls noch nicht da — eine Personal-Org + Workspace fuer den
    User an und gibt die `workspace_id` zurueck. Slug-Konvention identisch zur
    Migration 0013, damit Re-Runs keine Duplikate erzeugen.
    """
    org_id = await conn.fetchval(
        "INSERT INTO organization (name, slug, kind) "
        "VALUES ('Personal', $1, 'personal') "
        "ON CONFLICT (kind, slug) DO UPDATE SET name = excluded.name "
        "RETURNING id",
        str(user_id),
    )
    await conn.execute(
        "INSERT INTO org_member (org_id, user_id, role) VALUES ($1, $2, 'owner') "
        "ON CONFLICT (org_id, user_id) DO NOTHING",
        org_id,
        user_id,
    )
    workspace_id: UUID = await conn.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'Personal', 'personal') "
        "ON CONFLICT (org_id, slug) DO UPDATE SET name = excluded.name "
        "RETURNING id",
        org_id,
    )
    await conn.execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) "
        "VALUES ($1, $2, 'admin') ON CONFLICT (workspace_id, user_id) DO NOTHING",
        workspace_id,
        user_id,
    )
    return workspace_id


def setup_workspace(user_id: UUID) -> UUID:
    """Synchrone Convenience-Wrapper fuer Test-Setup."""

    async def _run() -> UUID:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await _ensure_workspace(conn, user_id)
        finally:
            await conn.close()

    return asyncio.run(_run())


def cleanup_workspaces(user_ids: list[UUID]) -> None:
    """Loescht Memberships und (Personal-)Orgs der Test-User, CASCADE raeumt
    persona/playbook/api_token/workspace ab."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            slugs = [str(uid) for uid in user_ids]
            await conn.execute(
                "DELETE FROM organization WHERE kind = 'personal' "
                "AND slug = ANY($1::text[])",
                slugs,
            )
            await conn.execute(
                "DELETE FROM org_member WHERE user_id = ANY($1::uuid[])",
                user_ids,
            )
            await conn.execute(
                "DELETE FROM workspace_member WHERE user_id = ANY($1::uuid[])",
                user_ids,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def fresh_user_id() -> UUID:
    """Eindeutige Test-User-UUID; deterministischer Prefix erleichtert das
    Sichten in einer geteilten Test-DB."""
    return UUID(bytes=secrets.token_bytes(16))
