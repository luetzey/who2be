"""Datenzugriff fuer die Knowledge Base (`kb_node`/`kb_edge`/..., Migration 0077).

Sichtbarkeits-Kern (Plan-Entscheidung 5, Spec E): ein Node ist fuer einen
Aufrufer mit beschraenktem Area-Scope genau dann lesbar, wenn KEINE seiner
Source-Areas (`kb_node_source_area`) ausserhalb der erlaubten Liste liegt;
Nodes ohne Source-Rows sind fuer alle lesbar. Das Praedikat ist EINE
wiederverwendete SQL-Bedingung (`_visible_sql`) und sitzt IN der WHERE-Klausel
jedes Read-Pfads (get/neighbors/search) — kein Nachfiltern, kein Existenz-Leak.
`None` als Scope-Liste (Mensch editor+) schaltet den Filter ab; die leere
Liste laesst bewusst nur quellenlose Nodes durch.

Die Schreibmethoden nehmen eine `Connection`: der Service haelt Node-/Edge-
Write, Evidence und `kb_node_source_area`-Pflege in EINER Transaktion zusammen
(Muster `wa_artifact_repository`). Reads laufen ueber Pool ODER Connection
(`_Fetcher`). Jede Query filtert auf `workspace_id` (Defense-in-Depth
zusaetzlich zur RLS).

Die KB-Suche liest per Konstruktion NUR `kb_node.search` ('simple', 0077) —
`wa_chunk`-Inhalte koennen hier nie auftauchen (getrennte Indizes, Spec C).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, TypeAlias
from uuid import UUID

import asyncpg

from who2be_models import KbEdgeRead, KbNeighbor, KbNodeRead, KbSearchHit

_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection

_NODE_FIELDS = (
    "id",
    "workspace_id",
    "tier",
    "content",
    "content_ref",
    "source_ref",
    "source_ref_kind",
    "ttl_expires_at",
    "status",
    "derivation_depth",
    "sensitivity",
    "occurred_at",
    "occurred_precision",
    "created_by",
    "created_at",
    "updated_at",
)
_NODE_COLUMNS = ", ".join(_NODE_FIELDS)
_NODE_COLUMNS_N = ", ".join(f"n.{field}" for field in _NODE_FIELDS)

_EDGE_COLUMNS = (
    "id, workspace_id, type, from_anchor, to_anchor, from_node_id, to_node_id, "
    "co_query, co_n, co_from, co_to, created_by, created_at"
)

# Obergrenze des Suche-Snippets: Anker + Kostprobe, nie die ganze Aussage
# (Muster WorkArea-Suche).
_SNIPPET_MAX_CHARS = 200


def _visible_sql(pos: int) -> str:
    """DIE wiederverwendete Sichtbarkeits-Bedingung fuer `kb_node n` (Spec E).

    Parameter an Position `pos` ist die Scope-Liste (`uuid[]` oder NULL):
    NULL = unbeschraenkt (Mensch editor+); sonst ist der Node lesbar, wenn
    keine Source-Area ausserhalb der Liste liegt. Nodes ohne Source-Rows
    (z. B. reine url-/blob-Belege) sind fuer alle lesbar — das NOT EXISTS
    ueber null Zeilen ist wahr.
    """
    return (
        f"(${pos}::uuid[] IS NULL OR NOT EXISTS ("
        "SELECT 1 FROM kb_node_source_area s "
        f"WHERE s.node_id = n.id AND NOT (s.area_id = ANY(${pos}::uuid[]))))"
    )


def _to_node(row: asyncpg.Record | dict[str, Any]) -> KbNodeRead:
    """Row → `KbNodeRead`; `created_by` (DB: Akteur-UUID) wird zum String."""
    data: dict[str, Any] = dict(row)
    created_by = data.get("created_by")
    data["created_by"] = str(created_by) if created_by is not None else None
    return KbNodeRead.model_validate(data)


def _to_edge(row: asyncpg.Record) -> KbEdgeRead:
    """Row → `KbEdgeRead` (ohne Evidence — die haengt der Service an)."""
    data: dict[str, Any] = dict(row)
    created_by = data.get("created_by")
    data["created_by"] = str(created_by) if created_by is not None else None
    return KbEdgeRead.model_validate(data)


def _to_neighbor(row: asyncpg.Record) -> KbNeighbor:
    """Row (Node-Spalten + `edge_*`-Aliase) → `KbNeighbor`.

    `co_n` kommt direkt aus `kb_edge.co_n` — fuer `co_occurs_with` per
    DB-CHECK immer gefuellt (Spec-Akzeptanz O), fuer andere Typen NULL.
    """
    data: dict[str, Any] = dict(row)
    edge_type = data.pop("edge_type")
    co_n = data.pop("edge_co_n")
    direction = data.pop("edge_direction")
    return KbNeighbor.model_validate(
        {"node": _to_node(data), "edge_type": edge_type, "direction": direction, "co_n": co_n}
    )


def _snippet(text: str) -> str:
    """Kuerzt die Aussage auf Snippet-Laenge (harte Kappung + Ellipse)."""
    if len(text) <= _SNIPPET_MAX_CHARS:
        return text
    return text[: _SNIPPET_MAX_CHARS - 1].rstrip() + "…"


class KbRepository(Protocol):
    """Vertrag des KB-Datenzugriffs (Service- und Resolver-Sicht)."""

    async def insert_node(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        *,
        tier: str,
        content: str,
        content_ref: str | None,
        source_ref: str,
        source_ref_kind: str,
        sensitivity: str,
        occurred_at: datetime,
        occurred_precision: str,
        created_by: UUID,
    ) -> KbNodeRead: ...

    async def update_node(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        node_id: UUID,
        *,
        content: str | None,
        tier: str | None,
    ) -> KbNodeRead | None: ...

    async def get_node(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        node_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
    ) -> KbNodeRead | None: ...

    async def node_visible(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        node_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
    ) -> bool: ...

    async def artifact_area(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        artifact_id: UUID,
        *,
        block_id: str | None,
        restrict_area_ids: list[UUID] | None,
    ) -> UUID | None: ...

    async def blob_exists(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        sha256: str,
        *,
        restrict_area_ids: list[UUID] | None,
    ) -> bool: ...

    async def add_source_areas(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        node_id: UUID,
        area_ids: list[UUID],
    ) -> None: ...

    async def source_areas(
        self, fetcher: _Fetcher, workspace_id: UUID, node_id: UUID
    ) -> list[UUID]: ...

    async def insert_edge(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        *,
        edge_type: str,
        from_anchor: str,
        to_anchor: str,
        from_node_id: UUID | None,
        to_node_id: UUID | None,
        co_query: str | None,
        co_n: int | None,
        co_from: datetime | None,
        co_to: datetime | None,
        created_by: UUID,
    ) -> KbEdgeRead: ...

    async def insert_evidence(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        edge_id: UUID,
        side: str,
        anchors: list[str],
    ) -> None: ...

    async def adjacent_to_nodes(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        node_ids: list[UUID],
        *,
        restrict_area_ids: list[UUID] | None,
        edge_type: str | None,
    ) -> list[KbNeighbor]: ...

    async def adjacent_to_anchor(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        anchor: str,
        *,
        restrict_area_ids: list[UUID] | None,
        edge_type: str | None,
    ) -> list[KbNeighbor]: ...

    async def search(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        query: str,
        limit: int,
        *,
        restrict_area_ids: list[UUID] | None,
    ) -> list[KbSearchHit]: ...


class PgKbRepository:
    """asyncpg-Implementierung von `KbRepository`.

    Bewusst ohne Pool im Konstruktor: die Schreibpfade laufen auf der
    Transaktions-Connection des Services (Muster `PgWaArtifactRepository`).
    """

    async def insert_node(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        *,
        tier: str,
        content: str,
        content_ref: str | None,
        source_ref: str,
        source_ref_kind: str,
        sensitivity: str,
        occurred_at: datetime,
        occurred_precision: str,
        created_by: UUID,
    ) -> KbNodeRead:
        row = await conn.fetchrow(
            "INSERT INTO kb_node "
            "(workspace_id, tier, content, content_ref, source_ref, source_ref_kind, "
            " sensitivity, occurred_at, occurred_precision, created_by) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
            f"RETURNING {_NODE_COLUMNS}",
            workspace_id,
            tier,
            content,
            content_ref,
            source_ref,
            source_ref_kind,
            sensitivity,
            occurred_at,
            occurred_precision,
            created_by,
        )
        assert row is not None
        return _to_node(row)

    async def update_node(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        node_id: UUID,
        *,
        content: str | None,
        tier: str | None,
    ) -> KbNodeRead | None:
        """Teilupdate (`NULL` = Feld unveraendert); `updated_at` immer neu."""
        row = await conn.fetchrow(
            "UPDATE kb_node SET "
            "content = coalesce($3, content), tier = coalesce($4, tier), updated_at = now() "
            "WHERE workspace_id = $1 AND id = $2 "
            f"RETURNING {_NODE_COLUMNS}",
            workspace_id,
            node_id,
            content,
            tier,
        )
        return _to_node(row) if row is not None else None

    async def get_node(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        node_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
    ) -> KbNodeRead | None:
        """Einzel-Read mit Sichtbarkeits-Praedikat IN der SQL (s. Modul-Kopf)."""
        row = await fetcher.fetchrow(
            f"SELECT {_NODE_COLUMNS_N} FROM kb_node n "
            f"WHERE n.workspace_id = $1 AND n.id = $2 AND {_visible_sql(3)}",
            workspace_id,
            node_id,
            restrict_area_ids,
        )
        return _to_node(row) if row is not None else None

    async def node_visible(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        node_id: UUID,
        *,
        restrict_area_ids: list[UUID] | None,
    ) -> bool:
        """Existenz IM Sichtbarkeits-Scope — fuer die Anker-Aufloesung."""
        found = await fetcher.fetchval(
            "SELECT 1 FROM kb_node n "
            f"WHERE n.workspace_id = $1 AND n.id = $2 AND {_visible_sql(3)}",
            workspace_id,
            node_id,
            restrict_area_ids,
        )
        return found is not None

    async def artifact_area(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        artifact_id: UUID,
        *,
        block_id: str | None,
        restrict_area_ids: list[UUID] | None,
    ) -> UUID | None:
        """Area des Artifacts, wenn es (und ggf. der Block) im Scope existiert.

        Der Area-Scope-Filter sitzt IN der SQL (kein Existenz-Leak fuer
        Artifacts ausserhalb des Lese-Scopes); `block_id` prueft gegen die
        `content`-Blockliste (Anker `<artifact_id>#<block_id>`, ADR-0021).
        """
        area_id = await fetcher.fetchval(
            "SELECT area_id FROM wa_artifact "
            "WHERE workspace_id = $1 AND id = $2 "
            "AND ($3::uuid[] IS NULL OR area_id = ANY($3::uuid[])) "
            "AND ($4::text IS NULL OR EXISTS ("
            "    SELECT 1 FROM jsonb_array_elements(coalesce(content, '[]'::jsonb)) b "
            "    WHERE b->>'block_id' = $4))",
            workspace_id,
            artifact_id,
            restrict_area_ids,
            block_id,
        )
        return area_id if area_id is not None else None

    async def blob_exists(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        sha256: str,
        *,
        restrict_area_ids: list[UUID] | None,
    ) -> bool:
        """Blob-Katalog-Lookup (`wa_blob`, 0075) — SCOPE-BEWUSST (L2).

        `wa_blob` selbst ist workspace-gebunden; damit der Lookup kein
        workspace-weites Existenz-Orakel wird (Security-Review 2026-08-13 L2),
        verlangt ein area-beschraenkter Aufrufer ein fuer ihn LESBARES
        blob-Artifact (`wa_artifact.type='blob'`, `content_ref` = Hash) in
        einer seiner Areas. Unbeschraenkte Aufrufer (Mensch editor+) pruefen
        nur den Katalog.
        """
        if restrict_area_ids is None:
            found = await fetcher.fetchval(
                "SELECT 1 FROM wa_blob WHERE workspace_id = $1 AND sha256 = $2",
                workspace_id,
                sha256,
            )
            return found is not None
        found = await fetcher.fetchval(
            "SELECT 1 FROM wa_blob b "
            "WHERE b.workspace_id = $1 AND b.sha256 = $2 "
            "  AND EXISTS (SELECT 1 FROM wa_artifact a "
            "              WHERE a.workspace_id = b.workspace_id "
            "                AND a.type = 'blob' AND a.content_ref = b.sha256 "
            "                AND a.area_id = ANY($3::uuid[]))",
            workspace_id,
            sha256,
            restrict_area_ids,
        )
        return found is not None

    async def add_source_areas(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        node_id: UUID,
        area_ids: list[UUID],
    ) -> None:
        """UNIONt Areas in `kb_node_source_area` — monoton, nie entfernend
        (`ON CONFLICT DO NOTHING` auf dem PK, Plan-Entscheidung 5)."""
        if not area_ids:
            return
        await conn.execute(
            "INSERT INTO kb_node_source_area (workspace_id, node_id, area_id) "
            "SELECT $1, $2, a FROM unnest($3::uuid[]) AS a "
            "ON CONFLICT (node_id, area_id) DO NOTHING",
            workspace_id,
            node_id,
            area_ids,
        )

    async def source_areas(
        self, fetcher: _Fetcher, workspace_id: UUID, node_id: UUID
    ) -> list[UUID]:
        rows = await fetcher.fetch(
            "SELECT area_id FROM kb_node_source_area "
            "WHERE workspace_id = $1 AND node_id = $2 ORDER BY area_id",
            workspace_id,
            node_id,
        )
        return [row["area_id"] for row in rows]

    async def insert_edge(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        *,
        edge_type: str,
        from_anchor: str,
        to_anchor: str,
        from_node_id: UUID | None,
        to_node_id: UUID | None,
        co_query: str | None,
        co_n: int | None,
        co_from: datetime | None,
        co_to: datetime | None,
        created_by: UUID,
    ) -> KbEdgeRead:
        row = await conn.fetchrow(
            "INSERT INTO kb_edge "
            "(workspace_id, type, from_anchor, to_anchor, from_node_id, to_node_id, "
            " co_query, co_n, co_from, co_to, created_by) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) "
            f"RETURNING {_EDGE_COLUMNS}",
            workspace_id,
            edge_type,
            from_anchor,
            to_anchor,
            from_node_id,
            to_node_id,
            co_query,
            co_n,
            co_from,
            co_to,
            created_by,
        )
        assert row is not None
        return _to_edge(row)

    async def insert_evidence(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        edge_id: UUID,
        side: str,
        anchors: list[str],
    ) -> None:
        await conn.executemany(
            "INSERT INTO kb_edge_evidence (workspace_id, edge_id, side, anchor) "
            "VALUES ($1, $2, $3, $4)",
            [(workspace_id, edge_id, side, anchor) for anchor in anchors],
        )

    async def adjacent_to_nodes(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        node_ids: list[UUID],
        *,
        restrict_area_ids: list[UUID] | None,
        edge_type: str | None,
    ) -> list[KbNeighbor]:
        """Nachbarn einer Node-Frontier (beide Kantenrichtungen), nur sichtbare.

        Der Nachbar ist der jeweils ANDERE Endpunkt der Kante; Kanten, deren
        anderer Endpunkt kein KB-Node ist (Artifact-Anker), fallen durch den
        JOIN heraus. `edge_type` NULL = alle Typen.
        """
        rows = await fetcher.fetch(
            f"SELECT {_NODE_COLUMNS_N}, "
            "       e.type AS edge_type, e.co_n AS edge_co_n, "
            "       CASE WHEN e.from_node_id = ANY($2::uuid[]) THEN 'out' ELSE 'in' END "
            "           AS edge_direction "
            "FROM kb_edge e "
            "JOIN kb_node n ON n.workspace_id = e.workspace_id "
            " AND n.id = CASE WHEN e.from_node_id = ANY($2::uuid[]) "
            "                 THEN e.to_node_id ELSE e.from_node_id END "
            "WHERE e.workspace_id = $1 "
            "  AND (e.from_node_id = ANY($2::uuid[]) OR e.to_node_id = ANY($2::uuid[])) "
            "  AND ($4::text IS NULL OR e.type = $4) "
            f"  AND {_visible_sql(3)} "
            "ORDER BY n.created_at, n.id",
            workspace_id,
            node_ids,
            restrict_area_ids,
            edge_type,
        )
        return [_to_neighbor(row) for row in rows]

    async def adjacent_to_anchor(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        anchor: str,
        *,
        restrict_area_ids: list[UUID] | None,
        edge_type: str | None,
    ) -> list[KbNeighbor]:
        """Nachbarn eines Nicht-Node-Ankers (Artifact-Anker als Kanten-Ende).

        Matcht die gespeicherte Anker-Schreibweise (`from_anchor`/`to_anchor`)
        exakt — Kanten bewahren die Eingabe-Schreibweise (0077).
        """
        rows = await fetcher.fetch(
            f"SELECT {_NODE_COLUMNS_N}, "
            "       e.type AS edge_type, e.co_n AS edge_co_n, "
            "       CASE WHEN e.from_anchor = $2 THEN 'out' ELSE 'in' END AS edge_direction "
            "FROM kb_edge e "
            "JOIN kb_node n ON n.workspace_id = e.workspace_id "
            " AND n.id = CASE WHEN e.from_anchor = $2 THEN e.to_node_id ELSE e.from_node_id END "
            "WHERE e.workspace_id = $1 "
            "  AND (e.from_anchor = $2 OR e.to_anchor = $2) "
            "  AND ($4::text IS NULL OR e.type = $4) "
            f"  AND {_visible_sql(3)} "
            "ORDER BY n.created_at, n.id",
            workspace_id,
            anchor,
            restrict_area_ids,
            edge_type,
        )
        return [_to_neighbor(row) for row in rows]

    async def search(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        query: str,
        limit: int,
        *,
        restrict_area_ids: list[UUID] | None,
    ) -> list[KbSearchHit]:
        """FTS ueber `kb_node.search` ('simple' wie die Generated Column 0077).

        Sichtbarkeit sitzt IN der WHERE-Klausel (Spec E); die leere
        Scope-Liste wird NICHT kurzgeschlossen — quellenlose Nodes bleiben
        fuer alle sichtbar (s. `_visible_sql`). Liefert Anker + Snippet,
        nie WorkArea-Inhalte (nur `kb_node`, s. Modul-Kopf).
        """
        rows = await fetcher.fetch(
            "SELECT n.id, n.tier, n.status, n.content, "
            "       ts_rank(n.search, plainto_tsquery('simple', $2)) AS score "
            "FROM kb_node n "
            "WHERE n.workspace_id = $1 "
            "  AND n.search @@ plainto_tsquery('simple', $2) "
            f"  AND {_visible_sql(4)} "
            "ORDER BY score DESC, n.id "
            "LIMIT $3",
            workspace_id,
            query,
            limit,
            restrict_area_ids,
        )
        return [
            KbSearchHit(
                node_id=row["id"],
                anchor=f"node:{row['id']}",
                snippet=_snippet(row["content"]),
                tier=row["tier"],
                status=row["status"],
                score=float(row["score"]),
            )
            for row in rows
        ]
