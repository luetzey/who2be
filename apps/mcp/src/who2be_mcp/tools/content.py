"""Markdown-Schreibweg der MCP-Werkzeuge (ADR-0058 §6.2, §7, Paket P3).

Seit P3 nehmen die zehn `create_*`/`update_*`-Werkzeuge fuer Persona, Playbook,
Resource, System-Prompt und externes Tool nur noch Markdown (harter Schnitt,
Owner W58-3 = A). Dieses Modul haelt, was die Werkzeuge in `server.py` und das
neue Werkzeug `edit_content` gemeinsam brauchen:

- die Eingabemodelle der Werkzeuge (`*MarkdownCreate`/`*MarkdownUpdate`). Ihr
  `content` ist das `*MarkdownContent`-Modell der API, die BlockNote-Felder
  sind dort Strings. Eine Block-Liste scheitert an der Schema-Validierung;
- den Waechter gegen Editor-JSON in einem Markdown-String
  (`reject_editor_json`): Ein String-Feld wie der Playbook-Body nimmt formal
  jeden Text an, also auch ein serialisiertes BlockNote-Array. Das wuerde als
  ein Absatz voll JSON gespeichert, still statt laut (ADR-0058 §7);
- die Abbildung Werkzeug-Elementart -> REST-Pfad.

Die Umwandlung selbst macht die API (`/markdown`-Routen, P2); der MCP-Prozess
bleibt ein duenner HTTP-Adapter (ADR-0005).
"""

from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field

from who2be_mcp.client import ApiClient
from who2be_mcp.core_logging import with_tool_log
from who2be_models.content_markdown import (
    ContentEdit,
    ExternalToolMarkdownContent,
    MarkdownCreate,
    MarkdownEntityType,
    MarkdownWrite,
    MarkdownWriteResult,
    PersonaMarkdownContent,
    PlaybookMarkdownContent,
    ResourceMarkdownContent,
    SystemPromptMarkdownContent,
)
from who2be_models.locale import ContentLocale
from who2be_models.slug import SlugStr

#: Elementarten, wie die MCP-Werkzeuge sie nennen (`list_versions` & Co.).
ContentEntityType = Literal["persona", "playbook", "resource", "system_prompt", "external_tool"]

#: Werkzeug-Elementart -> Pfadwert der `/markdown`-Routen.
ENTITY_PATH: dict[str, MarkdownEntityType] = {
    "persona": "personas",
    "playbook": "playbooks",
    "resource": "resources",
    "system_prompt": "system-prompts",
    "external_tool": "external_tools",
}

_BASE_REV = Field(default=None, min_length=1, max_length=64)


# --- Eingabemodelle der create_/update_-Werkzeuge -----------------------------


