"""Compliance-Naben fuer Gespraechsprotokoll und Massnahme (ADR-0053 A.1/A.2 E2, Paket E2a-2).

Belegt gegen die echte DB, was Migration 0103 fuer Art. 15/17/20 bedeutet:

- **Auskunft (Art. 15/20):** der GDPR-Export liefert je Workspace
  `feedback_sessions`, jedes Protokoll mit `case_ids` und `measures`, jede
  Massnahme mit `case_ids` und `events`. Sichtregel nach 6.6
  (`GET /feedback-sessions` ab `editor`, Muster D1): ab `editor` alle
  Protokolle, darunter nur die, an denen die Person beteiligt ist —
  eingereicht, Teilnehmer, abweichende Meinung oder Akteur eines
  Massnahmen-Events. Agent-Eintraege mit zufaellig gleicher UUID zaehlen
  nicht. Kind-Zeilen werden nur fuer exportierte Protokolle GELADEN.
- **Loeschung (Art. 17), Account (PM-6):** `purge_account_data` setzt
  `feedback_session.submitted_by` (nur `human`), die IDs menschlicher
  Eintraege in `participants` und `dissent` und `measure_event.actor_id`
  (nur `human`) auf den Sentinel — auch in einem FREMDEN Workspace.
  Agent-Eintraege und fremde Menschen bleiben, Reihenfolge und Text auch.
  Die Personal-Org mit Protokoll faellt per CASCADE.

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated, Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from test_case_compliance import (  # type: ignore[import-not-found]
    _add_member,
    _target_workspace,
    _workspace,
)
from test_feedback_session_schema import (  # type: ignore[import-not-found]
    _insert_case,
    _insert_event,
    _insert_measure,
    _insert_session,
    _insert_test_case,
    _link_measure_case,
    _link_session_case,
)

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.repositories.account_repository import (
    ANONYMIZED_USER_ID,
    PgAccountPurgeRepository,
)
from who2be_api.routers.gdpr import get_export_service
from who2be_api.services.gdpr_export_service import GdprExportService
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

pytestmark = pytest.mark.integration

AuthFactory = Callable[[UUID], dict[str, str]]


def _person(kind: str, person_id: UUID, role: str = "Teilnahme") -> dict[str, str]:
    return {"kind": kind, "id": str(person_id), "role": role}


def _dissent(kind: str, person_id: UUID, text: str) -> dict[str, str]:
    return {"participant_kind": kind, "participant_id": str(person_id), "text": text}


async def _protocol(
    conn: asyncpg.Connection,
    ws: UUID,
    agent: UUID,
    *,
    key: str,
    event_actor: tuple[str, UUID],
    **session: object,
) -> dict[str, UUID]:
    """Fall, Pruefall, Protokoll, Massnahme und ein `draft_linked`-Event."""
    case = await _insert_case(conn, ws, agent)
    test_case = await _insert_test_case(conn, ws, agent)
    sess = await _insert_session(conn, ws, agent, summary=f"Summary {key}", **session)
    await _link_session_case(conn, ws, sess, agent, case)
    measure = await _insert_measure(
        conn, ws, agent, sess, test_case, change_summary=f"Change {key}"
    )
    await _link_measure_case(conn, ws, measure, agent, case)
    event = await _insert_event(
        conn,
        ws,
        measure,
        "draft_linked",
        actor_kind=event_actor[0],
        actor_id=event_actor[1],
        version_entity_type="playbook",
        version_id=uuid4(),
        note=f"Notiz {key}",
    )
    return {"session": sess, "case": case, "measure": measure, "event": event}


# --- Auskunft (Art. 15/20) ---------------------------------------------------

_CHILD_TABLES = ("feedback_session_case", "measure", "measure_case", "measure_event")


class _SessionSpyPool:
    """Reicht alles an den echten Pool durch und merkt sich die GELADENEN
    Kind-Zeilen der Protokolle — belegt, was der Export liest, nicht nur, was
    er ausliefert."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self.session_ids: set[UUID] = set()
        self.measure_ids: set[UUID] = set()

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        rows: list[asyncpg.Record] = await self._pool.fetch(query, *args)
        if "FROM feedback_session_case" in query or "FROM measure WHERE" in query:
            self.session_ids.update(row["session_id"] for row in rows)
        if "FROM measure_case" in query or "FROM measure_event" in query:
            self.measure_ids.update(row["measure_id"] for row in rows)
        return rows

    def __getattr__(self, name: str) -> Any:
        return getattr(self._pool, name)


