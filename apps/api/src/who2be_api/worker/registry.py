"""Registry der Worker-Routinen (ADR-0057 §4).

Routinen melden sich per Decorator an::

    @routine(
        "purge",
        schedule="30 3 * * *",
        timeout=timedelta(hours=1),
        catch_up=True,
        touches_tablestore=True,
    )
    async def purge(ctx: RoutineContext) -> dict[str, int]:
        ...

- Der Name ist eindeutig; ein doppelter Name ist ein Fehler beim Import
  (`DuplicateRoutineError`). Erlaubt ist dieselbe Form wie im CHECK der
  Migration 0102 (`^[a-z][a-z0-9-]{0,62}$`), damit ein Name nie erst beim
  Slot-Claim scheitert.
- `schedule` ist ein Cron-Ausdruck, `@every …` oder ein `timedelta`
  (`worker.schedule`); er wird beim Anmelden geparst, ein ungueltiger
  Ausdruck scheitert also ebenfalls beim Import.
- Das Ergebnis einer Routine sind **nur Zaehler** (`dict[str, int]`), keine
  Inhalte und keine personenbezogenen Daten. `store.finish_run` erzwingt das
  beim Schreiben, die Migration zusaetzlich per CHECK.

Die Routine-Funktionen selbst bleiben in `core/` und werden nur angebunden
(P2). Runner und CLI (P1c) lesen die Registry ueber `REGISTRY`.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

import asyncpg

from who2be_api.worker.schedule import Schedule, parse_schedule
from who2be_api.worker.store import RunTrigger

#: Gleiche Form wie `routine_run.routine` (CHECK in Migration 0102).
ROUTINE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,62}$")


@dataclass(frozen=True)
class RoutineContext:
    """Was eine Routine je Lauf bekommt.

    `slot` ist die Referenzzeit des Laufs (UTC) und ersetzt in der Routine
    `datetime.now` — so rechnet ein nachgeholter Lauf mit seinem Slot.
    """

    conn: asyncpg.Connection
    slot: datetime
    trigger: RunTrigger
    worker_id: str


RoutineFn = Callable[[RoutineContext], Awaitable[dict[str, int]]]


@dataclass(frozen=True)
class Routine:
    """Eine angemeldete Routine samt Code-Zeitplan (ohne Env-Override)."""

    name: str
    fn: RoutineFn
    schedule: Schedule
    timeout: timedelta
    catch_up: bool
    touches_tablestore: bool


class RegistryError(ValueError):
    """Ungueltige Anmeldung einer Routine."""


class DuplicateRoutineError(RegistryError):
    """Zwei Routinen mit demselben Namen."""


class Registry:
    """Name → Routine. Reihenfolge der Anmeldung bleibt erhalten."""

    def __init__(self) -> None:
        self._routines: dict[str, Routine] = {}

    def add(self, routine: Routine) -> Routine:
        if routine.name in self._routines:
            raise DuplicateRoutineError(f"Routine {routine.name!r} ist bereits registriert.")
        self._routines[routine.name] = routine
        return routine

    def register(
        self,
        name: str,
        *,
        schedule: str | timedelta,
        timeout: timedelta,
        catch_up: bool = False,
        touches_tablestore: bool = False,
    ) -> Callable[[RoutineFn], RoutineFn]:
        """Decorator-Fabrik; prueft Name, Zeitplan und Timeout sofort."""
        if not ROUTINE_NAME_PATTERN.fullmatch(name):
            raise RegistryError(
                f"Routinen-Name {name!r} ungueltig: erlaubt sind a-z, 0-9 und '-', "
                "Beginn mit Buchstabe, hoechstens 63 Zeichen."
            )
        if timeout <= timedelta(0):
            raise RegistryError(f"Routine {name!r}: timeout muss positiv sein.")
        parsed = parse_schedule(schedule)

        def decorator(fn: RoutineFn) -> RoutineFn:
            self.add(
                Routine(
                    name=name,
                    fn=fn,
                    schedule=parsed,
                    timeout=timeout,
                    catch_up=catch_up,
                    touches_tablestore=touches_tablestore,
                )
            )
            return fn

        return decorator

    def get(self, name: str) -> Routine:
        try:
            return self._routines[name]
        except KeyError:
            raise KeyError(f"Unbekannte Routine {name!r}.") from None

    def names(self) -> list[str]:
        return list(self._routines)

    def __iter__(self) -> Iterator[Routine]:
        return iter(list(self._routines.values()))

    def __len__(self) -> int:
        return len(self._routines)

    def __contains__(self, name: object) -> bool:
        return name in self._routines


#: Die Registry des Prozesses; `@routine` meldet hier an.
REGISTRY = Registry()


def routine(
    name: str,
    *,
    schedule: str | timedelta,
    timeout: timedelta,
    catch_up: bool = False,
    touches_tablestore: bool = False,
) -> Callable[[RoutineFn], RoutineFn]:
    """Meldet eine Routine in `REGISTRY` an (ADR-0057 §4)."""
    return REGISTRY.register(
        name,
        schedule=schedule,
        timeout=timeout,
        catch_up=catch_up,
        touches_tablestore=touches_tablestore,
    )
