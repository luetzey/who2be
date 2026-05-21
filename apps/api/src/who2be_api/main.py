"""Application entrypoint for the Who2Be REST API.

Phase 1: Health-Endpoint, Infrastruktur-Fundament (zentrale Settings,
asyncpg-Pool), Auth (`/v1/tokens`), Persona- und Playbook-CRUD inklusive
Persona-Playbook-Verknuepfung.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from who2be_api import __version__
from who2be_api.core.db import database, lifespan
from who2be_api.routers import persona_playbooks, personas, playbooks, tokens

app = FastAPI(title="Who2Be API", version=__version__, lifespan=lifespan)
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
