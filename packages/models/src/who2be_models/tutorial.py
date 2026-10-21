"""Tutorials: Katalog-Definition und Fortschritts-Modelle (ADR-0060).

Ein Tutorial ist **Daten, kein Code**: je Tutorial eine sprachneutrale
Definitionsdatei `tutorials/<id>.json` in diesem Paket (id, Zielgruppe,
Begruessung ja/nein, Schritte mit `id` und Schritt-Typ). Die API validiert
Tutorial- und Schritt-IDs dagegen, das Web importiert dieselbe Datei; Titel und
Texte stehen je Sprache im Hilfe-Bereich des Web (Markdown mit
`tutorial: <id>`). Ein neues Tutorial ist damit eine JSON-Datei plus eine
Markdown-Datei je Sprache — ohne Code, solange es die Schritt-Typen aus
`StepType` nutzt. Ein neuer Schritt-Typ mit automatischer Erkennung ist ein
eigenes kleines Code-Paket (Ableitung in `services/tutorial_service.py`).
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Erlaubte Form fuer `tutorial_id` und `step_id`: Kleinbuchstaben-Slug.
#: Dieselbe Regel steht als CHECK in Migration 0108.
TUTORIAL_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
TUTORIAL_ID_MAX_LENGTH = 64

#: Fester Katalog der Schritt-Typen (ADR-0060 §3).
#:
#: * `head_start` — immer erledigt (Startvorsprung, z. B. „Builder ist bereit“).
#: * `first_mcp_call` — erste Auslieferung an einen Agenten ueber eine
#:   Verbindung dieses Nutzers (`usage_event`, `source='server'`).
#: * `agent_created` — ein nicht verwalteter Agent dieses Nutzers existiert.
#: * `own_agent_mcp_call` — wie `first_mcp_call`, aber fuer einen nicht
#:   verwalteten Agenten.
#: * `page_visited` — das Web meldet den Besuch der Seite `page`.
#: * `manual` — der Nutzer hakt den Schritt selbst ab.
StepType = Literal[
    "head_start",
    "first_mcp_call",
    "agent_created",
    "own_agent_mcp_call",
    "page_visited",
    "manual",
]

#: Typen, deren Zustand der Server aus vorhandenen Daten ableitet. Sie lassen
#: sich ueberspringen, aber nicht von Hand abhaken.
AUTOMATIC_STEP_TYPES: frozenset[str] = frozenset(
    {"head_start", "first_mcp_call", "agent_created", "own_agent_mcp_call"}
)

TutorialAudience = Literal["everyone"]
TutorialStepState = Literal["open", "done", "skipped"]

_TUTORIALS_DIR = Path(__file__).resolve().parent / "tutorials"


class TutorialStepDefinition(BaseModel):
    """Ein Schritt im Katalog."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=TUTORIAL_ID_PATTERN, max_length=TUTORIAL_ID_MAX_LENGTH)
    type: StepType
    #: Nur bei `page_visited`: Pfad der Web-Seite, deren Besuch zaehlt.
    page: str | None = Field(default=None, pattern=r"^/[a-z0-9/-]*$", max_length=200)

    @model_validator(mode="after")
    def _page_only_for_page_visited(self) -> TutorialStepDefinition:
        if (self.type == "page_visited") != (self.page is not None):
            raise ValueError("`page` ist genau bei Schritt-Typ `page_visited` Pflicht.")
        return self


class TutorialDefinition(BaseModel):
    """Eine Katalog-Datei `tutorials/<id>.json`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=TUTORIAL_ID_PATTERN, max_length=TUTORIAL_ID_MAX_LENGTH)
    audience: TutorialAudience
    #: Hat das Tutorial eine Begruessung (Dialog vor der Liste)?
    welcome: bool = False
    steps: list[TutorialStepDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_step_ids(self) -> TutorialDefinition:
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Tutorial {self.id!r}: Schritt-IDs muessen eindeutig sein.")
        return self

    def step(self, step_id: str) -> TutorialStepDefinition | None:
        return next((s for s in self.steps if s.id == step_id), None)


def load_tutorial_catalog(directory: Path | None = None) -> dict[str, TutorialDefinition]:
    """Liest und validiert alle Katalog-Dateien (Reihenfolge: Dateiname).

    Faellt laut, wenn eine Datei ungueltig ist oder ihr Name nicht zur `id`
    passt — ein kaputter Katalog soll beim Start auffallen, nicht beim ersten
    Nutzer.
    """
    catalog: dict[str, TutorialDefinition] = {}
    for path in sorted((directory or _TUTORIALS_DIR).glob("*.json")):
        definition = TutorialDefinition.model_validate(json.loads(path.read_text("utf-8")))
        if definition.id != path.stem:
            raise ValueError(f"{path.name}: `id` {definition.id!r} passt nicht zum Dateinamen.")
        catalog[definition.id] = definition
    return catalog


@lru_cache(maxsize=1)
def tutorial_catalog() -> dict[str, TutorialDefinition]:
    """Der ausgelieferte Katalog, einmal pro Prozess geladen."""
    return load_tutorial_catalog()


class TutorialStepRead(BaseModel):
    """Zustand eines Schritts fuer den aktuellen Nutzer."""

    id: str
    type: StepType
    page: str | None = None
    #: Vom Server abgeleitet (nicht von Hand abhakbar).
    automatic: bool
    state: TutorialStepState
    #: Zeitpunkt des Abhakens, Ueberspringens bzw. des ableitenden Ereignisses.
    completed_at: datetime | None = None


class TutorialRead(BaseModel):
    """Antwort von `GET /v1/me/tutorials/{tutorial_id}` und Listeneintrag."""

    id: str
    audience: TutorialAudience
    welcome: bool
    welcome_seen_at: datetime | None = None
    #: Letzter Neustart; automatische Schritte zaehlen erst ab hier.
    restarted_at: datetime | None = None
    #: Jeder Schritt erledigt oder uebersprungen.
    completed: bool
    steps: list[TutorialStepRead]


class TutorialPatch(BaseModel):
    """Body von `PATCH /v1/me/tutorials/{tutorial_id}`.

    `step_id` und `state` kommen nur gemeinsam (`open` nimmt Haken oder
    Ueberspringen zurueck). `welcome_seen: true` vermerkt die Begruessung.
    """

    model_config = ConfigDict(extra="forbid")

    step_id: str | None = Field(
        default=None, pattern=TUTORIAL_ID_PATTERN, max_length=TUTORIAL_ID_MAX_LENGTH
    )
    state: TutorialStepState | None = None
    welcome_seen: Literal[True] | None = None

    @model_validator(mode="after")
    def _consistent(self) -> TutorialPatch:
        if (self.step_id is None) != (self.state is None):
            raise ValueError("`step_id` und `state` nur gemeinsam angeben.")
        if self.step_id is None and self.welcome_seen is None:
            raise ValueError("Mindestens `step_id`+`state` oder `welcome_seen` angeben.")
        return self


__all__ = [
    "AUTOMATIC_STEP_TYPES",
    "TUTORIAL_ID_MAX_LENGTH",
    "TUTORIAL_ID_PATTERN",
    "StepType",
    "TutorialAudience",
    "TutorialDefinition",
    "TutorialPatch",
    "TutorialRead",
    "TutorialStepDefinition",
    "TutorialStepRead",
    "TutorialStepState",
    "load_tutorial_catalog",
    "tutorial_catalog",
]
