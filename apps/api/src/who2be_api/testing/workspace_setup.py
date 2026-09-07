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

    Die ``conn.transaction()``-Klammer ist keine Test-Eigenheit und kein
    RLS-Workaround, sondern dasselbe, was der einzige Produktiv-Aufrufer
    (`PgMeRepository.fetch`) mit derselben Begruendung tut: der Seed besteht
    aus mehreren Inserts (Org, Member, Workspace, Default-Templates, Agenten,
    Chunks) und gehoert deshalb atomar — bricht er in der Mitte ab, darf er
    keinen Teilzustand hinterlassen (keine Org ohne Workspace, kein Workspace
    ohne Membership). Die ON-CONFLICT-Klauseln in `ensure_personal_workspace`
    machen den Re-Lauf idempotent. Der Stub bleibt bewusst ausserhalb: er ist
    Schema-Vorbedingung, nicht Teil des Seeds.
    """
    await _ensure_auth_users_stub(conn)
    from who2be_api.repositories.workspace_repository import ensure_personal_workspace

    async with conn.transaction():
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
    persona/playbook/api_token/workspace ab.

    `agent_access_log` haengt bewusst NICHT am Cascade (Migration 0080,
    Security-Review H5: sonst raeumt ein Agent-Delete das Compliance-Log ab).
    Das Test-Cleanup ist — wie `core/purge.py` — ein OWNER-Pfad und loescht
    die Zeilen deshalb selbst, bevor die Org-CASCADE die Agenten erreicht.

    Die ``conn.transaction()``-Klammer liegt aus demselben Grund um die vier
    `DELETE`s wie die in `_ensure_workspace` (#480): der Abbau ist mehrstufig
    und gehoert deshalb atomar. Ohne sie laeuft jedes `DELETE` in einer
    eigenen impliziten Autocommit-Transaktion — bricht der Lauf nach dem
    ersten ab (Timeout, Ctrl-C, gekappte Verbindung), ist das Compliance-Log
    geloescht, seine Organisation steht aber noch. Das ist ein Zwischenzustand,
    den kein Produktivpfad erzeugen kann und den der naechste Testlauf vorfaende.
    Die Klammer umfasst bewusst alle vier: die Abhaengigkeit laeuft ueber alle
    vier, eine Teilklammer wuerde den Zwischenzustand nur verschieben. Die
    Reihenfolge bleibt unveraendert (`agent_access_log` vor der Org-CASCADE) —
    die Klammer entscheidet nur, ob ein halber Abbau sichtbar werden kann.

    Der `auth.users`-Teil bleibt bewusst ausserhalb, wie der Stub in
    `_ensure_workspace`: das `CREATE TABLE IF NOT EXISTS` ist idempotente
    Schema-Vorbedingung (DDL) und die Stub-Zeile gehoert zu keiner der vier
    abhaengigen Tabellen.
    """

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            slugs = [str(uid) for uid in user_ids]
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM agent_access_log WHERE workspace_id IN ("
                    "  SELECT w.id FROM workspace w"
                    "  JOIN organization o ON o.id = w.org_id"
                    "  WHERE o.kind = 'personal' AND o.slug = ANY($1::text[]))",
                    slugs,
                )
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
