from fastapi.testclient import TestClient

from who2be_api import __version__
from who2be_api.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
