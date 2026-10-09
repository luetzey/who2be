"""Integrationstests fuer Gespraechsprotokoll und Massnahme (ADR-0053 3.5/3.6, Migration 0103).

Belegt auf der Laufzeitrolle `who2be_app` (NOBYPASSRLS) in einem isolierten
Schema (Muster `test_agent_case_schema.py`):

- **CHECKs:** Laengen (summary 4 000, change_summary 2 000,
  success_criterion/counterposition je 1 000), Wertemengen, Pflichtfelder
  (`follow_up_at`, `test_case_id`), Event-Form (Version, `metrics`,
  `verdict`, Begruendung, Akteur).
- **Unveraenderlichkeit:** UPDATE und DELETE durch die App-Rolle schlagen auf
  allen fuenf Tabellen fehl (3.5).
- **RLS:** alle fuenf Tabellen strikt workspace-getrennt.
- **FKs:** Faelle, Pruefall und Korrektur gehoeren dem besprochenen Agenten;
  alles im selben Workspace.
- **Loeschen (PM-6):** Fall weg -> nur die Verknuepfungen gehen; Agent bzw.
  Workspace weg -> alles geht.
- **Repository:** Einreichen in der Transaktion des Aufrufers (samt
  Rueckrollen), Lesen je ID/Agent/Fall mit Cursor, Events mit abgeleitetem
  Zustand, Massnahmen je Fall und je verknuepfter Version.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

import asyncpg
import pytest
from pydantic import ValidationError

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.tenancy import apply_tenant_settings, tenant_scope
from who2be_api.repositories.session_repository import PgSessionRepository
from who2be_models import (
    MeasureActorKind,
    MeasureCreate,
    MeasureEventCreate,
    MeasureEventKind,
    MeasureState,
    MeasureTarget,
    MeasureVerdict,
    SessionCreate,
    SessionParticipantKind,
    SessionRead,
    SessionSubmitterKind,
    SessionTrigger,
    measure_state_for,
)

# Test-only Passwort fuer die App-Rolle (per format() in ALTER ROLE eingesetzt).
_APP_PASSWORD = "feedback_session_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret

_TABLES = (
    "feedback_session",
    "feedback_session_case",
    "measure",
    "measure_case",
    "measure_event",
)

_FOLLOW_UP = date(2026, 11, 20)


@dataclass(frozen=True)
class _Seed:
    schema: str
    ws_a: UUID
    ws_b: UUID
    agent_a: UUID
    agent_a2: UUID
    agent_b: UUID
    user: UUID


@dataclass
class _Env:
    owner: asyncpg.Connection
    app: asyncpg.Connection
    seed: _Seed

    async def as_tenant(self, workspace_id: UUID) -> None:
        await self.app.execute(
            "SELECT set_config('app.current_tenant', $1, false)", str(workspace_id)
        )


async def _seed(owner: asyncpg.Connection, schema: str) -> _Seed:
    ids: dict[str, UUID] = {}
    user = uuid4()
    for key in ("a", "b"):
        org_id = await owner.fetchval(
            "INSERT INTO organization (name, slug, kind) VALUES ($1, $1, 'company') RETURNING id",
            f"org-{key}-{secrets.token_hex(4)}",
        )
        ids[f"ws_{key}"] = await owner.fetchval(
            "INSERT INTO workspace (org_id, name, slug) VALUES ($1, $2, $2) RETURNING id",
            org_id,
            f"ws-{key}",
        )
    for name, ws in (("agent_a", "ws_a"), ("agent_a2", "ws_a"), ("agent_b", "ws_b")):
        ids[name] = await owner.fetchval(
            "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, $3) RETURNING id",
            ids[ws],
            user,
            name,
        )
    return _Seed(schema=schema, user=user, **ids)


def _with_env(body: Callable[[_Env], Awaitable[None]]) -> None:
    """Migriert ein isoliertes Schema, seedet zwei Workspaces, verbindet als App-Rolle."""
    settings = get_settings()
    schema = f"session_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        app: asyncpg.Connection | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)
            seed = await _seed(owner, schema)
            await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
            app = await asyncpg.connect(
                settings.database_url, user="who2be_app", password=_APP_PASSWORD
            )
            await app.execute(f'SET search_path TO "{schema}"')
            await body(_Env(owner=owner, app=app, seed=seed))
        finally:
            if app is not None:
                await app.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


# --- Roh-Inserts (Schema-Ebene) ---------------------------------------------------


async def _insert_case(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> UUID:
    case_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case (workspace_id, agent_id, reporter_kind, reporter_agent_id, "
        " situation, behavior, expected_behavior) "
        "VALUES ($1, $2, 'agent', $2, 'Kunde fragt.', 'Keine Frist.', 'Nennt die Frist.') "
        "RETURNING id",
        workspace_id,
        agent_id,
    )
    return case_id


async def _insert_test_case(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> UUID:
    test_case_id: UUID = await conn.fetchval(
        "INSERT INTO test_case (workspace_id, agent_id, title, input, expected_behavior, "
        " check_kind, created_by_kind, created_by) "
        "VALUES ($1, $2, 'Frist', 'Ich will kuendigen.', 'Nennt die Frist.', 'human_rule', "
        " 'agent', $2) RETURNING id",
        workspace_id,
        agent_id,
    )
    return test_case_id


async def _insert_session(
    conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID, **overrides: object
) -> UUID:
    values: dict[str, object] = {
        "trigger": "manual",
        "participants": "[]",
        "summary": "Frist fehlt im Playbook.",
        "decisions": "[]",
        "dissent": "[]",
        "follow_up_at": _FOLLOW_UP,
        "supersedes_id": None,
        "submitted_by_kind": "agent",
        "submitted_by": agent_id,
    }
    values.update(overrides)
    casts = {"participants", "decisions", "dissent"}
    placeholders = [
        f"${i}::text::jsonb" if key in casts else f"${i}" for i, key in enumerate(values, start=3)
    ]
    session_id: UUID = await conn.fetchval(
        "INSERT INTO feedback_session (workspace_id, agent_id, "
        + ", ".join(values)
        + ") VALUES ($1, $2, "
        + ", ".join(placeholders)
        + ") RETURNING id",
        workspace_id,
        agent_id,
        *values.values(),
    )
    return session_id


async def _link_session_case(
    conn: asyncpg.Connection, workspace_id: UUID, session_id: UUID, agent_id: UUID, case_id: UUID
) -> None:
    await conn.execute(
        "INSERT INTO feedback_session_case (workspace_id, session_id, agent_id, case_id) "
        "VALUES ($1, $2, $3, $4)",
        workspace_id,
        session_id,
        agent_id,
        case_id,
    )


async def _insert_measure(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    agent_id: UUID,
    session_id: UUID,
    test_case_id: UUID | None,
    **overrides: object,
) -> UUID:
    values: dict[str, object] = {
        "target": "playbook",
        "entity_id": uuid4(),
        "change_summary": "Frist ins Playbook.",
        "test_case_id": test_case_id,
        "success_criterion": "Pruefall besteht.",
        "counterposition": "Frist steht schon in der Resource.",
        "follow_up_at": None,
    }
    values.update(overrides)
    measure_id: UUID = await conn.fetchval(
        "INSERT INTO measure (workspace_id, agent_id, session_id, "
        + ", ".join(values)
        + ") VALUES ($1, $2, $3, "
        + ", ".join(f"${i}" for i in range(4, 4 + len(values)))
        + ") RETURNING id",
        workspace_id,
        agent_id,
        session_id,
        *values.values(),
    )
    return measure_id


async def _link_measure_case(
    conn: asyncpg.Connection, workspace_id: UUID, measure_id: UUID, agent_id: UUID, case_id: UUID
) -> None:
    await conn.execute(
        "INSERT INTO measure_case (workspace_id, measure_id, agent_id, case_id) "
        "VALUES ($1, $2, $3, $4)",
        workspace_id,
        measure_id,
        agent_id,
        case_id,
    )


async def _insert_event(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    measure_id: UUID,
    event: str,
    **overrides: object,
) -> UUID:
    values: dict[str, object] = {
        "actor_kind": "human",
        "actor_id": uuid4(),
        "version_entity_type": None,
        "version_id": None,
        "verdict": None,
        "metrics": None,
        "note": None,
    }
    values.update(overrides)
    placeholders = [
        f"${i}::text::jsonb" if key == "metrics" else f"${i}"
        for i, key in enumerate(values, start=4)
    ]
    event_id: UUID = await conn.fetchval(
        "INSERT INTO measure_event (workspace_id, measure_id, event, "
        + ", ".join(values)
        + ") VALUES ($1, $2, $3, "
        + ", ".join(placeholders)
        + ") RETURNING id",
        workspace_id,
        measure_id,
        event,
        *values.values(),
    )
    return event_id


@dataclass(frozen=True)
class _Graph:
    case: UUID
    test_case: UUID
    session: UUID
    measure: UUID
    event: UUID


async def _graph(conn: asyncpg.Connection, workspace_id: UUID, agent_id: UUID) -> _Graph:
    """Ein vollstaendiges Protokoll: Fall, Pruefall, Sitzung, Massnahme, Event."""
    case = await _insert_case(conn, workspace_id, agent_id)
    test_case = await _insert_test_case(conn, workspace_id, agent_id)
    session = await _insert_session(conn, workspace_id, agent_id)
    await _link_session_case(conn, workspace_id, session, agent_id, case)
    measure = await _insert_measure(conn, workspace_id, agent_id, session, test_case)
    await _link_measure_case(conn, workspace_id, measure, agent_id, case)
    event = await _insert_event(
        conn,
        workspace_id,
        measure,
        "draft_linked",
        version_entity_type="playbook",
        version_id=uuid4(),
    )
    return _Graph(case=case, test_case=test_case, session=session, measure=measure, event=event)


# --- CHECKs ----------------------------------------------------------------------


@pytest.mark.integration
def test_session_checks_lengths_and_value_sets() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        # Zulaessig: Obergrenze genau, jeder Anlass, beide Einreicher.
        await _insert_session(env.app, s.ws_a, s.agent_a, summary="s" * 4000)
        for trigger in ("threshold", "scheduled", "manual"):
            await _insert_session(env.app, s.ws_a, s.agent_a, trigger=trigger)
        await _insert_session(
            env.app, s.ws_a, s.agent_a, submitted_by_kind="human", submitted_by=s.user
        )

        rejected: list[dict[str, object]] = [
            {"summary": "s" * 4001},
            {"summary": ""},
            {"trigger": "weekly"},
            {"submitted_by_kind": "system"},
            {"participants": "{}"},  # Liste, kein Objekt
            {"decisions": '"text"'},
            {"dissent": "1"},
        ]
        for overrides in rejected:
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_session(env.app, s.ws_a, s.agent_a, **overrides)
        for column in ("follow_up_at", "summary", "submitted_by"):
            with pytest.raises(asyncpg.NotNullViolationError):
                await _insert_session(env.app, s.ws_a, s.agent_a, **{column: None})

    _with_env(body)


@pytest.mark.integration
def test_measure_checks_lengths_target_and_test_case_required() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        session = await _insert_session(env.app, s.ws_a, s.agent_a)
        test_case = await _insert_test_case(env.owner, s.ws_a, s.agent_a)

        async def measure(**overrides: object) -> UUID:
            chosen = overrides.pop("test_case_id", test_case)
            assert chosen is None or isinstance(chosen, UUID)
            return await _insert_measure(env.app, s.ws_a, s.agent_a, session, chosen, **overrides)

        # Zulaessig: Obergrenzen genau getroffen, jedes Ziel ausser model_limit.
        await measure(
            change_summary="c" * 2000,
            success_criterion="k" * 1000,
            counterposition="g" * 1000,
            follow_up_at=_FOLLOW_UP,
        )
        for target in ("persona", "playbook", "resource", "external_tool",
                       "system_prompt_template", "memory"):  # fmt: skip
            await measure(target=target)
        await measure(target="tool_policy", entity_id=None)

        rejected: list[dict[str, object]] = [
            {"change_summary": "c" * 2001},
            {"change_summary": ""},
            {"success_criterion": "k" * 1001},
            {"success_criterion": ""},
            {"counterposition": "g" * 1001},
            {"counterposition": ""},
            {"target": "model_limit", "entity_id": None},  # 3.6: ausser model_limit
            {"target": "tool_policy"},  # mit entity_id
            {"target": "playbook", "entity_id": None},  # ohne entity_id
        ]
        for overrides in rejected:
            with pytest.raises(asyncpg.CheckViolationError):
                await measure(**overrides)
        # Pruefall ist Pflicht (3.6), ebenso Zusammenfassung und Kriterien.
        for column in ("test_case_id", "change_summary", "success_criterion", "counterposition"):
            with pytest.raises(asyncpg.NotNullViolationError):
                await measure(**{column: None})

    _with_env(body)


@pytest.mark.integration
def test_measure_event_shape_checks() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        g = await _graph(env.owner, s.ws_a, s.agent_a)
        version: dict[str, object] = {"version_entity_type": "playbook", "version_id": uuid4()}
        system: dict[str, object] = {"actor_kind": "system", "actor_id": None}

        async def event(name: str, **overrides: object) -> UUID:
            return await _insert_event(env.app, s.ws_a, g.measure, name, **overrides)

        # Zulaessig: jedes Event mit seinen Pflichtfeldern und erlaubten Akteuren.
        await event("draft_linked", **version)
        await event("draft_linked", actor_kind="agent", **version)
        await event("activated", **system, **version)
        await event("follow_up_prepared", **system, metrics='{"before": 0.5}')
        await event("follow_up_prepared", actor_kind="agent", metrics="{}")
        await event("reviewed", verdict="effective")
        await event("reviewed", verdict="not_measurable")
        await event("reviewed", verdict="ineffective", note="Faelle kommen wieder.")
        await event("withdrawn", note="Ziel entfaellt.")

        rejected: list[tuple[str, dict[str, object]]] = [
            ("draft_linked", {}),  # ohne Version
            ("draft_linked", {"version_id": uuid4()}),  # Paar unvollstaendig
            ("draft_linked", {"version_entity_type": "tool_policy", "version_id": uuid4()}),
            ("activated", system),  # ohne Version
            ("reviewed", {"verdict": "effective", **version}),  # Version am falschen Event
            ("follow_up_prepared", {**system}),  # ohne metrics
            ("follow_up_prepared", {**system, "metrics": "[]"}),  # kein Objekt
            ("withdrawn", {"note": "n", "metrics": "{}"}),  # metrics am falschen Event
            ("reviewed", {}),  # ohne verdict
            ("reviewed", {"verdict": "great"}),  # verdict ausserhalb der Menge
            ("withdrawn", {"verdict": "effective", "note": "n"}),  # verdict am falschen Event
            ("reviewed", {"verdict": "ineffective"}),  # Begruendung fuer reopened (3.3)
            ("withdrawn", {}),  # ohne Begruendung
            ("withdrawn", {"note": "n" * 2001}),
            ("withdrawn", {"note": ""}),
            ("closed", {}),
            ("withdrawn", {"actor_kind": "robot", "note": "n"}),
            # Partei, nicht Richter (F-W7): nur ein Mensch stuft ein oder zieht zurueck.
            ("reviewed", {"actor_kind": "agent", "verdict": "effective"}),
            ("reviewed", {**system, "verdict": "effective"}),
            ("withdrawn", {"actor_kind": "agent", "note": "Nicht noetig."}),
            # `activated` setzt nur das System (3.6), auch kein Mensch.
            ("activated", {**version}),
            ("activated", {"actor_kind": "agent", **version}),
            # Kennzahlen bereitet nie ein Mensch vor (3.6 „Builder oder System“).
            ("follow_up_prepared", {"metrics": "{}"}),
            # Ein Mensch handelt nie ohne Nutzer-ID.
            ("withdrawn", {"actor_id": None, "note": "n"}),
        ]
        for name, overrides in rejected:
            with pytest.raises(asyncpg.CheckViolationError):
                await event(name, **overrides)

    _with_env(body)


# --- Unveraenderlichkeit -----------------------------------------------------------


@pytest.mark.integration
def test_app_role_can_neither_update_nor_delete() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        g = await _graph(env.app, s.ws_a, s.agent_a)
        denied = [
            ("UPDATE feedback_session SET summary = 'neu' WHERE id = $1", g.session),
            ("UPDATE feedback_session SET follow_up_at = now()::date WHERE id = $1", g.session),
            ("DELETE FROM feedback_session WHERE id = $1", g.session),
            ("UPDATE feedback_session_case SET created_at = now() WHERE session_id = $1",
             g.session),
            ("DELETE FROM feedback_session_case WHERE session_id = $1", g.session),
            ("UPDATE measure SET change_summary = 'neu' WHERE id = $1", g.measure),
            ("DELETE FROM measure WHERE id = $1", g.measure),
            ("UPDATE measure_case SET created_at = now() WHERE measure_id = $1", g.measure),
            ("DELETE FROM measure_case WHERE measure_id = $1", g.measure),
            ("UPDATE measure_event SET note = 'neu' WHERE id = $1", g.event),
            ("DELETE FROM measure_event WHERE id = $1", g.event),
        ]  # fmt: skip
        for sql, row_id in denied:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await env.app.execute(sql, row_id)
        for table in _TABLES:
            count = await env.owner.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608
            assert count == 1, table

    _with_env(body)


# --- RLS ----------------------------------------------------------------------------


@pytest.mark.integration
def test_rls_separates_workspaces_for_all_tables() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        graphs = {
            s.ws_a: await _graph(env.owner, s.ws_a, s.agent_a),
            s.ws_b: await _graph(env.owner, s.ws_b, s.agent_b),
        }
        for ws in (s.ws_a, s.ws_b):
            await env.as_tenant(ws)
            for table in _TABLES:
                # Bewusst OHNE WHERE: nur RLS trennt.
                rows = await env.app.fetch(f"SELECT workspace_id FROM {table}")  # noqa: S608
                assert {r["workspace_id"] for r in rows} == {ws}, table

        await env.as_tenant(uuid4())
        for table in _TABLES:
            assert await env.app.fetch(f"SELECT 1 FROM {table}") == [], table  # noqa: S608

        # WITH CHECK: Schreiben in den fremden Workspace wird abgewiesen.
        await env.as_tenant(s.ws_a)
        g_b = graphs[s.ws_b]
        writes: list[Callable[[], Awaitable[object]]] = [
            lambda: _insert_session(env.app, s.ws_b, s.agent_b),
            lambda: _link_session_case(env.app, s.ws_b, g_b.session, s.agent_b, g_b.case),
            lambda: _insert_measure(env.app, s.ws_b, s.agent_b, g_b.session, g_b.test_case),
            lambda: _link_measure_case(env.app, s.ws_b, g_b.measure, s.agent_b, g_b.case),
            lambda: _insert_event(env.app, s.ws_b, g_b.measure, "withdrawn", note="n"),
        ]
        for write in writes:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await write()

    _with_env(body)


# --- FKs ------------------------------------------------------------------------------


@pytest.mark.integration
def test_cases_test_case_and_correction_belong_to_the_discussed_agent() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        g = await _graph(env.app, s.ws_a, s.agent_a)
        other_case = await _insert_case(env.app, s.ws_a, s.agent_a2)
        other_test_case = await _insert_test_case(env.owner, s.ws_a, s.agent_a2)
        other_session = await _insert_session(env.app, s.ws_a, s.agent_a2)

        # Zulaessig: Korrektur eines Protokolls desselben Agenten.
        await _insert_session(env.app, s.ws_a, s.agent_a, supersedes_id=g.session)

        same_workspace: list[Callable[[], Awaitable[object]]] = [
            # Fall eines anderen Agenten im Protokoll.
            lambda: _link_session_case(env.app, s.ws_a, g.session, s.agent_a, other_case),
            lambda: _link_session_case(env.app, s.ws_a, g.session, s.agent_a2, other_case),
            # Pruefall eines anderen Agenten an der Massnahme.
            lambda: _insert_measure(env.app, s.ws_a, s.agent_a, g.session, other_test_case),
            # Massnahme an einem Protokoll eines anderen Agenten.
            lambda: _insert_measure(env.app, s.ws_a, s.agent_a, other_session, g.test_case),
            # Fall eines anderen Agenten an der Massnahme.
            lambda: _link_measure_case(env.app, s.ws_a, g.measure, s.agent_a, other_case),
            # Korrektur eines Protokolls eines anderen Agenten.
            lambda: _insert_session(env.app, s.ws_a, s.agent_a, supersedes_id=other_session),
            # Nicht existierender Pruefall bzw. Agent.
            lambda: _insert_measure(env.app, s.ws_a, s.agent_a, g.session, uuid4()),
            lambda: _insert_session(env.app, s.ws_a, uuid4()),
            lambda: _insert_event(env.app, s.ws_a, uuid4(), "withdrawn", note="n"),
        ]
        for write in same_workspace:
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await write()
        with pytest.raises(asyncpg.CheckViolationError):  # korrigiert sich nicht selbst
            await env.owner.execute(
                "INSERT INTO feedback_session (id, workspace_id, agent_id, trigger, summary, "
                " follow_up_at, supersedes_id, submitted_by_kind, submitted_by) "
                "VALUES ($1, $2, $3, 'manual', 's', $4, $1, 'agent', $3)",
                uuid4(),
                s.ws_a,
                s.agent_a,
                _FOLLOW_UP,
            )

        # Als Owner (RLS aus): nur die Composite-FKs halten die Workspace-Grenze.
        g_b = await _graph(env.owner, s.ws_b, s.agent_b)
        foreign: list[Callable[[], Awaitable[object]]] = [
            lambda: _insert_session(env.owner, s.ws_a, s.agent_b),
            lambda: _link_session_case(env.owner, s.ws_a, g.session, s.agent_a, g_b.case),
            lambda: _insert_measure(env.owner, s.ws_a, s.agent_a, g.session, g_b.test_case),
            lambda: _insert_measure(env.owner, s.ws_a, s.agent_a, g_b.session, g.test_case),
            lambda: _link_measure_case(env.owner, s.ws_a, g.measure, s.agent_a, g_b.case),
            lambda: _insert_event(env.owner, s.ws_a, g_b.measure, "withdrawn", note="n"),
        ]
        for write in foreign:
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await write()

    _with_env(body)


# --- Loeschen (PM-6) ----------------------------------------------------------------------


@pytest.mark.integration
def test_deleting_a_case_removes_only_the_links() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        g = await _graph(env.app, s.ws_a, s.agent_a)
        kept_case = await _insert_case(env.app, s.ws_a, s.agent_a)
        await _link_session_case(env.app, s.ws_a, g.session, s.agent_a, kept_case)
        await _link_measure_case(env.app, s.ws_a, g.measure, s.agent_a, kept_case)

        # Fall loeschen ist ab editor erlaubt (0100) — die App-Rolle darf das,
        # obwohl sie auf den Verknuepfungen selbst kein DELETE hat.
        assert await env.app.execute("DELETE FROM agent_case WHERE id = $1", g.case) == "DELETE 1"

        async def case_ids(table: str) -> set[UUID]:
            rows = await env.owner.fetch(f"SELECT case_id FROM {table}")  # noqa: S608
            return {r["case_id"] for r in rows}

        assert await case_ids("feedback_session_case") == {kept_case}
        assert await case_ids("measure_case") == {kept_case}
        # Protokoll, Massnahme und Verlauf bleiben.
        for table in ("feedback_session", "measure", "measure_event"):
            count = await env.owner.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608
            assert count == 1, table

        # Auch der letzte Fall geht, die Massnahme bleibt ohne Fall stehen.
        await env.app.execute("DELETE FROM agent_case WHERE id = $1", kept_case)
        assert await case_ids("measure_case") == set()
        assert await env.owner.fetchval("SELECT count(*) FROM measure") == 1

    _with_env(body)


@pytest.mark.integration
def test_agent_and_workspace_purge_remove_everything() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await _graph(env.owner, s.ws_a, s.agent_a)
        kept = await _graph(env.owner, s.ws_a, s.agent_a2)
        await _graph(env.owner, s.ws_b, s.agent_b)

        async def count(table: str, workspace_id: UUID) -> int:
            n: int = await env.owner.fetchval(
                f"SELECT count(*) FROM {table} WHERE workspace_id = $1",  # noqa: S608
                workspace_id,
            )
            return n

        # Agent-Purge: alles dieses Agenten, der andere Agent bleibt.
        await env.owner.execute("DELETE FROM agent WHERE id = $1", s.agent_a)
        for table in _TABLES:
            assert await count(table, s.ws_a) == 1, table
        assert (
            await env.owner.fetchval(
                "SELECT agent_id FROM feedback_session WHERE id = $1", kept.session
            )
            == s.agent_a2
        )

        # Workspace-Purge: alles.
        await env.owner.execute("DELETE FROM workspace WHERE id = $1", s.ws_b)
        for table in _TABLES:
            assert await count(table, s.ws_b) == 0, table

    _with_env(body)


@pytest.mark.integration
def test_deleting_a_corrected_session_keeps_the_correction() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        first = await _insert_session(env.owner, s.ws_a, s.agent_a)
        correction = await _insert_session(env.owner, s.ws_a, s.agent_a, supersedes_id=first)
        await env.owner.execute("DELETE FROM feedback_session WHERE id = $1", first)
        row = await env.owner.fetchrow(
            "SELECT agent_id, supersedes_id FROM feedback_session WHERE id = $1", correction
        )
        assert row is not None
        assert row["agent_id"] == s.agent_a
        assert row["supersedes_id"] is None

    _with_env(body)


@pytest.mark.integration
def test_migration_0103_is_idempotent() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await _graph(env.owner, s.ws_a, s.agent_a)
        sql = (MIGRATIONS_DIR / "0103_feedback_session_measure.sql").read_text(encoding="utf-8")
        async with env.owner.transaction():
            await env.owner.execute(sql)
        for table in _TABLES:
            count = await env.owner.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608
            assert count == 1, table

    _with_env(body)


# --- Modelle ------------------------------------------------------------------------------


def _measure_payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "case_ids": [uuid4()],
        "target": "playbook",
        "entity_id": uuid4(),
        "change_summary": "Frist ins Playbook.",
        "test_case_id": uuid4(),
        "success_criterion": "Pruefall besteht.",
        "counterposition": "Steht schon in der Resource.",
    }
    data.update(overrides)
    return data


def test_models_mirror_shape_rules() -> None:
    MeasureCreate.model_validate(_measure_payload())
    MeasureCreate.model_validate(_measure_payload(target="tool_policy", entity_id=None))
    invalid_measures: list[dict[str, object]] = [
        _measure_payload(case_ids=[]),  # >= 1 Fall (3.6)
        _measure_payload(test_case_id=None),  # Pruefall Pflicht
        _measure_payload(target="model_limit", entity_id=None),
        _measure_payload(target="tool_policy"),
        _measure_payload(entity_id=None),
        _measure_payload(change_summary="c" * 2001),
        _measure_payload(success_criterion="k" * 1001),
        _measure_payload(counterposition="g" * 1001),
    ]
    for payload in invalid_measures:
        with pytest.raises(ValidationError):
            MeasureCreate.model_validate(payload)
    case = uuid4()
    deduped = MeasureCreate.model_validate(_measure_payload(case_ids=[case, case]))
    assert deduped.case_ids == [case]

    session = {
        "agent_id": uuid4(),
        "trigger": "manual",
        "summary": "s",
        "follow_up_at": "2026-11-20",
    }
    SessionCreate.model_validate(session)
    for broken in (
        {"summary": "s" * 4001},
        {"follow_up_at": None},
        {"trigger": "weekly"},
        {"participants": [{"kind": "robot", "id": str(uuid4()), "role": "x"}]},
        {"submitted_by": str(uuid4())},  # setzt der Server
    ):
        with pytest.raises(ValidationError):
            SessionCreate.model_validate({**session, **broken})

    version: dict[str, object] = {"version_entity_type": "playbook", "version_id": uuid4()}
    MeasureEventCreate.model_validate({"event": "draft_linked", **version})
    MeasureEventCreate(event=MeasureEventKind.follow_up_prepared, metrics={})
    invalid_events: list[dict[str, object]] = [
        {"event": "draft_linked"},
        {"event": "withdrawn"},
        {"event": "reviewed"},
        {"event": "reviewed", "verdict": "ineffective"},
        {"event": "withdrawn", "note": "n", **version},
        {"event": "follow_up_prepared"},
        {"event": "withdrawn", "note": "n", "verdict": "effective"},
    ]
    for payload in invalid_events:
        with pytest.raises(ValidationError):
            MeasureEventCreate.model_validate(payload)

    assert measure_state_for(None, None) is MeasureState.agreed
    assert measure_state_for(MeasureEventKind.activated, None) is MeasureState.activated
    assert (
        measure_state_for(MeasureEventKind.reviewed, MeasureVerdict.ineffective)
        is MeasureState.ineffective
    )
    with pytest.raises(ValueError, match="verdict"):
        measure_state_for(MeasureEventKind.reviewed, None)


# --- Repository unter der App-Rolle ---------------------------------------------------------


def _with_repo(
    body: Callable[[PgSessionRepository, asyncpg.Pool, _Env], Awaitable[None]],
) -> None:
    """Repository auf einem `who2be_app`-Pool, Mandant ueber `tenant_scope`."""

    async def outer(env: _Env) -> None:
        pool = await asyncpg.create_pool(
            get_settings().database_url,
            user="who2be_app",
            password=_APP_PASSWORD,
            min_size=1,
            max_size=2,
            init=init_connection,
            setup=apply_tenant_settings,
            server_settings={"search_path": env.seed.schema},
        )
        assert pool is not None
        try:
            async with tenant_scope(env.seed.ws_a, None):
                await body(PgSessionRepository(pool), pool, env)
        finally:
            await pool.close()

    _with_env(outer)


def _protocol(
    agent_id: UUID,
    case_ids: list[UUID],
    measures: list[MeasureCreate],
    **overrides: object,
) -> SessionCreate:
    data: dict[str, object] = {
        "agent_id": agent_id,
        "trigger": SessionTrigger.threshold,
        "participants": [
            {"kind": "human", "id": str(uuid4()), "role": "Owner"},
            {"kind": "builder", "id": str(agent_id), "role": "Moderation"},
        ],
        "case_ids": case_ids,
        "summary": "Frist fehlt im Playbook.",
        "decisions": [{"text": "Playbook vor Resource.", "standard_ref": "ADR-0053 3.6"}],
        "dissent": [{"participant_kind": "agent", "participant_id": str(agent_id), "text": "Nein"}],
        "follow_up_at": _FOLLOW_UP,
        "measures": measures,
    }
    data.update(overrides)
    return SessionCreate.model_validate(data)


def _measure(case_ids: list[UUID], test_case_id: UUID, **overrides: object) -> MeasureCreate:
    return MeasureCreate.model_validate(
        _measure_payload(case_ids=case_ids, test_case_id=test_case_id, **overrides)
    )


@pytest.mark.integration
def test_repository_insert_and_read_session() -> None:
    async def body(repo: PgSessionRepository, pool: asyncpg.Pool, env: _Env) -> None:
        s = env.seed
        case_1 = await _insert_case(env.owner, s.ws_a, s.agent_a)
        case_2 = await _insert_case(env.owner, s.ws_a, s.agent_a)
        test_case = await _insert_test_case(env.owner, s.ws_a, s.agent_a)
        data = _protocol(
            s.agent_a,
            [case_2, case_1],
            [
                _measure([case_1], test_case),
                _measure(
                    [case_1, case_2], test_case, target="tool_policy", entity_id=None,
                    follow_up_at="2026-12-01",
                ),
            ],
        )  # fmt: skip
        async with pool.acquire() as conn, conn.transaction():
            detail = await repo.insert_session(
                conn,
                s.ws_a,
                data,
                submitted_by_kind=SessionSubmitterKind.agent,
                submitted_by=s.agent_a,
            )
        session = detail.session
        assert session.case_ids == [case_2, case_1]  # Reihenfolge wie eingereicht
        assert session.trigger is SessionTrigger.threshold
        assert [p.kind for p in session.participants] == [
            SessionParticipantKind.human,
            SessionParticipantKind.builder,
        ]
        assert session.decisions[0].standard_ref == "ADR-0053 3.6"
        assert session.dissent[0].text == "Nein"
        assert session.follow_up_at == _FOLLOW_UP
        assert [m.case_ids for m in detail.measures] == [[case_1], [case_1, case_2]]
        assert [m.target for m in detail.measures] == [MeasureTarget.playbook,
                                                      MeasureTarget.tool_policy]  # fmt: skip
        assert detail.measures[1].follow_up_at == date(2026, 12, 1)
        assert all(m.state is MeasureState.agreed and m.events == [] for m in detail.measures)
        assert all(m.session_id == session.id for m in detail.measures)

        # Lesen ueber den Pool liefert dasselbe; fremder Workspace und
        # unbekannte ID liefern nichts.
        assert await repo.get_session(s.ws_a, session.id) == detail
        assert await repo.get_session(s.ws_b, session.id) is None
        assert await repo.get_session(s.ws_a, uuid4()) is None
        assert await repo.get_measure(s.ws_a, detail.measures[0].id) == detail.measures[0]
        assert await repo.get_measure(s.ws_a, uuid4()) is None

    _with_repo(body)


@pytest.mark.integration
def test_repository_insert_rolls_back_with_the_callers_transaction() -> None:
    async def body(repo: PgSessionRepository, pool: asyncpg.Pool, env: _Env) -> None:
        s = env.seed
        case = await _insert_case(env.owner, s.ws_a, s.agent_a)
        foreign_case = await _insert_case(env.owner, s.ws_a, s.agent_a2)
        test_case = await _insert_test_case(env.owner, s.ws_a, s.agent_a)
        # Die Massnahme deckt einen Fall eines anderen Agenten ab: der
        # Composite-FK bricht ab, NACHDEM Sitzung und Faelle geschrieben sind.
        data = _protocol(s.agent_a, [case], [_measure([foreign_case], test_case)])
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            async with pool.acquire() as conn, conn.transaction():
                await repo.insert_session(
                    conn,
                    s.ws_a,
                    data,
                    submitted_by_kind=SessionSubmitterKind.human,
                    submitted_by=s.user,
                )
        for table in _TABLES:
            count = await env.owner.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608
            assert count == 0, table

    _with_repo(body)


@pytest.mark.integration
def test_repository_list_filters_and_cursor() -> None:
    async def body(repo: PgSessionRepository, pool: asyncpg.Pool, env: _Env) -> None:
        s = env.seed
        case_a = await _insert_case(env.owner, s.ws_a, s.agent_a)
        case_a2 = await _insert_case(env.owner, s.ws_a, s.agent_a2)

        async def submit(agent_id: UUID, case_ids: list[UUID], **extra: object) -> UUID:
            async with pool.acquire() as conn, conn.transaction():
                detail = await repo.insert_session(
                    conn,
                    s.ws_a,
                    _protocol(agent_id, case_ids, [], **extra),
                    submitted_by_kind=SessionSubmitterKind.human,
                    submitted_by=s.user,
                )
            return detail.session.id

        first = await submit(s.agent_a, [case_a])
        second = await submit(s.agent_a2, [case_a2])
        third = await submit(s.agent_a, [], supersedes_id=first)
        await _graph(env.owner, s.ws_b, s.agent_b)  # fremder Workspace

        def ids(rows: Sequence[SessionRead]) -> list[UUID]:
            return [r.id for r in rows]

        unfiltered = ids(await repo.list_sessions(s.ws_a))
        assert unfiltered == [third, second, first]  # neueste zuerst
        by_agent = ids(await repo.list_sessions(s.ws_a, agent_id=s.agent_a))
        assert by_agent == [third, first]
        by_case = ids(await repo.list_sessions(s.ws_a, case_id=case_a2))
        assert by_case == [second]
        for filtered in (by_agent, by_case):
            assert filtered != unfiltered
        assert await repo.list_sessions(s.ws_a, case_id=uuid4()) == []

        page_1 = await repo.list_sessions(s.ws_a, limit=2)
        last = page_1[-1]
        page_2 = await repo.list_sessions(s.ws_a, limit=2, cursor=(last.created_at, last.id))
        assert ids(page_1) + ids(page_2) == unfiltered

        correction = await repo.get_session(s.ws_a, third)
        assert correction is not None
        assert correction.session.supersedes_id == first

    _with_repo(body)


@pytest.mark.integration
def test_repository_events_state_and_lookups() -> None:
    async def body(repo: PgSessionRepository, pool: asyncpg.Pool, env: _Env) -> None:
        s = env.seed
        case_1 = await _insert_case(env.owner, s.ws_a, s.agent_a)
        case_2 = await _insert_case(env.owner, s.ws_a, s.agent_a)
        test_case = await _insert_test_case(env.owner, s.ws_a, s.agent_a)
        async with pool.acquire() as conn, conn.transaction():
            detail = await repo.insert_session(
                conn,
                s.ws_a,
                _protocol(
                    s.agent_a,
                    [case_1, case_2],
                    [_measure([case_1], test_case), _measure([case_1, case_2], test_case)],
                ),
                submitted_by_kind=SessionSubmitterKind.agent,
                submitted_by=s.agent_a,
            )
        m_1, m_2 = (m.id for m in detail.measures)
        draft_old, draft_new, draft_other = uuid4(), uuid4(), uuid4()

        async def append(
            measure_id: UUID, data: MeasureEventCreate, kind: MeasureActorKind, actor: UUID | None
        ) -> MeasureState:
            event = await repo.append_measure_event(
                s.ws_a, measure_id, data, actor_kind=kind, actor_id=actor
            )
            assert event is not None
            measure = await repo.get_measure(s.ws_a, measure_id)
            assert measure is not None
            assert measure.events[-1] == event
            return measure.state

        def linked(version_id: UUID) -> MeasureEventCreate:
            return MeasureEventCreate(
                event=MeasureEventKind.draft_linked,
                version_entity_type="playbook",
                version_id=version_id,
            )

        agent = MeasureActorKind.agent
        assert await append(m_1, linked(draft_old), agent, s.agent_a) is MeasureState.draft_linked
        assert await append(m_1, linked(draft_new), agent, s.agent_a) is MeasureState.draft_linked
        assert await append(m_2, linked(draft_other), agent, s.agent_a) is (
            MeasureState.draft_linked
        )

        # Je verknuepfter Version (E3): nur der juengste Entwurf gilt (QE4).
        async def for_version(version_id: UUID) -> list[UUID]:
            found = await repo.measures_for_version(s.ws_a, "playbook", version_id)
            return [m.id for m in found]

        assert await for_version(draft_new) == [m_1]
        assert await for_version(draft_old) == []
        assert await for_version(draft_other) == [m_2]
        assert await repo.measures_for_version(s.ws_a, "persona", draft_new) == []
        assert await repo.measures_for_version(s.ws_b, "playbook", draft_new) == []

        # In der Transaktion des Aufrufers (Versionswechsel + activated).
        async with pool.acquire() as conn, conn.transaction():
            found = await repo.measures_for_version(s.ws_a, "playbook", draft_new, conn=conn)
            assert [m.id for m in found] == [m_1]
            await repo.append_measure_event(
                s.ws_a,
                m_1,
                MeasureEventCreate(
                    event=MeasureEventKind.activated,
                    version_entity_type="playbook",
                    version_id=draft_new,
                ),
                actor_kind=MeasureActorKind.system,
                actor_id=None,
                conn=conn,
            )
        measure = await repo.get_measure(s.ws_a, m_1)
        assert measure is not None
        assert measure.state is MeasureState.activated

        metrics = {"pass_rate_before": 0.2, "pass_rate_after": 1.0}
        prepared = MeasureEventCreate(event=MeasureEventKind.follow_up_prepared, metrics=metrics)
        assert await append(m_1, prepared, agent, s.agent_a) is MeasureState.follow_up_prepared
        measure = await repo.get_measure(s.ws_a, m_1)
        assert measure is not None
        assert measure.events[-1].metrics == metrics
        review = MeasureEventCreate(
            event=MeasureEventKind.reviewed, verdict=MeasureVerdict.ineffective, note="Wieder da."
        )
        assert await append(m_1, review, MeasureActorKind.human, s.user) is (
            MeasureState.ineffective
        )
        withdraw = MeasureEventCreate(event=MeasureEventKind.withdrawn, note="Ziel entfaellt.")
        assert await append(m_2, withdraw, MeasureActorKind.human, s.user) is (
            MeasureState.withdrawn
        )

        # Die DB haelt „Partei, nicht Richter“ auch hinter dem Repository.
        with pytest.raises(asyncpg.CheckViolationError):
            await repo.append_measure_event(
                s.ws_a,
                m_2,
                MeasureEventCreate(
                    event=MeasureEventKind.reviewed, verdict=MeasureVerdict.effective
                ),
                actor_kind=MeasureActorKind.agent,
                actor_id=s.agent_a,
            )
        assert (
            await repo.append_measure_event(
                s.ws_a, uuid4(), withdraw, actor_kind=MeasureActorKind.human, actor_id=s.user
            )
            is None
        )

        # Je Fall: case_1 steckt in beiden, case_2 nur in der zweiten Massnahme.
        assert [m.id for m in await repo.measures_for_case(s.ws_a, case_1)] == [m_1, m_2]
        assert [m.id for m in await repo.measures_for_case(s.ws_a, case_2)] == [m_2]
        assert await repo.measures_for_case(s.ws_a, uuid4()) == []
        raw = await env.owner.fetchval(
            "SELECT metrics FROM measure_event WHERE event = 'follow_up_prepared'"
        )
        assert json.loads(raw) == metrics  # als Objekt gespeichert, nicht als String

    _with_repo(body)
