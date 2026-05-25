"""Tests fuer die Tool-Logging-Schicht des MCP-Servers (MS-3 H2)."""

import asyncio
import contextlib
from collections.abc import Iterator, Mapping, MutableMapping
from typing import Any

import pytest
import structlog

from who2be_mcp.core_logging import with_tool_log


@contextlib.contextmanager
def capture_with_context() -> Iterator[list[dict[str, Any]]]:
    """Eigener Capture, der merge_contextvars beibehaelt (anders als
    `structlog.testing.capture_logs`)."""
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


def _tool_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if r.get("event") == "mcp_tool_call"]


def test_sync_tool_log_emits_required_fields() -> None:
    @with_tool_log("ping_test")
    def _ping() -> str:
        return "pong"

    with capture_with_context() as records:
        result = _ping()

    assert result == "pong"
    tool_records = _tool_records(records)
    assert tool_records
    record = tool_records[-1]
    assert record["tool"] == "ping_test"
    assert isinstance(record["duration_ms"], float | int)
    assert record["request_id"]


def test_async_tool_log_emits_required_fields() -> None:
    @with_tool_log("async_test")
    async def _run(x: int) -> int:
        return x * 2

    with capture_with_context() as records:
        result = asyncio.run(_run(21))

    assert result == 42
    tool_records = _tool_records(records)
    assert tool_records
    assert tool_records[-1]["tool"] == "async_test"


def test_tool_log_records_error_and_re_raises() -> None:
    @with_tool_log("boom")
    def _explode() -> None:
        raise ValueError("kaputt")

    with capture_with_context() as records:
        with pytest.raises(ValueError, match="kaputt"):
            _explode()

    tool_records = _tool_records(records)
    assert tool_records
    assert tool_records[-1]["error"] == "ValueError"


def test_tool_log_request_ids_are_unique_per_call() -> None:
    @with_tool_log("repeat")
    def _noop() -> None:
        return None

    with capture_with_context() as records:
        _noop()
        _noop()

    ids = [r["request_id"] for r in _tool_records(records)]
    assert len(ids) == 2
    assert ids[0] != ids[1]
