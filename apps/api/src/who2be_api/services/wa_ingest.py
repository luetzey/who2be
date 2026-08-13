"""Ingest-Pipeline der Agent-WorkArea (ADR-0048, WP5 — Spec B): synchron, ohne Teilzustand.

Ablauf (Plan „Ingest-Pipeline (B)", bindend):

1. Eingang Datei (`file_b64`) oder URL — Limit `WHO2BE_INGEST_MAX_BYTES`
   (Base64-Schaetzung VOR dem Dekodieren; URL-Downloads streamen mit Byte-Cap)
   → 413 `ingest_too_large`.
2. SSRF-Guard fuer URLs (`ensure_url_allowed`, pur testbar): Schema-Allowlist
   http/https, DNS-Aufloesung via `socket.getaddrinfo`, JEDE IP gegen
   loopback/private/link-local/multicast/reserved/unspecified geprueft →
   403 `url_forbidden`. Redirects manuell (max. 3), jeder Hop erneut geprueft;
   Timeout 10 s; `trust_env=False` (keine Proxy-Umgehung des Guards).
3. Typ-Erkennung: Magic-Bytes (``%PDF-``, ``<html``/``<!doctype``) vor
   Content-Type vor Datei-Endung; PDF/HTML/Text/Markdown, sonst 422
   `ingest_unsupported`.
4. Extraktion in memory VOR jedem Write: PDF via pypdf (leer → 422, NICHTS
   persistiert); HTML via BeautifulSoup (script/style/noscript/iframe +
   ``on*``-Handler gestrippt, h1–h6 → ``#``-Headings, p/li → Absaetze);
   Text/Markdown direkt. Ergebnis laeuft durch `split_markdown`.
5. SHA-256 ueber die ORIGINALBYTES; Dedup pro (workspace, sha256, Ziel-Area)
   → 200 mit bestehenden IDs, `deduplicated=True`, kein Write.
6. Blob-PUT (`blob_key`) VOR der DB-Transaktion — content-addressed, ein
   Doppel-PUT ist harmlos; scheitert die Transaktion, bleibt hoechstens ein
   Orphan fuer den Purge-Sweep.
7. EINE Postgres-Transaktion: `wa_blob`-Upsert + blob-Artifact + doc-Artifact
   + `sync_artifact_chunks`.

Gates wie `wa_artifacts`: Agent → `require_capability(workarea_write)` +
`require_write_rate`; Mensch → `require_role(editor)`; beide zusaetzlich
`ensure_area_access(write)`. Ohne BlobStore → 503 `blobstore_unconfigured`.
ARC-3: kein SQL, keine HTTPException — nur `ApiGateError` + Repos.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
from base64 import b64decode
from datetime import UTC, datetime
from io import BytesIO
from posixpath import basename
from typing import Literal
from urllib.parse import urljoin, urlsplit
from uuid import UUID

import asyncpg
import httpx
from bs4 import BeautifulSoup, Tag
from fastapi import status
from pypdf import PdfReader

from who2be_api.blobstore import blob_key, build_blob_store
from who2be_api.core.config import get_settings
from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_write_rate,
)
from who2be_api.core.workarea_scope import (
    agent_not_found,
    ensure_area_access,
    is_agent_bound,
)
from who2be_api.repositories.wa_blob_repository import WaBlobRepository
from who2be_api.repositories.work_area_repository import WorkAreaRepository
from who2be_api.repositories.workspace_repository import WorkspaceRepository
from who2be_api.services.content_locale import resolve_content_locale
from who2be_api.services.wa_blocks import split_markdown
from who2be_api.services.wa_chunks import sync_artifact_chunks
from who2be_models import (
    AgentCapability,
    IngestRequest,
    IngestResult,
    OccurredPrecision,
    Sensitivity,
    WorkAreaGrantLevel,
    WorkspaceRole,
)

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_MAX_REDIRECTS = 3
_FETCH_TIMEOUT_SECONDS = 10.0
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# Titel-Obergrenze von `wa_artifact.title` (Modell `ArtifactCreate`).
_TITLE_MAX_LENGTH = 300

IngestKind = Literal["pdf", "html", "markdown", "text"]

# Kanonischer Media-Type pro erkannter Art — landet in `wa_blob.media_type`
# und als Objekt-Metadatum im BlobStore.
_MEDIA_TYPES: dict[IngestKind, str] = {
    "pdf": "application/pdf",
    "html": "text/html",
    "markdown": "text/markdown",
    "text": "text/plain",
}

_EXTENSION_KINDS: dict[str, IngestKind] = {
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
}

_CONTENT_TYPE_KINDS: dict[str, IngestKind] = {
    "application/pdf": "pdf",
    "text/html": "html",
    "application/xhtml+xml": "html",
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
    "text/plain": "text",
}

# HTML-Elemente, die vor der Text-Extraktion komplett entfallen (aktiver
# Inhalt bzw. Nicht-Inhalt) — Pipeline-Schritt 4.
_HTML_STRIP_TAGS = ("script", "style", "noscript", "iframe")
_HTML_TEXT_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li")

# Test-Injektionspunkt fuer den HTTP-Transport (Muster `set_blob_store`):
# Tests setzen einen `httpx.MockTransport` — echtes Netz ist im Test tabu.
_transport_override: httpx.AsyncBaseTransport | None = None


def set_ingest_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Setzt den HTTP-Transport fuer URL-Ingests — fuer Tests (MockTransport)."""
    global _transport_override
    _transport_override = transport


