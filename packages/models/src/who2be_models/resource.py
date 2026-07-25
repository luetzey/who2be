"""Pydantic-Modelle fuer das Resource-Aggregat (Phase 2.2).

Resources sind eine zweite, versionierte Wissensebene mit Block-Editor-Inhalt
(BlockNote-Dokument, ADR-0022). `resource_version.content` haelt das
Block-Array; jeder Block traegt eine stabile `id`, auf die Playbooks per
`playbook_resource_link` zeigen koennen (Block-Refs, ADR-0021).

Versionierung + Status spiegeln Persona/Playbook (ADR-0004 / ADR-0020):
ein `…Create`/`…Update`/`…Read`/`…VersionRead`-Satz, `…Content` typisiert das
`jsonb`-Feld.
"""

import json
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

from who2be_models.locale import DEFAULT_LOCALE, ContentLocale, validate_supported_locale
from who2be_models.slug import SlugStr
from who2be_models.status import VersionStatus

# Stabile BlockNote-Block-ID bzw. Block-Typ — die ID ist der Anker fuer
# Playbook-Block-Refs.
BlockId = Annotated[str, StringConstraints(min_length=1, max_length=100)]
BlockType = Annotated[str, StringConstraints(min_length=1, max_length=50)]

# Eingabe-Limit fuer Tags — analog zu PlaybookContent.TagStr (DoS-Schutz fuer
# in jsonb persistierte Strings, ADR-0009).
TagStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]

# Embed-Modus einer Einbettung (playbook->resource, resource->resource).
# 'lazy' (DEFAULT): reine Referenz — der MCP-Server sendet das Ziel NICHT inline
# mit; der Agent laedt es bei Bedarf via `fetch_resource` nach. 'inline': das
# Ziel-Dokument wird fest vom MCP mitgeliefert. Default 'lazy' reduziert den
# gesendeten Kontext (bewusst breaking fuer bestehende 'resource'-scope-Links).
EmbeddingMode = Literal["lazy", "inline"]

# DoS-Obergrenze fuer den serialisierten Block-Inhalt. Bloecke sind
# `extra="allow"` (BlockNote-Schema ist offen), darum greift hier ein
# Gesamt-Byte-Limit statt feldweiser `max_length` (F-01-Linie).
_MAX_CONTENT_BYTES = 1_000_000


class ResourceBlock(BaseModel):
    """Ein Top-Level-Block eines BlockNote-Dokuments.

    `extra="allow"`, weil das BlockNote-Schema (`props`, `content`, `children`,
    …) offen und versionsabhaengig ist. Verbindlich sind nur `id` (Anker fuer
    Block-Refs) und `type`.
    """

    model_config = ConfigDict(extra="allow")

    id: BlockId
    type: BlockType


class ResourceBlockAnchor(BaseModel):
    """Ein linkbarer Heading-Anker einer Resource (Read-only, WP-6).

    Quelle: die Heading-Bloecke der gelieferten Resource-Version (Active fuer
    MCP-/Token-Reads, Current fuer Mensch/JWT). `block_id` ist die stabile
    BlockNote-ID, auf die ein Playbook-Block-Ref bzw. Sub-Resource-Block-Link
    zeigen kann (ADR-0021, Heading-Only-Anker); `level` ist `props.level`
    (Default 1 = BlockNote-h1); `text` der Heading-Klartext.
    """

    model_config = ConfigDict(from_attributes=True)

    block_id: BlockId
    level: int
    text: str


