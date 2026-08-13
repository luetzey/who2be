"""WorkArea-Models (ADR-0047) — unversioniertes Rohmaterial fuer Agenten.

Die WorkArea ist der Arbeitsort eines Agenten: doc-/table-/blob-Artifacts in
Areas (`private` = genau eine Area pro Agent, auto-angelegt; `shared` = explizit
angelegte Team-Areas mit Grants). Anders als das Resource-Aggregat gibt es KEINE
Versionierung und KEINEN Status-Workflow — Schreibkonflikte loest eine
optimistische Revision (`rev`, 409 `rev_conflict` bei veralteter `expected_rev`).

Doc-Inhalte sind eine Block-Liste mit Markdown pro Block (Architektur-
Entscheidung 3.3): die API nimmt Markdown an, der Server splittet deterministisch
und vergibt stabile 8-stellige `block_id`s. Die Anker-Sprache folgt ADR-0021
(``<artifact_id>#<block_id>``) — Suchtreffer sind direkt `read(id, anchor)`-faehig.

Autorisierung (Area-Grants) ist bewusst NICHT Teil dieser Modelle: sie ist
dynamisch (`work_area_grant`) und wird serverseitig durchgesetzt
(`core/workarea_scope.py`, 403 `area_forbidden`).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Obergrenze fuer Markdown-Inhalte eines Artifacts (DoS-Schutz, F-01-Linie) —
# gilt fuer create/append/patch gleichermassen.
ARTIFACT_CONTENT_MAX_LENGTH = 500_000
# Obergrenze fuer den Markdown-Inhalt EINES Blocks (Server-Split haelt sie ein).
DOC_BLOCK_MD_MAX_LENGTH = 20_000


class WorkAreaScope(StrEnum):
    """Sichtbarkeitsart einer Area (ADR-0047).

    - ``private``: genau eine Area pro Agent, auto-angelegt beim ersten
      Zugriff; „privat" heisst privat gegenueber anderen **Agenten** —
      Menschen ab Rolle `editor` lesen alles.
    - ``shared``: explizit angelegte Team-Area; Agenten-Zugriff ueber Grants.
    """

    private = "private"
    shared = "shared"


class ArtifactType(StrEnum):
    """Art eines WorkArea-Artifacts (ADR-0047)."""

    doc = "doc"
    table = "table"
    blob = "blob"


class OccurredPrecision(StrEnum):
    """Praezision des fachlichen Zeitpunkts `occurred_at`.

    `occurred_at` ist Pflicht-Input ohne Server-Fallback auf now() —
    der bewusste Ausweg bei unbekanntem Zeitpunkt ist ``unknown``
    (Timeline sortiert solche Eintraege in den separaten unknown-Bucket).
    """

    day = "day"
    minute = "minute"
    unknown = "unknown"


class Sensitivity(StrEnum):
    """Sensibilitaets-Stufe eines Inhalts (Zugriffslog snapshottet sie)."""

    general = "general"
    sensitive = "sensitive"


class WorkAreaGrantLevel(StrEnum):
    """Zugriffsstufe eines Agenten auf eine Area (`work_area_grant.level`)."""

    read = "read"
    write = "write"


class DocBlockKind(StrEnum):
    """Blocktyp eines doc-Artifacts (deterministischer Markdown-Split)."""

    heading = "heading"
    paragraph = "paragraph"
    code = "code"
    list = "list"


class DocBlock(BaseModel):
    """Ein Block eines doc-Artifacts (ADR-0047, Entscheidung 3.3).

    `block_id` ist die stabile, serverseitig vergebene 8-stellige Kennung —
    der Anker-Teil von ``<artifact_id>#<block_id>`` (ADR-0021). `level` ist
    nur fuer ``heading``-Bloecke zulaessig (1..6).
    """

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    block_id: str = Field(min_length=8, max_length=8)
    kind: DocBlockKind
    level: int | None = Field(default=None, ge=1, le=6)
    md: str = Field(max_length=DOC_BLOCK_MD_MAX_LENGTH)

    @model_validator(mode="after")
    def _check_level_only_for_heading(self) -> Self:
        if self.level is not None and self.kind != DocBlockKind.heading:
            raise ValueError("`level` ist nur fuer heading-Bloecke zulaessig.")
        return self


class WorkAreaCreate(BaseModel):
    """Eingabe fuer `POST .../work-areas` — legt eine SHARED Area an.

    Nur shared Areas werden explizit angelegt (editor+); die private Area
    eines Agenten entsteht automatisch beim ersten Zugriff. `retention_days`
    None = unbegrenzt (Default, ADR-0047).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    retention_days: int | None = Field(default=None, gt=0)


