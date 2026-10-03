"""REST fuer `POST /memories/batch` und `DELETE /members/{user_id}/memories` (C3c-2b).

ADR-0053 6.4.1. Router-Tests gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`).
Die Fachlogik (Einzelpruefung je Eintrag, `memory_held`, Sichtbarkeit,
Audit) belegen die Service-Tests aus C3c-2a (`test_memory_batch_purge.py`);
hier geht es um den Weg ueber HTTP. Kritische Zusicherungen:

- Stapel: Teilerfolg ist 200 mit einem Ergebnis je Eintrag in der
  Reihenfolge der Auswahl (`id`, `ok`, `reason`); geaendert ist genau, was
  `ok` meldet. Fremdes Nutzergedaechtnis ist `memory_not_found`, auch fuer
  `admin`, und sein Inhalt erscheint nicht in der Antwort.
- Filter-Modus ueber HTTP, abweichende Zahl 409
  `memory_batch_count_mismatch` mit `params.count`; Body-Grenzen als 422.
- `viewer` mit Agentengedaechtnis: 403 auf den ganzen Aufruf, nichts
  geaendert; agent-gebundener Token 403.
- Purge: nur `admin` (editor/viewer und agent-gebundener Token 403
  `insufficient_role`), Antwort genau `{deleted: n}` ohne
  Inhalt oder IDs, inhaltsfreie `audit_log`-Zeile.
"""

from collections.abc import Callable, Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")


class Env:
    def __init__(self, client: TestClient, make_auth: AuthFactory) -> None:
        self.client = client
        self.owner, self.editor, self.viewer = fresh_user_id(), fresh_user_id(), fresh_user_id()
        self.ws = setup_workspace(self.owner)
        for user, role in ((self.editor, "editor"), (self.viewer, "viewer")):
            db_execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, $3)",
                self.ws,
                user,
                role,
            )
        self.prefix = f"/v1/workspaces/{self.ws}"
        self.admin_h = make_auth(self.owner)
        self.editor_h = make_auth(self.editor)
        self.viewer_h = make_auth(self.viewer)
        agent, self.agent_h = agent_token(
            client, self.prefix, "C3c2b-Agent", {"memory_mode": "auto"}, self.admin_h
        )
        self.agent = UUID(agent)

    def users(self) -> list[UUID]:
        return [self.owner, self.editor, self.viewer]

    def batch(self, headers: dict[str, str], body: dict[str, Any]) -> Any:
        return self.client.post(f"{self.prefix}/memories/batch", json=body, headers=headers)

    def purge(self, headers: dict[str, str], user: UUID) -> Any:
        return self.client.delete(f"{self.prefix}/members/{user}/memories", headers=headers)

    def memory(
        self,
        fact: str,
        *,
        subject: UUID | None = None,
        status: str = "pending",
        origin: str = "user_stated",
    ) -> UUID:
        """Legt einen Eintrag direkt an (an der Logik vorbei)."""
        memory_id: UUID = db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, subject_user_id) "
            "VALUES ($1, $2, $3, $4, $5, 'preference', 6, 'user_fact', $6, $7, $8) "
            "RETURNING id",
            self.ws,
            None if subject is not None else self.agent,
            self.agent,
            status,
            fact,
            "user" if subject is not None else "agent",
            origin,
            subject,
        )
        return memory_id

    def status(self, memory_id: UUID) -> str | None:
        """Status des Eintrags oder `None`, wenn geloescht."""
        value: str | None = db_fetchval("SELECT status FROM agent_memory WHERE id = $1", memory_id)
        return value


@pytest.fixture
def env(make_auth_headers: AuthFactory) -> Iterator[Env]:
    with TestClient(app) as client:
        e = Env(client, make_auth_headers)
        try:
            yield e
        finally:
            cleanup_workspaces(e.users())


def _reason(res: Any, status: int) -> str:
    assert res.status_code == status, res.text
    reason: str = res.json()["reason"]
    return reason


def _results(res: Any) -> list[tuple[str, bool, str | None]]:
    assert res.status_code == 200, res.text
    return [(r["id"], r["ok"], r.get("reason")) for r in res.json()["results"]]


# ------------------------------------------------------------------- Stapel


