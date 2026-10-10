"""Router `GET /v1/system/routines` (ADR-0057 §7 mit Nachtrag 2026-10-10, Paket P4c).

Die Route ist workspace-uebergreifend und nur fuer Betreiber da. Belegt wird
die Zugangsregel in beiden Editionen, ohne DB ueber Dependency-Overrides:

- Betreiber (gelistet, aal2) ⇒ 200, Cloud und On-Prem;
- Org-Admin einer Kunden-Org, der nicht gelistet ist ⇒ 403 (W2: keine Zaehler
  in Kunden-Admin-Sichten), ebenso leere Allowlist und API-Token;
- Betreiber ohne MFA (aal1, in der Cloud auch ohne aal-Claim) ⇒ 403;
- ungueltiger `WHO2BE_ROUTINE_*`-Override ⇒ 503 mit Variablennamen, kein 500.

On-Prem gilt seit dem Nachtrag 2026-10-10 (Owner E2a) dieselbe Allowlist wie
in der Cloud; die urspruengliche Regel „Org-Admin der Bootstrap-Org“ ist dort
ersetzt. Der On-Prem-Fall belegt deshalb: der gelistete Betreiber kommt durch,
ein nicht gelisteter Org-Admin nicht.

Dazu ein Integrationstest ueber den echten Weg (JWT, Pool, App-Rolle) in einem
Wegwerf-Schema: ein Lauf, den der Worker schreibt, steht in der Antwort.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.operators import OPERATORS_ENV
from who2be_api.core.security import CurrentPrincipal, get_current_principal
from who2be_api.main import app as real_app
from who2be_api.main import create_app
from who2be_api.routers import system_routines
from who2be_api.testing.isolated_schema import isolated_schema
from who2be_api.worker import store
from who2be_api.worker.schedule import schedule_env_key
from who2be_models import RoutinesOverview

_URL = "/v1/system/routines"
OPERATOR_ID = UUID("00000000-0000-4000-8000-0000000000a1")
_EMPTY = RoutinesOverview(routines=[], worker_last_seen_at=None)


class _FakePool:
    """Nur `acquire()`; die Verbindung sieht die gepatchte Uebersicht nie an."""

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[object]:
        yield object()


def _principal(
    user_id: UUID = OPERATOR_ID, *, aal: str | None = "aal2", token: bool = False
) -> CurrentPrincipal:
    return CurrentPrincipal(
        user_id=user_id,
        token_workspace_id=uuid4() if token else None,
        aal=None if token else aal,
    )


def _make_app(monkeypatch: pytest.MonkeyPatch, edition: str) -> Iterator[FastAPI]:
    monkeypatch.setenv("WHO2BE_EDITION", edition)
    monkeypatch.delenv(OPERATORS_ENV, raising=False)
    monkeypatch.delenv("WHO2BE_REQUIRE_MFA_ONPREM", raising=False)
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_pool] = _FakePool
    yield app
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def cloud_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    yield from _make_app(monkeypatch, "cloud")


@pytest.fixture
def onprem_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    yield from _make_app(monkeypatch, "onprem")


@pytest.fixture
def overview_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Ersetzt die Daten-Schicht; die Liste zaehlt, ob sie aufgerufen wurde."""
    calls: list[dict[str, Any]] = []

    async def _fake(conn: object, **kwargs: Any) -> RoutinesOverview:
        calls.append(kwargs)
        return _EMPTY

    monkeypatch.setattr(system_routines, "routines_overview", _fake)
    return calls


def _get(app: FastAPI, principal: CurrentPrincipal) -> Any:
    app.dependency_overrides[get_current_principal] = lambda: principal
    with TestClient(app) as client:
        return client.get(_URL, headers={"Authorization": "Bearer x"})


def test_cloud_operator_gets_overview(
    cloud_app: FastAPI, overview_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPERATORS_ENV, f"{uuid4()}, {OPERATOR_ID}")
    resp = _get(cloud_app, _principal())
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"routines": [], "worker_last_seen_at": None}
    assert len(overview_calls) == 1


