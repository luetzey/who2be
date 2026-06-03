"""Pydantic-Modelle fuer den Account-/Org-Lifecycle (Track O, Plan §3.2)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountDeletionRead(BaseModel):
    """Antwort auf `DELETE /v1/me` — bestaetigt die Vormerkung + Purge-Termin."""

    model_config = ConfigDict(from_attributes=True)

    # Frueheste Hard-Purge-Zeit (now + Grace). Bis dahin sind die Daten nur
    # eingemottet, nicht geloescht.
    purge_after: datetime


class OrganizationDeletionRead(BaseModel):
    """Antwort auf `DELETE /v1/organizations/{id}` — Soft-Delete + Purge-Termin."""

    model_config = ConfigDict(from_attributes=True)

    organization_id: str
    purge_after: datetime
