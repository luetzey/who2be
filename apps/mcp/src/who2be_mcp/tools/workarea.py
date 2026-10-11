"""WorkArea-MCP-Tools (ADR-0047, WP8) — Tools 1-8 des Plans.

Erstes Submodul nach Architektur-Entscheidung 3.2: modulweite async-Funktionen
(fuer Tests direkt aufrufbar), `register(mcp)` haengt sie an die
FastMCP-Instanz. `build_client` wird zur LAUFZEIT ueber das `server`-Modul
aufgeloest (`_client()` importiert es erst im Tool-Aufruf) — das haelt den
Import zyklisch-sicher in BEIDE Richtungen (`server.py` importiert dieses
Modul fuer `register`; ein Modul-Level-Rueck-Import wuerde als Einstiegspunkt
scheitern) und laesst den bestehenden Test-monkeypatch-Pfad
(`monkeypatch.setattr(server, "build_client", ...)`) unveraendert greifen.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from who2be_mcp.client import ApiClient
from who2be_mcp.clients import workarea as wa_api
from who2be_mcp.core_logging import with_tool_log
from who2be_mcp.tools.area_ref import parse_area_id, resolve_private_area_id
from who2be_models import (
    ArtifactAppend,
    ArtifactCreate,
    ArtifactMarkdown,
    ArtifactPatch,
    ArtifactPatchOp,
    ArtifactRead,
    IngestRequest,
    IngestResult,
    OccurredPrecision,
    Sensitivity,
    WorkAreaSearchHit,
)


async def _client() -> ApiClient:
    """Baut den API-Client fuer den aktuellen Aufruf ueber `server.build_client`.

    Der `server`-Import liegt bewusst IM Aufruf (nicht auf Modul-Ebene):
    `server.py` importiert dieses Modul fuer `register(mcp)` — ein
    Modul-Level-Rueck-Import braeche, sobald `tools.workarea` zuerst geladen
    wird. Der Laufzeit-Zugriff ueber das Modul-Attribut haelt zugleich den
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


def _block_id(anchor: str) -> str:
    """Normalisiert einen Anker auf die reine `block_id`.

    Suchtreffer tragen den vollen Anker ``<artifact_id>#<block_id>``
    (ADR-0021); die REST-Query erwartet nur die `block_id` — beide Formen
    werden akzeptiert, damit ein Agent den Treffer-Anker unveraendert
    weiterreichen kann.
    """
    return anchor.rsplit("#", 1)[-1]


def _first_error(exc: ValidationError) -> str:
    errors = exc.errors()
    return str(errors[0]["msg"]) if errors else "Ungueltige Eingabe."


@with_tool_log("create_artifact")
async def create_artifact(
    title: str,
    content_md: str,
    occurred_at: datetime,
    occurred_precision: OccurredPrecision = OccurredPrecision.minute,
    area_id: str | None = None,
    sensitivity: Sensitivity = Sensitivity.general,
    source_system: str | None = None,
    source_url: str | None = None,
    fetched_at: datetime | None = None,
) -> ArtifactRead:
    """Legt ein Dokument in der WorkArea an (unversioniert, ohne Sperre).

    `occurred_at` ist der fachliche Zeitpunkt des Inhalts, nicht der Aufruf; unbekannt:
    `occurred_precision='unknown'`. `area_id=None` ist die private Area. Inhalte aus
    Fremdsystemen tragen `source_system` und `fetched_at`. Die Antwort nennt die `block_id`s;
    weiter mit `append_artifact` oder `patch_artifact`.
    """
    client = await _client()
    try:
        data = ArtifactCreate(
            title=title,
            content_md=content_md,
            occurred_at=occurred_at,
            occurred_precision=occurred_precision,
            sensitivity=sensitivity,
            source_system=source_system,
            source_url=source_url,
            fetched_at=fetched_at,
        )
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await wa_api.create_artifact(client, parse_area_id(area_id), data)


@with_tool_log("append_artifact")
async def append_artifact(artifact_id: str, content_md: str) -> ArtifactRead:
    """Haengt Markdown als neue Bloecke an ein WorkArea-Dokument an, ohne Konflikt.

    Der sichere Weg zum Weiterschreiben, ohne `expected_rev`. Antwort: neue `block_id`s und
    `rev`.
    """
    client = await _client()
    try:
        data = ArtifactAppend(content_md=content_md)
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await wa_api.append_artifact(client, _parse_uuid(artifact_id, "Artifact"), data)


