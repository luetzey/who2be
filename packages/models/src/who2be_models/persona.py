"""Pydantic-Modelle fuer das Persona-Aggregat."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from who2be_models.locale import DEFAULT_LOCALE, ContentLocale, normalize_locale
from who2be_models.resource import ResourceBlock
from who2be_models.status import VersionStatus

# Eingabe-Limits — DoS-Schutz gegen riesige Payloads, da Versions-Inhalte
# unveraenderlich in `persona_version` eingefroren und in jeder
# `list_personas`-Antwort retourniert werden.
TraitStr = Annotated[str, StringConstraints(min_length=1, max_length=200)]
TagStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]
SkillNameStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]


def _coerce_str_to_blocks(value: object) -> object:
    """Read-Koerzion fuer PR-A: alter `str`-Inhalt → BlockNote-Block-Liste.

    Vor PR-A waren `identity_add`/`output_style_override` Plain-`str`. Damit
    bestehende `persona_version`-jsonb-Snapshots ohne DB-Backfill weiter valide
    deserialisieren, wird ein vorhandener String verlustfrei in einen einzelnen
    Paragraph-Block gewrappt. Leerer/Whitespace-String → leere Liste.
    """
    if isinstance(value, str):
        if value.strip() == "":
            return []
        return [
            {
                "id": "legacy-text",
                "type": "paragraph",
                "content": [{"type": "text", "text": value, "styles": {}}],
            }
        ]
    return value


class SkillRef(BaseModel):
    """Referenz auf einen relevanten Skill der Persona (Gap 3.5).

    Rein deskriptiv: `name` benennt den Skill, `note` haelt den Relevanz-Hinweis
    (z. B. „nuetzlich im Story-Crafter-Modus"). Keine Ausfuehrungs-Bindung —
    der gerenderte Profil-Text teilt dem Agenten die relevanten Skills mit.
    """

    model_config = ConfigDict(extra="forbid")

    name: SkillNameStr
    note: str = Field(default="", max_length=1_000)


class PersonaMode(BaseModel):
    """Ein einzelner Modus einer Multi-Modus-Persona (Gap 3.4).

    Ein Modus beschreibt, wie sich die Persona in einem bestimmten Kontext
    verhaelt. Er wird durch `trigger` erkannt (kommagetrennte Keywords); ohne
    Trigger-Match greift der Default-Modus (`is_default=True`).

    `identity_add` ergaenzt die Basis-Identitaet der Persona; `output_style_override`
    beschreibt, wie sich der Output-Stil in diesem Modus aendert; `anti_patterns`
    listet Dinge, die der Modus vermeidet. Alle drei sind BlockNote-Dokumente
    (PR-A — vorher `str`; Alt-Daten werden per `_coerce_str_to_blocks` gelesen).

    `playbook_id` bindet einen Modus an ein zugehoeriges Playbook (Brainstormer:
    „Zugehoeriges Playbook"); `playbook_name` ist ein denormalisierter Snapshot
    fuer das Rendering (der reine Profil-Resolver hat keinen DB-Zugriff). Der
    `playbook_id` bleibt die Wahrheit — der Name kann bei Umbenennung veralten.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    trigger: str | None = Field(default=None, max_length=2_000)
    is_default: bool = False
    identity_add: list[ResourceBlock] = Field(default_factory=list, max_length=500)
    output_style_override: list[ResourceBlock] = Field(default_factory=list, max_length=500)
    anti_patterns: list[ResourceBlock] = Field(default_factory=list, max_length=500)
    playbook_id: UUID | None = None
    playbook_name: str = Field(default="", max_length=200)

    @field_validator("identity_add", "output_style_override", "anti_patterns", mode="before")
    @classmethod
    def _coerce_legacy_str(cls, value: object) -> object:
        return _coerce_str_to_blocks(value)


class PersonaContent(BaseModel):
    """BlockNote-strukturierter Persona-Profil-Inhalt (Phase 3-0).

    Wird als optionales Feld an `PersonaVersionContent.content` haengen und
    traegt Rolle, Tonfall, Beispiele als BlockNote-Dokument (ADR-0022). Gleiche
    Obergrenze (`max_length=2000`) wie bei `ResourceContent.blocks` — gross
    genug fuer eine Persona-Karte, klein genug zum Embedden in Listen.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    blocks: list[ResourceBlock] = Field(default_factory=list, max_length=2_000)


class PersonaVersionContent(BaseModel):
    """Typisierter Inhalt einer Persona-Version (`persona_version.content`).

    Vor Phase 3-0 hiess diese Klasse `PersonaContent`. Der Name ist mit Phase
    3-0 an die neue BlockNote-Profil-Klasse uebergegangen; die per-Version
    persistierten Felder leben hier.

    `traits` ist mit Phase 3-0 als Persona-Strukturfeld deprecated — neue UIs
    liefern den strukturierten Profil-Inhalt ueber `content` (BlockNote). Das
    Feld bleibt mit Default `[]` als Wire-Schema-Backward-Compat (alte Clients
    schicken/erwarten es weiter).
    """

    model_config = ConfigDict(extra="forbid")

    # Welle 4: description hat Default "" — Create erlaubt leere Description.
    description: str = Field(default="", max_length=2_000)
    # `system_prompt` ist seit Phase 3 Runde 3 (Track 3 — Agents+Templates)
    # deprecated: der System-Prompt des Agenten lebt im verknuepften Template.
    # Default ist daher der leere String — neue UIs senden das Feld nicht mehr,
    # alte Clients (z. B. Bestand-Editoren) bleiben kompatibel.
    system_prompt: str = Field(default="", max_length=20_000)
    traits: list[TraitStr] = Field(default_factory=list, max_length=50)
    tags: list[TagStr] = Field(default_factory=list, max_length=50)
    content: PersonaContent | None = None
    # Gap 3.4: Multi-Modus-Personas. Default [] = Backward-Compat (alte Clients
    # senden das Feld nicht; additive jsonb-Evolution nach ADR-0009).
    modes: list[PersonaMode] = Field(default_factory=list, max_length=20)
    # Gap 3.5: relevante Skills der Persona (deskriptiv). Default [] = Backward-
    # Compat (additive jsonb-Evolution nach ADR-0009).
    skills: list[SkillRef] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _validate_modes(self) -> "PersonaVersionContent":
        """Validiert Invarianten ueber alle Modi:

        1. Hoechstens ein Modus darf `is_default=True` sein.
        2. Modus-Namen sind case-insensitive eindeutig.
        """
        default_count = sum(1 for m in self.modes if m.is_default)
        if default_count > 1:
            raise ValueError(
                f"Hoechstens ein Modus darf is_default=True sein, gefunden: {default_count}"
            )

        names_lower = [m.name.lower() for m in self.modes]
        if len(names_lower) != len(set(names_lower)):
            seen: set[str] = set()
            for n in names_lower:
                if n in seen:
                    raise ValueError(
                        f"Modus-Namen muessen case-insensitiv eindeutig sein, Duplikat: '{n}'"
                    )
                seen.add(n)

        return self


class PersonaCreate(BaseModel):
    """Eingabe fuer `POST /v1/personas` — legt Version 1 an.

    Welle 4: nur `name` ist Pflicht. `content` ist optional; fehlt es, wird
    eine leere `PersonaVersionContent` eingesetzt. Promote-Validation (draft →
    review/active) prueft im Transition-Endpunkt auf vollstaendige Pflichtfelder
    (description, body in `content.content.blocks`).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    content: PersonaVersionContent = Field(default_factory=PersonaVersionContent)
    # Content-i18n (ADR-0027): Sprachvarianten, die beim Anlegen erzeugt werden.
    # Default `['de']` haelt Bestands-Clients backward-compatible. Jede gewaehlte
    # Sprache startet als eigene Draft-v1 (Copy von `content`).
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


class PersonaUpdate(BaseModel):
    """Eingabe fuer `PUT /v1/personas/{id}` — erzeugt eine neue Version."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: PersonaVersionContent


class PersonaRead(BaseModel):
    """Persona im aktuellen Stand (inkl. Inhalt der aktuellen Version)."""

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
    # Sprachvariante, die diese Antwort traegt (ADR-0027). Default `'de'` deckt
    # Bestand + Lese-Pfade ohne locale-Angabe.
    locale: ContentLocale = DEFAULT_LOCALE
    content: PersonaVersionContent
    # List-Enrichment (Card-Pills): NUR der List-Endpoint befuellt diese
    # Batch-Aggregat-Zaehler (kein N+1). `playbook_count` = Anzahl der ueber
    # `persona_playbook` verknuepften Playbooks; `agent_count` = Anzahl der
    # Agenten mit `agent.persona_id = id`. Direkt konstruierte Reads
    # (get/create/update) lassen sie auf 0.
    playbook_count: int = 0
    agent_count: int = 0
    created_at: datetime
    updated_at: datetime


class PersonaVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot einer Persona."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    status: VersionStatus = VersionStatus.inactive
    locale: ContentLocale = DEFAULT_LOCALE
    content: PersonaVersionContent
    created_by: UUID
    created_at: datetime


class PersonaUsage(BaseModel):
    """Backlink-Record: welcher Agent nutzt diese Persona?

    Quelle: `agent.persona_id`. Blockiert das Hard-Delete einer Persona (409),
    weil der Composite-FK `agent.persona_id` auf `ON DELETE RESTRICT` steht —
    der Agent muss erst umgehaengt/geloescht werden.
    """

    model_config = ConfigDict(from_attributes=True)

    agent_id: UUID
    agent_name: str
