"""Integrationstests fuer Track B — Nur-BlockNote.

Prueft, dass die seitens Migration 0030 + Runtime-Seed bereitgestellten
Default-Templates valides BlockNote-JSON mit Placeholder-Pills sind und der
Render-Pfad sie (ohne body_format) zu Plain-Text expandiert.
"""

import asyncio
import json
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


def _has_placeholder(blocks: list[dict[str, object]]) -> bool:
    for block in blocks:
        content = block.get("content")
        if not isinstance(content, list):
            continue
        for inline in content:
            if isinstance(inline, dict) and inline.get("type") == "placeholder":
                return True
    return False


@pytest.mark.integration
def test_default_templates_are_blocknote_with_pills(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            templates = client.get(f"/v1/workspaces/{ws}/system-prompts", headers=auth).json()
            by_slug = {t["slug"]: t for t in templates}
            for slug in (
                "customer-support-agent",
                "knowledge-worker",
                "conversational-coach",
                "workflow-starter",
            ):
                assert slug in by_slug, f"Default-Template {slug} fehlt."
                tpl = by_slug[slug]
                # Kein body_format-Feld mehr in der Read-Antwort (Track B).
                assert "body_format" not in tpl
                blocks = json.loads(tpl["content"]["body"])
                assert isinstance(blocks, list) and blocks, f"{slug}: kein BlockNote-Array."
                assert _has_placeholder(blocks), f"{slug}: keine Placeholder-Pill."
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_default_template_renders_persona_name(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    persona_body = {
        "name": "Aurora",
        "content": {
            "description": "Senior Support",
            "content": {
                "description": "",
                "blocks": [
                    {
                        "id": "b1",
                        "type": "paragraph",
                        "props": {},
                        "content": [{"type": "text", "text": "Ruhig und klar.", "styles": {}}],
                        "children": [],
                    }
                ],
            },
        },
    }

    def _promote(base: str, eid: str) -> None:
        for to in ("review", "active"):
            client.post(
                f"{base}/{eid}/versions/1/transition", json={"to": to}, headers=auth
            )

    try:
        with TestClient(app) as client:
            persona = client.post(
                f"/v1/workspaces/{ws}/personas", json=persona_body, headers=auth
            ).json()
            _promote(f"/v1/workspaces/{ws}/personas", persona["id"])

            templates = client.get(f"/v1/workspaces/{ws}/system-prompts", headers=auth).json()
            tpl_id = next(t["id"] for t in templates if t["slug"] == "customer-support-agent")

            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={
                    "name": "A1",
                    "description": "",
                    "persona_id": persona["id"],
                    "system_prompt_template_id": tpl_id,
                },
                headers=auth,
            ).json()

            rendered = client.get(
                f"/v1/workspaces/{ws}/agents/{agent['id']}/render", headers=auth
            ).json()
            # persona-field:name + :description Pills sind expandiert.
            assert "Aurora" in rendered["content"]
            assert "Senior Support" in rendered["content"]
    finally:
        cleanup_workspaces([owner])
