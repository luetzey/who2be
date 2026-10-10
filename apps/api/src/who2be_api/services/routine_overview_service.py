"""Routinen-Uebersicht fuer Betreiber (ADR-0057 §7, §8 Schritt 2, Paket P4b).

Kombiniert, was der Worker im Code und in Postgres hinterlaesst:

- **Registry** und **effektive Tabelle** (`worker.schedule.effective_table`):
  Name, wirksamer Zeitplan, an/aus und ob ein Env-Override greift;
- **`routine_run`**: juengster Lauf je Routine (der letzte gewinnt) und
  juengster Erfolg (`store.latest_runs`, `store.latest_successes`);
- **externe Zeitplaene**: dieselbe Abfrage, mit der der Worker seine
  WARN-Zeile schreibt (`store.external_schedules`) — keine zweite Fassung;
- **`worker_heartbeat`**: „Worker zuletzt gesehen“ (`store.worker_seen_at`).

Gelesen wird ueber die App-Verbindung: `who2be_app` hat auf beiden Tabellen
nur SELECT (Migration 0102), beide sind global ohne Mandantenspalte und ohne
RLS. Die vier Abfragen laufen in einer lesenden Transaktion mit
`REPEATABLE READ`, damit letzter Lauf und letzter Erfolg aus demselben Stand
stammen.

Die effektive Tabelle wird aus der Umgebung **dieses** Prozesses gebildet.
Damit Overrides sichtbar sind, muss der API-Dienst die
`WHO2BE_ROUTINE_*`-Variablen genauso bekommen wie der Worker. Ein
ungueltiger Override wirft `ScheduleError` wie beim Worker-Start — kein
stiller Rueckfall auf den Code-Wert.

Keine Route, keine Rechte-Pruefung: das Einhaengen hinter die
Betreiber-Pruefung ist Paket P4c.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime

import asyncpg

# Meldet die Routinen in `REGISTRY` an (ADR-0057 P2), wie `worker.cli`.
from who2be_api.worker import routines as _routines  # noqa: F401
from who2be_api.worker import store
from who2be_api.worker.registry import REGISTRY, Routine
from who2be_api.worker.schedule import EffectiveRoutine, effective_table, worker_enabled
from who2be_models import RoutineLastRun, RoutinesOverview, RoutineStatus


def _last_run(run: store.RoutineRun) -> RoutineLastRun:
    duration_ms = None
    if run.finished_at is not None:
        duration_ms = max(0, int((run.finished_at - run.started_at).total_seconds() * 1000))
    return RoutineLastRun.model_validate(
        {
            "status": run.status,
            "trigger": run.trigger,
            "started_at": run.started_at,
            "duration_ms": duration_ms,
            "result": run.result,
            "error_class": run.error_class,
        }
    )


def _status(
    row: EffectiveRoutine,
    *,
    last: store.RoutineRun | None,
    success: store.RoutineRun | None,
    external: bool,
    scheduling: bool,
    now: datetime,
) -> RoutineStatus:
    return RoutineStatus(
        name=row.name,
        schedule=row.schedule.expr,
        enabled=row.enabled,
        source=row.source,
        last_run=_last_run(last) if last is not None else None,
        # Abgeschaltet (Routine oder Worker global): es gibt keinen Termin.
        next_run_at=row.schedule.next_slot(now) if row.enabled and scheduling else None,
        last_success_at=success.finished_at if success is not None else None,
        external_schedule_detected=external,
    )


async def routines_overview(
    conn: asyncpg.Connection,
    *,
    routines: Iterable[Routine] | None = None,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> RoutinesOverview:
    """Alle registrierten Routinen mit Zeitplan und Laufstand, nach Name sortiert.

    Laeufe von Routinen, die nicht (mehr) registriert sind, erscheinen nicht:
    ohne Registry-Eintrag gibt es weder Zeitplan noch Termin.

    Args:
        conn: Verbindung mit SELECT auf `routine_run` und `worker_heartbeat`.
        routines: Default `REGISTRY`; Tests uebergeben eine eigene Menge.
        env: Default `os.environ`; Tests uebergeben die Overrides direkt.
        now: Referenzzeit fuer `next_run_at` und das Fenster der externen
            Zeitplaene; Default jetzt (UTC).

    Raises:
        ScheduleError: bei ungueltigem `WHO2BE_ROUTINE_*`- oder
            `WHO2BE_WORKER_ENABLED`-Override.
    """
    reference = now or datetime.now(UTC)
    rows = effective_table(REGISTRY if routines is None else routines, env)
    scheduling = worker_enabled(env)
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        latest = await store.latest_runs(conn)
        successes = await store.latest_successes(conn)
        external = await store.external_schedules(conn, now=reference)
        seen = await store.worker_seen_at(conn)
    return RoutinesOverview(
        routines=[
            _status(
                row,
                last=latest.get(row.name),
                success=successes.get(row.name),
                external=row.name in external,
                scheduling=scheduling,
                now=reference,
            )
            for row in rows
        ],
        worker_last_seen_at=seen,
    )
