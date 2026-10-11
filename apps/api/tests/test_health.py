from fastapi.testclient import TestClient

from who2be_api import __version__
from who2be_api.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["db"] in {"ok", "unavailable"}
    assert body["worker"] in {"ok", "stale", "unknown"}


def test_health_worker_unknown_without_db_pool() -> None:
    # Ohne Lifespan gibt es keinen Pool: das Feld faellt auf `unknown`, die
    # Antwort bleibt 200 und `status` gruen.
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "unavailable"
    assert body["worker"] == "unknown"
