"""Zeitplaene der Worker-Routinen (ADR-0057 §4).

Ein Zeitplan ist entweder

- ein **Cron-Ausdruck** mit fuenf Feldern (`"30 3 * * *"`) oder ein Alias
  (`@hourly`, `@daily`, `@midnight`, `@weekly`, `@monthly`, `@yearly`,
  `@annually`), ausgewertet mit `croniter`, oder
- ein **einfaches Intervall**: im Code als `timedelta`, als Text
  `@every <n><einheit>…` mit den Einheiten `d`, `h`, `m`, `s`
  (z. B. `@every 15m`, `@every 1h30m`). Intervall-Slots liegen auf einem
  festen Raster ab der Unix-Epoche, damit jeder Worker und jeder Neustart
  dieselben Slots berechnet.

Alle Zeitpunkte sind UTC. `latest_slot(now)` liefert den juengsten faelligen
Slot `<= now` (ein Slot genau auf `now` ist faellig), `next_slot(now)` den
naechsten Termin `> now`. `now` wird immer uebergeben, nie hier gelesen — die
Berechnung ist mit fester Uhr testbar.

**Env-Override (W3 = a).** Der Code ist die Wahrheit, die Umgebung darf ohne
Rebuild ueberschreiben:

- `WHO2BE_ROUTINE_<NAME>_SCHEDULE` — anderer Zeitplan (Cron oder `@every`)
- `WHO2BE_ROUTINE_<NAME>_ENABLED` — `true`/`false`
- `WHO2BE_WORKER_ENABLED` — global; `false` heisst: der Worker laeuft und
  meldet Heartbeat, belegt aber keine Slots (§3).

`<NAME>` ist der Routinen-Name in Grossbuchstaben, Bindestrich wird
Unterstrich. Eine leere Variable gilt als nicht gesetzt (die Compose-Stacks
reichen alle mit leerem Default durch). Ein ungueltiger Override ist ein
**Startfehler**
(`ScheduleError`), es gibt keinen stillen Rueckfall auf den Code-Wert.
`effective_table` sammelt dabei alle Fehler und meldet sie zusammen, damit ein
Betreiber nicht Fehler fuer Fehler neu starten muss.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

# croniter bringt keine Typ-Stubs mit; `types-croniter` waere eine zweite neue
# Abhaengigkeit (Owner W1: croniter ist die einzige). Die genutzte Flaeche ist
# klein (`croniter(expr, start).get_prev/get_next(datetime)`) und vollstaendig
# getestet.
from croniter import (  # type: ignore[import-untyped]
    CroniterBadCronError,
    CroniterBadDateError,
    croniter,
)

if TYPE_CHECKING:
    from who2be_api.worker.registry import Routine

ScheduleKind = Literal["cron", "interval"]
Source = Literal["code", "env"]

#: Globaler Schalter des Workers.
WORKER_ENABLED_ENV = "WHO2BE_WORKER_ENABLED"
#: Praefix der Override-Variablen je Routine.
ROUTINE_ENV_PREFIX = "WHO2BE_ROUTINE_"

_CRON_ALIASES: frozenset[str] = frozenset(
    {"@yearly", "@annually", "@monthly", "@weekly", "@daily", "@midnight", "@hourly"}
)
_EVERY_PREFIX = "@every"
_EVERY_PART = re.compile(r"(\d+)([dhms])")
_UNIT_SECONDS = {"d": 86_400, "h": 3_600, "m": 60, "s": 1}
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_ONE_US = timedelta(microseconds=1)

_TRUE = frozenset({"true", "1", "yes", "on"})
_FALSE = frozenset({"false", "0", "no", "off"})


class ScheduleError(ValueError):
    """Ungueltiger Zeitplan oder Override — beim Start ein harter Fehler."""


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now muss zeitzonenbehaftet sein (UTC).")
    return now.astimezone(UTC)


@dataclass(frozen=True)
class Schedule:
    """Ein geparster Zeitplan. Anlegen ueber `parse_schedule`."""

    kind: ScheduleKind
    #: Kanonische Textform (Cron-Ausdruck bzw. `@every …`), fuer Log und Liste.
    expr: str
    #: Nur bei `kind == "interval"` gesetzt.
    interval: timedelta | None = None

    def latest_slot(self, now: datetime) -> datetime:
        """Juengster faelliger Slot `<= now`, in UTC."""
        ref = _utc(now)
        if self.interval is not None:
            steps = (ref - _EPOCH) // self.interval
            return _EPOCH + steps * self.interval
        # croniter.get_prev ist strikt `<`; mit +1 µs wird ein Slot genau auf
        # `now` mitgezaehlt. Cron-Slots liegen auf vollen Minuten, die
        # Mikrosekunde kann also keinen spaeteren Slot einfangen.
        prev: datetime = croniter(self.expr, ref + _ONE_US).get_prev(datetime)
        return prev.astimezone(UTC)

    def next_slot(self, now: datetime) -> datetime:
        """Naechster Termin `> now`, in UTC."""
        ref = _utc(now)
        if self.interval is not None:
            return self.latest_slot(ref) + self.interval
        nxt: datetime = croniter(self.expr, ref).get_next(datetime)
        return nxt.astimezone(UTC)


def _format_interval(interval: timedelta) -> str:
    seconds = int(interval.total_seconds())
    parts = []
    for unit, size in _UNIT_SECONDS.items():
        count, seconds = divmod(seconds, size)
        if count:
            parts.append(f"{count}{unit}")
    return f"{_EVERY_PREFIX} {''.join(parts)}"


def _interval_schedule(interval: timedelta) -> Schedule:
    if interval <= timedelta(0):
        raise ScheduleError(f"Intervall muss positiv sein, nicht {interval}.")
    if interval % timedelta(seconds=1):
        raise ScheduleError(f"Intervall muss ganze Sekunden haben, nicht {interval}.")
    return Schedule(kind="interval", expr=_format_interval(interval), interval=interval)


def _parse_every(text: str) -> Schedule:
    body = text[len(_EVERY_PREFIX) :].strip()
    if not body or _EVERY_PART.sub("", body):
        raise ScheduleError(f"Ungueltiges Intervall {text!r}, erwartet z. B. '@every 15m'.")
    seconds = sum(int(n) * _UNIT_SECONDS[unit] for n, unit in _EVERY_PART.findall(body))
    return _interval_schedule(timedelta(seconds=seconds))


def _parse_cron(text: str) -> Schedule:
    expr = " ".join(text.split())
    if expr.startswith("@"):
        if expr.lower() not in _CRON_ALIASES:
            raise ScheduleError(f"Unbekannter Cron-Alias {text!r}.")
        expr = expr.lower()
    elif len(expr.split(" ")) != 5:
        raise ScheduleError(f"Cron-Ausdruck {text!r} braucht genau fuenf Felder.")
    try:
        # Probelauf ab fester Referenz: faengt Syntaxfehler und Ausdruecke,
        # die nie feuern (z. B. 31. Februar).
        croniter(expr, _EPOCH).get_next(datetime)
    except (CroniterBadCronError, CroniterBadDateError, ValueError, KeyError) as exc:
        raise ScheduleError(f"Ungueltiger Cron-Ausdruck {text!r}.") from exc
    return Schedule(kind="cron", expr=expr)


def parse_schedule(spec: str | timedelta) -> Schedule:
    """Cron-Ausdruck, `@every …` oder `timedelta` → `Schedule`.

    Raises:
        ScheduleError: bei jedem ungueltigen Ausdruck.
    """
    if isinstance(spec, timedelta):
        return _interval_schedule(spec)
    text = spec.strip()
    if not text:
        raise ScheduleError("Leerer Zeitplan.")
    if text.lower().startswith(_EVERY_PREFIX):
        return _parse_every(text.lower())
    return _parse_cron(text)


# --- Env-Override -------------------------------------------------------------


def env_name(routine: str) -> str:
    """`purge` → `PURGE`, `routine-run-retention` → `ROUTINE_RUN_RETENTION`."""
    return routine.upper().replace("-", "_")


def schedule_env_key(routine: str) -> str:
    return f"{ROUTINE_ENV_PREFIX}{env_name(routine)}_SCHEDULE"


def enabled_env_key(routine: str) -> str:
    return f"{ROUTINE_ENV_PREFIX}{env_name(routine)}_ENABLED"


def parse_bool(key: str, value: str) -> bool:
    """Strenger Bool-Parser; alles ausser true/false/1/0/yes/no/on/off ist ein Fehler."""
    norm = value.strip().lower()
    if norm in _TRUE:
        return True
    if norm in _FALSE:
        return False
    raise ScheduleError(f"{key}={value!r} ist kein Wahrheitswert (true/false).")


def _environ(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _override(env: Mapping[str, str], key: str) -> str | None:
    """Wert einer Override-Variable; fehlend oder leer heisst: nicht gesetzt.

    Die Compose-Stacks reichen jede Variable mit leerem Default durch
    (`${WHO2BE_ROUTINE_PURGE_SCHEDULE:-}`), damit ein Eintrag in `.env` den
    Container erreicht. Ohne Eintrag kommt sie als leerer String an — das darf
    weder ein Startfehler sein noch den Code-Zeitplan verdecken.
    """
    value = env.get(key)
    if value is None or not value.strip():
        return None
    return value


def worker_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Globaler Schalter `WHO2BE_WORKER_ENABLED` (Default an, leer = Default)."""
    value = _override(_environ(env), WORKER_ENABLED_ENV)
    if value is None:
        return True
    return parse_bool(WORKER_ENABLED_ENV, value)