def test_stapel_teilerfolg_mit_ergebnis_je_eintrag(env: Env) -> None:
    ok = env.memory("Agent: offener Fakt")
    held = env.memory("Aus einer Webseite", origin="external_content")
    active = env.memory("Schon aktiv", status="active")
    own = env.memory("Admin mag Kaffee", subject=env.owner)
    secret = "Viewer hat eine Nussallergie"
    foreign = env.memory(secret, subject=env.viewer)
    unknown = uuid4()
    ids = [ok, held, active, own, foreign, unknown]

    res = env.batch(
        env.admin_h, {"action": "approve", "ids": [str(i) for i in ids], "note": "Stapel"}
    )
    # Teilerfolg ist 200, ein Ergebnis je Eintrag in der Reihenfolge der Auswahl.
    assert _results(res) == [
        (str(ok), True, None),
        (str(held), False, "memory_held"),
        (str(active), False, "memory_not_pending"),
        (str(own), True, None),
        # Owner-Entscheidung 3a: auch admin bekommt memory_not_found.
        (str(foreign), False, "memory_not_found"),
        (str(unknown), False, "memory_not_found"),
    ]
    assert secret not in res.text
    # Geaendert ist genau, was ok meldet.
    assert env.status(ok) == "active"
    assert env.status(own) == "active"
    assert env.status(held) == "pending"
    assert env.status(foreign) == "pending"
    note = db_fetchval("SELECT triage_note FROM agent_memory WHERE id = $1", ok)
    assert note == "Stapel"

    # delete und confirm laufen ueber dieselbe Route.
    deleted = env.batch(env.editor_h, {"action": "delete", "ids": [str(held), str(foreign)]})
    assert _results(deleted) == [
        (str(held), True, None),
        (str(foreign), False, "memory_not_found"),
    ]
    assert env.status(held) is None
    assert env.status(foreign) == "pending"
    confirmed = env.batch(env.editor_h, {"action": "confirm", "ids": [str(active)]})
    assert _results(confirmed) == [(str(active), True, None)]
    assert db_fetchval("SELECT confirmed_at IS NOT NULL FROM agent_memory WHERE id = $1", active)


def test_stapel_filter_modus_und_grenzen(env: Env) -> None:
    a = env.memory("Agent: eins")
    b = env.memory("Agent: zwei")
    foreign = env.memory("Viewer mag Krimis", subject=env.viewer)
    queue = {"action": "reject", "filter": {"status": "pending"}}

    # Abweichende Zahl: 409 mit params.count, nichts geaendert.
    mismatch = env.batch(env.admin_h, {**queue, "expected_count": 3})
    assert _reason(mismatch, 409) == "memory_batch_count_mismatch"
    assert mismatch.json()["params"] == {"count": 2}
    assert env.status(a) == env.status(b) == "pending"

    res = env.batch(env.admin_h, {**queue, "expected_count": 2})
    assert {(i, ok) for i, ok, _ in _results(res)} == {(str(a), True), (str(b), True)}
    assert env.status(a) == env.status(b) == "rejected"
    assert env.status(foreign) == "pending"

    # Body-Grenzen als 422 der Anfrage.
    one = [str(a)]
    for body in (
        {"action": "approve"},
        {"action": "approve", "ids": one, "filter": {}, "expected_count": 1},
        {"action": "approve", "filter": {}},
        {"action": "approve", "ids": []},
        {"action": "approve", "ids": [str(uuid4()) for _ in range(101)]},
        {"action": "archive", "ids": one},
        {"action": "approve", "ids": one, "extra": 1},
    ):
        assert env.batch(env.editor_h, body).status_code == 422, body
    at_limit = env.batch(
        env.editor_h, {"action": "reject", "ids": [str(uuid4()) for _ in range(100)]}
    )
    assert len(_results(at_limit)) == 100


