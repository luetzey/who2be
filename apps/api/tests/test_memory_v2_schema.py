"""Integrationstests fuer Gedaechtnis 2.0 (ADR-0053 3.1/3.1.1/3.1.2/5.1, Migration 0091, C1a).

Belegt auf der Laufzeitrolle `who2be_app` (NOBYPASSRLS) in einem isolierten
Schema (Muster `test_test_case_schema.py`):

- **Invarianten (DB-CHECK, 3.1):** `lesson` nie `active`; `scope='user'` nur
  mit `subject_user_id`, `kind='user_fact'`, `agent_id IS NULL`;
  `scope='agent'` nur mit `agent_id`; `converted` genau dann, wenn
  `converted_case_id` gesetzt ist; geschlossene Wertemengen.
- **Einreicher:** ein Nutzerfakt ueberlebt das Loeschen des Agenten, der ihn
  eingereicht hat (`created_by_agent_id` ON DELETE SET NULL); das
  Agentengedaechtnis faellt weiter per Cascade.
- **Historie:** `agent_memory_event` ist append-only (kein UPDATE/DELETE),
  workspace-getrennt per RLS, an den Eintrag desselben Workspace gebunden und
  faellt mit ihm.
- **Bestand (5.1):** eine Datenbank auf Stand 0090 mit `active`/`pending`/
  `rejected`-Zeilen traegt nach 0091 die vorgegebenen Werte.
- **Repository:** Abrufpfade liefern nur aktives Agentengedaechtnis (nie
  `lesson`, nie `scope='user'`); Zaehlabfrage je `(workspace_id,
  subject_user_id)` ueber alle Status; Loeschen hinterlaesst eine
  inhaltsfreie `audit_log`-Zeile.
"""

from __future__ import annotations

import asyncio
import secrets
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.tenancy import apply_tenant_settings, tenant_scope
from who2be_api.repositories.memory_repository import (
    MEMORY_DELETED_AUDIT_ACTION,
    PgMemoryRepository,
)
from who2be_models import (
    MEMORY_MAX_PER_USER,
    MemoryActorKind,
    MemoryEventCreate,
    MemoryEventKind,
    MemoryKind,
    MemoryOrigin,
    MemoryScope,
    MemorySource,
    MemoryStatus,
)

# Test-only Passwort fuer die App-Rolle (per format() in ALTER ROLE eingesetzt).
_APP_PASSWORD = "memory_v2_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret

_MIGRATION = "0091_agent_memory_v2.sql"


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


async def _connect_app(schema: str) -> asyncpg.Connection:
    settings = get_settings()
    app = await asyncpg.connect(settings.database_url, user="who2be_app", password=_APP_PASSWORD)
    await app.execute(f'SET search_path TO "{schema}"')
    return app


def _with_env(body: Callable[[_Env], Awaitable[None]]) -> None:
    """Migriert ein isoliertes Schema, seedet zwei Workspaces, verbindet als App-Rolle."""
    settings = get_settings()
    schema = f"mem_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        app: asyncpg.Connection | None = None
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)
            seed = await _seed(owner, schema)
            await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
            app = await _connect_app(schema)
            await body(_Env(owner=owner, app=app, seed=seed))
        finally:
            if app is not None:
                await app.close()
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


async def _insert_memory(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    agent_id: UUID | None,
    *,
    fact: str = "Bevorzugt Kontakt per E-Mail",
    status: str = "pending",
    kind: str = "user_fact",
    scope: str = "agent",
    subject_user_id: UUID | None = None,
    created_by_agent_id: UUID | None = None,
    converted_case_id: UUID | None = None,
    origin: str = "user_stated",
    source: str = "agent",
) -> UUID:
    memory_id: UUID = await conn.fetchval(
        "INSERT INTO agent_memory "
        "(workspace_id, agent_id, status, fact, kind, scope, subject_user_id, "
        " created_by_agent_id, converted_case_id, origin, source) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) RETURNING id",
        workspace_id,
        agent_id,
        status,
        fact,
        kind,
        scope,
        subject_user_id,
        created_by_agent_id,
        converted_case_id,
        origin,
        source,
    )
    return memory_id


