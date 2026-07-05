"""Integrationstests fuer Track A — Versionierung-Core.

Deckt Restore (non-destruktiv → neue Draft), Diff (against=active),
Provenance (status_history-Kette einer Version) und Reset-auf-Draft
(Reaktivierung der zuletzt aktiven Version) ueber die vier versionierten
Entitaeten ab. Laeuft nur mit erreichbarer Datenbank; ohne DB → Skip.
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


def _playbook_body(description: str, body: str = "") -> dict[str, object]:
    return {
        "name": "Onboard",
        "content": {
            "description": description,
            "body": body,
            "type": "workflow",
            "tags": ["a"],
            "triggers": "x",
        },
    }


def _to(
    client: TestClient,
    base: str,
    pid: str,
    version: int,
    status: str,
    auth: dict[str, str],
) -> httpx.Response:
    resp: httpx.Response = client.post(
        f"{base}/{pid}/versions/{version}/transition", json={"to": status}, headers=auth
    )
    return resp


@pytest.mark.integration
def test_playbook_diff_and_restore_and_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
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
            pid = client.post(base, json=_playbook_body("v1", "body one"), headers=auth).json()[
                "id"
            ]
            assert _to(client, base, pid, 1, "review", auth).status_code == 200
            assert _to(client, base, pid, 1, "active", auth).status_code == 200

            # Edit auf Active → v2 Draft mit geaendertem Body.
            v2 = client.put(f"{base}/{pid}", json=_playbook_body("v2", "body two"), headers=auth)
            assert v2.status_code == 200
            assert v2.json()["current_version"] == 2

            # Diff v2 gegen active (=v1): description + body geaendert.
            diff = client.get(f"{base}/{pid}/versions/2/diff?against=active", headers=auth)
            assert diff.status_code == 200, diff.text
            payload = diff.json()
            assert payload["against_version"] == 1
            assert payload["identical"] is False
            paths = {c["path"]: c for c in payload["changes"]}
            assert paths["body"]["before"] == "body one"
            assert paths["body"]["after"] == "body two"
            assert "description" in paths

            # Restore v1 bei offenem Draft (v2) → 409.
            assert client.post(f"{base}/{pid}/versions/1/restore", headers=auth).status_code == 409

            # Promote v2 → active, danach Restore v1 → v3 Draft mit v1-Body.
            assert _to(client, base, pid, 2, "review", auth).status_code == 200
            assert _to(client, base, pid, 2, "active", auth).status_code == 200
            restored = client.post(f"{base}/{pid}/versions/1/restore", headers=auth)
            assert restored.status_code == 201, restored.text
            assert restored.json()["current_version"] == 3
            assert restored.json()["current_status"] == "draft"
            assert restored.json()["content"]["body"] == "body one"

            # Provenance v1: enthaelt die Kette bis 'active' (warum aktiv).
            prov = client.get(f"{base}/{pid}/versions/1/provenance", headers=auth)
            assert prov.status_code == 200
            episodes = prov.json()
            assert any(e["to_status"] == "active" for e in episodes)
            assert all(e["version"] == 1 for e in episodes)
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_reset_reactivates_previous_active(monkeypatch: pytest.MonkeyPatch) -> None:
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
            pid = client.post(base, json=_playbook_body("v1", "one"), headers=auth).json()["id"]
            assert _to(client, base, pid, 1, "review", auth).status_code == 200
            assert _to(client, base, pid, 1, "active", auth).status_code == 200
            client.put(f"{base}/{pid}", json=_playbook_body("v2", "two"), headers=auth)
            assert _to(client, base, pid, 2, "review", auth).status_code == 200
            assert _to(client, base, pid, 2, "active", auth).status_code == 200

            # Reset-auf-Draft: v2 (active) → draft reaktiviert v1.
            reset = _to(client, base, pid, 2, "draft", auth)
            assert reset.status_code == 200, reset.text

            versions = {
                v["version"]: v["status"]
                for v in client.get(f"{base}/{pid}/versions", headers=auth).json()
            }
            assert versions[2] == "draft"
            assert versions[1] == "active"

            # Provenance v1 dokumentiert die Reaktivierung (inactive→active).
            prov = client.get(f"{base}/{pid}/versions/1/provenance", headers=auth).json()
            assert any(e["from_status"] == "inactive" and e["to_status"] == "active" for e in prov)
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_block_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    def block(bid: str, text: str) -> dict[str, object]:
        return {
            "id": bid,
            "type": "paragraph",
            "content": [{"type": "text", "text": text, "styles": {}}],
        }

    def body(desc: str, blocks: list[dict[str, object]]) -> dict[str, object]:
        return {"name": "Doc", "content": {"description": desc, "blocks": blocks}}

    try:
        with TestClient(app) as client:
            rid = client.post(base, json=body("v1", [block("b1", "x")]), headers=auth).json()["id"]
            assert _to(client, base, rid, 1, "review", auth).status_code == 200
            assert _to(client, base, rid, 1, "active", auth).status_code == 200
            client.put(
                f"{base}/{rid}", json=body("v1", [block("b1", "y"), block("b2", "z")]), headers=auth
            )

            diff = client.get(f"{base}/{rid}/versions/2/diff", headers=auth).json()
            ops = {c["path"]: c["op"] for c in diff["changes"]}
            assert ops["blocks[b1]"] == "changed"
            assert ops["blocks[b2]"] == "added"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_persona_and_template_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    def persona_body(desc: str) -> dict[str, object]:
        return {
            "name": "QA",
            "content": {
                "description": desc,
                "content": {
                    "description": desc,
                    "blocks": [
                        {
                            "id": "b1",
                            "type": "paragraph",
                            "content": [{"type": "text", "text": desc, "styles": {}}],
                        }
                    ],
                },
            },
        }

    try:
        with TestClient(app) as client:
            # Persona: v1 active → restore v1 → v2 Draft.
            pbase = f"/v1/workspaces/{ws}/personas"
            pid = client.post(pbase, json=persona_body("v1"), headers=auth).json()["id"]
            assert _to(client, pbase, pid, 1, "review", auth).status_code == 200
            assert _to(client, pbase, pid, 1, "active", auth).status_code == 200
            r = client.post(f"{pbase}/{pid}/versions/1/restore", headers=auth)
            assert r.status_code == 201, r.text
            assert r.json()["current_status"] == "draft"
            assert r.json()["content"]["description"] == "v1"

            # Template: v1 active → restore v1 → v2 Draft.
            tbase = f"/v1/workspaces/{ws}/system-prompts"
            tid = client.post(
                tbase,
                json={"name": "Tpl", "content": {"description": "", "body": "hello"}},
                headers=auth,
            ).json()["id"]
            assert _to(client, tbase, tid, 1, "review", auth).status_code == 200
            assert _to(client, tbase, tid, 1, "active", auth).status_code == 200
            tr = client.post(f"{tbase}/{tid}/versions/1/restore", headers=auth)
            assert tr.status_code == 201, tr.text
            assert tr.json()["current_status"] == "draft"
            assert tr.json()["content"]["body"] == "hello"
            tdiff = client.get(f"{tbase}/{tid}/versions/2/diff", headers=auth).json()
            assert tdiff["identical"] is True
    finally:
        cleanup_workspaces([owner])
