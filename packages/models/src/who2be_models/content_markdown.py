"""Markdown-Schreibweg fuer Agenten: Ein- und Ausgabemodelle (ADR-0058 §5.1, §6.2, §9 P2).

Die API wandelt Markdown in BlockNote um (das Speicherformat bleibt BlockNote,
ADR-0058 §2). Diese Modelle sind die Wire-Form des Wegs:

- `*MarkdownContent` je Elementart: dieselben Strukturfelder wie das
  JSON-Modell, die BlockNote-Felder als Markdown-Strings in der Normalform
  (Ueberschriften mit Anker ` [#id]`, Pills als `{{kind:target_id}}`).
- `MarkdownSource` ist die Quellfassung (`format=source`) mit dem
  Konflikt-Token `base_rev` im Kopf; jede Schreibantwort hat dieselbe Form
  plus `dangling_refs`.
- `MarkdownCreate`/`MarkdownWrite` sind Anlegen und Vollstand (PUT),
  `ContentEdit` die Teilaenderung (PATCH) an einem Anker oder Feld.

Welche `*MarkdownContent`-Form `content` hat, bestimmt die Elementart im Pfad;
die API validiert `content` gegen genau dieses Modell.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from who2be_models.content_budgets import LengthHint
from who2be_models.external_tool import ToolNameStr
from who2be_models.locale import ContentLocale
from who2be_models.persona import SkillRef
from who2be_models.playbook import PlaybookType
from who2be_models.slug import SlugStr
from who2be_models.status import VersionStatus

#: Elementarten des Markdown-Wegs, so wie sie im Pfad stehen.
MarkdownEntityType = Literal[
    "personas", "playbooks", "resources", "system-prompts", "external_tools"
]

_TagStr = Annotated[str, StringConstraints(min_length=1, max_length=100)]
# Ein Markdown-Feld. Die Grenze liegt ueber den 50 000 Zeichen der JSON-Bodys,
# weil Markdown kleiner ist als das Editor-JSON (ADR-0058 §8.2); die
# Block-Grenzen der Zielmodelle greifen nach der Umwandlung zusaetzlich.
_Markdown = Annotated[str, StringConstraints(max_length=200_000)]


class PersonaModeMarkdown(BaseModel):
    """Ein Persona-Modus; die drei Inhaltsfelder sind je ein Markdown-Dokument."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    trigger: str | None = Field(default=None, max_length=2_000)
    is_default: bool = False
    identity_add: _Markdown = ""
    output_style_override: _Markdown = ""
    anti_patterns: _Markdown = ""
    playbook_id: UUID | None = None
    playbook_name: str = Field(default="", max_length=200)


class PersonaMarkdownContent(BaseModel):
    """Persona: `profile` ist der Profil-Inhalt, Modi werden ueber den Namen zugeordnet."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    tags: list[_TagStr] = Field(default_factory=list, max_length=50)
    profile: _Markdown = ""
    modes: list[PersonaModeMarkdown] = Field(default_factory=list, max_length=20)
    skills: list[SkillRef] = Field(default_factory=list, max_length=50)


class PlaybookMarkdownContent(BaseModel):
    """Playbook: `body` als Markdown, sonst wie `PlaybookContent`."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    body: _Markdown = ""
    type: PlaybookType | Literal[""] = ""
    tags: list[_TagStr] = Field(default_factory=list, max_length=50)
    triggers: str | None = Field(default=None, max_length=2_000)


class ResourceMarkdownContent(BaseModel):
    """Resource: `body` als Markdown, GFM-Tabellen erlaubt."""

    # GFM-Tabellen: ADR-0058 §3.4 (Kommentar, nicht Docstring: der geht als
    # Werkzeug-Schema auf den Draht, siehe test_tool_payload_budget).
    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    body: _Markdown = ""
    tags: list[_TagStr] = Field(default_factory=list, max_length=50)


class SystemPromptMarkdownContent(BaseModel):
    """System-Prompt: `body` als Markdown mit Platzhalter-Tokens."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=2_000)
    body: _Markdown = ""


class ExternalToolMarkdownContent(BaseModel):
    """Externes Tool: `usage_notes` als Markdown (Owner W58-4), sonst wie `ExternalToolContent`."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(default="", max_length=200)
    mcp_server_name: str = Field(default="", max_length=200)
    tool_names: list[ToolNameStr] = Field(default_factory=list, max_length=100)
    usage_notes: _Markdown = ""
    fallback_note: str | None = Field(default=None, max_length=2_000)
    tags: list[_TagStr] = Field(default_factory=list, max_length=50)


MarkdownContent = (
    PersonaMarkdownContent
    | PlaybookMarkdownContent
    | ResourceMarkdownContent
    | SystemPromptMarkdownContent
    | ExternalToolMarkdownContent
)

#: Modell von `content` je Elementart.
MARKDOWN_CONTENT_MODELS: dict[str, type[BaseModel]] = {
    "personas": PersonaMarkdownContent,
    "playbooks": PlaybookMarkdownContent,
    "resources": ResourceMarkdownContent,
    "system-prompts": SystemPromptMarkdownContent,
    "external_tools": ExternalToolMarkdownContent,
}