async def _insert_event(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    memory_id: UUID,
    *,
    event: str = "created",
    actor_kind: str = "agent",
) -> UUID:
    event_id: UUID = await conn.fetchval(
        "INSERT INTO agent_memory_event (workspace_id, memory_id, event, actor_kind) "
        "VALUES ($1, $2, $3, $4) RETURNING id",
        workspace_id,
        memory_id,
        event,
        actor_kind,
    )
    return event_id


# --- Invarianten (3.1) ---------------------------------------------------------


@pytest.mark.integration
def test_lesson_can_never_be_active() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        # Zulaessig: pending, rejected, converted (mit Fall).
        lesson = await _insert_memory(env.app, s.ws_a, s.agent_a, kind="lesson", fact="L1")
        await _insert_memory(
            env.app, s.ws_a, s.agent_a, kind="lesson", status="rejected", fact="L2"
        )
        await _insert_memory(
            env.app,
            s.ws_a,
            s.agent_a,
            kind="lesson",
            status="converted",
            converted_case_id=uuid4(),
            fact="L3",
        )
        # Nie aktiv — weder beim Anlegen noch per Statuswechsel.
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_memory(env.app, s.ws_a, s.agent_a, kind="lesson", status="active")
        with pytest.raises(asyncpg.CheckViolationError):
            await env.app.execute("UPDATE agent_memory SET status = 'active' WHERE id = $1", lesson)
        # Auch `expired` ist fuer Lernvorschlaege nicht vorgesehen (3.1).
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_memory(env.app, s.ws_a, s.agent_a, kind="lesson", status="expired")
        # Andere Arten duerfen aktiv sein.
        await _insert_memory(env.app, s.ws_a, s.agent_a, kind="agent_note", status="active")

    _with_env(body)


@pytest.mark.integration
def test_user_scope_shape() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        # Zulaessig: Nutzerfakt ohne Agent, mit Einreicher.
        await _insert_memory(
            env.app,
            s.ws_a,
            None,
            scope="user",
            subject_user_id=s.user,
            created_by_agent_id=s.agent_a,
        )
        with pytest.raises(asyncpg.CheckViolationError):  # ohne betroffenen Nutzer
            await _insert_memory(env.app, s.ws_a, None, scope="user")
        with pytest.raises(asyncpg.CheckViolationError):  # mit agent_id
            await _insert_memory(env.app, s.ws_a, s.agent_a, scope="user", subject_user_id=s.user)
        for kind in ("agent_note", "lesson"):  # nur user_fact
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_memory(
                    env.app, s.ws_a, None, scope="user", subject_user_id=s.user, kind=kind
                )

    _with_env(body)


@pytest.mark.integration
def test_agent_scope_requires_agent() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_memory(env.app, s.ws_a, None, scope="agent")
        memory = await _insert_memory(env.app, s.ws_a, s.agent_a)
        with pytest.raises(asyncpg.CheckViolationError):
            await env.app.execute("UPDATE agent_memory SET agent_id = NULL WHERE id = $1", memory)

    _with_env(body)


@pytest.mark.integration
def test_converted_iff_case_id() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        with pytest.raises(asyncpg.CheckViolationError):  # converted ohne Fall
            await _insert_memory(env.app, s.ws_a, s.agent_a, kind="lesson", status="converted")
        with pytest.raises(asyncpg.CheckViolationError):  # Fall ohne converted
            await _insert_memory(
                env.app, s.ws_a, s.agent_a, kind="lesson", converted_case_id=uuid4()
            )
        # Kein FK bis D1: ein beliebiger Fall-Verweis ist zulaessig.
        await _insert_memory(
            env.app,
            s.ws_a,
            s.agent_a,
            kind="lesson",
            status="converted",
            converted_case_id=uuid4(),
        )

    _with_env(body)