@with_tool_log("patch_artifact")
async def patch_artifact(
    artifact_id: str,
    anchor: str,
    op: ArtifactPatchOp,
    expected_rev: int,
    content_md: str | None = None,
) -> ArtifactRead:
    """Aendert einen Block eines WorkArea-Dokuments am Anker, mit `expected_rev`.

    `op`: `replace`, `insert_after` (mit `content_md`) oder `delete`. Bei 409 `rev_conflict` neu
    lesen, den Edit pruefen und mit der aktuellen rev wiederholen. Zum Anhaengen besser
    `append_artifact`.
    """
    client = await _client()
    try:
        data = ArtifactPatch(
            anchor=_block_id(anchor),
            op=op,
            content_md=content_md,
            expected_rev=expected_rev,
        )
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await wa_api.patch_artifact(client, _parse_uuid(artifact_id, "Artifact"), data)


@with_tool_log("read_artifact")
async def read_artifact(artifact_id: str, anchor: str | None = None) -> ArtifactMarkdown:
    """Liest ein WorkArea-Dokument als Markdown mit `[#block_id]`-Ankern.

    `anchor` (block_id oder `<artifact_id>#<block_id>`) schneidet zu: der Anker eines
    Suchtreffers liefert die ganze Passage bis zur naechsten Ueberschrift, ein Anker mitten im
    Text genau diesen Block. Die Antwort traegt `rev` als `expected_rev` fuer `patch_artifact`.
    """
    client = await _client()
    block = None if anchor is None else _block_id(anchor)
    return await wa_api.read_artifact(client, _parse_uuid(artifact_id, "Artifact"), block)


@with_tool_log("list_artifacts")
async def list_artifacts(area_id: str | None = None) -> list[ArtifactRead]:
    """Listet die Dokumente einer WorkArea (Titel, Typ, rev, Zeitpunkt), ohne Inhalt.

    Nur fuer kleine Areas; eine Stelle findet `search_workarea`. `area_id=None` ist deine
    private Area.
    """
    client = await _client()
    parsed_area = parse_area_id(area_id)
    if parsed_area is None:
        parsed_area = await resolve_private_area_id(client)
    return await wa_api.list_artifacts(client, parsed_area)


@with_tool_log("delete_artifact")
async def delete_artifact(artifact_id: str) -> str:
    """Loescht ein WorkArea-Dokument endgueltig, ohne Papierkorb.

    Nur fuer nachweislich Obsoletes; Dauerhaftes vorher als Resource sichern
    (`promote_artifact`).
    """
    client = await _client()
    parsed = _parse_uuid(artifact_id, "Artifact")
    await wa_api.delete_artifact(client, parsed)
    return f"Artifact {parsed} geloescht."


@with_tool_log("ingest")
async def ingest(
    url: str | None = None,
    file_b64: str | None = None,
    filename: str | None = None,
    area_id: str | None = None,
    occurred_at: datetime | None = None,
    sensitivity: Sensitivity | None = None,
) -> IngestResult:
    """Nimmt eine Datei (`file_b64`) oder `url` in die WorkArea auf und macht sie durchsuchbar.

    Genau eine Quelle; PDF, HTML, Text oder Markdown. Derselbe Inhalt in derselben Area liefert
    `deduplicated=True` mit den bestehenden IDs. `occurred_at` ist der fachliche Zeitpunkt.
    Danach `search_workarea`.
    """
    client = await _client()
    try:
        data = IngestRequest(
            url=url,
            file_b64=file_b64,
            filename=filename,
            occurred_at=occurred_at,
            sensitivity=sensitivity,
        )
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    return await wa_api.ingest(client, parse_area_id(area_id), data)


@with_tool_log("search_workarea")
async def search_workarea(query: str, area_id: str | None = None) -> list[WorkAreaSearchHit]:
    """Volltextsuche in der WorkArea (Rohmaterial, Notizen, Ingest) mit Anker und Snippet.

    Einstieg statt `list_artifacts`. Der Anker `<artifact_id>#<block_id>` geht direkt an
    `read_artifact`. `area_id` schraenkt ein; durchsucht wird nur, was du lesen darfst. Nichts
    gefunden: sag es offen.
    """
    client = await _client()
    return await wa_api.search_workarea(client, query, parse_area_id(area_id))


def register(mcp: FastMCP) -> None:
    """Registriert die 8 WorkArea-Tools an der FastMCP-Instanz.

    Die Tool-Funktionen bleiben modulweite, direkt importier- und aufrufbare
    async-Funktionen (Test-Muster A); hier werden sie lediglich mit
    `output_schema=None` (Payload-Budget, siehe server.py) angehaengt.
    """
    for fn in (
        create_artifact,
        append_artifact,
        patch_artifact,
        read_artifact,
        list_artifacts,
        delete_artifact,
        ingest,
        search_workarea,
    ):
        mcp.tool(output_schema=None)(fn)
