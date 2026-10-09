"""Routinen des Workers und CLIs ueber Store und Lock (ADR-0057 §4/§6/§8/§10, P2).

Belegt:

- Contract: `who2be-worker list` zeigt jede Routine aus `worker/routines.py`
  mit den dokumentierten Zeitplaenen (RUNBOOK/Cloud-Inbetriebnahme).
- Allowlist (§10): Jede Routine mit `touches_tablestore=True` erreicht
  Tabellen-Store-Dateien nur ueber karenzgeschuetzte Funktionen; jede andere
  Routine erreicht sie gar nicht. Ein Gegenbeispiel zeigt, dass die Pruefung
  greift.
- DB: CLI-Lauf waehrend eines Worker-Laufs → `skipped` (auch ueber den echten
  Entrypoint, Exit 0, klare Meldung); CLI-Startzeit auf einer Slotgrenze →
  Ausweichen um 1 µs statt Fehler (PM-W5); `routine-run-retention` loescht nur
  Zeilen aelter als 90 Tage; Erkennung des externen Zeitplans samt WARN-Zeile;
  `catch_up` holt nach, wenn der juengste Slot `skipped` ist (Reviewer-Nit P1c).
- Die CLI-Ausgaben `Purge: …`/`Retention: …` und `Gedaechtnis: …` bleiben.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import logging
import secrets
import textwrap
import types
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import asyncpg
import pytest

from who2be_api.core import memory_expiry, purge
from who2be_api.core.config import get_settings
from who2be_api.services.tablestore_provider import reset_table_store, set_table_store
from who2be_api.tablestore import TableStore
from who2be_api.testing.isolated_schema import isolated_schema
from who2be_api.worker import cli, routines, store
from who2be_api.worker.registry import REGISTRY, Registry, RoutineContext
from who2be_api.worker.runner import SLOT_DODGE, Runner
from who2be_api.worker.store import FinalStatus, RunTrigger

_T0 = datetime(2026, 11, 6, 3, 45, tzinfo=UTC)

#: Routinen dieses Pakets mit ihren dokumentierten Zeitplaenen.
_EXPECTED = {
    "purge": "30 3 * * *",
    "memory-expire": "45 3 * * *",
    "routine-run-retention": "15 4 * * *",
}


def _own_routines() -> list[str]:
    return [r.name for r in REGISTRY if r.fn.__module__ == routines.__name__]


# --- Contract ----------------------------------------------------------------


def test_worker_list_contains_every_routine_from_routines_module(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert sorted(_own_routines()) == sorted(_EXPECTED)
    assert cli.main(["list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    listed = {line.split()[0]: line for line in lines[1:]}
    for name, schedule in _EXPECTED.items():
        assert name in listed, name
        assert schedule in listed[name]


def test_worker_list_shows_env_source_for_override(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Akzeptanz P3b: gesetzter Override ⇒ SOURCE=env, leerer ⇒ Code-Zeitplan."""
    monkeypatch.setenv("WHO2BE_ROUTINE_PURGE_SCHEDULE", "0 4 * * *")
    monkeypatch.setenv("WHO2BE_ROUTINE_MEMORY_EXPIRE_SCHEDULE", "")
    monkeypatch.setenv("WHO2BE_ROUTINE_MEMORY_EXPIRE_ENABLED", "")
    assert cli.main(["list"]) == 0
    rows = {line.split()[0]: line.split() for line in capsys.readouterr().out.splitlines()[1:]}
    assert rows["purge"][-1] == "env"
    assert "0 4 * * *" in " ".join(rows["purge"])
    assert rows["memory-expire"][-1] == "code"
    assert _EXPECTED["memory-expire"] in " ".join(rows["memory-expire"])


def test_routine_attributes_match_adr() -> None:
    p = REGISTRY.get("purge")
    assert (p.timeout, p.catch_up, p.touches_tablestore) == (timedelta(hours=1), True, True)
    m = REGISTRY.get("memory-expire")
    assert (m.catch_up, m.touches_tablestore) == (True, False)
    r = REGISTRY.get("routine-run-retention")
    assert (r.catch_up, r.touches_tablestore) == (False, False)
    assert store.ROUTINE_RUN_RETENTION == timedelta(days=90)


def test_purge_counters_are_counters_only_and_round_trip() -> None:
    result = purge.PurgeResult(organizations=2, accounts=1, blobstore_skipped=True)
    counters = purge.purge_counters(result)
    assert all(isinstance(v, int) and not isinstance(v, bool) for v in counters.values())
    assert counters["blobstore_skipped"] == 1
    assert purge._from_counters(counters) == result


