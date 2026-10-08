"""Integrationstests Lernschleife D2b: REST-Endpunkte fuer Faelle (ADR-0053 6.5).

Belegt am Router (echte DB, echter Auth-Pfad): Status je Rolle (viewer,
editor, Agent mit und ohne `case_triage`), 404 fuer Faelle aus einem fremden
Workspace, Replace-Semantik von `PUT /cases/{id}/elements`, je Filter von
`GET /cases` ein Ergebnis, das sich vom ungefilterten unterscheidet, die
Keyset-Paginierung ueber `X-Next-Cursor` und die Haertung: ein
agent-gebundener Aufruf ohne geladene Policy triagiert nicht.

Die Geschaeftsregeln selbst (jede Kante, Pflichtfelder) deckt
`test_case_service.py` ab; hier geht es um den Vertrag der HTTP-Schicht.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.core.tenancy import tenant_scope
from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

pytestmark = pytest.mark.integration

_PLAYBOOK = {"description": "d", "body": "1. Schritt.", "type": "workflow", "tags": []}


def _add_member(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> None:
    db_execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, $3) "
        "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role",
        workspace_id,
        user_id,
        role.value,
    )


def _case_body(agent_id: str, situation: str = "Lage", **extra: Any) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "situation": situation,
        "behavior": "Verhalten",
        "expected_behavior": "Erwartet",
        **extra,
    }


class _World:
    def __init__(
        self, client: TestClient, ws: UUID, owner: UUID, auth: dict[str, str], make: Any
    ) -> None:
        self.client = client
        self.ws = ws
        self.owner = owner
        self.auth = auth
        self.base = f"/v1/workspaces/{ws}"
        self._make = make
        self.extra_users: list[UUID] = []

    def member(self, role: WorkspaceRole) -> dict[str, str]:
        user = fresh_user_id()
        _add_member(self.ws, user, role)
        self.extra_users.append(user)
        headers: dict[str, str] = self._make(user)
        return headers

    def agent(
        self, name: str, policy: dict[str, object] | None = None
    ) -> tuple[str, dict[str, str]]:
        return agent_token(self.client, self.base, name, policy or {}, self.auth)

    def report(self, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        res = self.client.post(f"{self.base}/cases", json=body, headers=headers)
        assert res.status_code == 201, res.text
        created: dict[str, Any] = res.json()
        return created

    def playbook(self, name: str) -> str:
        res = self.client.post(
            f"{self.base}/playbooks",
            json={"name": name, "content": {**_PLAYBOOK, "triggers": name}},
            headers=self.auth,
        )
        assert res.status_code == 201, res.text
        return str(res.json()["id"])

    def put_elements(
        self, case_id: str, elements: list[dict[str, Any]], headers: dict[str, str] | None = None
    ) -> Any:
        return self.client.put(
            f"{self.base}/cases/{case_id}/elements",
            json={"elements": elements},
            headers=headers or self.auth,
        )

    def transition(
        self, case_id: str, body: dict[str, Any], headers: dict[str, str] | None = None
    ) -> Any:
        return self.client.post(
            f"{self.base}/cases/{case_id}/transition", json=body, headers=headers or self.auth
        )

    def ids(self, headers: dict[str, str], **params: Any) -> list[str]:
        res = self.client.get(f"{self.base}/cases", params=params, headers=headers)
        assert res.status_code == 200, res.text
        return [c["id"] for c in res.json()]


@pytest.fixture
def world(migrated_db: None, patched_jwt_secret: str, make_auth_headers: Any) -> Iterator[_World]:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    w: _World | None = None
    try:
        with TestClient(app) as client:
            w = _World(client, ws, owner, make_auth_headers(owner), make_auth_headers)
            yield w
    finally:
        cleanup_workspaces([owner, *(w.extra_users if w else [])])


def test_report_and_read_rights_per_role(world: _World) -> None:
    w = world
    subject_id, subject_auth = w.agent("Betroffen")
    _other_id, other_auth = w.agent("Anderer")
    triage_id, triage_auth = w.agent("Builder", {"case_triage": True})
    _mute_id, mute_auth = w.agent("Stumm", {"feedback_write": False})
    viewer = w.member(WorkspaceRole.viewer)
    editor = w.member(WorkspaceRole.editor)

    by_viewer = w.report(viewer, _case_body(subject_id, "vom Viewer"))
    assert by_viewer["reporter_kind"] == "human"
    assert by_viewer["status"] == "open"
    by_owner = w.report(w.auth, _case_body(subject_id, "vom Owner"))
    # Agent meldet einen anderen Agenten; mit case_triage gilt er als Builder.
    by_agent = w.report(other_auth, _case_body(triage_id, "vom Agenten"))
    assert by_agent["reporter_kind"] == "agent"
    by_builder = w.report(triage_auth, _case_body(subject_id, "vom Builder"))
    assert by_builder["reporter_kind"] == "builder"

    # Melden: ohne feedback_write 403, unbekannter Agent 404, Zuordnung im
    # Body und Melder-Felder 422 (Q2, Melder aus dem Aufrufweg).
    mute = w.client.post(f"{w.base}/cases", json=_case_body(subject_id), headers=mute_auth)
    assert mute.status_code == 403
    assert mute.json()["reason"] == "missing_capability"
    ghost = w.client.post(f"{w.base}/cases", json=_case_body(str(uuid4())), headers=w.auth)
    assert ghost.status_code == 404
    assert ghost.json()["reason"] == "agent_not_found"
    extras: list[dict[str, Any]] = [
        {"elements": [{"target": "model_limit"}]},
        {"reporter_kind": "human"},
    ]
    for extra in extras:
        bad = w.client.post(f"{w.base}/cases", json=_case_body(subject_id, **extra), headers=w.auth)
        assert bad.status_code == 422, extra

    everything = {by_viewer["id"], by_owner["id"], by_agent["id"], by_builder["id"]}
    # viewer: nur selbst gemeldete; fremder Fall ist 404 wie ein unbekannter.
    assert w.ids(viewer) == [by_viewer["id"]]
    assert w.client.get(f"{w.base}/cases/{by_viewer['id']}", headers=viewer).status_code == 200
    hidden = w.client.get(f"{w.base}/cases/{by_owner['id']}", headers=viewer)
    assert hidden.status_code == 404
    assert hidden.json()["reason"] == "case_not_found"
    # editor und Agent mit case_triage: alle.
    assert set(w.ids(editor)) == everything
    assert set(w.ids(triage_auth)) == everything
    # Agent ohne case_triage: die Faelle ueber sich selbst; fremder Agent 403.
    assert set(w.ids(subject_auth)) == {by_viewer["id"], by_owner["id"], by_builder["id"]}
    assert w.ids(other_auth) == []
    asked = w.client.get(f"{w.base}/cases", params={"agent_id": triage_id}, headers=other_auth)
    assert asked.status_code == 403
    assert asked.json()["reason"] == "missing_capability"

    detail = w.client.get(f"{w.base}/cases/{by_owner['id']}", headers=subject_auth)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["case"]["id"] == by_owner["id"]
    assert [e["event"] for e in body["events"]] == ["reported"]
    assert body["elements"] == [] and body["statements"] == []

    # Zaehler: je Status, auch 0, mit derselben Sichtbarkeit wie die Liste.
    counts = w.client.get(f"{w.base}/cases/counts", headers=editor).json()
    assert counts["open"] == 4 and counts["dismissed"] == 0
    assert set(counts) == {
        "open", "triaged", "in_progress", "addressed", "verified", "reopened", "dismissed"
    }  # fmt: skip
    assert w.client.get(f"{w.base}/cases/counts", headers=viewer).json()["open"] == 1


def test_list_filters_each_narrow_the_result(world: _World) -> None:
    """Je Filter ein Ergebnis, das sich vom ungefilterten unterscheidet."""
    w = world
    a_id, _ = w.agent("A")
    b_id, _ = w.agent("B")
    playbook = w.playbook("PB")
    on_a = w.report(w.auth, _case_body(a_id, "A eins"))
    on_a_triaged = w.report(w.auth, _case_body(a_id, "A zwei"))
    on_b = w.report(w.auth, _case_body(b_id, "B eins"))
    assigned = w.put_elements(on_a_triaged["id"], [{"target": "playbook", "entity_id": playbook}])
    assert assigned.status_code == 200, assigned.text
    assert w.transition(on_a_triaged["id"], {"to": "triaged"}).status_code == 200
    # Gleiches Ziel bei B, aber nicht triagiert: trennt `target` von `status`.
    assert w.put_elements(on_b["id"], [{"target": "model_limit"}]).status_code == 200

    unfiltered = set(w.ids(w.auth))
    assert unfiltered == {on_a["id"], on_a_triaged["id"], on_b["id"]}
    by_agent = set(w.ids(w.auth, agent_id=a_id))
    by_status = set(w.ids(w.auth, status="triaged"))
    by_target = set(w.ids(w.auth, target="playbook"))
    assert by_agent == {on_a["id"], on_a_triaged["id"]}
    assert by_status == {on_a_triaged["id"]}
    assert by_target == {on_a_triaged["id"]}
    assert set(w.ids(w.auth, target="model_limit")) == {on_b["id"]}
    for narrowed in (by_agent, by_status, by_target):
        assert narrowed != unfiltered
    assert w.ids(w.auth, agent_id=b_id, status="triaged") == []

    # Ungueltige Filterwerte sind 422, keine leere Liste.
    for params in ({"status": "bogus"}, {"target": "bogus"}, {"agent_id": "x"}):
        assert w.client.get(f"{w.base}/cases", params=params, headers=w.auth).status_code == 422

    # Zaehler mit agent_id folgen dem Filter.
    counts = w.client.get(f"{w.base}/cases/counts", params={"agent_id": a_id}, headers=w.auth)
    assert counts.json()["open"] == 1 and counts.json()["triaged"] == 1


def test_keyset_pagination_via_header(world: _World) -> None:
    w = world
    agent_id, _ = w.agent("A")
    made = [w.report(w.auth, _case_body(agent_id, f"Fall {i}"))["id"] for i in range(3)]

    first = w.client.get(f"{w.base}/cases", params={"limit": 2}, headers=w.auth)
    assert first.status_code == 200
    assert len(first.json()) == 2
    cursor = first.headers.get("X-Next-Cursor")
    assert cursor
    second = w.client.get(f"{w.base}/cases", params={"limit": 2, "cursor": cursor}, headers=w.auth)
    assert second.status_code == 200
    assert "X-Next-Cursor" not in second.headers
    seen = [c["id"] for c in first.json()] + [c["id"] for c in second.json()]
    assert sorted(seen) == sorted(made)
    assert len(set(seen)) == 3

    bad = w.client.get(f"{w.base}/cases", params={"cursor": "%%%"}, headers=w.auth)
    assert bad.status_code == 422
    assert bad.json()["reason"] == "invalid_cursor"
    assert w.client.get(f"{w.base}/cases", params={"limit": 0}, headers=w.auth).status_code == 422


def test_transition_status_per_role(world: _World) -> None:
    w = world
    subject_id, subject_auth = w.agent("Betroffen")
    _triage_id, triage_auth = w.agent("Builder", {"case_triage": True})
    viewer = w.member(WorkspaceRole.viewer)
    editor = w.member(WorkspaceRole.editor)
    case = w.report(viewer, _case_body(subject_id))
    cid = case["id"]
    assert w.put_elements(cid, [{"target": "model_limit"}]).status_code == 200

    # viewer sieht den eigenen Fall, triagiert ihn aber nicht.
    as_viewer = w.transition(cid, {"to": "triaged"}, viewer)
    assert as_viewer.status_code == 403
    # Agent ohne case_triage: 403 Capability; Richter-Ziele immer 403 human_only.
    plain = w.transition(cid, {"to": "triaged"}, subject_auth)
    assert plain.status_code == 403
    assert plain.json()["reason"] == "missing_capability"
    judge = w.transition(cid, {"to": "dismissed", "note": "n"}, triage_auth)
    assert judge.status_code == 403
    assert judge.json()["reason"] == "case_transition_human_only"
    # Phase E: in_progress/verified sind 409 mit requires=phase_e.
    later = w.transition(cid, {"to": "in_progress"}, editor)
    assert later.status_code == 409
    assert later.json()["reason"] == "case_transition_forbidden"
    assert later.json()["params"]["requires"] == "phase_e"
    # Unbekanntes Feld im Body: 422.
    assert w.transition(cid, {"to": "triaged", "foo": 1}, editor).status_code == 422

    ok = w.transition(cid, {"to": "triaged"}, triage_auth)
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "triaged"
    # Pflichtfeld fehlt: 409 mit params.missing.
    no_note = w.transition(cid, {"to": "dismissed"}, editor)
    assert no_note.status_code == 409
    assert no_note.json()["params"]["missing"] == "note"
    done = w.transition(cid, {"to": "dismissed", "note": "kein Fehler"}, editor)
    assert done.status_code == 200
    assert done.json()["status"] == "dismissed"
    events = w.client.get(f"{w.base}/cases/{cid}", headers=editor).json()["events"]
    assert [e["event"] for e in events if e["event"] in ("triaged", "dismissed")] == [
        "triaged",
        "dismissed",
    ]
    assert events[-1]["note"] == "kein Fehler"


def test_agent_bound_call_without_policy_cannot_triage(world: _World) -> None:
    """PM 2026-10-08: agent-gebunden mit `tool_policy=None` ist kein Triage-Freibrief.

    Der Zustand entsteht im echten Auth-Pfad, wenn der gebundene Agent
    zwischen Token-Auth und Policy-Load verschwindet (`_load_agent_tool_policy`).
    Hier per `dependency_overrides`, mit echtem Mandanten-Scope.
    """
    w = world
    subject_id, _ = w.agent("Betroffen")
    cid = w.report(w.auth, _case_body(subject_id))["id"]
    assert w.put_elements(cid, [{"target": "model_limit"}]).status_code == 200
    ctx = WorkspaceContext(
        workspace_id=w.ws,
        user_id=w.owner,
        role=WorkspaceRole.admin,
        is_api_token=True,
        agent_id=UUID(subject_id),
        tool_policy=None,
    )

    async def _no_policy() -> AsyncIterator[WorkspaceContext]:
        async with tenant_scope(w.ws, None):
            yield ctx

    app.dependency_overrides[get_current_workspace] = _no_policy
    try:
        # Lesen bleibt: der Fall ist ueber diesen Agenten.
        assert w.client.get(f"{w.base}/cases/{cid}").status_code == 200
        triage = w.client.post(f"{w.base}/cases/{cid}/transition", json={"to": "triaged"})
        assert triage.status_code == 403, triage.text
        assert triage.json()["reason"] == "missing_capability"
        assign = w.client.put(
            f"{w.base}/cases/{cid}/elements", json={"elements": [{"target": "tool_policy"}]}
        )
        assert assign.status_code == 403, assign.text
    finally:
        app.dependency_overrides.pop(get_current_workspace, None)
    detail = w.client.get(f"{w.base}/cases/{cid}", headers=w.auth).json()
    assert detail["case"]["status"] == "open"
    assert [e["target"] for e in detail["elements"]] == ["model_limit"]


def test_elements_replace_semantics(world: _World) -> None:
    w = world
    subject_id, subject_auth = w.agent("Betroffen")
    _triage_id, triage_auth = w.agent("Builder", {"case_triage": True})
    viewer = w.member(WorkspaceRole.viewer)
    pb1 = w.playbook("Eins")
    pb2 = w.playbook("Zwei")
    cid = w.report(viewer, _case_body(subject_id))["id"]

    first = w.put_elements(
        cid, [{"target": "playbook", "entity_id": pb1}, {"target": "model_limit"}]
    )
    assert first.status_code == 200, first.text
    assert {(e["target"], e["entity_id"]) for e in first.json()} == {
        ("playbook", pb1),
        ("model_limit", None),
    }
    # Ersetzen, nicht ergaenzen: nur noch pb2, durch den Builder-Agenten.
    second = w.put_elements(cid, [{"target": "playbook", "entity_id": pb2}], triage_auth)
    assert second.status_code == 200, second.text
    assert [(e["target"], e["entity_id"]) for e in second.json()] == [("playbook", pb2)]
    assert second.json()[0]["assigned_by_kind"] == "agent"
    detail = w.client.get(f"{w.base}/cases/{cid}", headers=w.auth).json()
    assert [(e["target"], e["entity_id"]) for e in detail["elements"]] == [("playbook", pb2)]
    kinds = [e["event"] for e in detail["events"]]
    assert kinds.count("element_assigned") == 3
    assert kinds.count("element_unassigned") == 2
    # Leere Liste leert die Zuordnung.
    empty = w.put_elements(cid, [])
    assert empty.status_code == 200
    assert empty.json() == []

    # Rechte und Eingaben.
    assert w.put_elements(cid, [{"target": "model_limit"}], viewer).status_code == 403
    plain = w.put_elements(cid, [{"target": "model_limit"}], subject_auth)
    assert plain.status_code == 403
    assert plain.json()["reason"] == "missing_capability"
    unknown = w.put_elements(cid, [{"target": "playbook", "entity_id": str(uuid4())}])
    assert unknown.status_code == 404
    assert unknown.json()["reason"] == "playbook_not_found"
    assert w.put_elements(cid, [{"target": "model_limit", "entity_id": pb1}]).status_code == 422
    too_many = [{"target": "playbook", "entity_id": pb1}] * 51
    assert w.put_elements(cid, too_many).status_code == 422
    assert w.client.get(f"{w.base}/cases/{cid}", headers=w.auth).json()["elements"] == []


def test_statement_and_delete(world: _World) -> None:
    w = world
    subject_id, subject_auth = w.agent("Betroffen")
    _other_id, other_auth = w.agent("Anderer", {"case_triage": True})
    viewer = w.member(WorkspaceRole.viewer)
    editor = w.member(WorkspaceRole.editor)
    cid = w.report(viewer, _case_body(subject_id))["id"]
    statement = {
        "followed_instruction": "Playbook X, Schritt 2",
        "missing_information": "",
        "conflict": "",
    }

    made = w.client.post(f"{w.base}/cases/{cid}/statement", json=statement, headers=subject_auth)
    assert made.status_code == 201, made.text
    assert made.json()["agent_id"] == subject_id
    for headers in (other_auth, w.auth):
        refused = w.client.post(f"{w.base}/cases/{cid}/statement", json=statement, headers=headers)
        assert refused.status_code == 403
        assert refused.json()["reason"] == "case_statement_not_subject"
    detail = w.client.get(f"{w.base}/cases/{cid}", headers=w.auth).json()
    assert [s["followed_instruction"] for s in detail["statements"]] == ["Playbook X, Schritt 2"]

    # Loeschen: viewer und Agenten nie, editor ja (Q6); danach 404.
    assert w.client.delete(f"{w.base}/cases/{cid}", headers=viewer).status_code == 403
    by_agent = w.client.delete(f"{w.base}/cases/{cid}", headers=other_auth)
    assert by_agent.status_code == 403
    assert by_agent.json()["reason"] == "missing_capability"
    assert w.client.delete(f"{w.base}/cases/{cid}", headers=editor).status_code == 204
    assert w.client.get(f"{w.base}/cases/{cid}", headers=w.auth).status_code == 404
    assert w.client.delete(f"{w.base}/cases/{cid}", headers=editor).status_code == 404


def test_case_from_foreign_workspace_is_404(world: _World, make_auth_headers: Any) -> None:
    """Fall-ID aus Workspace B im Pfad von Workspace A: 404, nichts geschrieben."""
    w = world
    other_owner = fresh_user_id()
    other_ws = setup_workspace(other_owner)
    w.extra_users.append(other_owner)
    other_auth = make_auth_headers(other_owner)
    other_base = f"/v1/workspaces/{other_ws}"
    foreign_agent, _ = agent_token(w.client, other_base, "Fremd", {}, other_auth)
    foreign = w.client.post(
        f"{other_base}/cases", json=_case_body(foreign_agent), headers=other_auth
    ).json()["id"]
    _own_agent, own_agent_auth = w.agent("Eigen", {"case_triage": True})

    calls = [
        ("GET", f"/cases/{foreign}", None, w.auth),
        ("POST", f"/cases/{foreign}/transition", {"to": "dismissed", "note": "n"}, w.auth),
        ("PUT", f"/cases/{foreign}/elements", {"elements": [{"target": "model_limit"}]}, w.auth),
        ("DELETE", f"/cases/{foreign}", None, w.auth),
        (
            "POST",
            f"/cases/{foreign}/statement",
            {"followed_instruction": "", "missing_information": "", "conflict": ""},
            own_agent_auth,
        ),
    ]
    for method, path, body, headers in calls:
        res = w.client.request(method, f"{w.base}{path}", json=body, headers=headers)
        assert res.status_code == 404, (method, path, res.text)
        assert res.json()["reason"] == "case_not_found", (method, path)
    # Ein Fall ueber einen fremden Agenten laesst sich nicht melden.
    reported = w.client.post(f"{w.base}/cases", json=_case_body(foreign_agent), headers=w.auth)
    assert reported.status_code == 404
    assert reported.json()["reason"] == "agent_not_found"
    # Fremde Faelle tauchen in keiner Liste auf.
    assert foreign not in w.ids(w.auth)
    assert w.ids(w.auth, agent_id=foreign_agent) == []
    # B ist unveraendert.
    untouched = w.client.get(f"{other_base}/cases/{foreign}", headers=other_auth).json()
    assert untouched["case"]["status"] == "open"
    assert untouched["elements"] == []
