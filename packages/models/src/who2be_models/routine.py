"""Betreiber-Sicht auf die Hintergrund-Routinen (ADR-0057 §7, §8 Schritt 2).

Read-Modelle fuer den Betreiber-Endpunkt (`/v1/system/routines`, Paket P4c).
Die Daten kommen aus Registry, effektiver Zeitplan-Tabelle, `routine_run` und
`worker_heartbeat` (`apps/api/src/who2be_api/services/routine_overview_service.py`).

Die Routinen sind workspace-uebergreifend; die Modelle tragen deshalb nur
Zaehler und Klassennamen, nie Inhalte oder personenbezogene Daten. Sichtbar
sind sie ausschliesslich fuer Betreiber (W2 = a).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Status eines Laufs, wie ihn `routine_run.status` erlaubt (Migration 0102).
RoutineRunStatus = Literal["running", "succeeded", "failed", "skipped"]
#: Ausloeser eines Laufs (`routine_run.trigger`).
RoutineRunTrigger = Literal["schedule", "cli", "manual"]
#: Herkunft der wirksamen Konfiguration: `env`, sobald ein Override greift.
RoutineConfigSource = Literal["code", "env"]


class RoutineLastRun(BaseModel):
    """Der juengste Lauf einer Routine, gleich welcher Status."""

    model_config = ConfigDict(frozen=True)

    status: RoutineRunStatus
    trigger: RoutineRunTrigger
    started_at: datetime
    #: `None`, solange der Lauf noch `running` ist.
    duration_ms: int | None = Field(default=None, ge=0)
    #: Nur Zaehler (Migration 0102 erzwingt das per CHECK).
    result: dict[str, int | float] | None = None
    #: Nur der Klassenname der Exception bzw. `Abandoned`; nie eine Meldung.
    error_class: str | None = None


class RoutineStatus(BaseModel):
    """Eine Routine mit wirksamem Zeitplan und Laufstand."""

    model_config = ConfigDict(frozen=True)

    name: str
    #: Kanonische Textform: Cron-Ausdruck oder `@every …`.
    schedule: str
    enabled: bool
    source: RoutineConfigSource
    last_run: RoutineLastRun | None = None
    #: Naechster Termin nach Zeitplan; `None`, wenn die Routine abgeschaltet ist.
    next_run_at: datetime | None = None
    #: Ende des juengsten erfolgreichen Laufs.
    last_success_at: datetime | None = None
    #: CLI-Laeufe an zwei aufeinanderfolgenden Tagen: ein Host-Cron oder
    #: Dokploy-Schedule laeuft noch neben dem Worker und kann entfernt werden.
    external_schedule_detected: bool = False


class RoutinesOverview(BaseModel):
    """Alle registrierten Routinen plus „Worker zuletzt gesehen“."""

    model_config = ConfigDict(frozen=True)

    routines: list[RoutineStatus]
    #: Juengster Heartbeat aller Worker; `None`, wenn nie einer lief.
    worker_last_seen_at: datetime | None = None
