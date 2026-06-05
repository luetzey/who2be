"""Integrationstest fuer den GDPR-Datenexport (`GET /v1/gdpr/export`, Track O)."""

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
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    seed_auth_user,
    setup_workspace,
)

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


def _persona_body() -> dict[str, object]:
    return {
        "name": "Export-Bot",
        "content": {
            "description": "exportierbar",
            "system_prompt": "Be precise.",
            "traits": ["thorough"],
            "content": {
                "description": "exportierbar",
                "blocks": [
                    {
                        "id": "b1",
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "hi", "styles": {}}],
                    }
                ],
            },
        },
    }


@pytest.mark.integration
def test_gdpr_export_bundles_user_data(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))

    owner = fresh_user_id()
    ws = setup_workspace(owner)
    seed_auth_user(owner, "export-user@example.com", name=None)
    try:
        with TestClient(app) as client:
            created = client.post(
                f"/v1/workspaces/{ws}/personas",
                json=_persona_body(),
                headers=_auth(owner),
            )
            assert created.status_code == 201
            persona_id = created.json()["id"]

            export = client.get("/v1/gdpr/export", headers=_auth(owner))
            assert export.status_code == 200
            assert "attachment" in export.headers.get("content-disposition", "")

            bundle = export.json()
            assert bundle["user_id"] == str(owner)
            assert "exported_at" in bundle

            # WP-E: account/identity-Block enthaelt die GoTrue-Email.
            assert bundle["account"]["id"] == str(owner)
            assert bundle["account"]["email"] == "export-user@example.com"

            # Personal-Org → Workspace → Persona inkl. Versionen ist enthalten.
            workspaces = [w for o in bundle["organizations"] for w in o["workspaces"]]
            target = next(w for w in workspaces if w["id"] == str(ws))
            persona_ids = {p["id"] for p in target["personas"]}
            assert persona_id in persona_ids
            exported_persona = next(p for p in target["personas"] if p["id"] == persona_id)
            assert len(exported_persona["versions"]) >= 1
            # Interne Mandanten-Spalte ist herausgefiltert.
            assert "workspace_id" not in exported_persona
    finally:
        cleanup_workspaces([owner])
