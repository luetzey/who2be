"""REST fuer Vorschlaege, Historie, Rollback und `/me/memories` (ADR-0053 6.4/6.4.1, C3b).

Router-Tests gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`). Die Fachlogik
belegen die Service-Tests aus C3a (`test_memory_proposals.py`); hier geht es
um den Weg ueber HTTP: jeder Endpunkt mit Erfolg, Rechten und Fehlergrund.
Kritische Zusicherungen, je mit Rot-Probe belegt:

- Kein Endpunkt zeigt einem anderen Menschen den Inhalt eines fremden
  Nutzergedaechtnisses — auch `admin` nicht (3.1.1, Owner-Entscheidung
  2026-10-01 3a). Fremd heisst fuer ihn `memory_not_found`.
- `POST /agent-memory-proposals` legt nur einen Vorschlag an (`pending`) und
  aendert den Eintrag nicht; fremde Eintraege sind `memory_not_found`.
- Alle Verwaltungs-Endpunkte sind human-only: ein agent-gebundener Token
  bekommt `missing_capability`.
- `viewer` verwaltet kein Agentengedaechtnis (`insufficient_role`), sehr wohl
  aber sein eigenes Nutzergedaechtnis.
"""

from collections.abc import Callable, Iterator
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


@pytest.fixture(autouse=True)
def _no_global_write_limit() -> Iterator[None]:
    # Das slowapi-Schreiblimit (30/min je Token) ist hier nicht Gegenstand;
    # ein Lauf macht mit demselben Admin-Token deutlich mehr Schreibaufrufe.
    enabled = rate_limit.limiter.enabled
    rate_limit.limiter.enabled = False
    try:
        yield
    finally:
        rate_limit.limiter.enabled = enabled


# ------------------------------------------------------------------ Umgebung


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
            client, self.prefix, "C3b-Agent", {"memory_mode": "suggest"}, self.admin_h
        )
        other, self.other_h = agent_token(
            client, self.prefix, "C3b-Fremd", {"memory_mode": "suggest"}, self.admin_h
        )
        self.agent, self.other_agent = UUID(agent), UUID(other)

    def users(self) -> list[UUID]:
        return [self.owner, self.editor, self.viewer]

    def url(self, path: str) -> str:
        return f"{self.prefix}{path}"

    def memory(
        self,
        fact: str,
        *,
        agent: UUID | None = None,
        subject: UUID | None = None,
        status: str = "active",
        confirmed: bool = False,
        expires: bool = False,
    ) -> UUID:
        """Legt einen Eintrag direkt an (Fixture, an der Service-Logik vorbei)."""
        scope = "user" if subject is not None else "agent"
        agent_id = None if subject is not None else (agent or self.agent)
        memory_id: UUID = db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, source, subject_user_id, "
            " confirmed_at, confirmed_by, expires_at) "
            "VALUES ($1, $2, $3, $4, $5, 'preference', 6, 'user_fact', $6, 'user_stated', "
            "        'agent', $7, CASE WHEN $8 THEN now() END, CASE WHEN $8 THEN $9::uuid END, "
            "        CASE WHEN $10 THEN now() + interval '30 days' END) "
            "RETURNING id",
            self.ws,
            agent_id,
            self.agent,
            status,
            fact,
            scope,
            subject,
            confirmed,
            self.owner,
            expires,
        )
        return memory_id

    def proposal(self, memory_id: UUID, new_fact: str, *, agent: UUID | None = None) -> UUID:
        """Vorschlag direkt anlegen — fuer Eintraege, die der Agent-Token nicht erreicht."""
        proposal_id: UUID = db_fetchval(
            "INSERT INTO agent_memory_proposal (workspace_id, memory_id, agent_id, action, "
            " new_fact, reason) VALUES ($1, $2, $3, 'change', $4, 'Test') RETURNING id",
            self.ws,
            memory_id,
            agent or self.agent,
            new_fact,
        )
        return proposal_id


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


def _fact(memory_id: UUID) -> str:
    fact: str = db_fetchval("SELECT fact FROM agent_memory WHERE id = $1", memory_id)
    return fact


# ------------------------------------------------------- Vorschlag (Agent-Pfad)


