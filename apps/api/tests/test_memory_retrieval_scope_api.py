"""Gedaechtnis-Abruf mit Nutzergedaechtnis und Push nur bestaetigt (ADR-0053 C4a).

Router-Tests gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`) ueber den Weg, den
der MCP-Server nimmt: `GET /agent-memories/search`, `GET /agent-memories` und
`GET /personas/{id}/rendered` mit einem agent-gebundenen Token. Kritische
Zusicherungen, je mit Rot-Probe belegt (Rot-Probe = genannte Zeile in
`memory_repository.py` bzw. `persona_service.py` geaendert, Test wird rot):

- Der Abruf liefert Agentengedaechtnis UND Nutzergedaechtnis des
  Token-Besitzers — und nie das Nutzergedaechtnis eines anderen Menschen.
  (Rot-Probe: `subject_user_id = $n` in `_retrieval_scope` entfernt.)
- `lesson` erscheint nie im Abruf, auch wenn der DB-CHECK fehlte.
  (Rot-Probe: `kind <> 'lesson'` in `_retrieval_scope` entfernt.)
- Jeder Treffer traegt `kind`, `scope` und `confirmed`.
  (Rot-Probe: `confirmed_at IS NOT NULL AS confirmed` invertiert.)
- Abrufe zaehlen auch Nutzereintraege ins Nutzungs-Log.
  (Rot-Probe: `_bump_retrieval` wieder nur auf `agent_id`.)
- Der Laufzeit-Push in `get_persona` zeigt nur bestaetigte Eintraege (M7 = a).
  (Rot-Probe: `confirmed_only=True` in `persona_service.py` entfernt.)
"""

from collections.abc import Callable, Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("patched_jwt_secret", "migrated_db"),
]

_LESSON_CHECK = "agent_memory_lesson_status_check"
_LESSON_CHECK_SQL = "CHECK (kind <> 'lesson' OR status IN ('pending', 'rejected', 'converted'))"


class Env:
    def __init__(self, client: TestClient, make_auth: AuthFactory) -> None:
        self.client = client
        self.owner, self.other = fresh_user_id(), fresh_user_id()
        self.ws = setup_workspace(self.owner)
        db_execute(
            "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'editor')",
            self.ws,
            self.other,
        )
        self.prefix = f"/v1/workspaces/{self.ws}"
        self.admin_h = make_auth(self.owner)
        agent, self.agent_h = agent_token(
            client, self.prefix, "C4a-Agent", {"memory_mode": "read_only"}, self.admin_h
        )
        other_agent, _ = agent_token(
            client, self.prefix, "C4a-Fremd", {"memory_mode": "read_only"}, self.admin_h
        )
        self.agent, self.other_agent = UUID(agent), UUID(other_agent)

    def memory(
        self,
        fact: str,
        *,
        kind: str = "user_fact",
        agent: UUID | None = None,
        subject: UUID | None = None,
        status: str = "active",
        confirmed: bool = True,
        importance: int = 6,
    ) -> UUID:
        """Legt einen Eintrag direkt an (Fixture, an der Service-Logik vorbei)."""
        scope = "user" if subject is not None else "agent"
        agent_id = None if subject is not None else (agent or self.agent)
        memory_id: UUID = db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, source, subject_user_id, "
            " confirmed_at, confirmed_by, expires_at) "
            "VALUES ($1, $2, $3, $4, $5, 'preference', $6, $7, $8, 'user_stated', 'agent', "
            "        $9, CASE WHEN $10 THEN now() END, CASE WHEN $10 THEN $11::uuid END, "
            "        CASE WHEN NOT $10 AND $4 = 'active' THEN now() + interval '30 days' END) "
            "RETURNING id",
            self.ws,
            agent_id,
            self.agent,
            status,
            fact,
            importance,
            kind,
            scope,
            subject,
            confirmed,
            self.owner,
        )
        return memory_id

    def search(self, query: str) -> list[dict[str, Any]]:
        res = self.client.get(
            f"{self.prefix}/agent-memories/search",
            params={"query": query, "k": 20},
            headers=self.agent_h,
        )
        assert res.status_code == 200, res.text
        hits: list[dict[str, Any]] = res.json()
        return hits

    def listed(self) -> list[dict[str, Any]]:
        res = self.client.get(
            f"{self.prefix}/agent-memories", params={"limit": 50}, headers=self.agent_h
        )
        assert res.status_code == 200, res.text
        hits: list[dict[str, Any]] = res.json()
        return hits


@pytest.fixture
def env(make_auth_headers: AuthFactory) -> Iterator[Env]:
    with TestClient(app) as client:
        e = Env(client, make_auth_headers)
        try:
            yield e
        finally:
            cleanup_workspaces([e.owner, e.other])


def _ids(hits: list[dict[str, Any]]) -> set[str]:
    return {hit["id"] for hit in hits}


def test_abruf_liefert_agenten_und_eigenes_nutzergedaechtnis_nie_fremdes(env: Env) -> None:
    own_agent = env.memory("Kaffeesorte Agent: Espresso")
    own_user = env.memory("Kaffeesorte Nutzer: Filterkaffee", subject=env.owner)
    foreign_user = env.memory("Kaffeesorte Kollege: Cappuccino", subject=env.other)
    foreign_agent = env.memory("Kaffeesorte Fremdagent: Mokka", agent=env.other_agent)

    for hits in (env.search("Kaffeesorte"), env.listed()):
        ids = _ids(hits)
        assert {str(own_agent), str(own_user)} <= ids
        assert str(foreign_user) not in ids
        assert str(foreign_agent) not in ids


