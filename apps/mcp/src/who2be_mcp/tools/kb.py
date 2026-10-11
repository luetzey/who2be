"""KB-MCP-Tools (ADR-0047, WP9) — Tools 9-14 des Plans.

Zweites Submodul nach Architektur-Entscheidung 3.2 (Muster aus WP8,
`tools/workarea.py`): modulweite `@with_tool_log`-async-Funktionen (fuer
Tests direkt aufrufbar), `register(mcp)` haengt sie an die FastMCP-Instanz.
`build_client` wird zur LAUFZEIT ueber das `server`-Modul aufgeloest
(`_client()` importiert es erst im Tool-Aufruf) — das haelt den Import
zyklisch-sicher in BEIDE Richtungen und laesst den bestehenden
Test-monkeypatch-Pfad (`monkeypatch.setattr(server, "build_client", ...)`)
unveraendert greifen.

`promote_artifact` (Tool 14) wurde hier in WP9 implementiert und wird seit
WP19 registriert — seine REST-Route (`POST .../wa-artifacts/{id}/promote`)
kam mit WP14.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from who2be_mcp.client import ApiClient
from who2be_mcp.clients import kb as kb_api
from who2be_mcp.core_logging import with_tool_log
from who2be_models import (
    EdgeType,
    KbEdgeCreate,
    KbEdgeRead,
    KbNeighbor,
    KbNodeCreate,
    KbNodeRead,
    KbNodeUpdate,
    KbSearchHit,
    NodeTier,
    OccurredPrecision,
    ResourceRead,
    Sensitivity,
)


async def _client() -> ApiClient:
    """Baut den API-Client fuer den aktuellen Aufruf ueber `server.build_client`.

    Der `server`-Import liegt bewusst IM Aufruf (nicht auf Modul-Ebene):
    `server.py` importiert dieses Modul fuer `register(mcp)` — ein
    Modul-Level-Rueck-Import braeche, sobald `tools.kb` zuerst geladen wird.
    Der Laufzeit-Zugriff ueber das Modul-Attribut haelt zugleich den
    Test-Pfad intakt (monkeypatch von `server.build_client`).
    """
    from who2be_mcp import server

    return await server.build_client()


def _parse_uuid(value: str, label: str) -> UUID:
    """Parst eine UUID oder wirft einen fuer Agenten lesbaren `ToolError`."""
    try:
        return UUID(value)
    except ValueError as exc:
        raise ToolError(f"Ungueltige {label}-UUID: '{value}'.") from exc


def _first_error(exc: ValidationError) -> str:
    errors = exc.errors()
    return str(errors[0]["msg"]) if errors else "Ungueltige Eingabe."


@with_tool_log("search_kb")
async def search_kb(query: str, limit: int = 20) -> list[KbSearchHit]:
    """Durchsucht die kuratierte Knowledge Base (belegte Aussagen), nie die WorkArea.

    Treffer tragen `snippet`, `tier`, `status` und den Anker `node:<id>` fuer `neighbors`.
    `limit` <= 50. Nichts gefunden: sag es offen.
    """
    client = await _client()
    return await kb_api.search_kb(client, query, limit)


@with_tool_log("create_node")
async def create_node(
    content: str,
    tier: NodeTier,
    source_ref: str,
    occurred_at: datetime,
    occurred_precision: OccurredPrecision = OccurredPrecision.day,
    content_ref: str | None = None,
    sensitivity: Sensitivity = Sensitivity.general,
) -> KbNodeRead:
    """Legt eine belegte Aussage in der Knowledge Base an.

    `content`: eine praezise Aussage. `source_ref` (Pflicht): `sha256:<hash>`, `url:<...>` oder
    `<artifact_id>[#block]`. `tier`: `hypothesis` (Normalfall), `derived`, `verified` nur fuer
    Verifiziertes. `occurred_at` ist der fachliche Zeitpunkt.
    """
    client = await _client()
    try:
        data = KbNodeCreate(
            content=content,
            tier=tier,
            source_ref=source_ref,
            occurred_at=occurred_at,
            occurred_precision=occurred_precision,
            content_ref=content_ref,
            sensitivity=sensitivity,
        )
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await kb_api.create_node(client, data)


@with_tool_log("update_node")
async def update_node(
    node_id: str,
    content: str | None = None,
    tier: NodeTier | None = None,
    additional_source_ref: str | None = None,
) -> KbNodeRead:
    """Aendert einen KB-Node; ein hoeherer `tier` braucht einen andersartigen Beleg.

    Nach `derived` nur mit `additional_source_ref` anderer Art; `verified` setzt nur ein Mensch
    (422). Abstufen ist frei.
    """
    client = await _client()
    try:
        data = KbNodeUpdate(content=content, tier=tier, additional_source_ref=additional_source_ref)
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await kb_api.update_node(client, _parse_uuid(node_id, "Node"), data)


@with_tool_log("create_edge")
async def create_edge(
    from_anchor: str,
    to_anchor: str,
    type: EdgeType,
    evidence_from: list[str],
    evidence_to: list[str],
    co_query: str | None = None,
    co_n: int | None = None,
    co_from: datetime | None = None,
    co_to: datetime | None = None,
) -> KbEdgeRead:
    """Verbindet zwei Anker mit einer getypten, belegten Kante.

    `evidence_from` und `evidence_to` je 1-20 Anker. Typen: supports, contradicts, supersedes,
    derived_from, belongs_to, co_occurs_with. Gleichzeitigkeit ergibt nur `co_occurs_with`, dann
    mit `co_query`, `co_n` (>= 20), `co_from` und `co_to`; andere Typen ohne `co_`-Felder.
    """
    client = await _client()
    try:
        data = KbEdgeCreate(
            from_anchor=from_anchor,
            to_anchor=to_anchor,
            type=type,
            evidence_from=evidence_from,
            evidence_to=evidence_to,
            co_query=co_query,
            co_n=co_n,
            co_from=co_from,
            co_to=co_to,
        )
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await kb_api.create_edge(client, data)


@with_tool_log("neighbors")
async def neighbors(anchor: str, type: EdgeType | None = None, depth: int = 1) -> list[KbNeighbor]:
    """Nachbar-Nodes eines KB-Ankers entlang der Kanten, Tiefe 1-3.

    `anchor`: `node:<id>` oder ein Artifact-Anker; `type` filtert die Kante. Bei
    `co_occurs_with` immer die Fallzahl `co_n` nennen: gemeinsames Auftreten ist weder Beleg
    noch Ursache.
    """
    client = await _client()
    return await kb_api.neighbors(client, anchor, type, depth)


@with_tool_log("promote_artifact")
async def promote_artifact(artifact_id: str, target_resource_id: str | None = None) -> ResourceRead:
    """Uebernimmt ein WorkArea-Dokument als Resource-Draft, nie direkt aktiv.

    Mit `target_resource_id` als neuer Draft einer bestehenden Resource, sonst als neue
    Resource. Aktivieren muss danach ein Mensch.
    """
    client = await _client()
    parsed_target = (
        None if target_resource_id is None else _parse_uuid(target_resource_id, "Resource")
    )
    return await kb_api.promote_artifact(
        client, _parse_uuid(artifact_id, "Artifact"), parsed_target
    )


def register(mcp: FastMCP) -> None:
    """Registriert die KB-Tools an der FastMCP-Instanz.

    Die Tool-Funktionen bleiben modulweite, direkt importier- und aufrufbare
    async-Funktionen (Test-Muster A); hier werden sie lediglich mit
    `output_schema=None` (Payload-Budget, siehe server.py) angehaengt.
    """
    for fn in (
        search_kb,
        create_node,
        update_node,
        create_edge,
        neighbors,
        # `promote_artifact` (WP9 implementiert) ist seit WP19 registriert —
        # die REST-Route existiert (WP14) und `target_resource_id` geht als
        # Query-Parameter raus (siehe `clients/kb.py`).
        promote_artifact,
    ):
        mcp.tool(output_schema=None)(fn)
