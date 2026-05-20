"""Application entrypoint for the Who2Be REST API.

Phase 0: nur ein Health-Endpoint, damit das Geruest lauffaehig und
verifizierbar ist. Persona-/Playbook-CRUD und Auth folgen in Phase 1.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from who2be_api import __version__

app = FastAPI(title="Who2Be API", version=__version__)


class Health(BaseModel):
    status: str
    version: str


@app.get("/v1/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", version=__version__)
