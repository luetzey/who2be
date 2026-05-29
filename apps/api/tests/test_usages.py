"""Integrationstest fuer die Reverse-Lookups (Phase 3-A).

`GET /v1/workspaces/{ws}/playbooks/{id}/usages` und
`GET /v1/workspaces/{ws}/resources/{id}/usages` muessen Backlinks korrekt
zaehlen, fremde Entities mit 404 ablehnen und auf Cross-Workspace strikt
isoliert sein.
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


def _heading(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "heading",
        "props": {"level": 1},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


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


def _persona_body(name: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {"description": "d", "system_prompt": "s"},
    }


def _resource_body(name: str, blocks: list[dict[str, object]]) -> dict[str, object]:
    return {"name": name, "content": {"description": "", "blocks": blocks}}


@pytest.mark.integration
def test_playbook_usages_lists_linking_personas(
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
    persona_base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            playbook_id = client.post(pb_base, json=_playbook_body("PB"), headers=auth).json()["id"]
            persona_a = client.post(persona_base, json=_persona_body("Alpha"), headers=auth).json()
            persona_b = client.post(persona_base, json=_persona_body("Bravo"), headers=auth).json()

            # Nur Alpha verlinkt; Bravo nicht.
            client.put(
                f"{persona_base}/{persona_a['id']}/playbooks",
                json={"playbook_ids": [playbook_id]},
                headers=auth,
            )

            usages = client.get(f"{pb_base}/{playbook_id}/usages", headers=auth)
            assert usages.status_code == 200, usages.text
            body = usages.json()
            assert [u["persona_id"] for u in body] == [persona_a["id"]]
            assert body[0]["persona_name"] == "Alpha"

            # Beide verlinkt -> beide in der Liste, sortiert nach Name.
            client.put(
                f"{persona_base}/{persona_b['id']}/playbooks",
                json={"playbook_ids": [playbook_id]},
                headers=auth,
            )
            body = client.get(f"{pb_base}/{playbook_id}/usages", headers=auth).json()
            assert [u["persona_name"] for u in body] == ["Alpha", "Bravo"]

            # Unbekanntes Playbook -> 404.
            unknown = "00000000-0000-0000-0000-000000000000"
            assert client.get(f"{pb_base}/{unknown}/usages", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_usages_groups_block_refs_by_playbook(
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
                json=_resource_body("Doc", [_heading("h1", "X"), _heading("h2", "Y")]),
                headers=auth,
            ).json()["id"]
            p1 = client.post(pbase, json=_playbook_body("Beta"), headers=auth).json()["id"]
            p2 = client.post(pbase, json=_playbook_body("Alpha"), headers=auth).json()["id"]

            # p1 referenziert 2 Bloecke; p2 referenziert 1.
            client.put(
                f"{pbase}/{p1}/resource_links",
                json={
                    "links": [
                        {"resource_id": rid, "block_id": "h1", "position": 0},
                        {"resource_id": rid, "block_id": "h2", "position": 1},
                    ]
                },
                headers=auth,
            )
            client.put(
                f"{pbase}/{p2}/resource_links",
                json={"links": [{"resource_id": rid, "block_id": "h1", "position": 0}]},
                headers=auth,
            )

            usages = client.get(f"{rbase}/{rid}/usages", headers=auth)
            assert usages.status_code == 200, usages.text
            body = usages.json()
            # Sortiert nach Playbook-Name: Alpha vor Beta.
            assert [u["playbook_name"] for u in body] == ["Alpha", "Beta"]
            counts = {u["playbook_id"]: u["block_count"] for u in body}
            assert counts == {p1: 2, p2: 1}

            # Unbekannte Resource -> 404.
            unknown = "00000000-0000-0000-0000-000000000000"
            assert client.get(f"{rbase}/{unknown}/usages", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_usages_strict_cross_workspace_isolation(
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
    auth_owner = _auth(owner)
    auth_other = _auth(other)

    try:
        with TestClient(app) as client:
            # Setup im Owner-Workspace: Playbook + Persona-Link, Resource + Block-Ref.
            pb_base = f"/v1/workspaces/{ws}/playbooks"
            persona_base = f"/v1/workspaces/{ws}/personas"
            rbase = f"/v1/workspaces/{ws}/resources"
            pid = client.post(pb_base, json=_playbook_body("PB"), headers=auth_owner).json()["id"]
            persona = client.post(persona_base, json=_persona_body("P"), headers=auth_owner).json()
            client.put(
                f"{persona_base}/{persona['id']}/playbooks",
                json={"playbook_ids": [pid]},
                headers=auth_owner,
            )
            rid = client.post(
                rbase,
                json=_resource_body("Doc", [_heading("h1", "X")]),
                headers=auth_owner,
            ).json()["id"]
            client.put(
                f"{pb_base}/{pid}/resource_links",
                json={"links": [{"resource_id": rid, "block_id": "h1", "position": 0}]},
                headers=auth_owner,
            )

            # Owner sieht Backlinks.
            assert len(client.get(f"{pb_base}/{pid}/usages", headers=auth_owner).json()) == 1
            assert len(client.get(f"{rbase}/{rid}/usages", headers=auth_owner).json()) == 1

            # Anderer Workspace: Lookup auf dieselbe Playbook-/Resource-ID -> 404,
            # weil sie nicht in `other_ws` existiert.
            other_pb = f"/v1/workspaces/{other_ws}/playbooks"
            other_r = f"/v1/workspaces/{other_ws}/resources"
            assert client.get(f"{other_pb}/{pid}/usages", headers=auth_other).status_code == 404
            assert client.get(f"{other_r}/{rid}/usages", headers=auth_other).status_code == 404

            # Owner-Workspace mit anderem User (kein Member) -> 403 vorm Lookup.
            assert client.get(f"{pb_base}/{pid}/usages", headers=auth_other).status_code == 403
            assert client.get(f"{rbase}/{rid}/usages", headers=auth_other).status_code == 403
    finally:
        cleanup_workspaces([owner, other])