def test_propose_legt_nur_pending_vorschlag_an(env: Env) -> None:
    c = env.client
    own = env.memory("Nutzer trinkt Tee")
    body = {
        "memory_id": str(own),
        "action": "change",
        "new_fact": "Nutzer trinkt Kaffee",
        "reason": "Hat es so gesagt",
    }
    res = c.post(env.url("/agent-memory-proposals"), json=body, headers=env.agent_h)
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "pending"
    assert res.json()["agent_id"] == str(env.agent)
    # Der Eintrag selbst bleibt unveraendert, bis ein Mensch entscheidet.
    assert _fact(own) == "Nutzer trinkt Tee"

    # Eintrag eines fremden Agenten: fuer diesen Agenten nicht vorhanden.
    foreign = env.memory("Fremder Fakt", agent=env.other_agent)
    res = c.post(
        env.url("/agent-memory-proposals"),
        json={**body, "memory_id": str(foreign)},
        headers=env.agent_h,
    )
    assert _reason(res, 404) == "memory_not_found"

    # Nutzergedaechtnis einer anderen Person als dem Token-Besitzer: ebenso.
    other_user = env.memory("Editor mag Jazz", subject=env.editor)
    res = c.post(
        env.url("/agent-memory-proposals"),
        json={**body, "memory_id": str(other_user)},
        headers=env.agent_h,
    )
    assert _reason(res, 404) == "memory_not_found"

    # Kein agent-gebundener Token: kein Vorschlagspfad.
    res = c.post(env.url("/agent-memory-proposals"), json=body, headers=env.admin_h)
    assert _reason(res, 403) == "missing_capability"

    # `new_fact` nur bei change (Modell-Validierung).
    res = c.post(
        env.url("/agent-memory-proposals"),
        json={"memory_id": str(own), "action": "delete", "new_fact": "x", "reason": "r"},
        headers=env.agent_h,
    )
    assert res.status_code == 422, res.text


# ----------------------------------------------- Vorschlaege listen, entscheiden


