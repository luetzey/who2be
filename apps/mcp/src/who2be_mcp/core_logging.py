"""Strukturierte JSON-Logs fuer den Who2Be-MCP-Server (ADR-0007).

Bewusst eigenes Modul (kein Import aus `who2be_api`) — MCP und API sind
nach ADR-0005 entkoppelte Prozesse. Pro Tool-Aufruf bindet der Decorator
`with_tool_log` eine `request_id` an `structlog.contextvars`, misst die
Dauer und emittiert eine strukturierte Log-Zeile.
"""

import functools
import inspect
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal, ParamSpec, TypeVar, cast

import structlog

LogFormat = Literal["json", "console"]

P = ParamSpec("P")
R = TypeVar("R")


def _build_shared_processors() -> list[Any]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def configure_logging(fmt: LogFormat = "json") -> None:
    """Konfiguriert structlog + stdlib-Root-Logger (idempotent / re-konfigurierbar)."""
    shared = _build_shared_processors()
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # MCP-Stdio-Transport reserviert stdout fuer JSON-RPC-Frames — Logs MUESSEN
    # auf stderr, sonst kollidieren strukturierte Log-Zeilen mit MCP-Antworten
    # und kein Client (Claude Desktop, Cursor) kann den Server lesen.
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


_tool_logger = structlog.get_logger("who2be_mcp.tool")


def with_tool_log(tool_name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator: bindet `request_id`, misst Dauer, loggt Erfolg / Fehler.

    Funktioniert sowohl mit `async def`- als auch mit `def`-Tools; bei
    Exceptions wird die Log-Zeile mit `error=<class>` emittiert und die
    Exception re-raised.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                request_id = uuid.uuid4().hex
                structlog.contextvars.bind_contextvars(request_id=request_id, tool=tool_name)
                start = time.perf_counter()
                try:
                    result = await cast(Callable[P, Awaitable[R]], func)(*args, **kwargs)
                except Exception as exc:
                    _emit("mcp_tool_call", start, tool_name, error=type(exc).__name__)
                    raise
                _emit("mcp_tool_call", start, tool_name)
                return result

            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            request_id = uuid.uuid4().hex
            structlog.contextvars.bind_contextvars(request_id=request_id, tool=tool_name)
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                _emit("mcp_tool_call", start, tool_name, error=type(exc).__name__)
                raise
            _emit("mcp_tool_call", start, tool_name)
            return result

        return sync_wrapper

    return decorator


def _emit(event: str, start: float, tool_name: str, **extra: Any) -> None:
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    _tool_logger.info(event, tool=tool_name, duration_ms=duration_ms, **extra)
