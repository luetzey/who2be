"""Laufprotokoll, Heartbeats und Advisory-Lock des Workers (ADR-0057 §5/§6).

Alle Funktionen laufen auf der **Owner-Verbindung** (`DATABASE_URL`) wie
`who2be-purge` und `who2be-memory-expire`: `routine_run` und
`worker_heartbeat` tragen keine Mandantendaten, die Laufzeitrolle
`who2be_app` darf sie nur lesen (Migration 0102).

Genau ein Lauf je Slot:
- **Slot-Claim** (`claim_slot`) ist die Exklusivitaet: `INSERT … ON CONFLICT
  (routine, slot) DO NOTHING RETURNING id`. Nur wer eine ID zurueckbekommt,
  fuehrt aus. Das haengt an keiner Session und haelt auch hinter einem
  Transaction-Pooler.
- **Advisory-Lock** (`routine_lock`) ist der zweite Gurt gegen Ueberlappung
  mit CLI- oder manuellen Laeufen. Er braucht eine **dedizierte
  Direktverbindung**: ein Session-Lock auf einer gepoolten Verbindung ginge
  mit deren Rueckgabe verloren bzw. bliebe an ihr haengen.

Zeitpunkte kommen aus Python (`now`, Default `datetime.now(UTC)`), nicht aus
`now()` der Datenbank — dieselbe Uhr fuer Claim, Heartbeat und Abandoned-
Pruefung, und mit fester Uhr testbar (Muster `core/memory_expiry.py`).

`result` und `error_class` sind bewusst eng: nur Zaehler bzw. nur der Name
der Exception-Klasse, nie eine Meldung mit Daten. Die Migration erzwingt
beides zusaetzlich per CHECK.

Die `jsonb`-Spalte wird als Text gebunden und gelesen (`$n::text::jsonb`,
`result::text`), damit die Funktionen mit und ohne den jsonb-Codec aus
`apps/api/src/who2be_api/core/db.py#init_connection` gleich arbeiten.
"""

from __future__ import annotations

import json
import os
import socket
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import UUID

import asyncpg

from who2be_api.core.config import get_settings

# --- Schwellen (PM-W4) --------------------------------------------------------

#: Container-Healthcheck: der eigene Worker-Heartbeat muss juenger sein.
WORKER_HEALTHCHECK_MAX_AGE = timedelta(minutes=2)
#: Health-Feld `worker: stale`, wenn der juengste Worker-Heartbeat aelter ist.
WORKER_STALE_AFTER = timedelta(minutes=5)
#: `running`-Laeufe mit aelterem `heartbeat_at` gelten als abgebrochen.
RUN_ABANDONED_AFTER = timedelta(minutes=5)

#: `routine_run`-Zeilen, die aelter sind, raeumt `routine-run-retention` ab (§6).
ROUTINE_RUN_RETENTION = timedelta(days=90)
#: Fenster, in dem `external_schedules` nach CLI-Laeufen sucht (§8 Schritt 2).
#: Eine Woche: alte Notfall-Laeufe sollen nicht dauerhaft warnen.
EXTERNAL_SCHEDULE_LOOKBACK = timedelta(days=7)

#: `error_class` abgebrochener Laeufe.
ABANDONED_ERROR_CLASS = "Abandoned"
#: Praefix des Advisory-Lock-Schluessels; CLIs nehmen denselben Lock (§8).
LOCK_NAME_PREFIX = "who2be.routine."

RunTrigger = Literal["schedule", "cli", "manual"]
RunStatus = Literal["running", "succeeded", "failed", "skipped"]
FinalStatus = Literal["succeeded", "failed", "skipped"]

_FINAL_STATUSES: frozenset[str] = frozenset({"succeeded", "failed", "skipped"})
_TRIGGERS: frozenset[str] = frozenset({"schedule", "cli", "manual"})


@dataclass(frozen=True)
class RoutineRun:
    """Eine Zeile aus `routine_run`."""

    id: UUID
    routine: str
    slot: datetime
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    heartbeat_at: datetime
    result: dict[str, int | float] | None
    error_class: str | None
    worker_id: str


_RUN_COLUMNS = (
    "id, routine, slot, trigger, status, started_at, finished_at, heartbeat_at, "
    "result::text AS result, error_class, worker_id"
)


