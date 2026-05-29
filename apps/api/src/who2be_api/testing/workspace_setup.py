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

_AUTH_USERS_STUB = """
    CREATE SCHEMA IF NOT EXISTS auth;
    CREATE TABLE IF NOT EXISTS auth.users (
        id                  uuid PRIMARY KEY,
        email               text,
        raw_user_meta_data  jsonb
    );
"""


async def _ensure_auth_users_stub(conn: asyncpg.Connection) -> None:
    """Spiegelt das Schema-Stueck, das GoTrue in Prod selbst anlegt.

    Migrationen referenzieren `auth.users` bewusst nicht (das Schema ist
    GoTrue-eigen), aber Read-Queries wie das Dashboard joinen darauf, um
    Anzeigenamen aufzuloesen. Im Pytest-Container existiert das Schema
    nicht — der Stub legt eine minimale Tabelle an, die das echte Schema
    vertraeglich erweitert (Spalten sind eine Teilmenge der GoTrue-Variante).
    """
    await conn.execute(_AUTH_USERS_STUB)


async def _ensure_workspace(conn: asyncpg.Connection, user_id: UUID) -> UUID:
    """Legt — falls noch nicht da — eine Personal-Org + Workspace fuer den
    User an und gibt die `workspace_id` zurueck. Slug-Konvention identisch zur
    Migration 0013, damit Re-Runs keine Duplikate erzeugen.
    """
    await _ensure_auth_users_stub(conn)
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
                "DELETE FROM organization WHERE kind = 'personal' AND slug = ANY($1::text[])",
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
            # Stub-Tabelle existiert nur, wenn ein vorheriger Test sie angelegt
            # hat; vor dem DELETE absichern, damit das Cleanup robust bleibt.
            await _ensure_auth_users_stub(conn)
            await conn.execute(
                "DELETE FROM auth.users WHERE id = ANY($1::uuid[])",
                user_ids,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def fresh_user_id() -> UUID:
    """Eindeutige Test-User-UUID; deterministischer Prefix erleichtert das
    Sichten in einer geteilten Test-DB."""
    return UUID(bytes=secrets.token_bytes(16))


def seed_auth_user(user_id: UUID, email: str | None, name: str | None) -> None:
    """Schreibt eine Zeile in den `auth.users`-Stub (s. `_ensure_auth_users_stub`).

    Genutzt von Dashboard-Tests, um `display_name`-Fallbacks (meta.name →
    Email-Local-Part → User-ID) reproduzierbar abzudecken. UPSERT auf id,
    damit Re-Runs idempotent bleiben."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await _ensure_auth_users_stub(conn)
            meta_json: str | None = None
            if name is not None:
                import json

                meta_json = json.dumps({"name": name})
            await conn.execute(
                "INSERT INTO auth.users (id, email, raw_user_meta_data) "
                "VALUES ($1, $2, $3::jsonb) "
                "ON CONFLICT (id) DO UPDATE SET "
                "email = excluded.email, "
                "raw_user_meta_data = excluded.raw_user_meta_data",
                user_id,
                email,
                meta_json,
            )
        finally:
            await conn.close()

    asyncio.run(_run())
