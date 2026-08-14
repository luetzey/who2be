"""Knowledge-Base-Models (ADR-0047) — belegpflichtige Nodes und getypte Kanten.

Die Knowledge Base ist die kuratierte Wissensschicht ueber der WorkArea:
jeder Node traegt eine Aussage (`content`) mit Pflicht-Beleg (`source_ref`:
``sha256:<h>`` | ``url:<u>`` | ``artifact:<uuid>[#block]``), jede Kante
verlangt Evidence-Anker auf BEIDEN Seiten (min. 1 pro Seite — der Service
prueft das in einer Transaktion, 422 `evidence_missing`). Unversioniert wie
die WorkArea: kein Status-Workflow, kein Draft.

Tier-Ordnung (`hypothesis` < `derived` < `verified`): Hochstufen von
`hypothesis` auf `derived` verlangt einen ZUSAETZLICHEN Beleg anderer
`source_ref_kind`; `derived` -> `verified` per Update ist immer 422
`tier_upgrade_forbidden` (Heben auf verified ist P2-UI-Thema).
`co_occurs_with`-Kanten sind statistisch belegpflichtig (co_query/co_n/
co_from/co_to); die Mindest-Fallzahl (n >= 20, 422 `correlation_underpowered`)
prueft der SERVICE mit dem tatsaechlichen n im detail — nicht das Modell.

Die P1-Schemafelder (`ttl_expires_at`, `status`, `derivation_depth`,
Conflict-Modell) sind bereits angelegt (Plan 2026-08-13); ihre Verfalls-/
Challenger-Logik kommt erst mit Spec-P1.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from who2be_models.workarea import OccurredPrecision, Sensitivity

# Obergrenzen (DoS-Schutz, F-01-Linie): Aussage-Text, Beleg-Referenz
# (2100 = URL-Praefix + 2000-Zeichen-URL), Herkunfts-Anker.
KB_NODE_CONTENT_MAX_LENGTH = 4000
KB_SOURCE_REF_MAX_LENGTH = 2100
KB_CONTENT_REF_MAX_LENGTH = 200

# Evidence-Anker einer Kanten-Seite (``<artifact_id>#<block_id>`` u. ae.).
EvidenceAnchor = Annotated[str, StringConstraints(min_length=1, max_length=200)]

# Obergrenze der Evidence-Anker PRO Kanten-Seite (DoS-Schutz, Security-Review
# 2026-08-13 M6): jeder Anker kostet serverseitig eine Aufloesung + eine
# `kb_edge_evidence`-Row — mehr als 20 Belege pro Seite sind kein sinnvoller
# Anwendungsfall, aber ein Amplifikations-Vektor.
KB_EDGE_EVIDENCE_MAX_ANCHORS = 20


class NodeTier(StrEnum):
    """Vertrauensstufe eines KB-Nodes (ADR-0047) — geordnete Leiter.

    - ``verified``: menschlich bestaetigt (Heben dorthin ist P2-UI-Thema).
    - ``derived``: aus mehreren Belegen abgeleitet.
    - ``hypothesis``: unbestaetigte Vermutung (Einstieg fuer Agenten).
    """

    verified = "verified"
    derived = "derived"
    hypothesis = "hypothesis"


class NodeStatus(StrEnum):
    """Lebenszustand eines Nodes (P1-Vorbereitung: TTL/Verfall).

    ``live`` ist der Default; ``stale`` markiert abgelaufene/ueberholte
    Nodes (gesetzt vom P1-Verfalls-Sweep, nie vom Agenten direkt).
    """

    live = "live"
    stale = "stale"


class SourceRefKind(StrEnum):
    """Art der Beleg-Referenz — vom Server aus `source_ref` abgeleitet."""

    blob = "blob"
    url = "url"
    artifact = "artifact"


class KbNodeCreate(BaseModel):
    """Eingabe fuer `POST .../kb/nodes` — eine belegte Aussage.

    `source_ref` ist Pflicht (Belegpflicht, ADR-0047): ``sha256:<h>`` |
    ``url:<u>`` | ``artifact:<uuid>[#block]``; die Aufloesung (422
    `anchor_unresolvable`) und die `source_ref_kind`-Ableitung macht der
    Server. `occurred_precision`-Default ist ``day`` (Wissens-Aussagen sind
    selten minutengenau). `content_ref` ist der optionale Herkunfts-Anker
    des Aussagen-Texts.
    """

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=KB_NODE_CONTENT_MAX_LENGTH)
    tier: NodeTier
    source_ref: str = Field(min_length=1, max_length=KB_SOURCE_REF_MAX_LENGTH)
    occurred_at: datetime
    occurred_precision: OccurredPrecision = OccurredPrecision.day
    content_ref: str | None = Field(default=None, max_length=KB_CONTENT_REF_MAX_LENGTH)
    sensitivity: Sensitivity = Sensitivity.general


class KbNodeRead(BaseModel):
    """Ein KB-Node im aktuellen Stand (`kb_node`).

    `created_by` ist die Akteur-Kennung (``agent:<id>`` | ``user:<id>``),
    analog `wa_category_rule.created_by`. `derivation_depth` zaehlt die
    `derived_from`-Kette ab Roh-Beleg (P1: Drift-Grenze).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    tier: NodeTier
    content: str
    content_ref: str | None = None
    source_ref: str
    source_ref_kind: SourceRefKind
    ttl_expires_at: datetime | None = None
    status: NodeStatus
    derivation_depth: int
    sensitivity: Sensitivity
    occurred_at: datetime
    occurred_precision: OccurredPrecision
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class KbNodeUpdate(BaseModel):
    """Eingabe fuer `PATCH .../kb/nodes/{id}` — Teilupdate, mind. ein Feld.

    Tier-Regeln prueft der Service: hypothesis -> derived nur mit
    `additional_source_ref` anderer `source_ref_kind`; derived -> verified
    immer 422 `tier_upgrade_forbidden` (ADR-0047).
    """

    model_config = ConfigDict(extra="forbid")

    content: str | None = Field(default=None, min_length=1, max_length=KB_NODE_CONTENT_MAX_LENGTH)
    tier: NodeTier | None = None
    additional_source_ref: str | None = Field(
        default=None, min_length=1, max_length=KB_SOURCE_REF_MAX_LENGTH
    )

    @model_validator(mode="after")
    def _check_at_least_one_field(self) -> Self:
        if self.content is None and self.tier is None and self.additional_source_ref is None:
            raise ValueError("Mindestens ein Feld angeben (content, tier, additional_source_ref).")
        return self