@pytest.mark.integration
def test_closed_value_sets() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        for kwargs in (
            {"kind": "procedure"},
            {"scope": "workspace"},
            {"origin": "rumor"},
            {"source": "backfill"},
            {"status": "archived"},
        ):
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_memory(env.app, s.ws_a, s.agent_a, **kwargs)  # type: ignore[arg-type]
        memory = await _insert_memory(env.app, s.ws_a, s.agent_a)
        with pytest.raises(asyncpg.CheckViolationError):
            await env.app.execute(
                "UPDATE agent_memory SET occurrence_count = 0 WHERE id = $1", memory
            )
        # Jeder Python-Wert ist in der DB zulaessig (Enum und CHECK deckungsgleich).
        for origin in MemoryOrigin:
            await _insert_memory(env.app, s.ws_a, s.agent_a, origin=origin.value, fact=origin)
        for source in MemorySource:
            await _insert_memory(env.app, s.ws_a, s.agent_a, source=source.value, fact=source)

    _with_env(body)


@pytest.mark.integration
def test_user_fact_survives_agent_delete() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        user_fact = await _insert_memory(
            env.app,
            s.ws_a,
            None,
            scope="user",
            subject_user_id=s.user,
            created_by_agent_id=s.agent_a,
        )
        agent_fact = await _insert_memory(env.app, s.ws_a, s.agent_a, created_by_agent_id=s.agent_a)
        await env.owner.execute("DELETE FROM agent WHERE id = $1", s.agent_a)

        row = await env.app.fetchrow(
            "SELECT created_by_agent_id FROM agent_memory WHERE id = $1", user_fact
        )
        assert row is not None and row["created_by_agent_id"] is None
        assert await env.app.fetchval("SELECT 1 FROM agent_memory WHERE id = $1", agent_fact) is (
            None
        )

    _with_env(body)


@pytest.mark.integration
def test_created_by_agent_must_share_workspace() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await _insert_memory(env.app, s.ws_a, s.agent_a, created_by_agent_id=s.agent_b)

    _with_env(body)


# --- Historie (3.1.2) ------------------------------------------------------------