def _to_run(row: asyncpg.Record) -> RoutineRun:
    raw = row["result"]
    return RoutineRun(
        id=row["id"],
        routine=row["routine"],
        slot=row["slot"],
        trigger=row["trigger"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        heartbeat_at=row["heartbeat_at"],
        result=json.loads(raw) if raw is not None else None,
        error_class=row["error_class"],
        worker_id=row["worker_id"],
    )


def _now(now: datetime | None) -> datetime:
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        raise ValueError("now muss zeitzonenbehaftet sein (UTC).")
    return reference


def default_worker_id() -> str:
    """`hostname:pid` des laufenden Prozesses."""
    return f"{socket.gethostname()}:{os.getpid()}"


def _encode_result(result: Mapping[str, int | float] | None) -> str | None:
    """Nur Zaehler: Schluessel Text, Werte Zahlen (kein bool, kein Text)."""
    if result is None:
        return None
    for key, value in result.items():
        if not isinstance(key, str):
            raise ValueError("result: Schluessel muessen Text sein.")
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"result[{key!r}]: nur Zaehler (int/float) erlaubt.")
    return json.dumps(dict(result))


# --- Slot-Claim und Abschluss -------------------------------------------------

_CLAIM_SQL = """
INSERT INTO routine_run
    (routine, slot, trigger, status, started_at, heartbeat_at, worker_id)
VALUES ($1, $2, $3, 'running', $4, $4, $5)
ON CONFLICT (routine, slot) DO NOTHING
RETURNING id
"""


async def claim_slot(
    conn: asyncpg.Connection,
    routine: str,
    slot: datetime,
    *,
    trigger: RunTrigger,
    worker_id: str,
    now: datetime | None = None,
) -> UUID | None:
    """Belegt den Slot. Liefert die Lauf-ID oder `None`, wenn er schon belegt ist."""
    if trigger not in _TRIGGERS:
        raise ValueError(f"Unbekannter trigger: {trigger!r}")
    if slot.tzinfo is None:
        raise ValueError("slot muss zeitzonenbehaftet sein (UTC).")
    run_id: UUID | None = await conn.fetchval(
        _CLAIM_SQL, routine, slot, trigger, _now(now), worker_id
    )
    return run_id


_FINISH_SQL = """
UPDATE routine_run
SET status = $2, finished_at = $3, heartbeat_at = $3,
    result = $4::text::jsonb, error_class = $5
WHERE id = $1 AND status = 'running'
RETURNING id
"""


async def finish_run(
    conn: asyncpg.Connection,
    run_id: UUID,
    status: FinalStatus,
    *,
    result: Mapping[str, int | float] | None = None,
    error: BaseException | None = None,
    now: datetime | None = None,
) -> bool:
    """Schliesst einen laufenden Lauf ab.

    `error` nur bei `failed`; gespeichert wird ausschliesslich der
    Klassenname. Liefert `False`, wenn der Lauf nicht (mehr) `running` ist —
    etwa weil er inzwischen als abgebrochen markiert wurde.
    """
    if status not in _FINAL_STATUSES:
        raise ValueError(f"Kein Abschluss-Status: {status!r}")
    if error is not None and status != "failed":
        raise ValueError("error ist nur bei status='failed' erlaubt.")
    error_class = type(error).__name__ if error is not None else None
    updated = await conn.fetchval(
        _FINISH_SQL, run_id, status, _now(now), _encode_result(result), error_class
    )
    return updated is not None


_TOUCH_SQL = """
UPDATE routine_run SET heartbeat_at = $2
WHERE id = $1 AND status = 'running'
RETURNING id
"""


async def touch_run(conn: asyncpg.Connection, run_id: UUID, *, now: datetime | None = None) -> bool:
    """Lauf-Heartbeat. `False`, wenn der Lauf nicht mehr `running` ist."""
    return await conn.fetchval(_TOUCH_SQL, run_id, _now(now)) is not None


_ABANDON_SQL = f"""
UPDATE routine_run
SET status = 'failed', finished_at = $1, error_class = '{ABANDONED_ERROR_CLASS}'
WHERE status = 'running' AND heartbeat_at < $1::timestamptz - $2::interval
RETURNING id
"""


