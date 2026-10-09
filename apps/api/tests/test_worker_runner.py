"""Runner und CLI des Workers (ADR-0057 §3/§5/§6, P1c).

Gegen echtes Postgres in einem isolierten Schema. Die Routinen sind
Test-Routinen in einer eigenen `Registry`, die nur hier existiert; die
Prozess-Registry `REGISTRY` bleibt unberuehrt. Die Uhr ist fest bzw. vom Test
gestellt, nur Timeout und Heartbeat-Takt laufen in echten Sekundenbruchteilen.

Belegt (die entscheidungstragenden Faelle aus ADR §9, zusammen mit
`test_worker_store.py` und `test_worker_schedule.py`):

- zwei Runner nebenlaeufig auf denselben Slot → genau eine `succeeded`-Zeile,
- Lock belegt (CLI-/manueller Lauf aktiv) → `skipped`,
- Timeout → `failed`/`TimeoutError`, Ausnahme → nur Klassenname,
- `catch_up` laeuft beim Start genau einmal, nicht je verpasstem Slot,
- `WHO2BE_WORKER_ENABLED=false` belegt nichts, meldet aber Heartbeat,
- `check` mit frischem und altem Heartbeat,
- `run-once` weicht bei belegtem Slot um 1 µs aus (PM-W5),
- SIGTERM-Semantik: erste Anforderung laesst die Routine enden, zweite bricht
  sie als `WorkerShutdown` ab.

Advisory-Locks gelten datenbankweit; Routinen-Namen tragen deshalb einen
Zufallsanteil.
"""

from __future__ import annotations

import asyncio
import secrets
import socket
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.testing.isolated_schema import isolated_schema
from who2be_api.worker import cli, store
from who2be_api.worker.registry import Registry, RoutineContext, RoutineFn
from who2be_api.worker.runner import SLOT_DODGE, TICK_INTERVAL, Runner

pytestmark = pytest.mark.integration

_T0 = datetime(2026, 11, 6, 3, 30, tzinfo=UTC)
#: Auf dem Stundenraster (Intervall-Slots liegen ab der Epoche auf :00).
_H0 = datetime(2026, 11, 6, 3, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)
FAST = timedelta(milliseconds=50)


def _name() -> str:
    return f"r-{secrets.token_hex(4)}"