def reset_ingest_transport() -> None:
    """Verwirft den Transport-Override (Test-Teardown)."""
    global _transport_override
    _transport_override = None


# ------------------------------------------------------------------ Fehler


def _url_forbidden(detail: str) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="url_forbidden",
        actionable_by="agent",
        detail=detail,
    )


def _too_large(max_bytes: int) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_413_CONTENT_TOO_LARGE,
        reason="ingest_too_large",
        actionable_by="agent",
        detail=f"Die Quelle ueberschreitet das Ingest-Limit von {max_bytes} Bytes.",
    )


def _unsupported(detail: str) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        reason="ingest_unsupported",
        actionable_by="agent",
        detail=detail,
    )


def _blobstore_unconfigured() -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
        reason="blobstore_unconfigured",
        actionable_by="human",
        detail=(
            "Kein Blob-Storage konfiguriert (WHO2BE_BLOBSTORE_*) — Ingest ist "
            "auf dieser Installation nicht verfuegbar."
        ),
    )


# ------------------------------------------------------------------ SSRF-Guard


def _is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True fuer Adressen, die der Ingest nie kontaktieren darf.

    Loopback, private Netze (inkl. IPv6-ULA fc00::/7), Link-Local
    (169.254.0.0/16 — Cloud-Metadaten! — bzw. fe80::/10), Multicast,
    reserved und unspecified. IPv4-mapped-IPv6 (::ffff:a.b.c.d) wird auf die
    innere IPv4-Adresse normalisiert, damit der Check nicht umgangen wird.
    """
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def ensure_url_allowed(url: str) -> None:
    """SSRF-Guard (Pipeline-Schritt 2) — pur testbar, wirft 403 `url_forbidden`.

    Prueft Schema (nur http/https), loest den Host via `socket.getaddrinfo`
    auf und prueft JEDE zurueckgegebene Adresse mit `_is_forbidden_ip`.
    Nicht aufloesbare Hosts sind ebenfalls verboten (fail closed).

    **DNS-Rebinding-Grenze (bewusste Entscheidung, im Plan freigegeben):**
    nach diesem Check verbindet httpx normal ueber den Hostnamen und loest ihn
    dabei ERNEUT auf. Ein Angreifer mit eigenem DNS koennte zwischen Check und
    Connect auf eine private IP umschwenken (TTL 0). Die Absicherung dagegen
    (gepinnte IP im Transport) staende in keinem Verhaeltnis zum Risiko dieses
    authentifizierten, editor-/capability-gegateten Endpunkts — dokumentierte
    Restluecke statt komplexem Custom-Transport.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise _url_forbidden(f"URL-Schema '{parts.scheme or '<leer>'}' ist nicht erlaubt.")
    host = parts.hostname
    if not host:
        raise _url_forbidden("URL ohne Host.")
    port = parts.port or (443 if scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise _url_forbidden(f"Host '{host}' ist nicht aufloesbar.") from exc
    if not infos:
        raise _url_forbidden(f"Host '{host}' ist nicht aufloesbar.")
    for info in infos:
        # sockaddr[0] ist die Adresse; IPv6-Scope-Suffix (%eth0) abschneiden.
        address = str(info[4][0]).split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise _url_forbidden(f"Host '{host}' liefert eine unlesbare Adresse.") from exc
        if _is_forbidden_ip(ip):
            raise _url_forbidden(
                f"Host '{host}' zeigt auf einen internen/reservierten Adressbereich."
            )


async def fetch_url(
    url: str, max_bytes: int, transport: httpx.AsyncBaseTransport | None = None
) -> tuple[bytes, str | None]:
    """Laedt eine geprueft-oeffentliche URL — Streaming mit Byte-Cap.

    Redirects laufen MANUELL (``follow_redirects=False``, max. 3 Hops), jeder
    Hop wird erneut durch `ensure_url_allowed` geprueft — ein Redirect auf
    eine interne Adresse bricht mit 403 ab. Rueckgabe: ``(bytes, content_type)``.
    """
    current = url
    async with httpx.AsyncClient(
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(_FETCH_TIMEOUT_SECONDS),
        transport=transport,
    ) as client:
        for _hop in range(_MAX_REDIRECTS + 1):
            # Blocking-DNS nicht auf dem Event-Loop ausfuehren.
            await asyncio.to_thread(ensure_url_allowed, current)
            try:
                async with client.stream("GET", current) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location:
                            raise _unsupported("Redirect-Antwort ohne Location-Header.")
                        current = urljoin(current, location)
                        continue
                    if not (200 <= response.status_code < 300):
                        raise _unsupported(
                            f"URL-Abruf fehlgeschlagen (HTTP {response.status_code})."
                        )
                    buffer = bytearray()
                    async for chunk in response.aiter_bytes():
                        buffer.extend(chunk)
                        if len(buffer) > max_bytes:
                            raise _too_large(max_bytes)
                    return bytes(buffer), response.headers.get("content-type")
            except httpx.HTTPError as exc:
                raise _unsupported(f"URL-Abruf fehlgeschlagen ({exc.__class__.__name__}).") from exc
    raise _url_forbidden(f"Zu viele Redirects (max. {_MAX_REDIRECTS}).")


# ------------------------------------------------------- Typ-Erkennung + Extraktion


def detect_kind(data: bytes, content_type: str | None, name: str | None) -> IngestKind | None:
    """Erkennt die Ingest-Art: Magic-Bytes vor Content-Type vor Datei-Endung.

    Magic-Bytes zuerst, weil sie die verlaesslichste Quelle sind (ein als
    ``text/plain`` ausgeliefertes PDF bleibt ein PDF). `None` = nicht
    unterstuetzt (Aufrufer → 422 `ingest_unsupported`).
    """
    if data.startswith(b"%PDF-"):
        return "pdf"
    head = data[:1024].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith(b"<html") or head.startswith(b"<!doctype"):
        return "html"
    if content_type is not None:
        base = content_type.split(";", 1)[0].strip().lower()
        kind = _CONTENT_TYPE_KINDS.get(base)
        if kind is not None:
            return kind
    if name is not None:
        lowered = name.strip().lower()
        for extension, kind in _EXTENSION_KINDS.items():
            if lowered.endswith(extension):
                return kind
    return None


def extract_pdf_text(data: bytes) -> str:
    """PDF-Text via pypdf, komplett in memory — leer/Whitespace → 422.

    Der 422 faellt VOR jedem Write (Pipeline-Schritt 4): ein PDF ohne
    extrahierbaren Text persistiert NICHTS — weder Blob noch Artifacts.
    """
    try:
        reader = PdfReader(BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # noqa: BLE001 — pypdf wirft eine breite, nicht
        # abschliessend dokumentierte Fehlerpalette (PdfReadError, ValueError,
        # …); jede davon heisst hier dasselbe: kein verwertbares PDF.
        raise _unsupported("PDF nicht lesbar.") from exc
    text = "\n\n".join(page.strip() for page in pages if page.strip()).strip()
    if not text:
        raise _unsupported("PDF ohne extrahierbaren Text (z. B. reiner Scan) — nichts persistiert.")
    return text


def html_to_markdown(html: str) -> str:
    """HTML → Markdown-Rohtext via BeautifulSoup (Pipeline-Schritt 4).

    Sanitisierung vor Extraktion: script/style/noscript/iframe entfallen
    komplett, ``on*``-Event-Handler-Attribute werden gestrippt. Danach werden
    h1–h6 zu ``#``-Headings und p/li zu Absaetzen; p/li innerhalb eines
    ``<li>`` entfallen (der Eltern-Eintrag traegt den Text bereits — keine
    Duplikate bei verschachtelten Listen). Ein Dokument ohne diese Elemente
    faellt auf den nackten Text zurueck. HTML ist nie Quellformat — nur
    dieses abgeleitete Markdown wird ein doc-Artifact.
    """
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(_HTML_STRIP_TAGS):
        element.decompose()
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        for attribute in [name for name in tag.attrs if name.lower().startswith("on")]:
            del tag.attrs[attribute]
    parts: list[str] = []
    for tag in soup.find_all(_HTML_TEXT_TAGS):
        if not isinstance(tag, Tag):
            continue
        if tag.find_parent("li") is not None:
            continue
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        if tag.name.startswith("h"):
            parts.append(f"{'#' * int(tag.name[1])} {text}")
        else:
            parts.append(text)
    if parts:
        return "\n\n".join(parts)
    return soup.get_text(" ", strip=True)


def _decode_utf8(data: bytes, kind: IngestKind) -> str:
    """UTF-8-Dekodierung; Binaermuell hinter Text-Endung/-Content-Type → 422."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _unsupported(f"Inhalt ist kein gueltiges UTF-8 ({kind}).") from exc


def _extract_markdown(data: bytes, kind: IngestKind) -> str:
    """Abgeleiteter Markdown-Text pro Art — komplett in memory, vor jedem Write."""
    if kind == "pdf":
        return extract_pdf_text(data)
    if kind == "html":
        return html_to_markdown(_decode_utf8(data, kind))
    return _decode_utf8(data, kind)


# ------------------------------------------------------------------ Eingang


def _decode_file(file_b64: str, max_bytes: int) -> bytes:
    """Base64-Datei dekodieren — Groessenschaetzung VOR dem Dekodieren.

    4 Base64-Zeichen tragen 3 Bytes; die Schaetzung ``len * 3 / 4`` weist
    einen zu grossen Upload ab, BEVOR die dekodierten Bytes Speicher belegen
    (Padding-Toleranz 2 Bytes zugunsten des Aufrufers). Der exakte Check
    folgt nach dem Dekodieren.
    """
    estimated = (len(file_b64) * 3) // 4
    if estimated > max_bytes + 2:
        raise _too_large(max_bytes)
    try:
        raw = b64decode(file_b64, validate=True)
    except ValueError as exc:
        raise _unsupported("`file_b64` ist kein gueltiges Base64.") from exc
    if len(raw) > max_bytes:
        raise _too_large(max_bytes)
    return raw


def _source_name(data: IngestRequest) -> str | None:
    """Dateiname der Quelle: explizites `filename`, sonst URL-Pfad-Basename."""
    if data.filename:
        return data.filename
    if data.url:
        name = basename(urlsplit(data.url).path)
        return name or None
    return None


def _derive_title(name: str | None, sha256: str) -> str:
    """Artifact-Titel aus dem Quellnamen; Fallback content-addressed."""
    title = (name or "").strip() or f"Ingest {sha256[:8]}"
    return title[:_TITLE_MAX_LENGTH]


# ------------------------------------------------------------------ Service


class WaIngestService:
    """Synchrone Ingest-Pipeline ueber BlobStore + WorkArea-Repos (Spec B)."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        blob_repo: WaBlobRepository,
        area_repo: WorkAreaRepository,
        workspace_repo: WorkspaceRepository | None = None,
    ) -> None:
        self._pool = pool
        self._blobs = blob_repo
        self._areas = area_repo
        self._workspaces = workspace_repo

    def _require_write(self, ctx: WorkspaceContext) -> None:
        """Schreib-Gate: Mensch → Rolle; Agent → Capability + Rate (Plan-Stack)."""
        if is_agent_bound(ctx):
            require_capability(ctx, AgentCapability.workarea_write)
            require_write_rate(ctx)
            return
        require_role(ctx, WorkspaceRole.editor)

    async def _resolve_area(self, ctx: WorkspaceContext, area_id: UUID | None) -> UUID:
        """Ziel-Area: explizit oder die private Area des gebundenen Agenten.

        Der Router hat den Menschen-ohne-Area-Fall bereits mit 422 abgewiesen;
        hier verbleibt der defensive 404-Pfad fuer einen parallel geloeschten
        Agenten (Muster `wa_artifacts.create`).
        """
        if area_id is not None:
            return area_id
        if ctx.agent_id is None:
            raise agent_not_found()
        private = await self._areas.get_or_create_private_area(ctx.workspace_id, ctx.agent_id)
        if private is None:
            raise agent_not_found()
        return private.id

    async def ingest(
        self, ctx: WorkspaceContext, area_id: UUID | None, data: IngestRequest
    ) -> IngestResult:
        """Fuehrt die Pipeline aus (Modul-Docstring); idempotent pro (area, sha256)."""
        self._require_write(ctx)
        target_area = await self._resolve_area(ctx, area_id)
        await ensure_area_access(self._pool, ctx, target_area, WorkAreaGrantLevel.write)

        store = build_blob_store()
        if store is None:
            raise _blobstore_unconfigured()

        max_bytes = get_settings().ingest_max_bytes
        content_type: str | None = None
        fetched_at: datetime | None = None
        if data.url is not None:
            raw, content_type = await fetch_url(data.url, max_bytes, _transport_override)
            fetched_at = datetime.now(UTC)
        else:
            raw = _decode_file(data.file_b64 or "", max_bytes)

        name = _source_name(data)
        kind = detect_kind(raw, content_type, name)
        if kind is None:
            raise _unsupported(
                "Format nicht unterstuetzt — Ingest nimmt PDF, HTML, Markdown und Text an."
            )
        # Extraktion VOR jedem Write: schlaegt sie fehl, ist NICHTS persistiert.
        blocks = split_markdown(_extract_markdown(raw, kind))
        sha256 = hashlib.sha256(raw).hexdigest()

        dedup = await self._blobs.find_dedup(self._pool, ctx.workspace_id, sha256, target_area)
        if dedup is not None:
            return IngestResult(
                blob_artifact_id=dedup.blob_artifact_id,
                doc_artifact_id=dedup.doc_artifact_id,
                sha256=sha256,
                deduplicated=True,
                block_count=dedup.block_count,
            )

        media_type = _MEDIA_TYPES[kind]
        # Blob-PUT VOR der DB-Transaktion (Pipeline-Schritt 6): content-addressed,
        # ein Doppel-PUT ist harmlos; ein PUT ohne Katalog-Zeile ist ein Orphan
        # fuer den Purge-Sweep — nie umgekehrt eine Katalog-Zeile ohne Objekt.
        await store.put(blob_key(ctx.workspace_id, sha256), raw, media_type)

        occurred_at = data.occurred_at or fetched_at or datetime.now(UTC)
        precision = (data.occurred_precision or OccurredPrecision.minute).value
        sensitivity = (data.sensitivity or Sensitivity.general).value
        title = _derive_title(name, sha256)
        actor = ctx.agent_id if ctx.agent_id is not None else ctx.user_id
        locale = await resolve_content_locale(self._workspaces, ctx.workspace_id, None)

        async with self._pool.acquire() as conn, conn.transaction():
            await self._blobs.upsert_blob(
                conn,
                ctx.workspace_id,
                sha256=sha256,
                size_bytes=len(raw),
                media_type=media_type,
                storage_key=blob_key(ctx.workspace_id, sha256),
                source_url=data.url,
                fetched_at=fetched_at,
            )
            blob_artifact_id = await self._blobs.insert_blob_artifact(
                conn,
                ctx.workspace_id,
                target_area,
                title=title,
                occurred_at=occurred_at,
                occurred_precision=precision,
                sensitivity=sensitivity,
                sha256=sha256,
                source_url=data.url,
                fetched_at=fetched_at,
                updated_by=actor,
            )
            doc_artifact_id = await self._blobs.insert_doc_artifact(
                conn,
                ctx.workspace_id,
                target_area,
                title=title,
                occurred_at=occurred_at,
                occurred_precision=precision,
                sensitivity=sensitivity,
                blob_sha256=sha256,
                source_url=data.url,
                fetched_at=fetched_at,
                blocks=blocks,
                updated_by=actor,
            )
            await sync_artifact_chunks(
                conn,
                workspace_id=ctx.workspace_id,
                artifact_id=doc_artifact_id,
                area_id=target_area,
                blocks=blocks,
                locale=locale,
            )
        return IngestResult(
            blob_artifact_id=blob_artifact_id,
            doc_artifact_id=doc_artifact_id,
            sha256=sha256,
            deduplicated=False,
            block_count=len(blocks),
        )
