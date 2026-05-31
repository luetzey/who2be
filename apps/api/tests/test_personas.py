"""Integrationstest fuer Personae unter `/v1/workspaces/{ws_id}/personas`.

Belegt die Versions-Erzeugung bei `PUT` und die Workspace-Isolation. Laeuft
nur mit erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
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


def _persona_body(description: str) -> dict[str, object]:
    return {
        "name": "QA-Bot",
        "content": {
            "description": description,
            "system_prompt": "Be precise.",
            "traits": ["thorough"],
        },
    }


@pytest.mark.integration
def test_persona_crud_versioning_and_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            assert client.get(base).status_code == 401

            created = client.post(base, json=_persona_body("v1"), headers=auth)
            assert created.status_code == 201
            persona = created.json()
            persona_id = persona["id"]
            assert persona["current_version"] == 1
            assert persona["workspace_id"] == str(ws)

            fetched = client.get(f"{base}/{persona_id}", headers=auth).json()
            assert fetched["content"]["description"] == "v1"

            listed = client.get(base, headers=auth).json()
            assert [p["id"] for p in listed] == [persona_id]

            # Phase 3-0: neue v1 startet als Draft (Migration 0019). PUT
            # wuerde sonst sofort 409 werfen, weil schon ein Draft existiert
            # — also v1 erst auf Active promoten.
            for to in ("review", "active"):
                client.post(
                    f"{base}/{persona_id}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )

            updated = client.put(
                f"{base}/{persona_id}",
                json=_persona_body("v2"),
                headers=auth,
            )
            assert updated.status_code == 200
            assert updated.json()["current_version"] == 2

            current = client.get(f"{base}/{persona_id}", headers=auth).json()
            assert current["content"]["description"] == "v2"

            versions = client.get(f"{base}/{persona_id}/versions", headers=auth).json()
            assert [v["version"] for v in versions] == [2, 1]

            v1 = client.get(f"{base}/{persona_id}/versions/1", headers=auth).json()
            assert v1["content"]["description"] == "v1"

            # Cross-Workspace: fremder User mit eigenem Workspace sieht 403,
            # weil er keine Membership im Owner-Workspace hat.
            assert client.get(base, headers=_auth(other)).status_code == 403
            # Im eigenen Workspace ist die Persona nicht sichtbar.
            other_base = f"/v1/workspaces/{other_ws}/personas"
            assert client.get(other_base, headers=_auth(other)).json() == []
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_persona_pagination_via_cursor_and_limit_validation(
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
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            created_ids: list[str] = []
            for i in range(3):
                resp = client.post(base, json=_persona_body(f"v{i}"), headers=auth)
                assert resp.status_code == 201
                created_ids.append(resp.json()["id"])

            page1 = client.get(f"{base}?limit=2", headers=auth)
            assert page1.status_code == 200
            assert len(page1.json()) == 2
            cursor = page1.headers.get("X-Next-Cursor")
            assert cursor is not None

            page2 = client.get(f"{base}?limit=2&cursor={cursor}", headers=auth)
            assert page2.status_code == 200
            assert len(page2.json()) == 1
            assert "X-Next-Cursor" not in page2.headers

            seen = {p["id"] for p in page1.json()} | {p["id"] for p in page2.json()}
            assert seen == set(created_ids)

            # Cross-Workspace: fremder Aufruf 403 (kein Membership).
            assert client.get(base, headers=_auth(other)).status_code == 403

            # Validation: Limit-Bereich und Cursor-Form.
            assert client.get(f"{base}?limit=0", headers=auth).status_code == 422
            assert client.get(f"{base}?limit=201", headers=auth).status_code == 422
            assert client.get(f"{base}?cursor=!!!", headers=auth).status_code == 422
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_persona_version_transitions_state_machine_and_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            created = client.post(base, json=_persona_body("v1"), headers=auth)
            persona_id = created.json()["id"]

            def transition(v: int, to: str, expected: int = 200) -> dict[str, object]:
                resp = client.post(
                    f"{base}/{persona_id}/versions/{v}/transition",
                    json={"to": to},
                    headers=auth,
                )
                assert resp.status_code == expected, resp.text
                return resp.json() if resp.status_code < 300 else {}

            # Phase 3-0: v1 startet bereits als Draft (Migration 0019).
            # Verbotener Uebergang: draft -> active (State-Machine erlaubt
            # nur draft -> review).
            transition(1, "active", expected=409)

            review = transition(1, "review", expected=200)
            assert review["status"] == "review"
            transition(1, "active", expected=200)

            # PUT auf Active erzeugt v2 als Draft; Active bleibt v1.
            updated = client.put(
                f"{base}/{persona_id}",
                json=_persona_body("v2"),
                headers=auth,
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["current_version"] == 2
            assert updated.json()["current_status"] == "draft"
            assert updated.json()["has_pending_draft"] is True

            # Promotion von v2: v1 wird auto-inactiviert (Plan §2.1.C),
            # v2 wird active.
            transition(2, "review", expected=200)
            promoted = transition(2, "active", expected=200)
            assert promoted["status"] == "active"
            versions = client.get(f"{base}/{persona_id}/versions", headers=auth).json()
            by_version = {v["version"]: v["status"] for v in versions}
            assert by_version == {1: "inactive", 2: "active"}

            # status_history-Audit: 5 Eigen-Transitions + 1 Auto-Inactivierung.
            async def history_count() -> int:
                conn = await asyncpg.connect(get_settings().database_url)
                try:
                    count = await conn.fetchval(
                        "SELECT count(*) FROM status_history "
                        "WHERE entity_type='persona' AND entity_id=$1",
                        UUID(persona_id),
                    )
                    return int(count)
                finally:
                    await conn.close()

            # Phase 3-0: 4 Eigen-Transitions auf v1/v2 (draft->review, review->active,
            # draft->review, review->active) + 1 Auto-Inactivierung von v1 = 5.
            assert asyncio.run(history_count()) == 5
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_persona_put_on_active_creates_draft_and_blocks_second_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            persona_id = client.post(base, json=_persona_body("v1"), headers=auth).json()["id"]
            # Auf Active hochziehen.
            for to in ("draft", "review", "active"):
                client.post(
                    f"{base}/{persona_id}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )
            first = client.put(f"{base}/{persona_id}", json=_persona_body("v2"), headers=auth)
            assert first.status_code == 200
            assert first.json()["current_status"] == "draft"

            # Zweiter PUT: Draft existiert noch → 409.
            second = client.put(f"{base}/{persona_id}", json=_persona_body("v3"), headers=auth)
            assert second.status_code == 409
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_persona_patch_draft_upserts_in_place_without_active_touch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PATCH erzeugt einen Draft (wenn nicht da) und ueberschreibt ihn in-place.

    - PATCH 1 auf Active-only-Stand: neuer Draft v2, Active bleibt v1.
    - PATCH 2 auf den Draft: Inhalt wird ueberschrieben, kein Versions-Increment.
    - Tenant-Isolation: Fremd-Workspace darf nicht editieren (403/404).
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    setup_workspace(other)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            persona_id = client.post(base, json=_persona_body("v1"), headers=auth).json()["id"]
            # Auf Active hochziehen.
            for to in ("review", "active"):
                client.post(
                    f"{base}/{persona_id}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )

            # PATCH 1: Draft v2 entsteht, Active bleibt v1.
            first = client.patch(
                f"{base}/{persona_id}/draft",
                json=_persona_body("draft-1"),
                headers=auth,
            )
            assert first.status_code == 200, first.text
            assert first.json()["current_version"] == 2
            assert first.json()["current_status"] == "draft"
            v1 = client.get(f"{base}/{persona_id}/versions/1", headers=auth).json()
            assert v1["status"] == "active"
            assert v1["content"]["description"] == "v1"

            # PATCH 2: gleicher Draft, in-place ueberschrieben.
            second = client.patch(
                f"{base}/{persona_id}/draft",
                json=_persona_body("draft-2"),
                headers=auth,
            )
            assert second.status_code == 200
            assert second.json()["current_version"] == 2
            assert second.json()["content"]["description"] == "draft-2"
            versions = client.get(f"{base}/{persona_id}/versions", headers=auth).json()
            # Genau zwei Versionen: v1 (active) + v2 (draft, ueberschrieben).
            assert [v["version"] for v in versions] == [2, 1]

            # Tenant-Isolation: fremder User hat keinen Zugriff (403, kein 200).
            assert (
                client.patch(
                    f"{base}/{persona_id}/draft",
                    json=_persona_body("foreign"),
                    headers=_auth(other),
                ).status_code
                == 403
            )
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_persona_patch_draft_on_review_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review-Version darf nicht ueberschrieben werden — 409 statt stiller Write."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            persona_id = client.post(base, json=_persona_body("v1"), headers=auth).json()["id"]
            # v1: draft → review (kein Draft mehr, current_status=review).
            client.post(
                f"{base}/{persona_id}/versions/1/transition",
                json={"to": "review"},
                headers=auth,
            )
            resp = client.patch(
                f"{base}/{persona_id}/draft",
                json=_persona_body("nope"),
                headers=auth,
            )
            assert resp.status_code == 409
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_persona_active_filter_for_api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    jwt_auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            inactive_id = client.post(
                base, json=_persona_body("inactive"), headers=jwt_auth
            ).json()["id"]
            active_id = client.post(base, json=_persona_body("active"), headers=jwt_auth).json()[
                "id"
            ]
            # Active-Pfad fuer den zweiten.
            for to in ("draft", "review", "active"):
                client.post(
                    f"{base}/{active_id}/versions/1/transition",
                    json={"to": to},
                    headers=jwt_auth,
                )

            # API-Token anlegen + nutzen.
            token_resp = client.post(
                f"/v1/workspaces/{ws}/tokens", json={"name": "mcp"}, headers=jwt_auth
            )
            token = token_resp.json()["token"]
            token_auth = {"Authorization": f"Bearer {token}"}

            # JWT sieht beide.
            jwt_list = client.get(base, headers=jwt_auth).json()
            assert {p["id"] for p in jwt_list} == {inactive_id, active_id}

            # Token sieht nur Active.
            token_list = client.get(base, headers=token_auth).json()
            assert [p["id"] for p in token_list] == [active_id]
            assert token_list[0]["current_status"] == "active"

            # Direkter Fetch der inaktiven Persona per Token → 404.
            assert client.get(f"{base}/{inactive_id}", headers=token_auth).status_code == 404
            assert client.get(f"{base}/{active_id}", headers=token_auth).status_code == 200
    finally:
        cleanup_workspaces([owner])
