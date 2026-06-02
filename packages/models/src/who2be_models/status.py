"""Status-Workflow pro Version (TASK Phase 2.1b).

Single-Source der State-Machine: API/MCP/Web teilen sich `VersionStatus` +
`ALLOWED_TRANSITIONS`. Die DB-Invariante "max. 1 Draft / 1 Review / 1 Active
pro Entity" lebt parallel in `0011_status_on_versions.sql` (Partial Unique
Indices) — diese Datei spiegelt nur die Anwendungs-Sicht.

Status-Wechsel bumpt KEINE Version; Audit-Eintraege landen in
`status_history` (siehe `status_history.py`).
"""

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class VersionStatus(StrEnum):
    """Status einer Persona-/Playbook-/Resource-Version."""

    draft = "draft"
    review = "review"
    active = "active"
    inactive = "inactive"


# State-Machine. `review -> draft` ist erlaubt, damit ein Reviewer den Autor
# zurueck an den Tisch schicken kann. `inactive -> draft` reaktiviert eine
# archivierte Version fuer weitere Bearbeitung (Edge-Case fuer das Lifecycle-
# Modell). `active -> draft` ist der „Reset-auf-Draft" (Track A): die aktive
# Version wird zur Bearbeitung zurueckgeholt; der Transition-Service reaktiviert
# dabei die zuletzt aktive Version, damit die Invariante „genau eine aktiv"
# haelt (siehe version_status.py). Direkte Uebergaenge nach `inactive` sind
# ausschliesslich aus `active` erlaubt — Drafts/Reviews werden ueber
# `review -> draft` (Bounce) bzw. ueber `active -> inactive` indirekt verworfen.
ALLOWED_TRANSITIONS: Mapping[VersionStatus, frozenset[VersionStatus]] = {
    VersionStatus.draft: frozenset({VersionStatus.review}),
    VersionStatus.review: frozenset({VersionStatus.active, VersionStatus.draft}),
    VersionStatus.active: frozenset({VersionStatus.inactive, VersionStatus.draft}),
    VersionStatus.inactive: frozenset({VersionStatus.draft}),
}


def is_allowed_transition(from_status: VersionStatus, to_status: VersionStatus) -> bool:
    """True wenn der Uebergang in der State-Machine erlaubt ist."""
    return to_status in ALLOWED_TRANSITIONS[from_status]


class VersionTransitionRequest(BaseModel):
    """Eingabe fuer `POST .../versions/{v}/transition`."""

    model_config = ConfigDict(extra="forbid")

    to: VersionStatus
    note: str | None = Field(default=None, max_length=2_000)