# --- Allowlist (ADR-0057 §10) ------------------------------------------------

#: Methoden des `TableStore`, die Dateien anlegen, schreiben oder loeschen.
_FILE_WRITING = frozenset(
    {
        "create_table",
        "drop_table",
        "insert_rows",
        "run_admin_sql",
        "reapply_category",
        "snapshot_to",
        "delete_area_store",
    }
)
#: Karenzgeschuetzte Funktionen (24-h-mtime-Karenz, ADR-0049-Nachtrag 2026-09-26):
#: der Sweep selbst und sein Datei-Helfer, der die Karenz prueft.
_GRACE_PROTECTED = frozenset(
    {
        "who2be_api.core.purge.cleanup_deleted_area_stores",
        "who2be_api.core.purge._remove_dangling_area_files",
    }
)


def _qualname(obj: object) -> str:
    return f"{obj.__module__}.{obj.__qualname__}"  # type: ignore[attr-defined]


def _resolve(node: ast.expr, scope: dict[str, object]) -> object | None:
    if isinstance(node, ast.Name):
        return scope.get(node.id)
    if isinstance(node, ast.Attribute):
        base = _resolve(node.value, scope)
        if isinstance(base, types.ModuleType | type):
            return getattr(base, node.attr, None)
    return None


def _ours(obj: object) -> bool:
    return (getattr(obj, "__module__", None) or "").startswith("who2be_api")


def _functions(obj: object) -> Iterator[Callable[..., object]]:
    """Zu verfolgende Funktionen: die Funktion selbst bzw. beim Konstruktor-
    Aufruf einer Klasse ihr `__init__`. Methoden-Aufrufe auf Objekten erfasst
    `tablestore_writers` ueber den Namen (`_FILE_WRITING`)."""
    fn = obj
    if inspect.isclass(obj):
        fn = vars(obj).get("__init__")
    if not inspect.isfunction(fn):
        return
    # Nur eigener Code; generierter Code (dataclass-`__init__`) hat keine Quelle.
    if not str(fn.__globals__.get("__name__", "")).startswith(("who2be_api", __name__)):
        return
    try:
        inspect.getsource(fn)
    except OSError:
        return
    yield fn


def tablestore_writers(entry: Callable[..., object]) -> set[str]:
    """Alle Funktionen im Aufrufgraph von `entry` (nur `who2be_api`), die eine
    dateischreibende `TableStore`-Methode aufrufen oder den Store holen."""
    seen: set[str] = set()
    writers: set[str] = set()
    todo: list[Callable[..., object]] = [entry]
    while todo:
        fn = todo.pop()
        name = _qualname(fn)
        if name in seen:
            continue
        seen.add(name)
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        scope = dict(fn.__globals__)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute) and node.func.attr in _FILE_WRITING:
                writers.add(name)
            target = _resolve(node.func, scope)
            if target is not None and _qualname(target).endswith(".get_table_store"):
                writers.add(name)
            if target is not None and _ours(target):
                todo.extend(_functions(target))
            # Funktionen als Argument (z. B. `replace(..., fn=x)`) ebenfalls.
            for arg in [*node.args, *(k.value for k in node.keywords)]:
                ref = _resolve(arg, scope)
                if ref is not None and _ours(ref):
                    todo.extend(_functions(ref))
    return writers


def test_tablestore_routines_call_only_grace_protected_functions() -> None:
    touching = [r for r in REGISTRY if r.touches_tablestore]
    assert [r.name for r in touching] == ["purge"]
    for r in REGISTRY:
        writers = tablestore_writers(r.fn)
        # `run_retention_sweeps` holt den Store nur und reicht ihn an den Sweep.
        holders = {w for w in writers if w not in _GRACE_PROTECTED}
        if r.touches_tablestore:
            assert holders <= {"who2be_api.core.purge.run_retention_sweeps"}, (r.name, holders)
            assert writers & _GRACE_PROTECTED, r.name
        else:
            assert writers == set(), (r.name, writers)


async def _unprotected(ctx: RoutineContext) -> dict[str, int]:  # pragma: no cover — nie ausgefuehrt
    tablestore = TableStore(base_dir=Path("/nonexistent"))
    await tablestore.delete_area_store(ctx.slot, ctx.slot)  # type: ignore[arg-type]
    return {}


def test_allowlist_check_detects_unprotected_access() -> None:
    assert tablestore_writers(_unprotected) == {f"{__name__}._unprotected"}


# --- DB ------------------------------------------------------------------------

pytest_integration = pytest.mark.integration


