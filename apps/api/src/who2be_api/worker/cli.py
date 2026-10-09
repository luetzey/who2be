"""CLI `who2be-worker` (ADR-0057 §3, P1c).

    who2be-worker [run]                 Tick-Schleife bis SIGTERM (Default)
    who2be-worker check                 Exit 0, wenn der eigene Heartbeat frisch ist
    who2be-worker list                  effektive Zeitplan-Tabelle
    who2be-worker run-once <name> [--force]
                                        ein manueller Lauf (trigger 'manual')

`check` ist der Container-Healthcheck: Er sucht den juengsten
`worker_heartbeat` dieses Hosts (Worker-ID `<hostname>:<pid>`; im Container
ist der Hostname die Container-ID) und verlangt, dass er juenger als
`WORKER_HEALTHCHECK_MAX_AGE` (2 min, PM-W4) ist.

`run-once` traegt die Startzeit als Slot und weicht bei einem belegten Slot um
1 µs aus (PM-W5). Er nimmt denselben Advisory-Lock wie der Worker: Laeuft die
Routine gerade, endet er als `skipped` (Exit 1). Ohne `--force` lehnt er
abgeschaltete Routinen ab.

Die Routinen selbst werden per Import in `REGISTRY` angemeldet (P2).
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

import asyncpg

from who2be_api.core.config import get_settings
from who2be_api.core.logging import configure_logging
from who2be_api.worker.registry import REGISTRY, Registry
from who2be_api.worker.runner import Runner
from who2be_api.worker.schedule import ScheduleError, effective_table, format_table
from who2be_api.worker.store import WORKER_HEALTHCHECK_MAX_AGE

_HOST_SEEN_SQL = """
SELECT max(seen_at) FROM worker_heartbeat
WHERE left(worker_id, length($1) + 1) = $1 || ':'
"""


async def host_heartbeat_fresh(
    conn: asyncpg.Connection, host: str, *, now: datetime | None = None
) -> bool:
    """Ist der juengste Heartbeat dieses Hosts juenger als die Healthcheck-Schwelle?"""
    seen: datetime | None = await conn.fetchval(_HOST_SEEN_SQL, host)
    if seen is None:
        return False
    return (now or datetime.now(UTC)) - seen < WORKER_HEALTHCHECK_MAX_AGE


async def _connect() -> asyncpg.Connection:
    try:
        return await asyncpg.connect(get_settings().database_url)
    except (asyncpg.PostgresError, OSError) as exc:
        # Nur die Klasse: die Meldung kann DSN-Teile tragen.
        raise SystemExit(f"Datenbank nicht erreichbar ({type(exc).__name__}).") from exc


async def _check() -> int:
    conn = await _connect()
    try:
        fresh = await host_heartbeat_fresh(conn, socket.gethostname())
    finally:
        await conn.close()
    print("worker: healthy" if fresh else "worker: stale")
    return 0 if fresh else 1


async def _run(registry: Registry) -> int:
    runner = Runner(registry)
    runner.install_signal_handlers()
    await runner.run()
    return 0


async def _run_once(registry: Registry, name: str, force: bool) -> int:
    runner = Runner(registry)
    conn = await _connect()
    try:
        outcome = await runner.run_once(conn, name, force=force)
    finally:
        await conn.close()
    detail = f" ({outcome.error_class})" if outcome.error_class else ""
    print(f"{outcome.routine} @ {outcome.slot.isoformat()}: {outcome.status}{detail}")
    return 0 if outcome.status == "succeeded" else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="who2be-worker", description="Hintergrund-Routinen von Who2Be (ADR-0057)."
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Tick-Schleife bis SIGTERM (Default).")
    sub.add_parser("check", help="Healthcheck: eigener Heartbeat juenger als 2 min.")
    sub.add_parser("list", help="Effektive Zeitplan-Tabelle zeigen.")
    once = sub.add_parser("run-once", help="Eine Routine jetzt einmal ausfuehren.")
    once.add_argument("name", help="Name der Routine.")
    once.add_argument(
        "--force", action="store_true", help="Auch ausfuehren, wenn per Env abgeschaltet."
    )
    return parser


def main(argv: Sequence[str] | None = None, registry: Registry = REGISTRY) -> int:
    """Einstieg mit Exit-Code (testbar); `cli` reicht ihn an `sys.exit` weiter."""
    args = _parser().parse_args(argv)
    command = args.command or "run"
    try:
        if command == "list":
            print(format_table(effective_table(registry)))
            return 0
        if command == "check":
            return asyncio.run(_check())
        configure_logging(get_settings().log_format)
        if command == "run-once":
            if args.name not in registry:
                print(f"Unbekannte Routine {args.name!r}.", file=sys.stderr)
                return 2
            return asyncio.run(_run_once(registry, args.name, args.force))
        return asyncio.run(_run(registry))
    except ScheduleError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def cli() -> None:
    """Console-Entrypoint `who2be-worker`."""
    sys.exit(main())


if __name__ == "__main__":
    cli()
