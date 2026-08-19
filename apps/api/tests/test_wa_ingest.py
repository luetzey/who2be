"""Tests fuer die WorkArea-Ingest-Pipeline (ADR-0048, WP5 — Spec B).

Zwei Ebenen:

- **SSRF-Unit-Tests** (DB-los): `ensure_url_allowed` blockt loopback/private/
  link-local/Metadaten-Adressen, fremde Schemata, DNS-auf-privat (monkeypatch)
  und nicht aufloesbare Hosts; `fetch_url` prueft jeden Redirect-Hop erneut,
  deckelt Redirects und streamt mit Byte-Cap — ausschliesslich
  `httpx.MockTransport`, KEIN echtes Netz.
- **Integrationstests** (echte DB): PDF-Roundtrip inkl. Blob im Memory-Store
  und Chunks; PDF ohne Text → 422 OHNE Teilzustand; HTML-Sanitisierung;
  Dedup (zweiter Ingest → 200, ein `wa_blob`, kein neues Objekt); 413; 422
  fuer unbekannte Formate; 503 ohne BlobStore; fremde Area ohne Grant → 404.

Der BlobStore wird ueber `set_blob_store` (Memory-Adapter) injiziert, der
HTTP-Transport ueber `set_ingest_transport` (MockTransport).
"""

import asyncio
import base64
import socket
from collections.abc import Callable, Iterator
from io import BytesIO
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from who2be_api.blobstore import blob_key, reset_blob_store, set_blob_store, workspace_prefix
from who2be_api.blobstore.adapters.memory import MemoryBlobStore
from who2be_api.core.errors import ApiGateError
from who2be_api.main import app
from who2be_api.services import wa_ingest as wa_ingest_module
from who2be_api.services.wa_ingest import (
    detect_kind,
    ensure_url_allowed,
    fetch_url,
    reset_ingest_transport,
    set_ingest_transport,
)
from who2be_api.testing.api_helpers import agent_token, shared_area
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

# Oeffentliche Literal-IP (example.com) — loest ohne DNS auf und passiert den
# SSRF-Guard; der MockTransport faengt jeden tatsaechlichen Request ab.
_PUBLIC_IP = "93.184.216.34"


def _mini_pdf(text: str) -> bytes:
    """Baut ein minimales, valides Ein-Seiten-PDF mit `text` im Content-Stream.

    Handgebaut mit korrekt berechneter xref (pypdf hat keine public
    Text-Zeichen-API); dass pypdf den Text extrahieren kann, verifiziert
    `test_mini_pdf_ist_pypdf_lesbar` als Selbsttest der Testbasis.
    """
    content = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 144] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (index, body)
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_at,
    )
    return bytes(out)


def _empty_pdf() -> bytes:
    """Mini-PDF via pypdf: eine leere Seite, kein extrahierbarer Text."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_mini_pdf_ist_pypdf_lesbar() -> None:
    """Selbsttest der Testbasis: pypdf extrahiert den Text des Mini-PDFs."""
    reader = PdfReader(BytesIO(_mini_pdf("Miete August 2026")))
    assert "Miete August 2026" in (reader.pages[0].extract_text() or "")


# --- SSRF-Guard (Unit, DB-los) ------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/geheim",
        "http://10.0.0.1/intern",
        "http://[::1]/geheim",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
def test_ssrf_blockt_interne_literal_adressen(url: str) -> None:
    with pytest.raises(ApiGateError) as excinfo:
        ensure_url_allowed(url)
    assert excinfo.value.reason == "url_forbidden"
    assert excinfo.value.status == 403


@pytest.mark.parametrize("url", ["ftp://example.com/f", "file:///etc/passwd", "gopher://x/"])
def test_ssrf_blockt_fremde_schemata(url: str) -> None:
    with pytest.raises(ApiGateError) as excinfo:
        ensure_url_allowed(url)
    assert excinfo.value.reason == "url_forbidden"


def test_ssrf_blockt_dns_auf_privat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hostname loest auf eine private IP auf → 403 (DNS-Ebene des Guards)."""

    def fake_getaddrinfo(*args: Any, **kwargs: Any) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 80))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ApiGateError) as excinfo:
        ensure_url_allowed("http://intern.example/report")
    assert excinfo.value.reason == "url_forbidden"


