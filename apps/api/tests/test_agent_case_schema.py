"""Integrationstests fuer den Fall (ADR-0053 3.3, Migration 0100, Paket D1a).

Belegt auf der Laufzeitrolle `who2be_app` (NOBYPASSRLS) in einem isolierten
Schema (Muster `test_test_case_schema.py`):

- **CHECKs:** Laengen, `severity`, `reporter_kind`, `signal`, `target`,
  `entity_id IS NULL` genau bei `tool_policy`/`model_limit`, Event-Form
  (Version bei `addressed`, Massnahme bei `in_progress`/`verified`,
  Begruendung bei `reopened`/`dismissed`, kein Agent als Richter).
- **Unveraenderlichkeit:** kein UPDATE am Fall; Events und Schilderungen
  append-only; Zuordnungen loeschbar, aber nicht aenderbar.
- **RLS:** alle vier Tabellen strikt workspace-getrennt.
- **FKs:** `agent_memory.converted_case_id` zeigt auf einen Fall desselben
  Agenten; Schilderung nur vom betroffenen Agenten; alles im selben
  Workspace; Cascade beim Agenten.
- **Repository:** abgeleiteter Status, Filter `agent_id`/`status`/`target`
  (je eine Probe, die sich vom ungefilterten Lauf unterscheidet), Cursor,
  Zaehler, Replace-Semantik mit Events, Loeschen mit Audit-Zeile.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

import asyncpg
import pytest
from pydantic import ValidationError

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.tenancy import apply_tenant_settings, tenant_scope
from who2be_api.repositories.case_repository import CASE_DELETED_AUDIT_ACTION, PgCaseRepository
from who2be_models import (
    CaseActorKind,
    CaseAssignedByKind,
    CaseCreate,
    CaseElementInput,
    CaseEventCreate,
    CaseEventKind,
    CaseRead,
    CaseReporterKind,
    CaseStatementCreate,
    CaseStatus,
    CaseTarget,
)

# Test-only Passwort fuer die App-Rolle (per format() in ALTER ROLE eingesetzt).
_APP_PASSWORD = "agent_case_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret

_TABLES = ("agent_case", "agent_case_event", "agent_case_element", "agent_case_statement")


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
    schema = f"case_{secrets.token_hex(6)}"

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


async def _insert_case(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    agent_id: UUID,
    **overrides: object,
) -> UUID:
    values: dict[str, object] = {
        "reporter_kind": "agent",
        "reporter_user_id": None,
        "reporter_agent_id": agent_id,
        "situation": "Kunde fragt nach der Kuendigungsfrist.",
        "behavior": "Agent nennt keine Frist.",
        "impact": None,
        "expected_behavior": "Nennt die Frist aus dem Playbook.",
        "severity": "medium",
        "signal": None,
        "source_ref": None,
        "source_feedback_id": None,
        "source_memory_id": None,
    }
    values.update(overrides)
    case_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case (workspace_id, agent_id, "
        + ", ".join(values)
        + ") VALUES ($1, $2, "
        + ", ".join(f"${i}" for i in range(3, 3 + len(values)))
        + ") RETURNING id",
        workspace_id,
        agent_id,
        *values.values(),
    )
    return case_id


async def _insert_event(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    case_id: UUID,
    event: str,
    **overrides: object,
) -> UUID:
    values: dict[str, object] = {
        "actor_kind": "human",
        "actor_id": uuid4(),
        "note": None,
        "version_entity_type": None,
        "version_id": None,
        "measure_id": None,
        "element_target": None,
        "element_entity_id": None,
    }
    values.update(overrides)
    event_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case_event (workspace_id, case_id, event, "
        + ", ".join(values)
        + ") VALUES ($1, $2, $3, "
        + ", ".join(f"${i}" for i in range(4, 4 + len(values)))
        + ") RETURNING id",
        workspace_id,
        case_id,
        event,
        *values.values(),
    )
    return event_id


async def _insert_element(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    case_id: UUID,
    target: str,
    entity_id: UUID | None,
) -> UUID:
    element_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case_element "
        "(workspace_id, case_id, target, entity_id, assigned_by_kind, assigned_by) "
        "VALUES ($1, $2, $3, $4, 'human', $5) RETURNING id",
        workspace_id,
        case_id,
        target,
        entity_id,
        uuid4(),
    )
    return element_id


async def _insert_statement(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    case_id: UUID,
    agent_id: UUID,
    *,
    conflict: str = "Kein Widerspruch.",
) -> UUID:
    statement_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case_statement "
        "(workspace_id, case_id, agent_id, followed_instruction, missing_information, conflict) "
        "VALUES ($1, $2, $3, 'Playbook Kuendigung', 'Die Frist', $4) RETURNING id",
        workspace_id,
        case_id,
        agent_id,
        conflict,
    )
    return statement_id


async def _insert_lesson(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    agent_id: UUID,
    *,
    converted_case_id: UUID | None = None,
    kind: str = "lesson",
) -> UUID:
    memory_id: UUID = await conn.fetchval(
        "INSERT INTO agent_memory "
        "(workspace_id, agent_id, status, fact, kind, scope, created_by_agent_id, "
        " converted_case_id, origin, source) "
        "VALUES ($1, $2, $3, $4, $5, 'agent', $2, $6, 'inferred', 'agent') RETURNING id",
        workspace_id,
        agent_id,
        "converted" if converted_case_id is not None else "pending",
        f"Lektion {secrets.token_hex(3)}",
        kind,
        converted_case_id,
    )
    return memory_id


# --- CHECKs am Fall ------------------------------------------------------------


@pytest.mark.integration
def test_case_checks_lengths_and_value_sets() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        # Zulaessig: Obergrenzen genau getroffen, alle Werte der Mengen.
        await _insert_case(
            env.app,
            s.ws_a,
            s.agent_a,
            situation="s" * 4000,
            behavior="b" * 4000,
            impact="i" * 2000,
            expected_behavior="e" * 2000,
            source_ref="r" * 500,
        )
        for severity in ("low", "medium", "high"):
            await _insert_case(env.app, s.ws_a, s.agent_a, severity=severity)
        for signal in ("helpful", "outdated", "incorrect", "unclear"):
            await _insert_case(env.app, s.ws_a, s.agent_a, signal=signal)
        for kind in ("agent", "builder", "pattern"):
            await _insert_case(env.app, s.ws_a, s.agent_a, reporter_kind=kind)
        await _insert_case(
            env.app, s.ws_a, s.agent_a, reporter_kind="human", reporter_user_id=s.user
        )

        rejected: list[dict[str, object]] = [
            {"situation": "s" * 4001},
            {"situation": ""},
            {"behavior": "b" * 4001},
            {"behavior": ""},
            {"impact": "i" * 2001},
            {"impact": ""},
            {"expected_behavior": "e" * 2001},
            {"expected_behavior": ""},
            {"source_ref": "r" * 501},
            {"severity": "critical"},
            {"signal": "angry"},
            {"reporter_kind": "anonymous"},
            # Ein Mensch meldet nie ohne Nutzer-ID (F2: kein anonymer Kanal).
            {"reporter_kind": "human", "reporter_user_id": None},
        ]
        for overrides in rejected:
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_case(env.app, s.ws_a, s.agent_a, **overrides)
        for column in ("situation", "behavior", "expected_behavior"):
            with pytest.raises(asyncpg.NotNullViolationError):
                await _insert_case(env.app, s.ws_a, s.agent_a, **{column: None})
        # agent_id ist Pflicht (F-W1).
        with pytest.raises(asyncpg.NotNullViolationError):
            await env.app.execute(
                "INSERT INTO agent_case (workspace_id, reporter_kind, situation, behavior, "
                " expected_behavior) VALUES ($1, 'pattern', 's', 'b', 'e')",
                s.ws_a,
            )

    _with_env(body)


# --- CHECKs an Zuordnung und Events -------------------------------------------


@pytest.mark.integration
def test_element_entity_null_exactly_for_agent_bound_targets() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)
        with_entity = (
            "persona",
            "playbook",
            "resource",
            "external_tool",
            "system_prompt_template",
            "memory",
        )
        for target in with_entity:
            await _insert_element(env.app, s.ws_a, case, target, uuid4())
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_element(env.app, s.ws_a, case, target, None)
        for target in ("tool_policy", "model_limit"):
            await _insert_element(env.app, s.ws_a, case, target, None)
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_element(env.app, s.ws_a, case, target, uuid4())
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_element(env.app, s.ws_a, case, "agent", uuid4())
        # Jedes Ziel hoechstens einmal je Fall, auch ohne entity_id.
        with pytest.raises(asyncpg.UniqueViolationError):
            await _insert_element(env.app, s.ws_a, case, "model_limit", None)

    _with_env(body)


@pytest.mark.integration
def test_event_shape_checks() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)
        version = {"version_entity_type": "playbook", "version_id": uuid4()}

        # Zulaessig: jedes Event mit seinen Pflichtfeldern.
        await _insert_event(env.app, s.ws_a, case, "reported", actor_kind="agent")
        await _insert_event(env.app, s.ws_a, case, "triaged")
        await _insert_event(env.app, s.ws_a, case, "in_progress", measure_id=uuid4())
        await _insert_event(env.app, s.ws_a, case, "addressed", **version)
        await _insert_event(
            env.app, s.ws_a, case, "addressed", actor_kind="system", actor_id=None, **version
        )
        await _insert_event(env.app, s.ws_a, case, "verified", measure_id=uuid4())
        await _insert_event(env.app, s.ws_a, case, "reopened", note="Wirkt nicht.")
        await _insert_event(env.app, s.ws_a, case, "dismissed", note="Modellgrenze.")
        await _insert_event(
            env.app, s.ws_a, case, "element_assigned", element_target="playbook",
            element_entity_id=uuid4(),
        )  # fmt: skip
        await _insert_event(
            env.app, s.ws_a, case, "element_unassigned", element_target="model_limit"
        )

        rejected: list[tuple[str, dict[str, object]]] = [
            ("addressed", {}),  # ohne Version (F-W6)
            ("addressed", {"version_id": uuid4()}),  # Paar unvollstaendig
            ("in_progress", {}),  # ohne Massnahme
            ("verified", {}),  # ohne Massnahme
            ("reopened", {}),  # ohne Begruendung
            ("dismissed", {}),  # ohne Begruendung
            ("element_assigned", {}),  # ohne Element
            ("triaged", {"element_target": "playbook"}),  # Element am Status-Event
            ("element_assigned", {"element_target": "tool_policy", "element_entity_id": uuid4()}),
            ("triaged", {"actor_kind": "human", "actor_id": None}),  # Mensch ohne ID
            ("triaged", {"note": "n" * 2001}),
            ("triaged", {"note": ""}),
            ("closed", {}),
            ("triaged", {"actor_kind": "robot"}),
            # Partei, nicht Richter (F-W7): ein Agent setzt nie diese drei.
            ("addressed", {"actor_kind": "agent", **version}),
            ("verified", {"actor_kind": "agent", "measure_id": uuid4()}),
            ("dismissed", {"actor_kind": "agent", "note": "Nicht mein Fehler."}),
        ]
        for event, overrides in rejected:
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_event(env.app, s.ws_a, case, event, **overrides)

    _with_env(body)


@pytest.mark.integration
def test_statement_length_checks() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)
        await _insert_statement(env.app, s.ws_a, case, s.agent_a, conflict="c" * 2000)
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_statement(env.app, s.ws_a, case, s.agent_a, conflict="c" * 2001)

    _with_env(body)


# --- Unveraenderlichkeit -------------------------------------------------------


@pytest.mark.integration
def test_case_content_is_immutable_events_and_statements_append_only() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)
        event = await _insert_event(env.app, s.ws_a, case, "reported")
        statement = await _insert_statement(env.app, s.ws_a, case, s.agent_a)
        element = await _insert_element(env.app, s.ws_a, case, "playbook", uuid4())

        denied = [
            ("UPDATE agent_case SET situation = 'neu' WHERE id = $1", case),
            ("UPDATE agent_case SET severity = 'high' WHERE id = $1", case),
            ("UPDATE agent_case_event SET event = 'dismissed' WHERE id = $1", event),
            ("DELETE FROM agent_case_event WHERE id = $1", event),
            ("UPDATE agent_case_statement SET conflict = 'neu' WHERE id = $1", statement),
            ("DELETE FROM agent_case_statement WHERE id = $1", statement),
            ("UPDATE agent_case_element SET entity_id = gen_random_uuid() WHERE id = $1", element),
        ]
        for sql, row_id in denied:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await env.app.execute(sql, row_id)

        # Erlaubt: Zuordnung loeschen (3.3) und Fall loeschen (Q6).
        await env.app.execute("DELETE FROM agent_case_element WHERE id = $1", element)
        await env.app.execute("DELETE FROM agent_case WHERE id = $1", case)
        # Der Verlauf geht mit (Hard-Delete samt Verlauf).
        for table in _TABLES:
            count = await env.owner.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608
            assert count == 0, table

    _with_env(body)


# --- RLS -------------------------------------------------------------------------


@pytest.mark.integration
def test_rls_separates_workspaces_for_all_tables() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        cases: dict[UUID, UUID] = {}
        for ws, agent in ((s.ws_a, s.agent_a), (s.ws_b, s.agent_b)):
            case = await _insert_case(env.owner, ws, agent)
            await _insert_event(env.owner, ws, case, "reported")
            await _insert_element(env.owner, ws, case, "model_limit", None)
            await _insert_statement(env.owner, ws, case, agent)
            cases[ws] = case

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
        case_b = cases[s.ws_b]
        writes: list[Callable[[], Awaitable[object]]] = [
            lambda: _insert_case(env.app, s.ws_b, s.agent_b),
            lambda: _insert_event(env.app, s.ws_b, case_b, "triaged"),
            lambda: _insert_element(env.app, s.ws_b, case_b, "model_limit", None),
            lambda: _insert_statement(env.app, s.ws_b, case_b, s.agent_b),
        ]
        for write in writes:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await write()
        # Loeschen trifft fremde Zeilen nicht.
        assert await env.app.execute("DELETE FROM agent_case WHERE id = $1", case_b) == "DELETE 0"

    _with_env(body)


# --- FKs -------------------------------------------------------------------------


@pytest.mark.integration
def test_converted_case_id_fk() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)
        other_agent_case = await _insert_case(env.app, s.ws_a, s.agent_a2)

        # Zulaessig: Lernvorschlag desselben Agenten wird zu diesem Fall.
        lesson = await _insert_lesson(env.app, s.ws_a, s.agent_a, converted_case_id=case)

        with pytest.raises(asyncpg.ForeignKeyViolationError):  # Fall existiert nicht
            await _insert_lesson(env.app, s.ws_a, s.agent_a, converted_case_id=uuid4())
        with pytest.raises(asyncpg.ForeignKeyViolationError):  # Fall eines anderen Agenten
            await _insert_lesson(env.app, s.ws_a, s.agent_a, converted_case_id=other_agent_case)
        with pytest.raises(asyncpg.CheckViolationError):  # nur fuer lesson (3.1)
            await env.app.execute(
                "INSERT INTO agent_memory (workspace_id, agent_id, status, fact, kind, scope, "
                " converted_case_id, origin, source) "
                "VALUES ($1, $2, 'converted', 'n', 'agent_note', 'agent', $3, 'inferred', "
                " 'agent')",
                s.ws_a,
                s.agent_a,
                case,
            )
        # Fremder Workspace, als Owner (RLS aus): nur der Composite-FK haelt.
        case_b = await _insert_case(env.owner, s.ws_b, s.agent_b)
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await _insert_lesson(env.owner, s.ws_a, s.agent_a, converted_case_id=case_b)

        # Ein Fall, aus dem ein Lernvorschlag wurde, laesst sich nicht wegloeschen.
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await env.app.execute("DELETE FROM agent_case WHERE id = $1", case)
        # Faellt der Agent, fallen Fall und Lernvorschlag gemeinsam.
        await env.owner.execute("DELETE FROM agent WHERE id = $1", s.agent_a)
        assert await env.owner.fetchval("SELECT count(*) FROM agent_case WHERE id = $1", case) == 0
        assert (
            await env.owner.fetchval("SELECT count(*) FROM agent_memory WHERE id = $1", lesson) == 0
        )

    _with_env(body)


@pytest.mark.integration
def test_statement_only_from_subject_and_references_stay_in_workspace() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)
        # Nur der betroffene Agent schildert (3.3).
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await _insert_statement(env.app, s.ws_a, case, s.agent_a2)

        # Als Owner (RLS aus): nur die Composite-FKs halten die Grenze.
        case_b = await _insert_case(env.owner, s.ws_b, s.agent_b)
        feedback_b = await env.owner.fetchval(
            "INSERT INTO agent_feedback (workspace_id, entity_type, entity_id, signal) "
            "VALUES ($1, 'playbook', gen_random_uuid(), 'unclear') RETURNING id",
            s.ws_b,
        )
        foreign: list[Callable[[], Awaitable[object]]] = [
            lambda: _insert_case(env.owner, s.ws_a, s.agent_b),  # fremder Agent
            lambda: _insert_case(env.owner, s.ws_a, s.agent_a, reporter_agent_id=s.agent_b),
            lambda: _insert_case(env.owner, s.ws_a, s.agent_a, source_feedback_id=feedback_b),
            lambda: _insert_event(env.owner, s.ws_a, case_b, "triaged"),
            lambda: _insert_element(env.owner, s.ws_a, case_b, "model_limit", None),
            lambda: _insert_statement(env.owner, s.ws_a, case_b, s.agent_b),
        ]
        for write in foreign:
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await write()

    _with_env(body)


@pytest.mark.integration
def test_sources_are_nulled_and_cases_follow_agent() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        feedback = await env.owner.fetchval(
            "INSERT INTO agent_feedback (workspace_id, entity_type, entity_id, signal) "
            "VALUES ($1, 'playbook', gen_random_uuid(), 'unclear') RETURNING id",
            s.ws_a,
        )
        lesson = await _insert_lesson(env.owner, s.ws_a, s.agent_a)
        case = await _insert_case(
            env.owner,
            s.ws_a,
            s.agent_a,
            reporter_agent_id=s.agent_a2,
            source_feedback_id=feedback,
            source_memory_id=lesson,
        )
        # `source_memory_id` ist ein weicher Verweis (kein FK, sonst Zyklus mit
        # converted_case_id im Org-Transfer): er ueberlebt das Loeschen der Quelle.
        other_lesson = await _insert_lesson(env.owner, s.ws_a, s.agent_a2)
        await _insert_case(env.owner, s.ws_a, s.agent_a, source_memory_id=other_lesson)

        # Quellen weg -> FK-Verweise werden genullt, der Fall bleibt.
        await env.owner.execute("DELETE FROM agent_feedback WHERE id = $1", feedback)
        await env.owner.execute("DELETE FROM agent_memory WHERE id = $1", lesson)
        await env.owner.execute("DELETE FROM agent WHERE id = $1", s.agent_a2)
        row = await env.owner.fetchrow(
            "SELECT agent_id, reporter_agent_id, source_feedback_id, source_memory_id "
            "FROM agent_case WHERE id = $1",
            case,
        )
        assert row is not None
        assert row["agent_id"] == s.agent_a
        assert row["reporter_agent_id"] is None
        assert row["source_feedback_id"] is None
        assert row["source_memory_id"] == lesson

        # Betroffener Agent weg -> Fall geht mit (ADR 3.3: ON DELETE CASCADE).
        await env.owner.execute("DELETE FROM agent WHERE id = $1", s.agent_a)
        assert await env.owner.fetchval("SELECT count(*) FROM agent_case") == 0

    _with_env(body)


# --- Modelle -----------------------------------------------------------------------


def test_models_mirror_shape_rules() -> None:
    CaseElementInput(target=CaseTarget.model_limit)
    CaseElementInput(target=CaseTarget.playbook, entity_id=uuid4())
    with pytest.raises(ValidationError):
        CaseElementInput(target=CaseTarget.tool_policy, entity_id=uuid4())
    with pytest.raises(ValidationError):
        CaseElementInput(target=CaseTarget.persona)

    CaseEventCreate(event=CaseEventKind.triaged)
    invalid: list[dict[str, object]] = [
        {"event": "addressed"},
        {"event": "in_progress"},
        {"event": "dismissed"},
        {"event": "triaged", "version_id": uuid4()},
        {"event": "element_assigned"},
    ]
    for payload in invalid:
        with pytest.raises(ValidationError):
            CaseEventCreate.model_validate(payload)
    with pytest.raises(ValidationError):  # Melden ohne Zuordnung (Q2)
        CaseCreate.model_validate(
            {
                "agent_id": uuid4(),
                "situation": "s",
                "behavior": "b",
                "expected_behavior": "e",
                "elements": [],
            }
        )


# --- Repository unter der App-Rolle ----------------------------------------------


def _with_repo(body: Callable[[PgCaseRepository, _Env], Awaitable[None]]) -> None:
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
                await body(PgCaseRepository(pool), env)
        finally:
            await pool.close()

    _with_env(outer)


def _report(agent_id: UUID, **overrides: object) -> CaseCreate:
    data: dict[str, object] = {
        "agent_id": agent_id,
        "situation": "Kunde fragt nach der Frist.",
        "behavior": "Keine Frist genannt.",
        "expected_behavior": "Nennt die Frist.",
    }
    data.update(overrides)
    return CaseCreate.model_validate(data)


async def _human_report(repo: PgCaseRepository, seed: _Seed, agent_id: UUID) -> UUID:
    case = await repo.create_case(
        seed.ws_a,
        _report(agent_id),
        reporter_kind=CaseReporterKind.human,
        reporter_user_id=seed.user,
        reporter_agent_id=None,
    )
    return case.id


@pytest.mark.integration
def test_repository_create_derives_status_and_detail() -> None:
    async def body(repo: PgCaseRepository, env: _Env) -> None:
        s = env.seed
        case = await repo.create_case(
            s.ws_a,
            _report(s.agent_a, severity="high", signal="incorrect", impact="Kunde verunsichert."),
            reporter_kind=CaseReporterKind.agent,
            reporter_user_id=None,
            reporter_agent_id=s.agent_a2,
        )
        assert case.status is CaseStatus.open
        assert case.reporter_agent_id == s.agent_a2
        assert await repo.get_case(s.ws_a, case.id) == case
        assert await repo.get_case(s.ws_b, case.id) is None
        assert await repo.get_case(s.ws_a, uuid4()) is None

        # Status folgt dem juengsten Status-Event; Element/Schilderung aendern ihn nicht.
        await repo.append_event(
            s.ws_a,
            case.id,
            CaseEventCreate(event=CaseEventKind.triaged),
            actor_kind=CaseActorKind.human,
            actor_id=s.user,
        )
        await repo.set_elements(
            s.ws_a,
            case.id,
            [CaseElementInput(target=CaseTarget.model_limit)],
            assigned_by_kind=CaseAssignedByKind.human,
            assigned_by=s.user,
        )
        await repo.add_statement(
            s.ws_a,
            case.id,
            s.agent_a,
            CaseStatementCreate(
                followed_instruction="Playbook", missing_information="Frist", conflict="Keiner"
            ),
        )
        reloaded = await repo.get_case(s.ws_a, case.id)
        assert reloaded is not None
        assert reloaded.status is CaseStatus.triaged

        await repo.append_event(
            s.ws_a,
            case.id,
            CaseEventCreate(event=CaseEventKind.dismissed, note="Modellgrenze."),
            actor_kind=CaseActorKind.human,
            actor_id=s.user,
        )
        detail = await repo.get_detail(s.ws_a, case.id)
        assert detail is not None
        assert detail.case.status is CaseStatus.dismissed
        assert [e.event for e in detail.events] == [
            CaseEventKind.reported,
            CaseEventKind.triaged,
            CaseEventKind.element_assigned,
            CaseEventKind.statement,
            CaseEventKind.dismissed,
        ]
        assert detail.events[0].actor_kind is CaseActorKind.agent
        assert detail.events[0].actor_id == s.agent_a2
        assert [e.target for e in detail.elements] == [CaseTarget.model_limit]
        assert [st.agent_id for st in detail.statements] == [s.agent_a]
        assert await repo.get_detail(s.ws_a, uuid4()) is None

        # Unbekannter Fall: kein Schreiben, None.
        missing = uuid4()
        assert (
            await repo.append_event(
                s.ws_a,
                missing,
                CaseEventCreate(event=CaseEventKind.triaged),
                actor_kind=CaseActorKind.human,
                actor_id=s.user,
            )
            is None
        )
        assert (
            await repo.set_elements(
                s.ws_a, missing, [], assigned_by_kind=CaseAssignedByKind.human, assigned_by=s.user
            )
            is None
        )

    _with_repo(body)


@pytest.mark.integration
def test_repository_list_filters_each_narrow_the_result() -> None:
    async def body(repo: PgCaseRepository, env: _Env) -> None:
        s = env.seed
        first = await _human_report(repo, s, s.agent_a)
        second = await _human_report(repo, s, s.agent_a2)
        third = await _human_report(repo, s, s.agent_a)
        await repo.append_event(
            s.ws_a,
            second,
            CaseEventCreate(event=CaseEventKind.triaged),
            actor_kind=CaseActorKind.human,
            actor_id=s.user,
        )
        await repo.set_elements(
            s.ws_a,
            third,
            [CaseElementInput(target=CaseTarget.playbook, entity_id=uuid4())],
            assigned_by_kind=CaseAssignedByKind.human,
            assigned_by=s.user,
        )
        # Fremder Melder: nur ueber den Agenten-Token, kein Nutzer.
        agent_reported = await repo.create_case(
            s.ws_a,
            _report(s.agent_a2),
            reporter_kind=CaseReporterKind.agent,
            reporter_user_id=None,
            reporter_agent_id=s.agent_a2,
        )

        def ids(cases: Sequence[CaseRead]) -> list[UUID]:
            return [c.id for c in cases]

        unfiltered = ids(await repo.list_cases(s.ws_a))
        assert unfiltered == [agent_reported.id, third, second, first]  # neueste zuerst

        by_agent = ids(await repo.list_cases(s.ws_a, agent_id=s.agent_a))
        assert by_agent == [third, first]
        by_status = ids(await repo.list_cases(s.ws_a, status=CaseStatus.triaged))
        assert by_status == [second]
        by_open = ids(await repo.list_cases(s.ws_a, status=CaseStatus.open))
        assert by_open == [agent_reported.id, third, first]
        by_target = ids(await repo.list_cases(s.ws_a, target=CaseTarget.playbook))
        assert by_target == [third]
        by_reporter = ids(await repo.list_cases(s.ws_a, reporter_user_id=s.user))
        assert by_reporter == [third, second, first]
        for filtered in (by_agent, by_status, by_target, by_reporter):
            assert filtered != unfiltered
        assert await repo.list_cases(s.ws_a, target=CaseTarget.memory) == []

        # Cursor: zwei Seiten ergeben die ungefilterte Liste ohne Luecke.
        page_1 = await repo.list_cases(s.ws_a, limit=2)
        last = page_1[-1]
        page_2 = await repo.list_cases(s.ws_a, limit=2, cursor=(last.created_at, last.id))
        assert ids(page_1) + ids(page_2) == unfiltered

        counts = await repo.count_by_status(s.ws_a)
        assert counts[CaseStatus.open] == 3
        assert counts[CaseStatus.triaged] == 1
        assert counts[CaseStatus.dismissed] == 0
        assert set(counts) == set(CaseStatus)
        agent_counts = await repo.count_by_status(s.ws_a, agent_id=s.agent_a2)
        assert agent_counts[CaseStatus.open] == 1
        assert agent_counts[CaseStatus.triaged] == 1
        own = await repo.count_by_status(s.ws_a, reporter_user_id=s.user)
        assert own[CaseStatus.open] == 2

    _with_repo(body)


@pytest.mark.integration
def test_repository_set_elements_replace_semantics_with_events() -> None:
    async def body(repo: PgCaseRepository, env: _Env) -> None:
        s = env.seed
        case = await _human_report(repo, s, s.agent_a)
        playbook = CaseElementInput(target=CaseTarget.playbook, entity_id=uuid4())
        policy = CaseElementInput(target=CaseTarget.tool_policy)
        limit = CaseElementInput(target=CaseTarget.model_limit)

        async def put(elements: list[CaseElementInput]) -> list[tuple[CaseTarget, UUID | None]]:
            result = await repo.set_elements(
                s.ws_a,
                case,
                elements,
                assigned_by_kind=CaseAssignedByKind.human,
                assigned_by=s.user,
            )
            assert result is not None
            return [(e.target, e.entity_id) for e in result]

        assert await put([playbook, policy, playbook]) == [
            (CaseTarget.playbook, playbook.entity_id),
            (CaseTarget.tool_policy, None),
        ]
        # Austausch: playbook bleibt, tool_policy geht, model_limit kommt.
        assert await put([limit, playbook]) == [
            (CaseTarget.playbook, playbook.entity_id),
            (CaseTarget.model_limit, None),
        ]
        assert await put([]) == []

        detail = await repo.get_detail(s.ws_a, case)
        assert detail is not None
        trail = [
            (e.event, e.element_target)
            for e in detail.events
            if e.event is not CaseEventKind.reported
        ]
        assert trail == [
            (CaseEventKind.element_assigned, CaseTarget.playbook),
            (CaseEventKind.element_assigned, CaseTarget.tool_policy),
            (CaseEventKind.element_unassigned, CaseTarget.tool_policy),
            (CaseEventKind.element_assigned, CaseTarget.model_limit),
            (CaseEventKind.element_unassigned, CaseTarget.playbook),
            (CaseEventKind.element_unassigned, CaseTarget.model_limit),
        ]
        assert all(e.actor_id == s.user for e in detail.events)

    _with_repo(body)


@pytest.mark.integration
def test_repository_statement_and_delete() -> None:
    async def body(repo: PgCaseRepository, env: _Env) -> None:
        s = env.seed
        case = await _human_report(repo, s, s.agent_a)
        statement = CaseStatementCreate(
            followed_instruction="Playbook", missing_information="Frist", conflict="Keiner"
        )
        first = await repo.add_statement(s.ws_a, case, s.agent_a, statement)
        second = await repo.add_statement(
            s.ws_a, case, s.agent_a, statement.model_copy(update={"conflict": "Zwei Regeln"})
        )
        assert first is not None
        assert second is not None
        detail = await repo.get_detail(s.ws_a, case)
        assert detail is not None
        # Neueste zuerst; die alte bleibt.
        assert [st.id for st in detail.statements] == [second.id, first.id]
        with pytest.raises(asyncpg.ForeignKeyViolationError):  # nicht der betroffene Agent
            await repo.add_statement(s.ws_a, case, s.agent_a2, statement)
        assert await repo.add_statement(s.ws_a, uuid4(), s.agent_a, statement) is None

        assert await repo.delete_case(s.ws_a, case, s.user) is True
        assert await repo.get_case(s.ws_a, case) is None
        assert await repo.delete_case(s.ws_a, case, s.user) is False
        audit = await env.owner.fetch(
            "SELECT actor_id, action, target, detail FROM audit_log WHERE action = $1",
            CASE_DELETED_AUDIT_ACTION,
        )
        assert [(r["actor_id"], r["target"]) for r in audit] == [(s.user, str(case))]
        assert audit[0]["detail"] in ("{}", {})  # inhaltsfrei
        for table in _TABLES:
            count = await env.owner.fetchval(f"SELECT count(*) FROM {table}")  # noqa: S608
            assert count == 0, table

    _with_repo(body)
