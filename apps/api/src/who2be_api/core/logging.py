"""Strukturierte JSON-Logs fuer die Who2Be-API (ADR-0007).

structlog konfiguriert die Ausgabe; eine `ProcessorFormatter` haengt sich an
das stdlib-Root-Logging, sodass bestehende `logging.getLogger(__name__)`-Aufrufe
(z. B. in `core/db.py`, `core/security.py`) automatisch im gleichen JSON-Format
ausgeben.

Kontext-Felder (`request_id`, `owner_id`) werden ueber
`structlog.contextvars` gebunden und durch den `merge_contextvars`-Processor
in jede Logzeile gemergt.
"""

import logging
import sys
from typing import Any, Literal, cast

import structlog

LogFormat = Literal["json", "console"]


def _build_shared_processors() -> list[Any]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def configure_logging(fmt: LogFormat = "json") -> None:
    """Konfiguriert structlog + stdlib-Root-Logger.

    Idempotent in dem Sinne, dass ein zweiter Aufruf die Konfiguration ersetzt —
    Tests koennen so zwischen "json" und "console" hin- und herwechseln.
    """
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

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Bequemer Wrapper, damit Konsumenten nicht direkt gegen structlog importieren."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
