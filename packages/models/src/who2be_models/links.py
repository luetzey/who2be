"""Pydantic-Modelle fuer die Persona-Playbook-Verknuepfung und Playbook-Composition."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PersonaPlaybookLinkSet(BaseModel):
    """Eingabe fuer `PUT /v1/personas/{id}/playbooks`.

    Setzt die Verknuepfungen einer Persona vollstaendig: die angegebene Liste
    ersetzt den bisherigen Stand (eine leere Liste loest alle Verknuepfungen).
    """

    model_config = ConfigDict(extra="forbid")

    # Obergrenze deckt jeden realistischen Persona-Fall ab und verhindert,
    # dass `set_persona_playbooks` mit beliebig grossen UUID-Arrays gegen die DB faehrt.
    playbook_ids: list[UUID] = Field(default_factory=list, max_length=200)


class PlaybookCompositionLinkSet(BaseModel):
    """Eingabe fuer PUT /playbooks/{id}/composes — geordnete Set-Replace.

    Reihenfolge der Liste = position (0..n). Leere Liste loest alle Kinder.
    """

    model_config = ConfigDict(extra="forbid")

    child_ids: list[UUID] = Field(default_factory=list, max_length=200)


class DeleteBlocked(BaseModel):
    """Strukturierter 409-Body, wenn ein Hard-Delete durch eingehende Referenzen
    blockiert wird (Single-Element-Delete, ADR-0032).

    `message` ist die Klartext-Begruendung (auch in `HTTPException.detail`
    gespiegelt). `blocked_by` ist eine maschinenlesbare Map: Schluessel benennt
    die Referenz-Quelle (`agents`/`personas`/`playbooks`/`resources`/
    `composites`), Wert ist die Liste der Verwender-Records (z. B.
    `PersonaUsage`/`PlaybookUsage`/`ResourceUsage`/`PlaybookRef`/`ResourceRef`).
    """

    model_config = ConfigDict(extra="forbid")

    message: str
    blocked_by: dict[str, list[Any]] = Field(default_factory=dict)
