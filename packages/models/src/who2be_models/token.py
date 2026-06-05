"""Pydantic-Modelle fuer das API-Token-Aggregat (ADR-0006).

Der Klartext-Token wird ausschliesslich in `TokenCreated` und nur genau
einmal bei der Erstellung zurueckgegeben; persistiert wird nur der Hash.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from who2be_models.workspace_member import WorkspaceRole


class TokenCreate(BaseModel):
    """Eingabe fuer `POST /v1/tokens`.

    `role` ist optional: `None` ⇒ der Service pinnt die aktuelle Rolle des
    Erstellers als Snapshot (Token-Role-Snapshot, ADR-0023). Ein explizit
    gesetzter Wert darf die Ersteller-Rolle nicht uebersteigen — das prueft
    der Service, nicht dieser Pydantic-Layer.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    role: WorkspaceRole | None = None
    # Optionale Bindung an einen Agenten: ist sie gesetzt, setzt das Backend die
    # MCP-Tool-Policy dieses Agenten bei jedem Aufruf des Tokens durch (Writes
    # gated, Reads gescoped). `None` = ungebundener Token (nur Rollen-Gate).
    agent_id: UUID | None = None


class TokenRead(BaseModel):
    """API-Token-Metadaten — ohne Hash und ohne Klartext."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    role: WorkspaceRole
    # An welchen Agenten der Token gebunden ist (None = ungebunden).
    agent_id: UUID | None = None
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class TokenCreated(TokenRead):
    """Antwort auf `POST /v1/tokens` — enthaelt den Klartext genau einmal."""

    token: str
