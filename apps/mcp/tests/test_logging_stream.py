"""Regression-Test: structured logs muessen auf `stderr` (ADR-0034).

Stdio-MCP-Transport reserviert `stdout` fuer JSON-RPC-Frames. Vor ADR-0034
schrieb der StreamHandler auf `sys.stdout` und korrumpierte damit jeden
Client-Connect (Claude Desktop, Cursor, FastMCP-stdio-Smoke).
"""

from __future__ import annotations

import logging
import sys

from who2be_mcp.core_logging import configure_logging


def test_configure_logging_attaches_stderr_handler() -> None:
    configure_logging("json")

    root_handlers = logging.getLogger().handlers
    stream_handlers = [
        h for h in root_handlers if isinstance(h, logging.StreamHandler)
    ]
    assert stream_handlers, "configure_logging muss einen StreamHandler setzen"
    assert all(
        h.stream is sys.stderr for h in stream_handlers
    ), "Stdio-Transport: Logs MUESSEN auf stderr — stdout ist fuer JSON-RPC reserviert."


def test_configure_logging_does_not_leak_stdout_handler() -> None:
    """Kein StreamHandler darf auf `sys.stdout` zeigen — auch nicht versehentlich
    durch foreign-pre-chain oder Adapter."""
    configure_logging("console")

    root_handlers = logging.getLogger().handlers
    stream_handlers = [
        h for h in root_handlers if isinstance(h, logging.StreamHandler)
    ]
    assert not any(
        getattr(h, "stream", None) is sys.stdout for h in stream_handlers
    ), "Kein Handler darf auf sys.stdout zeigen (Stdio-MCP-Frame-Korruption)."
