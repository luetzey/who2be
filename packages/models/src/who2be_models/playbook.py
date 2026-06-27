"""Pydantic-Modelle fuer das Playbook-Aggregat.

`type`, `tags` und `triggers` sind Teil des Versions-Inhalts und werden vom
Service auf die `playbook`-Zeile denormalisiert, damit `list_playbooks` ohne
Join filtern kann (siehe architecture.md §3).
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from who2be_models.locale import DEFAULT_LOCALE, ContentLocale, normalize_locale
from who2be_models.status import VersionStatus

# Eingabe-Limits — DoS-Schutz fuer in jsonb persistierte und unveraendert
# wiedergegebene Versions-Inhalte (siehe Persona-Pendant).
TagStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]


class PlaybookType(StrEnum):
    """Kurierte Playbook-Typen (Phase 3-0, Master-Plan §Track 0).

    Migration `0020_playbook_type_check.sql` setzt den passenden CHECK-
    Constraint in der DB. `PlaybookContent.type` bleibt aus Backward-Compat-
    Gruenden vorlaeufig `str`; Frontend/Service ziehen mit Track 3-A/B nach.
    """

    prompt = "prompt"
    instructions = "instructions"
    snippet = "snippet"
    workflow = "workflow"
    checklist = "checklist"
    faq = "faq"


# Kuratiertes Typ-Set fuer die Modell-Validierung — Spiegel des DB-CHECKs
# `playbook_type_check` (Migrationen 0020/0025). Einzige Quelle ist das Enum.
_PLAYBOOK_TYPE_VALUES: frozenset[str] = frozenset(member.value for member in PlaybookType)


class PlaybookContent(BaseModel):
    """Typisierter Inhalt einer Playbook-Version (`playbook_version.content`).

    Welle 4: description, body und type haben Default "" — Create erlaubt
    unvollstaendige Drafts. Promote-Validation (draft → review/active) prueft
    im Transition-Endpunkt auf vollstaendige Pflichtfelder.

    Track B (Nur-BlockNote): `body` ist immer ein stringifiziertes BlockNote-
    JSON-Dokument (`JSON.stringify(editor.document)`) mit Inline-Placeholder-
    Pills. Der frueher gefuehrte `body_format`-Schalter ist entfallen; Migration
    `0030_blocknote_only.sql` hat Altbestaende markdown-aware konvertiert und den
    `body_format`-Key aus allen Versions-Snapshots entfernt.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    body: str = Field(default="", max_length=50_000)
    # Welle 4: Default "" erlaubt Draft-Create ohne Typ. An `PlaybookType`
    # gebunden (∪ ""), damit ein ungueltiger Typ an der API-/MCP-Grenze ein
    # sauberes 422 liefert, statt erst beim INSERT als CheckViolation (500)
    # aufzuschlagen — und damit das MCP-Tool-Schema die erlaubten Werte
    # annonciert. Spiegelt den DB-CHECK `playbook_type_check` (Migration 0025).
    type: PlaybookType | Literal[""] = ""
    tags: list[TagStr] = Field(default_factory=list, max_length=50)
    triggers: str | None = Field(default=None, max_length=2_000)

    @field_validator("type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        """Spiegelt den DB-CHECK `playbook_type_check` (Migration 0020/0025) am
        Modell-Rand: erlaubt sind die kuratierten `PlaybookType`-Werte plus der
        Leerstring (Draft ohne Typ). Ohne diese Pruefung passiert ein nicht-
        kuratierter Typ (z. B. "Atomic" aus einem Import) die Pydantic-Schicht
        und schlaegt erst als unbehandelte `CheckViolationError` beim INSERT auf
        — der Client sieht dann faelschlich 500 statt 422. Reads sind sicher:
        die Migrationen garantieren, dass jeder persistierte Wert im Set liegt."""
        if value == "" or value in _PLAYBOOK_TYPE_VALUES:
            return value
        allowed = ", ".join(sorted(_PLAYBOOK_TYPE_VALUES))
        raise ValueError(
            f"Ungueltiger Playbook-Typ {value!r}; erlaubt: {allowed} (oder leer fuer Drafts)."
        )


class PlaybookCreate(BaseModel):
    """Eingabe fuer `POST /v1/playbooks` — legt Version 1 an.

    Welle 4: nur `name` ist Pflicht. `content` ist optional; fehlt es, wird
    eine leere `PlaybookContent` eingesetzt.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    content: PlaybookContent = Field(default_factory=PlaybookContent)
    # Content-i18n (ADR-0027): Sprachvarianten beim Anlegen. Default `['de']`
    # = Backward-Compat; jede Sprache startet als eigene Draft-v1 (Copy).
    locales: list[ContentLocale] = Field(default_factory=lambda: [DEFAULT_LOCALE])

    @field_validator("locales")
    @classmethod
    def _dedup_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Mindestens eine Sprache ist erforderlich.")
        seen: set[str] = set()
        ordered: list[str] = []
        for loc in value:
            norm = normalize_locale(loc)
            if norm not in seen:
                seen.add(norm)
                ordered.append(norm)
        return ordered


class PlaybookUpdate(BaseModel):
    """Eingabe fuer `PUT /v1/playbooks/{id}` — erzeugt eine neue Version."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: PlaybookContent


class PlaybookRead(BaseModel):
    """Playbook im aktuellen Stand inkl. denormalisierter Filterfelder."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    current_version: int
    # Vom System verwaltet (Builder-Lock): User-Edits werden serverseitig
    # mit 403 geblockt; nur Duplizieren ist erlaubt.
    is_managed: bool = False

    current_status: VersionStatus = VersionStatus.inactive
    has_pending_draft: bool = False
    locale: ContentLocale = DEFAULT_LOCALE
    type: str
    tags: list[str]
    triggers: str | None
    content: PlaybookContent
    created_at: datetime
    updated_at: datetime
    # Abgeleitet: EXISTS(child in playbook_composition). Default False fuer
    # Backward-Compat mit Konsumenten, die das Feld nicht liefern.
    is_composite: bool = False


class PlaybookVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot eines Playbooks."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    status: VersionStatus = VersionStatus.inactive
    locale: ContentLocale = DEFAULT_LOCALE
    content: PlaybookContent
    created_by: UUID
    created_at: datetime


class PlaybookUsage(BaseModel):
    """Backlink-Record: welche Persona referenziert ein Playbook?

    Quelle: `persona_playbook`-Tabelle. Wird in Track 3-A vom Reverse-Lookup-
    Endpoint `GET /v1/workspaces/{ws}/playbooks/{id}/usages` serviert.
    """

    model_config = ConfigDict(from_attributes=True)

    persona_id: UUID
    persona_name: str


class PlaybookRef(BaseModel):
    """Schlankes Playbook-Pointer-Tupel (id + name) fuer Aggregate."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class TriggerOverview(BaseModel):
    """Welle 5: ein deduplizierter Trigger mit den Playbooks, die ihn fuehren.

    Quelle: denormalisierte `playbook.triggers`-Spalte, kommagetrennt. Wird vom
    Discovery-Endpoint `GET /v1/workspaces/{ws}/playbooks/triggers` und vom
    MCP-Tool `list_triggers` zurueckgegeben — der LLM nutzt die Tabelle, um
    fuer eine User-Anfrage das passende Playbook zu finden, ohne dass alle
    Playbook-Bodies in den Systemprompt geladen werden muessen.
    """

    model_config = ConfigDict(from_attributes=True)

    trigger: str
    playbooks: list[PlaybookRef]
