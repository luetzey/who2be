"""Tests fuer den Placeholder-Kind-Katalog (WP-A).

Unit: der statische Katalog ist vollstaendig (exakt die REGISTRY-Kinds, gleiche
Reihenfolge) und in sich konsistent (Beispiel-Inline traegt den eigenen Kind;
enumerierte `target_id_values` enthalten den Beispiel-Wert).

Integration: `GET /v1/workspaces/{ws}/placeholders` ist membership-gegated
(401 ohne Token) und liefert den vollstaendigen Katalog.
"""

from __future__ import annotations

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
from who2be_api.services.placeholders.kind_catalog import placeholder_catalog
from who2be_api.services.placeholders.registry import REGISTRY
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"


def test_catalog_covers_exactly_the_registry_kinds() -> None:
    """Vollstaendigkeits-Invariante: neuer Resolver ohne Katalog-Eintrag (oder
    umgekehrt) bricht hier — der Katalog ist die Laufzeit-Doku der REGISTRY."""
    catalog = placeholder_catalog()
    assert [info.kind for info in catalog.kinds] == list(REGISTRY)


def test_catalog_entries_are_self_consistent() -> None:
    for info in placeholder_catalog().kinds:
        assert info.example.type == "placeholder"
        assert info.example.props.kind == info.kind
        assert info.description
        assert info.target_id_semantics
        assert info.example.props.label
        if info.target_id_values:
            assert info.example.props.target_id in info.target_id_values, info.kind


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
def test_placeholder_catalog_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    base = f"/v1/workspaces/{ws}/placeholders"

    try:
        with TestClient(app) as client:
            # Unauthentifiziert -> 401 (membership-gegated wie die anderen Reads).
            assert client.get(base).status_code == 401

            res = client.get(base, headers=_auth(owner))
            assert res.status_code == 200
            kinds = {entry["kind"] for entry in res.json()["kinds"]}
            assert kinds == set(REGISTRY)
            # Beispiel-Inline ist gebrauchsfertiges Placeholder-JSON.
            first = res.json()["kinds"][0]
            assert first["example"]["type"] == "placeholder"
            assert set(first["example"]["props"]) == {"kind", "target_id", "label"}
    finally:
        cleanup_workspaces([owner])