def test_ssrf_blockt_wenn_eine_von_mehreren_ips_privat_ist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JEDE aufgeloeste IP wird geprueft — eine private reicht zum Block."""

    def fake_getaddrinfo(*args: Any, **kwargs: Any) -> list[Any]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (_PUBLIC_IP, 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 80)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ApiGateError):
        ensure_url_allowed("http://zweigleisig.example/")


def test_ssrf_erlaubt_oeffentliche_adresse(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(*args: Any, **kwargs: Any) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (_PUBLIC_IP, 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    ensure_url_allowed("https://example.com/bericht.pdf")  # darf NICHT werfen


def test_ssrf_blockt_nicht_aufloesbare_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(*args: Any, **kwargs: Any) -> list[Any]:
        raise socket.gaierror("kein DNS")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(ApiGateError) as excinfo:
        ensure_url_allowed("http://gibtsnich.invalid/")
    assert excinfo.value.reason == "url_forbidden"


def test_fetch_url_blockt_redirect_auf_privat() -> None:
    """Jeder Redirect-Hop laeuft erneut durch den Guard (Pipeline-Schritt 2)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/geheim"})

    transport = httpx.MockTransport(handler)
    with pytest.raises(ApiGateError) as excinfo:
        asyncio.run(fetch_url(f"http://{_PUBLIC_IP}/start", 1024, transport))
    assert excinfo.value.reason == "url_forbidden"


def test_fetch_url_deckelt_redirect_kette() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": f"http://{_PUBLIC_IP}/weiter"})

    transport = httpx.MockTransport(handler)
    with pytest.raises(ApiGateError) as excinfo:
        asyncio.run(fetch_url(f"http://{_PUBLIC_IP}/start", 1024, transport))
    assert excinfo.value.reason == "url_forbidden"
    assert "Redirect" in excinfo.value.detail


def test_fetch_url_streaming_byte_cap() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 2048)

    transport = httpx.MockTransport(handler)
    with pytest.raises(ApiGateError) as excinfo:
        asyncio.run(fetch_url(f"http://{_PUBLIC_IP}/gross", 1024, transport))
    assert excinfo.value.reason == "ingest_too_large"
    assert excinfo.value.status == 413


# --- Typ-Erkennung (Unit) -----------------------------------------------------


def test_detect_kind_magic_schlaegt_content_type() -> None:
    # Ein als text/plain ausgeliefertes PDF bleibt ein PDF.
    assert detect_kind(b"%PDF-1.7 ...", "text/plain", "notiz.txt") == "pdf"
    assert detect_kind(b"  <!DOCTYPE html><html>", None, None) == "html"


def test_detect_kind_content_type_und_endung() -> None:
    assert detect_kind(b"# Titel", "text/markdown; charset=utf-8", None) == "markdown"
    assert detect_kind(b"hallo", None, "notizen.TXT") == "text"
    assert detect_kind(b"\x00\x01\x02", "application/octet-stream", "daten.bin") is None


# --- Integrations-Aufbau ------------------------------------------------------


@pytest.fixture
def memory_store() -> Iterator[MemoryBlobStore]:
    """Injiziert den Memory-Adapter als BlobStore (Muster `set_blob_store`)."""
    store = MemoryBlobStore()
    set_blob_store(store)
    yield store
    reset_blob_store()


@pytest.fixture
def mock_transport() -> Iterator[None]:
    """Raeumt einen per `set_ingest_transport` gesetzten MockTransport ab."""
    yield
    reset_ingest_transport()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _ingest(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    area_id: str | None,
    **body: Any,
) -> Any:
    url = f"{prefix}/ingest" if area_id is None else f"{prefix}/work-areas/{area_id}/ingest"
    return client.post(url, json=body, headers=headers)


