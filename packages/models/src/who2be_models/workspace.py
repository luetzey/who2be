"""Pydantic-Modelle fuer das Workspace-Aggregat (TASK-301).

Zweite Stufe der Tenant-Hierarchie. Ein Workspace haengt an genau einer
Organization; Personae/Playbooks/Tokens leben innerhalb eines Workspaces.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from who2be_models.locale import DEFAULT_LOCALE, ContentLocale, validate_supported_locale

WorkspaceNameStr = Annotated[str, StringConstraints(min_length=1, max_length=200)]
WorkspaceSlugStr = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class WorkspaceCreate(BaseModel):
    """Eingabe fuer `POST /v1/organizations/{org_id}/workspaces`."""

    model_config = ConfigDict(extra="forbid")

    name: WorkspaceNameStr
    slug: WorkspaceSlugStr
    # Workspace-Content-Sprache (Plan „Ein Element, eine Sprache", 2026-07-24):
    # bestimmt die Default-Sprache neuer Inhalte UND die Sprache der
    # ausgerollten Standard-Inhalte (Seeding). Nur Sprachen aus
    # `SUPPORTED_LOCALES` sind erlaubt — anders als das offene `locale`-Feld
    # auf Persona/Playbook/etc. gibt es fuer Workspaces kein „unbekannte
    # Sprache, wird spaeter gesetzt": ausgerollte Inhalte existieren nur in
    # `SUPPORTED_LOCALES`.
    content_locale: ContentLocale = DEFAULT_LOCALE

    @field_validator("content_locale")
    @classmethod
    def _validate_content_locale(cls, value: str) -> str:
        return validate_supported_locale(value)


class WorkspaceUpdate(BaseModel):
    """Eingabe fuer `PATCH /v1/workspaces/{id}` — nur `name` aenderbar."""

    model_config = ConfigDict(extra="forbid")

    name: WorkspaceNameStr | None = Field(default=None)


class WorkspaceRead(BaseModel):
    """Workspace-Metadaten."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    slug: str
    # Default `'de'` deckt Bestand ohne Migration-Backfill-Race + Lese-Pfade
    # ohne explizite Spalte ab (spiegelt `PersonaRead.locale` u.a.).
    content_locale: ContentLocale = DEFAULT_LOCALE
    created_at: datetime