@dataclass(frozen=True)
class EffectiveRoutine:
    """Eine Zeile der effektiven Tabelle (Start-Log, `who2be-worker list`)."""

    name: str
    schedule: Schedule
    enabled: bool
    schedule_source: Source
    enabled_source: Source

    @property
    def source(self) -> Source:
        """`env`, sobald irgendein Override greift, sonst `code`."""
        if "env" in (self.schedule_source, self.enabled_source):
            return "env"
        return "code"


def _effective(routine: Routine, env: Mapping[str, str]) -> EffectiveRoutine:
    schedule = routine.schedule
    schedule_source: Source = "code"
    sched_key = schedule_env_key(routine.name)
    if (raw := _override(env, sched_key)) is not None:
        try:
            schedule = parse_schedule(raw)
        except ScheduleError as exc:
            raise ScheduleError(f"{sched_key}: {exc}") from exc
        schedule_source = "env"
    enabled = True
    enabled_source: Source = "code"
    enabled_key = enabled_env_key(routine.name)
    if (raw := _override(env, enabled_key)) is not None:
        enabled, enabled_source = parse_bool(enabled_key, raw), "env"
    return EffectiveRoutine(
        name=routine.name,
        schedule=schedule,
        enabled=enabled,
        schedule_source=schedule_source,
        enabled_source=enabled_source,
    )