async def mark_abandoned(
    conn: asyncpg.Connection,
    *,
    now: datetime | None = None,
    threshold: timedelta = RUN_ABANDONED_AFTER,
) -> list[UUID]:
    """Setzt `running`-Laeufe mit `heartbeat_at` aelter als `threshold` auf
    `failed`/`Abandoned`. Liefert die betroffenen Lauf-IDs."""
    rows = await conn.fetch(_ABANDON_SQL, _now(now), threshold)
    return [row["id"] for row in rows]


# --- Lesen --------------------------------------------------------------------


async def last_run(conn: asyncpg.Connection, routine: str) -> RoutineRun | None:
    """Juengster Lauf einer Routine (nach `started_at`), gleich welcher Status."""
    row = await conn.fetchrow(
        f"SELECT {_RUN_COLUMNS} FROM routine_run WHERE routine = $1 "
        "ORDER BY started_at DESC, id DESC LIMIT 1",
        routine,
    )
    return _to_run(row) if row is not None else None


async def last_success(conn: asyncpg.Connection, routine: str) -> RoutineRun | None:
    """Juengster erfolgreicher Lauf einer Routine (nach `finished_at`)."""
    row = await conn.fetchrow(
        f"SELECT {_RUN_COLUMNS} FROM routine_run "
        "WHERE routine = $1 AND status = 'succeeded' "
        "ORDER BY finished_at DESC, id DESC LIMIT 1",
        routine,
    )
    return _to_run(row) if row is not None else None


async def latest_runs(conn: asyncpg.Connection) -> dict[str, RoutineRun]:
    """Juengster Lauf je Routine."""
    rows = await conn.fetch(
        f"SELECT DISTINCT ON (routine) {_RUN_COLUMNS} FROM routine_run "
        "ORDER BY routine, started_at DESC, id DESC"
    )
    return {row["routine"]: _to_run(row) for row in rows}


async def latest_successes(conn: asyncpg.Connection) -> dict[str, RoutineRun]:
    """Juengster erfolgreicher Lauf je Routine."""
    rows = await conn.fetch(
        f"SELECT DISTINCT ON (routine) {_RUN_COLUMNS} FROM routine_run "
        "WHERE status = 'succeeded' "
        "ORDER BY routine, finished_at DESC, id DESC"
    )
    return {row["routine"]: _to_run(row) for row in rows}


_EXTERNAL_SCHEDULES_SQL = """
WITH days AS (
    SELECT DISTINCT routine, (started_at AT TIME ZONE 'UTC')::date AS day
    FROM routine_run
    WHERE trigger = 'cli' AND started_at >= $1::timestamptz - $2::interval
)
SELECT d.routine, max(d.day) AS last_day
FROM days d
JOIN days p ON p.routine = d.routine AND p.day = d.day - 1
GROUP BY d.routine
ORDER BY d.routine
"""


async def external_schedules(
    conn: asyncpg.Connection,
    *,
    now: datetime | None = None,
    lookback: timedelta = EXTERNAL_SCHEDULE_LOOKBACK,
) -> dict[str, date]:
    """Routinen mit `cli`-Laeufen an mindestens zwei aufeinanderfolgenden
    UTC-Tagen innerhalb von `lookback` (ADR-0057 §8 Schritt 2).

    Das ist das Zeichen fuer einen noch laufenden Host-Cron oder
    Dokploy-Schedule neben dem Worker. Gezaehlt wird jeder Status, auch
    `skipped`: ein uebersprungener CLI-Lauf belegt den Zeitplan ebenso.
    Liefert Routine → juengster Tag eines solchen Paares. Der Worker loggt
    daraus eine WARN-Zeile, der Betreiber-Endpunkt (P4b) nutzt dieselbe Abfrage.
    """
    rows = await conn.fetch(_EXTERNAL_SCHEDULES_SQL, _now(now), lookback)
    return {row["routine"]: row["last_day"] for row in rows}


async def delete_runs_before(conn: asyncpg.Connection, cutoff: datetime) -> int:
    """Loescht `routine_run`-Zeilen mit `started_at` vor `cutoff`; liefert die Anzahl.

    `running`-Zeilen bleiben stehen: ein laufender Lauf gehoert dem Abandoned-
    Pfad, nicht der Aufbewahrung.
    """
    if cutoff.tzinfo is None:
        raise ValueError("cutoff muss zeitzonenbehaftet sein (UTC).")
    rows = await conn.fetch(
        "DELETE FROM routine_run WHERE started_at < $1 AND status <> 'running' RETURNING id",
        cutoff,
    )
    return len(rows)