@pytest.mark.integration
def test_event_is_append_only() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        memory = await _insert_memory(env.app, s.ws_a, s.agent_a)
        event = await _insert_event(env.app, s.ws_a, memory)
        assert await env.app.fetchval(
            "SELECT event FROM agent_memory_event WHERE id = $1", event
        ) == ("created")

        for column, value in (
            ("event", "'approved'"),
            ("reason", "'umgeschrieben'"),
            ("before", "'{}'::jsonb"),
            ("created_at", "now()"),
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await env.app.execute(
                    f"UPDATE agent_memory_event SET {column} = {value} WHERE id = $1",  # noqa: S608
                    event,
                )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await env.app.execute("DELETE FROM agent_memory_event WHERE id = $1", event)

    _with_env(body)


@pytest.mark.integration
def test_event_checks_and_cascade() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        memory = await _insert_memory(env.app, s.ws_a, s.agent_a)
        # Jeder Python-Wert ist zulaessig, fremde Werte nicht.
        for kind in MemoryEventKind:
            await _insert_event(env.app, s.ws_a, memory, event=kind.value)
        for actor in MemoryActorKind:
            await _insert_event(env.app, s.ws_a, memory, actor_kind=actor.value)
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_event(env.app, s.ws_a, memory, event="deleted")
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_event(env.app, s.ws_a, memory, actor_kind="robot")
        with pytest.raises(asyncpg.CheckViolationError):
            await env.app.execute(
                "INSERT INTO agent_memory_event "
                "(workspace_id, memory_id, event, actor_kind, reason) "
                "VALUES ($1, $2, 'rejected', 'human', $3)",
                s.ws_a,
                memory,
                "x" * 501,
            )

        # Die Historie geht mit dem Eintrag (Hard-Delete, M5).
        await env.app.execute("DELETE FROM agent_memory WHERE id = $1", memory)
        assert (
            await env.app.fetchval(
                "SELECT count(*) FROM agent_memory_event WHERE memory_id = $1", memory
            )
            == 0
        )

    _with_env(body)


@pytest.mark.integration
def test_event_must_share_workspace_with_memory() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        memory_a = await _insert_memory(env.owner, s.ws_a, s.agent_a)
        # Als Owner (RLS-Bypass): nur der Composite-FK haelt den Workspace gleich.
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await _insert_event(env.owner, s.ws_b, memory_a)

    _with_env(body)


@pytest.mark.integration
def test_event_rls_separates_workspaces() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        memory_a = await _insert_memory(env.owner, s.ws_a, s.agent_a)
        memory_b = await _insert_memory(env.owner, s.ws_b, s.agent_b)
        await _insert_event(env.owner, s.ws_a, memory_a)
        await _insert_event(env.owner, s.ws_b, memory_b)

        for ws in (s.ws_a, s.ws_b):
            await env.as_tenant(ws)
            # Bewusst OHNE WHERE: nur RLS trennt.
            rows = await env.app.fetch("SELECT workspace_id FROM agent_memory_event")
            assert {r["workspace_id"] for r in rows} == {ws}

        await env.as_tenant(uuid4())
        assert await env.app.fetch("SELECT id FROM agent_memory_event") == []

        # WITH CHECK: Schreiben in den fremden Workspace wird abgewiesen.
        await env.as_tenant(s.ws_a)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await _insert_event(env.app, s.ws_b, memory_b)

    _with_env(body)


# --- Bestand (5.1) ---------------------------------------------------------------


@pytest.mark.integration
def test_migration_of_existing_rows(tmp_path: Path) -> None:
    """Stand 0090 mit Bestandszeilen -> 0091 -> Werte laut ADR-0053 5.1."""
    settings = get_settings()
    schema = f"mem_mig_{secrets.token_hex(6)}"
    for path in MIGRATIONS_DIR.glob("*.sql"):
        if path.name < _MIGRATION:
            shutil.copy(path, tmp_path / path.name)

    async def _run() -> None:
        owner = await asyncpg.connect(settings.database_url)
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            applied = await apply_migrations(owner, tmp_path)
            assert _MIGRATION not in applied
            seed = await _seed(owner, schema)

            confirmed_then = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
            rows: dict[str, UUID] = {}
            for status in ("active", "pending", "rejected"):
                rows[status] = await owner.fetchval(
                    "INSERT INTO agent_memory "
                    "(workspace_id, agent_id, status, fact, created_at, updated_at) "
                    "VALUES ($1, $2, $3, $4, $5, $5) RETURNING id",
                    seed.ws_a,
                    seed.agent_a,
                    status,
                    f"Bestand {status}",
                    confirmed_then,
                )

            shutil.copy(MIGRATIONS_DIR / _MIGRATION, tmp_path / _MIGRATION)
            assert await apply_migrations(owner, tmp_path) == [_MIGRATION]

            for status, memory_id in rows.items():
                row = await owner.fetchrow(
                    "SELECT status, fact, kind, scope, origin, source, subject_user_id, "
                    "       created_by_agent_id, confirmed_at, confirmed_by, expires_at, "
                    "       occurrence_count, converted_case_id, agent_id "
                    "FROM agent_memory WHERE id = $1",
                    memory_id,
                )
                assert row is not None
                # Inhaltlich unveraendert.
                assert row["status"] == status
                assert row["fact"] == f"Bestand {status}"
                assert row["agent_id"] == seed.agent_a
                # Umgeformt laut 5.1.
                assert row["kind"] == MemoryKind.user_fact
                assert row["scope"] == MemoryScope.agent
                assert row["origin"] == MemoryOrigin.legacy_unknown
                assert row["source"] == MemorySource.agent
                assert row["created_by_agent_id"] == seed.agent_a
                assert row["occurrence_count"] == 1
                for column in ("subject_user_id", "confirmed_by", "expires_at"):
                    assert row[column] is None, column
                assert row["converted_case_id"] is None
                # M6: nur `active` gilt als bestaetigt, mit `updated_at`.
                expected = confirmed_then if status == "active" else None
                assert row["confirmed_at"] == expected, status

            # Idempotent: ein zweiter Lauf wendet nichts mehr an.
            assert await apply_migrations(owner, tmp_path) == []
        finally:
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


# --- Repository ------------------------------------------------------------------


def _with_repo(body: Callable[[PgMemoryRepository, _Env], Awaitable[None]]) -> None:
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
            # `public` dahinter: dort liegt pg_trgm (`similarity`), das die
            # Abrufpfade brauchen; die Tabellen kommen aus dem Testschema.
            server_settings={"search_path": f"{env.seed.schema},public"},
        )
        assert pool is not None
        try:
            async with tenant_scope(env.seed.ws_a, None):
                await body(PgMemoryRepository(pool), env)
        finally:
            await pool.close()

    _with_env(outer)