class DanglingRef(BaseModel):
    """Ein gespeicherter Verweis auf eine Ueberschrift, die das Schreiben geloescht hat."""

    source_type: Literal["playbook", "resource"]
    source_id: UUID
    block_id: str


class MarkdownSource(BaseModel):
    """Quellfassung (`format=source`): Vorlage fuer Vollstand und Teilaenderung.

    `base_rev` ist der Konflikt-Token der Version, auf die geschrieben wuerde
    (ADR-0058 §6.3). Er fehlt (`null`), wenn die gelieferte Version nicht das
    Schreibziel ist: bei Versions-Snapshots und bei Lesern, die nur die aktive
    Version sehen, waehrend ein Draft offen ist.
    """

    entity_type: MarkdownEntityType
    id: UUID
    name: str
    locale: ContentLocale
    version: int
    status: VersionStatus
    base_rev: str | None
    content: MarkdownContent


class MarkdownWriteResult(MarkdownSource):
    """Antwort eines Schreibens: der neue Stand samt neuem `base_rev`.

    `dangling_refs` nennt gespeicherte Verweise (Playbook- und
    Sub-Resource-Links) auf Ueberschriften, die dieses Schreiben entfernt hat
    (ADR-0058 §4.2). Die Verweise bleiben stehen wie nach einem Loeschen im
    Web-Editor.
    """

    dangling_refs: list[DanglingRef] = Field(default_factory=list)
    length_hints: list[LengthHint] = Field(
        default_factory=list,
        description=(
            "Weiche Laengen-Hinweise (ADR-0063): Inhalt ueber der Warnschwelle, "
            "gespeichert wurde trotzdem."
        ),
    )


class MarkdownCreate(BaseModel):
    """Anlegen per Markdown (`POST …/{entity_type}/markdown`).

    `slug` gilt fuer Resource und System-Prompt, `alias` fuer das externe
    Tool; bei den anderen Elementarten ist das Feld ein 422. Anker sind beim
    Anlegen immer unbekannt (ADR-0058 §4.2).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    locale: ContentLocale | None = None
    slug: SlugStr | None = None
    alias: SlugStr | None = None
    content: dict[str, Any] = Field(
        default_factory=dict,
        description="Felder je Elementart, siehe die `*MarkdownContent`-Schemas.",
    )


class MarkdownWrite(BaseModel):
    """Vollstand per Markdown (`PUT …/{entity_type}/{id}/markdown`), PUT-Semantik wie `update_*`.

    `base_rev` ist optional: gesetzt prueft der Server ihn unter der
    Zeilensperre (409 `version_conflict`).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    locale: ContentLocale | None = None
    base_rev: str | None = Field(default=None, min_length=1, max_length=64)
    content: dict[str, Any] = Field(
        description="Felder je Elementart, siehe die `*MarkdownContent`-Schemas.",
    )


class ContentEdit(BaseModel):
    """Teilaenderung (`PATCH …/{entity_type}/{id}/markdown`, ADR-0058 §6.2).

    Genau eines von `anchor` (Ueberschriften-ID; der Abschnitt reicht bis vor
    die naechste Ueberschrift gleicher oder hoeherer Ebene) und `field` (ein
    ganzes Markdown-Feld: `body`, `usage_notes`, `profile`,
    `modes[<Name>].identity_add|output_style_override|anti_patterns`).
    `markdown` ist bei `replace`/`insert_after` Pflicht, bei `delete` verboten.
    Geschrieben wird in den offenen Draft, sonst entsteht einer.
    """

    model_config = ConfigDict(extra="forbid")

    base_rev: str = Field(min_length=1, max_length=64)
    op: Literal["replace", "insert_after", "delete"]
    anchor: str | None = Field(default=None, min_length=1, max_length=100)
    field: str | None = Field(default=None, min_length=1, max_length=200)
    markdown: _Markdown | None = None

    @model_validator(mode="after")
    def _check_target(self) -> ContentEdit:
        if (self.anchor is None) == (self.field is None):
            raise ValueError("Genau eines von 'anchor' und 'field' angeben.")
        if self.op == "delete" and self.markdown is not None:
            raise ValueError("'delete' nimmt kein 'markdown'.")
        if self.op != "delete" and self.markdown is None:
            raise ValueError(f"'{self.op}' braucht 'markdown'.")
        return self


__all__ = [
    "MARKDOWN_CONTENT_MODELS",
    "ContentEdit",
    "DanglingRef",
    "ExternalToolMarkdownContent",
    "MarkdownContent",
    "MarkdownCreate",
    "MarkdownEntityType",
    "MarkdownSource",
    "MarkdownWrite",
    "MarkdownWriteResult",
    "PersonaMarkdownContent",
    "PersonaModeMarkdown",
    "PlaybookMarkdownContent",
    "ResourceMarkdownContent",
    "SystemPromptMarkdownContent",
]
