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
    WorkAreaScope,
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


def _parse_area_id(area_id: str | None) -> UUID | None:
    return None if area_id is None else _parse_uuid(area_id, "Area")


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
    """Legt ein doc-Artifact in der WorkArea an (unversioniert, lockfrei).

    `occurred_at` ist der Zeitpunkt, zu dem der Inhalt PASSIERT ist (Meeting,
    Beleg, Ereignis) — NICHT der Aufruf-Zeitpunkt. Kennst du ihn nicht, setze
    `occurred_precision='unknown'` (ein now()-Fallback existiert bewusst
    nicht). `area_id=None` schreibt in deine private Area (auto-angelegt);
    fuer Team-Inhalte eine shared Area angeben (siehe `whoami.work_areas`).
    Stammt der Inhalt aus einem Fremdsystem, setze `source_system` +
    `fetched_at` (Pflicht-Paar) und ggf. `source_url`.

    Der Server splittet `content_md` deterministisch in Bloecke und vergibt
    stabile 8-stellige `block_id`s — die Antwort traegt sie in `blocks`.
    `<artifact_id>#<block_id>` ist der Anker, mit dem `read_artifact(anchor)`
    und `patch_artifact` einen Block direkt adressieren; Suchtreffer liefern
    ihn mit. Weiterschreiben: `append_artifact` (konfliktfrei) oder
    `patch_artifact` (gezielt am Anker).
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
    return await wa_api.create_artifact(client, _parse_area_id(area_id), data)


@with_tool_log("append_artifact")
async def append_artifact(artifact_id: str, content_md: str) -> ArtifactRead:
    """Haengt Markdown als neue Bloecke an ein doc-Artifact an (lockfrei).

    Der sichere Default fuers Weiterschreiben: Append ist atomar (rev+1),
    braucht KEIN `expected_rev` und kollidiert nie mit parallelen Appends
    anderer Agenten. Nutze `patch_artifact` nur, wenn ein BESTEHENDER Block
    gezielt geaendert werden muss. Die Antwort traegt die neuen Bloecke mit
    ihren stabilen 8-stelligen `block_id`s (Anker-Sprache
    `<artifact_id>#<block_id>`) und die neue `rev`.
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
    """Bearbeitet EINEN Block eines doc-Artifacts am Anker (optimistisch).

    `anchor` ist die 8-stellige `block_id` — aus `read_artifact` (dort als
    `[#block_id]` annotiert) oder aus einem Suchtreffer-Anker
    `<artifact_id>#<block_id>` (beide Formen werden akzeptiert). `op`:
    'replace' ersetzt den Block, 'insert_after' fuegt `content_md` als neue
    Bloecke dahinter ein, 'delete' entfernt ihn (dann ohne `content_md`).

    `expected_rev` ist die zuletzt GELESENE `rev` des Artifacts. Ist sie
    veraltet, antwortet der Server 409 `rev_conflict` — die AKTUELLE rev
    steht im Fehlerdetail. Dann: Artifact via `read_artifact` neu lesen,
    pruefen, ob dein Edit noch passt, und den Patch mit der aktuellen rev
    wiederholen — nicht blind die rev aus dem Fehler einsetzen. Fuer reines
    Anhaengen ist `append_artifact` konfliktfrei die bessere Wahl.
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
    """Liest ein doc-Artifact als Markdown mit `[#block_id]`-Anker-Annotationen.

    Jeder Block ist mit seinem stabilen Anker annotiert — der `block_id`-Teil
    der Anker-Sprache `<artifact_id>#<block_id>` (Suchtreffer, Patches). Mit
    `anchor` liefert der Server NUR den einen Block — der richtige
    Folgeschritt nach einem `search_workarea`-Treffer, statt das ganze
    Dokument zu laden; akzeptiert die reine `block_id` oder den vollen
    Treffer-Anker. Die Antwort traegt zudem die aktuelle `rev` — nutze sie
    als `expected_rev` fuer einen anschliessenden `patch_artifact`.
    """
    client = await _client()
    block = None if anchor is None else _block_id(anchor)
    return await wa_api.read_artifact(client, _parse_uuid(artifact_id, "Artifact"), block)


@with_tool_log("list_artifacts")
async def list_artifacts(area_id: str | None = None) -> list[ArtifactRead]:
    """NICHT der Einstieg — nutze `search_workarea`; list nur fuer die
    vollstaendige Bestandsaufnahme kleiner Areas.

    Liefert die Artifact-METADATEN einer Area (Titel, Typ, `rev`,
    `occurred_at`, `sensitivity` — keine Inhalte). `area_id=None` = deine
    private Area. Inhalte danach gezielt via `read_artifact(artifact_id)`
    laden; suchst du eine bestimmte Stelle, liefert `search_workarea` Anker
    (`<artifact_id>#<block_id>`) + Snippet, ohne dass du Dokumente
    durchgehen musst.
    """
    client = await _client()
    parsed_area = _parse_area_id(area_id)
    if parsed_area is None:
        parsed_area = await _resolve_private_area_id(client)
    return await wa_api.list_artifacts(client, parsed_area)


async def _resolve_private_area_id(client: ApiClient) -> UUID:
    """Loest `area_id=None` auf die private Area des Aufrufers auf.

    `GET .../work-areas` legt die private Area eines agent-gebundenen Tokens
    beim ersten Zugriff automatisch an (ADR-0047). Menschen/ungebundene
    Tokens haben keine (bzw. editor+ sieht mehrere fremde private Areas) —
    dann ist eine explizite `area_id` gefordert.
    """
    areas = await wa_api.list_work_areas(client)
    private = [area for area in areas if area.scope == WorkAreaScope.private]
    if len(private) == 1:
        return private[0].id
    if not private:
        raise ToolError(
            "Keine private Area aufloesbar — nur agent-gebundene Tokens haben eine. "
            "Gib `area_id` explizit an (sichtbare Areas: `whoami.work_areas`)."
        )
    raise ToolError("Mehrere private Areas sichtbar (Mensch/editor+) — gib `area_id` explizit an.")


@with_tool_log("delete_artifact")
async def delete_artifact(artifact_id: str) -> str:
    """Loescht ein WorkArea-Artifact endgueltig (inkl. seiner Such-Chunks).

    Es gibt KEINEN Papierkorb und keine Versionierung in der WorkArea —
    geloescht ist geloescht. Nutze das nur fuer Rohmaterial, das nachweislich
    obsolet ist (Duplikat, Fehl-Ingest, ueberholter Zwischenstand). Inhalte,
    die dauerhaft gebraucht werden, gehoeren VOR dem Loeschen als kuratierte
    Resource gesichert. Antwort ist eine kurze Bestaetigung.
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
    """Ingestiert eine Datei (`file_b64`) ODER eine `url` in die WorkArea.

    Der Server extrahiert den Text (PDF, HTML, Text/Markdown — sonst 422)
    und legt in EINER Transaktion an: den Roh-Blob (content-addressed,
    SHA-256), ein blob-Artifact und ein doc-Artifact mit dem Text als
    durchsuchbare Bloecke inkl. Such-Chunks. Genau EINE Quelle angeben; bei
    `file_b64` moeglichst auch `filename`. Dedup laeuft ueber den
    Inhalts-Hash: derselbe Inhalt in derselben Area liefert
    `deduplicated=True` mit den bestehenden IDs — idempotent, kein Fehler.

    `area_id=None` = deine private Area. `occurred_at` ist der fachliche
    Zeitpunkt des Inhalts (z. B. Rechnungsdatum), nicht der Abruf-Zeitpunkt.
    Danach findet `search_workarea` die Passagen (Anker
    `<artifact_id>#<block_id>`), `read_artifact` liest das doc-Artifact.
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
    return await wa_api.ingest(client, _parse_area_id(area_id), data)


@with_tool_log("search_workarea")
async def search_workarea(query: str, area_id: str | None = None) -> list[WorkAreaSearchHit]:
    """DER Einstieg in die WorkArea: Volltextsuche mit Anker + Snippet.

    Beginne hier statt bei `list_artifacts`. Jeder Treffer traegt `snippet`
    (die Passage), `title`, `area_id` und den Anker
    `<artifact_id>#<block_id>` (ADR-0021): damit liefert
    `read_artifact(artifact_id, anchor)` direkt den EINEN Block, ohne das
    ganze Dokument zu laden. Durchsucht werden nur Areas, die du lesen
    darfst; `area_id` schraenkt optional auf eine Area ein — ausserhalb
    deines Scopes ist das Ergebnis leer (kein Existenz-Orakel). Findest du
    nichts, sag das offen, statt zu raten.
    """
    client = await _client()
    return await wa_api.search_workarea(client, query, _parse_area_id(area_id))


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
