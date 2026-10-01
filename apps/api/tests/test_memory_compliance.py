"""Compliance-Naben fuer Gedaechtnis 2.0 (ADR-0053 Anhang A.1/A.2, Paket C1b).

Belegt gegen die echte DB, was Migration 0091 fuer Art. 15/17/20 bedeutet:

- **Auskunft (Art. 15/20):** der GDPR-Export liefert je Workspace das
  Agentengedaechtnis (`agent_memories`, nur `scope='agent'`) und das
  Nutzergedaechtnis des exportierenden Menschen (`user_memories`, nur
  `subject_user_id` = er), beide mit ihrer Historie unter `events`. Das
  Nutzergedaechtnis anderer Mitglieder steht nirgends im Buendel (3.1.1).
- **Loeschung (Art. 17), Account:** `purge_account_data` hinterlaesst keine
  Zeile mit `subject_user_id` des geloeschten Menschen — auch in einem
  FREMDEN Workspace, den keine Personal-Org-CASCADE erreicht. Je geloeschter
  Zeile steht eine `audit_log`-Spur `memory.deleted` ohne Inhalt; was mit
  der Personal-Org per Cascade faellt, bekommt keine (0091). `confirmed_by`
  und menschliche `actor_id` der Historie werden anonymisiert.

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.repositories.account_repository import (
    ANONYMIZED_USER_ID,
    PgAccountPurgeRepository,
)
from who2be_api.repositories.memory_repository import MEMORY_DELETED_AUDIT_ACTION
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

pytestmark = pytest.mark.integration

AuthFactory = Callable[[UUID], dict[str, str]]


async def _insert_memory(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    fact: str,
    *,
    agent_id: UUID | None = None,
    subject_user_id: UUID | None = None,
    created_by_agent_id: UUID | None = None,
    confirmed_by: UUID | None = None,
) -> UUID:
    """Ein Eintrag; mit `subject_user_id` Nutzergedaechtnis, sonst Agentengedaechtnis."""
    scope = "user" if subject_user_id is not None else "agent"
    memory_id: UUID = await conn.fetchval(
        "INSERT INTO agent_memory "
        "(workspace_id, agent_id, scope, subject_user_id, created_by_agent_id, status, "
        " fact, origin, confirmed_by, confirmed_at) "
        "VALUES ($1, $2, $3, $4, $5, 'active', $6, 'user_stated', $7, "
        "        CASE WHEN $7::uuid IS NULL THEN NULL ELSE now() END) RETURNING id",
        workspace_id,
        agent_id,
        scope,
        subject_user_id,
        created_by_agent_id,
        fact,
        confirmed_by,
    )
    return memory_id


async def _insert_event(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    memory_id: UUID,
    event: str,
    *,
    actor_kind: str,
    actor_id: UUID | None = None,
    agent_id: UUID | None = None,
    reason: str | None = None,
) -> UUID:
    event_id: UUID = await conn.fetchval(
        "INSERT INTO agent_memory_event "
        "(workspace_id, memory_id, event, actor_kind, actor_id, agent_id, reason) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
        workspace_id,
        memory_id,
        event,
        actor_kind,
        actor_id,
        agent_id,
        reason,
    )
    return event_id


# --- Auskunft (Art. 15/20) ---------------------------------------------------


def _target_workspace(bundle: dict[str, Any], ws: UUID) -> dict[str, Any]:
    workspaces = [
        w for org in bundle["organizations"] for w in org["workspaces"] if w["id"] == str(ws)
    ]
    assert len(workspaces) == 1, workspaces
    return workspaces[0]


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_gdpr_export_contains_own_user_memory_and_events(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    try:
        with TestClient(app) as client:
            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={"name": "Merker"},
                headers=make_auth_headers(owner),
            )
            assert agent.status_code == 201, agent.text
            agent_id = UUID(agent.json()["id"])

            # Es gibt noch keinen Schreibpfad fuer `scope='user'` (C2a) — Seed
            # direkt als Owner.
            async def _seed() -> dict[str, UUID]:
                conn = await asyncpg.connect(get_settings().database_url)
                try:
                    own = await _insert_memory(
                        conn,
                        ws,
                        "Owner bevorzugt kurze Antworten",
                        subject_user_id=owner,
                        created_by_agent_id=agent_id,
                        confirmed_by=owner,
                    )
                    foreign = await _insert_memory(
                        conn,
                        ws,
                        "Fremder Nutzer arbeitet nachts",
                        subject_user_id=other,
                        created_by_agent_id=agent_id,
                    )
                    agent_note = await _insert_memory(
                        conn, ws, "Werkzeug X braucht Retry", agent_id=agent_id
                    )
                    ids = {"own": own, "foreign": foreign, "agent_note": agent_note}
                    ids["own_created"] = await _insert_event(
                        conn, ws, own, "created", actor_kind="agent", agent_id=agent_id
                    )
                    ids["own_confirmed"] = await _insert_event(
                        conn, ws, own, "confirmed", actor_kind="human", actor_id=owner
                    )
                    await _insert_event(
                        conn,
                        ws,
                        foreign,
                        "created",
                        actor_kind="agent",
                        agent_id=agent_id,
                        reason="Fremde Historie",
                    )
                    ids["note_created"] = await _insert_event(
                        conn, ws, agent_note, "created", actor_kind="agent", agent_id=agent_id
                    )
                    return ids
                finally:
                    await conn.close()

            ids = asyncio.run(_seed())

            exported = client.get("/v1/gdpr/export", headers=make_auth_headers(owner))
            assert exported.status_code == 200, exported.text
            bundle = exported.json()

        target = _target_workspace(bundle, ws)

        # Nutzergedaechtnis: genau der eigene Eintrag, samt Historie in Reihenfolge.
        assert [m["id"] for m in target["user_memories"]] == [str(ids["own"])]
        own = target["user_memories"][0]
        assert own["fact"] == "Owner bevorzugt kurze Antworten"
        assert own["scope"] == "user"
        assert own["subject_user_id"] == str(owner)
        assert own["created_by_agent_id"] == str(agent_id)
        assert own["confirmed_by"] == str(owner)
        assert "workspace_id" not in own
        assert "search" not in own
        assert [e["id"] for e in own["events"]] == [
            str(ids["own_created"]),
            str(ids["own_confirmed"]),
        ]
        assert [e["event"] for e in own["events"]] == ["created", "confirmed"]
        assert own["events"][1]["actor_id"] == str(owner)
        assert "workspace_id" not in own["events"][0]

        # Agentengedaechtnis: nur `scope='agent'`, ebenfalls mit Historie.
        assert [m["id"] for m in target["agent_memories"]] == [str(ids["agent_note"])]
        note = target["agent_memories"][0]
        assert note["scope"] == "agent"
        assert [e["id"] for e in note["events"]] == [str(ids["note_created"])]

        # Fremdes Nutzergedaechtnis steht nirgends im Buendel — weder der
        # Eintrag noch seine Historie.
        dumped = json.dumps(bundle, default=str)
        assert str(ids["foreign"]) not in dumped
        assert "Fremder Nutzer arbeitet nachts" not in dumped
        assert "Fremde Historie" not in dumped
    finally:
        cleanup_workspaces([owner])


# --- Loeschung (Art. 17) -----------------------------------------------------


def _in_isolated_schema(body: Callable[[asyncpg.Connection], Awaitable[None]]) -> None:
    """Owner-Verbindung (wie der Purge-Job) auf einem frisch migrierten Schema."""
    schema = f"mem_erasure_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(get_settings().database_url)
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)
            await body(owner)
        finally:
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


async def _workspace(
    owner: asyncpg.Connection, member: UUID, *, kind: str = "company", slug: str | None = None
) -> tuple[UUID, UUID]:
    """Org + Workspace + Agent; liefert (workspace_id, agent_id)."""
    org_id: UUID = await owner.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, $2) RETURNING id",
        slug or f"o-{secrets.token_hex(4)}",
        kind,
    )
    ws_id: UUID = await owner.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
        org_id,
    )
    agent_id: UUID = await owner.fetchval(
        "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, 'a') RETURNING id",
        ws_id,
        member,
    )
    return ws_id, agent_id


def test_account_purge_deletes_user_memory_with_contentless_audit() -> None:
    async def body(owner: asyncpg.Connection) -> None:
        user, other_user = uuid4(), uuid4()
        # Fremder Company-Workspace: hier greift KEINE CASCADE, nur der
        # Purge-Schritt selbst kann das Nutzergedaechtnis entfernen.
        ws, agent = await _workspace(owner, other_user)
        # Personal-Org des Users: faellt per Cascade, ohne Audit-Spur je Eintrag.
        ws_personal, _ = await _workspace(owner, user, kind="personal", slug=str(user))

        secret_fact = "User hat eine Allergie gegen Nuesse"
        mem_user = await _insert_memory(
            owner, ws, secret_fact, subject_user_id=user, created_by_agent_id=agent
        )
        await _insert_event(
            owner, ws, mem_user, "created", actor_kind="agent", agent_id=agent, reason=secret_fact
        )
        mem_personal = await _insert_memory(
            owner, ws_personal, "Persoenlicher Fakt", subject_user_id=user
        )
        mem_other = await _insert_memory(
            owner, ws, "Anderer Nutzer mag Tabellen", subject_user_id=other_user
        )
        ev_other = await _insert_event(
            owner, ws, mem_other, "created", actor_kind="agent", agent_id=agent
        )
        # Eintrag eines anderen, den der User bestaetigt hat — er bleibt, die
        # Person verschwindet aus `confirmed_by` und aus der Historie.
        mem_confirmed = await _insert_memory(
            owner, ws, "Werkzeug Y ist langsam", agent_id=agent, confirmed_by=user
        )
        ev_human = await _insert_event(
            owner, ws, mem_confirmed, "confirmed", actor_kind="human", actor_id=user
        )
        ev_other_human = await _insert_event(
            owner, ws, mem_other, "confirmed", actor_kind="human", actor_id=other_user
        )
        # Agent-Event, dessen `actor_id` zufaellig die User-UUID traegt: das
        # ist keine Person — der Purge darf es nicht anfassen (Muster
        # `test_case.created_by_kind` in B1c).
        ev_agent_same_id = await _insert_event(
            owner, ws, mem_confirmed, "edited", actor_kind="agent", actor_id=user, agent_id=agent
        )

        anonymized = await PgAccountPurgeRepository(owner).purge_account_data(user)
        # `confirmed_by` + ein menschliches Event des Users.
        assert anonymized == 2

        # Keine Zeile mit `subject_user_id` des Users mehr — in keinem Workspace.
        left = await owner.fetchval(
            "SELECT count(*) FROM agent_memory WHERE subject_user_id = $1", user
        )
        assert left == 0
        # Historie des geloeschten Eintrags ist per Cascade mit weg.
        assert (
            await owner.fetchval(
                "SELECT count(*) FROM agent_memory_event WHERE memory_id = ANY($1::uuid[])",
                [mem_user, mem_personal],
            )
            == 0
        )

        # Genau eine Spur `memory.deleted` — fuer den Eintrag im fremden
        # Workspace, nicht fuer den per Org-Cascade gefallenen.
        audits = await owner.fetch(
            "SELECT workspace_id, actor_id, target, detail FROM audit_log WHERE action = $1",
            MEMORY_DELETED_AUDIT_ACTION,
        )
        assert [(a["workspace_id"], a["target"]) for a in audits] == [(ws, str(mem_user))]
        audit = audits[0]
        assert audit["actor_id"] is None
        # Inhaltsfrei: weder Fakt noch Historie in irgendeiner Spalte der Spur.
        detail = (
            json.loads(audit["detail"]) if isinstance(audit["detail"], str) else audit["detail"]
        )
        assert detail == {}
        audit_rows = await owner.fetch("SELECT * FROM audit_log")
        assert secret_fact not in json.dumps([dict(r) for r in audit_rows], default=str)

        # Fremdes Nutzergedaechtnis bleibt samt Historie unberuehrt.
        assert await owner.fetchval("SELECT fact FROM agent_memory WHERE id = $1", mem_other) == (
            "Anderer Nutzer mag Tabellen"
        )
        actors = {
            row["id"]: row["actor_id"]
            for row in await owner.fetch("SELECT id, actor_id FROM agent_memory_event")
        }
        assert actors == {
            ev_other: None,
            ev_human: ANONYMIZED_USER_ID,
            ev_other_human: other_user,
            ev_agent_same_id: user,
        }
        assert (
            await owner.fetchval(
                "SELECT confirmed_by FROM agent_memory WHERE id = $1", mem_confirmed
            )
            == ANONYMIZED_USER_ID
        )

        # Idempotent: ein zweiter Lauf findet nichts mehr und schreibt keine Spur.
        assert await PgAccountPurgeRepository(owner).purge_account_data(user) == 0
        assert (
            await owner.fetchval(
                "SELECT count(*) FROM audit_log WHERE action = $1", MEMORY_DELETED_AUDIT_ACTION
            )
            == 1
        )

    _in_isolated_schema(body)
