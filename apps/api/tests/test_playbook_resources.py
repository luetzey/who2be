"""Integrationstest fuer Playbook->Resource-Block-Refs (Phase 2.2).

Pfad `/v1/workspaces/{ws}/playbooks/{id}/resource_links`. Deckt ab:
Set-Replace-Semantik, `available`/`preview`-Aufloesung gegen die aktive
Resource-Version, das "Block geloescht"-Verhalten nach einer neuen Version
ohne den Block, und Cross-Workspace-Isolation. Skippt ohne erreichbare DB.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _prepare_db() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


def _auth(owner_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _block(block_id: str, text: str, block_type: str = "paragraph") -> dict[str, object]:
    return {
        "id": block_id,
        "type": block_type,
        "props": {},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _heading(block_id: str, text: str, level: int = 1) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {"level": level},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _resource_body(name: str, blocks: list[dict[str, object]]) -> dict[str, object]:
    # Welle 4: Promote-Validator verlangt nicht-leere description fuer
    # draft -> review/active. blocks kommt schon vom Caller; description
    # bekommt eine harmlose, eindeutige Vorgabe.
    return {"name": name, "content": {"description": f"resource {name}", "blocks": blocks}}


def _playbook_body(name: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "body": "1. Step.",
            "type": "workflow",
            "tags": [],
            "triggers": None,
        },
    }


def _activate(
    client: TestClient, base: str, entity_id: str, version: int, auth: dict[str, str]
) -> None:
    """Hebt eine Version auf `active`. Ueberspringt Schritte, deren Status die
    Version bereits hat (z.B. ist eine Draft-on-Edit-Version schon `draft`)."""
    versions = client.get(f"{base}/{entity_id}/versions", headers=auth).json()
    current = next((v["status"] for v in versions if v["version"] == version), None)
    steps = ["draft", "review", "active"]
    start = steps.index(current) + 1 if current in steps else 0
    for to in steps[start:]:
        resp = client.post(
            f"{base}/{entity_id}/versions/{version}/transition", json={"to": to}, headers=auth
        )
        assert resp.status_code == 200, resp.text


@pytest.mark.integration
def test_resource_links_set_replace_and_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            rid = client.post(
                rbase,
                json=_resource_body(
                    "Doc",
                    [
                        _heading("h1", "Erster Block"),
                        _block("p1", "Paragraph zu h1"),
                        _heading("h2", "Zweiter"),
                        _block("p2", "Paragraph zu h2"),
                    ],
                ),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)

            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"

            # Leerer Stand.
            assert client.get(links_url, headers=auth).json() == []

            # Set: zwei Heading-Anker verlinken.
            resp = client.put(
                links_url,
                json={
                    "links": [
                        {"resource_id": rid, "block_id": "h1", "position": 0},
                        {"resource_id": rid, "block_id": "h2", "position": 1},
                    ]
                },
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert [link["block_id"] for link in body] == ["h1", "h2"]
            assert all(link["available"] for link in body)
            assert all(link["available_in"] == "active" for link in body)
            assert body[0]["preview"] == "Erster Block"
            assert body[0]["resource_name"] == "Doc"
            # Section reicht von h1 bis exklusive h2 (gleiches Level).
            assert body[0]["section_block_ids"] == ["h1", "p1"]
            assert "Erster Block" in body[0]["section_preview"]
            assert "Paragraph zu h1" in body[0]["section_preview"]
            # h2-Section laeuft bis Dokument-Ende.
            assert body[1]["section_block_ids"] == ["h2", "p2"]

            # Set-Replace: nur noch h1.
            replaced = client.put(
                links_url,
                json={"links": [{"resource_id": rid, "block_id": "h1", "position": 0}]},
                headers=auth,
            ).json()
            assert [link["block_id"] for link in replaced] == ["h1"]

            # Neue aktive Version OHNE h1 -> Link wird unavailable ("Block geloescht").
            client.put(
                rbase + f"/{rid}",
                json=_resource_body("Doc", [_heading("h2", "Nur h2")]),
                headers=auth,
            )
            _activate(client, rbase, rid, 2, auth)
            after = client.get(links_url, headers=auth).json()
            assert after[0]["block_id"] == "h1"
            assert after[0]["available"] is False
            assert after[0]["available_in"] is None
            assert after[0]["preview"] is None
            assert after[0]["section_block_ids"] == []
            assert after[0]["section_preview"] is None

            # Leere Liste loest alle Links.
            assert client.put(links_url, json={"links": []}, headers=auth).json() == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_links_reject_cross_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            # Resource im fremden Workspace.
            foreign_rid = client.post(
                f"/v1/workspaces/{other_ws}/resources",
                json=_resource_body("Foreign", [_heading("h1", "x")]),
                headers=_auth(other),
            ).json()["id"]
            pid = client.post(
                f"/v1/workspaces/{ws}/playbooks", json=_playbook_body("PB"), headers=auth
            ).json()["id"]

            # Fremde Resource im eigenen Playbook verlinken -> 404.
            resp = client.put(
                f"/v1/workspaces/{ws}/playbooks/{pid}/resource_links",
                json={"links": [{"resource_id": foreign_rid, "block_id": "h1", "position": 0}]},
                headers=auth,
            )
            assert resp.status_code == 404
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_resource_links_reject_non_heading_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            rid = client.post(
                rbase,
                json=_resource_body(
                    "Doc",
                    [_heading("h1", "Heading"), _block("p1", "Paragraph")],
                ),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)

            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"

            # Paragraph als Anker → 422.
            resp = client.put(
                links_url,
                json={"links": [{"resource_id": rid, "block_id": "p1", "position": 0}]},
                headers=auth,
            )
            assert resp.status_code == 422, resp.text
            assert "Heading" in resp.json()["detail"]

            # Heading als Anker geht durch.
            ok = client.put(
                links_url,
                json={"links": [{"resource_id": rid, "block_id": "h1", "position": 0}]},
                headers=auth,
            )
            assert ok.status_code == 200, ok.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_links_section_nesting_keeps_deeper_headings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            # h1 -> p -> h2 (tieferes Level, bleibt drin) -> p -> h1' (beendet Section).
            rid = client.post(
                rbase,
                json=_resource_body(
                    "Doc",
                    [
                        _heading("h1a", "Erstes Kapitel", level=1),
                        _block("p1", "Intro"),
                        _heading("h2a", "Unterkapitel", level=2),
                        _block("p2", "Detail"),
                        _heading("h1b", "Zweites Kapitel", level=1),
                        _block("p3", "Outro"),
                    ],
                ),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)

            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"
            resp = client.put(
                links_url,
                json={"links": [{"resource_id": rid, "block_id": "h1a", "position": 0}]},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            link = resp.json()[0]
            # h2a bleibt in der Section (tieferes Level); h1b beendet sie.
            assert link["section_block_ids"] == ["h1a", "p1", "h2a", "p2"]
            assert "Erstes Kapitel" in link["section_preview"]
            assert "Detail" in link["section_preview"]
            assert "Zweites Kapitel" not in link["section_preview"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_links_available_fallback_to_current_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            # Resource hat NUR Draft-v1 (keine Active).
            rid = client.post(
                rbase,
                json=_resource_body("Doc", [_heading("h1", "Nur in Draft")]),
                headers=auth,
            ).json()["id"]
            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"

            resp = client.put(
                links_url,
                json={"links": [{"resource_id": rid, "block_id": "h1", "position": 0}]},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            link = resp.json()[0]
            assert link["available"] is True
            assert link["available_in"] == "draft"
            assert link["preview"] == "Nur in Draft"
            assert link["section_block_ids"] == ["h1"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_links_resource_scope_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase-3-Fixes Track 4: 'resource'-Scope verlinkt das Volldokument.

    block_id ist None, preview/section bleiben leer; available_in ergibt
    sich aus der Existenz einer Active-Version.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            rid = client.post(
                rbase,
                json=_resource_body("Doc", [_heading("h1", "Heading"), _block("p1", "Body")]),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)

            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"

            resp = client.put(
                links_url,
                json={
                    "links": [
                        {
                            "resource_id": rid,
                            "block_id": None,
                            "position": 0,
                            "link_scope": "resource",
                        }
                    ]
                },
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert len(body) == 1
            assert body[0]["link_scope"] == "resource"
            assert body[0]["block_id"] is None
            assert body[0]["available"] is True
            assert body[0]["available_in"] == "active"
            assert body[0]["preview"] is None
            assert body[0]["section_block_ids"] == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_links_resource_and_block_scopes_coexist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Playbook darf neben dem 'resource'-Link beliebig viele 'block'-Refs
    auf dieselbe Resource haben — die partiellen Unique-Indexe aus 0021
    kollidieren nicht.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            rid = client.post(
                rbase,
                json=_resource_body(
                    "Doc",
                    [_heading("h1", "A"), _block("p1", "x"), _heading("h2", "B")],
                ),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)

            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"

            resp = client.put(
                links_url,
                json={
                    "links": [
                        {
                            "resource_id": rid,
                            "block_id": None,
                            "position": 0,
                            "link_scope": "resource",
                        },
                        {
                            "resource_id": rid,
                            "block_id": "h1",
                            "position": 1,
                            "link_scope": "block",
                        },
                        {
                            "resource_id": rid,
                            "block_id": "h2",
                            "position": 2,
                            "link_scope": "block",
                        },
                    ]
                },
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert len(body) == 3
            scopes = sorted(link["link_scope"] for link in body)
            assert scopes == ["block", "block", "resource"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_links_resource_scope_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zweimal denselben 'resource'-Link schicken — Service-Dedup laesst nur
    einen durch, sodass der partielle Unique-Index aus 0021 nicht feuert.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            rid = client.post(
                rbase,
                json=_resource_body("Doc", [_heading("h1", "Heading")]),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)
            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"

            resp = client.put(
                links_url,
                json={
                    "links": [
                        {
                            "resource_id": rid,
                            "block_id": None,
                            "position": 0,
                            "link_scope": "resource",
                        },
                        {
                            "resource_id": rid,
                            "block_id": None,
                            "position": 1,
                            "link_scope": "resource",
                        },
                    ]
                },
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert len(body) == 1
            assert body[0]["link_scope"] == "resource"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_links_active_wins_over_current_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            # v1 wird Active; v2 wird neuer Draft (current_version=2) ohne h1.
            rid = client.post(
                rbase,
                json=_resource_body("Doc", [_heading("h1", "Aktiver Text")]),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)
            # Draft-on-Edit erzeugt v2 ohne den h1-Block.
            client.put(
                rbase + f"/{rid}",
                json=_resource_body("Doc", [_heading("h2", "Anderer Heading")]),
                headers=auth,
            )

            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"
            resp = client.put(
                links_url,
                json={"links": [{"resource_id": rid, "block_id": "h1", "position": 0}]},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            link = resp.json()[0]
            # h1 ist in Active (v1) und nicht in Current (v2) — Active gewinnt.
            assert link["available_in"] == "active"
            assert link["preview"] == "Aktiver Text"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_links_embedding_mode_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Embed-Modus: Default 'lazy', explizit auf 'inline' setzbar (Set-Replace).

    Steuert, ob `fetch_playbook` das Volldokument inline mitsendet (MCP-Seite).
    Hier nur der REST-Roundtrip: schreiben + zuruecklesen.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    rbase = f"/v1/workspaces/{ws}/resources"
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            rid = client.post(
                rbase,
                json=_resource_body("Doc", [_heading("h1", "Heading")]),
                headers=auth,
            ).json()["id"]
            _activate(client, rbase, rid, 1, auth)
            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]
            links_url = f"{pbase}/{pid}/resource_links"

            # Default ohne embedding_mode → 'lazy'.
            resp = client.put(
                links_url,
                json={
                    "links": [
                        {
                            "resource_id": rid,
                            "block_id": None,
                            "position": 0,
                            "link_scope": "resource",
                        }
                    ]
                },
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()[0]["embedding_mode"] == "lazy"

            # Explizit auf 'inline' umschalten.
            resp = client.put(
                links_url,
                json={
                    "links": [
                        {
                            "resource_id": rid,
                            "block_id": None,
                            "position": 0,
                            "link_scope": "resource",
                            "embedding_mode": "inline",
                        }
                    ]
                },
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()[0]["embedding_mode"] == "inline"
    finally:
        cleanup_workspaces([owner])
