"""Integrationstest fuer `GET /v1/workspaces/{ws}/personas/tags` (Phase 3-A).

DISTINCT-sortierte Tag-Liste fuer den Tag-Picker im Persona-Editor. Persona-
Tags liegen im Versions-JSON statt denormalisiert auf der Identitaets-Zeile
— Cross-Workspace-Isolation ist explizit Teil des Vertrags.
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


def _persona_body(name: str, tags: list[str]) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "system_prompt": "Sei hilfsbereit.",
            "traits": [],
            "tags": tags,
        },
    }


@pytest.mark.integration
def test_persona_tags_distinct_sorted_and_workspace_scoped(
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
    other_auth = _auth(other)
    base = f"/v1/workspaces/{ws}/personas"
    other_base = f"/v1/workspaces/{other_ws}/personas"

    try:
        with TestClient(app) as client:
            # Neue Workspaces sind NICHT leer: der Onboarding-Seed legt die
            # „Builder"-Persona mit Tags an. Baseline dynamisch erfassen und das
            # Delta pruefen — robust gegen Aenderungen am Seed-Inhalt.
            baseline = client.get(f"{base}/tags", headers=auth).json()

            # Owner-Workspace: drei Personae mit ueberlappenden Tags + 1 ohne Tags.
            for tags in [["beta", "alpha"], ["beta", "gamma"], [], ["alpha"]]:
                resp = client.post(
                    base,
                    json=_persona_body(f"P-{','.join(tags) or 'none'}", tags),
                    headers=auth,
                )
                assert resp.status_code == 201, resp.text

            # Fremder Workspace: anderer Tag, darf nicht in der Owner-Liste auftauchen.
            client.post(other_base, json=_persona_body("Other", ["delta"]), headers=other_auth)

            resp = client.get(f"{base}/tags", headers=auth)
            assert resp.status_code == 200, resp.text
            # Distinct + sortiert + workspace-scoped: Seed-Baseline plus die
            # eigenen Tags, OHNE das fremde `delta`.
            assert resp.json() == sorted(set(baseline) | {"alpha", "beta", "gamma"})

            # Fremder Workspace (gleicher Seed) bekommt seine Baseline + `delta`,
            # NICHT die Owner-Tags.
            other_resp = client.get(f"{other_base}/tags", headers=other_auth)
            assert other_resp.json() == sorted(set(baseline) | {"delta"})

            # Nicht-Mitglied wird vor dem Lookup geblockt (403).
            assert client.get(f"{base}/tags", headers=other_auth).status_code == 403
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_persona_tags_only_seed_baseline_for_fresh_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein frischer Workspace hat keine NUTZER-Personae, aber die vom Onboarding
    geseedete „Builder"-Persona — die Tag-Liste ist daher die Seed-Baseline
    (sortiert, distinct), nicht leer. Aendert sich der Seed, gehoert dieser Wert
    mit angepasst."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            resp = client.get(f"/v1/workspaces/{ws}/personas/tags", headers=auth)
            assert resp.status_code == 200
            assert resp.json() == ["agent-building", "crud", "meta-agent"]
    finally:
        cleanup_workspaces([owner])