class ResourceContent(BaseModel):
    """Typisierter Inhalt einer Resource-Version (`resource_version.content`).

    E3 (Track E3, ADR-0009 additive jsonb-Evolution): `tags` ermoeglicht das
    Filtern ueber `GET /resources?tag=` ohne denormalisierte DB-Spalte.
    Default `[]` — Backward-Compat: alte Versionen ohne Tags bleiben gueltig.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    blocks: list[ResourceBlock] = Field(default_factory=list, max_length=2_000)
    tags: list[TagStr] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _check_total_size(self) -> Self:
        size = len(json.dumps(self.model_dump(mode="json")))
        if size > _MAX_CONTENT_BYTES:
            raise ValueError(f"Resource-Inhalt zu gross ({size} > {_MAX_CONTENT_BYTES} Bytes).")
        return self


class ResourceCreate(BaseModel):
    """Eingabe fuer `POST /v1/workspaces/{ws}/resources` — legt Version 1 an.

    Welle 4: nur `name` ist Pflicht. `content` ist optional; fehlt es, wird
    eine leere `ResourceContent` eingesetzt (description="" + blocks=[]).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    # `slug` wird beim Create automatisch aus `name` abgeleitet, falls nicht
    # gesetzt (spiegelt SystemPromptTemplateCreate). Workspace-eindeutig; ein
    # explizit gesetzter Slug erlaubt stabile Kennungen fuer Seeds/Imports.
    slug: SlugStr | None = None
    content: ResourceContent = Field(default_factory=ResourceContent)
    # „Ein Element, eine Sprache" (Plan 2026-07-24, ersetzt das ADR-0027-
    # Multi-Locale-`locales`-Feld): `None` bedeutet „Service setzt spaeter den
    # Workspace-Default" (`workspace.content_locale`); ist der Wert gesetzt,
    # muss er zu `SUPPORTED_LOCALES` gehoeren.
    locale: ContentLocale | None = None

    @field_validator("locale")
    @classmethod
    def _validate_locale(cls, value: str | None) -> str | None:
        return None if value is None else validate_supported_locale(value)


class ResourceUpdate(BaseModel):
    """Eingabe fuer `PUT /v1/workspaces/{ws}/resources/{id}` — neue Version."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: ResourceContent
    # Sprachwechsel (Plan „Ein Element, eine Sprache"): `None` = Sprache
    # bleibt unveraendert; gesetzt = neue Sprache fuer die Identitaets-Zeile.
    locale: ContentLocale | None = None

    @field_validator("locale")
    @classmethod
    def _validate_locale(cls, value: str | None) -> str | None:
        return None if value is None else validate_supported_locale(value)


class ResourceRead(BaseModel):
    """Resource im aktuellen Stand (inkl. Inhalt der aktuellen Version)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    owner_id: UUID
    name: str
    # Workspace-eindeutiger Slug (Migration 0064). Spiegelt
    # `SystemPromptTemplateRead.slug`; beim Create aus `name` abgeleitet.
    slug: str
    current_version: int
    # Vom System verwaltet (Builder-Lock): User-Edits werden serverseitig
    # mit 403 geblockt; nur Duplizieren ist erlaubt.
    is_managed: bool = False

    current_status: VersionStatus = VersionStatus.inactive
    has_pending_draft: bool = False
    locale: ContentLocale = DEFAULT_LOCALE
    content: ResourceContent
    # Track E: direkte Sub-Resource-Verweise (Resource->Resource). Default `[]`
    # — REST-Reads befuellen das Feld nicht (dafuer gibt es den dedizierten
    # `GET .../sub_resources`-Endpoint); der MCP-`fetch_resource`-Pfad haengt
    # die direkten Kinder hier an, damit der Agent Body + Sub-Ref-Tabelle in
    # einem Modell sieht (Kinder werden NICHT expandiert, §3.3).
    sub_resources: list["SubResourceRead"] = Field(default_factory=list)
    # Track Embed-Modus: Volldokumente der direkten Sub-Resources, die auf
    # `embedding_mode='inline'` (link_scope='resource') stehen. Der
    # `fetch_resource`-Pfad fuellt das Feld (eine Ebene, keine Rekursion);
    # 'lazy'-Kinder bleiben reine Pointer in `sub_resources`. Spiegelt
    # `PlaybookWithResources.linked_resources`.
    inline_sub_resources: list["ResourceRead"] = Field(default_factory=list)
    # List-Enrichment (Card-Pills): NUR der List-Endpoint befuellt diese
    # Batch-Aggregat-Zaehler (kein N+1). `playbook_link_count` = Anzahl der
    # DISTINCT Playbooks, die (ueber `playbook_resource_link`) auf diese Resource
    # zeigen; `sub_resource_count` = Anzahl der ueber `resource_composition`
    # eingebetteten/verlinkten Sub-Resources (parent_id = id). Direkt
    # konstruierte Reads (get/create/update, MCP-fetch) lassen sie auf 0.
    playbook_link_count: int = 0
    sub_resource_count: int = 0
    created_at: datetime
    updated_at: datetime


