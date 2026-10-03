"""REST fuer `GET /memories` und `GET /memories/counts` (ADR-0053 6.4.1, C3c-1b).

Router-Tests gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`). Die Fachlogik
(Sichtbarkeit, Facetten, Keyset, held/health) belegen die Service-Tests aus
C3c-1a (`test_memory_list_counts.py`); hier geht es um den Weg ueber HTTP:
Query-Parameter kommen beim Service an, Grenzen greifen als 422, Fehler
kommen mit `reason` zurueck. Kritische Zusicherungen, je mit Rot-Probe belegt:

- Filter, `sort`, Cursor und `limit` (hoechstens 50) wirken ueber HTTP; der
  Cursor fuehrt ohne Luecke und ohne Dublette durch die Liste. Jeder Filter
  (auch origin, source, health, held, created_after) liefert ein anderes
  Ergebnis als ohne ihn, in Liste und Zaehlern.
- `group_by` ist wiederholbar; `group_by=subject_user_id` nur `admin`
  (403 `insufficient_role`) und nur als Zahl je Person.
- Fremdes Nutzergedaechtnis (Owner-Entscheidung 3a): `admin` sieht es in der
  Liste weder mit Inhalt noch mit ID, auch nicht ueber `q` oder `scope=user`.
- `viewer` sieht nur das eigene Nutzergedaechtnis, ein agent-gebundener Token
  bekommt 403 `missing_capability`.
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

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
            client, self.prefix, "C3c1b-Agent", {"memory_mode": "auto"}, self.admin_h
        )
        self.agent = UUID(agent)
        other, _ = agent_token(
            client, self.prefix, "C3c1b-Zweit", {"memory_mode": "auto"}, self.admin_h
        )
        self.other_agent = UUID(other)
        self._clock = datetime.now(UTC) - timedelta(hours=1)

    def users(self) -> list[UUID]:
        return [self.owner, self.editor, self.viewer]

    def get(self, path: str, headers: dict[str, str], **params: Any) -> Any:
        return self.client.get(f"{self.prefix}{path}", params=params, headers=headers)

    def memory(
        self,
        fact: str,
        *,
        agent: UUID | None = None,
        subject: UUID | None = None,
        status: str = "active",
        kind: str = "user_fact",
        origin: str = "user_stated",
        source: str = "agent",
        confirmed: bool = True,
    ) -> UUID:
        """Legt einen Eintrag direkt an (an der Logik vorbei), je Aufruf eine Sekunde spaeter.

        `confirmed=False` laesst `confirmed_at` auch bei `active` leer
        (Zustand `unconfirmed`).
        """
        self._clock += timedelta(seconds=1)
        submitter = agent or self.agent
        scope = "user" if subject is not None else "agent"
        memory_id: UUID = db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, source, subject_user_id, "
            " confirmed_at, expires_at, created_at) "
            "VALUES ($1, $2, $3, $4, $5, 'preference', 6, $6, $7, $10, $11, "
            "        $8, CASE WHEN $4 = 'active' AND $12 THEN now() END, "
            "        now() + interval '30 days', $9) "
            "RETURNING id",
            self.ws,
            None if subject is not None else submitter,
            submitter,
            status,
            fact,
            kind,
            scope,
            subject,
            self._clock,
            origin,
            source,
            confirmed,
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


def _ids(res: Any) -> list[str]:
    assert res.status_code == 200, res.text
    return [item["id"] for item in res.json()["items"]]


def test_filter_sort_cursor_und_limit(env: Env) -> None:
    first = env.memory("Nutzer mag Tee", status="pending")
    second = env.memory("Nutzer mag Jazz", status="pending", agent=env.other_agent)
    note = env.memory("Notiz zu Kiel", status="pending", kind="agent_note")
    lesson = env.memory("Lernvorschlag", status="pending", kind="lesson")
    active = env.memory("Nutzer mag Ocker")

    # Ohne Filter: alles Sichtbare, neueste zuerst.
    assert _ids(env.get("/memories", env.editor_h)) == [
        str(m) for m in (active, lesson, note, second, first)
    ]
    # Warteschlange: status=pending ohne Lernvorschlaege.
    queue = env.get("/memories", env.editor_h, status="pending", sort="oldest")
    assert _ids(queue) == [str(first), str(second), str(note)]
    assert queue.json()["next_cursor"] is None
    # Einzelne Filter kommen beim Service an.
    assert _ids(env.get("/memories", env.editor_h, kind="lesson", status="pending")) == [
        str(lesson)
    ]
    assert _ids(env.get("/memories", env.editor_h, agent_id=str(env.other_agent))) == [str(second)]
    assert _ids(env.get("/memories", env.editor_h, q="jazz")) == [str(second)]
    assert _ids(env.get("/memories", env.editor_h, status="active")) == [str(active)]

    # Cursor: Seiten zu zwei, ohne Luecke und ohne Dublette.
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(5):
        params: dict[str, Any] = {"limit": 2, "sort": "oldest"}
        if cursor is not None:
            params["cursor"] = cursor
        page = env.get("/memories", env.editor_h, **params)
        assert len(_ids(page)) <= 2
        seen += _ids(page)
        cursor = page.json()["next_cursor"]
        if cursor is None:
            break
    assert seen == [str(m) for m in (first, second, note, lesson, active)]

    # Grenzen als 422 der Anfrage.
    assert env.get("/memories", env.editor_h, limit=50).status_code == 200
    assert env.get("/memories", env.editor_h, limit=51).status_code == 422
    assert env.get("/memories", env.editor_h, limit=0).status_code == 422
    assert _reason(env.get("/memories", env.editor_h, cursor="kaputt"), 422) == "invalid_cursor"
    assert env.get("/memories", env.editor_h, sort="random").status_code == 422
    assert env.get("/memories", env.editor_h, q="").status_code == 422
    # created_after braucht eine Zeitzone (wie MemoryFilter).
    naive = env.get("/memories", env.editor_h, created_after="2020-01-01T00:00:00")
    assert naive.status_code == 422
    aware = env.get("/memories", env.editor_h, created_after="2020-01-01T00:00:00Z")
    assert len(_ids(aware)) == 5


def test_filter_origin_source_health_held_created_after(env: Env) -> None:
    """Jeder dieser Filter liefert ueber HTTP etwas anderes als ohne Filter."""
    plain = env.memory("Nutzer mag Tee", status="pending")
    inferred = env.memory(
        "Nutzer mag wohl Jazz", status="pending", origin="inferred", source="human"
    )
    imported = env.memory("Nutzer mag Ocker", source="import", confirmed=False)
    confirmed = env.memory("Nutzer mag Kiel")
    everything = {str(m) for m in (plain, inferred, imported, confirmed)}
    assert set(_ids(env.get("/memories", env.editor_h))) == everything

    def only(**params: Any) -> set[str]:
        return set(_ids(env.get("/memories", env.editor_h, **params)))

    assert only(origin="inferred") == {str(inferred)}
    assert only(origin="user_stated") == {str(plain), str(imported), str(confirmed)}
    assert only(source="human") == {str(inferred)}
    assert only(source="import") == {str(imported)}
    # unconfirmed: active ohne confirmed_at; external_or_inferred: Herkunft.
    assert only(health="unconfirmed") == {str(imported)}
    assert only(health="external_or_inferred") == {str(inferred)}
    # held: pending und Herkunft inferred/external_content (abgeleitet).
    assert only(held="true") == {str(inferred)}
    assert only(held="false") == {str(plain), str(imported), str(confirmed)}
    # created_after zwischen dem ersten und dem zweiten Eintrag.
    created = db_fetchval("SELECT created_at FROM agent_memory WHERE id = $1", plain)
    between = (created + timedelta(milliseconds=500)).isoformat()
    assert only(created_after=between) == {str(inferred), str(imported), str(confirmed)}

    # Dieselben Filter wirken auch auf die Zaehler.
    def total(**params: Any) -> int:
        res = env.get("/memories/counts", env.editor_h, **params)
        assert res.status_code == 200, res.text
        count: int = res.json()["total"]
        return count

    assert total() == 4
    assert total(origin="inferred") == 1
    assert total(source="import") == 1
    assert total(health="unconfirmed") == 1
    assert total(held="true") == 1
    assert total(created_after=between) == 3


def test_counts_facetten_und_group_by(env: Env) -> None:
    env.memory("Offen A", status="pending")
    env.memory("Offen B", status="pending", agent=env.other_agent)
    env.memory("Lernvorschlag", status="pending", kind="lesson")
    env.memory("Aktiv", agent=env.other_agent)

    res = env.get(
        "/memories/counts", env.editor_h, status="pending", group_by=["agent", "status", "kind"]
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # total = Laenge der Warteschlange (ohne lesson).
    assert body["total"] == 2
    assert body["total"] == len(_ids(env.get("/memories", env.editor_h, status="pending")))
    assert body["groups"]["agent"] == {str(env.agent): 1, str(env.other_agent): 1}
    # Facette status ohne den eigenen Filter.
    assert body["groups"]["status"] == {"pending": 2, "active": 1}
    assert body["groups"]["kind"] == {"user_fact": 2, "lesson": 1}

    # Ohne group_by nur total.
    plain = env.get("/memories/counts", env.editor_h, agent_id=str(env.other_agent))
    assert plain.json() == {"total": 2, "groups": {}}
    # Unbekannte Gruppe: 422.
    assert env.get("/memories/counts", env.editor_h, group_by="fact").status_code == 422


def test_admin_sieht_fremdes_nutzergedaechtnis_nur_als_zahl(env: Env) -> None:
    """Owner-Entscheidung 3a: fremdes Nutzergedaechtnis nur als Zahl je Person."""
    secret = "Editor hat eine Nussallergie"
    foreign = env.memory(secret, subject=env.editor, status="pending")
    own = env.memory("Admin mag Tee", subject=env.owner)
    agent_mem = env.memory("Agentenfakt")

    for params in ({}, {"scope": "user"}, {"q": "Nussallergie"}, {"status": "pending"}):
        res = env.get("/memories", env.admin_h, **params)
        assert res.status_code == 200, res.text
        assert secret not in res.text, params
        assert str(foreign) not in res.text, params
    assert _ids(env.get("/memories", env.admin_h, scope="user")) == [str(own)]
    assert set(_ids(env.get("/memories", env.admin_h))) == {str(own), str(agent_mem)}

    counts = env.get("/memories/counts", env.admin_h, group_by="subject_user_id")
    assert counts.status_code == 200, counts.text
    assert counts.json()["groups"]["subject_user_id"] == {str(env.editor): 1, str(env.owner): 1}
    assert secret not in counts.text
    assert str(foreign) not in counts.text
    # Die Person selbst sieht ihren Eintrag.
    assert _ids(env.get("/memories", env.editor_h, scope="user")) == [str(foreign)]


def test_rechte(env: Env) -> None:
    env.memory("Agentenfakt")
    own = env.memory("Viewer mag Hoerspiele", subject=env.viewer)

    # viewer: nur das eigene Nutzergedaechtnis, kein Agentengedaechtnis.
    assert _ids(env.get("/memories", env.viewer_h)) == [str(own)]
    assert env.get("/memories/counts", env.viewer_h).json()["total"] == 1
    # group_by=subject_user_id nur admin.
    for headers in (env.editor_h, env.viewer_h):
        res = env.get("/memories/counts", headers, group_by="subject_user_id")
        assert _reason(res, 403) == "insufficient_role"
    # Agent-gebundener Token: 403 auf beiden Routen.
    assert _reason(env.get("/memories", env.agent_h), 403) == "missing_capability"
    assert _reason(env.get("/memories/counts", env.agent_h), 403) == "missing_capability"
    # Unbekannter Agent im Filter.
    unknown = "00000000-0000-0000-0000-000000000000"
    assert _reason(env.get("/memories", env.editor_h, agent_id=unknown), 404) == "agent_not_found"
    assert (
        _reason(env.get("/memories/counts", env.editor_h, agent_id=unknown), 404)
        == "agent_not_found"
    )
