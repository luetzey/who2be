"""Integrationstests Lernschleife D2c-2: convert und promote am Router (ADR-0053 6.4/6.5).

Belegt am Router (echte DB, echter Auth-Pfad):

- `POST /agents/{agent_id}/memories/{memory_id}/convert`: ein offener
  Lernvorschlag wird ein Fall (201, Agent aus dem Lernvorschlag, Body ohne
  `agent_id`); Wiederholung 409 `memory_not_convertible`.
- `POST /feedback/{feedback_id}/promote`: ein offenes Alt-Feedback wird ein
  Fall (201); Wiederholung 409 `feedback_not_promotable`.
- Rechte: convert: Agent ohne `case_triage` 403, viewer 403, editor 201,
  Builder (`case_triage`, PM-4) 201 mit Melder `pattern`. promote:
  Agent-Token 403 (auch mit `case_triage`), viewer 403, editor 201.
- `GET /memories/{memory_id}` fuer den Builder (PM-4): nur `kind=lesson`,
  alles andere 404 wie eine unbekannte ID.
- Fremder Workspace: Objekt aus B ist fuer A nicht da (404), Workspace B im
  Pfad mit A-Login wird abgewiesen.

Atomaritaet und Geschaeftsregeln deckt `test_case_convert_promote.py`
(Service) ab; hier geht es um den Vertrag der HTTP-Schicht.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

pytestmark = pytest.mark.integration

_PLAYBOOK = {"description": "d", "body": "1. Schritt.", "type": "workflow", "tags": []}
_CASE_FIELDS = {"situation": "Lage", "behavior": "Verhalten", "expected_behavior": "Erwartet"}


class _World:
    def __init__(self, client: TestClient, make: Any) -> None:
        self.client = client
        self._make = make
        self.users: list[UUID] = []

    def workspace(self) -> tuple[str, dict[str, str]]:
        owner = fresh_user_id()
        self.users.append(owner)
        ws = setup_workspace(owner)
        return f"/v1/workspaces/{ws}", self._make(owner)

    def member(self, base: str, role: WorkspaceRole) -> dict[str, str]:
        user = fresh_user_id()
        self.users.append(user)
        db_execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, $3)",
            UUID(base.rsplit("/", 1)[1]),
            user,
            role.value,
        )
        headers: dict[str, str] = self._make(user)
        return headers

    def lesson(self, base: str, agent_id: str) -> str:
        """Offener Lernvorschlag des Agenten, direkt in der DB (wie die Service-Tests)."""
        return str(
            db_fetchval(
                "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
                " created_by_agent_id, origin, source) "
                "VALUES ($1, $2::uuid, 'pending', 'Frist nennen', 'lesson', 'agent', $2::uuid, "
                " 'inferred', 'agent') RETURNING id",
                UUID(base.rsplit("/", 1)[1]),
                agent_id,
            )
        )

    def feedback(self, base: str, auth: dict[str, str], agent_auth: dict[str, str]) -> str:
        """Offenes Alt-Feedback ueber den regulaeren Weg (`POST /feedback`)."""
        playbook = self.client.post(
            f"{base}/playbooks",
            json={"name": "Frist", "content": {**_PLAYBOOK, "triggers": "frist"}},
            headers=auth,
        )
        assert playbook.status_code == 201, playbook.text
        res = self.client.post(
            f"{base}/feedback",
            json={
                "entity_type": "playbook",
                "entity_id": playbook.json()["id"],
                "signal": "incorrect",
                "note": "Schritt 1 nennt keine Frist",
            },
            headers=agent_auth,
        )
        assert res.status_code == 201, res.text
        return str(res.json()["id"])

    def convert(self, base: str, agent_id: str, memory_id: str, headers: dict[str, str]) -> Any:
        return self.client.post(
            f"{base}/agents/{agent_id}/memories/{memory_id}/convert",
            json=_CASE_FIELDS,
            headers=headers,
        )

    def promote(self, base: str, feedback_id: str, agent_id: str, headers: dict[str, str]) -> Any:
        return self.client.post(
            f"{base}/feedback/{feedback_id}/promote",
            json={"agent_id": agent_id, **_CASE_FIELDS},
            headers=headers,
        )


@pytest.fixture
def world(migrated_db: None, patched_jwt_secret: str, make_auth_headers: Any) -> Iterator[_World]:
    w: _World | None = None
    try:
        with TestClient(app) as client:
            w = _World(client, make_auth_headers)
            yield w
    finally:
        cleanup_workspaces(w.users if w else [])


def test_convert_rights_conflict_and_scope(world: _World) -> None:
    w = world
    base, auth = w.workspace()
    agent_id, agent_auth = agent_token(w.client, base, "Betroffen", {}, auth)
    builder, triage_auth = agent_token(w.client, base, "Builder", {"case_triage": True}, auth)
    viewer = w.member(base, WorkspaceRole.viewer)
    editor = w.member(base, WorkspaceRole.editor)
    memory_id = w.lesson(base, agent_id)

    # Agent ohne case_triage und viewer nicht; der Builder darf (PM-4, unten).
    for headers in (agent_auth, viewer):
        denied = w.convert(base, agent_id, memory_id, headers)
        assert denied.status_code == 403, denied.text
    # Body mit agent_id (oder Zuordnung) ist kein CaseConvertRequest (Q2, Weiche 1).
    extras: list[dict[str, Any]] = [{"agent_id": agent_id}, {"elements": []}]
    for extra in extras:
        bad = w.client.post(
            f"{base}/agents/{agent_id}/memories/{memory_id}/convert",
            json={**_CASE_FIELDS, **extra},
            headers=editor,
        )
        assert bad.status_code == 422, extra

    created = w.convert(base, agent_id, memory_id, editor)
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["agent_id"] == agent_id
    assert case["status"] == "open"
    assert case["reporter_kind"] == "human"
    assert case["source_memory_id"] == memory_id

    # Wiederholung: eigener Grund, kein zweiter Fall.
    again = w.convert(base, agent_id, memory_id, editor)
    assert again.status_code == 409, again.text
    assert again.json()["reason"] == "memory_not_convertible"
    listed = w.client.get(f"{base}/cases", headers=editor).json()
    assert [c["id"] for c in listed] == [case["id"]]

    # Fremder Workspace: B-Lernvorschlag unter A nicht da; B im Pfad abgewiesen.
    base_b, auth_b = w.workspace()
    agent_b, _ = agent_token(w.client, base_b, "Fremd", {}, auth_b)
    memory_b = w.lesson(base_b, agent_b)
    foreign = w.convert(base, agent_b, memory_b, auth)
    assert foreign.status_code == 404
    assert foreign.json()["reason"] == "agent_not_found"
    assert w.convert(base, agent_id, memory_b, auth).status_code == 404
    assert w.convert(base_b, agent_b, memory_b, auth).status_code in (403, 404)
    assert w.convert(base_b, agent_b, memory_b, auth_b).status_code == 201

    # Builder (case_triage, PM-4): Melder `pattern`, Builder als reporter_agent_id.
    lesson2 = w.lesson(base, agent_id)
    by_builder = w.convert(base, agent_id, lesson2, triage_auth)
    assert by_builder.status_code == 201, by_builder.text
    built = by_builder.json()
    assert built["reporter_kind"] == "pattern"
    assert built["reporter_agent_id"] == builder
    assert built["reporter_user_id"] is None
    assert built["source_memory_id"] == lesson2
    again_builder = w.convert(base, agent_id, lesson2, triage_auth)
    assert again_builder.status_code == 409
    # Der Builder kommt nicht in einen fremden Workspace.
    memory_b2 = w.lesson(base_b, agent_b)
    assert w.convert(base, agent_b, memory_b2, triage_auth).status_code == 404
    assert w.convert(base_b, agent_b, memory_b2, triage_auth).status_code in (401, 403, 404)


def test_builder_reads_lessons_only(world: _World) -> None:
    """PM-4: `GET /memories/{id}` liefert dem Builder genau Lernvorschlaege.

    Lernvorschlag eines beliebigen Agenten im Workspace: 200. Jede andere Art
    (agent_note, Nutzergedaechtnis), fremder Workspace und unbekannte ID: 404
    `memory_not_found` mit derselben Antwort. Agent ohne case_triage: 403.
    """
    w = world
    base, auth = w.workspace()
    ws = UUID(base.rsplit("/", 1)[1])
    agent_id, agent_auth = agent_token(w.client, base, "Betroffen", {}, auth)
    builder_id, triage_auth = agent_token(w.client, base, "Builder", {"case_triage": True}, auth)
    lesson = w.lesson(base, agent_id)
    note = str(
        db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
            " created_by_agent_id, origin, source) "
            "VALUES ($1, $2::uuid, 'active', 'Interne Notiz', 'agent_note', 'agent', $2::uuid, "
            " 'inferred', 'agent') RETURNING id",
            ws,
            agent_id,
        )
    )
    own_note = str(
        db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
            " created_by_agent_id, origin, source) "
            "VALUES ($1, $2::uuid, 'pending', 'Builder-Notiz', 'agent_note', 'agent', $2::uuid, "
            " 'inferred', 'agent') RETURNING id",
            ws,
            builder_id,
        )
    )
    owner_id = db_fetchval("SELECT user_id FROM workspace_member WHERE workspace_id = $1", ws)
    user_fact = str(
        db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, kind, scope, origin, source, subject_user_id) "
            "VALUES ($1, NULL, $2::uuid, 'active', 'Mag Tee', 'user_fact', 'user', "
            " 'user_stated', 'agent', $3) RETURNING id",
            ws,
            builder_id,
            owner_id,
        )
    )
    base_b, auth_b = w.workspace()
    agent_b, _ = agent_token(w.client, base_b, "Fremd", {}, auth_b)
    lesson_b = w.lesson(base_b, agent_b)

    def get(memory_id: str, headers: dict[str, str]) -> Any:
        return w.client.get(f"{base}/memories/{memory_id}", headers=headers)

    ok = get(lesson, triage_auth)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert (body["id"], body["kind"], body["agent_id"]) == (lesson, "lesson", agent_id)
    assert body["fact"] == "Frist nennen"

    unknown = get("00000000-0000-0000-0000-000000000000", triage_auth)
    assert unknown.status_code == 404
    assert unknown.json()["reason"] == "memory_not_found"
    for hidden in (note, own_note, user_fact, lesson_b):
        res = get(hidden, triage_auth)
        assert res.status_code == 404, (hidden, res.text)
        assert res.json()["reason"] == "memory_not_found"
        assert res.json()["detail"] == unknown.json()["detail"]
    assert "Interne Notiz" not in get(note, triage_auth).text

    # Ohne case_triage bleibt es 403 (wie vor PM-4); der Mensch sieht wie bisher.
    denied = get(lesson, agent_auth)
    assert denied.status_code == 403
    assert denied.json()["reason"] == "missing_capability"
    assert get(note, auth).status_code == 200


def test_promote_rights_conflict_and_scope(world: _World) -> None:
    w = world
    base, auth = w.workspace()
    agent_id, agent_auth = agent_token(w.client, base, "Betroffen", {}, auth)
    _t, triage_auth = agent_token(
        w.client, base, "Builder", {"case_triage": True, "feedback_resolve": True}, auth
    )
    viewer = w.member(base, WorkspaceRole.viewer)
    editor = w.member(base, WorkspaceRole.editor)
    feedback_id = w.feedback(base, auth, agent_auth)

    for headers in (agent_auth, triage_auth, viewer):
        denied = w.promote(base, feedback_id, agent_id, headers)
        assert denied.status_code == 403, denied.text
    # Zuordnung im Body bleibt verboten (Q2: Melden und Einordnen getrennt).
    bad = w.client.post(
        f"{base}/feedback/{feedback_id}/promote",
        json={"agent_id": agent_id, **_CASE_FIELDS, "elements": []},
        headers=editor,
    )
    assert bad.status_code == 422

    created = w.promote(base, feedback_id, agent_id, editor)
    assert created.status_code == 201, created.text
    case = created.json()
    assert case["agent_id"] == agent_id
    assert case["source_feedback_id"] == feedback_id
    assert case["reporter_kind"] == "human"

    again = w.promote(base, feedback_id, agent_id, editor)
    assert again.status_code == 409, again.text
    assert again.json()["reason"] == "feedback_not_promotable"
    detail = w.client.get(f"{base}/feedback/{feedback_id}", headers=editor)
    assert detail.status_code == 200, detail.text
    assert f"case:{case['id']}" in detail.text

    base_b, auth_b = w.workspace()
    _agent_b, agent_b_auth = agent_token(w.client, base_b, "Fremd", {}, auth_b)
    feedback_b = w.feedback(base_b, auth_b, agent_b_auth)
    foreign = w.promote(base, feedback_b, agent_id, auth)
    assert foreign.status_code == 404
    assert foreign.json()["reason"] == "feedback_element_not_found"
    assert w.promote(base_b, feedback_b, agent_id, auth).status_code in (403, 404)