@pytest.mark.integration
def test_repository_retrieval_only_active_agent_memory() -> None:
    async def body(repo: PgMemoryRepository, env: _Env) -> None:
        s = env.seed
        created = await repo.insert(
            s.ws_a, s.agent_a, MemoryStatus.active, "Rechnung per PDF", None, "preference", 7
        )
        # Die Defaults bilden den heutigen Schreibpfad ab.
        assert created.kind is MemoryKind.user_fact
        assert created.scope is MemoryScope.agent
        assert created.origin is MemoryOrigin.legacy_unknown
        assert created.source is MemorySource.agent
        assert created.created_by_agent_id == s.agent_a
        assert created.confirmed_at is None

        # Nicht abrufbar: Lernvorschlag desselben Agenten, Nutzerfakt im Workspace.
        await _insert_memory(
            env.owner, s.ws_a, s.agent_a, kind="lesson", fact="Rechnung zuerst pruefen"
        )
        await _insert_memory(
            env.owner,
            s.ws_a,
            None,
            scope="user",
            subject_user_id=s.user,
            status="active",
            fact="Rechnung geht an die Buchhaltung",
        )

        hits = await repo.search_active(s.ws_a, s.agent_a, "Rechnung", 10)
        assert [hit.id for hit in hits] == [created.id]
        listed = await repo.list_active(s.ws_a, s.agent_a, 10)
        assert [hit.id for hit in listed] == [created.id]

    _with_repo(body)


@pytest.mark.integration
def test_repository_count_for_user_counts_all_status() -> None:
    async def body(repo: PgMemoryRepository, env: _Env) -> None:
        s = env.seed
        other_user = uuid4()
        for index, status in enumerate(("pending", "active", "rejected", "expired")):
            await _insert_memory(
                env.owner,
                s.ws_a,
                None,
                scope="user",
                subject_user_id=s.user,
                status=status,
                fact=f"Nutzerfakt {index}",
            )
        # Zaehlen nicht mit: anderer Nutzer, anderer Workspace, Agentengedaechtnis.
        await _insert_memory(env.owner, s.ws_a, None, scope="user", subject_user_id=other_user)
        await _insert_memory(env.owner, s.ws_b, None, scope="user", subject_user_id=s.user)
        await _insert_memory(env.owner, s.ws_a, s.agent_a)

        assert await repo.count_for_user(s.ws_a, s.user) == 4
        assert await repo.count_for_user(s.ws_a, other_user) == 1
        assert await repo.count_for_user(s.ws_a, uuid4()) == 0
        # Nutzerfakten zaehlen nicht gegen die Agentengrenze (3.1.1).
        assert await repo.count_for_agent(s.ws_a, s.agent_a) == 1
        assert MEMORY_MAX_PER_USER == 500  # gesetzte Annahme, ADR-0053 Anhang B

    _with_repo(body)