def test_eintrag_aus_fremdem_workspace_ist_nicht_gefunden(env: Env) -> None:
    """Weder Stapel noch Purge reichen ueber die Workspace-Grenze.

    Antwort wie fuer eine unbekannte ID (`memory_not_found` bzw. 0) — ein
    anderer `reason` waere ein Existenz-Orakel, das der Statuscode-Vergleich
    im Isolationslauf nicht sieht.
    """
    other_owner = fresh_user_id()
    other_ws = setup_workspace(other_owner)
    try:
        other_agent = db_fetchval(
            "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, 'Fremd') "
            "RETURNING id",
            other_ws,
            other_owner,
        )
        foreign = db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin) "
            "VALUES ($1, $2, $2, 'pending', 'Fremder Fakt', 'preference', 6, 'user_fact', "
            "        'agent', 'user_stated') RETURNING id",
            other_ws,
            other_agent,
        )
        db_execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'viewer')",
            other_ws,
            env.viewer,
        )
        elsewhere = db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, subject_user_id) "
            "VALUES ($1, NULL, $2, 'active', 'Viewer mag Oper', 'preference', 6, 'user_fact', "
            "        'user', 'user_stated', $3) RETURNING id",
            other_ws,
            other_agent,
            env.viewer,
        )
        for action in ("approve", "reject", "confirm", "delete"):
            res = env.batch(env.admin_h, {"action": action, "ids": [str(foreign)]})
            assert _results(res) == [(str(foreign), False, "memory_not_found")], action
        assert "Fremder Fakt" not in res.text
        assert db_fetchval("SELECT status FROM agent_memory WHERE id = $1", foreign) == "pending"

        # Purge im eigenen Workspace laesst das Gedaechtnis derselben Person
        # im anderen Workspace stehen.
        own = env.memory("Viewer mag Jazz", subject=env.viewer)
        assert env.purge(env.admin_h, env.viewer).json() == {"deleted": 1}
        assert env.status(own) is None
        assert db_fetchval("SELECT count(*) FROM agent_memory WHERE id = $1", elsewhere) == 1
    finally:
        cleanup_workspaces([other_owner])


def test_stapel_rechte(env: Env) -> None:
    agent_memory = env.memory("Agent: offener Fakt")
    own = env.memory("Viewer mag Hoerbuecher", subject=env.viewer)

    # viewer nennt Agentengedaechtnis: 403 auf den ganzen Aufruf.
    res = env.batch(env.viewer_h, {"action": "approve", "ids": [str(own), str(agent_memory)]})
    assert _reason(res, 403) == "insufficient_role"
    assert env.status(own) == env.status(agent_memory) == "pending"
    # Nur das eigene Nutzergedaechtnis: erlaubt.
    assert _results(env.batch(env.viewer_h, {"action": "approve", "ids": [str(own)]})) == [
        (str(own), True, None)
    ]
    # Agent-gebundener Token: 403, nichts geaendert.
    agent = env.batch(env.agent_h, {"action": "approve", "ids": [str(agent_memory)]})
    assert _reason(agent, 403) == "missing_capability"
    assert env.status(agent_memory) == "pending"


# -------------------------------------------------------------------- Purge


def test_purge_nur_admin_nur_anzahl(env: Env) -> None:
    secret = "Viewer hat eine Nussallergie"
    mine = [
        env.memory(secret, subject=env.viewer),
        env.memory("Viewer mag Jazz", subject=env.viewer, status="active"),
    ]
    editor_memory = env.memory("Editor mag Tabellen", subject=env.editor)
    agent_memory = env.memory("Agent: Fakt", status="active")

    assert _reason(env.purge(env.editor_h, env.viewer), 403) == "insufficient_role"
    assert _reason(env.purge(env.viewer_h, env.viewer), 403) == "insufficient_role"
    # Agent-gebundene Tokens sind auf editor gedeckelt (AGENT_BOUND_MAX_ROLE):
    # schon die Rolle reicht nicht; deny_agent_bound_workspace_admin bleibt
    # die zweite Wand wie an den Nachbarrouten.
    assert _reason(env.purge(env.agent_h, env.viewer), 403) == "insufficient_role"
    assert all(env.status(m) is not None for m in mine)

    res = env.purge(env.admin_h, env.viewer)
    assert res.status_code == 200, res.text
    # Nur die Anzahl, nie Inhalt oder IDs (Owner-Entscheidung 3a).
    assert res.json() == {"deleted": 2}
    assert secret not in res.text
    assert all(str(m) not in res.text for m in mine)
    assert all(env.status(m) is None for m in mine)
    assert env.status(editor_memory) is not None
    assert env.status(agent_memory) is not None
    detail = db_fetchval(
        "SELECT detail::text FROM audit_log WHERE workspace_id = $1 "
        "AND action = 'memory.user_purged' AND target = $2",
        env.ws,
        str(env.viewer),
    )
    assert detail is not None and secret not in detail

    # Unbekannte Person (oder ehemaliges Mitglied ohne Eintraege): 0, kein 404.
    assert env.purge(env.admin_h, uuid4()).json() == {"deleted": 0}
    assert env.purge(env.admin_h, env.owner).status_code == 200
    assert (
        env.client.delete(
            f"{env.prefix}/members/kein-uuid/memories", headers=env.admin_h
        ).status_code
        == 422
    )
