"""Laufprotokoll und Store des Workers (ADR-0057 §5/§6, Migration 0102, P1a).

Gegen echtes Postgres in einem isolierten Schema (`isolated_schema`). Belegt:

- **Genau ein Lauf je Slot:** zwei nebenlaeufige `claim_slot` auf denselben
  Slot (zwei Verbindungen, gleichzeitig gestartet) ergeben genau eine Zeile
  und genau eine Lauf-ID.
- **Abandoned erst nach der Schwelle:** ein `running`-Lauf ohne Heartbeat
  bleibt bis `RUN_ABANDONED_AFTER` stehen und wird danach `failed`/`Abandoned`;
  ein frischer Heartbeat schiebt die Grenze.
- **Advisory-Lock:** der zweite Versuch (zweite Verbindung) liefert `False`,
  nach dem Freigeben wieder `True`.
- **Grants:** `who2be_app` darf beide Tabellen lesen, aber nicht schreiben.
- **Constraints:** `result` nur Zaehler, `error_class` nur bei `failed`.
- **Org-Transfer:** beide Tabellen sind global; `load_schema` klassifiziert
  sie ohne Fehler (der Waechter ist fail-closed fuer Tabellen ohne
  Mandantenspalte).

Advisory-Locks gelten datenbankweit, nicht je Schema. Die Routinen-Namen
tragen deshalb einen Zufallsanteil, damit parallele Laeufe aus anderen
Worktrees nicht kollidieren.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from who2be_api.core import org_transfer
from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR
from who2be_api.testing.isolated_schema import isolated_schema
from who2be_api.worker import store
from who2be_api.worker.store import (
    ABANDONED_ERROR_CLASS,
    RUN_ABANDONED_AFTER,
    WORKER_HEALTHCHECK_MAX_AGE,
    WORKER_STALE_AFTER,
)

pytestmark = pytest.mark.integration

# Test-only Passwort fuer die App-Rolle (per format() in ALTER ROLE eingesetzt).
_APP_PASSWORD = "worker_store_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret

_T0 = datetime(2026, 11, 6, 3, 30, tzinfo=UTC)
_WORKER = "test-host:1"


def _routine() -> str:
    return f"purge-{secrets.token_hex(4)}"


def _in_schema(body: Callable[[asyncpg.Connection], Awaitable[None]]) -> None:
    """Fuehrt `body` mit einer Owner-Verbindung im frisch migrierten Schema aus."""
    with isolated_schema("worker"):
        url = get_settings().database_url

        async def _run() -> None:
            conn = await asyncpg.connect(url)
            try:
                await body(conn)
            finally:
                await conn.close()

        asyncio.run(_run())


# --- Schwellen ---------------------------------------------------------------


def test_thresholds_match_pm_w4() -> None:
    assert WORKER_HEALTHCHECK_MAX_AGE == timedelta(minutes=2)
    assert WORKER_STALE_AFTER == timedelta(minutes=5)
    assert RUN_ABANDONED_AFTER == timedelta(minutes=5)


# --- Slot-Claim --------------------------------------------------------------


def test_concurrent_claims_on_same_slot_yield_exactly_one_row() -> None:
    routine = _routine()

    async def body(owner: asyncpg.Connection) -> None:
        url = get_settings().database_url
        first = await asyncpg.connect(url)
        second = await asyncpg.connect(url)
        try:
            # Beide INSERTs offen in eigenen Transaktionen, damit sich die
            # Claims wirklich ueberlappen: der zweite wartet auf den ersten und
            # sieht nach dessen COMMIT den Konflikt.
            gate = asyncio.Event()

            async def claim(conn: asyncpg.Connection, worker: str) -> object:
                async with conn.transaction():
                    await gate.wait()
                    run_id = await store.claim_slot(
                        conn, routine, _T0, trigger="schedule", worker_id=worker, now=_T0
                    )
                    await asyncio.sleep(0.2)
                    return run_id

            tasks = [
                asyncio.create_task(claim(first, "host-a:1")),
                asyncio.create_task(claim(second, "host-b:2")),
            ]
            await asyncio.sleep(0.05)
            gate.set()
            results = await asyncio.gather(*tasks)
        finally:
            await first.close()
            await second.close()

        winners = [r for r in results if r is not None]
        assert len(winners) == 1, results
        rows = await owner.fetch(
            "SELECT id, status, trigger FROM routine_run WHERE routine = $1", routine
        )
        assert len(rows) == 1
        assert rows[0]["id"] == winners[0]
        assert rows[0]["status"] == "running"
        assert rows[0]["trigger"] == "schedule"

    _in_schema(body)


def test_many_concurrent_claims_yield_one_winner() -> None:
    routine = _routine()

    async def body(owner: asyncpg.Connection) -> None:
        url = get_settings().database_url
        pool = await asyncpg.create_pool(url, min_size=8, max_size=8)
        try:

            async def claim(i: int) -> object:
                async with pool.acquire() as conn:
                    return await store.claim_slot(
                        conn, routine, _T0, trigger="schedule", worker_id=f"h:{i}", now=_T0
                    )

            results = await asyncio.gather(*(claim(i) for i in range(16)))
        finally:
            await pool.close()
        assert sum(r is not None for r in results) == 1
        assert (
            await owner.fetchval("SELECT count(*) FROM routine_run WHERE routine = $1", routine)
            == 1
        )

    _in_schema(body)


def test_other_slot_and_other_routine_claim_independently() -> None:
    routine, other = _routine(), _routine()

    async def body(conn: asyncpg.Connection) -> None:
        a = await store.claim_slot(conn, routine, _T0, trigger="schedule", worker_id=_WORKER)
        b = await store.claim_slot(
            conn, routine, _T0 + timedelta(days=1), trigger="schedule", worker_id=_WORKER
        )
        c = await store.claim_slot(conn, other, _T0, trigger="cli", worker_id=_WORKER)
        again = await store.claim_slot(conn, routine, _T0, trigger="cli", worker_id=_WORKER)
        assert None not in (a, b, c)
        assert len({a, b, c}) == 3
        assert again is None

    _in_schema(body)


def test_claim_rejects_naive_slot_and_unknown_trigger() -> None:
    routine = _routine()

    async def body(conn: asyncpg.Connection) -> None:
        with pytest.raises(ValueError, match="zeitzonenbehaftet"):
            await store.claim_slot(
                conn,
                routine,
                datetime(2026, 1, 1),  # noqa: DTZ001 — bewusst naiv, der Store weist es ab
                trigger="schedule",
                worker_id=_WORKER,
            )
        with pytest.raises(ValueError, match="trigger"):
            await store.claim_slot(
                conn,
                routine,
                _T0,
                trigger="cron",  # type: ignore[arg-type]
                worker_id=_WORKER,
            )
        assert await conn.fetchval("SELECT count(*) FROM routine_run") == 0

    _in_schema(body)


# --- Abschluss ---------------------------------------------------------------


def test_finish_records_counters_and_error_class_only() -> None:
    ok_routine, bad_routine, skip_routine = _routine(), _routine(), _routine()

    async def body(conn: asyncpg.Connection) -> None:
        ok = await store.claim_slot(
            conn, ok_routine, _T0, trigger="schedule", worker_id=_WORKER, now=_T0
        )
        bad = await store.claim_slot(
            conn, bad_routine, _T0, trigger="schedule", worker_id=_WORKER, now=_T0
        )
        skip = await store.claim_slot(
            conn, skip_routine, _T0, trigger="schedule", worker_id=_WORKER, now=_T0
        )
        assert ok and bad and skip
        done = _T0 + timedelta(minutes=3)

        assert await store.finish_run(
            conn, ok, "succeeded", result={"purged": 3, "swept": 0}, now=done
        )
        assert await store.finish_run(
            conn,
            bad,
            "failed",
            error=RuntimeError("Nutzer max@example.com nicht gefunden"),
            now=done,
        )
        assert await store.finish_run(conn, skip, "skipped", now=done)
        # Zweiter Abschluss ist ein No-op.
        assert not await store.finish_run(conn, ok, "failed", now=done)

        ok_run = await store.last_run(conn, ok_routine)
        assert ok_run is not None
        assert ok_run.status == "succeeded"
        assert ok_run.result == {"purged": 3, "swept": 0}
        assert ok_run.finished_at == done
        assert ok_run.error_class is None

        bad_run = await store.last_run(conn, bad_routine)
        assert bad_run is not None
        assert bad_run.status == "failed"
        # Nur der Klassenname, nie die Meldung mit Daten.
        assert bad_run.error_class == "RuntimeError"
        stored = await conn.fetchval(
            "SELECT row_to_json(r)::text FROM routine_run r WHERE id = $1", bad
        )
        assert "example.com" not in stored

        skip_run = await store.last_run(conn, skip_routine)
        assert skip_run is not None and skip_run.status == "skipped"

    _in_schema(body)


def test_finish_guards_status_error_and_result() -> None:
    routine = _routine()

    async def body(conn: asyncpg.Connection) -> None:
        run_id = await store.claim_slot(conn, routine, _T0, trigger="cli", worker_id=_WORKER)
        assert run_id is not None
        with pytest.raises(ValueError, match="Abschluss-Status"):
            await store.finish_run(conn, run_id, "running")  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="failed"):
            await store.finish_run(conn, run_id, "succeeded", error=RuntimeError())
        with pytest.raises(ValueError, match="Zaehler"):
            await store.finish_run(
                conn,
                run_id,
                "succeeded",
                result={"note": "text"},  # type: ignore[dict-item]
            )
        with pytest.raises(ValueError, match="Zaehler"):
            await store.finish_run(conn, run_id, "succeeded", result={"flag": True})
        run = await store.last_run(conn, routine)
        assert run is not None and run.status == "running"

    _in_schema(body)


def test_db_checks_reject_non_counter_result_and_misplaced_error_class() -> None:
    routine = _routine()

    async def body(conn: asyncpg.Connection) -> None:
        insert = (
            "INSERT INTO routine_run (routine, slot, trigger, status, finished_at, "
            "result, error_class, worker_id) VALUES ($1, $2, 'cli', $3, $4, "
            "$5::text::jsonb, $6, 'w')"
        )
        bad_rows = [
            ("succeeded", _T0, '{"user": "max@example.com"}', None),
            ("succeeded", _T0, "[1, 2]", None),
            ("succeeded", _T0, None, "RuntimeError"),
            ("failed", _T0, None, "kaputt mit Leerzeichen"),
            ("running", _T0, None, None),  # running mit finished_at
            ("succeeded", None, None, None),  # Abschluss ohne finished_at
        ]
        for i, (status, finished, result, error_class) in enumerate(bad_rows):
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    insert,
                    routine,
                    _T0 + timedelta(seconds=i),
                    status,
                    finished,
                    result,
                    error_class,
                )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO routine_run (routine, slot, trigger, worker_id) "
                "VALUES ($1, $2, 'cron', 'w')",
                routine,
                _T0,
            )
        await conn.execute(
            insert, routine, _T0, "succeeded", _T0, '{"purged": 2, "ratio": 0.5}', None
        )

    _in_schema(body)


# --- Heartbeat und Abandoned -------------------------------------------------


def test_mark_abandoned_only_after_threshold() -> None:
    stale, fresh = _routine(), _routine()

    async def body(conn: asyncpg.Connection) -> None:
        stale_id = await store.claim_slot(
            conn, stale, _T0, trigger="schedule", worker_id=_WORKER, now=_T0
        )
        fresh_id = await store.claim_slot(
            conn, fresh, _T0, trigger="schedule", worker_id=_WORKER, now=_T0
        )
        assert stale_id and fresh_id

        # Genau auf der Schwelle: noch nicht abgebrochen.
        at_threshold = _T0 + RUN_ABANDONED_AFTER
        assert await store.mark_abandoned(conn, now=at_threshold) == []

        # Heartbeat fuer `fresh` kurz vor Ablauf schiebt dessen Grenze.
        assert await store.touch_run(conn, fresh_id, now=_T0 + timedelta(minutes=4))

        past = at_threshold + timedelta(seconds=1)
        assert await store.mark_abandoned(conn, now=past) == [stale_id]

        stale_run = await store.last_run(conn, stale)
        assert stale_run is not None
        assert stale_run.status == "failed"
        assert stale_run.error_class == ABANDONED_ERROR_CLASS
        assert stale_run.finished_at == past
        fresh_run = await store.last_run(conn, fresh)
        assert fresh_run is not None and fresh_run.status == "running"

        # Ein abgebrochener Lauf laesst sich nicht mehr abschliessen oder
        # auffrischen; ein zweiter Sweep findet ihn nicht erneut.
        assert not await store.finish_run(conn, stale_id, "succeeded", now=past)
        assert not await store.touch_run(conn, stale_id, now=past)
        assert await store.mark_abandoned(conn, now=past) == []

    _in_schema(body)


def test_mark_abandoned_ignores_finished_runs() -> None:
    routine = _routine()

    async def body(conn: asyncpg.Connection) -> None:
        run_id = await store.claim_slot(
            conn, routine, _T0, trigger="schedule", worker_id=_WORKER, now=_T0
        )
        assert run_id
        await store.finish_run(conn, run_id, "succeeded", result={"n": 1}, now=_T0)
        assert await store.mark_abandoned(conn, now=_T0 + timedelta(days=1)) == []

    _in_schema(body)


def test_worker_heartbeat_upsert() -> None:
    async def body(conn: asyncpg.Connection) -> None:
        assert await store.worker_seen_at(conn) is None
        await store.record_worker_heartbeat(conn, worker_id="host-a:1", version="1.0.0", now=_T0)
        later = _T0 + timedelta(seconds=30)
        await store.record_worker_heartbeat(conn, worker_id="host-a:1", version="1.0.1", now=later)
        await store.record_worker_heartbeat(conn, worker_id="host-b:2", version="1.0.1", now=_T0)

        rows = await conn.fetch("SELECT worker_id, seen_at, version FROM worker_heartbeat")
        by_id = {r["worker_id"]: r for r in rows}
        assert set(by_id) == {"host-a:1", "host-b:2"}
        assert by_id["host-a:1"]["seen_at"] == later
        assert by_id["host-a:1"]["version"] == "1.0.1"
        assert await store.worker_seen_at(conn, "host-b:2") == _T0
        assert await store.worker_seen_at(conn) == later
        assert await store.worker_seen_at(conn, "unknown:9") is None

    _in_schema(body)


def test_default_worker_id_is_host_and_pid() -> None:
    host, _, pid = store.default_worker_id().rpartition(":")
    assert host
    assert pid.isdigit()


# --- Lesen -------------------------------------------------------------------


def test_last_run_and_last_success_per_routine() -> None:
    routine, other = _routine(), _routine()

    async def body(conn: asyncpg.Connection) -> None:
        assert await store.last_run(conn, routine) is None
        assert await store.last_success(conn, routine) is None

        first = await store.claim_slot(
            conn, routine, _T0, trigger="schedule", worker_id=_WORKER, now=_T0
        )
        assert first
        await store.finish_run(conn, first, "succeeded", result={"n": 1}, now=_T0)
        day2 = _T0 + timedelta(days=1)
        second = await store.claim_slot(
            conn, routine, day2, trigger="schedule", worker_id=_WORKER, now=day2
        )
        assert second
        await store.finish_run(conn, second, "failed", error=TimeoutError(), now=day2)
        other_id = await store.claim_slot(
            conn, other, _T0, trigger="cli", worker_id=_WORKER, now=_T0
        )

        latest = await store.last_run(conn, routine)
        success = await store.last_success(conn, routine)
        assert latest is not None and latest.id == second
        assert latest.error_class == "TimeoutError"
        assert success is not None and success.id == first

        runs = await store.latest_runs(conn)
        assert runs[routine].id == second
        assert runs[other].id == other_id
        successes = await store.latest_successes(conn)
        assert successes[routine].id == first
        assert other not in successes

    _in_schema(body)


# --- Advisory-Lock -----------------------------------------------------------


def test_second_advisory_lock_attempt_returns_false() -> None:
    routine = _routine()

    async def body(_: asyncpg.Connection) -> None:
        url = get_settings().database_url
        a = await asyncpg.connect(url)
        b = await asyncpg.connect(url)
        try:
            assert await store.try_advisory_lock(a, routine) is True
            assert await store.try_advisory_lock(b, routine) is False
            # Eine andere Routine ist unabhaengig.
            assert await store.try_advisory_lock(b, routine + "-x") is True
            assert await store.release_advisory_lock(b, routine + "-x") is True
            # Nur der Halter kann freigeben.
            assert await store.release_advisory_lock(b, routine) is False
            assert await store.release_advisory_lock(a, routine) is True
            assert await store.try_advisory_lock(b, routine) is True
            assert await store.release_advisory_lock(b, routine) is True
        finally:
            await a.close()
            await b.close()

    _in_schema(body)


def test_routine_lock_context_uses_dedicated_connection() -> None:
    routine = _routine()

    async def body(conn: asyncpg.Connection) -> None:
        async with store.routine_lock(routine) as held:
            assert held is True
            # Die Test-Verbindung ist eine andere Session: der Lock ist belegt.
            assert await store.try_advisory_lock(conn, routine) is False
            async with store.routine_lock(routine) as second:
                assert second is False
        # Nach dem Verlassen frei.
        assert await store.try_advisory_lock(conn, routine) is True
        async with store.routine_lock(routine) as blocked:
            assert blocked is False
        assert await store.release_advisory_lock(conn, routine) is True

    _in_schema(body)


# --- Grants und Waechter -----------------------------------------------------


def test_app_role_may_select_but_not_write() -> None:
    routine = _routine()

    async def body(owner: asyncpg.Connection) -> None:
        run_id = await store.claim_slot(
            owner, routine, _T0, trigger="schedule", worker_id=_WORKER, now=_T0
        )
        await store.record_worker_heartbeat(owner, worker_id=_WORKER, version="1", now=_T0)
        await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
        app = await asyncpg.connect(
            get_settings().database_url, user="who2be_app", password=_APP_PASSWORD
        )
        try:
            assert await app.fetchval("SELECT count(*) FROM routine_run") == 1
            assert await app.fetchval("SELECT count(*) FROM worker_heartbeat") == 1
            writes = [
                (
                    "INSERT INTO routine_run (routine, slot, trigger, worker_id) "
                    "VALUES ($1, $2, 'manual', 'w')",
                    (routine, _T0 + timedelta(hours=1)),
                ),
                ("UPDATE routine_run SET status = 'skipped' WHERE id = $1", (run_id,)),
                ("DELETE FROM routine_run WHERE id = $1", (run_id,)),
                (
                    "INSERT INTO worker_heartbeat (worker_id, version) VALUES ('x:1', '1')",
                    (),
                ),
                ("UPDATE worker_heartbeat SET version = '2'", ()),
                ("DELETE FROM worker_heartbeat", ()),
            ]
            for sql, args in writes:
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await app.execute(sql, *args)
        finally:
            await app.close()
        assert await owner.fetchval("SELECT status FROM routine_run WHERE id = $1", run_id) == (
            "running"
        )

    _in_schema(body)


def test_org_transfer_classifies_worker_tables_as_global() -> None:
    async def body(conn: asyncpg.Connection) -> None:
        schema = await org_transfer.load_schema(conn)
        assert schema.tables["routine_run"].mode == "skip"
        assert schema.tables["worker_heartbeat"].mode == "skip"

    _in_schema(body)


def test_migration_0102_is_idempotent() -> None:
    async def body(conn: asyncpg.Connection) -> None:
        sql = (MIGRATIONS_DIR / "0102_routine_run.sql").read_text(encoding="utf-8")
        routine = _routine()
        await store.claim_slot(conn, routine, _T0, trigger="cli", worker_id=_WORKER)
        async with conn.transaction():
            await conn.execute(sql)
        assert await conn.fetchval("SELECT count(*) FROM routine_run") == 1

    _in_schema(body)