def test_vorschlaege_listen_und_entscheiden(env: Env) -> None:
    c = env.client
    mem = env.memory("Nutzer wohnt in Kiel")
    created = c.post(
        env.url("/agent-memory-proposals"),
        json={
            "memory_id": str(mem),
            "action": "change",
            "new_fact": "Nutzer wohnt in Luebeck",
            "reason": "Umzug erwaehnt",
        },
        headers=env.agent_h,
    )
    assert created.status_code == 201, created.text
    proposal_id = created.json()["id"]

    per_agent = c.get(
        env.url(f"/agents/{env.agent}/memory-proposals"),
        params={"status": "pending"},
        headers=env.editor_h,
    )
    assert per_agent.status_code == 200, per_agent.text
    assert [p["id"] for p in per_agent.json()] == [proposal_id]
    # Filter auf einen anderen Agenten: leer.
    other = c.get(env.url(f"/agents/{env.other_agent}/memory-proposals"), headers=env.editor_h)
    assert other.json() == []
    workspace_wide = c.get(
        env.url("/memory-proposals"), params={"agent_id": str(env.agent)}, headers=env.editor_h
    )
    assert [p["id"] for p in workspace_wide.json()] == [proposal_id]
    # viewer sieht Vorschlaege zum Agentengedaechtnis nicht.
    assert c.get(env.url("/memory-proposals"), headers=env.viewer_h).json() == []
    unknown_agent = c.get(
        env.url("/agents/00000000-0000-0000-0000-000000000000/memory-proposals"),
        headers=env.editor_h,
    )
    assert _reason(unknown_agent, 404) == "agent_not_found"
    assert (
        _reason(c.get(env.url("/memory-proposals"), headers=env.agent_h), 403)
        == "missing_capability"
    )

    decide = env.url(f"/memory-proposals/{proposal_id}/decide")
    # viewer darf Agentengedaechtnis nicht entscheiden: nicht gefunden (kein 403).
    assert _reason(c.post(decide, json={"accept": True}, headers=env.viewer_h), 404) == (
        "memory_not_found"
    )
    assert _reason(c.post(decide, json={"accept": True}, headers=env.agent_h), 403) == (
        "missing_capability"
    )
    accepted = c.post(decide, json={"accept": True, "note": "passt"}, headers=env.editor_h)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["decided_by"] == str(env.editor)
    assert _fact(mem) == "Nutzer wohnt in Luebeck"
    again = c.post(decide, json={"accept": False}, headers=env.editor_h)
    assert _reason(again, 409) == "memory_proposal_not_pending"
    missing = c.post(
        env.url("/memory-proposals/00000000-0000-0000-0000-000000000000/decide"),
        json={"accept": True},
        headers=env.editor_h,
    )
    assert _reason(missing, 404) == "memory_not_found"

    # Ablehnung laesst den Eintrag unveraendert.
    second = env.proposal(mem, "Nutzer wohnt in Hamburg")
    rejected = c.post(
        env.url(f"/memory-proposals/{second}/decide"), json={"accept": False}, headers=env.admin_h
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert _fact(mem) == "Nutzer wohnt in Luebeck"
    accepted_only = c.get(
        env.url(f"/agents/{env.agent}/memory-proposals"),
        params={"status": "accepted"},
        headers=env.editor_h,
    )
    assert [p["id"] for p in accepted_only.json()] == [proposal_id]


# ------------------------------- Fremdes Nutzergedaechtnis: auch admin nicht


def test_admin_sieht_fremdes_nutzergedaechtnis_nicht(env: Env) -> None:
    """3.1.1: Kein Endpunkt liefert admin den Inhalt des Gedaechtnisses einer anderen Person."""
    c = env.client
    secret_fact = "Editor hat eine Nussallergie"
    mem = env.memory(secret_fact, subject=env.editor)
    proposal = env.proposal(mem, "Editor hat eine Erdnussallergie")
    admin = env.admin_h

    reads = [
        c.get(env.url("/me/memories"), headers=admin),
        c.get(env.url("/memory-proposals"), headers=admin),
        c.get(env.url(f"/agents/{env.agent}/memory-proposals"), headers=admin),
        c.get(env.url(f"/agents/{env.agent}/memories"), headers=admin),
    ]
    for res in reads:
        assert res.status_code == 200, res.text
        assert secret_fact not in res.text
        assert str(mem) not in res.text
        assert str(proposal) not in res.text

    not_found = [
        c.get(env.url(f"/me/memories/{mem}/history"), headers=admin),
        c.post(env.url(f"/me/memories/{mem}/confirm"), headers=admin),
        c.post(env.url(f"/me/memories/{mem}/reactivate"), headers=admin),
        c.post(
            env.url(f"/me/memories/{mem}/rollback"),
            json={"event_id": "00000000-0000-0000-0000-000000000000"},
            headers=admin,
        ),
        c.post(env.url(f"/me/memories/{mem}/triage"), json={"action": "reject"}, headers=admin),
        c.put(env.url(f"/me/memories/{mem}"), json={"fact": "ueberschrieben"}, headers=admin),
        c.delete(env.url(f"/me/memories/{mem}"), headers=admin),
        c.get(env.url(f"/agents/{env.agent}/memories/{mem}/history"), headers=admin),
        c.post(
            env.url(f"/memory-proposals/{proposal}/decide"), json={"accept": True}, headers=admin
        ),
    ]
    for res in not_found:
        assert _reason(res, 404) == "memory_not_found"
        assert secret_fact not in res.text
    assert _fact(mem) == secret_fact

    # Die Person selbst sieht und entscheidet — schon als editor ohne admin-Rechte.
    own = c.get(env.url("/me/memories"), headers=env.editor_h)
    assert [m["id"] for m in own.json()] == [str(mem)]
    own_proposals = c.get(env.url("/memory-proposals"), headers=env.editor_h)
    assert str(proposal) in [p["id"] for p in own_proposals.json()]
    decided = c.post(
        env.url(f"/memory-proposals/{proposal}/decide"),
        json={"accept": True},
        headers=env.editor_h,
    )
    assert decided.status_code == 200, decided.text
    assert _fact(mem) == "Editor hat eine Erdnussallergie"


# --------------------------- Historie, Rollback, Bestaetigen (Agentengedaechtnis)


def test_agentengedaechtnis_historie_rollback_confirm_reactivate(env: Env) -> None:
    c = env.client
    mem = env.memory("Nutzer mag Gruen", expires=True)
    base = env.url(f"/agents/{env.agent}/memories/{mem}")

    edited = c.put(base, json={"fact": "Nutzer mag Blau"}, headers=env.editor_h)
    assert edited.status_code == 200, edited.text
    history = c.get(f"{base}/history", headers=env.editor_h)
    assert history.status_code == 200, history.text
    events = history.json()
    assert [e["event"] for e in events] == ["edited"]
    edit_event = events[0]["id"]

    rolled = c.post(f"{base}/rollback", json={"event_id": edit_event}, headers=env.editor_h)
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()["fact"] == "Nutzer mag Gruen"
    after = [e["event"] for e in c.get(f"{base}/history", headers=env.editor_h).json()]
    assert after == ["edited", "rolled_back"]
    # Ereignis eines anderen Eintrags: gehoert nicht zu diesem, also nicht gefunden.
    other = env.memory("Anderer Eintrag")
    c.put(
        env.url(f"/agents/{env.agent}/memories/{other}"), json={"fact": "x y"}, headers=env.editor_h
    )
    other_event = c.get(
        env.url(f"/agents/{env.agent}/memories/{other}/history"), headers=env.editor_h
    ).json()[0]["id"]
    foreign = c.post(f"{base}/rollback", json={"event_id": other_event}, headers=env.editor_h)
    assert _reason(foreign, 404) == "memory_not_found"

    # Bestaetigen hebt den Verfall auf; zweimal geht nicht.
    confirmed = c.post(f"{base}/confirm", headers=env.editor_h)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["confirmed_at"] is not None
    assert confirmed.json()["expires_at"] is None
    twice = c.post(f"{base}/confirm", headers=env.editor_h)
    assert _reason(twice, 409) == "memory_transition_invalid"
    assert twice.json()["params"]["status"] == "active"

    # Reaktivieren nur aus `expired`.
    assert _reason(c.post(f"{base}/reactivate", headers=env.editor_h), 409) == (
        "memory_transition_invalid"
    )
    expired = env.memory("Abgelaufen", status="expired")
    revived = c.post(
        env.url(f"/agents/{env.agent}/memories/{expired}/reactivate"), headers=env.editor_h
    )
    assert revived.status_code == 200, revived.text
    assert revived.json()["status"] == "active"
    assert revived.json()["confirmed_at"] is not None

    # Rechte: viewer zu schwach, Agent-Token gesperrt, fremder Agent-Pfad: nicht gefunden.
    for method, path in (
        ("get", f"{base}/history"),
        ("post", f"{base}/confirm"),
        ("post", f"{base}/reactivate"),
    ):
        assert _reason(getattr(c, method)(path, headers=env.viewer_h), 403) == "insufficient_role"
        assert _reason(getattr(c, method)(path, headers=env.agent_h), 403) == "missing_capability"
    assert (
        _reason(
            c.post(f"{base}/rollback", json={"event_id": edit_event}, headers=env.viewer_h), 403
        )
        == "insufficient_role"
    )
    assert (
        _reason(c.post(f"{base}/rollback", json={"event_id": edit_event}, headers=env.agent_h), 403)
        == "missing_capability"
    )
    wrong_agent = env.url(f"/agents/{env.other_agent}/memories/{mem}/history")
    assert _reason(c.get(wrong_agent, headers=env.editor_h), 404) == "memory_not_found"


def test_rollback_ohne_vorzustand(env: Env) -> None:
    """Ein Ereignis ohne `before` (z. B. `created`) hat keinen Vorzustand: 409."""
    c = env.client
    mem = env.memory("Nutzer mag Rot")
    event_id = db_fetchval(
        "INSERT INTO agent_memory_event (workspace_id, memory_id, event, actor_kind, after) "
        "VALUES ($1, $2, 'created', 'system', '{}'::jsonb) RETURNING id",
        env.ws,
        mem,
    )
    res = c.post(
        env.url(f"/agents/{env.agent}/memories/{mem}/rollback"),
        json={"event_id": str(event_id)},
        headers=env.editor_h,
    )
    assert _reason(res, 409) == "memory_transition_invalid"
    assert res.json()["params"] == {"status": "active", "event": "created"}


# ------------------------------------------------- Eigenes Nutzergedaechtnis


def test_me_memories_kuratieren(env: Env) -> None:
    c = env.client
    pending = env.memory("Viewer arbeitet remote", subject=env.viewer, status="pending")
    active = env.memory("Viewer mag Katzen", subject=env.viewer, expires=True)
    expired = env.memory("Viewer spielt Schach", subject=env.viewer, status="expired")
    me = env.viewer_h

    listed = c.get(env.url("/me/memories"), headers=me)
    assert listed.status_code == 200, listed.text
    assert {m["id"] for m in listed.json()} == {str(pending), str(active), str(expired)}
    only_pending = c.get(env.url("/me/memories"), params={"status": "pending"}, headers=me)
    assert [m["id"] for m in only_pending.json()] == [str(pending)]
    assert _reason(c.get(env.url("/me/memories"), headers=env.agent_h), 403) == (
        "missing_capability"
    )

    # Triage (bisher ungetestet, C3a-Review): Freigabe mit Fakt-Edition, dann 409.
    approved = c.post(
        env.url(f"/me/memories/{pending}/triage"),
        json={"action": "approve", "fact": "Viewer arbeitet meist remote"},
        headers=me,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "active"
    assert approved.json()["fact"] == "Viewer arbeitet meist remote"
    again = c.post(env.url(f"/me/memories/{pending}/triage"), json={"action": "reject"}, headers=me)
    assert _reason(again, 409) == "memory_not_pending"
    rejectable = env.memory("Viewer mag Laerm", subject=env.viewer, status="pending")
    rejected = c.post(
        env.url(f"/me/memories/{rejectable}/triage"),
        json={"action": "reject", "fact": "ignoriert", "note": "falsch"},
        headers=me,
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["fact"] == "Viewer mag Laerm"
    agent_triage = c.post(
        env.url(f"/me/memories/{active}/triage"), json={"action": "reject"}, headers=env.agent_h
    )
    assert _reason(agent_triage, 403) == "missing_capability"

    # Bearbeiten, Historie, Rollback.
    edited = c.put(env.url(f"/me/memories/{active}"), json={"fact": "Viewer mag Hunde"}, headers=me)
    assert edited.status_code == 200, edited.text
    history = c.get(env.url(f"/me/memories/{active}/history"), headers=me)
    assert history.status_code == 200, history.text
    assert [e["event"] for e in history.json()] == ["edited"]
    rolled = c.post(
        env.url(f"/me/memories/{active}/rollback"),
        json={"event_id": history.json()[0]["id"]},
        headers=me,
    )
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()["fact"] == "Viewer mag Katzen"

    # Bestaetigen und Reaktivieren.
    confirmed = c.post(env.url(f"/me/memories/{active}/confirm"), headers=me)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["expires_at"] is None
    assert _reason(c.post(env.url(f"/me/memories/{active}/confirm"), headers=me), 409) == (
        "memory_transition_invalid"
    )
    revived = c.post(env.url(f"/me/memories/{expired}/reactivate"), headers=me)
    assert revived.status_code == 200, revived.text
    assert revived.json()["status"] == "active"
    assert _reason(c.post(env.url(f"/me/memories/{expired}/reactivate"), headers=me), 409) == (
        "memory_transition_invalid"
    )

    # Ein Eintrag des Agentengedaechtnisses ist ueber /me nicht erreichbar.
    agent_mem = env.memory("Agent-Fakt")
    for res in (
        c.put(env.url(f"/me/memories/{agent_mem}"), json={"fact": "x y"}, headers=env.admin_h),
        c.get(env.url(f"/me/memories/{agent_mem}/history"), headers=env.admin_h),
        c.delete(env.url(f"/me/memories/{agent_mem}"), headers=env.admin_h),
    ):
        assert _reason(res, 404) == "memory_not_found"
    assert _fact(agent_mem) == "Agent-Fakt"

    # Loeschen: hart, danach nicht gefunden.
    assert c.delete(env.url(f"/me/memories/{active}"), headers=me).status_code == 204
    assert _reason(c.delete(env.url(f"/me/memories/{active}"), headers=me), 404) == (
        "memory_not_found"
    )
    assert db_fetchval("SELECT count(*) FROM agent_memory WHERE id = $1", active) == 0
    assert _reason(c.delete(env.url(f"/me/memories/{expired}"), headers=env.agent_h), 403) == (
        "missing_capability"
    )
