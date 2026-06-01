"""Pydantic-Modelle fuer das Playbook-Aggregat.

`type`, `tags` und `triggers` sind Teil des Versions-Inhalts und werden vom
Service auf die `playbook`-Zeile denormalisiert, damit `list_playbooks` ohne
Join filtern kann (siehe architecture.md §3).
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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


class PlaybookContent(BaseModel):
    """Typisierter Inhalt einer Playbook-Version (`playbook_version.content`).

    Welle 4: description, body und type haben Default "" — Create erlaubt
    unvollstaendige Drafts. Promote-Validation (draft → review/active) prueft
    im Transition-Endpunkt auf vollstaendige Pflichtfelder.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    body: str = Field(default="", max_length=50_000)
    # Welle 4: min_length entfernt; Default "" erlaubt Draft-Create ohne Typ.
    # Der denormalisierte DB-Wert wird im Repo auf "prompt" gemappt wenn leer.
    type: str = Field(default="", max_length=100)
    tags: list[TagStr] = Field(default_factory=list, max_length=50)
    triggers: str | None = Field(default=None, max_length=2_000)
    # PR-B: Format des `body`-Felds. "plain" = \n\n-getrennter Plaintext (Alt-
    # bestand, Default fuer fehlende Keys → Backward-Compat). "blocknote" =
    # stringifiziertes BlockNote-JSON mit Inline-Placeholder-Pills (resource/
    # playbook). Liegt bewusst im versionierten Content-jsonb (nicht als Spalte),
    # damit alte Versions-Snapshots automatisch "plain" bleiben (additive
    # jsonb-Evolution nach ADR-0009; wird nicht gequert/gefiltert).
    body_format: Literal["plain", "blocknote"] = "plain"


class PlaybookCreate(BaseModel):
    """Eingabe fuer `POST /v1/playbooks` — legt Version 1 an.

    Welle 4: nur `name` ist Pflicht. `content` ist optional; fehlt es, wird
    eine leere `PlaybookContent` eingesetzt.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    content: PlaybookContent = Field(default_factory=PlaybookContent)


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
    current_status: VersionStatus = VersionStatus.inactive
    has_pending_draft: bool = False
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
