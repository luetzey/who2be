"""Die Routinen des Workers (ADR-0057 §4/§6/§8, Paket P2).

Angebunden werden die bestehenden Nachtlaeufe; ihre Logik bleibt in `core/`:

| Routine                 | Zeitplan (UTC) | Timeout | catch_up | Tabellen-Store |
|-------------------------|----------------|---------|----------|----------------|
| `purge`                 | `30 3 * * *`   | 1 h     | ja       | ja (Sweep mit 24-h-Karenz) |
| `memory-expire`         | `45 3 * * *`   | 15 min  | ja       | nein           |
| `audit-retention`       | `0 4 * * *`    | 15 min  | ja       | nein           |
| `routine-run-retention` | `15 4 * * *`   | 15 min  | nein     | nein           |

Purge und Verfall tragen dieselben Zeiten wie bisher die Hetzner-Crontab und
die Dokploy-Schedules (RUNBOOK §Retention-Cron, Cloud-Inbetriebnahme
§Hintergrundjobs: 03:30 bzw. 03:45). `audit-retention` (Owner E1a,
`core/audit_retention.py`) loescht den anonymen Audit-Rest geloeschter
Workspaces/Orgs 12 Monate nach der Anonymisierung; sie hat kein eigenes CLI.
`routine-run-retention` laeuft danach und
vor der Access-Log-Rotation (04:30). Jeder Zeitplan ist per
`WHO2BE_ROUTINE_<NAME>_SCHEDULE` ueberschreibbar.

Jede Routine rechnet mit `ctx.slot` statt `datetime.now` und liefert **nur
Zaehler**.

**CLIs ueber denselben Weg (§8).** `who2be-purge` und `who2be-memory-expire`
rufen `run_as_cli`: derselbe Slot-Claim (`trigger='cli'`, Startzeit als Slot,
Ausweichen um 1 µs nach PM-W5), derselbe Advisory-Lock, dieselbe Routine-
Funktion wie der Worker. Es gibt keinen zweiten Ausfuehrungspfad.

**Externer Zeitplan (§8 Schritt 2).** `routine-run-retention` prueft taeglich
`store.external_schedules` und schreibt je betroffener Routine eine
WARN-Zeile. Die Abfrage selbst liegt im Store, damit der Betreiber-Endpunkt
(P4b) sie wiederverwendet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import asyncpg

from who2be_api.core.audit_retention import delete_expired_anonymized_audit
from who2be_api.core.config import get_settings
from who2be_api.core.memory_expiry import expire_unconfirmed_memories
from who2be_api.core.purge import purge_counters, purge_expired, run_retention_sweeps
from who2be_api.repositories.account_repository import PgAccountPurgeRepository
from who2be_api.worker import store
from who2be_api.worker.registry import REGISTRY, Registry, RoutineContext, routine
from who2be_api.worker.runner import Runner, RunOutcome

logger = logging.getLogger(__name__)

PURGE = "purge"
MEMORY_EXPIRE = "memory-expire"
AUDIT_RETENTION = "audit-retention"
ROUTINE_RUN_RETENTION = "routine-run-retention"


@routine(
    PURGE,
    schedule="30 3 * * *",
    timeout=timedelta(hours=1),
    catch_up=True,
    touches_tablestore=True,
)
async def purge(ctx: RoutineContext) -> dict[str, int]:
    """DSGVO-Hard-Purge plus WorkArea-/KB-Sweeps (`core/purge.py`)."""
    result = await purge_expired(PgAccountPurgeRepository(ctx.conn), ctx.slot)
    result = await run_retention_sweeps(ctx.conn, result, ctx.slot)
    return purge_counters(result)


@routine(
    MEMORY_EXPIRE,
    schedule="45 3 * * *",
    timeout=timedelta(minutes=15),
    catch_up=True,
)
async def memory_expire(ctx: RoutineContext) -> dict[str, int]:
    """Verfall unbestaetigten Gedaechtnisses (`core/memory_expiry.py`)."""
    return {"expired": await expire_unconfirmed_memories(ctx.conn, ctx.slot)}


@routine(
    AUDIT_RETENTION,
    schedule="0 4 * * *",
    timeout=timedelta(minutes=15),
    catch_up=True,
)
async def audit_retention(ctx: RoutineContext) -> dict[str, int]:
    """Loescht den anonymen Audit-Rest 12 Monate nach der Anonymisierung (E1a)."""
    return {"deleted": await delete_expired_anonymized_audit(ctx.conn, ctx.slot)}


@routine(
    ROUTINE_RUN_RETENTION,
    schedule="15 4 * * *",
    timeout=timedelta(minutes=15),
)
async def routine_run_retention(ctx: RoutineContext) -> dict[str, int]:
    """Loescht Laufprotokoll aelter als 90 Tage; meldet externe Zeitplaene."""
    deleted = await store.delete_runs_before(ctx.conn, ctx.slot - store.ROUTINE_RUN_RETENTION)
    external = await store.external_schedules(ctx.conn, now=ctx.slot)
    for name, last_day in external.items():
        logger.warning(
            "Externer Zeitplan erkannt: Routine %s lief an aufeinanderfolgenden Tagen "
            "per CLI (zuletzt %s). Crontab-Zeile bzw. Dokploy-Schedule kann entfernt "
            "werden, der Worker uebernimmt.",
            name,
            last_day.isoformat(),
        )
    return {"deleted_runs": deleted, "external_schedules": len(external)}


# --- CLI-Pfad ----------------------------------------------------------------


@dataclass(frozen=True)
class CliRun:
    """Ergebnis eines CLI-Laufs: Lauf-Ausgang plus Zaehler (bei `succeeded`)."""

    outcome: RunOutcome
    counters: dict[str, int] | None


class CliRunFailed(RuntimeError):
    """Der CLI-Lauf endete als `failed` ohne eigene Ausnahme (z. B. Timeout)."""


async def run_as_cli(
    name: str,
    *,
    registry: Registry = REGISTRY,
    dsn: str | None = None,
    now: datetime | None = None,
) -> CliRun:
    """Fuehrt eine Routine als CLI-Lauf aus (ADR-0057 §8).

    `trigger='cli'`, die Startzeit ist der Slot; ist er belegt, weicht der
    Lauf auf den naechsten freien Zeitpunkt aus (PM-W5). Haelt gerade ein
    anderer Lauf den Advisory-Lock, endet der CLI-Lauf als `skipped`.

    Der CLI-Lauf schreibt **keinen** `worker_heartbeat`: ein CLI im
    api-Container ist kein Worker.

    Wirft die Routine, steht im Protokoll nur die Klasse; die Ausnahme selbst
    wird danach erneut geworfen, damit der Aufrufer wie bisher mit Traceback
    und Exit ungleich 0 endet. Der Lauf ist schon abgeschlossen, bevor sie
    wieder auftaucht.
    """
    target = registry.get(name)
    counters: list[dict[str, int]] = []
    raised: list[BaseException] = []

    async def capture(ctx: RoutineContext) -> dict[str, int]:
        try:
            result = await target.fn(ctx)
        except Exception as exc:
            raised.append(exc)
            raise
        counters.append(result)
        return result

    dsn = dsn or get_settings().database_url

    def clock() -> datetime:
        return now if now is not None else datetime.now(UTC)

    # env={}: Env-Overrides betreffen Zeitplaene; ein CLI-Lauf ist davon
    # unabhaengig und soll auch bei einem kaputten Override laufen (Notfallweg).
    runner = Runner(registry, dsn=dsn, env={}, clock=clock, worker_heartbeat=False)
    try:
        conn = await asyncpg.connect(dsn)
    except (asyncpg.PostgresError, OSError) as exc:
        # Nur die Klasse: die Meldung kann DSN-Teile tragen.
        raise SystemExit(f"Datenbank nicht erreichbar ({type(exc).__name__}).") from exc
    try:
        outcome = await runner.execute(
            conn, replace(target, fn=capture), clock(), "cli", dodge=True
        )
    finally:
        await conn.close()
    if outcome is None:  # pragma: no cover — dodge liefert immer einen Slot oder wirft
        raise RuntimeError("Kein freier Slot gefunden.")
    if raised:
        raise raised[0]
    if outcome.status == "failed":
        raise CliRunFailed(f"Routine {name} fehlgeschlagen ({outcome.error_class}).")
    return CliRun(outcome, counters[0] if counters else None)


def skipped_message(name: str) -> str:
    """Klare Meldung fuer einen CLI-Lauf, der wegen des Locks entfallen ist."""
    return (
        f"Routine {name} uebersprungen: ein anderer Lauf (Worker oder CLI) haelt "
        "gerade den Lock. Nichts zu tun; der laufende Lauf erledigt die Arbeit."
    )
