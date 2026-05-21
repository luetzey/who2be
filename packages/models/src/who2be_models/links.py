"""Pydantic-Modelle fuer die Persona-Playbook-Verknuepfung."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PersonaPlaybookLinkSet(BaseModel):
    """Eingabe fuer `PUT /v1/personas/{id}/playbooks`.

    Setzt die Verknuepfungen einer Persona vollstaendig: die angegebene Liste
    ersetzt den bisherigen Stand (eine leere Liste loest alle Verknuepfungen).
    """

    model_config = ConfigDict(extra="forbid")

    playbook_ids: list[UUID] = Field(default_factory=list)