class EdgeType(StrEnum):
    """Kantentyp der Knowledge Base (ADR-0047)."""

    supports = "supports"
    contradicts = "contradicts"
    supersedes = "supersedes"
    derived_from = "derived_from"
    belongs_to = "belongs_to"
    co_occurs_with = "co_occurs_with"


class KbEdgeCreate(BaseModel):
    """Eingabe fuer `POST .../kb/edges` — getypte, belegpflichtige Kante.

    `evidence_from`/`evidence_to`: min. 1, max. `KB_EDGE_EVIDENCE_MAX_ANCHORS`
    Anker PRO Seite (der Service prueft Aufloesbarkeit + Persistenz in EINER
    Transaktion — 422 `evidence_missing`/`anchor_unresolvable`, kein
    Teilzustand). `co_occurs_with` verlangt die
    statistischen Felder co_query/co_n/co_from/co_to; alle anderen Typen
    duerfen sie NICHT tragen. Die Mindest-Fallzahl (n >= 20) prueft der
    SERVICE mit sprechendem 422 `correlation_underpowered` (tatsaechliches n
    im detail) — hier gilt nur `co_n >= 1`.
    """

    model_config = ConfigDict(extra="forbid")

    from_anchor: str = Field(min_length=1, max_length=200)
    to_anchor: str = Field(min_length=1, max_length=200)
    type: EdgeType
    evidence_from: list[EvidenceAnchor] = Field(
        min_length=1, max_length=KB_EDGE_EVIDENCE_MAX_ANCHORS
    )
    evidence_to: list[EvidenceAnchor] = Field(min_length=1, max_length=KB_EDGE_EVIDENCE_MAX_ANCHORS)
    co_query: str | None = Field(default=None, max_length=4000)
    co_n: int | None = Field(default=None, ge=1)
    co_from: datetime | None = None
    co_to: datetime | None = None

    @model_validator(mode="after")
    def _check_co_fields_match_type(self) -> Self:
        co_fields = (self.co_query, self.co_n, self.co_from, self.co_to)
        if self.type == EdgeType.co_occurs_with:
            if any(value is None for value in co_fields):
                raise ValueError(
                    "type='co_occurs_with' verlangt co_query, co_n, co_from und co_to."
                )
        elif any(value is not None for value in co_fields):
            raise ValueError("co_-Felder sind nur fuer type='co_occurs_with' zulaessig.")
        return self


class KbEdgeRead(BaseModel):
    """Eine KB-Kante im aktuellen Stand (`kb_edge` + `kb_edge_evidence`).

    `from_node_id`/`to_node_id` sind die aufgeloesten Node-Bezuege (None,
    wenn der Anker kein KB-Node ist). Kanten sind im MVP nicht loeschbar,
    daher gibt es kein Update-/Delete-Modell.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    type: EdgeType
    from_anchor: str
    to_anchor: str
    from_node_id: UUID | None = None
    to_node_id: UUID | None = None
    evidence_from: list[str] = Field(default_factory=list)
    evidence_to: list[str] = Field(default_factory=list)
    co_query: str | None = None
    co_n: int | None = None
    co_from: datetime | None = None
    co_to: datetime | None = None
    created_by: str | None = None
    created_at: datetime


class KbNeighbor(BaseModel):
    """Ein Nachbar-Node aus `GET .../kb/neighbors` (ADR-0047).

    `direction` ist die Kantenrichtung relativ zum Ausgangs-Anker; bei
    `co_occurs_with` traegt `co_n` IMMER die Fallzahl mit (Spec-Akzeptanz O).
    """

    model_config = ConfigDict(from_attributes=True)

    node: KbNodeRead
    edge_type: EdgeType
    direction: Literal["in", "out"]
    co_n: int | None = None


class KbSearchHit(BaseModel):
    """Ein Treffer der KB-Suche — nie WorkArea-Inhalte (getrennte Indizes)."""

    model_config = ConfigDict(from_attributes=True)

    node_id: UUID
    anchor: str
    snippet: str
    tier: NodeTier
    status: NodeStatus
    score: float


class KbConflictKind(StrEnum):
    """Art eines offenen Konflikts (`kb_conflict.kind`).

    ``node``: widerspruechliche Nodes (P1-Challenger legt sie an);
    ``rule``: zwei aktive Kategorie-Regeln matchen dieselbe Row mit
    verschiedenen Kategorien (Welle 6, L).
    """

    node = "node"
    rule = "rule"


class KbConflictRead(BaseModel):
    """Ein offener/aufgeloester Konflikt (`kb_conflict`)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: KbConflictKind
    a_id: UUID
    b_id: UUID
    reason: str
    opened_at: datetime
    resolved_at: datetime | None = None
    resolution: str | None = None
