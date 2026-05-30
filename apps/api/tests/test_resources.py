"""Integrationstest fuer Resources unter `/v1/workspaces/{ws_id}/resources`.

Deckt Phase 2.2 ab: Resource-CRUD + Versionierung, Block-Content-Roundtrip,
Status-Transitionen inkl. DB-Invariante "max. 1 Active", Draft-on-Edit-409,
Active-Filter fuer API-Tokens (MCP-Pfad) und Workspace-Isolation. Laeuft nur
mit erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
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


def _resource_body(
    name: str, description: str, blocks: list[dict[str, object]]
) -> dict[str, object]:
    return {"name": name, "content": {"description": description, "blocks": blocks}}


@pytest.mark.integration
def test_resource_crud_versioning_and_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    setup_workspace(other)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            assert client.get(base).status_code == 401

            created = client.post(
                base,
                json=_resource_body("Runbook", "v1", [_block("b1", "Hallo Welt")]),
                headers=auth,
            )
            assert created.status_code == 201, created.text
            rid = created.json()["id"]
            assert created.json()["current_version"] == 1
            # Phase 3-0: neue v1 startet als Draft (Migration 0019).
            assert created.json()["current_status"] == "draft"
            assert created.json()["workspace_id"] == str(ws)
            assert created.json()["content"]["blocks"][0]["id"] == "b1"

            # Vor PUT erst v1 auf Active promoten, sonst 409 (Draft existiert).
            for to in ("review", "active"):
                client.post(
                    f"{base}/{rid}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )

            # Update -> neue Version, Block-Content-Roundtrip.
            updated = client.put(
                f"{base}/{rid}",
                json=_resource_body("Runbook", "v2", [_block("b1", "Geaendert")]),
                headers=auth,
            )
            assert updated.status_code == 200
            assert updated.json()["current_version"] == 2

            versions = client.get(f"{base}/{rid}/versions", headers=auth).json()
            assert [v["version"] for v in versions] == [2, 1]
            v1 = client.get(f"{base}/{rid}/versions/1", headers=auth).json()
            assert v1["content"]["blocks"][0]["content"][0]["text"] == "Hallo Welt"

            # Workspace-Isolation: fremder User sieht die Resource nicht (403).
            assert client.get(f"{base}/{rid}", headers=_auth(other)).status_code == 403
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_resource_transitions_invariant_and_draft_on_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            rid = client.post(
                base,
                json=_resource_body("Doc", "v1", [_block("b1", "x")]),
                headers=auth,
            ).json()["id"]

            # Phase 3-0: v1 startet bereits als Draft; nur review + active
            # uebrig auf dem Weg nach Active.
            for to in ("review", "active"):
                resp = client.post(
                    f"{base}/{rid}/versions/1/transition", json={"to": to}, headers=auth
                )
                assert resp.status_code == 200, resp.text

            # Verbotener Uebergang active -> draft.
            assert (
                client.post(
                    f"{base}/{rid}/versions/1/transition", json={"to": "draft"}, headers=auth
                ).status_code
                == 409
            )

            # Edit auf Active -> neuer Draft.
            updated = client.put(
                f"{base}/{rid}",
                json=_resource_body("Doc", "v2", [_block("b1", "y")]),
                headers=auth,
            )
            assert updated.json()["current_status"] == "draft"
            assert updated.json()["has_pending_draft"] is True

            # Zweiter PUT -> 409 (Draft existiert bereits).
            assert (
                client.put(
                    f"{base}/{rid}",
                    json=_resource_body("Doc", "v3", [_block("b1", "z")]),
                    headers=auth,
                ).status_code
                == 409
            )

            # Promotion v2 -> active inactiviert v1 (Invariante "max. 1 Active").
            client.post(f"{base}/{rid}/versions/2/transition", json={"to": "review"}, headers=auth)
            client.post(f"{base}/{rid}/versions/2/transition", json={"to": "active"}, headers=auth)
            versions = client.get(f"{base}/{rid}/versions", headers=auth).json()
            assert {v["version"]: v["status"] for v in versions} == {1: "inactive", 2: "active"}
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_patch_draft_upserts_in_place_without_active_touch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    setup_workspace(other)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            rid = client.post(
                base,
                json=_resource_body("Doc", "v1", [_block("b1", "active")]),
                headers=auth,
            ).json()["id"]
            for to in ("review", "active"):
                client.post(f"{base}/{rid}/versions/1/transition", json={"to": to}, headers=auth)

            first = client.patch(
                f"{base}/{rid}/draft",
                json=_resource_body("Doc", "d1", [_block("b1", "draft-1")]),
                headers=auth,
            )
            assert first.status_code == 200, first.text
            assert first.json()["current_version"] == 2
            assert first.json()["current_status"] == "draft"
            v1 = client.get(f"{base}/{rid}/versions/1", headers=auth).json()
            assert v1["status"] == "active"
            assert v1["content"]["description"] == "v1"

            second = client.patch(
                f"{base}/{rid}/draft",
                json=_resource_body("Doc", "d2", [_block("b1", "draft-2")]),
                headers=auth,
            )
            assert second.status_code == 200
            assert second.json()["current_version"] == 2
            assert second.json()["content"]["description"] == "d2"
            versions = client.get(f"{base}/{rid}/versions", headers=auth).json()
            assert [v["version"] for v in versions] == [2, 1]

            assert (
                client.patch(
                    f"{base}/{rid}/draft",
                    json=_resource_body("Doc", "f", [_block("b1", "foreign")]),
                    headers=_auth(other),
                ).status_code
                == 403
            )
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_resource_patch_draft_on_review_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
            rid = client.post(
                base,
                json=_resource_body("Doc", "v1", [_block("b1", "x")]),
                headers=auth,
            ).json()["id"]
            client.post(f"{base}/{rid}/versions/1/transition", json={"to": "review"}, headers=auth)
            assert (
                client.patch(
                    f"{base}/{rid}/draft",
                    json=_resource_body("Doc", "nope", [_block("b1", "y")]),
                    headers=auth,
                ).status_code
                == 409
            )
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_active_filter_for_api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    jwt_auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            inactive_id = client.post(
                base, json=_resource_body("Inactive", "v1", [_block("b1", "x")]), headers=jwt_auth
            ).json()["id"]
            active_id = client.post(
                base, json=_resource_body("Active", "v1", [_block("b1", "x")]), headers=jwt_auth
            ).json()["id"]
            for to in ("draft", "review", "active"):
                client.post(
                    f"{base}/{active_id}/versions/1/transition", json={"to": to}, headers=jwt_auth
                )

            token = client.post(
                f"/v1/workspaces/{ws}/tokens", json={"name": "mcp"}, headers=jwt_auth
            ).json()["token"]
            token_auth = {"Authorization": f"Bearer {token}"}

            jwt_list = client.get(base, headers=jwt_auth).json()
            assert {r["id"] for r in jwt_list} == {inactive_id, active_id}

            token_list = client.get(base, headers=token_auth).json()
            assert [r["id"] for r in token_list] == [active_id]
            assert token_list[0]["current_status"] == "active"

            assert client.get(f"{base}/{inactive_id}", headers=token_auth).status_code == 404
            assert client.get(f"{base}/{active_id}", headers=token_auth).status_code == 200
    finally:
        cleanup_workspaces([owner])