class ResourceVersionRead(BaseModel):
    """Ein unveraenderlicher Versions-Snapshot einer Resource."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    status: VersionStatus = VersionStatus.inactive
    locale: ContentLocale = DEFAULT_LOCALE
    content: ResourceContent
    created_by: UUID
    created_at: datetime


class ResourceLinkItem(BaseModel):
    """Ein einzelner Playbook→Resource-Verweis (Eingabe).

    Phase-3-Fixes Track 4: `link_scope` unterscheidet zwischen Volldokument-
    Referenz (`'resource'`, kein `block_id`) und Block-Anker (`'block'`, mit
    `block_id`). Default `'block'` ist Backward-Compat fuer alte Clients;
    Default `block_id=None` erzwingt im Validator die explizite Block-ID
    fuer 'block'-Items.
    """

    model_config = ConfigDict(extra="forbid")

    resource_id: UUID
    block_id: BlockId | None = None
    position: int = Field(ge=0)
    link_scope: Literal["resource", "block"] = "block"
    # Embed-Modus (Default 'lazy'): nur 'inline' wird vom MCP mitgesendet.
    embedding_mode: EmbeddingMode = "lazy"

    @model_validator(mode="after")
    def _check_scope_block_pairing(self) -> Self:
        if self.link_scope == "resource" and self.block_id is not None:
            raise ValueError("link_scope='resource' darf kein block_id setzen.")
        if self.link_scope == "block" and self.block_id is None:
            raise ValueError("link_scope='block' verlangt eine block_id.")
        return self


class ResourceLinkSet(BaseModel):
    """Eingabe fuer `PUT .../playbooks/{id}/resource_links`.

    Set-Replace-Semantik: die Liste ersetzt den bisherigen Stand vollstaendig
    (leere Liste loest alle Links). Obergrenze schuetzt vor Riesen-Arrays.
    """

    model_config = ConfigDict(extra="forbid")

    links: list[ResourceLinkItem] = Field(default_factory=list, max_length=200)


class ResourceLinkRead(BaseModel):
    """Ein aufgeloester Block-Ref inkl. Verfuegbarkeit + Vorschau (Ausgabe).

    Phase 3-A erweitert das Read-Modell um Section-Sicht und Available-
    Fallback:
    - `available_in='active'` — Anker in der aktiven Version aufgeloest.
    - `available_in='draft'` — keine aktive Version, aber die aktuelle
      (Draft-/Review-/Inactive-)Version traegt den Anker → UI rendert
      "Nur in Draft".
    - `available_in=None` — Anker existiert nirgends mehr (Block geloescht).
    `available` bleibt aus Wire-Backward-Compat (= `available_in is not None`).
    `section_block_ids` und `section_preview` traegt die Section ab dem
    Anker-Heading bis (exklusive) zum naechsten Heading desselben Levels.
    """

    model_config = ConfigDict(from_attributes=True)

    resource_id: UUID
    resource_name: str
    block_id: str | None = None
    position: int
    available: bool
    available_in: Literal["active", "draft"] | None = None
    preview: str | None = None
    section_block_ids: list[str] = Field(default_factory=list)
    section_preview: str | None = None
    link_scope: Literal["resource", "block"] = "block"
    # Embed-Modus (Default 'lazy'): steuert, ob `fetch_playbook` das Volldokument
    # inline mitsendet. Nur fuer 'resource'-scope-Links wirksam.
    embedding_mode: EmbeddingMode = "lazy"


class LinkedBlockSection(ResourceLinkRead):
    """Block-Ref erweitert um alle Bloecke der Section ab dem Anker-Heading
    (Phase 3-0 Helper-Shape, fuer Section-Aware-Picker/Preview in Track 3-A/B).

    Die Section reicht vom Heading-Block mit `block_id` bis (ausschliesslich)
    zum naechsten Heading desselben Levels. `section_blocks` enthaelt alle
    dieser Bloecke in Dokument-Reihenfolge — inklusive des Anker-Headings.
    Leere Liste = Resource enthielt den Anker nicht (mehr).
    """

    section_blocks: list[ResourceBlock] = Field(default_factory=list)


class ResourceUsage(BaseModel):
    """Backlink-Record: welche Playbooks referenzieren Bloecke einer Resource?

    Quelle: `playbook_resource_link` GROUP BY playbook_id. `block_count` ist
    die Anzahl der Block-Refs aus genau diesem Playbook auf die Ziel-Resource.
    Wird in Track 3-A vom Endpoint
    `GET /v1/workspaces/{ws}/resources/{id}/usages` serviert.
    """

    model_config = ConfigDict(from_attributes=True)

    playbook_id: UUID
    playbook_name: str
    block_count: int = Field(ge=0)


class ResourceRef(BaseModel):
    """Schlanker Resource-Pointer (id + name) fuer Backlinks/Aggregate.

    Pendant zu `PlaybookRef` — getragen z. B. von `GET .../{id}/used_by`
    (welche Resources referenzieren diese Resource als Sub-Resource?).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class SubResourceLinkItem(BaseModel):
    """Eingabe-Item fuer einen Sub-Resource-Link (Resource->Resource, Track E).

    Spiegelt `ResourceLinkItem`: `link_scope='resource'` referenziert das ganze
    Kind-Dokument (kein `block_id`), `link_scope='block'` einen Heading-Anker
    im Kind (mit `block_id`). Default ist `'resource'` — bei Sub-Resources ist
    die Volldokument-Referenz der Normalfall.
    """

    model_config = ConfigDict(extra="forbid")

    child_id: UUID
    block_id: BlockId | None = None
    position: int = Field(default=0, ge=0)
    link_scope: Literal["resource", "block"] = "resource"
    # Embed-Modus (Default 'lazy'): nur 'inline' wird vom MCP mitgesendet.
    embedding_mode: EmbeddingMode = "lazy"

    @model_validator(mode="after")
    def _check_scope_block_pairing(self) -> Self:
        if self.link_scope == "resource" and self.block_id is not None:
            raise ValueError("link_scope='resource' darf kein block_id setzen.")
        if self.link_scope == "block" and self.block_id is None:
            raise ValueError("link_scope='block' verlangt eine block_id.")
        return self