def test_treffer_tragen_kind_scope_confirmed(env: Env) -> None:
    note = env.memory("Werkzeug Ripgrep ist installiert", kind="agent_note", confirmed=False)
    fact = env.memory("Werkzeug der Wahl ist Neovim", subject=env.owner)

    expected = {
        str(note): {"kind": "agent_note", "scope": "agent", "confirmed": False},
        str(fact): {"kind": "user_fact", "scope": "user", "confirmed": True},
    }
    for hits in (env.search("Werkzeug"), env.listed()):
        by_id = {hit["id"]: hit for hit in hits}
        assert set(by_id) == set(expected)
        for memory_id, fields in expected.items():
            hit = by_id[memory_id]
            assert {key: hit[key] for key in fields} == fields
            # Bewusst schmal: kein context, kein Personenbezug, keine Triage-Daten.
            assert set(hit) == {"id", "fact", "category", "kind", "scope", "confirmed"}


def test_lesson_nie_im_abruf(env: Env) -> None:
    visible = env.memory("Rechnungslauf immer freitags")
    pending_lesson = env.memory(
        "Rechnungslauf vorher pruefen", kind="lesson", status="pending", confirmed=False
    )
    assert _ids(env.search("Rechnungslauf")) == {str(visible)}
    assert _ids(env.listed()) == {str(visible)}

    # Zweite Linie: auch ein aktiver Lernvorschlag (heute vom DB-CHECK
    # verhindert) fliesst nie in den Abruf. Der CHECK wird dafuer kurz
    # entfernt und in jedem Fall wiederhergestellt.
    db_execute(f"ALTER TABLE agent_memory DROP CONSTRAINT {_LESSON_CHECK}")
    try:
        db_execute("UPDATE agent_memory SET status = 'active' WHERE id = $1", pending_lesson)
        assert _ids(env.search("Rechnungslauf")) == {str(visible)}
        assert _ids(env.listed()) == {str(visible)}
    finally:
        db_execute("DELETE FROM agent_memory WHERE id = $1", pending_lesson)
        db_execute(f"ALTER TABLE agent_memory ADD CONSTRAINT {_LESSON_CHECK} {_LESSON_CHECK_SQL}")


def test_abruf_zaehlt_nutzereintraege_ins_nutzungs_log(env: Env) -> None:
    own_user = env.memory("Lieblingsfarbe ist Petrol", subject=env.owner)
    foreign_user = env.memory("Lieblingsfarbe ist Ocker", subject=env.other)

    assert _ids(env.search("Lieblingsfarbe")) == {str(own_user)}
    count = "SELECT retrieval_count FROM agent_memory WHERE id = $1"
    assert db_fetchval(count, own_user) == 1
    assert db_fetchval(count, foreign_user) == 0


def _active_persona(env: Env) -> str:
    persona = env.client.post(
        f"{env.prefix}/personas",
        json={
            "name": "C4a-Persona",
            "content": {
                "description": "hilfsbereit",
                "system_prompt": "Sei praezise.",
                "traits": [],
                "content": {
                    "description": "hilfsbereit",
                    "blocks": [
                        {
                            "id": "b1",
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "Profil.", "styles": {}}],
                        }
                    ],
                },
            },
        },
        headers=env.admin_h,
    )
    assert persona.status_code == 201, persona.text
    pid: str = persona.json()["id"]
    for to in ("review", "active"):
        res = env.client.post(
            f"{env.prefix}/personas/{pid}/versions/1/transition",
            json={"to": to},
            headers=env.admin_h,
        )
        assert res.status_code == 200, res.text
    return pid


def test_get_persona_push_zeigt_nur_bestaetigte(env: Env) -> None:
    # Regelfall-Fixture: bestaetigte UND unbestaetigte aktive Eintraege in
    # beiden Geltungsbereichen, das Unbestaetigte mit hoeherer Wichtigkeit
    # (es wuerde ohne Filter zuerst gezeigt).
    env.memory("Bestaetigter Agentenfakt: Deploy auf Hetzner")
    env.memory("Bestaetigter Nutzerfakt: antwortet auf Deutsch", subject=env.owner)
    env.memory("Unbestaetigter Agentenfakt: mag Tabellen", confirmed=False, importance=9)
    env.memory("Unbestaetigter Nutzerfakt: trinkt Tee", subject=env.owner, confirmed=False)
    env.memory("Fremder Nutzerfakt: faehrt Rad", subject=env.other)

    body = env.client.get(
        f"{env.prefix}/personas/{_active_persona(env)}/rendered", headers=env.agent_h
    ).json()["body_rendered"]

    assert "## Gedaechtnis" in body
    assert "Bestaetigter Agentenfakt: Deploy auf Hetzner" in body
    assert "Bestaetigter Nutzerfakt: antwortet auf Deutsch" in body
    assert "Unbestaetigter Agentenfakt" not in body
    assert "Unbestaetigter Nutzerfakt" not in body
    assert "Fremder Nutzerfakt" not in body
    # Der Abruf auf Anfrage liefert das Unbestaetigte dagegen (M7 = a).
    assert any(hit["fact"].startswith("Unbestaetigter Agentenfakt") for hit in env.listed())
