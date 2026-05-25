"""Tests fuer strukturierte JSON-Logs (MS-3 H2, structlog).

Belegt drei Eigenschaften:
1. `X-Request-ID` wird propagiert (Eingangs uebernommen, sonst generiert).
2. Pro HTTP-Request wird `event="http_request"` mit allen Pflichtfeldern
   geloggt (request_id, path, status, duration_ms).
3. `configure_logging("console")` schaltet auf den `ConsoleRenderer` um —
   sichtbar daran, dass Stdout-Capture kein JSON mehr liefert.
"""

import contextlib
import json
import logging
from collections.abc import Iterator, Mapping, MutableMapping
from typing import Any

import structlog
from fastapi.testclient import TestClient

from who2be_api.core.logging import configure_logging
from who2be_api.main import app


@contextlib.contextmanager
def capture_with_context() -> Iterator[list[dict[str, Any]]]:
    """structlog.testing.capture_logs verwirft merge_contextvars — eigener Helper
    haengt einen Capture-Processor an die existierende Pipeline, sodass
    `request_id`/`owner_id` aus contextvars in jedem Record landen."""
    entries: list[dict[str, Any]] = []

    def append(
        _: Any, __: str, event_dict: MutableMapping[str, Any]
    ) -> Mapping[str, Any]:
        entries.append(dict(event_dict))
        raise structlog.DropEvent

    old_config = structlog.get_config()
    structlog.configure(
        processors=[structlog.contextvars.merge_contextvars, append],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )
    structlog.contextvars.clear_contextvars()
    try:
        yield entries
    finally:
        structlog.contextvars.clear_contextvars()
        structlog.configure(**old_config)


def _http_request_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if r.get("event") == "http_request"]


def test_request_id_generated_when_missing() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/health")
    assert response.status_code == 200
    assert "x-request-id" in {k.lower() for k in response.headers}
    assert response.headers["x-request-id"]


def test_request_id_round_trips_from_header() -> None:
    custom = "trace-abc-12345"
    with TestClient(app) as client:
        response = client.get("/v1/health", headers={"X-Request-ID": custom})
    assert response.headers["x-request-id"] == custom


def test_access_log_emits_required_fields() -> None:
    with capture_with_context() as records, TestClient(app) as client:
        client.get("/v1/health", headers={"X-Request-ID": "fixed-id-1"})

    http_records = _http_request_records(records)
    assert http_records, "AccessLogMiddleware hat keine http_request-Zeile emittiert"
    record = http_records[-1]
    assert record["path"] == "/v1/health"
    assert record["status"] == 200
    assert isinstance(record["duration_ms"], float | int)
    assert record["request_id"] == "fixed-id-1"


def test_access_log_anonymous_has_no_owner_id() -> None:
    with capture_with_context() as records, TestClient(app) as client:
        client.get("/v1/health")
    http_records = _http_request_records(records)
    assert http_records
    assert "owner_id" not in http_records[-1]


def test_console_format_is_not_json(capsys: Any) -> None:
    # Re-konfigurieren auf Console-Renderer; nach dem Test wieder JSON setzen,
    # damit Folgetests nicht beeinflusst werden.
    try:
        configure_logging("console")
        logger = structlog.get_logger("test_console")
        logger.info("manual_event", foo="bar")
        captured = capsys.readouterr().out
        for line in captured.splitlines():
            if "manual_event" in line:
                try:
                    json.loads(line)
                except ValueError:
                    return  # erwartet: keine JSON-Zeile
                raise AssertionError("ConsoleRenderer hat trotzdem JSON ausgegeben")
        raise AssertionError("Keine console-Logzeile gefunden")
    finally:
        configure_logging("json")
        logging.getLogger().setLevel(logging.INFO)