_OWN_KEYS = ("submitted", "participant", "dissent", "actor")


def _seed_sessions(ws: UUID, agent: UUID, owner: UUID, member: UUID) -> dict[str, dict[str, UUID]]:
    """Vier Protokolle mit Beteiligung des Mitglieds, eins ohne.

    Das fremde Protokoll nennt die UUID des Mitglieds nur in Agent-Rollen
    (Teilnehmer, abweichende Meinung, Event-Akteur, Einreicher) — das darf
    nicht als Beteiligung zaehlen.
    """

    async def _run() -> dict[str, dict[str, UUID]]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            human_owner = ("human", owner)
            return {
                "submitted": await _protocol(
                    conn,
                    ws,
                    agent,
                    key="submitted",
                    event_actor=human_owner,
                    submitted_by_kind="human",
                    submitted_by=member,
                ),
                "participant": await _protocol(
                    conn,
                    ws,
                    agent,
                    key="participant",
                    event_actor=human_owner,
                    participants=json.dumps([_person("human", member)]),
                ),
                "dissent": await _protocol(
                    conn,
                    ws,
                    agent,
                    key="dissent",
                    event_actor=human_owner,
                    dissent=json.dumps([_dissent("human", member, "Dagegen")]),
                ),
                "actor": await _protocol(
                    conn, ws, agent, key="actor", event_actor=("human", member)
                ),
                "foreign": await _protocol(
                    conn,
                    ws,
                    agent,
                    key="foreign",
                    event_actor=("agent", member),
                    participants=json.dumps(
                        [
                            _person("human", owner),
                            _person("agent", member),
                            _person("builder", member),
                        ]
                    ),
                    dissent=json.dumps([_dissent("agent", member, "Agent dagegen")]),
                    submitted_by_kind="agent",
                    submitted_by=member,
                ),
            }
        finally:
            await conn.close()

    return asyncio.run(_run())


@pytest.mark.parametrize(
    ("member_role", "sees_all"),
    [(WorkspaceRole.viewer, False), (WorkspaceRole.editor, True)],
)
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_gdpr_export_sessions_follow_role_and_load_only_exported_children(
    make_auth_headers: AuthFactory, member_role: WorkspaceRole, sees_all: bool
) -> None:
    owner = fresh_user_id()
    member = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, member, member_role)
    spy: dict[str, _SessionSpyPool] = {}

    def _spied_service(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> GdprExportService:
        spy["pool"] = _SessionSpyPool(pool)
        return GdprExportService(spy["pool"])

    try:
        with TestClient(app) as client:
            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={"name": "Berater"},
                headers=make_auth_headers(owner),
            )
            assert agent.status_code == 201, agent.text
            ids = _seed_sessions(ws, UUID(agent.json()["id"]), owner, member)

            app.dependency_overrides[get_export_service] = _spied_service
            try:
                exported = client.get("/v1/gdpr/export", headers=make_auth_headers(member))
            finally:
                app.dependency_overrides.pop(get_export_service, None)
            assert exported.status_code == 200, exported.text
            bundle = exported.json()

        target = _target_workspace(bundle, ws)
        expected = [*_OWN_KEYS, "foreign"] if sees_all else list(_OWN_KEYS)
        sessions = target["feedback_sessions"]
        assert [s["id"] for s in sessions] == [str(ids[k]["session"]) for k in expected]

        # Ein Protokoll vollstaendig: Inhalt, Faelle, Massnahme mit Faellen und Verlauf.
        first = sessions[0]
        assert first["summary"] == "Summary submitted"
        assert first["submitted_by"] == str(member)
        assert "workspace_id" not in first
        assert first["case_ids"] == [str(ids["submitted"]["case"])]
        [measure] = first["measures"]
        assert measure["id"] == str(ids["submitted"]["measure"])
        assert measure["change_summary"] == "Change submitted"
        assert measure["case_ids"] == [str(ids["submitted"]["case"])]
        assert "workspace_id" not in measure
        assert [e["id"] for e in measure["events"]] == [str(ids["submitted"]["event"])]
        assert measure["events"][0]["note"] == "Notiz submitted"
        assert "workspace_id" not in measure["events"][0]

        loaded = spy["pool"]
        manifest = target["export_manifest"]["feedback_sessions"]
        if sees_all:
            assert loaded.session_ids == {ids[k]["session"] for k in expected}
            assert manifest == {"included": True, "scope": "workspace"}
        else:
            dumped = json.dumps(bundle, default=str)
            foreign = ids["foreign"]
            for value in (*foreign.values(), "Summary foreign", "Change foreign", "Notiz foreign"):
                assert str(value) not in dumped
            assert loaded.session_ids == {ids[k]["session"] for k in _OWN_KEYS}
            assert loaded.measure_ids == {ids[k]["measure"] for k in _OWN_KEYS}
            assert manifest["scope"] == "own_participation"
            assert "editor" in manifest["reason"]
    finally:
        cleanup_workspaces([owner])


