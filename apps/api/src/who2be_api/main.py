"""Application entrypoint for the Who2Be REST API.

Phase 1: Health-Endpoint, Infrastruktur-Fundament (zentrale Settings,
asyncpg-Pool), Auth (`/v1/tokens`), Persona- und Playbook-CRUD inklusive
Persona-Playbook-Verknuepfung.
"""

from typing import cast

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from slowapi.middleware import SlowAPIMiddleware

from who2be_api import __version__
from who2be_api.core.config import get_settings
from who2be_api.core.db import database, lifespan
from who2be_api.core.logging import configure_logging
from who2be_api.core.middleware import AccessLogMiddleware, RequestIDMiddleware
from who2be_api.core.rate_limit import (
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
    limiter,
)
from who2be_api.routers import persona_playbooks, personas, playbooks, tokens

configure_logging(get_settings().log_format)


def _on_rate_limit(request: Request, exc: Exception) -> Response:
    # slowapi's Handler ist auf `RateLimitExceeded` typisiert; Starlette erwartet
    # `Exception`. Duenner Adapter haelt mypy strict, ohne `type: ignore`.
    return _rate_limit_exceeded_handler(request, cast(RateLimitExceeded, exc))


app = FastAPI(title="Who2Be API", version=__version__, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _on_rate_limit)
# SlowAPIMiddleware vor CORSMiddleware adden: Starlette stacked LIFO, dann liegt
# CORS aussen und Preflight-OPTIONS triggert das Limit nicht.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)
# Observability-Stack: AccessLog innen, RequestID aussen — Starlette stacked LIFO,
# also wird RequestID zuerst aufgerufen, bindet die ID, und der AccessLog-Logger
# kann sie ueber `structlog.contextvars` lesen, bevor er die Zeile emittiert.
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)
app.include_router(tokens.router)
app.include_router(personas.router)
app.include_router(playbooks.router)
app.include_router(persona_playbooks.router)


class Health(BaseModel):
    status: str
    version: str
    db: str


@app.get("/v1/health", response_model=Health)
async def health() -> Health:
    db_status = "ok" if await database.ping() else "unavailable"
    return Health(status="ok", version=__version__, db=db_status)
