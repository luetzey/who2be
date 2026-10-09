"""Registry und Zeitplaene des Workers (ADR-0057 §4, P1b).

Reine Logik ohne DB. Jede Zeitberechnung bekommt eine **feste Uhr**
(`now=…`); kein Test liest die Systemzeit. Env-Overrides laufen ueber ein
uebergebenes Mapping statt ueber `os.environ`, ausser dort, wo der
Default-Pfad (`env=None` → `os.environ`) selbst geprueft wird.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from who2be_api.worker import registry as registry_mod
from who2be_api.worker.registry import (
    DuplicateRoutineError,
    Registry,
    RegistryError,
    RoutineContext,
    routine,
)
from who2be_api.worker.schedule import (
    ScheduleError,
    effective_table,
    enabled_env_key,
    env_name,
    format_table,
    parse_schedule,
    schedule_env_key,
    unknown_overrides,
    worker_enabled,
)

HOUR = timedelta(hours=1)


async def _noop(ctx: RoutineContext) -> dict[str, int]:
    return {"rows": 0}


def _registry(*names: str, schedule: str | timedelta = "30 3 * * *") -> Registry:
    reg = Registry()
    for name in names:
        reg.register(name, schedule=schedule, timeout=HOUR)(_noop)
    return reg


def _at(year: int, month: int, day: int, hour: int = 0, minute: int = 0, sec: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, sec, tzinfo=UTC)


# --- Registry -----------------------------------------------------------------


def test_register_keeps_metadata_and_returns_function() -> None:
    reg = Registry()
    fn = reg.register(
        "purge", schedule="30 3 * * *", timeout=HOUR, catch_up=True, touches_tablestore=True
    )(_noop)
    assert fn is _noop
    entry = reg.get("purge")
    assert (entry.fn, entry.timeout, entry.catch_up, entry.touches_tablestore) == (
        _noop,
        HOUR,
        True,
        True,
    )
    assert entry.schedule.kind == "cron"
    assert reg.names() == ["purge"] and "purge" in reg and len(reg) == 1


def test_duplicate_name_is_an_error() -> None:
    reg = _registry("purge")
    with pytest.raises(DuplicateRoutineError, match="purge"):
        reg.register("purge", schedule="@hourly", timeout=HOUR)(_noop)
    assert len(reg) == 1


def test_module_decorator_registers_in_global_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = Registry()
    monkeypatch.setattr(registry_mod, "REGISTRY", fresh)

    @routine("memory-expire", schedule=timedelta(minutes=15), timeout=HOUR)
    async def expire(ctx: RoutineContext) -> dict[str, int]:
        return {}

    assert fresh.get("memory-expire").fn is expire
    with pytest.raises(DuplicateRoutineError):
        routine("memory-expire", schedule="@daily", timeout=HOUR)(_noop)


@pytest.mark.parametrize("name", ["Purge", "1purge", "purge_run", "", "a" * 64, "-x"])
def test_invalid_names_fail_at_registration(name: str) -> None:
    with pytest.raises(RegistryError):
        Registry().register(name, schedule="@daily", timeout=HOUR)


def test_invalid_schedule_and_timeout_fail_at_registration() -> None:
    with pytest.raises(ScheduleError):
        Registry().register("purge", schedule="not a cron", timeout=HOUR)
    with pytest.raises(RegistryError, match="timeout"):
        Registry().register("purge", schedule="@daily", timeout=timedelta(0))


def test_unknown_routine_lookup() -> None:
    with pytest.raises(KeyError, match="nope"):
        Registry().get("nope")


# --- Cron ---------------------------------------------------------------------


def test_cron_latest_and_next_slot() -> None:
    sched = parse_schedule("30 3 * * *")
    now = _at(2026, 10, 9, 12, 0)
    assert sched.latest_slot(now) == _at(2026, 10, 9, 3, 30)
    assert sched.next_slot(now) == _at(2026, 10, 10, 3, 30)


def test_cron_slot_boundary_is_inclusive_for_latest_exclusive_for_next() -> None:
    sched = parse_schedule("30 3 * * *")
    exact = _at(2026, 10, 9, 3, 30)
    assert sched.latest_slot(exact) == exact
    assert sched.next_slot(exact) == _at(2026, 10, 10, 3, 30)
    just_before = exact - timedelta(microseconds=1)
    assert sched.latest_slot(just_before) == _at(2026, 10, 8, 3, 30)
    assert sched.next_slot(just_before) == exact


def test_cron_is_evaluated_in_utc_regardless_of_input_zone() -> None:
    sched = parse_schedule("30 3 * * *")
    cest = timezone(timedelta(hours=2))
    # 05:30 CEST == 03:30 UTC: genau der Slot, nicht 05:30 lokal.
    now = datetime(2026, 10, 9, 5, 30, tzinfo=cest)
    slot = sched.latest_slot(now)
    assert slot == _at(2026, 10, 9, 3, 30)
    assert slot.utcoffset() == timedelta(0)
    assert sched.next_slot(now).utcoffset() == timedelta(0)


def test_cron_alias_and_whitespace_normalised() -> None:
    assert parse_schedule("@Hourly").expr == "@hourly"
    assert parse_schedule("  0   4 * * * ").expr == "0 4 * * *"
    assert parse_schedule("@daily").latest_slot(_at(2026, 1, 2, 5)) == _at(2026, 1, 2)


def test_naive_now_is_rejected() -> None:
    sched = parse_schedule("@daily")
    with pytest.raises(ValueError, match="zeitzonenbehaftet"):
        sched.latest_slot(datetime(2026, 1, 1))  # noqa: DTZ001 - Absicht des Tests


# --- Intervall ----------------------------------------------------------------


def test_interval_slots_on_epoch_grid() -> None:
    sched = parse_schedule(timedelta(minutes=15))
    assert sched.kind == "interval" and sched.expr == "@every 15m"
    now = _at(2026, 10, 9, 10, 7, 30)
    assert sched.latest_slot(now) == _at(2026, 10, 9, 10, 0)
    assert sched.next_slot(now) == _at(2026, 10, 9, 10, 15)


def test_interval_slot_boundary() -> None:
    sched = parse_schedule("@every 15m")
    exact = _at(2026, 10, 9, 10, 15)
    assert sched.latest_slot(exact) == exact
    assert sched.next_slot(exact) == _at(2026, 10, 9, 10, 30)
    assert sched.latest_slot(exact - timedelta(microseconds=1)) == _at(2026, 10, 9, 10, 0)


def test_interval_text_forms() -> None:
    assert parse_schedule("@every 1h30m").interval == timedelta(minutes=90)
    assert parse_schedule("@EVERY 1d").expr == "@every 1d"
    assert parse_schedule(timedelta(hours=25)).expr == "@every 1d1h"


@pytest.mark.parametrize(
    "spec",
    [
        "",
        "   ",
        "bad",
        "61 * * * *",
        "* * * *",
        "* * * * * *",
        "0 0 31 2 *",
        "@reboot",
        "@every",
        "@every 15",
        "@every 15x",
        "@every 0m",
        timedelta(0),
        timedelta(seconds=-5),
        timedelta(milliseconds=500),
    ],
)
def test_invalid_expressions(spec: str | timedelta) -> None:
    with pytest.raises(ScheduleError):
        parse_schedule(spec)


# --- Env-Override -------------------------------------------------------------


def test_env_key_names() -> None:
    assert env_name("routine-run-retention") == "ROUTINE_RUN_RETENTION"
    assert schedule_env_key("purge") == "WHO2BE_ROUTINE_PURGE_SCHEDULE"
    assert enabled_env_key("memory-expire") == "WHO2BE_ROUTINE_MEMORY_EXPIRE_ENABLED"


def test_effective_table_without_overrides_is_code() -> None:
    rows = effective_table(_registry("purge", "memory-expire"), env={})
    assert [(r.name, r.schedule.expr, r.enabled, r.source) for r in rows] == [
        ("memory-expire", "30 3 * * *", True, "code"),
        ("purge", "30 3 * * *", True, "code"),
    ]


def test_schedule_override_changes_slots() -> None:
    env = {"WHO2BE_ROUTINE_PURGE_SCHEDULE": "0 4 * * *"}
    (row,) = effective_table(_registry("purge"), env=env)
    assert (row.schedule.expr, row.schedule_source, row.enabled_source, row.source) == (
        "0 4 * * *",
        "env",
        "code",
        "env",
    )
    assert row.schedule.latest_slot(_at(2026, 10, 9, 3, 45)) == _at(2026, 10, 8, 4)


def test_interval_override_for_hyphenated_name() -> None:
    env = {"WHO2BE_ROUTINE_MEMORY_EXPIRE_SCHEDULE": "@every 1h"}
    (row,) = effective_table(_registry("memory-expire"), env=env)
    assert row.schedule.interval == HOUR


def test_enabled_false_switches_routine_off() -> None:
    env = {"WHO2BE_ROUTINE_PURGE_ENABLED": "false"}
    rows = {r.name: r for r in effective_table(_registry("purge", "other"), env=env)}
    assert (rows["purge"].enabled, rows["purge"].source) == (False, "env")
    assert (rows["other"].enabled, rows["other"].source) == (True, "code")


def test_invalid_schedule_override_is_start_error_without_fallback() -> None:
    env = {"WHO2BE_ROUTINE_PURGE_SCHEDULE": "every night"}
    with pytest.raises(ScheduleError, match="WHO2BE_ROUTINE_PURGE_SCHEDULE"):
        effective_table(_registry("purge"), env=env)


def test_all_invalid_overrides_reported_together() -> None:
    env = {
        "WHO2BE_ROUTINE_PURGE_SCHEDULE": "nope",
        "WHO2BE_ROUTINE_OTHER_ENABLED": "vielleicht",
        "WHO2BE_WORKER_ENABLED": "jein",
    }
    with pytest.raises(ScheduleError) as info:
        effective_table(_registry("purge", "other"), env=env)
    message = str(info.value)
    for key in env:
        assert key in message


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, True), ("true", True), ("1", True), ("FALSE", False), (" off ", False)],
)
def test_worker_enabled(value: str | None, expected: bool) -> None:
    env = {} if value is None else {"WHO2BE_WORKER_ENABLED": value}
    assert worker_enabled(env) is expected


def test_worker_enabled_invalid_is_error() -> None:
    with pytest.raises(ScheduleError, match="WHO2BE_WORKER_ENABLED"):
        worker_enabled({"WHO2BE_WORKER_ENABLED": "maybe"})


def test_defaults_read_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_WORKER_ENABLED", "false")
    monkeypatch.setenv("WHO2BE_ROUTINE_PURGE_ENABLED", "false")
    assert worker_enabled() is False
    (row,) = effective_table(_registry("purge"))
    assert row.enabled is False


def test_unknown_overrides_are_listed() -> None:
    env = {
        "WHO2BE_ROUTINE_PURGE_SCHEDULE": "@daily",
        "WHO2BE_ROUTINE_PRUGE_ENABLED": "false",
        "WHO2BE_ROUTINE_UNRELATED": "x",
    }
    assert unknown_overrides(_registry("purge"), env=env) == ["WHO2BE_ROUTINE_PRUGE_ENABLED"]


def test_format_table() -> None:
    env = {"WHO2BE_ROUTINE_PURGE_ENABLED": "false"}
    text = format_table(effective_table(_registry("purge", "routine-run-retention"), env=env))
    lines = text.splitlines()
    assert lines[0].split() == ["ROUTINE", "SCHEDULE", "ENABLED", "SOURCE"]
    assert lines[1].split() == ["purge", "30", "3", "*", "*", "*", "off", "env"]
    assert lines[2].split() == ["routine-run-retention", "30", "3", "*", "*", "*", "on", "code"]
    # Spalten stehen untereinander.
    assert lines[1].index(" off ") == lines[2].index(" on ")