def _in_schema(body: Callable[[asyncpg.Connection], Awaitable[None]]) -> None:
    with isolated_schema("worker_routines"):
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
        "SELECT slot, trigger, status, result::text AS result FROM routine_run "
        "WHERE routine = $1 ORDER BY slot",
        routine,
    )
    return rows


async def _insert_run(
    conn: asyncpg.Connection,
    routine: str,
    started: datetime,
    *,
    trigger: RunTrigger = "cli",
    status: FinalStatus | Literal["running"] = "succeeded",
) -> None:
    run_id = await store.claim_slot(
        conn, routine, started, trigger=trigger, worker_id="t:1", now=started
    )
    assert run_id is not None
    if status != "running":
        await store.finish_run(conn, run_id, status, result={}, now=started)


@pytest_integration
def test_cli_run_during_worker_run_is_skipped() -> None:
    name = f"r-{secrets.token_hex(4)}"
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []

    async def slow(ctx: RoutineContext) -> dict[str, int]:
        calls.append(ctx.trigger)
        started.set()
        await release.wait()
        return {"rows": 1}

    async def body(conn: asyncpg.Connection) -> None:
        reg = Registry()
        reg.register(name, schedule="45 3 * * *", timeout=timedelta(seconds=10))(slow)
        worker = Runner(reg, env={}, clock=lambda: _T0, worker_id="w:1")
        worker_run = asyncio.create_task(worker.execute(conn, reg.get(name), _T0, "schedule"))
        await asyncio.wait_for(started.wait(), 5)
        cli_run = await routines.run_as_cli(name, registry=reg, now=_T0 + timedelta(minutes=1))
        release.set()
        outcome = await asyncio.wait_for(worker_run, 5)
        assert outcome is not None and outcome.status == "succeeded"
        assert (cli_run.outcome.status, cli_run.outcome.trigger) == ("skipped", "cli")
        assert cli_run.counters is None
        assert calls == ["schedule"]
        rows = await _rows(conn, name)
        assert [(r["trigger"], r["status"]) for r in rows] == [
            ("schedule", "succeeded"),
            ("cli", "skipped"),
        ]
        # Ein CLI-Lauf meldet keinen Worker-Heartbeat.
        assert await store.worker_seen_at(conn) is None

    _in_schema(body)


@pytest_integration
def test_memory_expire_entrypoint_with_held_lock_exits_zero_with_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with isolated_schema("worker_routines"):

        async def hold_and_call() -> None:
            async with store.routine_lock(routines.MEMORY_EXPIRE) as held:
                assert held
                # Der Entrypoint ruft `asyncio.run` und laeuft deshalb im Thread.
                await asyncio.to_thread(memory_expiry.cli)

        asyncio.run(hold_and_call())

        async def check() -> list[asyncpg.Record]:
            conn = await asyncpg.connect(get_settings().database_url)
            try:
                return await _rows(conn, routines.MEMORY_EXPIRE)
            finally:
                await conn.close()

        rows = asyncio.run(check())
    out = capsys.readouterr().out
    assert "uebersprungen" in out and "memory-expire" in out
    assert [(r["trigger"], r["status"]) for r in rows] == [("cli", "skipped")]


@pytest_integration
def test_cli_entrypoints_keep_output_and_record_cli_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    set_table_store(TableStore(base_dir=tmp_path))
    try:
        with isolated_schema("worker_routines"):
            purge.cli()
            memory_expiry.cli()

            async def check() -> dict[str, list[asyncpg.Record]]:
                conn = await asyncpg.connect(get_settings().database_url)
                try:
                    return {
                        n: await _rows(conn, n) for n in (routines.PURGE, routines.MEMORY_EXPIRE)
                    }
                finally:
                    await conn.close()

            rows = asyncio.run(check())
    finally:
        reset_table_store()
    out = capsys.readouterr().out
    assert out.startswith("Purge: 0 Org(s), 0 Account(s) geloescht;")
    assert "\nRetention: 0 Artifact(s) abgelaufen," in out
    assert "Gedaechtnis: 0 unbestaetigte(r) Eintrag/Eintraege abgelaufen." in out
    for name in (routines.PURGE, routines.MEMORY_EXPIRE):
        assert [(r["trigger"], r["status"]) for r in rows[name]] == [("cli", "succeeded")]
    assert '"organizations": 0' in rows[routines.PURGE][0]["result"]
    assert rows[routines.MEMORY_EXPIRE][0]["result"] == '{"expired": 0}'


