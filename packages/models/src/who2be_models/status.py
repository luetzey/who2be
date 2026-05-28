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


class VersionStatus(StrEnum):
    """Status einer Persona-/Playbook-/Resource-Version."""

    draft = "draft"
    review = "review"
    active = "active"
    inactive = "inactive"


# State-Machine. `inactive` ist terminal (passt zum Migration-Backfill, in
# dem alle Nicht-Current-Versionen auf `inactive` gehen). `review -> draft`
# ist erlaubt, damit ein Reviewer den Autor zurueck an den Tisch schicken
# kann ohne den Draft zu verwerfen.
ALLOWED_TRANSITIONS: Mapping[VersionStatus, frozenset[VersionStatus]] = {
    VersionStatus.draft: frozenset({VersionStatus.review, VersionStatus.inactive}),
    VersionStatus.review: frozenset(
        {VersionStatus.draft, VersionStatus.active, VersionStatus.inactive}
    ),
    VersionStatus.active: frozenset({VersionStatus.inactive}),
    VersionStatus.inactive: frozenset(),
}


def is_allowed_transition(from_status: VersionStatus, to_status: VersionStatus) -> bool:
    """True wenn der Uebergang in der State-Machine erlaubt ist."""
    return to_status in ALLOWED_TRANSITIONS[from_status]
