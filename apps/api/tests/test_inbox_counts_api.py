"""`GET /inbox/counts[?agent_id]` — Aufgaben-Zaehler (Navigation & Transparenz W1).

Belegt gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`) die Tabelle §2.2 der
Spec `navigation-transparenz-design-2026-10.md`:

- **Rollen:** viewer sieht nur `memory_approval` (eigenes Nutzergedaechtnis),
  alle anderen Arten sind `null`; editor sieht alle Arten, Versionen und
  Muster zaehlen nicht in `total`; admin zaehlt Versionen und System-Prompts
  mit, Muster nie.
- **Gleiche Zahl wie die Liste:** `memory_approval` = `GET /memories/counts
  ?status=pending` + offene `GET /memory-proposals`, `cases_open` = Faelle
  `open`+`reopened` aus `GET /cases/counts`, `patterns` = Laenge von
  `GET /patterns`, je Rolle.
- **Faellig-Regel:** Nachschau-Datum der Massnahme, sonst des Protokolls;
  `reviewed`/`withdrawn` zaehlt nicht, ein anderes juengstes Event schon.
- **`agent_id`:** filtert jede Art; Versionen entfallen (`null`); ein
  fremder oder unbekannter Agent ist 404 `agent_not_found`.
- **Isolation:** ein zweiter Workspace bleibt unberuehrt, fremder Workspace
  ist zu, und der Weg laeuft unter der Laufzeitrolle `who2be_app` (RLS).
- Agent-gebundene Tokens: 403 `missing_capability`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient
from test_rls_control_plane_api import app_role_client  # type: ignore[import-not-found]

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("migrated_db")]

__all__ = ["app_role_client"]

_TODAY = datetime.now(UTC).date()
_PAST = _TODAY - timedelta(days=3)
_FUTURE = _TODAY + timedelta(days=30)


def _db(coro_fn: Callable[[asyncpg.Connection], Any]) -> Any:
    async def _run() -> Any:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await coro_fn(conn)
        finally:
            await conn.close()

    return asyncio.run(_run())


class Env:
    """Ein Workspace mit admin (Owner), editor, viewer und zwei Agenten."""

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
        self.base = f"/v1/workspaces/{self.ws}"
        self.admin_h = make_auth(self.owner)
        self.editor_h = make_auth(self.editor)
        self.viewer_h = make_auth(self.viewer)
        agent, self.agent_h = agent_token(client, self.base, "Inbox-Agent", {}, self.admin_h)
        self.agent = UUID(agent)
        other, _ = agent_token(client, self.base, "Inbox-Zweit", {}, self.admin_h)
        self.other_agent = UUID(other)

    def users(self) -> list[UUID]:
        return [self.owner, self.editor, self.viewer]

    def counts(self, headers: dict[str, str], **params: Any) -> dict[str, Any]:
        res = self.client.get(f"{self.base}/inbox/counts", params=params, headers=headers)
        assert res.status_code == 200, res.text
        body: dict[str, Any] = res.json()
        return body

    # --- Seeds (an der Logik vorbei, damit jede Art gezielt entsteht) -------

    def memory(
        self,
        *,
        status: str = "pending",
        agent: UUID | None = None,
        subject: UUID | None = None,
        kind: str = "user_fact",
    ) -> UUID:
        submitter = agent or self.agent
        memory_id: UUID = db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, source, subject_user_id) "
            "VALUES ($1, $2, $3, $4, 'Fakt ' || gen_random_uuid(), 'preference', 6, $5, $6, "
            "        'user_stated', 'agent', $7) RETURNING id",
            self.ws,
            None if subject is not None else submitter,
            submitter,
            status,
            kind,
            "user" if subject is not None else "agent",
            subject,
        )
        return memory_id

    def proposal(self, memory_id: UUID, agent: UUID | None = None) -> None:
        db_execute(
            "INSERT INTO agent_memory_proposal (workspace_id, memory_id, agent_id, action, "
            " new_fact, reason) VALUES ($1, $2, $3, 'change', 'Neu', 'Test')",
            self.ws,
            memory_id,
            agent or self.agent,
        )

    def case(self, agent: UUID, headers: dict[str, str] | None = None) -> str:
        res = self.client.post(
            f"{self.base}/cases",
            json={
                "agent_id": str(agent),
                "situation": "Lage",
                "behavior": "Verhalten",
                "expected_behavior": "Erwartet",
            },
            headers=headers or self.admin_h,
        )
        assert res.status_code == 201, res.text
        return str(res.json()["id"])

    def case_status(self, case_id: str, status: str) -> None:
        # Status ist aus dem juengsten Event abgeleitet; fuer die Zaehlung reicht
        # ein Event mit `to_status` (Muster der Fall-Schema-Tests).
        db_execute(
            "INSERT INTO agent_case_event (workspace_id, case_id, event, actor_kind, actor_id, "
            " note) VALUES ($1, $2, $3, 'human', $4, 'Test')",
            self.ws,
            UUID(case_id),
            status,
            self.owner,
        )

    def measure(
        self,
        agent: UUID,
        *,
        session_follow_up: date,
        measure_follow_up: date | None = None,
        last_event: str | None = None,
    ) -> UUID:
        async def _run(conn: asyncpg.Connection) -> UUID:
            case_id = await conn.fetchval(
                "INSERT INTO agent_case (workspace_id, agent_id, reporter_kind, "
                " reporter_agent_id, situation, behavior, expected_behavior) "
                "VALUES ($1, $2, 'agent', $2, 'S', 'B', 'E') RETURNING id",
                self.ws,
                agent,
            )
            # Fall soll die Zahl `cases_open` nicht veraendern: gleich abschliessen.
            await conn.execute(
                "INSERT INTO agent_case_event (workspace_id, case_id, event, actor_kind, "
                " actor_id, note) VALUES ($1, $2, 'dismissed', 'human', $3, 'Test')",
                self.ws,
                case_id,
                self.owner,
            )
            test_case_id = await conn.fetchval(
                "INSERT INTO test_case (workspace_id, agent_id, title, input, "
                " expected_behavior, check_kind, created_by_kind, created_by) "
                "VALUES ($1, $2, 'T', 'I', 'E', 'human_rule', 'agent', $2) RETURNING id",
                self.ws,
                agent,
            )
            session_id = await conn.fetchval(
                "INSERT INTO feedback_session (workspace_id, agent_id, trigger, summary, "
                " follow_up_at, submitted_by_kind, submitted_by) "
                "VALUES ($1, $2, 'manual', 'Zusammenfassung', $3, 'agent', $2) RETURNING id",
                self.ws,
                agent,
                session_follow_up,
            )
            measure_id: UUID = await conn.fetchval(
                "INSERT INTO measure (workspace_id, agent_id, session_id, target, entity_id, "
                " change_summary, test_case_id, success_criterion, counterposition, "
                " follow_up_at) "
                "VALUES ($1, $2, $3, 'playbook', gen_random_uuid(), 'C', $4, 'S', 'G', $5) "
                "RETURNING id",
                self.ws,
                agent,
                session_id,
                test_case_id,
                measure_follow_up,
            )
            await conn.execute(
                "INSERT INTO measure_case (workspace_id, measure_id, agent_id, case_id) "
                "VALUES ($1, $2, $3, $4)",
                self.ws,
                measure_id,
                agent,
                case_id,
            )
            if last_event is not None:
                await self._event(conn, measure_id, last_event)
            return measure_id

        result: UUID = _db(_run)
        return result

    async def _event(self, conn: asyncpg.Connection, measure_id: UUID, event: str) -> None:
        verdict = "effective" if event == "reviewed" else None
        note = "Grund" if event == "withdrawn" else None
        actor_kind = "system" if event in ("activated", "follow_up_prepared") else "human"
        version_type = "playbook" if event in ("draft_linked", "activated") else None
        metrics = '{"passed": 1}' if event == "follow_up_prepared" else None
        await conn.execute(
            "INSERT INTO measure_event (workspace_id, measure_id, event, actor_kind, actor_id, "
            " version_entity_type, version_id, verdict, note, metrics) "
            "VALUES ($1, $2, $3, $4, $5, $6, CASE WHEN $6::text IS NULL THEN NULL "
            "        ELSE gen_random_uuid() END, $7, $8, $9::text::jsonb)",
            self.ws,
            measure_id,
            event,
            actor_kind,
            self.owner if actor_kind == "human" else None,
            version_type,
            verdict,
            note,
            metrics,
        )


@pytest.fixture
def env(patched_jwt_secret: str, make_auth_headers: AuthFactory) -> Iterator[Env]:
    with TestClient(app) as client:
        e = Env(client, make_auth_headers)
        try:
            yield e
        finally:
            cleanup_workspaces(e.users())


def _persona_in_review(env: Env) -> None:
    res = env.client.post(
        f"{env.base}/personas",
        json={
            "name": "Inbox-Persona",
            "content": {"description": "d", "system_prompt": "s", "traits": ["t"]},
        },
        headers=env.admin_h,
    )
    assert res.status_code == 201, res.text
    db_execute(
        "UPDATE persona_version SET status = 'review' WHERE persona_id = $1 AND version = 1",
        UUID(res.json()["id"]),
    )


def _system_prompt_in_review(env: Env) -> None:
    res = env.client.post(
        f"{env.base}/system-prompts",
        json={"name": "Inbox-Template", "content": {"body": "Du bist ein Test-Agent."}},
        headers=env.admin_h,
    )
    assert res.status_code == 201, res.text
    db_execute(
        "UPDATE system_prompt_template_version SET status = 'review' "
        "WHERE template_id = $1 AND version = 1",
        UUID(res.json()["id"]),
    )


def _seed_every_kind(env: Env) -> None:
    """Je Art mindestens ein offener Eintrag, verteilt auf zwei Agenten."""
    # Art 2: Agentengedaechtnis (editor+), eigenes Nutzergedaechtnis des viewers,
    # fremdes Nutzergedaechtnis (zaehlt fuer niemanden ausser der Person),
    # Lernvorschlag (zaehlt nie), ein offener Vorschlag.
    env.memory(agent=env.agent)
    env.memory(agent=env.other_agent)
    env.memory(subject=env.viewer)
    env.memory(subject=env.editor)
    env.memory(kind="lesson", agent=env.agent)
    env.proposal(env.memory(status="active", agent=env.agent))
    # Art 4: zwei offen, einer wieder offen, einer eingeordnet (zaehlt nicht).
    env.case(env.agent)
    env.case(env.other_agent, headers=env.viewer_h)  # vom viewer gemeldet
    env.case_status(env.case(env.agent), "reopened")
    env.case_status(env.case(env.agent), "triaged")
    # Art 1: drei faellig, zwei nicht.
    env.measure(env.agent, session_follow_up=_PAST)
    env.measure(env.agent, session_follow_up=_FUTURE, measure_follow_up=_TODAY)
    env.measure(env.other_agent, session_follow_up=_PAST, last_event="activated")
    env.measure(env.agent, session_follow_up=_PAST, measure_follow_up=_FUTURE)
    env.measure(env.agent, session_follow_up=_PAST, last_event="reviewed")
    # Art 3
    _persona_in_review(env)
    _system_prompt_in_review(env)


def _list_numbers(env: Env, headers: dict[str, str], **params: Any) -> dict[str, int]:
    """Dieselben Zahlen ueber die Listen-Endpunkte, je Rolle."""
    agent = params.get("agent_id")
    mem = env.client.get(
        f"{env.base}/memories/counts",
        params={"status": "pending", **({"agent_id": agent} if agent else {})},
        headers=headers,
    )
    assert mem.status_code == 200, mem.text
    props = env.client.get(
        f"{env.base}/memory-proposals",
        params={"status": "pending", **({"agent_id": agent} if agent else {})},
        headers=headers,
    )
    assert props.status_code == 200, props.text
    out = {"memory_approval": mem.json()["total"] + len(props.json())}
    cases = env.client.get(f"{env.base}/cases/counts", params=params, headers=headers)
    assert cases.status_code == 200, cases.text
    out["cases_open"] = cases.json()["open"] + cases.json()["reopened"]
    patterns = env.client.get(f"{env.base}/patterns", params=params, headers=headers)
    if patterns.status_code == 200:
        out["patterns"] = len(patterns.json()["patterns"])
    return out


def test_viewer_sieht_nur_eigenes_gedaechtnis(env: Env) -> None:
    _seed_every_kind(env)
    counts = env.counts(env.viewer_h)
    # Nur das eigene Nutzergedaechtnis; Fall, Muster, Versionen, Nachkontrollen
    # sind keine Arten fuer viewer — auch der selbst gemeldete Fall nicht.
    assert counts == {
        "follow_ups_due": None,
        "memory_approval": 1,
        "versions_review": None,
        "system_prompts_review": None,
        "cases_open": None,
        "patterns": None,
        "total": 1,
    }
    assert counts["memory_approval"] == _list_numbers(env, env.viewer_h)["memory_approval"]


def test_editor_alle_arten_versionen_und_muster_ohne_glocke(env: Env) -> None:
    before = env.counts(env.editor_h)
    _seed_every_kind(env)
    counts = env.counts(env.editor_h)
    listed = _list_numbers(env, env.editor_h)
    # Agentengedaechtnis 2 + eigenes Nutzergedaechtnis 1 + Vorschlag 1.
    assert counts["memory_approval"] == listed["memory_approval"] == 4
    assert counts["cases_open"] == listed["cases_open"] == 3
    assert counts["patterns"] == listed["patterns"]
    assert counts["follow_ups_due"] == 3
    assert counts["versions_review"] == before["versions_review"] + 1
    assert counts["system_prompts_review"] == before["system_prompts_review"] + 1
    # Versionen nur fuer admin, Muster nie in der Glocke.
    assert counts["total"] == 4 + 3 + 3


def test_admin_zaehlt_versionen_mit_muster_nie(env: Env) -> None:
    _seed_every_kind(env)
    # Drei offene Faelle am selben Agenten ohne Zuordnung bilden kein Muster;
    # drei Lernvorschlaege gleichen Inhalts schon (Spec 3.7) — Muster > 0.
    for _ in range(3):
        db_execute(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, kind, scope, origin) VALUES ($1, $2, $2, 'pending', "
            " 'Der Agent nennt die Kuendigungsfrist nicht', 'lesson', 'agent', 'inferred')",
            env.ws,
            env.agent,
        )
    counts = env.counts(env.admin_h)
    listed = _list_numbers(env, env.admin_h)
    assert counts["patterns"] == listed["patterns"]
    assert counts["patterns"] >= 1
    # admin sieht fremdes Nutzergedaechtnis nie (auch nicht als Zahl): 2 + 1.
    assert counts["memory_approval"] == listed["memory_approval"] == 3
    expected = (
        counts["memory_approval"]
        + counts["cases_open"]
        + counts["follow_ups_due"]
        + counts["versions_review"]
        + counts["system_prompts_review"]
    )
    assert counts["total"] == expected
    assert counts["total"] > counts["memory_approval"] + counts["cases_open"] + 3


def test_agent_filter(env: Env) -> None:
    _seed_every_kind(env)
    one = env.counts(env.editor_h, agent_id=str(env.agent))
    other = env.counts(env.editor_h, agent_id=str(env.other_agent))
    assert (
        one["memory_approval"]
        == _list_numbers(env, env.editor_h, agent_id=str(env.agent))["memory_approval"]
    )
    assert one["cases_open"] == 2
    assert other["cases_open"] == 1
    assert one["follow_ups_due"] == 2
    assert other["follow_ups_due"] == 1
    # Versionen gehoeren keinem Agenten.
    assert one["versions_review"] is None
    assert one["system_prompts_review"] is None
    assert one["total"] == one["memory_approval"] + one["cases_open"] + one["follow_ups_due"]
    # viewer mit Agent-Filter: nur das eigene Nutzergedaechtnis dieses Agenten.
    viewer = env.counts(env.viewer_h, agent_id=str(env.agent))
    assert viewer["memory_approval"] == 1
    assert viewer["cases_open"] is None


def test_faellig_regel(env: Env) -> None:
    base = env.counts(env.editor_h)["follow_ups_due"]
    assert base == 0
    env.measure(env.agent, session_follow_up=_PAST, last_event="withdrawn")
    env.measure(env.agent, session_follow_up=_PAST, measure_follow_up=_FUTURE)
    env.measure(env.agent, session_follow_up=_TODAY + timedelta(days=1))
    assert env.counts(env.editor_h)["follow_ups_due"] == 0
    for event in ("draft_linked", "follow_up_prepared"):
        env.measure(env.agent, session_follow_up=_PAST, last_event=event)
    env.measure(env.agent, session_follow_up=_FUTURE, measure_follow_up=_PAST)
    assert env.counts(env.editor_h)["follow_ups_due"] == 3


def test_fremder_agent_fremder_workspace_und_agent_token(
    env: Env, make_auth_headers: AuthFactory
) -> None:
    stranger = fresh_user_id()
    foreign_ws = setup_workspace(stranger)
    try:
        foreign_h = make_auth_headers(stranger)
        foreign_agent, _ = agent_token(
            env.client, f"/v1/workspaces/{foreign_ws}", "Fremd", {}, foreign_h
        )
        _seed_every_kind(env)
        foreign_before = env.client.get(
            f"/v1/workspaces/{foreign_ws}/inbox/counts", headers=foreign_h
        ).json()
        # Ein Agent aus einem anderen Workspace ist hier unbekannt.
        res = env.client.get(
            f"{env.base}/inbox/counts", params={"agent_id": foreign_agent}, headers=env.admin_h
        )
        assert res.status_code == 404, res.text
        assert res.json()["reason"] == "agent_not_found"
        # Fremder Workspace ist zu.
        blocked = env.client.get(f"/v1/workspaces/{foreign_ws}/inbox/counts", headers=env.admin_h)
        assert blocked.status_code in (403, 404), blocked.text
        # Der fremde Workspace zaehlt nichts aus diesem.
        assert foreign_before["memory_approval"] == 0
        assert foreign_before["cases_open"] == 0
        assert foreign_before["follow_ups_due"] == 0
        # Agent-Token: der Eingang ist Menschen vorbehalten.
        agent = env.client.get(f"{env.base}/inbox/counts", headers=env.agent_h)
        assert agent.status_code == 403, agent.text
        assert agent.json()["reason"] == "missing_capability"
    finally:
        cleanup_workspaces([stranger])


def test_unter_laufzeitrolle_who2be_app(
    app_role_client: TestClient, make_auth_headers: AuthFactory
) -> None:
    """RLS: unter `who2be_app` dieselben Zahlen, ein zweiter Workspace bleibt 0."""
    owner, stranger = fresh_user_id(), fresh_user_id()
    ws, foreign = setup_workspace(owner), setup_workspace(stranger)
    try:
        auth, foreign_auth = make_auth_headers(owner), make_auth_headers(stranger)
        base = f"/v1/workspaces/{ws}"
        agent, _ = agent_token(app_role_client, base, "RLS-Inbox", {}, auth)
        env = Env.__new__(Env)
        env.client, env.ws, env.owner, env.agent = app_role_client, ws, owner, UUID(agent)
        env.memory(agent=env.agent)
        env.measure(env.agent, session_follow_up=_PAST)
        res = app_role_client.get(f"{base}/inbox/counts", headers=auth)
        assert res.status_code == 200, res.text
        assert res.json()["memory_approval"] == 1
        assert res.json()["follow_ups_due"] == 1
        other = app_role_client.get(f"/v1/workspaces/{foreign}/inbox/counts", headers=foreign_auth)
        assert other.status_code == 200, other.text
        assert other.json()["memory_approval"] == 0
        assert other.json()["follow_ups_due"] == 0
    finally:
        cleanup_workspaces([owner, stranger])