@pytest_integration
def test_cli_start_on_slot_boundary_dodges_instead_of_failing() -> None:
    async def body(conn: asyncpg.Connection) -> None:
        # Der Worker hat den geplanten Slot 03:45 schon belegt; die CLI startet
        # genau auf dieser Grenze (Dokploy-Schedule mit derselben Zeit).
        await _insert_run(conn, routines.MEMORY_EXPIRE, _T0, trigger="schedule")
        run = await routines.run_as_cli(routines.MEMORY_EXPIRE, now=_T0)
        assert (run.outcome.status, run.outcome.slot) == ("succeeded", _T0 + SLOT_DODGE)
        assert run.counters == {"expired": 0}
        rows = await _rows(conn, routines.MEMORY_EXPIRE)
        assert [(r["slot"], r["trigger"]) for r in rows] == [
            (_T0, "schedule"),
            (_T0 + SLOT_DODGE, "cli"),
        ]

    _in_schema(body)


@pytest_integration
def test_retention_deletes_only_rows_older_than_ninety_days() -> None:
    now = _T0
    cutoff = now - timedelta(days=90)

    async def body(conn: asyncpg.Connection) -> None:
        await _insert_run(conn, "purge", cutoff - timedelta(days=1), trigger="schedule")
        await _insert_run(conn, "purge", cutoff - timedelta(seconds=1), status="failed")
        await _insert_run(conn, "purge", cutoff, trigger="schedule")
        await _insert_run(conn, "purge", now - timedelta(days=1), trigger="schedule")
        # Ein uralter `running`-Lauf gehoert dem Abandoned-Pfad.
        await _insert_run(conn, "memory-expire", cutoff - timedelta(days=5), status="running")
        run = await routines.run_as_cli(routines.ROUTINE_RUN_RETENTION, now=now)
        assert run.counters == {"deleted_runs": 2, "external_schedules": 0}
        left = await conn.fetch(
            "SELECT routine, slot FROM routine_run WHERE routine <> $1 ORDER BY slot",
            routines.ROUTINE_RUN_RETENTION,
        )
        assert [(r["routine"], r["slot"]) for r in left] == [
            ("memory-expire", cutoff - timedelta(days=5)),
            ("purge", cutoff),
            ("purge", now - timedelta(days=1)),
        ]

    _in_schema(body)


@pytest_integration
def test_external_schedule_detection(caplog: pytest.LogCaptureFixture) -> None:
    now = _T0
    day = timedelta(days=1)

    async def body(conn: asyncpg.Connection) -> None:
        # purge: CLI an zwei aufeinanderfolgenden Tagen (einer davon skipped) → erkannt.
        await _insert_run(conn, "purge", now - day)
        await _insert_run(conn, "purge", now - timedelta(minutes=5), status="skipped")
        # memory-expire: CLI an Tagen mit Luecke → nicht erkannt.
        await _insert_run(conn, "memory-expire", now - 3 * day)
        await _insert_run(conn, "memory-expire", now - day)
        # x-sched: geplante Laeufe an Folgetagen zaehlen nicht.
        await _insert_run(conn, "x-sched", now - day, trigger="schedule")
        await _insert_run(conn, "x-sched", now, trigger="schedule")
        # x-old: Folgetage, aber vor dem 7-Tage-Fenster.
        await _insert_run(conn, "x-old", now - 10 * day)
        await _insert_run(conn, "x-old", now - 9 * day)

        found = await store.external_schedules(conn, now=now)
        assert found == {"purge": now.date()}

        with caplog.at_level(logging.WARNING, logger=routines.__name__):
            run = await routines.run_as_cli(routines.ROUTINE_RUN_RETENTION, now=now)
        assert run.counters == {"deleted_runs": 0, "external_schedules": 1}
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "Externer Zeitplan erkannt" in warnings[0] and "purge" in warnings[0]

    _in_schema(body)


@pytest_integration
def test_catch_up_after_skipped_slot_runs_once_at_start_time() -> None:
    name = f"r-{secrets.token_hex(4)}"
    calls: list[datetime] = []

    async def fn(ctx: RoutineContext) -> dict[str, int]:
        calls.append(ctx.slot)
        return {"rows": 1}

    async def body(conn: asyncpg.Connection) -> None:
        reg = Registry()
        reg.register(name, schedule="45 3 * * *", timeout=timedelta(seconds=10), catch_up=True)(fn)
        # Juengster Slot endete skipped (Lock belegt), ohne Erfolg danach.
        await _insert_run(conn, name, _T0, trigger="schedule", status="skipped")
        start = _T0 + timedelta(minutes=20)
        outcomes = await Runner(reg, env={}, clock=lambda: start).start(conn)
        assert [(o.status, o.slot) for o in outcomes] == [("succeeded", start)]
        assert calls == [start]

    _in_schema(body)
