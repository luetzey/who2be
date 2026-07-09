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


@pytest.mark.integration
def test_purge_covers_feedback_usage_and_oauth() -> None:
    """Reproduziert die Erasure-Luecke CMP-1 (Standards-Review 2026-07-08).

    Beweist auf der echten DB:
    - `usage_event.actor_id` und `agent_feedback.actor_id` (Migration 0053) des
      geloeschten Users werden auf den Sentinel anonymisiert; fremde Akteure
      bleiben unveraendert.
    - `oauth_authorization_code`-Zeilen des Users (Migration 0049) werden
      geloescht; fremde Codes bleiben.
    - `oauth_refresh_token`-Zeilen des Users verschwinden ueber den
      `api_token`-CASCADE (FK ON DELETE CASCADE, 0049).
    - `cleanup_expired_oauth` raeumt abgelaufene/konsumierte Codes und
      abgelaufene Refresh-Tokens ab; konsumierte, noch nicht abgelaufene
      Refresh-Tokens bleiben (Grace-Retry + Rotationskette). Idempotent.
    """
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

            # Feedback-Flywheel (0053): je eine Zeile des Users + eine fremde.
            for actor in (user, other_user):
                await owner.execute(
                    "INSERT INTO usage_event (workspace_id, actor_id, entity_type, entity_id) "
                    "VALUES ($1, $2, 'persona', $3)",
                    ws_id,
                    actor,
                    persona_id,
                )
                await owner.execute(
                    "INSERT INTO agent_feedback "
                    "(workspace_id, actor_id, entity_type, entity_id, signal) "
                    "VALUES ($1, $2, 'persona', $3, 'helpful')",
                    ws_id,
                    actor,
                    persona_id,
                )

            # OAuth-Connector (0049): Client + Agent (Codes brauchen agent_id).
            await owner.execute(
                "INSERT INTO oauth_client (client_id, redirect_uris) "
                "VALUES ('test-client', ARRAY['https://client.example/cb'])"
            )
            template_id = await owner.fetchval(
                "INSERT INTO system_prompt_template (workspace_id, owner_id, name, slug) "
                "VALUES ($1, $2, 't', 't') RETURNING id",
                ws_id,
                user,
            )
            agent_id = await owner.fetchval(
                "INSERT INTO agent "
                "(workspace_id, owner_id, name, persona_id, system_prompt_template_id) "
                "VALUES ($1, $2, 'a', $3, $4) RETURNING id",
                ws_id,
                user,
                persona_id,
                template_id,
            )

            now = datetime.now(UTC)
            past = now - timedelta(hours=1)
            future = now + timedelta(days=1)

            async def _insert_code(code_hash: str, code_user: UUID, **kw: object) -> None:
                await owner.execute(
                    "INSERT INTO oauth_authorization_code "
                    "(code_hash, client_id, redirect_uri, code_challenge, user_id, "
                    " workspace_id, agent_id, role, resource, expires_at, consumed_at) "
                    "VALUES ($1, 'test-client', 'https://client.example/cb', 'ch', $2, "
                    "        $3, $4, 'editor', 'https://mcp.example/mcp', $5, $6)",
                    code_hash,
                    code_user,
                    ws_id,
                    agent_id,
                    kw.get("expires_at", future),
                    kw.get("consumed_at"),
                )

            await _insert_code("code-user-live", user)
            await _insert_code("code-other-live", other_user)
            await _insert_code("code-other-expired", other_user, expires_at=past)
            await _insert_code("code-other-consumed", other_user, consumed_at=now)

            # api_token (revoked ⇒ CHECK agent_bound_or_revoked erfuellt) +
            # Refresh-Tokens: einer des Users (live), drei des fremden Users.
            async def _insert_token(owner_id: UUID) -> UUID:
                token_id: UUID = await owner.fetchval(
                    "INSERT INTO api_token (owner_id, name, token_hash, workspace_id, "
                    " revoked_at) VALUES ($1, 't', $2, $3, now()) RETURNING id",
                    owner_id,
                    f"h-{secrets.token_hex(8)}",
                    ws_id,
                )
                return token_id

            user_token = await _insert_token(user)
            other_token = await _insert_token(other_user)

            async def _insert_refresh(token_hash: str, api_token_id: UUID, **kw: object) -> None:
                await owner.execute(
                    "INSERT INTO oauth_refresh_token "
                    "(token_hash, api_token_id, client_id, expires_at, consumed_at) "
                    "VALUES ($1, $2, 'test-client', $3, $4)",
                    token_hash,
                    api_token_id,
                    kw.get("expires_at", future),
                    kw.get("consumed_at"),
                )

            await _insert_refresh("refresh-user-live", user_token)
            await _insert_refresh("refresh-other-live", other_token)
            await _insert_refresh("refresh-other-expired", other_token, expires_at=past)
            await _insert_refresh("refresh-other-consumed", other_token, consumed_at=now)

            repo = PgAccountPurgeRepository(owner)
            anonymized = await repo.purge_account_data(user)
            # Je eine usage_event- + agent_feedback-Zeile gehoeren dem User.
            assert anonymized == 2

            # usage_event/agent_feedback: User-Zeile anonymisiert, fremde intakt.
            for table in ("usage_event", "agent_feedback"):
                actors = {
                    row["actor_id"]
                    for row in await owner.fetch(f"SELECT actor_id FROM {table}")  # noqa: S608
                }
                assert actors == {ANONYMIZED_USER_ID, other_user}, table

            # Authorization-Codes des Users geloescht, fremde vollstaendig da.
            remaining_codes = {
                row["code_hash"]
                for row in await owner.fetch("SELECT code_hash FROM oauth_authorization_code")
            }
            assert remaining_codes == {
                "code-other-live",
                "code-other-expired",
                "code-other-consumed",
            }

            # Refresh-Tokens des Users via api_token-CASCADE weg, fremde da.
            remaining_refresh = {
                row["token_hash"]
                for row in await owner.fetch("SELECT token_hash FROM oauth_refresh_token")
            }
            assert remaining_refresh == {
                "refresh-other-live",
                "refresh-other-expired",
                "refresh-other-consumed",
            }

            # Expiry-/Consumed-Cleanup: 2 Codes (expired + consumed) + 1
            # Refresh (expired). Der konsumierte, nicht abgelaufene Refresh
            # bleibt (30s-Grace-Retry + Rotationskette, oauth_service).
            cleaned = await repo.cleanup_expired_oauth(now)
            assert cleaned == 3
            assert await repo.cleanup_expired_oauth(now) == 0

            remaining_codes = {
                row["code_hash"]
                for row in await owner.fetch("SELECT code_hash FROM oauth_authorization_code")
            }
            assert remaining_codes == {"code-other-live"}
            remaining_refresh = {
                row["token_hash"]
                for row in await owner.fetch("SELECT token_hash FROM oauth_refresh_token")
            }
            assert remaining_refresh == {"refresh-other-live", "refresh-other-consumed"}
        finally:
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


def test_anonymized_user_id_is_zero_uuid() -> None:
    assert ANONYMIZED_USER_ID == UUID("00000000-0000-0000-0000-000000000000")
