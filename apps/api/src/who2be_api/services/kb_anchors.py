"""Anker-Aufloesung fuer die Knowledge Base (ADR-0047, WP7 — Spec D).

Aufgeloeste Formen (ADR-0021 + Plan-Datenmodell 0077):

- ``<artifact_uuid>#<block_id>`` — Artifact im Workspace, Block muss in der
  `content`-Blockliste stehen; auch als ``artifact:<uuid>[#block]``
  (Beleg-Schreibweise aus 0077) akzeptiert.
- ``<artifact_uuid>`` — nur das Artifact.
- ``node:<uuid>`` — bestehender KB-Node.
- ``sha256:<hex64>`` — Blob im Katalog (`wa_blob`, 0075).
- ``url:<http…>`` — rein syntaktisch (http/https), kein Lookup.

Die Aufloesung ist SCOPE-BEWUSST: Artifact- und Node-Lookups laufen mit der
Scope-Liste des Aufrufers (`readable_area_ids`) IN der SQL — ein Anker auf
nicht lesbares Material ist von einem nicht existierenden nicht
unterscheidbar (422 statt Existenz-Orakel). Unaufloesbar → 422
`anchor_unresolvable` mit dem Anker im detail.

ARC-3: kein SQL — die Lookups laufen ueber das strukturelle
`AnchorLookup`-Protokoll (erfuellt von `PgKbRepository`); `fetcher` darf die
Transaktions-Connection des Aufrufers sein (Teilzustands-freie Edge-Writes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeAlias
from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiGateError
from who2be_models import SourceRefKind

_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection

_SHA256_RE = re.compile(r"[0-9a-f]{64}")


class AnchorKind(StrEnum):
    """Art eines aufgeloesten Ankers (Obermenge von `SourceRefKind`)."""

    artifact = "artifact"
    node = "node"
    blob = "blob"
    url = "url"


@dataclass(frozen=True)
class ResolvedAnchor:
    """Ergebnis der Anker-Aufloesung.

    `area_id` ist nur fuer Artifact-Anker gesetzt (Quell-Area fuer
    `kb_node_source_area`); `node_id` nur fuer ``node:``-Anker.
    """

    anchor: str
    kind: AnchorKind
    artifact_id: UUID | None = None
    block_id: str | None = None
    node_id: UUID | None = None
    area_id: UUID | None = None

    @property
    def source_kind(self) -> SourceRefKind:
        """`source_ref_kind`-Ableitung — nie fuer ``node:``-Anker aufrufen
        (`resolve_source_ref` weist die Form vorher ab)."""
        return SourceRefKind(self.kind.value)


class AnchorLookup(Protocol):
    """Struktureller Lookup-Vertrag (Teilmenge von `KbRepository`)."""

    async def artifact_area(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        artifact_id: UUID,
        *,
        block_id: str | None,
        restrict_area_ids: list[UUID] | None,
    ) -> UUID | None: ...

    async def blob_exists(self, fetcher: _Fetcher, workspace_id: UUID, sha256: str) -> bool: ...

    async def node_visible(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        node_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
    ) -> bool: ...


def _unresolvable(anchor: str, hint: str) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        reason="anchor_unresolvable",
        actionable_by="agent",
        detail=f"Der Anker '{anchor}' ist nicht aufloesbar: {hint}",
    )


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


async def resolve_anchor(
    lookup: AnchorLookup,
    fetcher: _Fetcher,
    workspace_id: UUID,
    anchor: str,
    *,
    restrict_area_ids: list[UUID] | None,
) -> ResolvedAnchor:
    """Loest einen Anker in jeder unterstuetzten Form auf (s. Modul-Kopf).

    Wirft 422 `anchor_unresolvable` (Anker im detail), wenn die Form
    unbekannt ist oder das referenzierte Objekt im Lese-Scope des Aufrufers
    nicht existiert.
    """
    text = anchor.strip()
    if text.startswith("node:"):
        node_id = _parse_uuid(text.removeprefix("node:"))
        if node_id is None:
            raise _unresolvable(anchor, "hinter 'node:' wird eine UUID erwartet.")
        if not await lookup.node_visible(
            fetcher, workspace_id, node_id, restrict_area_ids=restrict_area_ids
        ):
            raise _unresolvable(anchor, "kein KB-Node mit dieser ID im Lese-Scope.")
        return ResolvedAnchor(anchor=text, kind=AnchorKind.node, node_id=node_id)
    if text.startswith("sha256:"):
        digest = text.removeprefix("sha256:").lower()
        if _SHA256_RE.fullmatch(digest) is None:
            raise _unresolvable(anchor, "hinter 'sha256:' werden 64 Hex-Zeichen erwartet.")
        if not await lookup.blob_exists(fetcher, workspace_id, digest):
            raise _unresolvable(anchor, "kein Blob mit diesem Hash im Workspace-Katalog.")
        return ResolvedAnchor(anchor=text, kind=AnchorKind.blob)
    if text.startswith("url:"):
        # Rein syntaktisch (kein Abruf, kein Lookup) — der Beleg ist die URL.
        if not text.removeprefix("url:").startswith(("http://", "https://")):
            raise _unresolvable(anchor, "hinter 'url:' wird eine http(s)-URL erwartet.")
        return ResolvedAnchor(anchor=text, kind=AnchorKind.url)

    body = text.removeprefix("artifact:")
    artifact_part, sep, block_id = body.partition("#")
    artifact_id = _parse_uuid(artifact_part)
    if artifact_id is None or (sep and not block_id):
        raise _unresolvable(
            anchor,
            "erwartet wird <artifact_uuid>[#block_id], node:<uuid>, "
            "sha256:<hex64> oder url:<http…>.",
        )
    area_id = await lookup.artifact_area(
        fetcher,
        workspace_id,
        artifact_id,
        block_id=block_id if sep else None,
        restrict_area_ids=restrict_area_ids,
    )
    if area_id is None:
        raise _unresolvable(anchor, "kein Artifact (bzw. Block) mit dieser Kennung im Lese-Scope.")
    return ResolvedAnchor(
        anchor=text,
        kind=AnchorKind.artifact,
        artifact_id=artifact_id,
        block_id=block_id if sep else None,
        area_id=area_id,
    )


async def resolve_source_ref(
    lookup: AnchorLookup,
    fetcher: _Fetcher,
    workspace_id: UUID,
    source_ref: str,
    *,
    restrict_area_ids: list[UUID] | None,
) -> ResolvedAnchor:
    """Loest eine Beleg-Referenz auf — nur ``sha256:``/``url:``/Artifact-Form.

    ``node:``-Anker sind KEIN gueltiger Beleg (`source_ref_kind` kennt nur
    blob|url|artifact, 0077) → 422 `anchor_unresolvable`.
    """
    resolved = await resolve_anchor(
        lookup, fetcher, workspace_id, source_ref, restrict_area_ids=restrict_area_ids
    )
    if resolved.kind == AnchorKind.node:
        raise _unresolvable(
            source_ref,
            "ein Beleg (source_ref) muss sha256:<hex64>, url:<http…> oder "
            "ein Artifact-Anker sein — kein node:-Anker.",
        )
    return resolved


async def resolve_edge_end(
    lookup: AnchorLookup,
    fetcher: _Fetcher,
    workspace_id: UUID,
    anchor: str,
    *,
    restrict_area_ids: list[UUID] | None,
) -> ResolvedAnchor:
    """Loest ein Kanten-Ende auf — nur ``node:``- oder Artifact-Anker.

    ``sha256:``/``url:``-Formen sind als Kanten-Ende nicht zulaessig (Kanten
    verbinden Wissens-Objekte, nicht Roh-Belege) → 422 `anchor_unresolvable`.
    """
    resolved = await resolve_anchor(
        lookup, fetcher, workspace_id, anchor, restrict_area_ids=restrict_area_ids
    )
    if resolved.kind not in (AnchorKind.node, AnchorKind.artifact):
        raise _unresolvable(
            anchor,
            "Kanten-Enden muessen node:<uuid>- oder Artifact-Anker sein "
            "(sha256:/url: sind nur als Evidence/Beleg zulaessig).",
        )
    return resolved
