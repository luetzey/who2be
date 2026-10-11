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
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


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


# Menschenlesbare SSoT-Beschreibung der State-Machine fuer Tool-/API-Docs.
# Spiegelt `ALLOWED_TRANSITIONS` 1:1 — bei Aenderungen der Map hier mitziehen.
# Genutzt in den drei MCP-`transition_*`-Docstrings (per f-String), damit der
# Wortlaut nicht dreifach driftet.
TRANSITION_RULE_DOC = (
    "Erlaubte Uebergaenge (State-Machine): draft->review, review->{active,draft}, "
    "active->{inactive,draft}, inactive->draft. "
    "draft->active geht NICHT direkt — der Zwischenstopp review ist Pflicht. "
    "Promote (->active) und Retire (->inactive) erfordern die admin-Rolle, "
    "sonst genuegt editor."
)


def is_allowed_transition(from_status: VersionStatus, to_status: VersionStatus) -> bool:
    """True wenn der Uebergang in der State-Machine erlaubt ist."""
    return to_status in ALLOWED_TRANSITIONS[from_status]


# Obergrenze fuer `override_reason` (ADR-0053 Anhang B, gesetzte Annahme): die
# halbe `note`-Grenze, weil Grund und `note` zusammen in dieselbe
# `status_history.note` geschrieben werden.
OVERRIDE_REASON_MAX_LENGTH = 1_000
TRANSITION_NOTE_MAX_LENGTH = 2_000


# `acknowledge_test_report` und `override_reason` gehoeren zum
# Aktivierungsvertrag aus ADR-0053 6.3. Ein leerer Grund ist hier zulaessig
# und wird erst vom Service als 409 `test_override_reason_required`
# beantwortet — der Vertrag unterscheidet „bestaetigt ohne Grund"
# ausdruecklich von einem Formatfehler.
class VersionTransitionRequest(BaseModel):
    """Eingabe fuer `POST .../versions/{v}/transition`.

    Sind Pruefaelle der Zielversion rot oder fehlen Ergebnisse, verlangt
    `to='active'` zusaetzlich `acknowledge_test_report=true` und einen
    `override_reason`. Ist die Pruefall-Menge leer oder alles `pass`, werden
    beide ignoriert.

    `override_reason` wird getrimmt; danach gilt hoechstens 1 000 Zeichen. Ein
    leerer Grund wird mit 409 `test_override_reason_required` abgelehnt.
    """

    model_config = ConfigDict(extra="forbid")

    to: VersionStatus
    note: str | None = Field(default=None, max_length=TRANSITION_NOTE_MAX_LENGTH)
    acknowledge_test_report: bool = False
    override_reason: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, max_length=OVERRIDE_REASON_MAX_LENGTH),
        ]
        | None
    ) = None