# --- Worker-Heartbeat ---------------------------------------------------------

_WORKER_HEARTBEAT_SQL = """
INSERT INTO worker_heartbeat (worker_id, seen_at, version)
VALUES ($1, $2, $3)
ON CONFLICT (worker_id) DO UPDATE
SET seen_at = EXCLUDED.seen_at, version = EXCLUDED.version
"""


async def record_worker_heartbeat(
    conn: asyncpg.Connection,
    *,
    worker_id: str,
    version: str,
    now: datetime | None = None,
) -> None:
    """Frischt den Heartbeat dieses Worker-Prozesses auf (Upsert)."""
    await conn.execute(_WORKER_HEARTBEAT_SQL, worker_id, _now(now), version)


async def worker_seen_at(conn: asyncpg.Connection, worker_id: str | None = None) -> datetime | None:
    """Letzter Heartbeat eines bestimmten Workers oder, ohne `worker_id`, des
    juengsten ueberhaupt („Worker zuletzt gesehen“)."""
    if worker_id is None:
        seen: datetime | None = await conn.fetchval("SELECT max(seen_at) FROM worker_heartbeat")
    else:
        seen = await conn.fetchval(
            "SELECT seen_at FROM worker_heartbeat WHERE worker_id = $1", worker_id
        )
    return seen


#: Health-Feld `worker` (ADR-0057 §7): `unknown` = keine Heartbeat-Zeile.
WorkerHealth = Literal["ok", "stale", "unknown"]


def classify_worker_seen(seen: datetime | None, now: datetime | None = None) -> WorkerHealth:
    """`ok`, wenn der juengste Heartbeat hoechstens `WORKER_STALE_AFTER` alt ist,
    sonst `stale`; ohne Heartbeat `unknown`."""
    if seen is None:
        return "unknown"
    return "stale" if _now(now) - seen > WORKER_STALE_AFTER else "ok"


async def worker_health(conn: asyncpg.Connection, now: datetime | None = None) -> WorkerHealth:
    """Health-Feld `worker` aus dem juengsten Heartbeat aller Worker.

    Laeuft auch auf der App-Rolle `who2be_app` (Lese-Grant, Migration 0102).
    """
    return classify_worker_seen(await worker_seen_at(conn), now)


# --- Advisory-Lock ------------------------------------------------------------

_LOCK_ID_SQL = "hashtextextended($1::text || $2::text, 0)"


async def try_advisory_lock(conn: asyncpg.Connection, routine: str) -> bool:
    """`pg_try_advisory_lock` (Session-Lock) fuer die Routine; nicht blockierend."""
    acquired: bool = await conn.fetchval(
        f"SELECT pg_try_advisory_lock({_LOCK_ID_SQL})", LOCK_NAME_PREFIX, routine
    )
    return acquired


async def release_advisory_lock(conn: asyncpg.Connection, routine: str) -> bool:
    """Gibt den Session-Lock frei. `False`, wenn diese Session ihn nicht hielt."""
    released: bool = await conn.fetchval(
        f"SELECT pg_advisory_unlock({_LOCK_ID_SQL})", LOCK_NAME_PREFIX, routine
    )
    return released


@asynccontextmanager
async def routine_lock(routine: str, dsn: str | None = None) -> AsyncIterator[bool]:
    """Advisory-Lock auf einer **dedizierten Direktverbindung**.

    Liefert `True`, wenn der Lock gehalten wird, sonst `False` (dann laeuft
    gerade ein anderer Lauf derselben Routine; der Aufrufer beendet seinen
    Lauf als `skipped`). Beim Verlassen wird der Lock freigegeben und die
    Verbindung geschlossen — das Schliessen gibt einen Session-Lock auch dann
    frei, wenn das Unlock selbst scheitert.
    """
    conn = await asyncpg.connect(dsn or get_settings().database_url)
    try:
        acquired = await try_advisory_lock(conn, routine)
        try:
            yield acquired
        finally:
            if acquired and not conn.is_closed():
                # Scheitert das Unlock, gibt close() unten den Session-Lock frei.
                with suppress(asyncpg.PostgresError, OSError):
                    await release_advisory_lock(conn, routine)
    finally:
        await conn.close()
