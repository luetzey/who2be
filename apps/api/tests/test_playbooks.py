"""Integrationstest fuer Playbooks unter `/v1/workspaces/{ws_id}/playbooks`
und die Persona-Playbook-Verknuepfung.

Deckt AC2/AC3 ab: Playbook-CRUD + Versionierung, Tag-/Trigger-Filter und das
Verknuepfen von Playbooks mit einer Persona. Laeuft nur mit erreichbarer
Datenbank; ohne DB wird der Test uebersprungen.
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


def _playbook_body(
    name: str, description: str, tags: list[str], triggers: str
) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": description,
            "body": "1. Step.",
            "type": "workflow",
            "tags": tags,
            "triggers": triggers,
        },
    }


@pytest.mark.integration
def test_playbook_crud_filters_and_persona_linking(
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
    pb_base = f"/v1/workspaces/{ws}/playbooks"
    persona_base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            assert client.get(pb_base).status_code == 401

            first = client.post(
                pb_base,
                json=_playbook_body("Onboard", "v1", ["onboarding"], "new user"),
                headers=auth,
            )
            assert first.status_code == 201
            first_id = first.json()["id"]
            assert first.json()["current_version"] == 1
            assert first.json()["tags"] == ["onboarding"]
            assert first.json()["workspace_id"] == str(ws)

            second = client.post(
                pb_base,
                json=_playbook_body("Recover", "v1", ["recovery"], "on error"),
                headers=auth,
            )
            second_id = second.json()["id"]

            # Tag-Filter
            by_tag = client.get(pb_base, params={"tag": "onboarding"}, headers=auth).json()
            assert [p["id"] for p in by_tag] == [first_id]

            # Trigger-Filter (case-insensitive Teilstring)
            by_trigger = client.get(pb_base, params={"trigger": "USER"}, headers=auth).json()
            assert [p["id"] for p in by_trigger] == [first_id]

            # Phase 3-0: neue v1 startet als Draft (Migration 0019). Vor PUT
            # erst auf Active promoten, sonst 409 (Draft existiert bereits).
            for to in ("review", "active"):
                client.post(
                    f"{pb_base}/{first_id}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )

            # Update -> neue Version
            updated = client.put(
                f"{pb_base}/{first_id}",
                json=_playbook_body("Onboard", "v2", ["onboarding"], "new user"),
                headers=auth,
            )
            assert updated.status_code == 200
            assert updated.json()["current_version"] == 2

            versions = client.get(f"{pb_base}/{first_id}/versions", headers=auth).json()
            assert [v["version"] for v in versions] == [2, 1]
            v1 = client.get(f"{pb_base}/{first_id}/versions/1", headers=auth).json()
            assert v1["content"]["description"] == "v1"

            # Persona anlegen und Playbooks verknuepfen
            persona = client.post(
                persona_base,
                json={
                    "name": "QA",
                    "content": {"description": "d", "system_prompt": "s"},
                },
                headers=auth,
            )
            persona_id = persona.json()["id"]

            linked = client.put(
                f"{persona_base}/{persona_id}/playbooks",
                json={"playbook_ids": [first_id, second_id]},
                headers=auth,
            )
            assert linked.status_code == 200
            assert {p["id"] for p in linked.json()} == {first_id, second_id}

            assert {
                p["id"]
                for p in client.get(f"{persona_base}/{persona_id}/playbooks", headers=auth).json()
            } == {first_id, second_id}

            # Verknuepfung vollstaendig ersetzen (leere Liste loest alle)
            cleared = client.put(
                f"{persona_base}/{persona_id}/playbooks",
                json={"playbook_ids": []},
                headers=auth,
            )
            assert cleared.json() == []

            # Cross-Workspace: fremdes Playbook im eigenen Workspace verknuepfen -> 404
            # (Persona im fremden WS verlangt Membership des Aufrufers dort).
            other_persona = client.post(
                f"/v1/workspaces/{other_ws}/personas",
                json={
                    "name": "Other",
                    "content": {"description": "d", "system_prompt": "s"},
                },
                headers=_auth(other),
            )
            other_persona_id = other_persona.json()["id"]
            assert (
                client.put(
                    f"/v1/workspaces/{other_ws}/personas/{other_persona_id}/playbooks",
                    json={"playbook_ids": [first_id]},
                    headers=_auth(other),
                ).status_code
                == 404
            )

            # Workspace-Isolation: fremder Workspace sieht das Playbook nicht
            assert client.get(f"{pb_base}/{first_id}", headers=_auth(other)).status_code == 403
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_playbook_pagination_combined_with_tag_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pb_base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            tagged_ids: list[str] = []
            for i in range(3):
                resp = client.post(
                    pb_base,
                    json=_playbook_body(f"Tagged-{i}", "v1", ["alpha"], "match"),
                    headers=auth,
                )
                assert resp.status_code == 201
                tagged_ids.append(resp.json()["id"])
            # Ein Playbook mit anderem Tag, das nicht auftauchen darf.
            other_tag = client.post(
                pb_base,
                json=_playbook_body("Other", "v1", ["beta"], "other"),
                headers=auth,
            )
            assert other_tag.status_code == 201

            page1 = client.get(f"{pb_base}?tag=alpha&limit=2", headers=auth)
            assert page1.status_code == 200
            assert len(page1.json()) == 2
            cursor = page1.headers.get("X-Next-Cursor")
            assert cursor is not None
            assert {p["tags"][0] for p in page1.json()} == {"alpha"}

            page2 = client.get(f"{pb_base}?tag=alpha&limit=2&cursor={cursor}", headers=auth)
            assert page2.status_code == 200
            assert len(page2.json()) == 1
            assert "X-Next-Cursor" not in page2.headers

            seen = {p["id"] for p in page1.json()} | {p["id"] for p in page2.json()}
            assert seen == set(tagged_ids)

            assert client.get(f"{pb_base}?limit=0", headers=auth).status_code == 422
            assert client.get(f"{pb_base}?limit=201", headers=auth).status_code == 422
            assert client.get(f"{pb_base}?cursor=!!!", headers=auth).status_code == 422
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_version_transitions_and_draft_on_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            playbook_id = client.post(
                base,
                json=_playbook_body("Onboard", "v1", ["a"], "x"),
                headers=auth,
            ).json()["id"]
            # Phase 3-0: v1 startet bereits als Draft (Migration 0019); nur
            # review + active uebrig auf dem Weg nach Active.
            for to in ("review", "active"):
                resp = client.post(
                    f"{base}/{playbook_id}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )
                assert resp.status_code == 200, resp.text

            # Verbotener Uebergang: active -> review (active darf nur nach
            # inactive oder — als Reset-auf-Draft, Track A — nach draft).
            assert (
                client.post(
                    f"{base}/{playbook_id}/versions/1/transition",
                    json={"to": "review"},
                    headers=auth,
                ).status_code
                == 409
            )

            updated = client.put(
                f"{base}/{playbook_id}",
                json=_playbook_body("Onboard", "v2", ["a"], "x"),
                headers=auth,
            )
            assert updated.status_code == 200
            assert updated.json()["current_version"] == 2
            assert updated.json()["current_status"] == "draft"
            assert updated.json()["has_pending_draft"] is True

            # Zweiter PUT → 409 (Draft existiert).
            second = client.put(
                f"{base}/{playbook_id}",
                json=_playbook_body("Onboard", "v3", ["a"], "x"),
                headers=auth,
            )
            assert second.status_code == 409

            # Promotion v2 → active: v1 wird auto-inactiviert.
            client.post(
                f"{base}/{playbook_id}/versions/2/transition",
                json={"to": "review"},
                headers=auth,
            )
            client.post(
                f"{base}/{playbook_id}/versions/2/transition",
                json={"to": "active"},
                headers=auth,
            )
            versions = client.get(f"{base}/{playbook_id}/versions", headers=auth).json()
            assert {v["version"]: v["status"] for v in versions} == {
                1: "inactive",
                2: "active",
            }
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_patch_draft_upserts_in_place_without_active_touch(
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
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            pid = client.post(
                base,
                json=_playbook_body("PB", "v1", ["x"], "boot"),
                headers=auth,
            ).json()["id"]
            for to in ("review", "active"):
                client.post(f"{base}/{pid}/versions/1/transition", json={"to": to}, headers=auth)

            first = client.patch(
                f"{base}/{pid}/draft",
                json=_playbook_body("PB", "d1", ["x"], "boot"),
                headers=auth,
            )
            assert first.status_code == 200, first.text
            assert first.json()["current_version"] == 2
            assert first.json()["current_status"] == "draft"
            v1 = client.get(f"{base}/{pid}/versions/1", headers=auth).json()
            assert v1["status"] == "active"
            assert v1["content"]["description"] == "v1"

            second = client.patch(
                f"{base}/{pid}/draft",
                json=_playbook_body("PB", "d2", ["x"], "boot"),
                headers=auth,
            )
            assert second.status_code == 200
            assert second.json()["current_version"] == 2
            assert second.json()["content"]["description"] == "d2"
            versions = client.get(f"{base}/{pid}/versions", headers=auth).json()
            assert [v["version"] for v in versions] == [2, 1]

            assert (
                client.patch(
                    f"{base}/{pid}/draft",
                    json=_playbook_body("PB", "f", ["x"], "boot"),
                    headers=_auth(other),
                ).status_code
                == 403
            )
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_playbook_patch_draft_on_review_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            pid = client.post(
                base, json=_playbook_body("PB", "v1", [], "boot"), headers=auth
            ).json()["id"]
            client.post(f"{base}/{pid}/versions/1/transition", json={"to": "review"}, headers=auth)
            assert (
                client.patch(
                    f"{base}/{pid}/draft",
                    json=_playbook_body("PB", "nope", [], "boot"),
                    headers=auth,
                ).status_code
                == 409
            )
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def _agent_in(ws: UUID) -> str:
    """ID des Seed-„Builder"-Agenten (Tokens sind agent-gebunden, 0048; Builder
    hat playbook_read='all' → liest alle Playbooks)."""

    async def _run() -> str:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            agent_id = await conn.fetchval(
                "SELECT id FROM agent WHERE workspace_id = $1 LIMIT 1", ws
            )
            assert agent_id is not None, "Seed-Agent fehlt"
            return str(agent_id)
        finally:
            await conn.close()

    return asyncio.run(_run())


def test_playbook_active_filter_for_api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    agent_id = _agent_in(ws)
    jwt_auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            inactive_id = client.post(
                base,
                json=_playbook_body("Inactive", "v1", ["t"], "x"),
                headers=jwt_auth,
            ).json()["id"]
            active_id = client.post(
                base,
                json=_playbook_body("Active", "v1", ["t"], "x"),
                headers=jwt_auth,
            ).json()["id"]
            for to in ("draft", "review", "active"):
                client.post(
                    f"{base}/{active_id}/versions/1/transition",
                    json={"to": to},
                    headers=jwt_auth,
                )

            token = client.post(
                f"/v1/workspaces/{ws}/tokens",
                json={"name": "mcp", "agent_id": agent_id},
                headers=jwt_auth,
            ).json()["token"]
            token_auth = {"Authorization": f"Bearer {token}"}

            # JWT sieht beide eigenen (neben den Seed-Playbooks).
            jwt_ids = {p["id"] for p in client.get(base, headers=jwt_auth).json()}
            assert {inactive_id, active_id} <= jwt_ids

            # Token sieht NUR Active: die eigene aktive ja, die inaktive nicht,
            # und jedes sichtbare Playbook ist aktiv (Seed-Playbooks sind aktiv).
            token_list = client.get(base, headers=token_auth).json()
            token_ids = {p["id"] for p in token_list}
            assert active_id in token_ids
            assert inactive_id not in token_ids
            assert all(p["current_status"] == "active" for p in token_list)

            assert client.get(f"{base}/{inactive_id}", headers=token_auth).status_code == 404
            assert client.get(f"{base}/{active_id}", headers=token_auth).status_code == 200
    finally:
        cleanup_workspaces([owner])
