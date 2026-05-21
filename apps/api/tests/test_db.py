"""Integrationstest fuer den asyncpg-Pool.

Laeuft nur mit erreichbarer Datenbank (CI-postgres-Service bzw. lokales
`docker compose up -d`); ohne DB wird der Test uebersprungen.
"""

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app


@pytest.mark.integration
def test_health_reports_db_ok_with_lifespan() -> None:
    # TestClient als Contextmanager startet den Lifespan -> Pool wird gebaut.
    with TestClient(app) as client:
        body = client.get("/v1/health").json()
    if body["db"] != "ok":
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    assert body["db"] == "ok"