def _workspace_counts(workspace_id: UUID) -> tuple[int, int, int]:
    """(wa_blob, wa_artifact, wa_chunk)-Zeilen des Workspace — Teilzustands-Check."""
    import asyncpg

    from who2be_api.core.config import get_settings

    async def _run() -> tuple[int, int, int]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            blobs = await conn.fetchval(
                "SELECT count(*) FROM wa_blob WHERE workspace_id = $1", workspace_id
            )
            artifacts = await conn.fetchval(
                "SELECT count(*) FROM wa_artifact WHERE workspace_id = $1", workspace_id
            )
            chunks = await conn.fetchval(
                "SELECT count(*) FROM wa_chunk WHERE workspace_id = $1", workspace_id
            )
            return int(blobs), int(artifacts), int(chunks)
        finally:
            await conn.close()

    return asyncio.run(_run())


# --- Integration: Pipeline ----------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_pdf_ingest_roundtrip(
    make_auth_headers: AuthFactory, memory_store: MemoryBlobStore
) -> None:
    """PDF-Upload: Blob im Store unter `blobs/{ws}/{sha}`, wa_blob-Zeile,
    blob- + doc-Artifact mit Provenance, Chunks — und der Text ist lesbar."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    pdf = _mini_pdf("Zahlung Miete August 2026")
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Ingest-Roundtrip")
            res = _ingest(
                client,
                prefix,
                auth,
                area_id,
                file_b64=_b64(pdf),
                filename="miete-august.pdf",
                occurred_at="2026-08-01T12:00:00Z",
                sensitivity="sensitive",
            )
            assert res.status_code == 201, res.text
            result = res.json()
            assert result["deduplicated"] is False
            assert result["block_count"] >= 1

            # Blob liegt content-addressed im Store, Media-Type kanonisch.
            key = blob_key(ws, result["sha256"])
            assert asyncio.run(memory_store.get(key)) == pdf
            assert memory_store.media_type(key) == "application/pdf"

            # Genau EINE wa_blob-Zeile, zwei Artifacts (blob + doc), Chunks da.
            blobs, artifacts, chunks = _workspace_counts(ws)
            assert (blobs, artifacts) == (1, 2)
            assert chunks >= 1

            # Der abgeleitete Text ist als doc-Artifact lesbar.
            read = client.get(f"{prefix}/wa-artifacts/{result['doc_artifact_id']}", headers=auth)
            assert read.status_code == 200, read.text
            assert "Zahlung Miete August 2026" in read.json()["markdown"]

            # Metadaten: doc traegt blob_sha256 + sensitivity, blob den content_ref.
            listed = {
                a["type"]: a
                for a in client.get(f"{prefix}/work-areas/{area_id}/artifacts", headers=auth).json()
            }
            assert listed["doc"]["blob_sha256"] == result["sha256"]
            assert listed["doc"]["sensitivity"] == "sensitive"
            assert listed["doc"]["title"] == "miete-august.pdf"
            assert listed["blob"]["content_ref"] == result["sha256"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_pdf_ohne_text_persistiert_nichts(
    make_auth_headers: AuthFactory, memory_store: MemoryBlobStore
) -> None:
    """Spec-Akzeptanz: PDF ohne extrahierbaren Text → 422 und NICHTS im
    System — keine DB-Zeile, kein Objekt im Store (kein Teilzustand)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Leeres-PDF")
            before = _workspace_counts(ws)
            res = _ingest(client, prefix, auth, area_id, file_b64=_b64(_empty_pdf()))
            assert res.status_code == 422, res.text
            assert res.json()["reason"] == "ingest_unsupported"
            assert _workspace_counts(ws) == before
            assert asyncio.run(memory_store.list_keys(workspace_prefix(ws))) == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "memory_store")
