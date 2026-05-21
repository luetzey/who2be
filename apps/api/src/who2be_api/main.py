"""Application entrypoint for the Who2Be REST API.

Phase 1: Health-Endpoint, Infrastruktur-Fundament (zentrale Settings,
asyncpg-Pool) und Auth (`/v1/tokens`). Persona-/Playbook-CRUD folgt.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from who2be_api import __version__
from who2be_api.core.db import database, lifespan
from who2be_api.routers import tokens

app = FastAPI(title="Who2Be API", version=__version__, lifespan=lifespan)
app.include_router(tokens.router)


class Health(BaseModel):
    status: str
    version: str
    db: str


@app.get("/v1/health", response_model=Health)
async def health() -> Health:
    db_status = "ok" if await database.ping() else "unavailable"
    return Health(status="ok", version=__version__, db=db_status)
