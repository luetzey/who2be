"""Endpoint-Tests fuer den Cloud-Manual-Override (`who2be_billing/router.py`).

Geprueft werden die DB-freien Pfade: On-Prem ⇒ 404 (Billing-Paket nicht
registriert), Nicht-Admin ⇒ 403, unbekannter Plan ⇒ 422 und die Pflicht-Befristung
(`days`) + Pflicht-`reason` ⇒ 422 (Pydantic). Der erfolgreiche Upsert-Pfad ist
integration-gated und hier nicht abgedeckt.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.main import create_app
from who2be_models import WorkspaceRole


def _admin_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=False,
        aal="aal2",
    )


def _viewer_ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(), user_id=uuid4(), role=WorkspaceRole.viewer, is_api_token=False
    )


@pytest.fixture
def cloud_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    monkeypatch.setenv("WHO2BE_EDITION", "cloud")
    get_settings.cache_clear()
    app = create_app()
    yield app
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _post(app: FastAPI, body: dict[str, object]) -> int:
    with TestClient(app) as client:
        resp: httpx.Response = client.post(
            f"/v1/workspaces/{uuid4()}/billing/override",
            json=body,
            headers={"Authorization": "Bearer w2b_dummy"},
        )
    return resp.status_code


def test_override_rejects_non_admin(cloud_app: FastAPI) -> None:
    cloud_app.dependency_overrides[get_current_workspace] = _viewer_ctx
    assert _post(cloud_app, {"plan": "pro", "days": 30, "reason": "Kulanz"}) == 403


def test_override_rejects_unknown_plan(cloud_app: FastAPI) -> None:
    cloud_app.dependency_overrides[get_current_workspace] = _admin_ctx
    assert _post(cloud_app, {"plan": "unobtanium", "days": 30, "reason": "Kulanz"}) == 422


def test_override_requires_bounded_duration(cloud_app: FastAPI) -> None:
    cloud_app.dependency_overrides[get_current_workspace] = _admin_ctx
    # days=0 (nicht > 0) und days=999 (> 365) sind beide unzulaessig.
    assert _post(cloud_app, {"plan": "pro", "days": 0, "reason": "x"}) == 422
    assert _post(cloud_app, {"plan": "pro", "days": 999, "reason": "Kulanz"}) == 422


def test_override_requires_reason(cloud_app: FastAPI) -> None:
    cloud_app.dependency_overrides[get_current_workspace] = _admin_ctx
    assert _post(cloud_app, {"plan": "pro", "days": 30}) == 422


def test_override_404_on_onprem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHO2BE_EDITION", "onprem")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_current_workspace] = _admin_ctx
    try:
        status_code = _post(app, {"plan": "pro", "days": 30, "reason": "Kulanz"})
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
    # On-Prem ist das Billing-Paket nicht registriert ⇒ Route existiert nicht.
    assert status_code == 404
