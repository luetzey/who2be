"""Runner des Workers: Tick-Schleife, Slot-Claim, Lock, Timeout (ADR-0057 §3/§5/§6).

Ein Tick (etwa alle `TICK_INTERVAL`) macht der Reihe nach:

1. `worker_heartbeat` auffrischen,
2. abgebrochene Laeufe markieren (`store.mark_abandoned`, Schwelle 5 min),
3. ist der Worker aktiviert: je aktivierter Routine den juengsten faelligen
   Slot berechnen, `claim_slot`, dann den Advisory-Lock auf einer dedizierten
   Direktverbindung nehmen. Ist der Lock belegt (ein CLI- oder manueller Lauf
   ist aktiv), endet der Lauf als `skipped`.

Ein Lauf bekommt eine **eigene Verbindung** (`RoutineContext.conn`) und laeuft
mit dem Timeout seiner Routine. Waehrend er laeuft, frischt eine Nebenaufgabe
etwa alle `RUN_HEARTBEAT_INTERVAL` `routine_run.heartbeat_at` und den
Worker-Heartbeat auf — sonst saehe der 2-min-Healthcheck einen einstuendigen
Purge als toten Worker. Danach `succeeded` mit den Zaehlern oder `failed` mit
**nur** dem Namen der Exception-Klasse.

Laeufe einer Routine sind strikt nacheinander; Routinen laufen ebenfalls
nacheinander. Bei fuenf bis zehn Nachtlaeufen reicht das, und ein verspaeteter
Slot wird beim naechsten Tick nachgezogen (der juengste faellige Slot zaehlt).

**Nachholen (`catch_up`).** Nur beim Start: Liegt ein Slot der Routine
zwischen ihrem letzten Erfolg und jetzt (oder gibt es keinen Erfolg), laeuft
sie genau **einmal** sofort — nicht je verpasstem Slot. Ohne `catch_up`
werden Slots vor dem Start nicht nachgeholt; der Tick belegt nur Slots ab dem
Startzeitpunkt.

**Herunterfahren.** Die erste Stopp-Anforderung (SIGTERM/SIGINT) belegt keine
neuen Slots mehr und laesst die laufende Routine bis zu ihrem Ende oder
Timeout weiterlaufen. Eine zweite bricht die Routine ab; der Lauf endet sauber
als `failed` mit `error_class='WorkerShutdown'`.

**`WHO2BE_WORKER_ENABLED=false`.** Der Prozess laeuft weiter, meldet
Heartbeat und markiert Abgebrochenes, belegt aber keine Slots.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg

from who2be_api import __version__
from who2be_api.core.config import get_settings
from who2be_api.worker import store
from who2be_api.worker.registry import Registry, Routine, RoutineContext
from who2be_api.worker.schedule import (
    EffectiveRoutine,
    effective_table,
    format_table,
    unknown_overrides,
    worker_enabled,
)
from who2be_api.worker.store import FinalStatus, RunTrigger

logger = logging.getLogger(__name__)

#: Abstand der Ticks (ADR-0057 §5: etwa alle 30 s).
TICK_INTERVAL = timedelta(seconds=30)
#: Abstand des Lauf-Heartbeats waehrend einer Routine (§6: etwa alle 30 s).
RUN_HEARTBEAT_INTERVAL = timedelta(seconds=30)
#: Ausweichschritt, wenn ein manueller Slot schon belegt ist (PM-W5).
SLOT_DODGE = timedelta(microseconds=1)
#: Obergrenze der Ausweichversuche; danach ist etwas grundsaetzlich falsch.
_MAX_SLOT_DODGES = 1000

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class WorkerShutdown(Exception):  # noqa: N818 — Name landet als error_class im Protokoll
    """Lauf wurde durch die zweite Stopp-Anforderung abgebrochen."""


class InvalidRoutineResult(Exception):  # noqa: N818 — Name landet als error_class
    """Die Routine lieferte etwas anderes als Zaehler."""


@dataclass(frozen=True)
class RunOutcome:
    """Ergebnis eines belegten Laufs (fuer Log, CLI und Tests)."""

    routine: str
    slot: datetime
    trigger: RunTrigger
    status: FinalStatus
    error_class: str | None = None


def _check_counters(result: object) -> dict[str, int | float]:
    """Nur Zaehler: `dict[str, int|float]` ohne bool (wie `store.finish_run`)."""
    if not isinstance(result, dict):
        raise InvalidRoutineResult
    for key, value in result.items():
        if not isinstance(key, str) or isinstance(value, bool):
            raise InvalidRoutineResult
        if not isinstance(value, int | float):
            raise InvalidRoutineResult
    return result


class Runner:
    """Fuehrt die Routinen einer `Registry` nach Zeitplan aus.

    `clock`, `env` und die Intervalle sind fuer Tests injizierbar; im Betrieb
    gelten Systemuhr (UTC), `os.environ` und die Konstanten oben.
    """

    def __init__(
        self,
        registry: Registry,
        *,
        dsn: str | None = None,
        worker_id: str | None = None,
        env: Mapping[str, str] | None = None,
        clock: Clock = _utc_now,
        tick_interval: timedelta = TICK_INTERVAL,
        run_heartbeat_interval: timedelta = RUN_HEARTBEAT_INTERVAL,
        version: str = __version__,
        worker_heartbeat: bool = True,
    ) -> None:
        self.registry = registry
        self.dsn = dsn or get_settings().database_url
        self.worker_id = worker_id or store.default_worker_id()
        self.version = version
        # CLI-Laeufe (`routines.run_as_cli`) sind kein Worker und melden deshalb
        # keinen `worker_heartbeat`; der Lauf-Heartbeat bleibt.
        self._worker_heartbeat = worker_heartbeat
        self._env = env
        self._clock = clock
        self._tick_interval = tick_interval
        self._run_heartbeat_interval = run_heartbeat_interval
        # Startfehler bei ungueltigen Overrides, nicht erst im ersten Tick.
        self.table: list[EffectiveRoutine] = effective_table(registry, env)
        self.enabled = worker_enabled(env)
        self.started_at: datetime | None = None
        self._stop = asyncio.Event()
        self._abort = asyncio.Event()

    # --- Steuerung ------------------------------------------------------------

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def request_stop(self) -> None:
        """Erste Anforderung: keine neuen Slots. Zweite: laufende Routine abbrechen."""
        if self._stop.is_set():
            if not self._abort.is_set():
                logger.warning("Zweite Stopp-Anforderung: laufende Routine wird abgebrochen.")
            self._abort.set()
            return
        logger.info("Stopp angefordert: keine neuen Slots, laufende Routine darf enden.")
        self._stop.set()

    def install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.request_stop)

    # --- Start und Schleife -----------------------------------------------------

    def log_table(self) -> None:
        logger.info(
            "Worker %s (Version %s), %s. Effektive Zeitplaene (UTC):\n%s",
            self.worker_id,
            self.version,
            "aktiviert" if self.enabled else "abgeschaltet (WHO2BE_WORKER_ENABLED=false)",
            format_table(self.table),
        )
        for key in unknown_overrides(self.registry, self._env):
            logger.warning("%s passt zu keiner registrierten Routine und wirkt nicht.", key)

    async def start(self, conn: asyncpg.Connection) -> list[RunOutcome]:
        """Start: Tabelle loggen, Heartbeat, Abgebrochenes markieren, Nachholen."""
        self.started_at = self._clock()
        self.log_table()
        await self._housekeeping(conn)
        if not self.enabled:
            return []
        outcomes: list[RunOutcome] = []
        for row in self.table:
            routine = self.registry.get(row.name)
            if not (row.enabled and routine.catch_up) or self.stopping:
                continue
            outcome = await self._catch_up(conn, routine, row)
            if outcome is not None:
                outcomes.append(outcome)
        return outcomes

    async def tick(self, conn: asyncpg.Connection) -> list[RunOutcome]:
        """Ein Tick: Heartbeat, Abandoned, faellige Slots belegen und ausfuehren."""
        if self.started_at is None:
            raise RuntimeError("Runner.start() vor dem ersten Tick aufrufen.")
        await self._housekeeping(conn)
        if not self.enabled:
            return []
        outcomes: list[RunOutcome] = []
        for row in self.table:
            if not row.enabled or self.stopping:
                continue
            slot = row.schedule.latest_slot(self._clock())
            if slot < self.started_at:
                # Vor dem Start faellig: nur `catch_up` holt nach (in `start`).
                continue
            outcome = await self.execute(conn, self.registry.get(row.name), slot, "schedule")
            if outcome is not None:
                outcomes.append(outcome)
        return outcomes

    async def run(self) -> None:
        """Hauptschleife bis zur Stopp-Anforderung (`who2be-worker run`)."""
        conn: asyncpg.Connection | None = None
        started = False
        while not self.stopping:
            try:
                if conn is None or conn.is_closed():
                    conn = await asyncpg.connect(self.dsn)
                if not started:
                    await self.start(conn)
                    started = True
                else:
                    await self.tick(conn)
            except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as exc:
                # Nur die Klasse: Meldungen koennen DSN-Teile tragen.
                logger.error(
                    "Tick fehlgeschlagen (%s); naechster Versuch im naechsten Tick.",
                    type(exc).__name__,
                )
                if conn is not None:
                    with suppress(Exception):
                        await conn.close()
                conn = None
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), self._tick_interval.total_seconds())
        if conn is not None:
            with suppress(Exception):
                await conn.close()
        logger.info("Worker %s beendet.", self.worker_id)

    # --- Ausfuehrung ------------------------------------------------------------

    async def _housekeeping(self, conn: asyncpg.Connection) -> None:
        now = self._clock()
        await store.record_worker_heartbeat(
            conn, worker_id=self.worker_id, version=self.version, now=now
        )
        abandoned = await store.mark_abandoned(conn, now=now)
        if abandoned:
            logger.warning(
                "%d abgebrochene(r) Lauf/Laeufe auf failed/Abandoned gesetzt.", len(abandoned)
            )

    async def _catch_up(
        self, conn: asyncpg.Connection, routine: Routine, row: EffectiveRoutine
    ) -> RunOutcome | None:
        now = self._clock()
        latest = row.schedule.latest_slot(now)
        success = await store.last_success(conn, routine.name)
        if success is not None and success.slot >= latest:
            return None
        logger.info(
            "Routine %s: letzter Erfolg vor dem faelligen Slot, einmal nachholen.", routine.name
        )
        # Bevorzugt den verpassten Slot selbst. Ist er schon belegt, laeuft er
        # entweder gerade (anderer Worker) oder ist fehlgeschlagen, abgebrochen
        # bzw. uebersprungen (Lock war belegt); nur im zweiten Fall traegt der
        # Nachhol-Lauf den Startzeitpunkt — sonst liefe ein Slot doppelt.
        # `skipped` zaehlt mit: der Lauf, der den Lock hielt, kann selbst
        # gescheitert sein, und der letzte Erfolg liegt ja vor dem Slot.
        outcome = await self.execute(conn, routine, latest, "schedule")
        if outcome is None:
            previous = await store.last_run(conn, routine.name)
            if previous is not None and previous.status in ("failed", "skipped"):
                outcome = await self.execute(conn, routine, now, "schedule", dodge=True)
        return outcome

    async def run_once(
        self, conn: asyncpg.Connection, name: str, *, force: bool = False
    ) -> RunOutcome:
        """Ein manueller Lauf (`who2be-worker run-once`), Startzeit als Slot (PM-W5).

        Ohne `force` lehnt er ab, wenn Worker oder Routine abgeschaltet sind.
        """
        routine = self.registry.get(name)
        row = next(r for r in self.table if r.name == name)
        if not force and not (self.enabled and row.enabled):
            raise PermissionError(
                f"Routine {name!r} ist abgeschaltet; mit --force trotzdem ausfuehren."
            )
        outcome = await self.execute(conn, routine, self._clock(), "manual", dodge=True)
        if outcome is None:  # pragma: no cover — dodge liefert immer einen Slot oder wirft
            raise RuntimeError("Kein freier Slot gefunden.")
        return outcome

    async def execute(
        self,
        conn: asyncpg.Connection,
        routine: Routine,
        slot: datetime,
        trigger: RunTrigger,
        *,
        dodge: bool = False,
    ) -> RunOutcome | None:
        """Belegt `slot` und fuehrt die Routine unter dem Advisory-Lock aus.

        `None`, wenn der Slot schon belegt ist. Mit `dodge` weicht der Lauf
        stattdessen um je `SLOT_DODGE` auf den naechsten freien Zeitpunkt aus.
        """
        run_id = await store.claim_slot(
            conn, routine.name, slot, trigger=trigger, worker_id=self.worker_id, now=self._clock()
        )
        attempts = 0
        while run_id is None and dodge:
            attempts += 1
            if attempts > _MAX_SLOT_DODGES:
                raise RuntimeError(f"Kein freier Slot fuer {routine.name!r} gefunden.")
            slot += SLOT_DODGE
            run_id = await store.claim_slot(
                conn,
                routine.name,
                slot,
                trigger=trigger,
                worker_id=self.worker_id,
                now=self._clock(),
            )
        if run_id is None:
            return None

        async with store.routine_lock(routine.name, self.dsn) as held:
            if not held:
                await store.finish_run(conn, run_id, "skipped", now=self._clock())
                logger.info(
                    "Routine %s, Slot %s: Lock belegt, skipped.", routine.name, slot.isoformat()
                )
                return RunOutcome(routine.name, slot, trigger, "skipped")
            logger.info("Routine %s, Slot %s (%s): Start.", routine.name, slot.isoformat(), trigger)
            result, error = await self._invoke(conn, routine, run_id, slot, trigger)
            # Abschluss noch unter dem Lock: ein wartender CLI-Lauf sieht erst
            # den fertigen Lauf.
            if error is None:
                await store.finish_run(conn, run_id, "succeeded", result=result, now=self._clock())
                logger.info(
                    "Routine %s, Slot %s: succeeded %s.", routine.name, slot.isoformat(), result
                )
                return RunOutcome(routine.name, slot, trigger, "succeeded")
            await store.finish_run(conn, run_id, "failed", error=error, now=self._clock())
            error_class = type(error).__name__
            logger.error(
                "Routine %s, Slot %s: failed (%s).", routine.name, slot.isoformat(), error_class
            )
            return RunOutcome(routine.name, slot, trigger, "failed", error_class)

    async def _invoke(
        self,
        conn: asyncpg.Connection,
        routine: Routine,
        run_id: UUID,
        slot: datetime,
        trigger: RunTrigger,
    ) -> tuple[dict[str, int | float] | None, BaseException | None]:
        """Fuehrt die Routine mit Timeout aus; liefert (Zaehler, None) oder (None, Fehler)."""
        beat_done = asyncio.Event()
        beat = asyncio.create_task(self._beat(conn, run_id, beat_done))
        try:
            routine_conn = await asyncpg.connect(self.dsn)
        except (asyncpg.PostgresError, OSError) as exc:
            beat_done.set()
            await beat
            return None, exc
        try:
            ctx = RoutineContext(
                conn=routine_conn, slot=slot, trigger=trigger, worker_id=self.worker_id
            )
            work = asyncio.create_task(
                asyncio.wait_for(routine.fn(ctx), routine.timeout.total_seconds())
            )
            abort = asyncio.create_task(self._abort.wait())
            try:
                await asyncio.wait({work, abort}, return_when=asyncio.FIRST_COMPLETED)
            finally:
                abort.cancel()
            if not work.done():
                work.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await work
                return None, WorkerShutdown()
            try:
                return _check_counters(work.result()), None
            except Exception as exc:  # noqa: BLE001 — jede Routinen-Ausnahme wird zu failed
                return None, exc
        finally:
            # Heartbeat sauber beenden statt abbrechen: ein abgebrochener
            # asyncpg-Aufruf liesse die Kontrollverbindung belegt zurueck.
            beat_done.set()
            await beat
            with suppress(Exception):
                await routine_conn.close()

    async def _beat(self, conn: asyncpg.Connection, run_id: UUID, done: asyncio.Event) -> None:
        interval = self._run_heartbeat_interval.total_seconds()
        while True:
            with suppress(TimeoutError):
                await asyncio.wait_for(done.wait(), interval)
            if done.is_set():
                return
            now = self._clock()
            try:
                await store.touch_run(conn, run_id, now=now)
                if self._worker_heartbeat:
                    await store.record_worker_heartbeat(
                        conn, worker_id=self.worker_id, version=self.version, now=now
                    )
            except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as exc:
                logger.warning("Lauf-Heartbeat fehlgeschlagen (%s).", type(exc).__name__)
