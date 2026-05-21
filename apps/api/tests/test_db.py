"""Tests rund um den asyncpg-Pool und den Lifespan-Start.

Der Integrationstest laeuft nur mit erreichbarer Datenbank (CI-postgres-
Service bzw. lokales `docker compose up -d`); ohne DB wird er uebersprungen.
"""

import logging

import pytest
from fastapi.testclient import TestClient

from who2be_api.core import db
from who2be_api.core.config import Settings
from who2be_api.main import app


@pytest.mark.integration
def test_health_reports_db_ok_with_lifespan() -> None:
    # TestClient als Contextmanager startet den Lifespan -> Pool wird gebaut.
    with TestClient(app) as client:
        body = client.get("/v1/health").json()
    if body["db"] != "ok":
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    assert body["db"] == "ok"


def test_lifespan_warns_on_weak_jwt_secret(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(db, "get_settings", lambda: Settings(jwt_secret=""))
    with caplog.at_level(logging.WARNING), TestClient(app):
        pass
    assert any("JWT_SECRET" in record.message for record in caplog.records)

