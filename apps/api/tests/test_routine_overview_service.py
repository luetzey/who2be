"""Routinen-Uebersicht fuer Betreiber (ADR-0057 §7, §8 Schritt 2, Paket P4b).

Gegen echtes Postgres in einem isolierten Schema. Die Routinen stehen in einer
eigenen Test-`Registry` mit Zufallsnamen; die Prozess-Registry bleibt
unberuehrt. Die Laeufe schreibt der Test wie der Worker ueber die
Owner-Verbindung (`store`), gelesen wird ueber die App-Rolle `who2be_app`
(nur SELECT, Migration 0102) — so wie der Betreiber-Endpunkt liest.

Belegt:

- mehrere Laeufe je Routine: der juengste gewinnt, `last_success_at` ist das
  Ende des juengsten Erfolgs, Dauer und Zaehler kommen mit;
- Routine ohne Lauf: kein letzter Lauf, kein Erfolg, aber ein Termin;
- Env-Override sichtbar (`source='env'`, wirksamer Zeitplan), abgeschaltete
  Routine und abgeschalteter Worker haben keinen Termin;
- externer Zeitplan erkannt (CLI-Laeufe an zwei aufeinanderfolgenden Tagen);
- kein Heartbeat → `worker_last_seen_at` ist `None`, sonst der juengste;
- Laeufe nicht registrierter Routinen erscheinen nicht.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from who2be_api.core.config import get_settings
from who2be_api.services.routine_overview_service import routines_overview
from who2be_api.testing.isolated_schema import isolated_schema
from who2be_api.worker import store
from who2be_api.worker.registry import Registry, RoutineContext
from who2be_api.worker.schedule import ScheduleError, schedule_env_key

pytestmark = pytest.mark.integration

# Test-only Passwort fuer die App-Rolle (per format() in ALTER ROLE eingesetzt).
_APP_PASSWORD = "routine_overview_secret"  # noqa: S105 — Test-Fixture, kein echtes Secret

#: Referenzzeit: Freitag 2026-11-06, 10:00 UTC.
_NOW = datetime(2026, 11, 6, 10, 0, tzinfo=UTC)
_WORKER = "test-host:1"


async def _noop(ctx: RoutineContext) -> dict[str, int]:
    return {}


def _registry(*names: str, schedule: str = "30 3 * * *") -> Registry:
    reg = Registry()
    for name in names:
        reg.register(name, schedule=schedule, timeout=timedelta(minutes=5))(_noop)
    return reg


def _name(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


def _with_app_conn(
    seed: Callable[[asyncpg.Connection], Awaitable[None]],
    check: Callable[[asyncpg.Connection], Awaitable[None]],
) -> None:
    """`seed` auf der Owner-Verbindung, `check` auf der App-Rolle — im Wegwerf-Schema."""
    with isolated_schema("routine_overview"):
        url = get_settings().database_url

        async def _run() -> None:
            owner = await asyncpg.connect(url)
            try:
                await seed(owner)
                await owner.execute(f"ALTER ROLE who2be_app WITH PASSWORD '{_APP_PASSWORD}'")
                app = await asyncpg.connect(url, user="who2be_app", password=_APP_PASSWORD)
                try:
                    await check(app)
                finally:
                    await app.close()
            finally:
                await owner.close()

        asyncio.run(_run())


async def _run(
    conn: asyncpg.Connection,
    routine: str,
    started: datetime,
    status: store.FinalStatus,
    *,
    trigger: store.RunTrigger = "schedule",
    duration: timedelta = timedelta(seconds=2),
    result: dict[str, int] | None = None,
    error: BaseException | None = None,
) -> None:
    run_id = await store.claim_slot(
        conn, routine, started, trigger=trigger, worker_id=_WORKER, now=started
    )
    assert run_id is not None
    await store.finish_run(conn, run_id, status, result=result, error=error, now=started + duration)


def test_latest_run_wins_and_routine_without_run() -> None:
    busy, idle, gone = _name("busy"), _name("idle"), _name("gone")
    reg = _registry(busy, idle)
    day1 = datetime(2026, 11, 4, 3, 30, tzinfo=UTC)
    day2 = datetime(2026, 11, 5, 3, 30, tzinfo=UTC)
    day3 = datetime(2026, 11, 6, 3, 30, tzinfo=UTC)

    async def seed(conn: asyncpg.Connection) -> None:
        await _run(conn, busy, day1, "succeeded", result={"deleted": 1})
        await _run(
            conn, busy, day2, "succeeded", duration=timedelta(seconds=7), result={"deleted": 4}
        )
        await _run(
            conn,
            busy,
            day3,
            "failed",
            duration=timedelta(milliseconds=1500),
            error=RuntimeError("geheim"),
        )
        await _run(conn, gone, day3, "succeeded")

    async def check(app: asyncpg.Connection) -> None:
        overview = await routines_overview(app, routines=reg, env={}, now=_NOW)
        assert [r.name for r in overview.routines] == sorted([busy, idle])
        by_name = {r.name: r for r in overview.routines}

        status = by_name[busy]
        assert status.schedule == "30 3 * * *"
        assert status.enabled is True
        assert status.source == "code"
        assert status.last_run is not None
        assert status.last_run.status == "failed"
        assert status.last_run.trigger == "schedule"
        assert status.last_run.started_at == day3
        assert status.last_run.duration_ms == 1500
        assert status.last_run.error_class == "RuntimeError"
        assert status.last_run.result is None
        # Letzter Erfolg ist der vom Vortag, nicht der fehlgeschlagene Lauf.
        assert status.last_success_at == day2 + timedelta(seconds=7)
        assert status.next_run_at == datetime(2026, 11, 7, 3, 30, tzinfo=UTC)
        assert status.external_schedule_detected is False

        empty = by_name[idle]
        assert empty.last_run is None
        assert empty.last_success_at is None
        assert empty.next_run_at == datetime(2026, 11, 7, 3, 30, tzinfo=UTC)

        assert overview.worker_last_seen_at is None

    _with_app_conn(seed, check)


def test_running_run_has_no_duration_and_counters_come_along() -> None:
    name = _name("live")
    reg = _registry(name)
    started = _NOW - timedelta(minutes=1)

    async def seed(conn: asyncpg.Connection) -> None:
        await _run(conn, name, started - timedelta(days=1), "succeeded", result={"rows": 3})
        assert await store.claim_slot(
            conn, name, started, trigger="manual", worker_id=_WORKER, now=started
        )

    async def check(app: asyncpg.Connection) -> None:
        (status,) = (await routines_overview(app, routines=reg, env={}, now=_NOW)).routines
        assert status.last_run is not None
        assert status.last_run.status == "running"
        assert status.last_run.trigger == "manual"
        assert status.last_run.duration_ms is None
        assert status.last_success_at == started - timedelta(days=1) + timedelta(seconds=2)

    _with_app_conn(seed, check)


def test_env_override_and_disabled_routines_are_visible() -> None:
    moved, off = _name("moved"), _name("off")
    reg = _registry(moved, off)
    env = {
        schedule_env_key(moved): "@every 15m",
        f"WHO2BE_ROUTINE_{off.upper().replace('-', '_')}_ENABLED": "false",
    }

    async def seed(conn: asyncpg.Connection) -> None:
        await store.record_worker_heartbeat(
            conn, worker_id="a:1", version="1", now=_NOW - timedelta(minutes=9)
        )
        await store.record_worker_heartbeat(
            conn, worker_id="b:2", version="1", now=_NOW - timedelta(seconds=20)
        )

    async def check(app: asyncpg.Connection) -> None:
        overview = await routines_overview(app, routines=reg, env=env, now=_NOW)
        by_name = {r.name: r for r in overview.routines}
        assert by_name[moved].source == "env"
        assert by_name[moved].schedule == "@every 15m"
        assert by_name[moved].next_run_at == _NOW + timedelta(minutes=15)
        assert by_name[off].source == "env"
        assert by_name[off].enabled is False
        assert by_name[off].next_run_at is None
        # Juengster Heartbeat aller Worker.
        assert overview.worker_last_seen_at == _NOW - timedelta(seconds=20)

        # Worker global aus: Routinen bleiben „an“, aber es gibt keinen Termin.
        paused = await routines_overview(
            app, routines=reg, env={**env, "WHO2BE_WORKER_ENABLED": "false"}, now=_NOW
        )
        assert all(r.next_run_at is None for r in paused.routines)
        assert {r.name: r.enabled for r in paused.routines} == {moved: True, off: False}

        # Ungueltiger Override: harter Fehler wie beim Worker-Start.
        with pytest.raises(ScheduleError):
            await routines_overview(
                app, routines=reg, env={schedule_env_key(moved): "kaputt"}, now=_NOW
            )

    _with_app_conn(seed, check)


def test_external_schedule_detected() -> None:
    cron, once = _name("cron"), _name("once")
    reg = _registry(cron, once)

    async def seed(conn: asyncpg.Connection) -> None:
        # Host-Cron: CLI-Laeufe an zwei aufeinanderfolgenden Tagen (einer skipped).
        await _run(conn, cron, datetime(2026, 11, 4, 3, 30, tzinfo=UTC), "succeeded", trigger="cli")
        await _run(conn, cron, datetime(2026, 11, 5, 3, 30, tzinfo=UTC), "skipped", trigger="cli")
        # Ein einzelner Notfall-Lauf ist kein Zeitplan.
        await _run(conn, once, datetime(2026, 11, 5, 9, 0, tzinfo=UTC), "succeeded", trigger="cli")

    async def check(app: asyncpg.Connection) -> None:
        overview = await routines_overview(app, routines=reg, env={}, now=_NOW)
        flags = {r.name: r.external_schedule_detected for r in overview.routines}
        assert flags == {cron: True, once: False}

    _with_app_conn(seed, check)
