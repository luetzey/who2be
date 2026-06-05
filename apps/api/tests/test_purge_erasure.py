"""Integrationstest fuer die Erasure-Vollstaendigkeit (WP-D, ADR-0031).

Beweist auf der echten DB (Owner-Verbindung — wie der Purge-Job):
- `status_history.changed_by` und `audit_log.actor_id` des geloeschten Users
  werden auf den Sentinel `00000000-0000-0000-0000-000000000000` gesetzt
  (anonymisiert, nicht geloescht — Audit-Integritaet bleibt).
- `workspace_invitation.email` akzeptierter/abgelaufener Einladungen wird
  ueber `cleanup_expired_invitations` auf `<redacted>` gesetzt; offene,
  zukuenftige Einladungen bleiben unangetastet.
- `entitlement_history` bleibt unveraendert (gesetzliche Aufbewahrung).

Laeuft in einem isolierten Schema; ohne DB uebersprungen.
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.repositories.account_repository import (
    ANONYMIZED_USER_ID,
    PgAccountPurgeRepository,
)


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


@pytest.mark.integration
def test_purge_anonymises_audit_and_keeps_entitlement_history() -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

    settings = get_settings()
    schema = f"erasure_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)

            # Seed: Org + Workspace + Persona + status_history + audit_log + history
            user = uuid4()
            other_user = uuid4()
            org_id = await owner.fetchval(
                "INSERT INTO organization (name, slug, kind) "
                "VALUES ('o', $1, 'company') RETURNING id",
                f"o-{secrets.token_hex(4)}",
            )
            ws_id = await owner.fetchval(
                "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
                org_id,
            )
            persona_id = await owner.fetchval(
                "INSERT INTO persona (workspace_id, owner_id, name) "
                "VALUES ($1, $2, 'p') RETURNING id",
                ws_id,
                user,
            )
            await owner.execute(
                "INSERT INTO status_history "
                "(entity_type, entity_id, from_status, to_status, changed_by) "
                "VALUES ('persona', $1, NULL, 'draft', $2)",
                persona_id,
                user,
            )
            # Eine zweite status_history-Zeile von einem fremden Akteur bleibt erhalten.
            await owner.execute(
                "INSERT INTO status_history "
                "(entity_type, entity_id, from_status, to_status, changed_by) "
                "VALUES ('persona', $1, 'draft', 'review', $2)",
                persona_id,
                other_user,
            )
            await owner.execute(
                "INSERT INTO audit_log (org_id, workspace_id, actor_id, action) "
                "VALUES ($1, $2, $3, 'token.issued')",
                org_id,
                ws_id,
                user,
            )
            # Ein entitlement_history-Eintrag, der explizit erhalten bleiben soll
            # (GoBD, ADR-0031). `created_by` traegt den User — bewusst nicht
            # anonymisiert (gesetzliche Aufbewahrung schliesst Anonymisierung aus).
            await owner.execute(
                "INSERT INTO entitlement_history (org_id, status, source, created_by, reason) "
                "VALUES ($1, 'active', 'manual_override', $2, 'kulanz')",
                org_id,
                user,
            )

            # Drei Invitations: (a) akzeptiert, (b) abgelaufen, (c) noch offen.
            now = datetime.now(UTC)
            past = now - timedelta(days=8)
            future = now + timedelta(days=7)
            await owner.execute(
                "INSERT INTO workspace_invitation "
                "(workspace_id, email, role, token_hash, expires_at, created_by, accepted_at) "
                "VALUES ($1, 'a@example.com', 'editor', $2, $3, $4, now())",
                ws_id,
                f"h-{secrets.token_hex(8)}",
                future,
                user,
            )
            await owner.execute(
                "INSERT INTO workspace_invitation "
                "(workspace_id, email, role, token_hash, expires_at, created_by) "
                "VALUES ($1, 'b@example.com', 'editor', $2, $3, $4)",
                ws_id,
                f"h-{secrets.token_hex(8)}",
                past,
                user,
            )
            await owner.execute(
                "INSERT INTO workspace_invitation "
                "(workspace_id, email, role, token_hash, expires_at, created_by) "
                "VALUES ($1, 'c@example.com', 'editor', $2, $3, $4)",
                ws_id,
                f"h-{secrets.token_hex(8)}",
                future,
                user,
            )

            repo = PgAccountPurgeRepository(owner)
            anonymized = await repo.purge_account_data(user)
            # Genau eine status_history- und eine audit_log-Zeile gehoeren dem User.
            assert anonymized == 2

            cleaned = await repo.cleanup_expired_invitations(now)
            # 2 Invitations betroffen: (a) accepted, (b) expired.
            assert cleaned == 2

            # status_history: die User-Zeile ist anonymisiert, die fremde unveraendert.
            actors = await owner.fetch(
                "SELECT changed_by FROM status_history WHERE entity_id = $1 ORDER BY changed_at",
                persona_id,
            )
            assert [row["changed_by"] for row in actors] == [ANONYMIZED_USER_ID, other_user]

            # audit_log: aktor anonymisiert.
            audit_actor = await owner.fetchval(
                "SELECT actor_id FROM audit_log WHERE workspace_id = $1",
                ws_id,
            )
            assert audit_actor == ANONYMIZED_USER_ID

            # entitlement_history bleibt **unveraendert** (GoBD).
            history_row = await owner.fetchrow(
                "SELECT created_by, source FROM entitlement_history WHERE org_id = $1",
                org_id,
            )
            assert history_row is not None
            assert history_row["created_by"] == user
            assert history_row["source"] == "manual_override"

            # Invitations: a/b redacted, c (offen, zukuenftig) unveraendert.
            emails = await owner.fetch(
                "SELECT email, accepted_at, expires_at FROM workspace_invitation "
                "WHERE workspace_id = $1 ORDER BY created_at",
                ws_id,
            )
            email_map = {row["email"] for row in emails}
            assert "<redacted>" in email_map
            assert "c@example.com" in email_map
            assert "a@example.com" not in email_map
            assert "b@example.com" not in email_map

            # Zweiter cleanup-Lauf = No-op (idempotent).
            assert await repo.cleanup_expired_invitations(now) == 0
        finally:
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


def test_anonymized_user_id_is_zero_uuid() -> None:
    assert ANONYMIZED_USER_ID == UUID("00000000-0000-0000-0000-000000000000")