class WorkAreaRead(BaseModel):
    """Eine Area im aktuellen Stand (`work_area`)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    scope: WorkAreaScope
    # Nur fuer private Areas gesetzt (CHECK-Constraint in 0073).
    owner_agent_id: UUID | None = None
    name: str
    retention_days: int | None = None
    created_at: datetime
    updated_at: datetime


class WorkAreaGrantSet(BaseModel):
    """Eingabe fuer `PUT .../work-areas/{id}/grants/{agent_id}` (nur Mensch)."""

    model_config = ConfigDict(extra="forbid")

    level: WorkAreaGrantLevel


class WorkAreaGrantRead(BaseModel):
    """Ein Area-Grant eines Agenten (`work_area_grant`)."""

    model_config = ConfigDict(from_attributes=True)

    area_id: UUID
    agent_id: UUID
    level: WorkAreaGrantLevel
    created_at: datetime


class WorkAreaAssignment(BaseModel):
    """Area-Zuordnung eines Agenten fuer `whoami.work_areas` (ADR-0047)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    scope: WorkAreaScope
    level: WorkAreaGrantLevel


class ArtifactCreate(BaseModel):
    """Eingabe fuer `POST .../work-areas/{area_id}/artifacts` (doc-Artifact).

    `occurred_at` ist Pflicht (kein now()-Fallback; Ausweg:
    `occurred_precision='unknown'`). Schatten-System-Schutz (Spec §3):
    ist `source_system` gesetzt, MUSS `fetched_at` gesetzt sein — aus einem
    Fremdsystem uebernommene Daten tragen immer ihren Abrufzeitpunkt.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    content_md: str = Field(default="", max_length=ARTIFACT_CONTENT_MAX_LENGTH)
    occurred_at: datetime
    occurred_precision: OccurredPrecision = OccurredPrecision.minute
    sensitivity: Sensitivity = Sensitivity.general
    source_system: str | None = Field(default=None, max_length=100)
    source_url: str | None = Field(default=None, max_length=2000)
    fetched_at: datetime | None = None

    @model_validator(mode="after")
    def _check_source_system_requires_fetched_at(self) -> Self:
        if self.source_system is not None and self.fetched_at is None:
            raise ValueError("`source_system` verlangt ein `fetched_at` (Schatten-System-Schutz).")
        return self


class ArtifactRead(BaseModel):
    """Ein WorkArea-Artifact im aktuellen Stand (`wa_artifact`).

    `blocks` ist nur fuer doc-Artifacts gefuellt; blob-Artifacts tragen
    `blob_sha256`, table-Artifacts referenzieren ueber `content_ref` die
    `wa_table`-Zeile. `updated_by` ist die Akteur-Kennung
    (``agent:<id>`` | ``user:<id>``), analog `wa_category_rule.created_by`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    area_id: UUID
    workspace_id: UUID
    type: ArtifactType
    title: str
    rev: int
    occurred_at: datetime
    occurred_precision: OccurredPrecision
    sensitivity: Sensitivity
    source_system: str | None = None
    source_url: str | None = None
    fetched_at: datetime | None = None
    blob_sha256: str | None = None
    content_ref: str | None = None
    created_at: datetime
    updated_at: datetime
    updated_by: str | None = None
    blocks: list[DocBlock] | None = None


class ArtifactAppend(BaseModel):
    """Eingabe fuer `POST .../wa-artifacts/{id}/append` — lockfreies Anhaengen.

    Atomar `content || $blocks, rev+1` (Entscheidung 3.3): kein
    `expected_rev` noetig, Appends kollidieren nie.
    """

    model_config = ConfigDict(extra="forbid")

    content_md: str = Field(min_length=1, max_length=ARTIFACT_CONTENT_MAX_LENGTH)


# Patch-Operation an einem Block-Anker. Bewusst ein Literal statt StrEnum
# (Muster `EmbeddingMode`): der Member-Name `replace` wuerde sonst die
# gleichnamige `str`-Methode der StrEnum-Basis verschatten.
ArtifactPatchOp = Literal["replace", "insert_after", "delete"]


