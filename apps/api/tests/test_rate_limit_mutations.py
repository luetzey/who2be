"""Integrationstest fuer Rate-Limiting auf den zuvor ungedeckelten Mutationen.

Schliesst F-Phase2-01 (`docs/security-findings-phase-2.md` §8): jeder
mutierende Member-/Link-/Composition-/Resource-Link-Endpoint sowie die
Revoke-/Workspace-Mgmt-Pfade tragen jetzt `@limiter.limit(write_limit)`.

Pro Endpunkt wird belegt, dass der Limiter greift: bei `1/minute` darf der
erste Aufruf durch (Status != 429, egal ob 200/204/404/409), der zweite
muss 429 liefern. slowapi bucketet hier mit `key_style="url"` pro
(Token, Request-URL), daher bekommt jeder Endpunkt einen frischen
Owner/Workspace und der Limiter-State wird zwischen den Tests zurueckgesetzt.

Setup analog `test_rate_limit.py`: nur mit erreichbarer DB; ohne DB Skip.
"""

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient
from httpx import Response

from who2be_api.core import rate_limit, security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"
_TEST_LIMIT = "1/minute"


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


@pytest.fixture(autouse=True)
def _reset_limiter() -> Iterator[None]:
    """Limiter ist Modul-Singleton; State muss zwischen Tests weg."""
    rate_limit.limiter.reset()
    yield
    rate_limit.limiter.reset()


def _override_settings(monkeypatch: pytest.MonkeyPatch, limit: str) -> None:
    settings = Settings(jwt_secret=_TEST_SECRET, rate_limit_write=limit)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(rate_limit, "get_settings", lambda: settings)


# Builder-Signatur: (client, ws, auth, rid) -> Response. `rid` ist eine pro Test
# einmal gezogene UUID, die beide Aufrufe teilen — wichtig, weil der Limiter mit
# `key_style="url"` pro voller Request-URL bucketet; ein wechselnder Pfad-Param
# laege in getrennten Buckets und liefe nie ins Limit. Ziel-IDs existieren nicht
# (404/409), das ist hier egal: der Limiter greift VOR dem Handler-Body.
_Builder = Callable[[TestClient, str, dict[str, str], str], Response]

_MUTATIONS: list[tuple[str, _Builder]] = [
    (
        "members_patch",
        lambda c, ws, auth, rid: c.patch(
            f"/v1/workspaces/{ws}/members/{rid}", json={"role": "editor"}, headers=auth
        ),
    ),
    (
        "members_delete",
        lambda c, ws, auth, rid: c.delete(f"/v1/workspaces/{ws}/members/{rid}", headers=auth),
    ),
    (
        "persona_playbooks_put",
        lambda c, ws, auth, rid: c.put(
            f"/v1/workspaces/{ws}/personas/{rid}/playbooks",
            json={"playbook_ids": []},
            headers=auth,
        ),
    ),
    (
        "playbook_composition_put",
        lambda c, ws, auth, rid: c.put(
            f"/v1/workspaces/{ws}/playbooks/{rid}/composes",
            json={"child_ids": []},
            headers=auth,
        ),
    ),
    (
        "workspaces_patch",
        lambda c, ws, auth, rid: c.patch(
            f"/v1/workspaces/{ws}", json={"name": "Renamed"}, headers=auth
        ),
    ),
    (
        # Loescht nicht wirklich: Personal-Org-Guard liefert 409 (letzter Workspace).
        "workspaces_delete",
        lambda c, ws, auth, rid: c.delete(f"/v1/workspaces/{ws}", headers=auth),
    ),
    (
        "invitations_delete",
        lambda c, ws, auth, rid: c.delete(f"/v1/workspaces/{ws}/invitations/{rid}", headers=auth),
    ),
    (
        "tokens_delete",
        lambda c, ws, auth, rid: c.delete(f"/v1/workspaces/{ws}/tokens/{rid}", headers=auth),
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize("name,call", _MUTATIONS, ids=[m[0] for m in _MUTATIONS])
def test_mutation_endpoint_is_rate_limited(
    name: str,
    call: _Builder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    _override_settings(monkeypatch, _TEST_LIMIT)

    owner = fresh_user_id()
    ws = str(setup_workspace(owner))
    auth = _auth(owner)
    rid = str(uuid4())

    try:
        with TestClient(app) as client:
            first = call(client, ws, auth, rid)
            second = call(client, ws, auth, rid)
            # Erster Aufruf darf durch (Status haengt vom Handler ab), zweiter
            # ueberschreitet das 1/minute-Limit.
            assert first.status_code != 429, f"{name}: erster Aufruf bereits 429"
            assert second.status_code == 429, f"{name}: Limit greift nicht ({second.status_code})"
    finally:
        cleanup_workspaces([owner])