class _Create(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    locale: ContentLocale | None = None


class _Update(BaseModel):
    """Vollstand (PUT): `content` ersetzt den gespeicherten Stand vollstaendig."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    locale: ContentLocale | None = None
    base_rev: str | None = _BASE_REV


class PersonaMarkdownCreate(_Create):
    content: PersonaMarkdownContent = Field(default_factory=PersonaMarkdownContent)


class PersonaMarkdownUpdate(_Update):
    content: PersonaMarkdownContent


class PlaybookMarkdownCreate(_Create):
    content: PlaybookMarkdownContent = Field(default_factory=PlaybookMarkdownContent)


class PlaybookMarkdownUpdate(_Update):
    content: PlaybookMarkdownContent


class ResourceMarkdownCreate(_Create):
    slug: SlugStr | None = None
    content: ResourceMarkdownContent = Field(default_factory=ResourceMarkdownContent)


class ResourceMarkdownUpdate(_Update):
    content: ResourceMarkdownContent


class SystemPromptMarkdownCreate(_Create):
    slug: SlugStr | None = None
    content: SystemPromptMarkdownContent


class SystemPromptMarkdownUpdate(_Update):
    content: SystemPromptMarkdownContent


class ExternalToolMarkdownCreate(_Create):
    alias: SlugStr | None = None
    content: ExternalToolMarkdownContent = Field(default_factory=ExternalToolMarkdownContent)


class ExternalToolMarkdownUpdate(_Update):
    content: ExternalToolMarkdownContent


AnyMarkdownCreate = (
    PersonaMarkdownCreate
    | PlaybookMarkdownCreate
    | ResourceMarkdownCreate
    | SystemPromptMarkdownCreate
    | ExternalToolMarkdownCreate
)
AnyMarkdownUpdate = (
    PersonaMarkdownUpdate
    | PlaybookMarkdownUpdate
    | ResourceMarkdownUpdate
    | SystemPromptMarkdownUpdate
    | ExternalToolMarkdownUpdate
)


# --- Waechter gegen Editor-JSON -----------------------------------------------


def _looks_like_editor_json(value: str) -> bool:
    """Ist `value` ein serialisierter BlockNote-Block oder eine Block-Liste?

    Erkannt wird JSON, dessen Elemente Objekte mit `type` sind: genau die Form
    des Editor-JSON. Markdown, das mit `[` beginnt (ein Link am Absatzanfang),
    ist kein gueltiges JSON und faellt durch.
    """
    text = value.strip()
    if not text.startswith(("[", "{")):
        return False
    try:
        parsed = json.loads(text)
    except ValueError:
        return False
    items = parsed if isinstance(parsed, list) else [parsed]
    return bool(items) and all(isinstance(item, dict) and "type" in item for item in items)


def _markdown_fields(content: BaseModel) -> list[tuple[str, str]]:
    """Die Markdown-Felder eines `*MarkdownContent` als `(feld, wert)`."""
    if isinstance(content, PersonaMarkdownContent):
        out = [("profile", content.profile)]
        for mode in content.modes:
            for attr in ("identity_add", "output_style_override", "anti_patterns"):
                out.append((f"modes[{mode.name}].{attr}", getattr(mode, attr)))
        return out
    if isinstance(content, ExternalToolMarkdownContent):
        return [("usage_notes", content.usage_notes)]
    return [("body", content.body)]  # type: ignore[attr-defined]


def reject_editor_json(fields: list[tuple[str, str | None]]) -> None:
    """Weist Editor-JSON in einem Markdown-Feld mit klarer Meldung ab (ADR-0058 §7)."""
    for name, value in fields:
        if value and _looks_like_editor_json(value):
            raise ToolError(
                f"{name}: Editor-JSON (BlockNote) wird nicht mehr angenommen. "
                'Inhalt als Markdown schreiben; die Vorlage liefert `format="source"`.'
            )


# --- gemeinsame Schreibschritte -----------------------------------------------


async def _client() -> ApiClient:
    """API-Client ueber `server.build_client` (Laufzeit-Import, Muster `tools/tables.py`)."""
    from who2be_mcp import server

    return await server.build_client()


def _parse_uuid(value: str, label: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ToolError(f"Ungueltige {label}-UUID: '{value}'.") from exc


async def create_markdown(
    client: ApiClient, entity_type: ContentEntityType, data: AnyMarkdownCreate, locale: str | None
) -> MarkdownWriteResult:
    """Legt ein Element aus Markdown an (`POST …/{entity_type}/markdown`)."""
    reject_editor_json(list(_markdown_fields(data.content)))
    body = MarkdownCreate(
        name=data.name,
        locale=locale,
        slug=getattr(data, "slug", None),
        alias=getattr(data, "alias", None),
        content=data.content.model_dump(mode="json"),
    )
    return await client.create_markdown(ENTITY_PATH[entity_type], body)


async def put_markdown(
    entity_type: ContentEntityType, entity_id: str, label: str, data: AnyMarkdownUpdate
) -> MarkdownWriteResult:
    """Vollstand per Markdown (`PUT …/{entity_type}/{id}/markdown`)."""
    parsed = _parse_uuid(entity_id, label)
    reject_editor_json(list(_markdown_fields(data.content)))
    body = MarkdownWrite(
        name=data.name,
        locale=data.locale,
        base_rev=data.base_rev,
        content=data.content.model_dump(mode="json"),
    )
    client = await _client()
    return await client.put_markdown(ENTITY_PATH[entity_type], parsed, body)


# --- edit_content ---------------------------------------------------------------


@with_tool_log("edit_content")
async def edit_content(
    entity_type: ContentEntityType,
    entity_id: str,
    base_rev: str,
    op: Literal["replace", "insert_after", "delete"],
    anchor: str | None = None,
    field: str | None = None,
    markdown: str | None = None,
) -> MarkdownWriteResult:
    """Aendert einen Abschnitt oder ein Feld eines Elements als Draft, der Rest bleibt bitgleich.

    Ziel ist genau eines: `anchor` (ID einer Ueberschrift; der Abschnitt reicht bis vor die
    naechste gleicher oder hoeherer Ebene) oder `field` (ganzes Markdown-Feld: `body`,
    `profile`, `usage_notes`, `modes[<Name>].identity_add|output_style_override|anti_patterns`).
    `markdown` braucht `replace` und `insert_after`, `delete` nimmt keins.

    `base_rev` aus `format="source"` oder der letzten Schreibantwort. Ist schon ein Draft offen,
    wird bei passendem `base_rev` in ihn geschrieben; sonst 409 `version_conflict`: neu lesen,
    nicht blind wiederholen. Die Antwort traegt den neuen `base_rev`.
    """
    parsed = _parse_uuid(entity_id, entity_type)
    reject_editor_json([(field or anchor or "markdown", markdown)])
    try:
        data = ContentEdit(base_rev=base_rev, op=op, anchor=anchor, field=field, markdown=markdown)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    client = await _client()
    return await client.edit_markdown(ENTITY_PATH[entity_type], parsed, data)


def register(mcp: FastMCP) -> None:
    """Haengt `edit_content` an den Server (`output_schema=None`: Payload-Budget)."""
    mcp.tool(output_schema=None)(edit_content)