def test_html_wird_sanitisiert(make_auth_headers: AuthFactory) -> None:
    """Script/Style/Handler fliegen raus; h1–h6 → `#`-Headings, p/li → Absaetze."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    html = (
        "<html><head><style>body{color:red}</style>"
        "<script>alert('boese')</script></head>"
        "<body><h1 onclick=\"alert('klick')\">Quartalsbericht</h1>"
        "<p>Umsatz stabil.</p><ul><li>Punkt eins</li><li>Punkt zwei</li></ul>"
        "<noscript>kein JS</noscript><iframe src='http://x'></iframe></body></html>"
    )
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "HTML-Sanitisierung")
            res = _ingest(client, prefix, auth, area_id, file_b64=_b64(html.encode()))
            assert res.status_code == 201, res.text
            doc_id = res.json()["doc_artifact_id"]
            read = client.get(f"{prefix}/wa-artifacts/{doc_id}", headers=auth)
            markdown = read.json()["markdown"]
            assert "# Quartalsbericht" in markdown
            assert "Umsatz stabil." in markdown
            assert "Punkt eins" in markdown
            for verboten in ("alert", "boese", "klick", "color:red", "kein JS", "iframe"):
                assert verboten not in markdown
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "memory_store")
def test_text_ingest(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Text-Ingest")
            res = _ingest(
                client,
                prefix,
                auth,
                area_id,
                file_b64=_b64(b"# Notiz\n\nEin Absatz."),
                filename="notiz.md",
            )
            assert res.status_code == 201, res.text
            assert res.json()["block_count"] == 2
            doc_id = res.json()["doc_artifact_id"]
            read = client.get(f"{prefix}/wa-artifacts/{doc_id}", headers=auth)
            assert "# Notiz" in read.json()["markdown"]
            assert "Ein Absatz." in read.json()["markdown"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_dedup_zweiter_ingest_idempotent(
    make_auth_headers: AuthFactory, memory_store: MemoryBlobStore
) -> None:
    """Gleicher Inhalt in dieselbe Area: 200, identische IDs, EIN wa_blob,
    EIN Objekt im Store, keine neuen Artifacts."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    pdf = _mini_pdf("Dedup-Beleg")
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Dedup")
            first = _ingest(client, prefix, auth, area_id, file_b64=_b64(pdf))
            assert first.status_code == 201, first.text
            counts_after_first = _workspace_counts(ws)

            second = _ingest(client, prefix, auth, area_id, file_b64=_b64(pdf))
            assert second.status_code == 200, second.text
            assert second.json()["deduplicated"] is True
            assert second.json()["doc_artifact_id"] == first.json()["doc_artifact_id"]
            assert second.json()["blob_artifact_id"] == first.json()["blob_artifact_id"]
            assert second.json()["block_count"] == first.json()["block_count"]

            assert _workspace_counts(ws) == counts_after_first
            assert _workspace_counts(ws)[0] == 1  # genau EINE wa_blob-Zeile
            assert len(asyncio.run(memory_store.list_keys(workspace_prefix(ws)))) == 1
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "memory_store", "mock_transport")
def test_url_ingest_mit_provenance_und_ssrf_redirect(make_auth_headers: AuthFactory) -> None:
    """URL-Modus via MockTransport: HTML wird geladen + sanitisiert, das
    doc-Artifact traegt source_url/fetched_at; ein Redirect auf eine private
    Adresse bricht mit 403 `url_forbidden` ab (kein Write)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    page = b"<html><body><h1>Marktanalyse</h1><p>Nachfrage steigt.</p></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bericht.html":
            return httpx.Response(
                200, headers={"content-type": "text/html; charset=utf-8"}, content=page
            )
        if request.url.path == "/umleitung":
            return httpx.Response(302, headers={"location": "http://10.0.0.1/intern"})
        return httpx.Response(404)

    set_ingest_transport(httpx.MockTransport(handler))
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "URL-Ingest")
            res = _ingest(client, prefix, auth, area_id, url=f"http://{_PUBLIC_IP}/bericht.html")
            assert res.status_code == 201, res.text
            doc_id = res.json()["doc_artifact_id"]
            read = client.get(f"{prefix}/wa-artifacts/{doc_id}", headers=auth)
            assert "# Marktanalyse" in read.json()["markdown"]
            listed = {
                a["id"]: a
                for a in client.get(f"{prefix}/work-areas/{area_id}/artifacts", headers=auth).json()
            }
            assert listed[doc_id]["source_url"] == f"http://{_PUBLIC_IP}/bericht.html"
            assert listed[doc_id]["fetched_at"] is not None
            assert listed[doc_id]["title"] == "bericht.html"

            before = _workspace_counts(ws)
            blocked = _ingest(client, prefix, auth, area_id, url=f"http://{_PUBLIC_IP}/umleitung")
            assert blocked.status_code == 403, blocked.text
            assert blocked.json()["reason"] == "url_forbidden"
            assert _workspace_counts(ws) == before
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "memory_store")
def test_zu_grosse_datei_413(
    make_auth_headers: AuthFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Base64-Schaetzung VOR dem Dekodieren: ueber dem Limit → 413, kein Write."""
    from who2be_api.core.config import Settings

    monkeypatch.setattr(
        wa_ingest_module,
        "get_settings",
        lambda: Settings(_env_file=None, ingest_max_bytes=64),  # type: ignore[call-arg]
    )
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Zu-gross")
            res = _ingest(
                client, prefix, auth, area_id, file_b64=_b64(b"x" * 512), filename="gross.txt"
            )
            assert res.status_code == 413, res.text
            assert res.json()["reason"] == "ingest_too_large"
            assert _workspace_counts(ws) == (0, 0, 0)
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_unbekanntes_format_422(
    make_auth_headers: AuthFactory, memory_store: MemoryBlobStore
) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Unbekannt")
            res = _ingest(
                client,
                prefix,
                auth,
                area_id,
                file_b64=_b64(b"\x00\x01\x02\x03binaer"),
                filename="daten.bin",
            )
            assert res.status_code == 422, res.text
            assert res.json()["reason"] == "ingest_unsupported"
            assert _workspace_counts(ws) == (0, 0, 0)
            assert asyncio.run(memory_store.list_keys(workspace_prefix(ws))) == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_ohne_blobstore_503(make_auth_headers: AuthFactory) -> None:
    """`build_blob_store` → None ⇒ 503 `blobstore_unconfigured` (Fail-soft-Pfad)."""
    set_blob_store(None)
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Ohne-Store")
            res = _ingest(client, prefix, auth, area_id, file_b64=_b64(b"nur text"))
            assert res.status_code == 503, res.text
            assert res.json()["reason"] == "blobstore_unconfigured"
    finally:
        reset_blob_store()
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "memory_store")
def test_gates_area_capability_und_private_area(make_auth_headers: AuthFactory) -> None:
    """Agent ohne Grant auf fremde Area → 404 (kein Existenz-Leak); Agent ohne
    `workarea_write` → 403; Agent MIT Capability ingestiert in seine private
    Area (POST /ingest); Mensch ohne Area → 422 (keine private Area)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    payload = _b64(b"Agenten-Notiz.")
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Gate-Area")

            # Ohne Grant: die Area ist fuer den Agenten unsichtbar → 404.
            _, no_grant = agent_token(client, prefix, "ing-nogrant", {"workarea_write": True}, auth)
            blocked = _ingest(client, prefix, no_grant, area_id, file_b64=payload, filename="n.txt")
            assert blocked.status_code == 404, blocked.text

            # Ohne Capability: 403 `missing_capability` — vor jedem Area-Check.
            _, no_cap = agent_token(client, prefix, "ing-nocap", {}, auth)
            forbidden = _ingest(client, prefix, no_cap, None, file_b64=payload, filename="n.txt")
            assert forbidden.status_code == 403, forbidden.text
            assert forbidden.json()["reason"] == "missing_capability"

            # Mit Capability, ohne Area: private Area (Auto-Anlage) + Ingest.
            _, agent_tok = agent_token(client, prefix, "ing-agent", {"workarea_write": True}, auth)
            private = _ingest(client, prefix, agent_tok, None, file_b64=payload, filename="n.txt")
            assert private.status_code == 201, private.text
            doc_id = private.json()["doc_artifact_id"]
            assert (
                client.get(f"{prefix}/wa-artifacts/{doc_id}", headers=agent_tok).status_code == 200
            )

            # Mensch ohne area_id: 422 — Menschen haben keine private Area.
            human = _ingest(client, prefix, auth, None, file_b64=payload, filename="n.txt")
            assert human.status_code == 422, human.text
    finally:
        cleanup_workspaces([owner])
