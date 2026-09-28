"""Integrationstests fuer Pruefall + Prueflauf (ADR-0053 3.2, Migration 0089, Paket B1).

Belegt auf der Laufzeitrolle `who2be_app` (NOBYPASSRLS) in einem isolierten
Schema (Muster `test_audit_append_only.py`/`test_rls_isolation.py`):

- **RLS:** beide Tabellen sind strikt workspace-getrennt — Lesen ohne
  `WHERE` zeigt nur den eigenen Mandanten, Schreiben in einen fremden wird
  per `WITH CHECK` abgewiesen.
- **CHECKs:** `runs_total >= 1`, `0 <= runs_passed <= runs_total`, `pass`
  nur bei n/n; `human_rating` nur mit `reported_by_user_id`; Element-Paar
  und `check_pattern` passend zu `check_kind`.
- **Unveraenderlichkeit:** am Pruefall ist NUR `status` aenderbar, kein
  DELETE; `test_run` ist append-only.
- **Gleicher Workspace:** Agent, Vorgaenger und Pruefall eines Laufs muessen
  aus demselben Workspace stammen (Composite-FKs); `supersedes_id` wird beim
  Loeschen des Vorgaengers genullt.
- **Repository:** laeuft vollstaendig unter `who2be_app` + `tenant_scope`
  (also unter RLS und den engen Grants) — inklusive Korrektur in einer
  Transaktion, Vereinigung nach 3.2.1 und „letztes Ergebnis zaehlt".
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.tenancy import apply_tenant_settings, tenant_scope
from who2be_api.repositories.test_case_repository import PgTestCaseRepository
from who2be_models import (
    TestAttestation,
    TestCaseCreate,
    TestCaseCreatedByKind,
    TestCaseStatus,
    TestCheckKind,
    TestRunCreate,
    TestRunRead,
    TestVerdict,
)

# Test-only Passwort fuer die App-Rolle (kein Injection-Vektor; per format()
# in ALTER ROLE eingesetzt).
_APP_PASSWORD = "test_case_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret


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
    schema = f"tc_{secrets.token_hex(6)}"

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
    *,
    title: str = "Kuendigung",
    entity: tuple[str, UUID] | None = None,
    check_kind: str = "human_rule",
    check_pattern: str | None = None,
    supersedes_id: UUID | None = None,
) -> UUID:
    case_id: UUID = await conn.fetchval(
        "INSERT INTO test_case "
        "(workspace_id, agent_id, entity_type, entity_id, title, input, expected_behavior, "
        " check_kind, check_pattern, supersedes_id, created_by_kind, created_by) "
        "VALUES ($1, $2, $3, $4, $5, 'Ich will kuendigen.', 'Nennt die Frist.', "
        "        $6, $7, $8, 'human', $9) RETURNING id",
        workspace_id,
        agent_id,
        entity[0] if entity else None,
        entity[1] if entity else None,
        title,
        check_kind,
        check_pattern,
        supersedes_id,
        uuid4(),
    )
    return case_id


async def _insert_run(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    case_id: UUID,
    *,
    runs_total: int = 3,
    runs_passed: int = 3,
    verdict: str = "pass",
    attestation: str = "client_self_report",
    reported_by_user_id: UUID | None = None,
    version_id: UUID | None = None,
) -> UUID:
    run_id: UUID = await conn.fetchval(
        "INSERT INTO test_run "
        "(workspace_id, test_case_id, subject_entity_type, subject_version_id, "
        " runs_total, runs_passed, verdict, attestation, reported_by_user_id) "
        "VALUES ($1, $2, 'playbook', $3, $4, $5, $6, $7, $8) RETURNING id",
        workspace_id,
        case_id,
        version_id or uuid4(),
        runs_total,
        runs_passed,
        verdict,
        attestation,
        reported_by_user_id,
    )
    return run_id


# --- RLS ---------------------------------------------------------------------


@pytest.mark.integration
def test_rls_separates_workspaces_for_both_tables() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        # Je Workspace ein Pruefall + ein Lauf, als Owner (RLS-Bypass) gesetzt.
        case_a = await _insert_case(env.owner, s.ws_a, s.agent_a)
        case_b = await _insert_case(env.owner, s.ws_b, s.agent_b)
        await _insert_run(env.owner, s.ws_a, case_a)
        await _insert_run(env.owner, s.ws_b, case_b)

        for ws in (s.ws_a, s.ws_b):
            await env.as_tenant(ws)
            for table in ("test_case", "test_run"):
                # Bewusst OHNE WHERE: nur RLS trennt.
                rows = await env.app.fetch(f"SELECT workspace_id FROM {table}")  # noqa: S608
                assert {r["workspace_id"] for r in rows} == {ws}, table

        # Fremder Mandant sieht nichts.
        await env.as_tenant(uuid4())
        assert await env.app.fetch("SELECT id FROM test_case") == []
        assert await env.app.fetch("SELECT id FROM test_run") == []

        # WITH CHECK: Schreiben in den fremden Workspace wird abgewiesen.
        await env.as_tenant(s.ws_a)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await _insert_case(env.app, s.ws_b, s.agent_b)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await _insert_run(env.app, s.ws_b, case_b)

    _with_env(body)


# --- CHECKs am Prueflauf -----------------------------------------------------


@pytest.mark.integration
def test_run_checks_runs_and_verdict() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)

        # Zulaessig: n/n pass, teilweise fail, error mit 0/n.
        await _insert_run(env.app, s.ws_a, case, runs_total=3, runs_passed=3, verdict="pass")
        await _insert_run(env.app, s.ws_a, case, runs_total=3, runs_passed=2, verdict="fail")
        await _insert_run(env.app, s.ws_a, case, runs_total=1, runs_passed=0, verdict="error")

        rejected = [
            {"runs_total": 3, "runs_passed": 2, "verdict": "pass"},  # pass ohne n/n
            {"runs_total": 0, "runs_passed": 0, "verdict": "fail"},  # kein Lauf
            {"runs_total": 2, "runs_passed": 3, "verdict": "fail"},  # mehr bestanden als gelaufen
            {"runs_total": 2, "runs_passed": -1, "verdict": "fail"},  # negativ
        ]
        for kwargs in rejected:
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_run(env.app, s.ws_a, case, **kwargs)  # type: ignore[arg-type]
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_run(env.app, s.ws_a, case, verdict="flaky")

    _with_env(body)


@pytest.mark.integration
def test_run_checks_attestation() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)

        await _insert_run(env.app, s.ws_a, case, attestation="client_self_report")
        await _insert_run(
            env.app, s.ws_a, case, attestation="human_rating", reported_by_user_id=s.user
        )
        # Menschliche Bewertung ohne Menschen.
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_run(env.app, s.ws_a, case, attestation="human_rating")
        # Ein dritter Wert existiert nicht.
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_run(env.app, s.ws_a, case, attestation="server_executed")

    _with_env(body)


# --- CHECKs am Pruefall ------------------------------------------------------


@pytest.mark.integration
def test_case_checks_shape() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        element = ("playbook", uuid4())
        # Zulaessig: ohne Element, mit Element, deterministisch mit Muster.
        await _insert_case(env.app, s.ws_a, s.agent_a)
        await _insert_case(env.app, s.ws_a, s.agent_a, entity=element)
        await _insert_case(
            env.app, s.ws_a, s.agent_a, check_kind="must_contain", check_pattern="Frist"
        )

        with pytest.raises(asyncpg.CheckViolationError):  # deterministisch ohne Muster
            await _insert_case(env.app, s.ws_a, s.agent_a, check_kind="must_not_contain")
        with pytest.raises(asyncpg.CheckViolationError):  # human_rule mit Muster
            await _insert_case(env.app, s.ws_a, s.agent_a, check_pattern="Frist")
        with pytest.raises(asyncpg.CheckViolationError):  # unbekannte Elementart
            await _insert_case(env.app, s.ws_a, s.agent_a, entity=("agent", uuid4()))
        with pytest.raises(asyncpg.CheckViolationError):  # Element nur halb
            await env.app.execute(
                "INSERT INTO test_case (workspace_id, agent_id, entity_type, title, input, "
                " expected_behavior, check_kind, created_by_kind, created_by) "
                "VALUES ($1, $2, 'playbook', 't', 'i', 'e', 'human_rule', 'human', $3)",
                s.ws_a,
                s.agent_a,
                uuid4(),
            )
        with pytest.raises(asyncpg.CheckViolationError):  # Titel ueber 200
            await _insert_case(env.app, s.ws_a, s.agent_a, title="x" * 201)
        with pytest.raises(asyncpg.NotNullViolationError):  # agent_id ist Pflicht
            await env.app.execute(
                "INSERT INTO test_case (workspace_id, title, input, expected_behavior, "
                " check_kind, created_by_kind, created_by) "
                "VALUES ($1, 't', 'i', 'e', 'human_rule', 'human', $2)",
                s.ws_a,
                uuid4(),
            )

    _with_env(body)


# --- Unveraenderlichkeit -----------------------------------------------------


@pytest.mark.integration
def test_case_only_status_is_updatable_and_no_delete() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)

        # Erlaubt: nur der Status.
        await env.app.execute("UPDATE test_case SET status = 'retired' WHERE id = $1", case)
        assert await env.app.fetchval("SELECT status FROM test_case WHERE id = $1", case) == (
            "retired"
        )
        # Jede Inhaltsspalte ist gesperrt.
        for column, value in (
            ("title", "'neu'"),
            ("input", "'neu'"),
            ("expected_behavior", "'neu'"),
            ("check_kind", "'must_contain'"),
            ("agent_id", "agent_id"),
            ("supersedes_id", "NULL"),
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await env.app.execute(
                    f"UPDATE test_case SET {column} = {value} WHERE id = $1",  # noqa: S608
                    case,
                )
        # Zurueckziehen statt loeschen.
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await env.app.execute("DELETE FROM test_case WHERE id = $1", case)
        # Kein Rueckfall in einen unbekannten Status.
        with pytest.raises(asyncpg.CheckViolationError):
            await env.app.execute("UPDATE test_case SET status = 'draft' WHERE id = $1", case)

    _with_env(body)


@pytest.mark.integration
def test_run_is_append_only() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        case = await _insert_case(env.app, s.ws_a, s.agent_a)
        run = await _insert_run(env.app, s.ws_a, case)

        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await env.app.execute("UPDATE test_run SET verdict = 'fail' WHERE id = $1", run)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await env.app.execute("DELETE FROM test_run WHERE id = $1", run)
        # Der Owner (Purge/Erasure) behaelt Vollzugriff.
        await env.owner.execute(
            "UPDATE test_run SET reported_by_user_id = $2 WHERE id = $1", run, uuid4()
        )

    _with_env(body)


# --- Gleicher Workspace + Korrekturkette -------------------------------------


@pytest.mark.integration
def test_references_stay_in_one_workspace() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        # Als Owner (RLS aus): nur die Composite-FKs halten die Grenze.
        case_b = await _insert_case(env.owner, s.ws_b, s.agent_b)
        with pytest.raises(asyncpg.ForeignKeyViolationError):  # fremder Agent
            await _insert_case(env.owner, s.ws_a, s.agent_b)
        with pytest.raises(asyncpg.ForeignKeyViolationError):  # fremder Vorgaenger
            await _insert_case(env.owner, s.ws_a, s.agent_a, supersedes_id=case_b)
        with pytest.raises(asyncpg.ForeignKeyViolationError):  # Lauf zu fremdem Pruefall
            await _insert_run(env.owner, s.ws_a, case_b)

    _with_env(body)


@pytest.mark.integration
def test_supersedes_is_set_null_on_delete_and_cases_follow_agent() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        old = await _insert_case(env.owner, s.ws_a, s.agent_a)
        new = await _insert_case(env.owner, s.ws_a, s.agent_a2, supersedes_id=old)
        await _insert_run(env.owner, s.ws_a, old)

        # Vorgaenger weg (nur der Owner darf loeschen) -> Verweis genullt,
        # Nachfolger bleibt; seine Laeufe gehen mit.
        await env.owner.execute("DELETE FROM test_case WHERE id = $1", old)
        row = await env.owner.fetchrow(
            "SELECT workspace_id, supersedes_id FROM test_case WHERE id = $1", new
        )
        assert row is not None
        assert row["supersedes_id"] is None
        assert row["workspace_id"] == s.ws_a
        assert await env.owner.fetchval("SELECT count(*) FROM test_run") == 0

        # Agent weg -> seine Pruefaelle gehen mit (ADR 3.2: ON DELETE CASCADE).
        await env.owner.execute("DELETE FROM agent WHERE id = $1", s.agent_a2)
        assert await env.owner.fetchval("SELECT count(*) FROM test_case WHERE id = $1", new) == 0

    _with_env(body)


# --- Repository unter der App-Rolle ------------------------------------------


def _case_input(agent_id: UUID, **overrides: object) -> TestCaseCreate:
    data: dict[str, object] = {
        "agent_id": agent_id,
        "title": "Kuendigungsfrist",
        "input": "Wie kuendige ich?",
        "expected_behavior": "Nennt die Frist aus dem Playbook.",
    }
    data.update(overrides)
    return TestCaseCreate.model_validate(data)


class _HumanAuthor(TypedDict):
    created_by_kind: TestCaseCreatedByKind
    created_by: UUID


def _human(seed: _Seed) -> _HumanAuthor:
    """Urheberschaft „Mensch" fuer Repository-Aufrufe (Seed-User)."""
    return {"created_by_kind": TestCaseCreatedByKind.human, "created_by": seed.user}