class ArtifactPatch(BaseModel):
    """Eingabe fuer `PATCH .../wa-artifacts/{id}` — optimistisches Block-Edit.

    `expected_rev` traegt die zuletzt gelesene Revision; stimmt sie nicht
    mehr, antwortet der Server 409 `rev_conflict` (aktuelle rev im detail).
    """

    model_config = ConfigDict(extra="forbid")

    # Block-Anker (`block_id`) innerhalb des Artifacts.
    anchor: str = Field(min_length=1, max_length=64)
    op: ArtifactPatchOp
    content_md: str | None = Field(default=None, max_length=ARTIFACT_CONTENT_MAX_LENGTH)
    expected_rev: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_content_required_unless_delete(self) -> Self:
        if self.op != "delete" and self.content_md is None:
            raise ValueError(f"op='{self.op}' verlangt ein `content_md`.")
        return self


class ArtifactMarkdown(BaseModel):
    """Read-Antwort eines doc-Artifacts: Markdown mit ``[#block_id]``-Ankern.

    Das gerenderte Markdown annotiert jeden Block mit seinem Anker, damit ein
    Agent Suchtreffer/Patch-Anker direkt im Text verorten kann (ADR-0021).
    """

    model_config = ConfigDict(from_attributes=True)

    artifact_id: UUID
    title: str
    rev: int
    markdown: str


class IngestRequest(BaseModel):
    """Eingabe fuer `POST .../work-areas/{area_id}/ingest` — Datei ODER URL.

    Genau EINE der Quellen `url`/`file_b64` muss gesetzt sein. Das
    Byte-Limit (`WHO2BE_INGEST_MAX_BYTES`, 413 `ingest_too_large`) und der
    SSRF-Guard (403 `url_forbidden`) werden serverseitig geprueft — darum
    traegt `file_b64` hier bewusst keine Modell-Obergrenze.
    """

    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(default=None, max_length=2000)
    file_b64: str | None = None
    filename: str | None = Field(default=None, max_length=300)
    occurred_at: datetime | None = None
    occurred_precision: OccurredPrecision | None = None
    sensitivity: Sensitivity | None = None

    @model_validator(mode="after")
    def _check_exactly_one_source(self) -> Self:
        if (self.url is None) == (self.file_b64 is None):
            raise ValueError("Genau eine Quelle angeben: `url` ODER `file_b64`.")
        return self


class IngestResult(BaseModel):
    """Ergebnis eines Ingests: Blob- + abgeleitetes Doc-Artifact (ADR-0048).

    `deduplicated=True`: dieselbe (area, sha256)-Kombination existierte
    bereits — der Ingest ist idempotent, die bestehenden IDs kommen zurueck.
    """

    model_config = ConfigDict(from_attributes=True)

    blob_artifact_id: UUID
    doc_artifact_id: UUID
    sha256: str
    deduplicated: bool
    block_count: int


class WorkAreaSearchHit(BaseModel):
    """Ein Suchtreffer der WorkArea-Suche — Anker + Snippet, nie das Dokument.

    `anchor` ist ``<artifact_id>#<block_id>`` (ADR-0021) und direkt
    `read_artifact(id, anchor)`-faehig.
    """

    model_config = ConfigDict(from_attributes=True)

    anchor: str
    artifact_id: UUID
    block_id: str
    title: str
    snippet: str
    score: float
    area_id: UUID


class TimelineGranularity(StrEnum):
    """Bucket-Granularitaet der Timeline-Abfrage."""

    day = "day"
    week = "week"
    month = "month"


class TimelineItem(BaseModel):
    """Ein Timeline-Eintrag: Anker + Quellenart (z. B. 'artifact', 'node')."""

    model_config = ConfigDict(from_attributes=True)

    anchor: str
    kind: str


class TimelineSlice(BaseModel):
    """Eine Zeitscheibe der Timeline (`bucket` = date_trunc-Schluessel)."""

    model_config = ConfigDict(from_attributes=True)

    bucket: str
    items: list[TimelineItem] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


class TimelineResult(BaseModel):
    """Timeline-Antwort: Zeitscheiben + separater unknown-Bucket.

    Eintraege mit `occurred_precision='unknown'` landen NIE in einer
    Zeitscheibe — sie stehen gesammelt in `unknown` (Spec-Akzeptanz N).
    """

    model_config = ConfigDict(from_attributes=True)

    slices: list[TimelineSlice] = Field(default_factory=list)
    unknown: list[TimelineItem] = Field(default_factory=list)
