"""KB-MCP-Tools (ADR-0047, WP9) — Tools 9-14 des Plans.

Zweites Submodul nach Architektur-Entscheidung 3.2 (Muster aus WP8,
`tools/workarea.py`): modulweite `@with_tool_log`-async-Funktionen (fuer
Tests direkt aufrufbar), `register(mcp)` haengt sie an die FastMCP-Instanz.
`build_client` wird zur LAUFZEIT ueber das `server`-Modul aufgeloest
(`_client()` importiert es erst im Tool-Aufruf) — das haelt den Import
zyklisch-sicher in BEIDE Richtungen und laesst den bestehenden
Test-monkeypatch-Pfad (`monkeypatch.setattr(server, "build_client", ...)`)
unveraendert greifen.

Besonderheit WP9: `promote_artifact` (Tool 14) ist fertig implementiert,
wird aber erst in WP14 registriert — seine REST-Route existiert noch nicht.
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
    """Durchsucht NUR die kuratierte Knowledge Base — nie die WorkArea.

    KB und WorkArea haben getrennte Indizes: Rohmaterial findest du mit
    `search_workarea`, hier liegen kuratierte, BELEGTE Aussagen (Nodes).
    Jeder Treffer traegt `snippet`, `tier` (Vertrauensstufe), `status` und
    den Anker ``node:<id>`` — reiche ihn unveraendert an
    `neighbors(anchor)` weiter, um die Kontext-Kanten des Nodes zu sehen.
    Durchsucht wird nur, was du laut deiner Quell-Area-Grants lesen darfst;
    findest du nichts, sag das offen, statt zu raten. `limit` <= 50.
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
    """Legt eine belegte Aussage in der Knowledge Base an (Belegpflicht).

    `content` ist EINE praezise Aussage; `source_ref` ist ihr Pflicht-Beleg:
    ``sha256:<hash>`` (Roh-Blob), ``url:<...>`` (externe Quelle) oder
    ``<artifact_id>[#block]`` (WorkArea-Artifact, moeglichst mit
    Block-Anker). Der Server loest den Beleg auf (unaufloesbar → 422) und
    leitet `source_ref_kind` + Quell-Areas selbst ab. `tier`: `hypothesis`
    (unbestaetigte Vermutung — dein Normalfall), `derived` (aus mehreren
    Belegen abgeleitet), `verified` NUR fuer nachweislich Verifiziertes —
    im Zweifel niedriger einsteigen und spaeter per `update_node` heben.
    `occurred_at` ist der fachliche Zeitpunkt der Aussage (Default-
    Praezision `day`), nie der Aufruf-Zeitpunkt. `content_ref` nennt
    optional den Herkunfts-Anker des Aussagen-Texts.
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
    """Teilupdate eines KB-Nodes — Tier-Aufstieg braucht neuen, ANDERSARTIGEN Beleg.

    Mindestens ein Feld angeben. `tier='derived'` von `hypothesis` aus
    verlangt `additional_source_ref` mit einem Beleg ANDERER Art als der
    bestehende (z. B. ``url:<...>`` zusaetzlich zu einem Artifact-Beleg) —
    derselbe Beleg-Typ zaehlt nicht. Heben auf `verified` ist per Update
    GESPERRT (immer 422 `tier_upgrade_forbidden`); das bestaetigt ein
    Mensch. Abstufen ist frei. `additional_source_ref` nutzt die Formate
    von `create_node` (``sha256:<hash>`` | ``url:<...>`` |
    ``<artifact_id>[#block]``).
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
    """Verbindet zwei Anker mit einer getypten, belegpflichtigen Kante.

    `evidence_from`/`evidence_to`: min. 1, max. 20 Anker JE Seite — der
    Server prueft Aufloesbarkeit und persistiert alles in EINER Transaktion
    (fehlende Evidence → 422 `evidence_missing`, kein Teilzustand). Typen:
    supports | contradicts | supersedes | derived_from | belongs_to |
    co_occurs_with. Aus blosser GLEICHZEITIGKEIT folgt NUR
    `co_occurs_with` — nie supports/derived_from. `co_occurs_with`
    verlangt zusaetzlich die Statistik-Felder `co_query` (die Abfrage),
    `co_n` (Fallzahl, n >= 20 — darunter 422 mit tatsaechlichem n) und den
    Zeitraum `co_from`/`co_to`; alle anderen Typen duerfen KEINE
    co_-Felder tragen.
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
    """Nachbar-Nodes eines Ankers entlang der KB-Kanten (Tiefe 1-3).

    `anchor` ist ``node:<id>`` (z. B. aus einem `search_kb`-Treffer) oder
    ein Artifact-Anker; `type` filtert optional auf einen Kantentyp. Jeder
    Nachbar traegt den Node selbst, `edge_type` und `direction` (Richtung
    relativ zum Ausgangs-Anker). WICHTIG bei `co_occurs_with`: `co_n`
    traegt IMMER die Fallzahl — kommuniziere sie mit (etwa: tritt gemeinsam
    auf, n=34), nie als blanke Behauptung; Ko-Okkurrenz ist KEINE
    Kausalitaet und KEIN Beleg fuer supports/derived_from.
    """
    client = await _client()
    return await kb_api.neighbors(client, anchor, type, depth)


@with_tool_log("promote_artifact")
async def promote_artifact(artifact_id: str, target_resource_id: str | None = None) -> ResourceRead:
    """Kuratiert ein WorkArea-Artifact als Resource-DRAFT (nie direkt active).

    Der einzige Uebergang von Rohmaterial zu kuratiertem Wissen (Spec G):
    der Server uebernimmt den Inhalt als neuen Resource-Draft —
    `target_resource_id` ergaenzt eine BESTEHENDE Resource um einen Draft,
    ohne sie entsteht eine neue Resource — und protokolliert die Herkunft
    (`status_history`-Note). Aktivieren muss danach ein Mensch bzw. eine
    separate Transition; Promote veroeffentlicht NICHTS.
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
    ):
        mcp.tool(output_schema=None)(fn)
    # promote_artifact wird in WP14 registriert (REST-Route folgt) — Tool- und
    # Client-Funktion sind fertig; mit der Registrierung kommen dann auch der
    # `tool_requirements`-Eintrag (resource_write, bestehende Capability), der
    # `_TOOLS`-Eintrag im Prompt-Resolver und die Count-Guards (71 -> 72).