@pytest.mark.integration
def test_repository_events_roundtrip() -> None:
    async def body(repo: PgMemoryRepository, env: _Env) -> None:
        s = env.seed
        memory = await repo.insert(
            s.ws_a, s.agent_a, MemoryStatus.pending, "Fakt", None, "general", 5
        )
        snapshot = {"fact": "Fakt", "status": "pending", "kind": "user_fact"}
        first = await repo.insert_event(
            s.ws_a,
            MemoryEventCreate(
                memory_id=memory.id,
                event=MemoryEventKind.created,
                actor_kind=MemoryActorKind.agent,
                agent_id=s.agent_a,
                after=snapshot,
            ),
        )
        second = await repo.insert_event(
            s.ws_a,
            MemoryEventCreate(
                memory_id=memory.id,
                event=MemoryEventKind.approved,
                actor_kind=MemoryActorKind.human,
                actor_id=s.user,
                before=snapshot,
                after={**snapshot, "status": "active"},
                reason="passt",
            ),
        )
        assert first.after == snapshot and first.before is None
        assert second.before == snapshot and second.after == {**snapshot, "status": "active"}

        events = await repo.list_events(s.ws_a, memory.id)
        assert [e.id for e in events] == [first.id, second.id]
        assert events[1] == second
        # Fremder Workspace sieht die Historie nicht (Signatur + RLS).
        assert await repo.list_events(s.ws_b, memory.id) == []

    _with_repo(body)


@pytest.mark.integration
def test_repository_delete_leaves_contentless_audit() -> None:
    async def body(repo: PgMemoryRepository, env: _Env) -> None:
        s = env.seed
        secret_fact = "Geheimnis der Kundin"
        one = await repo.insert(
            s.ws_a, s.agent_a, MemoryStatus.active, secret_fact, "aus Chat", "fact", 6
        )
        await repo.insert_event(
            s.ws_a,
            MemoryEventCreate(
                memory_id=one.id,
                event=MemoryEventKind.created,
                actor_kind=MemoryActorKind.agent,
                after={"fact": secret_fact},
            ),
        )
        others = [
            await repo.insert(s.ws_a, s.agent_a, MemoryStatus.pending, f"F{i}", None, "general", 5)
            for i in range(2)
        ]
        untouched = await repo.insert(
            s.ws_a, s.agent_a2, MemoryStatus.pending, "Anderer Agent", None, "general", 5
        )

        assert await repo.delete(s.ws_a, s.agent_a, one.id, s.user) is True
        assert await repo.delete(s.ws_a, s.agent_a, one.id, s.user) is False
        assert await repo.delete_all(s.ws_a, s.agent_a, s.user) == 2
        assert await repo.get(s.ws_a, s.agent_a2, untouched.id) is not None

        audits = await env.owner.fetch(
            "SELECT workspace_id, actor_id, target, detail::text AS detail FROM audit_log "
            "WHERE action = $1 ORDER BY created_at",
            MEMORY_DELETED_AUDIT_ACTION,
        )
        assert {a["target"] for a in audits} == {str(one.id), *(str(o.id) for o in others)}
        for audit in audits:
            assert audit["workspace_id"] == s.ws_a
            assert audit["actor_id"] == s.user
            assert audit["detail"] == "{}"  # inhaltsfrei
        # Kein Rest des Inhalts, auch nicht in der Historie.
        assert (
            await env.owner.fetchval(
                "SELECT count(*) FROM agent_memory_event WHERE memory_id = $1", one.id
            )
            == 0
        )

    _with_repo(body)
