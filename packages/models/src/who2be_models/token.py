"""Pydantic-Modelle fuer das API-Token-Aggregat (ADR-0006).

Der Klartext-Token wird ausschliesslich in `TokenCreated` und nur genau
einmal bei der Erstellung zurueckgegeben; persistiert wird nur der Hash.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TokenCreate(BaseModel):
    """Eingabe fuer `POST /v1/tokens`."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class TokenRead(BaseModel):
    """API-Token-Metadaten — ohne Hash und ohne Klartext."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class TokenCreated(TokenRead):
    """Antwort auf `POST /v1/tokens` — enthaelt den Klartext genau einmal."""

    token: str