def _with_repo(
    body: Callable[[PgTestCaseRepository, _Env], Awaitable[None]],
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
                await body(PgTestCaseRepository(pool), env)
        finally:
            await pool.close()

    _with_env(outer)


@pytest.mark.integration
def test_repository_create_list_retire() -> None:
    async def body(repo: PgTestCaseRepository, env: _Env) -> None:
        s = env.seed
        element_id = uuid4()
        bound = await repo.create_case(
            s.ws_a,
            _case_input(
                s.agent_a,
                entity_type="playbook",
                entity_id=element_id,
                check_kind="must_contain",
                check_pattern="Frist",
            ),
            created_by_kind=TestCaseCreatedByKind.agent,
            created_by=s.agent_a,
        )
        other = await repo.create_case(
            s.ws_a,
            _case_input(s.agent_a2),
            created_by_kind=TestCaseCreatedByKind.human,
            created_by=s.user,
        )
        assert bound.status is TestCaseStatus.active
        assert bound.check_kind is TestCheckKind.must_contain
        assert bound.created_by_kind is TestCaseCreatedByKind.agent
        assert await repo.get_case(s.ws_a, bound.id) == bound

        assert [c.id for c in await repo.list_cases(s.ws_a)] == [bound.id, other.id]
        assert [c.id for c in await repo.list_cases(s.ws_a, agent_id=s.agent_a2)] == [other.id]
        by_element = await repo.list_cases(s.ws_a, entity_type="playbook", entity_id=element_id)
        assert [c.id for c in by_element] == [bound.id]

        retired = await repo.retire_case(s.ws_a, other.id)
        assert retired is not None
        assert retired.status is TestCaseStatus.retired
        active = await repo.list_cases(s.ws_a, status=TestCaseStatus.active)
        assert [c.id for c in active] == [bound.id]
        assert await repo.retire_case(s.ws_a, uuid4()) is None
        # Fremder Workspace: per Signatur-Filter und RLS unsichtbar.
        assert await repo.get_case(s.ws_b, bound.id) is None

    _with_repo(body)


@pytest.mark.integration
def test_repository_active_for_element_is_union() -> None:
    """ADR 3.2.1: direkt gebunden (egal welcher Agent) ODER Agent betroffen."""

    async def body(repo: PgTestCaseRepository, env: _Env) -> None:
        s = env.seed
        element_id = uuid4()
        direct = await repo.create_case(
            s.ws_a,
            _case_input(s.agent_a2, entity_type="playbook", entity_id=element_id),
            **_human(s),
        )
        via_agent = await repo.create_case(s.ws_a, _case_input(s.agent_a), **_human(s))
        # Gleicher Agent UND direkt gebunden -> genau einmal in der Menge.
        both = await repo.create_case(
            s.ws_a,
            _case_input(s.agent_a, entity_type="playbook", entity_id=element_id),
            **_human(s),
        )
        # Anderes Element, nicht betroffener Agent -> nicht dabei.
        await repo.create_case(
            s.ws_a,
            _case_input(s.agent_a2, entity_type="playbook", entity_id=uuid4()),
            **_human(s),
        )
        retired = await repo.create_case(s.ws_a, _case_input(s.agent_a), **_human(s))
        await repo.retire_case(s.ws_a, retired.id)

        result = await repo.list_active_for_element(s.ws_a, "playbook", element_id, [s.agent_a])
        assert [c.id for c in result] == [direct.id, via_agent.id, both.id]

        only_direct = await repo.list_active_for_element(s.ws_a, "playbook", element_id, [])
        assert [c.id for c in only_direct] == [direct.id, both.id]

    _with_repo(body)


@pytest.mark.integration
def test_repository_supersede_is_one_transaction() -> None:
    async def body(repo: PgTestCaseRepository, env: _Env) -> None:
        s = env.seed
        old = await repo.create_case(s.ws_a, _case_input(s.agent_a), **_human(s))

        new = await repo.supersede_case(
            s.ws_a, old.id, _case_input(s.agent_a, title="Frist, korrigiert"), **_human(s)
        )
        assert new is not None
        assert new.supersedes_id == old.id
        reloaded = await repo.get_case(s.ws_a, old.id)
        assert reloaded is not None
        assert reloaded.status is TestCaseStatus.retired
        assert reloaded.title == old.title  # Inhalt unveraendert

        # Ein zurueckgezogener Vorgaenger laesst sich nicht erneut korrigieren.
        again = await repo.supersede_case(s.ws_a, old.id, _case_input(s.agent_a), **_human(s))
        assert again is None

        # Scheitert der Insert (fremder Agent), bleibt der Vorgaenger aktiv.
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await repo.supersede_case(s.ws_a, new.id, _case_input(s.agent_b), **_human(s))
        still = await repo.get_case(s.ws_a, new.id)
        assert still is not None
        assert still.status is TestCaseStatus.active
        assert len(await repo.list_cases(s.ws_a)) == 2

    _with_repo(body)


@pytest.mark.integration
def test_repository_runs_latest_wins_and_batch_is_atomic() -> None:
    async def body(repo: PgTestCaseRepository, env: _Env) -> None:
        s = env.seed
        case_1 = await repo.create_case(s.ws_a, _case_input(s.agent_a), **_human(s))
        case_2 = await repo.create_case(s.ws_a, _case_input(s.agent_a2), **_human(s))
        version = uuid4()

        def run(case_id: UUID, verdict: str, passed: int) -> TestRunCreate:
            return TestRunCreate.model_validate(
                {
                    "test_case_id": case_id,
                    "runs_total": 3,
                    "runs_passed": passed,
                    "verdict": verdict,
                }
            )

        async def agent_report(version_id: UUID, results: list[TestRunCreate]) -> list[TestRunRead]:
            return await repo.insert_runs(
                s.ws_a,
                "playbook",
                version_id,
                results,
                attestation=TestAttestation.client_self_report,
                reported_by_agent_id=s.agent_a,
                reported_by_user_id=None,
                model_provider="local",
                model_name="m1",
            )

        first = await agent_report(version, [run(case_1.id, "fail", 1)])
        assert first[0].attestation is TestAttestation.client_self_report
        assert first[0].model_name == "m1"
        # Menschliche Bewertung danach -> zaehlt als letztes Ergebnis.
        rated = await repo.insert_runs(
            s.ws_a,
            "playbook",
            version,
            [run(case_1.id, "pass", 3)],
            attestation=TestAttestation.human_rating,
            reported_by_agent_id=None,
            reported_by_user_id=s.user,
            model_provider=None,
            model_name=None,
        )
        # Ergebnis fuer eine ANDERE Version darf den Bericht nicht beeinflussen.
        await agent_report(uuid4(), [run(case_2.id, "pass", 3)])

        latest = await repo.latest_runs_for_version(s.ws_a, version, [case_1.id, case_2.id])
        assert set(latest) == {case_1.id}  # case_2 fehlt -> im Bericht „missing"
        assert latest[case_1.id].id == rated[0].id
        assert latest[case_1.id].verdict is TestVerdict.pass_

        # Charge mit einem inkonsistenten Ergebnis: nichts wird geschrieben.
        before = await env.owner.fetchval("SELECT count(*) FROM test_run")
        with pytest.raises(asyncpg.CheckViolationError):
            await agent_report(version, [run(case_2.id, "pass", 3), run(case_1.id, "pass", 2)])
        assert await env.owner.fetchval("SELECT count(*) FROM test_run") == before

    _with_repo(body)