# --- Loeschung (Art. 17), Account ----------------------------------------------


def _in_isolated_schema(body: Callable[[asyncpg.Connection], Awaitable[None]]) -> None:
    """Owner-Verbindung (wie der Purge-Job) auf einem frisch migrierten Schema."""
    schema = f"session_erasure_{secrets.token_hex(6)}"

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


def test_account_purge_anonymizes_session_and_measure_person_references() -> None:
    async def body(owner: asyncpg.Connection) -> None:
        user, other = uuid4(), uuid4()
        sentinel = ANONYMIZED_USER_ID
        # Fremder Company-Workspace: hier greift KEINE CASCADE.
        ws, agent = await _workspace(owner, other)
        ws_personal, agent_personal = await _workspace(owner, user, kind="personal", slug=str(user))

        participants = [
            _person("human", user, "Moderation"),
            _person("agent", user),
            _person("human", other),
            _person("builder", user),
        ]
        dissent = [
            _dissent("human", user, "Ich nicht"),
            _dissent("agent", user, "Agent nicht"),
            _dissent("human", other, "Ich auch nicht"),
        ]
        mine = await _protocol(
            owner,
            ws,
            agent,
            key="mine",
            event_actor=("human", user),
            submitted_by_kind="human",
            submitted_by=user,
            participants=json.dumps(participants),
            dissent=json.dumps(dissent),
        )
        ev_agent = await _insert_event(
            owner,
            ws,
            mine["measure"],
            "follow_up_prepared",
            actor_kind="agent",
            actor_id=user,
            metrics=json.dumps({"rate": 1}),
        )
        ev_other = await _insert_event(
            owner, ws, mine["measure"], "withdrawn", actor_id=other, note="Aufgegeben"
        )
        # Einreicher Agent mit zufaellig gleicher UUID: keine Person.
        agent_sub = await _protocol(
            owner,
            ws,
            agent,
            key="agent",
            event_actor=("human", other),
            submitted_by_kind="agent",
            submitted_by=user,
        )
        personal = await _protocol(
            owner,
            ws_personal,
            agent_personal,
            key="personal",
            event_actor=("human", user),
            submitted_by_kind="human",
            submitted_by=user,
        )

        anonymized = await PgAccountPurgeRepository(owner).purge_account_data(user)
        # submitted_by + participants-Zeile + dissent-Zeile + ein menschliches Event.
        assert anonymized == 4

        assert (
            await owner.fetchval(
                "SELECT count(*) FROM feedback_session WHERE id = $1", personal["session"]
            )
            == 0
        )

        submitters = {
            row["id"]: row["submitted_by"]
            for row in await owner.fetch("SELECT id, submitted_by FROM feedback_session")
        }
        assert submitters == {mine["session"]: sentinel, agent_sub["session"]: user}

        row = await owner.fetchrow(
            "SELECT participants, dissent, summary FROM feedback_session WHERE id = $1",
            mine["session"],
        )
        assert row is not None
        got_participants = row["participants"]
        got_dissent = row["dissent"]
        if isinstance(got_participants, str):  # Owner-Connection ohne jsonb-Codec
            got_participants, got_dissent = json.loads(got_participants), json.loads(got_dissent)
        assert got_participants == [
            _person("human", sentinel, "Moderation"),
            _person("agent", user),
            _person("human", other),
            _person("builder", user),
        ]
        assert got_dissent == [
            _dissent("human", sentinel, "Ich nicht"),
            _dissent("agent", user, "Agent nicht"),
            _dissent("human", other, "Ich auch nicht"),
        ]
        assert row["summary"] == "Summary mine"

        actors = {
            r["id"]: r["actor_id"]
            for r in await owner.fetch("SELECT id, actor_id FROM measure_event")
        }
        assert actors == {
            mine["event"]: sentinel,
            ev_agent: user,
            ev_other: other,
            agent_sub["event"]: other,
        }

        # Idempotent: ein zweiter Lauf findet nichts mehr.
        assert await PgAccountPurgeRepository(owner).purge_account_data(user) == 0

    _in_isolated_schema(body)
