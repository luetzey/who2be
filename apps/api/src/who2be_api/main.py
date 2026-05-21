"""Application entrypoint for the Who2Be REST API.

Phase 0/1: Health-Endpoint plus Infrastruktur-Fundament (zentrale Settings,
asyncpg-Pool). Persona-/Playbook-CRUD und Auth folgen in Phase 1+.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from who2be_api import __version__
from who2be_api.core.db import database, lifespan

app = FastAPI(title="Who2Be API", version=__version__, lifespan=lifespan)


class Health(BaseModel):
    status: str
    version: str
    db: str


@app.get("/v1/health", response_model=Health)
async def health() -> Health:
    db_status = "ok" if await database.ping() else "unavailable"
    return Health(status="ok", version=__version__, db=db_status)
