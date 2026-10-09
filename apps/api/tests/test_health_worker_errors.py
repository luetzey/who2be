"""Health-Feld `worker`: Fehlerpfade (ADR-0057 §7, Review PR #893).

Das Feld ist reine Information. Weder ein DB-Fehler noch ein schliessender Pool
noch eine haengende Abfrage (z. B. ein Lock auf `worker_heartbeat`) duerfen
`/v1/health` brechen oder ueber den Container-Healthcheck-Timeout (5 s) hinaus
aufhalten: erwartet sind 200, `status: ok`, `worker: unknown`.

Der Pool ist ein Fake, damit `db` `ok` meldet (wie im belegten Lock-Fall, in
dem `ping()` die Tabelle nicht liest) und nur `worker_health` gestoert wird.
Ein Integrationstest haelt zusaetzlich einen echten ACCESS-EXCLUSIVE-Lock.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api import main
from who2be_api.core.config import get_settings
from who2be_api.core.db import database
from who2be_api.main import WORKER_HEALTH_TIMEOUT_S, app
from who2be_api.testing.isolated_schema import isolated_schema

#: Spielraum ueber der Zeitgrenze fuer Event-Loop und HTTP-Roundtrip.
_SLACK_S = 1.0
#: Der Container-Healthcheck bricht nach 5 s ab (docker-compose.yml).
_HEALTHCHECK_TIMEOUT_S = 5.0


class _FakeConn:
    async def execute(self, *_args: Any) -> str:
        return "SELECT 1"


class _FakePool:
    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[_FakeConn]:
        yield _FakeConn()


@pytest.fixture
def fake_pool(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(database, "_pool", _FakePool())
    yield


def _get_health() -> tuple[dict[str, Any], float]:
    client = TestClient(app)
    started = time.monotonic()
    response = client.get("/v1/health")
    elapsed = time.monotonic() - started
    assert response.status_code == 200
    return response.json(), elapsed


def _assert_unknown(body: dict[str, Any]) -> None:
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["worker"] == "unknown"


def test_timeout_stays_below_container_healthcheck() -> None:
    assert WORKER_HEALTH_TIMEOUT_S + _SLACK_S < _HEALTHCHECK_TIMEOUT_S


@pytest.mark.parametrize(
    "error",
    [
        asyncpg.PostgresError("kaputt"),
        asyncpg.InterfaceError("pool is closing"),
    ],
    ids=["postgres-error", "interface-error"],
)
def test_worker_health_error_yields_unknown(
    fake_pool: None, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    async def _raise(_conn: object) -> str:
        raise error

    monkeypatch.setattr(main, "worker_health", _raise)
    body, elapsed = _get_health()
    _assert_unknown(body)
    assert elapsed < WORKER_HEALTH_TIMEOUT_S


def test_hanging_worker_health_is_cut_at_timeout(
    fake_pool: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    hang_s = WORKER_HEALTH_TIMEOUT_S + 8.0

    async def _hang(_conn: object) -> str:
        await asyncio.sleep(hang_s)
        return "ok"

    monkeypatch.setattr(main, "worker_health", _hang)
    body, elapsed = _get_health()
    _assert_unknown(body)
    # Abgebrochen an der Zeitgrenze, nicht erst nach `hang_s`.
    assert elapsed < WORKER_HEALTH_TIMEOUT_S + _SLACK_S
    assert elapsed < _HEALTHCHECK_TIMEOUT_S


@pytest.mark.integration
def test_locked_heartbeat_table_yields_unknown_in_time() -> None:
    """Der belegte Fall: eine andere Verbindung haelt LOCK TABLE worker_heartbeat."""
    with isolated_schema("health_worker_lock"), TestClient(app) as client:
        if client.get("/v1/health").json()["db"] != "ok":
            pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")

        loop = asyncio.new_event_loop()
        conn = loop.run_until_complete(asyncpg.connect(get_settings().database_url))
        try:
            loop.run_until_complete(
                conn.execute("BEGIN; LOCK TABLE worker_heartbeat IN ACCESS EXCLUSIVE MODE")
            )
            # Request im Thread: ohne Zeitgrenze im Code haengt er am Lock. Dann
            # gibt der Test den Lock selbst frei und wird rot, statt den Lauf
            # endlos zu blockieren (kein pytest-timeout im Repo).
            with ThreadPoolExecutor(max_workers=1) as pool:
                started = time.monotonic()
                future = pool.submit(client.get, "/v1/health")
                try:
                    response = future.result(timeout=_HEALTHCHECK_TIMEOUT_S)
                except FutureTimeout:
                    loop.run_until_complete(conn.execute("ROLLBACK"))
                    future.result()
                    pytest.fail("/v1/health haengt am Lock auf worker_heartbeat")
                elapsed = time.monotonic() - started
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "ok"
            assert body["db"] == "ok"
            assert body["worker"] == "unknown"
            assert elapsed < WORKER_HEALTH_TIMEOUT_S + _SLACK_S

            loop.run_until_complete(conn.execute("ROLLBACK"))
            # Nach dem Lock ist der Pool wieder benutzbar.
            again = client.get("/v1/health").json()
            assert again["worker"] == "unknown"
            assert again["db"] == "ok"
        finally:
            loop.run_until_complete(conn.close())
            loop.close()