class SubResourceLinkSet(BaseModel):
    """Eingabe fuer `PUT .../resources/{id}/sub_resources`.

    Set-Replace-Semantik wie `ResourceLinkSet`/`PlaybookCompositionLinkSet`:
    die Liste ersetzt den bisherigen Stand vollstaendig (leere Liste loest
    alle Sub-Resource-Links). Obergrenze schuetzt vor Riesen-Arrays.
    """

    model_config = ConfigDict(extra="forbid")

    links: list[SubResourceLinkItem] = Field(default_factory=list, max_length=200)


class SubResourceRead(BaseModel):
    """Ein direkter Sub-Resource-Verweis (Ausgabe).

    `fetch_call` ist die fertige MCP-Anweisung, das Kind separat zu laden —
    der `fetch_resource`-Vertrag (§3.3) expandiert Kinder NICHT, sondern
    reicht diese Tabelle durch. Das Feld ist `computed`, damit es immer aus
    der `id` abgeleitet wird (kein Duplikat-State, keine Drift).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    link_scope: Literal["resource", "block"] = "resource"
    block_id: str | None = None
    position: int = 0
    # Embed-Modus (Default 'lazy'): bei 'inline' haengt `fetch_resource` das
    # Volldokument zusaetzlich an `ResourceRead.inline_sub_resources`.
    embedding_mode: EmbeddingMode = "lazy"
    # List-Card-Summary (nur der Resource-List-Endpoint befuellt diese Felder,
    # kein N+1): `status`/`version` sind Status + Nummer der aktuellen Version
    # des Kindes, damit die aufklappbare Karte den Kind-Stand ohne Extra-Fetch
    # zeigt. Der MCP-`fetch_resource`-Pfad (Link-Tabelle) laesst sie auf None.
    status: VersionStatus | None = None
    version: int | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fetch_call(self) -> str:
        return f"fetch_resource('{self.id}')"


# `ResourceRead.sub_resources` referenziert `SubResourceRead` als Forward-Ref —
# jetzt aufloesen, da der Typ oben definiert ist.
ResourceRead.model_rebuild()
