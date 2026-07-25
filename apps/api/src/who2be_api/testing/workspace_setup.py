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
from who2be_api.core.db import init_connection

_AUTH_USERS_STUB = """
    CREATE SCHEMA IF NOT EXISTS auth;
    CREATE TABLE IF NOT EXISTS auth.users (
        id                  uuid PRIMARY KEY,
        email               text,
        raw_user_meta_data  jsonb,
        encrypted_password  text,
        created_at          timestamptz,
        last_sign_in_at     timestamptz
    );
    -- Defensive: aeltere Test-Runs haben die Tabelle ohne diese Spalten
    -- angelegt; bei geteilter Test-DB sonst Fehler.
    ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email text;
    ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS raw_user_meta_data jsonb;
    ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS encrypted_password text;
    ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS created_at timestamptz;
    ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS last_sign_in_at timestamptz;
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


async def _ensure_workspace(
    conn: asyncpg.Connection, user_id: UUID, content_locale: str = "de"
) -> UUID:
    """Duenner Test-Helper-Wrapper um ``ensure_personal_workspace`` (DRY).

    Stellt den `auth.users`-Stub bereit (nur in Test-DBs noetig) und
    delegiert die eigentliche Seed-Logik an das Prod-Modul.
    ``content_locale`` bestimmt die Sprache der geseedeten Inhalte (ADR-0045).
    """
    await _ensure_auth_users_stub(conn)
    from who2be_api.repositories.workspace_repository import ensure_personal_workspace

    return await ensure_personal_workspace(
        conn, user_id, user_email=None, content_locale=content_locale
    )


async def _connect_with_codec() -> asyncpg.Connection:
    """Test-Connection mit dem gleichen jsonb-Codec wie der Prod-Pool.

    Ohne den Codec akzeptiert asyncpg nur pre-serialisierte JSON-Strings fuer
    jsonb-Spalten — Tests laufen, Prod-Code mit dict-Inputs ueber den Pool
    crasht. Das hat den Double-Encoded-Seed-Bug in `seed_default_templates`
    verdeckt. Test-Setup muss die Prod-Realitaet spiegeln.
    """
    conn = await asyncpg.connect(get_settings().database_url)
    await init_connection(conn)
    return conn


def setup_workspace(user_id: UUID, content_locale: str = "de") -> UUID:
    """Synchrone Convenience-Wrapper fuer Test-Setup."""

    async def _run() -> UUID:
        conn = await _connect_with_codec()
        try:
            return await _ensure_workspace(conn, user_id, content_locale)
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


def seed_auth_user(
    user_id: UUID,
    email: str | None,
    name: str | None,
    preferred_locale: str | None = None,
) -> None:
    """Schreibt eine Zeile in den `auth.users`-Stub (s. `_ensure_auth_users_stub`).

    Genutzt von Dashboard-Tests, um `display_name`-Fallbacks (meta.name →
    Email-Local-Part → User-ID) reproduzierbar abzudecken, sowie von den
    me-Tests fuer die `preferred_locale`-Ableitung der Workspace-Content-
    Sprache (ADR-0045). UPSERT auf id, damit Re-Runs idempotent bleiben."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await _ensure_auth_users_stub(conn)
            meta: dict[str, str] = {}
            if name is not None:
                meta["name"] = name
            if preferred_locale is not None:
                meta["preferred_locale"] = preferred_locale
            meta_json: str | None = None
            if meta:
                import json

                meta_json = json.dumps(meta)
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
