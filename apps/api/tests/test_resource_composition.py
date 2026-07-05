"""Integrationstest fuer die Sub-Resource-Relation (Track E, §3.3).

Pfade `/v1/workspaces/{ws}/resources/{id}/sub_resources` und `used_by`.
Deckt ab: Set-Replace-Semantik + Reihenfolge, Block-Scope-Links,
Cross-Workspace-Isolation, transitiver Zyklus (A->B->C->A), Selbst-Referenz,
Used-By-Backlinks. Skippt ohne erreichbare Datenbank.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import httpx
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


def _resource_body(name: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "blocks": [{"id": "b1", "type": "heading", "props": {"level": 1}}],
            "tags": [],
        },
    }


@pytest.mark.integration
def test_sub_resource_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """set/list/reorder/clear + used_by + fetch_call-Ableitung."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            parent = client.post(base, json=_resource_body("Parent"), headers=auth).json()["id"]
            child_a = client.post(base, json=_resource_body("Child-A"), headers=auth).json()["id"]
            child_b = client.post(base, json=_resource_body("Child-B"), headers=auth).json()["id"]

            subs_url = f"{base}/{parent}/sub_resources"
            used_by_url = f"{base}/{child_a}/used_by"

            # Leer am Anfang.
            assert client.get(subs_url, headers=auth).json() == []

            # Set: beide Kinder als Volldokument-Refs.
            resp = client.put(
                subs_url,
                json={
                    "links": [
                        {"child_id": child_a, "link_scope": "resource", "position": 0},
                        {"child_id": child_b, "link_scope": "resource", "position": 1},
                    ]
                },
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            subs = resp.json()
            assert [s["id"] for s in subs] == [child_a, child_b]
            # fetch_call wird serverseitig aus der id abgeleitet.
            assert subs[0]["fetch_call"] == f"fetch_resource('{child_a}')"
            assert subs[0]["link_scope"] == "resource"
            assert subs[0]["block_id"] is None

            # GET liefert dieselbe geordnete Liste.
            assert [s["id"] for s in client.get(subs_url, headers=auth).json()] == [
                child_a,
                child_b,
            ]

            # used_by: child_a wird von parent referenziert.
            by = client.get(used_by_url, headers=auth).json()
            assert any(p["id"] == parent for p in by)

            # Der GET /resources/{id}-Read traegt selbst KEINE sub_resources (dedizierter
            # Endpoint bedient den Web-Picker); Default bleibt leer.
            parent_read = client.get(f"{base}/{parent}", headers=auth).json()
            assert parent_read.get("sub_resources", []) == []

            # Reorder.
            reorder = client.put(
                subs_url,
                json={
                    "links": [
                        {"child_id": child_b, "link_scope": "resource", "position": 0},
                        {"child_id": child_a, "link_scope": "resource", "position": 1},
                    ]
                },
                headers=auth,
            )
            assert [s["id"] for s in reorder.json()] == [child_b, child_a]

            # Leere Liste loest alle.
            assert client.put(subs_url, json={"links": []}, headers=auth).json() == []
            assert client.get(used_by_url, headers=auth).json() == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_sub_resource_block_scope_link(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block-Scope-Link: child + block_id wird gespeichert und gelesen."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            parent = client.post(base, json=_resource_body("Parent"), headers=auth).json()["id"]
            child = client.post(base, json=_resource_body("Child"), headers=auth).json()["id"]
            subs_url = f"{base}/{parent}/sub_resources"

            resp = client.put(
                subs_url,
                json={
                    "links": [
                        {"child_id": child, "link_scope": "block", "block_id": "b1", "position": 0},
                    ]
                },
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            sub = resp.json()[0]
            assert sub["link_scope"] == "block"
            assert sub["block_id"] == "b1"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_sub_resource_cross_workspace_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cross-Workspace-Kind -> 404 (Same-Workspace-Guard)."""
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
            parent = client.post(
                f"/v1/workspaces/{ws}/resources", json=_resource_body("Parent"), headers=auth
            ).json()["id"]
            foreign = client.post(
                f"/v1/workspaces/{other_ws}/resources",
                json=_resource_body("Foreign"),
                headers=_auth(other),
            ).json()["id"]

            resp = client.put(
                f"/v1/workspaces/{ws}/resources/{parent}/sub_resources",
                json={"links": [{"child_id": foreign, "link_scope": "resource", "position": 0}]},
                headers=auth,
            )
            assert resp.status_code == 404
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_sub_resource_transitive_cycle_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Transitiver Zyklus A->B->C->A wird mit 409 abgelehnt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    def _set(parent: str, child: str) -> int:
        resp: httpx.Response = client.put(
            f"{base}/{parent}/sub_resources",
            json={"links": [{"child_id": child, "link_scope": "resource", "position": 0}]},
            headers=auth,
        )
        return resp.status_code

    try:
        with TestClient(app) as client:
            res_a = client.post(base, json=_resource_body("A"), headers=auth).json()["id"]
            res_b = client.post(base, json=_resource_body("B"), headers=auth).json()["id"]
            res_c = client.post(base, json=_resource_body("C"), headers=auth).json()["id"]

            assert _set(res_a, res_b) == 200  # A -> B
            assert _set(res_b, res_c) == 200  # B -> C
            # C -> A schliesst den Zyklus -> 409.
            assert _set(res_c, res_a) == 409
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def _agent_in(ws: UUID) -> str:
    """ID des Seed-„Builder"-Agenten (Tokens sind agent-gebunden, 0048; Builder
    hat resource_read='all')."""

    async def _run() -> str:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id = await conn.fetchval(
                "SELECT id FROM agent WHERE workspace_id = $1 LIMIT 1", ws
            )
            assert agent_id is not None, "Seed-Agent fehlt"
            # Token an einen Read-all-CONSUMER binden (keine Writes → sees_drafts
            # False → nur active sichtbar). Der Seed-Builder traegt Writes und
            # saehe sonst auch Drafts (korrektes sees_drafts-Verhalten).
            await conn.execute(
                "UPDATE agent SET tool_policy = $2::jsonb WHERE id = $1",
                agent_id,
                '{"playbook_read":"all","resource_read":"all",'
                '"agent_read":"all","persona_read":true}',
            )
            return str(agent_id)
        finally:
            await conn.close()

    return asyncio.run(_run())


def test_sub_resource_active_filter_for_api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP-/API-Token-Pfad blendet Sub-Resources ohne aktive Kind-Version aus.

    Konsistent zur Invariante "MCP sieht nur active" (Phase 2.1b): ein Link auf
    eine nur als Draft existierende Sub-Resource ist fuer den JWT-/Web-Pfad
    sichtbar, fuer den Token-Pfad aber gefiltert (kein toter Pointer fuer Agenten).
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            parent = client.post(base, json=_resource_body("Parent"), headers=auth).json()["id"]
            active_child = client.post(
                base, json=_resource_body("Active-Child"), headers=auth
            ).json()["id"]
            draft_child = client.post(
                base, json=_resource_body("Draft-Child"), headers=auth
            ).json()["id"]
            # active_child auf active heben; draft_child bleibt Draft.
            for to in ("draft", "review", "active"):
                client.post(
                    f"{base}/{active_child}/versions/1/transition", json={"to": to}, headers=auth
                )

            client.put(
                f"{base}/{parent}/sub_resources",
                json={
                    "links": [
                        {"child_id": active_child, "link_scope": "resource", "position": 0},
                        {"child_id": draft_child, "link_scope": "resource", "position": 1},
                    ]
                },
                headers=auth,
            )

            # Token ist agent-gebunden (0048); der Seed-Builder hat
            # resource_read='all'.
            token = client.post(
                f"/v1/workspaces/{ws}/tokens",
                json={"name": "mcp", "agent_id": _agent_in(ws)},
                headers=auth,
            ).json()["token"]
            token_auth = {"Authorization": f"Bearer {token}"}

            # JWT-Pfad: beide Links sichtbar.
            jwt_subs = client.get(f"{base}/{parent}/sub_resources", headers=auth).json()
            assert {s["id"] for s in jwt_subs} == {active_child, draft_child}

            # Token-Pfad: nur das Kind mit aktiver Version.
            token_subs = client.get(f"{base}/{parent}/sub_resources", headers=token_auth).json()
            assert [s["id"] for s in token_subs] == [active_child]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_sub_resource_self_reference_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direkter Self-Ref wird defensiv herausgefiltert (kein 4xx, leeres Ergebnis)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            res = client.post(base, json=_resource_body("Solo"), headers=auth).json()["id"]
            resp = client.put(
                f"{base}/{res}/sub_resources",
                json={"links": [{"child_id": res, "link_scope": "resource", "position": 0}]},
                headers=auth,
            )
            assert resp.status_code == 200
            assert resp.json() == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_sub_resource_embedding_mode_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Embed-Modus: Default 'lazy', explizit auf 'inline' setzbar (Set-Replace).

    'inline'-Kinder zieht der MCP-`fetch_resource`-Pfad als Volldokument mit;
    hier nur der REST-Roundtrip.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            parent = client.post(base, json=_resource_body("Parent"), headers=auth).json()["id"]
            child = client.post(base, json=_resource_body("Child"), headers=auth).json()["id"]
            subs_url = f"{base}/{parent}/sub_resources"

            # Default ohne embedding_mode → 'lazy'.
            resp = client.put(
                subs_url,
                json={"links": [{"child_id": child, "link_scope": "resource", "position": 0}]},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()[0]["embedding_mode"] == "lazy"

            # Explizit auf 'inline' umschalten.
            resp = client.put(
                subs_url,
                json={
                    "links": [
                        {
                            "child_id": child,
                            "link_scope": "resource",
                            "position": 0,
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
