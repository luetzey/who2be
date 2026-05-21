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
