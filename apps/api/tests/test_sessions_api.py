"""Integrationstests Lernschleife E2b-3: REST fuer Protokolle und Massnahmen (ADR-0053 6.6).

Belegt am Router (echte DB, echter Auth-Pfad) den Vertrag der HTTP-Schicht:

- **Statuscodes je Rolle:** viewer und Agent ohne `case_triage` 403
  `missing_capability` an allen sieben Routen; editor und Agent mit
  `case_triage` duerfen einreichen, lesen, verknuepfen und die Kennzahlen
  lesen; review und withdraw nur Mensch ab editor — der Builder bekommt 403,
  auch mit `case_triage`.
- **Fehlergruende:** `agent_not_found`, `session_cases_invalid`,
  `measure_test_case_required`, `session_not_found`, `measure_not_found`,
  `test_subject_version_not_found`, `measure_transition_forbidden` (mit
  `params.state`), 422 fuer Bodys mit fremden Feldern und fuer `ineffective`
  bzw. withdraw ohne Begruendung.
- **Liste:** Filter `agent_id`/`case_id`/`due`, Zeilenzaehler (QE2 = a),
  Keyset-Seite ueber `X-Next-Cursor`.
- **Fremder Workspace:** jede Route mit einer ID aus Workspace B -> 404.
- **Ohne geladene Policy:** ein agent-gebundener Aufruf ohne Policy darf nichts.
- **write_limit:** jede schreibende Route liefert beim zweiten Aufruf 429.

Mutationsprobe: Rechte prueft allein der Service. Nimmt man dort eine der
Pruefungen heraus (`require_triage_right` in `SessionService`/`MeasureService`,
`require_human_editor` in review/withdraw), wird `test_rights_per_role` rot;
nimmt man am Router `@limiter.limit(write_limit)` von einer Schreibroute,
wird `test_write_routes_are_rate_limited` rot.

Die Geschaeftsregeln selbst (jede Event-Folge, Kennzahlen) decken
`test_session_service.py` und `test_measure_service.py` ab.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from who2be_api.core import rate_limit
from who2be_api.core.config import Settings
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.core.tenancy import tenant_scope
from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

pytestmark = pytest.mark.integration

_PERSONA = {"description": "d", "system_prompt": "s", "content": {"blocks": []}}


def _add_member(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> None:
    db_execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, $3) "
        "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role",
        workspace_id,
        user_id,
        role.value,
    )


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

    def post(self, path: str, body: Any, headers: dict[str, str] | None = None) -> Any:
        return self.client.post(f"{self.base}{path}", json=body, headers=headers or self.auth)

    def get(self, path: str, headers: dict[str, str] | None = None, **params: Any) -> Any:
        return self.client.get(f"{self.base}{path}", params=params, headers=headers or self.auth)

    def created(self, path: str, body: Any) -> dict[str, Any]:
        res = self.post(path, body)
        assert res.status_code == 201, res.text
        data: dict[str, Any] = res.json()
        return data

    def triaged_case(self, agent_id: str) -> str:
        """Fall in `triaged` (Zuordnung `model_limit`), damit das Protokoll ihn startet."""
        cid = self.created(
            "/cases",
            {"agent_id": agent_id, "situation": "s", "behavior": "b", "expected_behavior": "e"},
        )["id"]
        put = self.client.put(
            f"{self.base}/cases/{cid}/elements",
            json={"elements": [{"target": "model_limit"}]},
            headers=self.auth,
        )
        assert put.status_code == 200, put.text
        assert self.post(f"/cases/{cid}/transition", {"to": "triaged"}).status_code == 200
        return str(cid)

    def test_case(self, agent_id: str) -> str:
        body = {"agent_id": agent_id, "title": "t", "input": "i", "expected_behavior": "e"}
        return str(self.created("/test-cases", body)["id"])

    def persona(self) -> tuple[str, str]:
        persona = self.created("/personas", {"name": f"p-{uuid4().hex[:6]}", "content": _PERSONA})
        versions = self.get(f"/personas/{persona['id']}/versions").json()
        return str(persona["id"]), str(versions[0]["id"])

    def protocol(
        self, agent_id: str, persona_id: str, *, summary: str = "Protokoll"
    ) -> dict[str, Any]:
        """Protokollbody mit einem triagierten Fall und einer Massnahme an der Persona."""
        case_id = self.triaged_case(agent_id)
        return {
            "agent_id": agent_id,
            "trigger": "manual",
            "case_ids": [case_id],
            "summary": summary,
            "follow_up_at": "2099-01-01",
            "measures": [
                {
                    "case_ids": [case_id],
                    "target": "persona",
                    "entity_id": persona_id,
                    "change_summary": "c",
                    "test_case_id": self.test_case(agent_id),
                    "success_criterion": "s",
                    "counterposition": "k",
                }
            ],
        }

    def activate(self, measure_id: str, version_id: str) -> None:
        """`activated` wie E3 es schreibt (System, mit Version)."""
        db_execute(
            "INSERT INTO measure_event (workspace_id, measure_id, event, actor_kind, "
            " version_entity_type, version_id) VALUES ($1, $2::uuid, 'activated', 'system', "
            " 'persona', $3::uuid)",
            self.ws,
            measure_id,
            version_id,
        )


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


def _reason(res: Any) -> str:
    reason: str = res.json()["reason"]
    return reason


def test_submit_and_read_happy_path(world: _World) -> None:
    w = world
    agent_id, _ = w.agent("Betroffen")
    persona_id, _ = w.persona()
    body = w.protocol(agent_id, persona_id)

    res = w.post("/feedback-sessions", body)
    assert res.status_code == 201, res.text
    out = res.json()
    session = out["detail"]["session"]
    measure = out["detail"]["measures"][0]
    assert session["submitted_by_kind"] == "human"
    assert session["case_ids"] == body["case_ids"]
    assert measure["session_id"] == session["id"]
    assert measure["state"] == "agreed"
    # W-E2 = a: der triagierte Fall geht in derselben Transaktion auf in_progress.
    assert out["cases_started"] == body["case_ids"]
    assert out["cases_unchanged"] == []
    case = w.get(f"/cases/{body['case_ids'][0]}").json()["case"]
    assert case["status"] == "in_progress"

    detail = w.get(f"/feedback-sessions/{session['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["session"]["summary"] == "Protokoll"
    assert [m["id"] for m in detail.json()["measures"]] == [measure["id"]]

    follow = w.get(f"/measures/{measure['id']}/follow-up")
    assert follow.status_code == 200, follow.text
    report = follow.json()
    assert report["measure_id"] == measure["id"]
    assert report["state"] == "agreed"
    assert report["reviewable"] is False
    assert report["insufficient"] is True
    assert report["min_uses"] > 0


def test_rights_per_role(world: _World) -> None:
    """viewer und Agent ohne case_triage: 403 ueberall; Builder: nie review/withdraw."""
    w = world
    agent_id, plain_auth = w.agent("Betroffen")
    _builder_id, builder_auth = w.agent("Builder", {"case_triage": True})
    viewer = w.member(WorkspaceRole.viewer)
    editor = w.member(WorkspaceRole.editor)
    persona_id, version_id = w.persona()

    # Einreichen: viewer und Agent ohne case_triage nicht; editor und Builder ja.
    for headers in (viewer, plain_auth):
        refused = w.post("/feedback-sessions", w.protocol(agent_id, persona_id), headers)
        assert refused.status_code == 403, refused.text
    by_builder = w.post("/feedback-sessions", w.protocol(agent_id, persona_id), builder_auth)
    assert by_builder.status_code == 201, by_builder.text
    assert by_builder.json()["detail"]["session"]["submitted_by_kind"] == "agent"
    by_editor = w.post("/feedback-sessions", w.protocol(agent_id, persona_id), editor)
    assert by_editor.status_code == 201, by_editor.text
    session_id = by_editor.json()["detail"]["session"]["id"]
    measure_id = by_editor.json()["detail"]["measures"][0]["id"]

    # Lesen, Verknuepfen, Kennzahlen: viewer und Agent ohne case_triage 403.
    reads = [
        ("GET", "/feedback-sessions", None),
        ("GET", f"/feedback-sessions/{session_id}", None),
        ("GET", f"/measures/{measure_id}/follow-up", None),
        (
            "POST",
            f"/measures/{measure_id}/link-draft",
            {"version_entity_type": "persona", "version_id": version_id},
        ),
    ]
    for method, path, body in reads:
        for headers in (viewer, plain_auth):
            res = w.client.request(method, f"{w.base}{path}", json=body, headers=headers)
            assert res.status_code == 403, (method, path, res.text)
            if headers is plain_auth:
                assert _reason(res) == "missing_capability"
        for headers in (editor, builder_auth):
            res = w.client.request(method, f"{w.base}{path}", json=body, headers=headers)
            assert res.status_code in (200, 201), (method, path, res.text)

    # review und withdraw: nur Mensch ab editor; der Builder auch mit case_triage nicht.
    decisions = [
        (f"/measures/{measure_id}/review", {"verdict": "not_measurable"}),
        (f"/measures/{measure_id}/withdraw", {"note": "Doch nicht."}),
    ]
    for path, body in decisions:
        for headers in (viewer, plain_auth, builder_auth):
            res = w.post(path, body, headers)
            assert res.status_code == 403, (path, res.text)
        assert _reason(w.post(path, body, builder_auth)) == "missing_capability"
    # Keine der Abweisungen hat geschrieben: nur die zwei link-draft-Events.
    events = w.get(f"/feedback-sessions/{session_id}").json()["measures"][0]["events"]
    assert [e["event"] for e in events] == ["draft_linked", "draft_linked"]
    assert [e["actor_kind"] for e in events] == ["human", "agent"]

    # editor darf zurueckziehen.
    done = w.post(f"/measures/{measure_id}/withdraw", {"note": "Doch nicht."}, editor)
    assert done.status_code == 200, done.text
    assert done.json()["event"]["event"] == "withdrawn"


def test_submit_error_reasons(world: _World) -> None:
    w = world
    agent_id, _ = w.agent("Betroffen")
    other_id, _ = w.agent("Anderer")
    persona_id, _ = w.persona()

    ghost = w.post(
        "/feedback-sessions", w.protocol(agent_id, persona_id) | {"agent_id": str(uuid4())}
    )
    assert ghost.status_code == 404
    assert _reason(ghost) == "agent_not_found"

    # Fall eines anderen Agenten im Protokoll.
    foreign_case = w.triaged_case(other_id)
    body = w.protocol(agent_id, persona_id)
    body["case_ids"].append(foreign_case)
    wrong_case = w.post("/feedback-sessions", body)
    assert wrong_case.status_code == 422
    assert _reason(wrong_case) == "session_cases_invalid"
    assert wrong_case.json()["params"]["case_ids"] == [foreign_case]

    # Pruefall eines anderen Agenten an der Massnahme.
    body = w.protocol(agent_id, persona_id)
    body["measures"][0]["test_case_id"] = w.test_case(other_id)
    no_test = w.post("/feedback-sessions", body)
    assert no_test.status_code == 422
    assert _reason(no_test) == "measure_test_case_required"

    supersedes = w.post(
        "/feedback-sessions", w.protocol(agent_id, persona_id) | {"supersedes_id": str(uuid4())}
    )
    assert supersedes.status_code == 404
    assert _reason(supersedes) == "session_not_found"

    # Einreicher-Felder und Unbekanntes im Body: 422 (Einreicher aus dem Aufrufweg).
    for extra in ({"submitted_by_kind": "human"}, {"foo": 1}):
        bad = w.post("/feedback-sessions", w.protocol(agent_id, persona_id) | extra)
        assert bad.status_code == 422, extra
    # Nichts davon hat ein Protokoll hinterlassen.
    assert w.get("/feedback-sessions").json() == []


def test_measure_error_reasons(world: _World) -> None:
    w = world
    agent_id, _ = w.agent("Betroffen")
    persona_id, version_id = w.persona()
    _other_persona, other_version = w.persona()
    out = w.created("/feedback-sessions", w.protocol(agent_id, persona_id))
    measure_id = out["detail"]["measures"][0]["id"]
    unknown = str(uuid4())

    assert _reason(w.get(f"/feedback-sessions/{unknown}")) == "session_not_found"
    for method, path, body in (
        ("GET", f"/measures/{unknown}/follow-up", None),
        ("POST", f"/measures/{unknown}/review", {"verdict": "effective"}),
        ("POST", f"/measures/{unknown}/withdraw", {"note": "n"}),
    ):
        res = w.client.request(method, f"{w.base}{path}", json=body, headers=w.auth)
        assert res.status_code == 404, (path, res.text)
        assert _reason(res) == "measure_not_found"
    # link-draft: Version eines anderen Elements bzw. unbekannte Version -> 404.
    for version in (other_version, unknown):
        res = w.post(
            f"/measures/{measure_id}/link-draft",
            {"version_entity_type": "persona", "version_id": version},
        )
        assert res.status_code == 404, res.text
        assert _reason(res) == "test_subject_version_not_found"
    bad_type = w.post(
        f"/measures/{measure_id}/link-draft",
        {"version_entity_type": "memory", "version_id": version_id},
    )
    assert bad_type.status_code == 422

    # review vor der Aktivierung: 409 mit dem Zustand.
    early = w.post(f"/measures/{measure_id}/review", {"verdict": "effective"})
    assert early.status_code == 409, early.text
    assert _reason(early) == "measure_transition_forbidden"
    assert early.json()["params"] == {"state": "agreed", "action": "review"}

    # Begruendung: ineffective und withdraw ohne note sind 422, nicht 500.
    w.activate(measure_id, version_id)
    assert w.post(f"/measures/{measure_id}/review", {"verdict": "ineffective"}).status_code == 422
    assert w.post(f"/measures/{measure_id}/withdraw", {}).status_code == 422
    assert w.post(f"/measures/{measure_id}/review", {"verdict": "x"}).status_code == 422

    # Nach der Aktivierung: genau einmal einstufen, danach nur noch lesen.
    first = w.post(
        f"/measures/{measure_id}/review", {"verdict": "ineffective", "note": "Hilft nicht."}
    )
    assert first.status_code == 201, first.text
    assert first.json()["verdict"] == "ineffective"
    again = w.post(f"/measures/{measure_id}/review", {"verdict": "effective"})
    assert again.status_code == 409
    assert again.json()["params"]["state"] == "ineffective"
    late = w.post(f"/measures/{measure_id}/withdraw", {"note": "n"})
    assert late.status_code == 409
    assert _reason(late) == "measure_transition_forbidden"
    relink = w.post(
        f"/measures/{measure_id}/link-draft",
        {"version_entity_type": "persona", "version_id": version_id},
    )
    assert relink.status_code == 409


def test_withdraw_resets_cases(world: _World) -> None:
    w = world
    agent_id, _ = w.agent("Betroffen")
    persona_id, _ = w.persona()
    out = w.created("/feedback-sessions", w.protocol(agent_id, persona_id))
    measure_id = out["detail"]["measures"][0]["id"]
    case_id = out["cases_started"][0]

    res = w.post(f"/measures/{measure_id}/withdraw", {"note": "Falsche Stelle."})
    assert res.status_code == 200, res.text
    assert res.json()["cases_reset"] == [case_id]
    assert res.json()["event"]["note"] == "Falsche Stelle."
    assert w.get(f"/cases/{case_id}").json()["case"]["status"] == "triaged"


def test_list_filters_and_pagination(world: _World) -> None:
    w = world
    a_id, _ = w.agent("A")
    b_id, _ = w.agent("B")
    persona_id, _ = w.persona()
    on_a = [
        w.created("/feedback-sessions", w.protocol(a_id, persona_id, summary=f"A{i}"))
        for i in range(3)
    ]
    on_b = w.created("/feedback-sessions", w.protocol(b_id, persona_id, summary="B"))

    def ids(res: Any) -> list[str]:
        assert res.status_code == 200, res.text
        return [s["id"] for s in res.json()]

    a_ids = [s["detail"]["session"]["id"] for s in on_a]
    everything = ids(w.get("/feedback-sessions"))
    assert set(everything) == {*a_ids, on_b["detail"]["session"]["id"]}
    # Neueste zuerst.
    assert everything[0] == on_b["detail"]["session"]["id"]
    assert ids(w.get("/feedback-sessions", agent_id=a_id)) == list(reversed(a_ids))
    first_case = on_a[0]["detail"]["session"]["case_ids"][0]
    assert ids(w.get("/feedback-sessions", case_id=first_case)) == [a_ids[0]]
    assert ids(w.get("/feedback-sessions", agent_id=b_id, case_id=first_case)) == []

    # Keyset-Seiten ueber X-Next-Cursor.
    page1 = w.get("/feedback-sessions", agent_id=a_id, limit=2)
    cursor = page1.headers.get("X-Next-Cursor")
    assert cursor, page1.headers
    page2 = w.get("/feedback-sessions", agent_id=a_id, limit=2, cursor=cursor)
    assert "X-Next-Cursor" not in page2.headers
    assert ids(page1) + ids(page2) == list(reversed(a_ids))
    assert w.get("/feedback-sessions", cursor="kaputt").status_code == 422
    assert w.get("/feedback-sessions", limit=0).status_code == 422


def test_list_due_and_row_counters(world: _World) -> None:
    """QE2 = a am Router: Zaehler je Zeile, `due=true`, Cursor ueber das due-Ergebnis.

    Die Grenzfaelle (gestern/heute/morgen, Endzustaende) belegt der
    Service-Test mit festem Stichtag; hier zaehlt der HTTP-Vertrag.
    """
    w = world
    agent_id, _ = w.agent("Betroffen")
    persona_id, _ = w.persona()

    def submit(follow_up_at: str, summary: str, **extra: Any) -> dict[str, Any]:
        body = w.protocol(agent_id, persona_id, summary=summary)
        body["measures"][0]["follow_up_at"] = follow_up_at
        return w.created("/feedback-sessions", body | extra)

    due_old = submit("2000-01-01", "faellig alt")
    later = submit("2099-01-01", "spaeter")
    due_new = submit("2000-01-02", "faellig neu", supersedes_id=due_old["detail"]["session"]["id"])
    withdrawn = submit("2000-01-03", "zurueckgezogen")
    measure_id = withdrawn["detail"]["measures"][0]["id"]
    assert w.post(f"/measures/{measure_id}/withdraw", {"note": "n"}).status_code == 200

    def sid(out: dict[str, Any]) -> str:
        return str(out["detail"]["session"]["id"])

    res = w.get("/feedback-sessions")
    assert res.status_code == 200, res.text
    rows = {r["id"]: r for r in res.json()}
    fields = (
        "case_count",
        "measure_count",
        "due_measure_count",
        "next_follow_up_at",
        "superseded_by_id",
    )
    assert {k: tuple(r[f] for f in fields) for k, r in rows.items()} == {
        sid(due_old): (1, 1, 1, "2000-01-01", sid(due_new)),
        sid(later): (1, 1, 0, "2099-01-01", None),
        sid(due_new): (1, 1, 1, "2000-01-02", None),
        sid(withdrawn): (1, 1, 0, None, None),
    }
    # GET /feedback-sessions/{id}: derselbe Nachfolger wie in der Liste,
    # null fuer ein nicht ersetztes Protokoll (additives Feld neben session/measures).
    for key, row in rows.items():
        detail = w.get(f"/feedback-sessions/{key}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["superseded_by_id"] == row["superseded_by_id"], key
    assert w.get(f"/feedback-sessions/{sid(due_old)}").json()["superseded_by_id"] == sid(due_new)
    assert w.get(f"/feedback-sessions/{sid(later)}").json()["superseded_by_id"] is None

    def ids(res: Any) -> list[str]:
        assert res.status_code == 200, res.text
        return [s["id"] for s in res.json()]

    assert ids(w.get("/feedback-sessions", due="true")) == [sid(due_new), sid(due_old)]
    assert ids(w.get("/feedback-sessions", due="false")) == ids(w.get("/feedback-sessions"))
    case_id = later["detail"]["session"]["case_ids"][0]
    assert ids(w.get("/feedback-sessions", due="true", case_id=case_id)) == []
    page1 = w.get("/feedback-sessions", due="true", agent_id=agent_id, limit=1)
    cursor = page1.headers.get("X-Next-Cursor")
    assert cursor, page1.headers
    page2 = w.get("/feedback-sessions", due="true", agent_id=agent_id, limit=1, cursor=cursor)
    assert "X-Next-Cursor" not in page2.headers
    assert ids(page1) + ids(page2) == [sid(due_new), sid(due_old)]
    assert w.get("/feedback-sessions", due="vielleicht").status_code == 422


def test_foreign_workspace_is_404(world: _World, make_auth_headers: Any) -> None:
    """IDs aus Workspace B im Pfad von Workspace A: 404 wie unbekannt, nichts geschrieben."""
    w = world
    other_owner = fresh_user_id()
    other_ws = setup_workspace(other_owner)
    w.extra_users.append(other_owner)
    other = _World(w.client, other_ws, other_owner, make_auth_headers(other_owner), None)
    foreign_agent, _ = other.agent("Fremd")
    foreign_persona, foreign_version = other.persona()
    out = other.created("/feedback-sessions", other.protocol(foreign_agent, foreign_persona))
    session_id = out["detail"]["session"]["id"]
    measure_id = out["detail"]["measures"][0]["id"]
    _own_builder, builder_auth = w.agent("Builder", {"case_triage": True})

    calls: list[tuple[str, str, Any, dict[str, str], str]] = [
        ("GET", f"/feedback-sessions/{session_id}", None, w.auth, "session_not_found"),
        ("GET", f"/measures/{measure_id}/follow-up", None, builder_auth, "measure_not_found"),
        (
            "POST",
            f"/measures/{measure_id}/link-draft",
            {"version_entity_type": "persona", "version_id": foreign_version},
            w.auth,
            "measure_not_found",
        ),
        (
            "POST",
            f"/measures/{measure_id}/review",
            {"verdict": "effective"},
            w.auth,
            "measure_not_found",
        ),
        ("POST", f"/measures/{measure_id}/withdraw", {"note": "n"}, w.auth, "measure_not_found"),
        (
            "POST",
            "/feedback-sessions",
            {
                "agent_id": foreign_agent,
                "trigger": "manual",
                "summary": "x",
                "follow_up_at": "2099-01-01",
            },
            w.auth,
            "agent_not_found",
        ),
    ]
    for method, path, body, headers, reason in calls:
        res = w.client.request(method, f"{w.base}{path}", json=body, headers=headers)
        assert res.status_code == 404, (method, path, res.text)
        assert _reason(res) == reason
    # Nichts in B geschrieben, A sieht keine Protokolle.
    detail = other.get(f"/feedback-sessions/{session_id}").json()
    assert detail["measures"][0]["events"] == []
    assert w.get("/feedback-sessions").json() == []


def test_agent_bound_call_without_policy_is_refused(world: _World) -> None:
    """Agent-gebunden mit `tool_policy=None` ist kein Freibrief (Muster `test_cases_api`)."""
    w = world
    agent_id, _ = w.agent("Betroffen")
    persona_id, version_id = w.persona()
    body = w.protocol(agent_id, persona_id)
    out = w.created("/feedback-sessions", w.protocol(agent_id, persona_id))
    measure_id = out["detail"]["measures"][0]["id"]
    ctx = WorkspaceContext(
        workspace_id=w.ws,
        user_id=w.owner,
        role=WorkspaceRole.admin,
        is_api_token=True,
        agent_id=UUID(agent_id),
        tool_policy=None,
    )

    async def _no_policy() -> AsyncIterator[WorkspaceContext]:
        async with tenant_scope(w.ws, None):
            yield ctx

    app.dependency_overrides[get_current_workspace] = _no_policy
    try:
        calls = [
            ("POST", "/feedback-sessions", body),
            ("GET", "/feedback-sessions", None),
            ("GET", f"/measures/{measure_id}/follow-up", None),
            (
                "POST",
                f"/measures/{measure_id}/link-draft",
                {"version_entity_type": "persona", "version_id": version_id},
            ),
            ("POST", f"/measures/{measure_id}/withdraw", {"note": "n"}),
        ]
        for method, path, payload in calls:
            res = w.client.request(method, f"{w.base}{path}", json=payload)
            assert res.status_code == 403, (method, path, res.text)
    finally:
        app.dependency_overrides.pop(get_current_workspace, None)
    assert len(w.get("/feedback-sessions").json()) == 1
    assert w.get(f"/measures/{measure_id}/follow-up").json()["state"] == "agreed"


_WRITE_ROUTES: list[tuple[str, str, dict[str, Any]]] = [
    (
        "submit",
        "/feedback-sessions",
        {
            "agent_id": str(uuid4()),
            "trigger": "manual",
            "summary": "x",
            "follow_up_at": "2099-01-01",
        },
    ),
    (
        "link_draft",
        "/measures/{mid}/link-draft",
        {"version_entity_type": "persona", "version_id": str(uuid4())},
    ),
    ("review", "/measures/{mid}/review", {"verdict": "effective"}),
    ("withdraw", "/measures/{mid}/withdraw", {"note": "n"}),
]


@pytest.mark.parametrize(("name", "path", "body"), _WRITE_ROUTES, ids=[r[0] for r in _WRITE_ROUTES])
def test_write_routes_are_rate_limited(
    name: str,
    path: str,
    body: dict[str, Any],
    world: _World,
    patched_jwt_secret: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`@limiter.limit(write_limit)`: bei 1/minute ist der zweite Aufruf 429.

    Gueltige Bodys mit unbekannten IDs (404 beim ersten Aufruf): die
    Body-Validierung laeuft vor dem Limiter, der Lookup danach.
    """
    settings = Settings(jwt_secret=patched_jwt_secret, rate_limit_write="1/minute")
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)
    rate_limit.limiter.reset()
    url = path.format(mid=uuid4())
    try:
        first = world.post(url, body)
        second = world.post(url, body)
    finally:
        rate_limit.limiter.reset()
    assert first.status_code == 404, f"{name}: erster Aufruf {first.status_code} {first.text}"
    assert second.status_code == 429, f"{name}: Limit greift nicht ({second.status_code})"
