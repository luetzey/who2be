"""REST fuer den Not-Aus `POST /memories/revoke-auto` (ADR-0053 6.4.1, C3b-2b).

Router-Tests gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`). Die Fachlogik
(Auswahl, Atomaritaet, Zeitraum) belegen die Service-Tests aus C3b-2a
(`test_memory_revoke_auto.py`); hier geht es um den Weg ueber HTTP.
Kritische Zusicherungen, je mit Rot-Probe belegt:

- `dry_run` aendert nichts; ohne `dry_run` und mit abweichendem
  `expected_count` kommt 409 `memory_batch_count_mismatch` mit
  `params={count}`, und nichts ist geaendert.
- Die Ruecknahme setzt `pending` und schreibt je Eintrag `auto_revoked`.
- `viewer` bekommt 403 `insufficient_role`, ein agent-gebundener Token 403
  `missing_capability`, `include_other_users` ohne `admin` 403.
- Fremdes Nutzergedaechtnis (Owner-Entscheidung 3a): auch `admin` bekommt mit
  `include_other_users` nur `hidden_count` — weder Inhalt noch ID, weder in
  der Vorschau noch im Ergebnis.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.core import rate_limit
from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")

_PATH = "/memories/revoke-auto"


@pytest.fixture(autouse=True)
def _no_global_write_limit() -> Iterator[None]:
    # Das slowapi-Schreiblimit ist hier nicht Gegenstand.
    enabled = rate_limit.limiter.enabled
    rate_limit.limiter.enabled = False
    try:
        yield
    finally:
        rate_limit.limiter.enabled = enabled


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
            client, self.prefix, "C3b2b-Agent", {"memory_mode": "auto"}, self.admin_h
        )
        self.agent = UUID(agent)
        self.since = (datetime.now(UTC) - timedelta(hours=2)).isoformat()

    def users(self) -> list[UUID]:
        return [self.owner, self.editor, self.viewer]

    def post(self, body: dict[str, Any], headers: dict[str, str]) -> Any:
        return self.client.post(f"{self.prefix}{_PATH}", json=body, headers=headers)

    def memory(self, fact: str, *, subject: UUID | None = None, auto: bool = True) -> UUID:
        """Aktiv, unbestaetigt; mit `auto_activated` vor einer Stunde (an der Logik vorbei)."""
        scope = "user" if subject is not None else "agent"
        memory_id: UUID = db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, source, subject_user_id, "
            " expires_at) "
            "VALUES ($1, $2, $3, 'active', $4, 'preference', 6, 'user_fact', $5, "
            "        'user_stated', 'agent', $6, now() + interval '30 days') RETURNING id",
            self.ws,
            None if subject is not None else self.agent,
            self.agent,
            fact,
            scope,
            subject,
        )
        if auto:
            db_execute(
                "INSERT INTO agent_memory_event (workspace_id, memory_id, event, actor_kind, "
                " agent_id, after, created_at) VALUES ($1, $2, 'auto_activated', 'system', "
                " $3, '{}'::jsonb, now() - interval '1 hour')",
                self.ws,
                memory_id,
                self.agent,
            )
        return memory_id


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


def _status(memory_id: UUID) -> str:
    status: str = db_fetchval("SELECT status FROM agent_memory WHERE id = $1", memory_id)
    return status


def _events(memory_id: UUID, event: str) -> int:
    count: int = db_fetchval(
        "SELECT count(*) FROM agent_memory_event WHERE memory_id = $1 AND event = $2",
        memory_id,
        event,
    )
    return count


def test_vorschau_zahlabgleich_und_ruecknahme(env: Env) -> None:
    first = env.memory("Nutzer mag Tee")
    second = env.memory("Nutzer mag Jazz")
    manual = env.memory("Von Hand freigegeben", auto=False)

    preview = env.post({"since": env.since, "dry_run": True}, env.editor_h)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["count"] == 2
    assert body["hidden_count"] == 0
    assert {m["id"] for m in body["sample"]} == {str(first), str(second)}
    assert "results" not in body
    # Die Vorschau aendert nichts.
    assert {_status(first), _status(second)} == {"active"}

    # Ohne dry_run ist expected_count Pflicht (Modell-Validierung).
    assert env.post({"since": env.since}, env.editor_h).status_code == 422

    # Abweichende Zahl: 409 mit der Serverzahl, nichts geaendert.
    mismatch = env.post({"since": env.since, "expected_count": 1}, env.editor_h)
    assert _reason(mismatch, 409) == "memory_batch_count_mismatch"
    assert mismatch.json()["params"] == {"count": 2}
    assert {_status(first), _status(second)} == {"active"}
    assert _events(first, "auto_revoked") == 0

    done = env.post({"since": env.since, "expected_count": 2}, env.editor_h)
    assert done.status_code == 200, done.text
    result = done.json()
    assert result["count"] == 2
    assert result["hidden_count"] == 0
    assert sorted(r["id"] for r in result["results"]) == sorted([str(first), str(second)])
    assert all(r["ok"] for r in result["results"])
    assert "sample" not in result
    for memory_id in (first, second):
        assert _status(memory_id) == "pending"
        assert _events(memory_id, "auto_revoked") == 1
    # Ohne auto_activated: unberuehrt.
    assert _status(manual) == "active"

    # Ein zweiter Lauf findet nichts mehr.
    again = env.post({"since": env.since, "dry_run": True}, env.editor_h)
    assert again.json()["count"] == 0


def test_rechte(env: Env) -> None:
    mem = env.memory("Nutzer mag Kiel")
    body = {"since": env.since, "dry_run": True}

    assert _reason(env.post(body, env.viewer_h), 403) == "insufficient_role"
    assert _reason(env.post(body, env.agent_h), 403) == "missing_capability"
    assert (
        _reason(env.post({**body, "include_other_users": True}, env.editor_h), 403)
        == "insufficient_role"
    )
    unknown = env.post({**body, "agent_id": "00000000-0000-0000-0000-000000000000"}, env.editor_h)
    assert _reason(unknown, 404) == "agent_not_found"
    # Auch ohne dry_run greift die Rolle vor jeder Aenderung.
    real = {"since": env.since, "expected_count": 1}
    assert _reason(env.post(real, env.viewer_h), 403) == "insufficient_role"
    assert _status(mem) == "active"
    assert _events(mem, "auto_revoked") == 0


def test_admin_sieht_fremdes_nutzergedaechtnis_nur_als_zahl(env: Env) -> None:
    """Owner-Entscheidung 3a: fremdes Nutzergedaechtnis nur als `hidden_count`."""
    secret = "Editor hat eine Nussallergie"
    foreign = env.memory(secret, subject=env.editor)
    agent_mem = env.memory("Nutzer mag Ocker")

    # Ohne Schalter bleibt das fremde Nutzergedaechtnis aussen vor.
    plain = env.post({"since": env.since, "dry_run": True}, env.admin_h)
    assert plain.status_code == 200, plain.text
    assert plain.json()["count"] == 1
    assert plain.json()["hidden_count"] == 0

    preview = env.post(
        {"since": env.since, "dry_run": True, "include_other_users": True}, env.admin_h
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["count"] == 2
    assert preview.json()["hidden_count"] == 1
    assert [m["id"] for m in preview.json()["sample"]] == [str(agent_mem)]
    assert secret not in preview.text
    assert str(foreign) not in preview.text

    done = env.post(
        {"since": env.since, "include_other_users": True, "expected_count": 2}, env.admin_h
    )
    assert done.status_code == 200, done.text
    assert done.json()["hidden_count"] == 1
    assert [r["id"] for r in done.json()["results"]] == [str(agent_mem)]
    assert secret not in done.text
    assert str(foreign) not in done.text
    # Zurueckgenommen ist der fremde Eintrag trotzdem.
    assert _status(foreign) == "pending"
    assert _events(foreign, "auto_revoked") == 1

    # Die Person selbst sieht ihren Eintrag wieder in der eigenen Warteschlange.
    own = env.client.get(
        f"{env.prefix}/me/memories", params={"status": "pending"}, headers=env.editor_h
    )
    assert [m["id"] for m in own.json()] == [str(foreign)]
