"""Health-Feld `worker` (ADR-0057 §7, PM-W4).

`/v1/health` meldet den Worker als `ok` (juengster `worker_heartbeat` hoechstens
5 min alt), `stale` (aelter) oder `unknown` (keine Zeile). Das Feld ist reine
Information: die Antwort bleibt 200 mit `status: ok`.

Der Endpunkttest laeuft gegen echtes Postgres in einem isolierten Schema; die
App liest den Heartbeat ueber ihren eigenen Pool, der Test schreibt ihn ueber
die Owner-Verbindung wie der Worker.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.testing.isolated_schema import isolated_schema
from who2be_api.worker import store
from who2be_api.worker.store import WORKER_STALE_AFTER, classify_worker_seen

_NOW = datetime(2026, 11, 6, 3, 30, tzinfo=UTC)


def test_classify_without_heartbeat_is_unknown() -> None:
    assert classify_worker_seen(None, _NOW) == "unknown"


def test_classify_boundary_is_still_ok() -> None:
    assert classify_worker_seen(_NOW - WORKER_STALE_AFTER, _NOW) == "ok"
    assert classify_worker_seen(_NOW - timedelta(seconds=10), _NOW) == "ok"


def test_classify_older_than_threshold_is_stale() -> None:
    seen = _NOW - WORKER_STALE_AFTER - timedelta(seconds=1)
    assert classify_worker_seen(seen, _NOW) == "stale"


async def _set_heartbeat(seen_at: datetime | None) -> None:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        await conn.execute("DELETE FROM worker_heartbeat")
        if seen_at is not None:
            await store.record_worker_heartbeat(
                conn, worker_id="health-test:1", version="t", now=seen_at
            )
    finally:
        await conn.close()


@pytest.mark.integration
def test_health_worker_field_ok_stale_unknown() -> None:
    with isolated_schema("health_worker"), TestClient(app) as client:
        first = client.get("/v1/health")
        if first.json()["db"] != "ok":
            pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

        cases = [
            (None, "unknown"),
            (datetime.now(UTC) - timedelta(seconds=5), "ok"),
            (datetime.now(UTC) - WORKER_STALE_AFTER - timedelta(minutes=1), "stale"),
        ]
        for seen_at, expected in cases:
            asyncio.run(_set_heartbeat(seen_at))
            response = client.get("/v1/health")
            assert response.status_code == 200
            body = response.json()
            assert body["worker"] == expected, seen_at
            assert body["status"] == "ok"
            assert body["db"] == "ok"