def test_customer_org_admin_is_rejected(
    cloud_app: FastAPI, overview_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """W2: ein Admin einer Kunden-Org ist kein Betreiber und sieht nichts."""
    monkeypatch.setenv(OPERATORS_ENV, str(OPERATOR_ID))
    resp = _get(cloud_app, _principal(uuid4()))
    assert resp.status_code == 403
    assert OPERATORS_ENV in resp.json()["detail"]
    assert overview_calls == []


def test_api_token_is_rejected_even_for_listed_owner(
    cloud_app: FastAPI, overview_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPERATORS_ENV, str(OPERATOR_ID))
    resp = _get(cloud_app, _principal(token=True))
    assert resp.status_code == 403
    assert overview_calls == []


def test_empty_allowlist_rejects_everyone(
    cloud_app: FastAPI, overview_calls: list[dict[str, Any]]
) -> None:
    resp = _get(cloud_app, _principal())
    assert resp.status_code == 403
    assert overview_calls == []


@pytest.mark.parametrize("aal", ["aal1", None])
def test_cloud_operator_without_mfa_is_rejected(
    cloud_app: FastAPI,
    overview_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    aal: str | None,
) -> None:
    """Betreiberdaten nur mit MFA; in der Cloud zaehlt ein fehlender Claim als fehlende MFA."""
    monkeypatch.setenv(OPERATORS_ENV, str(OPERATOR_ID))
    resp = _get(cloud_app, _principal(aal=aal))
    assert resp.status_code == 403
    assert resp.json()["reason"] == "mfa_required"
    assert overview_calls == []


def test_onprem_operator_gets_overview(
    onprem_app: FastAPI, overview_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """On-Prem gilt dieselbe Allowlist (Nachtrag 2026-10-10, E2a)."""
    monkeypatch.setenv(OPERATORS_ENV, str(OPERATOR_ID))
    resp = _get(onprem_app, _principal())
    assert resp.status_code == 200, resp.text
    assert len(overview_calls) == 1


def test_onprem_unlisted_org_admin_is_rejected(
    onprem_app: FastAPI, overview_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPERATORS_ENV, str(OPERATOR_ID))
    resp = _get(onprem_app, _principal(uuid4()))
    assert resp.status_code == 403
    assert overview_calls == []


def test_onprem_operator_with_aal1_is_rejected(
    onprem_app: FastAPI, overview_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein expliziter Nicht-aal2-Wert sperrt auch On-Prem (wie `require_aal2`)."""
    monkeypatch.setenv(OPERATORS_ENV, str(OPERATOR_ID))
    resp = _get(onprem_app, _principal(aal="aal1"))
    assert resp.status_code == 403
    assert resp.json()["reason"] == "mfa_required"
    assert overview_calls == []


def test_invalid_schedule_override_is_503_not_500(
    cloud_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein kaputter Override geht durch den echten Service bis zur `ScheduleError`."""
    key = schedule_env_key("purge")
    monkeypatch.setenv(OPERATORS_ENV, str(OPERATOR_ID))
    monkeypatch.setenv(key, "kein cron")
    cloud_app.dependency_overrides[get_current_principal] = lambda: _principal()
    with TestClient(cloud_app, raise_server_exceptions=False) as client:
        resp = client.get(_URL, headers={"Authorization": "Bearer x"})
    assert resp.status_code == 503, resp.text
    detail = resp.json()["detail"]
    assert key in detail
    assert "ADR-0057" in detail


# --- Integration: echter JWT, echter Pool ----------------------------------


def _operator_jwt(secret: str, user_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "aal": "aal2",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_run(started: datetime) -> None:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        run_id = await store.claim_slot(
            conn, "purge", started, trigger="cli", worker_id="router-test:1", now=started
        )
        assert run_id is not None
        await store.finish_run(
            conn, run_id, "succeeded", result={"deleted": 3}, now=started + timedelta(seconds=2)
        )
    finally:
        await conn.close()


@pytest.mark.integration
def test_operator_reads_worker_runs_end_to_end(
    patched_jwt_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(OPERATORS_ENV, str(OPERATOR_ID))
    started = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=5)
    with isolated_schema("system_routines"):
        asyncio.run(_seed_run(started))
        with TestClient(real_app) as client:
            ok = client.get(_URL, headers=_operator_jwt(patched_jwt_secret, OPERATOR_ID))
            other = client.get(_URL, headers=_operator_jwt(patched_jwt_secret, uuid4()))

    assert ok.status_code == 200, ok.text
    by_name = {r["name"]: r for r in ok.json()["routines"]}
    assert "purge" in by_name
    last = by_name["purge"]["last_run"]
    assert last["status"] == "succeeded"
    assert last["trigger"] == "cli"
    assert last["result"] == {"deleted": 3}
    assert last["duration_ms"] == 2000
    assert other.status_code == 403
