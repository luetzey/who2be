"""Regressionstests zu den Security-Review-Findings 2026-08-13 (Wellen 1–2).

Je Finding mindestens ein reproduzierender Fall (ADR-0047 Nachtrag):

- **H1**: viewer-Agent-Token schreibt trotz Capabilities NIRGENDS
  (Rollen-Gate vor Capability, Muster `resource_service.create`).
- **H2**: Nodes area-beschraenkter Aufrufer mit rein externem Beleg erben
  die private Area des Agenten — kein workspace-weiter Exfiltrationskanal.
- **H3**: Ingest deckelt extrahierten Text und Blockzahl (413, nichts
  persistiert).
- **M2**: SSRF-Guard blockt Nicht-Standard-Ports und CGNAT (100.64.0.0/10).
- **M5**: Agenten aendern nur eigene Nodes; `verified` bleibt Menschen
  vorbehalten.
- **M6**: Evidence-Listen sind pro Seite gedeckelt (Modell-422).
- **M7**: Appends respektieren das kumulative Block-Limit atomar.
- **L2**: `sha256:`-Anker ist kein workspace-weites Existenz-Orakel.
- **L5**: `artifact:`-Praefix und kanonische Form finden dieselbe Kante.
"""

import socket
from collections.abc import Callable, Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import who2be_api.repositories.wa_artifact_repository as wa_artifact_repo_module
import who2be_api.services.wa_ingest as wa_ingest_module
from who2be_api.blobstore import reset_blob_store, set_blob_store
from who2be_api.blobstore.adapters.memory import MemoryBlobStore
from who2be_api.core.errors import ApiGateError
from who2be_api.main import app
from who2be_api.services.wa_ingest import ensure_url_allowed
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval, grant, shared_area
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

_ALL_WRITE_POLICY: dict[str, object] = {
    "workarea_write": True,
    "kb_write": True,
    "kb_edge_write": True,
}