def effective_table(
    routines: Iterable[Routine], env: Mapping[str, str] | None = None
) -> list[EffectiveRoutine]:
    """Code-Zeitplaene plus Env-Overrides, nach Name sortiert.

    Raises:
        ScheduleError: mit allen ungueltigen Overrides auf einmal.
    """
    environ = _environ(env)
    rows: list[EffectiveRoutine] = []
    errors: list[str] = []
    for routine in sorted(routines, key=lambda r: r.name):
        try:
            rows.append(_effective(routine, environ))
        except ScheduleError as exc:
            errors.append(str(exc))
    try:
        worker_enabled(environ)
    except ScheduleError as exc:
        errors.append(str(exc))
    if errors:
        raise ScheduleError("Ungueltige Worker-Konfiguration: " + "; ".join(errors))
    return rows


def unknown_overrides(
    routines: Iterable[Routine], env: Mapping[str, str] | None = None
) -> list[str]:
    """`WHO2BE_ROUTINE_*`-Variablen, die zu keiner registrierten Routine passen.

    Kein Startfehler (eine Variable kann eine entfernte Routine ueberdauern),
    aber ein Tippfehler soll im Start-Log sichtbar sein statt still zu wirken.
    """
    known = set()
    for routine in routines:
        known.add(schedule_env_key(routine.name))
        known.add(enabled_env_key(routine.name))
    return sorted(
        key
        for key in _environ(env)
        if key.startswith(ROUTINE_ENV_PREFIX)
        and key.endswith(("_SCHEDULE", "_ENABLED"))
        and key not in known
    )


def format_table(rows: Iterable[EffectiveRoutine]) -> str:
    """Effektive Tabelle als Klartext (Start-Log, `who2be-worker list`)."""
    lines = [("ROUTINE", "SCHEDULE", "ENABLED", "SOURCE")]
    lines += [
        (row.name, row.schedule.expr, "on" if row.enabled else "off", row.source) for row in rows
    ]
    widths = [max(len(line[i]) for line in lines) for i in range(3)]
    return "\n".join(
        "  ".join([*(line[i].ljust(widths[i]) for i in range(3)), line[3]]) for line in lines
    )