class Clock:
    """Stellbare Uhr fuer den Runner."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _registry(
    name: str,
    fn: RoutineFn,
    *,
    schedule: str | timedelta = HOUR,
    timeout: timedelta = timedelta(seconds=10),
    catch_up: bool = False,
) -> Registry:
    reg = Registry()
    reg.register(name, schedule=schedule, timeout=timeout, catch_up=catch_up)(fn)
    return reg


def _counting() -> tuple[RoutineFn, list[RoutineContext]]:
    calls: list[RoutineContext] = []

    async def fn(ctx: RoutineContext) -> dict[str, int]:
        calls.append(ctx)
        # Die Routine bekommt eine eigene, nutzbare Verbindung.
        assert await ctx.conn.fetchval("SELECT 1") == 1
        return {"rows": len(calls)}

    return fn, calls


def _runner(reg: Registry, clock: Clock, **kwargs: object) -> Runner:
    kwargs.setdefault("env", {})
    return Runner(
        reg,
        dsn=get_settings().database_url,
        clock=clock,
        run_heartbeat_interval=FAST,
        tick_interval=FAST,
        **kwargs,  # type: ignore[arg-type]
    )


def _in_schema(body: Callable[[asyncpg.Connection], Awaitable[None]]) -> None:
    with isolated_schema("worker_runner"):
        url = get_settings().database_url

        async def _run() -> None:
            conn = await asyncpg.connect(url)
            try:
                await body(conn)
            finally:
                await conn.close()

        asyncio.run(_run())


async def _rows(conn: asyncpg.Connection, routine: str) -> list[asyncpg.Record]:
    rows: list[asyncpg.Record] = await conn.fetch(
        "SELECT slot, trigger, status, error_class, result::text AS result "
        "FROM routine_run WHERE routine = $1 ORDER BY slot",
        routine,
    )
    return rows


def test_tick_interval_is_about_thirty_seconds() -> None:
    assert TICK_INTERVAL == timedelta(seconds=30)


# --- Genau ein Lauf ------------------------------------------------------------


def test_two_runners_on_same_slot_yield_exactly_one_succeeded_row() -> None:
    name = _name()
    calls: list[str] = []

    async def slow(ctx: RoutineContext) -> dict[str, int]:
        calls.append(ctx.worker_id)
        await asyncio.sleep(0.3)
        return {"rows": 1}

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, slow)
        clock = Clock(_T0)
        url = get_settings().database_url
        a_conn, b_conn = await asyncpg.connect(url), await asyncpg.connect(url)
        try:
            a = _runner(reg, clock, worker_id="host-a:1")
            b = _runner(reg, clock, worker_id="host-b:2")
            routine = reg.get(name)
            results = await asyncio.gather(
                a.execute(a_conn, routine, _T0, "schedule"),
                b.execute(b_conn, routine, _T0, "schedule"),
            )
        finally:
            await a_conn.close()
            await b_conn.close()
        winners = [r for r in results if r is not None]
        assert len(winners) == 1 and winners[0].status == "succeeded"
        assert len(calls) == 1
        rows = await _rows(conn, name)
        assert [(r["status"], r["trigger"]) for r in rows] == [("succeeded", "schedule")]

    _in_schema(body)


def test_tick_runs_due_slot_once_and_records_counters() -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        clock = Clock(_T0)
        runner = _runner(_registry(name, fn, schedule="30 3 * * *"), clock)
        assert await runner.start(conn) == []  # ohne catch_up kein Nachholen
        # Erster Tick nach dem Slot 03:30 am naechsten Tag.
        clock.now = _T0 + timedelta(days=1, seconds=5)
        first = await runner.tick(conn)
        assert [(o.status, o.slot) for o in first] == [("succeeded", _T0 + timedelta(days=1))]
        # Weitere Ticks im selben Slot belegen nichts.
        clock.now += timedelta(seconds=30)
        assert await runner.tick(conn) == []
        assert len(calls) == 1
        assert calls[0].slot == _T0 + timedelta(days=1)
        assert calls[0].trigger == "schedule"
        rows = await _rows(conn, name)
        assert len(rows) == 1 and rows[0]["result"] == '{"rows": 1}'

    _in_schema(body)


def test_slot_before_start_is_not_run_without_catch_up() -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        clock = Clock(_T0 + timedelta(minutes=10))
        runner = _runner(_registry(name, fn, schedule="30 3 * * *"), clock)
        await runner.start(conn)
        assert await runner.tick(conn) == []
        assert calls == []
        assert await _rows(conn, name) == []

    _in_schema(body)


def test_tick_requires_start() -> None:
    fn, _ = _counting()
    runner = Runner(_registry(_name(), fn), dsn="postgresql://unused", env={})
    with pytest.raises(RuntimeError, match="start"):
        asyncio.run(runner.tick(None))


# --- Lock, Timeout, Fehler ------------------------------------------------------


def test_held_lock_ends_run_as_skipped() -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        runner = _runner(_registry(name, fn), Clock(_T0))
        # Ein CLI-Lauf haelt denselben Lock (ADR §8).
        async with store.routine_lock(name) as held:
            assert held
            outcome = await runner.execute(conn, runner.registry.get(name), _T0, "schedule")
        assert outcome is not None and outcome.status == "skipped"
        assert calls == []
        rows = await _rows(conn, name)
        assert [(r["status"], r["error_class"]) for r in rows] == [("skipped", None)]
        # Der Lock wurde vom Runner nicht uebernommen und ist wieder frei.
        assert await store.try_advisory_lock(conn, name)
        assert await store.release_advisory_lock(conn, name)

    _in_schema(body)


def test_timeout_ends_run_as_failed() -> None:
    name = _name()

    async def hangs(ctx: RoutineContext) -> dict[str, int]:
        await asyncio.sleep(30)
        return {"rows": 0}

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, hangs, timeout=timedelta(milliseconds=200))
        runner = _runner(reg, Clock(_T0))
        outcome = await runner.execute(conn, reg.get(name), _T0, "schedule")
        assert outcome is not None
        assert (outcome.status, outcome.error_class) == ("failed", "TimeoutError")
        rows = await _rows(conn, name)
        assert [(r["status"], r["error_class"]) for r in rows] == [("failed", "TimeoutError")]
        # Lock nach dem Lauf frei.
        async with store.routine_lock(name) as held:
            assert held

    _in_schema(body)


def test_exception_and_non_counter_result_store_only_class_name() -> None:
    raising, bad_result = _name(), _name()

    async def boom(ctx: RoutineContext) -> dict[str, int]:
        raise LookupError("Nutzer max@example.com fehlt")

    async def text(ctx: RoutineContext) -> dict[str, int]:
        return {"note": "max@example.com"}  # type: ignore[dict-item]

    async def body(conn: asyncpg.Connection) -> None:
        reg = Registry()
        reg.register(raising, schedule=HOUR, timeout=HOUR)(boom)
        reg.register(bad_result, schedule=HOUR, timeout=HOUR)(text)
        runner = _runner(reg, Clock(_T0))
        a = await runner.execute(conn, reg.get(raising), _T0, "schedule")
        b = await runner.execute(conn, reg.get(bad_result), _T0, "schedule")
        assert a is not None and a.error_class == "LookupError"
        assert b is not None and b.error_class == "InvalidRoutineResult"
        dump = await conn.fetchval(
            "SELECT string_agg(row_to_json(r)::text, ' ') FROM routine_run r "
            "WHERE routine = ANY($1::text[])",
            [raising, bad_result],
        )
        assert "example.com" not in dump

    _in_schema(body)


def test_run_heartbeat_refreshes_run_and_worker_during_routine() -> None:
    name = _name()
    clock = Clock(_T0)

    async def slow(ctx: RoutineContext) -> dict[str, int]:
        # Uhr vorstellen; der Heartbeat-Takt (50 ms) traegt sie in die DB.
        clock.now = _T0 + timedelta(minutes=4)
        await asyncio.sleep(0.4)
        return {"rows": 1}

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, slow)
        runner = _runner(reg, clock, worker_id="beat-host:7")
        seen: list[datetime] = []

        async def watch() -> None:
            # Waehrend des Laufs: heartbeat_at wandert mit der Uhr.
            watcher = await asyncpg.connect(get_settings().database_url)
            try:
                for _ in range(40):
                    await asyncio.sleep(0.02)
                    value = await watcher.fetchval(
                        "SELECT heartbeat_at FROM routine_run "
                        "WHERE routine = $1 AND status = 'running'",
                        name,
                    )
                    if value is not None:
                        seen.append(value)
            finally:
                await watcher.close()

        await asyncio.gather(runner.execute(conn, reg.get(name), _T0, "schedule"), watch())
        assert _T0 + timedelta(minutes=4) in seen
        assert await store.worker_seen_at(conn, "beat-host:7") == _T0 + timedelta(minutes=4)

    _in_schema(body)


def test_tick_marks_abandoned_runs_and_records_heartbeat() -> None:
    name, other = _name(), _name()
    fn, _ = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        stale = await store.claim_slot(
            conn, other, _T0, trigger="schedule", worker_id="dead:1", now=_T0
        )
        clock = Clock(_T0 + timedelta(minutes=6))
        runner = _runner(_registry(name, fn), clock, worker_id="live:1")
        await runner.start(conn)
        run = await store.last_run(conn, other)
        assert run is not None and run.id == stale
        assert (run.status, run.error_class) == ("failed", store.ABANDONED_ERROR_CLASS)
        clock.now += timedelta(seconds=30)
        await runner.tick(conn)
        assert await store.worker_seen_at(conn, "live:1") == clock.now

    _in_schema(body)


# --- catch_up ---------------------------------------------------------------


def test_catch_up_runs_exactly_once_not_per_missed_slot() -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, fn, catch_up=True)
        # Letzter Erfolg im Slot 03:00, Start um 08:10: fuenf Slots verpasst
        # (Stundenraster ab der Epoche).
        first = _T0 - timedelta(minutes=30)
        done = await store.claim_slot(
            conn, name, first, trigger="schedule", worker_id="old:1", now=_T0
        )
        assert done
        await store.finish_run(conn, done, "succeeded", result={"rows": 0}, now=_T0)
        clock = Clock(_T0 + timedelta(hours=4, minutes=40))
        runner = _runner(reg, clock)
        outcomes = await runner.start(conn)
        assert [(o.status, o.slot) for o in outcomes] == [("succeeded", first + timedelta(hours=5))]
        # Tick im selben Slot und ein zweiter Start holen nichts mehr nach.
        assert await runner.tick(conn) == []
        assert await _runner(reg, clock).start(conn) == []
        assert len(calls) == 1
        assert calls[0].slot == first + timedelta(hours=5)
        assert len(await _rows(conn, name)) == 2

    _in_schema(body)


def test_catch_up_without_any_success_and_up_to_date_routine() -> None:
    fresh, never = _name(), _name()
    fresh_fn, fresh_calls = _counting()
    never_fn, never_calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        reg = Registry()
        reg.register(fresh, schedule=HOUR, timeout=HOUR, catch_up=True)(fresh_fn)
        reg.register(never, schedule=HOUR, timeout=HOUR, catch_up=True)(never_fn)
        slot = _H0 + timedelta(hours=1)
        done = await store.claim_slot(
            conn, fresh, slot, trigger="schedule", worker_id="old:1", now=slot
        )
        assert done
        await store.finish_run(conn, done, "succeeded", result={"rows": 0}, now=slot)
        outcomes = await _runner(reg, Clock(slot + timedelta(minutes=20))).start(conn)
        assert [o.routine for o in outcomes] == [never]
        assert fresh_calls == [] and len(never_calls) == 1

    _in_schema(body)


def test_catch_up_after_failed_slot_runs_once_at_start_time() -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, fn, catch_up=True)
        slot = _H0
        failed = await store.claim_slot(
            conn, name, slot, trigger="schedule", worker_id="old:1", now=slot
        )
        assert failed
        await store.finish_run(conn, failed, "failed", error=TimeoutError(), now=slot)
        start = slot + timedelta(minutes=20)
        outcomes = await _runner(reg, Clock(start)).start(conn)
        assert [(o.status, o.slot) for o in outcomes] == [("succeeded", start)]
        assert len(calls) == 1

    _in_schema(body)


def test_catch_up_skips_slot_still_running_elsewhere() -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, fn, catch_up=True)
        start = _H0 + timedelta(minutes=1)
        running = await store.claim_slot(
            conn, name, _H0, trigger="schedule", worker_id="other:1", now=start
        )
        assert running
        assert await _runner(reg, Clock(start)).start(conn) == []
        assert calls == []

    _in_schema(body)


# --- Abschalten -----------------------------------------------------------------


def test_worker_disabled_claims_nothing_but_records_heartbeat() -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, fn, catch_up=True)
        clock = Clock(_T0 + timedelta(minutes=1))
        runner = _runner(reg, clock, worker_id="off:1", env={"WHO2BE_WORKER_ENABLED": "false"})
        assert runner.enabled is False
        assert await runner.start(conn) == []
        clock.now += HOUR
        assert await runner.tick(conn) == []
        assert calls == []
        assert await _rows(conn, name) == []
        assert await store.worker_seen_at(conn, "off:1") == clock.now
        # Manuell nur mit --force.
        with pytest.raises(PermissionError):
            await runner.run_once(conn, name)
        outcome = await runner.run_once(conn, name, force=True)
        assert (outcome.status, outcome.trigger) == ("succeeded", "manual")

    _in_schema(body)


def test_routine_disabled_by_env_is_not_claimed() -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        key = f"WHO2BE_ROUTINE_{name.upper().replace('-', '_')}_ENABLED"
        clock = Clock(_T0)
        runner = _runner(_registry(name, fn, catch_up=True), clock, env={key: "false"})
        assert await runner.start(conn) == []
        clock.now += HOUR
        assert await runner.tick(conn) == []
        assert calls == []

    _in_schema(body)


# --- run-once (PM-W5) -------------------------------------------------------------


def test_run_once_dodges_occupied_slot_by_one_microsecond() -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, fn)
        # Ein geplanter Lauf belegt genau den Zeitpunkt des manuellen Starts.
        taken = await store.claim_slot(
            conn, name, _T0, trigger="schedule", worker_id="w:1", now=_T0
        )
        assert taken
        await store.finish_run(conn, taken, "succeeded", result={"rows": 0}, now=_T0)
        outcome = await _runner(reg, Clock(_T0)).run_once(conn, name)
        assert (outcome.status, outcome.trigger) == ("succeeded", "manual")
        assert outcome.slot == _T0 + SLOT_DODGE
        assert calls[0].trigger == "manual"
        rows = await _rows(conn, name)
        assert [(r["slot"], r["trigger"]) for r in rows] == [
            (_T0, "schedule"),
            (_T0 + SLOT_DODGE, "manual"),
        ]

    _in_schema(body)


# --- Herunterfahren -------------------------------------------------------------


def test_first_stop_lets_routine_finish_and_ends_loop() -> None:
    name = _name()
    started = asyncio.Event()

    async def slow(ctx: RoutineContext) -> dict[str, int]:
        started.set()
        await asyncio.sleep(0.3)
        return {"rows": 1}

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, slow, catch_up=True)
        runner = _runner(reg, Clock(_T0 + timedelta(minutes=1)))
        loop = asyncio.create_task(runner.run())
        await asyncio.wait_for(started.wait(), 5)
        runner.request_stop()
        await asyncio.wait_for(loop, 5)
        rows = await _rows(conn, name)
        assert [r["status"] for r in rows] == ["succeeded"]

    _in_schema(body)


def test_second_stop_aborts_routine_as_failed() -> None:
    name = _name()
    started = asyncio.Event()

    async def hangs(ctx: RoutineContext) -> dict[str, int]:
        started.set()
        await asyncio.sleep(30)
        return {"rows": 0}

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, hangs, timeout=timedelta(minutes=5))
        runner = _runner(reg, Clock(_T0))
        run = asyncio.create_task(runner.execute(conn, reg.get(name), _T0, "schedule"))
        await asyncio.wait_for(started.wait(), 5)
        runner.request_stop()
        await asyncio.sleep(0.1)
        assert not run.done()
        runner.request_stop()
        outcome = await asyncio.wait_for(run, 5)
        assert outcome is not None
        assert (outcome.status, outcome.error_class) == ("failed", "WorkerShutdown")
        # Nach dem Stopp belegt ein Tick nichts mehr.
        runner.started_at = _T0
        assert await runner.tick(conn) == []

    _in_schema(body)


# --- CLI ------------------------------------------------------------------------


def test_check_with_fresh_and_old_heartbeat() -> None:
    async def body(conn: asyncpg.Connection) -> None:
        now = datetime.now(UTC)
        host = f"host-{secrets.token_hex(3)}"
        assert not await cli.host_heartbeat_fresh(conn, host, now=now)
        await store.record_worker_heartbeat(
            conn, worker_id=f"{host}:1", version="t", now=now - timedelta(minutes=3)
        )
        assert not await cli.host_heartbeat_fresh(conn, host, now=now)
        await store.record_worker_heartbeat(
            conn, worker_id=f"{host}:1", version="t", now=now - timedelta(minutes=1)
        )
        assert await cli.host_heartbeat_fresh(conn, host, now=now)
        # Ein anderer Host mit gleichem Praefix zaehlt nicht.
        assert not await cli.host_heartbeat_fresh(conn, host[:-1], now=now)

        # Der echte Befehl gegen den Hostnamen dieses Prozesses.
        own = socket.gethostname()
        await conn.execute("DELETE FROM worker_heartbeat")
        await store.record_worker_heartbeat(
            conn, worker_id=f"{own}:9", version="t", now=now - timedelta(minutes=3)
        )
        assert await asyncio.to_thread(cli.main, ["check"]) == 1
        await store.record_worker_heartbeat(conn, worker_id=f"{own}:9", version="t")
        assert await asyncio.to_thread(cli.main, ["check"]) == 0

    _in_schema(body)


def test_cli_list_and_run_once(capsys: pytest.CaptureFixture[str]) -> None:
    name = _name()
    fn, calls = _counting()

    async def body(conn: asyncpg.Connection) -> None:
        reg = _registry(name, fn, schedule="30 3 * * *")
        assert await asyncio.to_thread(cli.main, ["list"], reg) == 0
        assert await asyncio.to_thread(cli.main, ["run-once", "nope"], reg) == 2
        assert await asyncio.to_thread(cli.main, ["run-once", name], reg) == 0
        assert len(calls) == 1
        rows = await _rows(conn, name)
        assert [(r["trigger"], r["status"]) for r in rows] == [("manual", "succeeded")]

    _in_schema(body)
    out = capsys.readouterr().out
    assert name in out and "30 3 * * *" in out and "succeeded" in out


def test_cli_rejects_invalid_override(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    name = _name()
    fn, _ = _counting()
    monkeypatch.setenv(f"WHO2BE_ROUTINE_{name.upper().replace('-', '_')}_SCHEDULE", "kaputt")
    assert cli.main(["list"], _registry(name, fn)) == 2
    assert "kaputt" in capsys.readouterr().err