def _artifact(
    client: TestClient, prefix: str, auth: dict[str, str], area_id: str, content_md: str
) -> tuple[str, str]:
    created = client.post(
        f"{prefix}/work-areas/{area_id}/artifacts",
        json={"title": "Beleg", "content_md": content_md, "occurred_at": "2026-08-01T12:00:00Z"},
        headers=auth,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    return body["id"], body["blocks"][0]["block_id"]


def _node_body(source_ref: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "content": "Kunde Alpha bevorzugt Textilfarbe Indigo.",
        "tier": "hypothesis",
        "source_ref": source_ref,
        "occurred_at": "2026-08-01T00:00:00Z",
    }
    body.update(overrides)
    return body


@pytest.fixture
def memory_store() -> Iterator[MemoryBlobStore]:
    store = MemoryBlobStore()
    set_blob_store(store)
    yield store
    reset_blob_store()


# --------------------------------------------------------------------- H1


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_h1_viewer_agent_token_cannot_write(make_auth_headers: AuthFactory) -> None:
    """Rollen-Gate vor Capability: ein viewer-Token schreibt nie (H1/L1)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, viewer_headers = agent_token(
                client, prefix, "leser", _ALL_WRITE_POLICY, auth, role="viewer"
            )
            artifact = client.post(
                f"{prefix}/artifacts",
                json={
                    "title": "x",
                    "content_md": "x",
                    "occurred_at": "2026-08-01T00:00:00Z",
                },
                headers=viewer_headers,
            )
            assert artifact.status_code == 403, artifact.text
            assert artifact.json()["reason"] == "insufficient_role"
            area = client.post(
                f"{prefix}/work-areas", json={"name": "leak"}, headers=viewer_headers
            )
            assert area.status_code == 403
            node = client.post(
                f"{prefix}/kb/nodes",
                json=_node_body("url:https://example.com"),
                headers=viewer_headers,
            )
            assert node.status_code == 403
            ingest = client.post(
                f"{prefix}/ingest", json={"file_b64": "aGFsbG8="}, headers=viewer_headers
            )
            assert ingest.status_code == 403
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- H2


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_h2_external_source_node_inherits_private_area(make_auth_headers: AuthFactory) -> None:
    """Agent-Node mit url:-Beleg ist NICHT workspace-weit sichtbar (H2)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, a_headers = agent_token(client, prefix, "autor", _ALL_WRITE_POLICY, auth)
            _, b_headers = agent_token(client, prefix, "fremd", _ALL_WRITE_POLICY, auth)
            created = client.post(
                f"{prefix}/kb/nodes",
                json=_node_body("url:https://example.com", content="Geheimnis aus P"),
                headers=a_headers,
            )
            assert created.status_code == 201, created.text
            node_id = created.json()["id"]
            source_areas = db_fetchval(
                "SELECT count(*) FROM kb_node_source_area WHERE node_id = $1", UUID(node_id)
            )
            assert int(source_areas) == 1  # private Area des Autors materialisiert
            assert client.get(f"{prefix}/kb/nodes/{node_id}", headers=a_headers).status_code == 200
            assert client.get(f"{prefix}/kb/nodes/{node_id}", headers=b_headers).status_code == 404
            hits = client.get(f"{prefix}/kb-search", params={"q": "Geheimnis"}, headers=b_headers)
            assert hits.status_code == 200
            assert hits.json() == []
            # Kontrast: ein MENSCHLICHER kuratierter Node ohne Quell-Area
            # bleibt workspace-weit lesbar (auch fuer Agenten).
            human_node = client.post(
                f"{prefix}/kb/nodes",
                json=_node_body("url:https://example.com", content="Kuratiert"),
                headers=auth,
            )
            assert human_node.status_code == 201
            visible = client.get(f"{prefix}/kb/nodes/{human_node.json()['id']}", headers=b_headers)
            assert visible.status_code == 200
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- H3


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db", "memory_store")
def test_h3_ingest_caps_content_and_blocks(
    make_auth_headers: AuthFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Extrahierter Text und Blockzahl sind gedeckelt — 413, nichts persistiert."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            import base64

            # Menschen ingestieren mit expliziter Area (der area-lose Pfad ist
            # agent-gebundenen Tokens vorbehalten).
            area = shared_area(client, prefix, auth, "Eingang")
            monkeypatch.setattr(wa_ingest_module, "ARTIFACT_CONTENT_MAX_LENGTH", 100)
            payload = base64.b64encode(b"x" * 200).decode()
            too_long = client.post(
                f"{prefix}/work-areas/{area}/ingest",
                json={"file_b64": payload, "filename": "notiz.txt"},
                headers=auth,
            )
            assert too_long.status_code == 413, too_long.text
            assert too_long.json()["reason"] == "ingest_too_large"

            monkeypatch.setattr(wa_ingest_module, "ARTIFACT_CONTENT_MAX_LENGTH", 500_000)
            monkeypatch.setattr(wa_ingest_module, "INGEST_MAX_BLOCKS", 2)
            many_blocks = base64.b64encode(b"a\n\nb\n\nc\n\nd").decode()
            too_many = client.post(
                f"{prefix}/work-areas/{area}/ingest",
                json={"file_b64": many_blocks, "filename": "notiz.txt"},
                headers=auth,
            )
            assert too_many.status_code == 413, too_many.text
            count = db_fetchval("SELECT count(*) FROM wa_artifact WHERE workspace_id = $1", ws)
            assert int(count) == 0  # kein Teilzustand
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- M2


def test_m2_ssrf_blocks_nonstandard_port() -> None:
    with pytest.raises(ApiGateError) as err:
        ensure_url_allowed("http://example.com:8080/report.pdf")
    assert err.value.reason == "url_forbidden"


def test_m2_ssrf_blocks_cgnat(monkeypatch: pytest.MonkeyPatch) -> None:
    """100.64.0.0/10 (CGNAT/Tailscale) ist nicht global → verboten."""

    def _fake_getaddrinfo(*_args: object, **_kwargs: object) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.64.1.1", 80))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    with pytest.raises(ApiGateError) as err:
        ensure_url_allowed("http://intern.example.com/report.pdf")
    assert err.value.reason == "url_forbidden"


# --------------------------------------------------------------------- M5


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_m5_node_updates_require_ownership(make_auth_headers: AuthFactory) -> None:
    """Sichtbarkeit ist keine Schreib-Erlaubnis: fremde/verified Nodes → 403."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            shared = shared_area(client, prefix, auth, "Team")
            a_id, a_headers = agent_token(client, prefix, "autor", _ALL_WRITE_POLICY, auth)
            b_id, b_headers = agent_token(client, prefix, "fremd", _ALL_WRITE_POLICY, auth)
            grant(client, prefix, auth, shared, a_id, "write")
            grant(client, prefix, auth, shared, b_id, "read")
            artifact_id, block_id = _artifact(client, prefix, auth, shared, "Team-Notiz Indigo")
            created = client.post(
                f"{prefix}/kb/nodes",
                json=_node_body(f"{artifact_id}#{block_id}"),
                headers=a_headers,
            )
            assert created.status_code == 201, created.text
            node_id = created.json()["id"]
            # Fremder Agent SIEHT den Node (Grant auf die Area) …
            assert client.get(f"{prefix}/kb/nodes/{node_id}", headers=b_headers).status_code == 200
            # … darf ihn aber nicht umschreiben.
            foreign = client.patch(
                f"{prefix}/kb/nodes/{node_id}", json={"content": "verfaelscht"}, headers=b_headers
            )
            assert foreign.status_code == 403, foreign.text
            assert foreign.json()["reason"] == "area_forbidden"
            own = client.patch(
                f"{prefix}/kb/nodes/{node_id}", json={"content": "praezisiert"}, headers=a_headers
            )
            assert own.status_code == 200, own.text
            # `verified` aendert auch der Ersteller-Agent nicht.
            verified = client.post(
                f"{prefix}/kb/nodes",
                json=_node_body(f"{artifact_id}#{block_id}", tier="verified"),
                headers=a_headers,
            )
            assert verified.status_code == 201
            locked = client.patch(
                f"{prefix}/kb/nodes/{verified.json()['id']}",
                json={"content": "umgeschrieben"},
                headers=a_headers,
            )
            assert locked.status_code == 403
            # Mensch (editor) bleibt frei.
            human = client.patch(
                f"{prefix}/kb/nodes/{node_id}", json={"content": "kuratiert"}, headers=auth
            )
            assert human.status_code == 200, human.text
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- M6


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_m6_evidence_list_is_capped(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            res = client.post(
                f"{prefix}/kb/edges",
                json={
                    "from_anchor": f"node:{UUID(int=1)}",
                    "to_anchor": f"node:{UUID(int=2)}",
                    "type": "supports",
                    "evidence_from": [f"url:https://example.com/{i}" for i in range(21)],
                    "evidence_to": ["url:https://example.com/x"],
                },
                headers=auth,
            )
            assert res.status_code == 422  # Pydantic max_length, vor jeder Aufloesung
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- M7


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_m7_append_respects_cumulative_block_cap(
    make_auth_headers: AuthFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            monkeypatch.setattr(wa_artifact_repo_module, "INGEST_MAX_BLOCKS", 3)
            shared = shared_area(client, prefix, auth, "Log")
            artifact_id, _ = _artifact(client, prefix, auth, shared, "eins\n\nzwei")
            rejected = client.post(
                f"{prefix}/wa-artifacts/{artifact_id}/append",
                json={"content_md": "drei\n\nvier"},
                headers=auth,
            )
            assert rejected.status_code == 413, rejected.text
            assert rejected.json()["reason"] == "ingest_too_large"
            unchanged = client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=auth)
            assert unchanged.json()["rev"] == 1
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- L2


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_l2_sha256_anchor_is_scoped(make_auth_headers: AuthFactory) -> None:
    """Der Blob-Anker verraet area-beschraenkten Aufrufern keine fremden Inhalte."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    digest = "ab" * 32
    try:
        with TestClient(app) as client:
            shared = shared_area(client, prefix, auth, "Quellen")
            db_execute(
                "INSERT INTO wa_blob (workspace_id, sha256, size_bytes, media_type, storage_key) "
                "VALUES ($1, $2, 5, 'text/plain', $3)",
                ws,
                digest,
                f"blobs/{ws}/{digest}",
            )
            db_execute(
                "INSERT INTO wa_artifact (workspace_id, area_id, type, title, occurred_at, "
                "occurred_precision, content_ref) "
                "VALUES ($1, $2::uuid, 'blob', 'Quelle', now(), 'minute', $3)",
                ws,
                shared,
                digest,
            )
            agent_id, agent_headers = agent_token(
                client, prefix, "analyst", _ALL_WRITE_POLICY, auth
            )
            blocked = client.post(
                f"{prefix}/kb/nodes",
                json=_node_body(f"sha256:{digest}"),
                headers=agent_headers,
            )
            assert blocked.status_code == 422, blocked.text
            assert blocked.json()["reason"] == "anchor_unresolvable"
            grant(client, prefix, auth, shared, agent_id, "read")
            allowed = client.post(
                f"{prefix}/kb/nodes",
                json=_node_body(f"sha256:{digest}"),
                headers=agent_headers,
            )
            assert allowed.status_code == 201, allowed.text
    finally:
        cleanup_workspaces([owner])


# --------------------------------------------------------------------- L5


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_l5_prefixed_and_bare_anchor_find_same_edge(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            shared = shared_area(client, prefix, auth, "Wissen")
            artifact_id, block_id = _artifact(client, prefix, auth, shared, "Indigo-Beleg")
            node = client.post(
                f"{prefix}/kb/nodes",
                json=_node_body(f"{artifact_id}#{block_id}"),
                headers=auth,
            )
            assert node.status_code == 201
            node_id = node.json()["id"]
            edge = client.post(
                f"{prefix}/kb/edges",
                json={
                    # BEWUSST die praefigierte Schreibweise — gespeichert wird
                    # die kanonische Form (L5).
                    "from_anchor": f"artifact:{artifact_id}#{block_id}",
                    "to_anchor": f"node:{node_id}",
                    "type": "supports",
                    "evidence_from": [f"{artifact_id}#{block_id}"],
                    "evidence_to": [f"{artifact_id}#{block_id}"],
                },
                headers=auth,
            )
            assert edge.status_code == 201, edge.text
            stored = db_fetchval(
                "SELECT from_anchor FROM kb_edge WHERE id = $1", UUID(edge.json()["id"])
            )
            assert stored == f"{artifact_id}#{block_id}"  # ohne Praefix
            neighbors = client.get(
                f"{prefix}/kb/neighbors",
                params={"anchor": f"{artifact_id}#{block_id}"},
                headers=auth,
            )
            assert neighbors.status_code == 200, neighbors.text
            found = [n["node"]["id"] for n in neighbors.json()]
            assert node_id in found
    finally:
        cleanup_workspaces([owner])
