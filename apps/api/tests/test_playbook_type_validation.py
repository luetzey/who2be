"""Regressionstest: ungueltiger Playbook-`type` → sauberes 422 statt 500.

Bug: `PlaybookContent.type` war ein freier `str`, die DB hat aber einen
`playbook_type_check`-CHECK ({'', prompt, instructions, snippet, workflow,
checklist, faq}). Ein vom MCP-Agenten gesendeter Typ ausserhalb des Enums (z. B.
"guideline") schlug erst beim INSERT als CheckViolation auf → unbehandelter 500.
create_persona war nicht betroffen (kein type-Feld). Fix: `type` ist an
`PlaybookType` (∪ "") gebunden → Validierung an der API-/MCP-Grenze (422), und
das MCP-Tool-Schema annonciert die erlaubten Werte.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import PlaybookContent, PlaybookType

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"


# --- DB-frei: Modell-Validierung ------------------------------------------


def test_playbook_content_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        PlaybookContent(type="guideline")  # type: ignore[arg-type]


def test_playbook_content_accepts_enum_and_empty() -> None:
    assert PlaybookContent(type="").type == ""
    assert PlaybookContent(type="workflow").type == PlaybookType.workflow  # type: ignore[arg-type]
    # Default (Draft ohne Typ) bleibt leer.
    assert PlaybookContent().type == ""


# --- DB-Integration: ungueltiger Typ am Endpoint → 422 (frueher 500) ------


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


@pytest.mark.integration
def test_create_playbook_invalid_type_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    try:
        with TestClient(app) as client:
            resp = client.post(
                f"/v1/workspaces/{ws}/playbooks",
                json={"name": "Bad", "content": {"body": "1. Step.", "type": "guideline"}},
                headers=_auth(owner),
            )
            assert resp.status_code == 422, f"erwartet 422, war {resp.status_code}: {resp.text}"
    finally:
        cleanup_workspaces([owner])
