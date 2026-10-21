"""Markdown-Schreibweg fuer Agenten (ADR-0058 §5.1, §6, Paket P2).

Die API wandelt Markdown in BlockNote um und ruft danach **dieselben**
Service-Methoden wie der JSON-Weg (ADR-0058 §6.2): Rechte, Tag-Scope,
Rate-Limit, der Schutz verwalteter Inhalte und die Versionsregeln gelten
dadurch unveraendert. Dieses Modul kennt nur die Abbildung je Elementart:

- Lesen (`source`): gespeicherte Bloecke -> Markdown-Normalform, dazu der
  Konflikt-Token `base_rev` des Schreibziels.
- Anlegen (`create`) und Vollstand (`put`): Markdown -> Bloecke, IDs stabil
  gegen die Basisversion (ADR-0058 §4), dann `create`/`update` des Services.
- Teilaenderung (`edit`): ein Abschnitt (Ueberschriften-Anker) oder ein
  ganzes Markdown-Feld, dann `update_draft` des Services (arbeitet auf dem
  offenen Draft, ADR-0058 §6.2).

Konflikt-Token: `edit` verlangt ihn, `put` prueft ihn, wenn er gesetzt ist.
Geprueft wird zweimal: frueh gegen die gelesene Basis (damit die
ID-Zuordnung auf genau dem Stand laeuft, den der Aufrufer kennt) und
verbindlich unter der Zeilensperre im Repository (`expected_base_rev`).

Unveraenderte Felder bleiben bitgleich: ergibt das Markdown dieselben Bloecke
wie die Basis, schreibt der Weg den gespeicherten Body-String unveraendert
zurueck (ADR-0058 §5.2 G1).
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

import asyncpg
from fastapi import status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError

from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext, require_write_rate
from who2be_api.repositories.versioned_repository import (
    BaseRevConflictError,
    expected_base_rev,
)
from who2be_api.services.external_tool_service import ExternalToolService
from who2be_api.services.persona_service import PersonaService
from who2be_api.services.playbook_service import PlaybookService
from who2be_api.services.resource_service import ResourceService
from who2be_api.services.system_prompt_template_service import SystemPromptTemplateService
from who2be_models import (
    ExternalToolContent,
    ExternalToolCreate,
    ExternalToolUpdate,
    MarkdownConversionError,
    PersonaContent,
    PersonaCreate,
    PersonaMode,
    PersonaUpdate,
    PersonaVersionContent,
    PlaybookContent,
    PlaybookCreate,
    PlaybookUpdate,
    ResourceContent,
    ResourceCreate,
    ResourceUpdate,
    SystemPromptTemplateContent,
    SystemPromptTemplateCreate,
    SystemPromptTemplateUpdate,
    from_markdown,
    to_markdown,
)
from who2be_models.blocknote_markdown import default_new_block_id
from who2be_models.blocknote_text import block_plain_text, parse_blocknote_blocks
from who2be_models.content_markdown import (
    MARKDOWN_CONTENT_MODELS,
    ContentEdit,
    DanglingRef,
    ExternalToolMarkdownContent,
    MarkdownCreate,
    MarkdownEntityType,
    MarkdownSource,
    MarkdownWrite,
    MarkdownWriteResult,
    PersonaMarkdownContent,
    PersonaModeMarkdown,
    PlaybookMarkdownContent,
    ResourceMarkdownContent,
    SystemPromptMarkdownContent,
)

Block = dict[str, Any]

_MODE_FIELDS = ("identity_add", "output_style_override", "anti_patterns")
_MODE_FIELD_RE = re.compile(r"modes\[(.+)\]\.(identity_add|output_style_override|anti_patterns)")
_HEADING_LINE_RE = re.compile(r"#{1,3}[ \t]")
_TRAILING_ANCHOR_RE = re.compile(r"[ \t]\[#[A-Za-z0-9_.:-]+\][ \t]*$")
_PILL_RE = re.compile(r"\{\{([a-z][a-z0-9-]*):([^{}\n]*)\}\}")
# Obergrenze fuer Label-Abfragen je Aufruf (DoS-Schutz: jede neue Pill kostet
# eine Abfrage, ein Dokument mit tausend erfundenen Pills soll nicht tausend
# Roundtrips ausloesen; der Rest faellt auf `kind:target_id` zurueck).
_MAX_LABEL_LOOKUPS = 100

# Feste Labels, wie die Picker im Web-Editor sie setzen
# (`apps/web/src/components/editor/system-prompt/pickers/*.tsx`).
_STATIC_LABELS: dict[tuple[str, str], str] = {
    ("persona-field", "name"): "Persona: Name",
    ("persona-field", "description"): "Persona: Beschreibung",
    ("persona-field", "profile"): "Persona: Profil (vollständig)",
    ("persona-field", "profile-body"): "Persona: Profil-Inhalt",
    ("persona-field", "modes"): "Persona: Modi",
    ("date", "human"): "Datum (lesbar)",
    ("date", ""): "Datum (ISO-8601)",
    ("persona-ref", ""): "Persona laden",
    ("tools-overview", ""): "MCP-Tools",
    ("memory", ""): "Gedaechtnis",
}


# --- Fehler -----------------------------------------------------------------


def _conversion_error(exc: MarkdownConversionError, field: str) -> ApiError:
    params: dict[str, Any] = {"field": field}
    if exc.line is not None:
        params["line"] = exc.line
    if exc.block_id is not None:
        params["block_id"] = exc.block_id
    if exc.construct is not None:
        params["construct"] = exc.construct
    detail = f"{field}: {exc}"
    if exc.reason == "block_not_representable":
        detail += " Diesen Block aendert der Web-Editor."
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail,
        reason=exc.reason,
        params=params,
    )


def _version_conflict(current_version: int | None, current_base_rev: str | None) -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Der Stand hat sich seit dem Lesen geaendert (base_rev passt nicht). "
            "Quellfassung neu lesen und die Aenderung darauf anwenden."
        ),
        reason="version_conflict",
        params={"current_version": current_version, "current_base_rev": current_base_rev},
    )


def _anchor_unknown(detail: str, **params: Any) -> ApiError:
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail,
        reason="anchor_unknown",
        params=params,
    )


def _invalid(loc: tuple[str | int, ...], exc: ValidationError) -> RequestValidationError:
    """Pydantic-Fehler eines nachgelagerten Modells als regulaeres 422 der API."""
    errors = [
        {**err, "loc": (*loc, *err["loc"])}
        for err in exc.errors(include_url=False, include_context=False)
    ]
    return RequestValidationError(errors)


def _validate(model: type[BaseModel], data: Any, loc: tuple[str | int, ...]) -> Any:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise _invalid(loc, exc) from exc


@contextmanager
def _conflict_as_409() -> Iterator[None]:
    try:
        yield
    except BaseRevConflictError as exc:
        raise _version_conflict(exc.current_version, exc.current_base_rev) from exc


# --- Bloecke <-> gespeicherte Felder -----------------------------------------


def _dump_blocks(blocks: list[Any]) -> list[Block]:
    return [b.model_dump(mode="json") if isinstance(b, BaseModel) else b for b in blocks]


def _body_blocks(body: str) -> list[Block]:
    """Bloecke eines stringifizierten Bodys. Alt-Bestand ohne BlockNote-JSON
    erscheint als ein Absatz mit dem Rohtext, damit nichts still verschwindet."""
    blocks, raw = parse_blocknote_blocks(body)
    if blocks is not None:
        return blocks
    if not raw:
        return []
    return [
        {
            "id": "legacy-text",
            "type": "paragraph",
            "props": {
                "textColor": "default",
                "backgroundColor": "default",
                "textAlignment": "left",
            },
            "content": [{"type": "text", "text": raw, "styles": {}}],
            "children": [],
        }
    ]


def _body_string(blocks: list[Block], base_body: str, *, empty: str = "") -> str:
    """Body-String fuer `blocks`; unveraenderte Bloecke behalten den gespeicherten String."""
    if base_body and blocks == _body_blocks(base_body):
        return base_body
    if not blocks:
        return empty
    return json.dumps(blocks, ensure_ascii=False, separators=(",", ":"))


def _walk(blocks: list[Block]) -> Iterator[Block]:
    for block in blocks:
        if isinstance(block, dict):
            yield block
            yield from _walk(block.get("children") or [])


def _all_ids(blocks: list[Block]) -> set[str]:
    return {str(b.get("id")) for b in _walk(blocks)}


def _heading_ids(blocks: list[Block]) -> set[str]:
    return {str(b.get("id")) for b in _walk(blocks) if b.get("type") == "heading"}


@dataclass
class _Field:
    """Ein Markdown-Feld eines Elements: Name, gespeicherte Bloecke, Tabellen erlaubt."""

    name: str
    blocks: list[Block]
    allow_tables: bool = False


# --- Abbildung je Elementart -------------------------------------------------


class _Mapper(Protocol):
    def fields(self, content: Any) -> list[_Field]: ...

    def to_markdown_content(self, content: Any) -> BaseModel: ...

    def from_markdown_content(
        self, md: Any, base: Any | None, convert: _Converter
    ) -> BaseModel: ...

    def replace_field(self, content: Any, field: str, blocks: list[Block]) -> BaseModel: ...


_Converter = Callable[[str, "_Field | None", str, bool], list[Block]]


def _persona_base_mode(base: PersonaVersionContent | None, name: str) -> PersonaMode | None:
    for mode in base.modes if base is not None else []:
        if mode.name.lower() == name.lower():
            return mode
    return None


class _PersonaMapper:
    def fields(self, content: PersonaVersionContent) -> list[_Field]:
        out = [_Field("profile", _dump_blocks(content.content.blocks if content.content else []))]
        for mode in content.modes:
            for attr in _MODE_FIELDS:
                out.append(_Field(f"modes[{mode.name}].{attr}", _dump_blocks(getattr(mode, attr))))
        return out

    def to_markdown_content(self, content: PersonaVersionContent) -> PersonaMarkdownContent:
        profile = content.content.blocks if content.content else []
        return PersonaMarkdownContent(
            description=content.description,
            tags=content.tags,
            profile=to_markdown(_dump_blocks(profile)),
            modes=[
                PersonaModeMarkdown(
                    name=m.name,
                    trigger=m.trigger,
                    is_default=m.is_default,
                    identity_add=to_markdown(_dump_blocks(m.identity_add)),
                    output_style_override=to_markdown(_dump_blocks(m.output_style_override)),
                    anti_patterns=to_markdown(_dump_blocks(m.anti_patterns)),
                    playbook_id=m.playbook_id,
                    playbook_name=m.playbook_name,
                )
                for m in content.modes
            ],
            skills=content.skills,
        )

    def from_markdown_content(
        self,
        md: PersonaMarkdownContent,
        base: PersonaVersionContent | None,
        convert: _Converter,
    ) -> PersonaVersionContent:
        base_profile = base.content if base is not None else None
        profile_base = _Field("profile", _dump_blocks(base_profile.blocks if base_profile else []))
        profile = convert(md.profile, profile_base, "profile", False)
        if base_profile is None and not profile:
            persona_content: PersonaContent | None = None
        else:
            persona_content = PersonaContent(
                description=base_profile.description if base_profile else "",
                blocks=cast(Any, profile),
            )
        modes: list[dict[str, Any]] = []
        for mode in md.modes:
            old = _persona_base_mode(base, mode.name)
            fields: dict[str, Any] = {}
            for attr in _MODE_FIELDS:
                name = f"modes[{mode.name}].{attr}"
                old_blocks = _dump_blocks(getattr(old, attr)) if old is not None else []
                fields[attr] = convert(getattr(mode, attr), _Field(name, old_blocks), name, False)
            modes.append(
                {
                    "name": mode.name,
                    "trigger": mode.trigger,
                    "is_default": mode.is_default,
                    "playbook_id": mode.playbook_id,
                    "playbook_name": mode.playbook_name,
                    **fields,
                }
            )
        return cast(
            PersonaVersionContent,
            _validate(
                PersonaVersionContent,
                {
                    "description": md.description,
                    # Veraltete Felder zeigt Markdown nicht; sie bleiben aus der Basis.
                    "system_prompt": base.system_prompt if base is not None else "",
                    "traits": base.traits if base is not None else [],
                    "tags": md.tags,
                    "content": persona_content,
                    "modes": modes,
                    "skills": md.skills,
                },
                ("body", "content"),
            ),
        )

    def replace_field(
        self, content: PersonaVersionContent, field: str, blocks: list[Block]
    ) -> PersonaVersionContent:
        data = content.model_dump(mode="json")
        if field == "profile":
            profile = data.get("content") or {"description": "", "blocks": []}
            profile["blocks"] = blocks
            data["content"] = profile
        else:
            match = _MODE_FIELD_RE.fullmatch(field)
            assert match is not None
            for mode in data["modes"]:
                if mode["name"].lower() == match.group(1).lower():
                    mode[match.group(2)] = blocks
        return cast(
            PersonaVersionContent,
            _validate(PersonaVersionContent, data, ("body", "markdown")),
        )


class _BodyMapper:
    """Playbook, System-Prompt und externes Tool: ein stringifiziertes BlockNote-Feld."""

    def __init__(
        self,
        stored: type[BaseModel],
        markdown: type[BaseModel],
        field: str,
        *,
        empty: str = "",
    ) -> None:
        self._stored = stored
        self._markdown = markdown
        self._field = field
        self._empty = empty

    def fields(self, content: Any) -> list[_Field]:
        return [_Field(self._field, _body_blocks(getattr(content, self._field)))]

    def to_markdown_content(self, content: Any) -> BaseModel:
        data = content.model_dump(mode="json")
        data[self._field] = to_markdown(_body_blocks(data[self._field]))
        return self._markdown.model_validate(data)

    def from_markdown_content(self, md: Any, base: Any | None, convert: _Converter) -> BaseModel:
        base_body = getattr(base, self._field) if base is not None else ""
        blocks = convert(
            getattr(md, self._field),
            _Field(self._field, _body_blocks(base_body)),
            self._field,
            False,
        )
        data = md.model_dump(mode="json")
        data[self._field] = _body_string(blocks, base_body, empty=self._empty)
        return cast(BaseModel, _validate(self._stored, data, ("body", "content")))

    def replace_field(self, content: Any, field: str, blocks: list[Block]) -> BaseModel:
        data = content.model_dump(mode="json")
        data[self._field] = _body_string(blocks, data[self._field], empty=self._empty)
        return cast(BaseModel, _validate(self._stored, data, ("body", "markdown")))


class _ResourceMapper:
    def fields(self, content: ResourceContent) -> list[_Field]:
        return [_Field("body", _dump_blocks(content.blocks), allow_tables=True)]

    def to_markdown_content(self, content: ResourceContent) -> ResourceMarkdownContent:
        return ResourceMarkdownContent(
            description=content.description,
            body=to_markdown(_dump_blocks(content.blocks)),
            tags=content.tags,
        )

    def from_markdown_content(
        self, md: ResourceMarkdownContent, base: ResourceContent | None, convert: _Converter
    ) -> ResourceContent:
        old = _dump_blocks(base.blocks) if base is not None else []
        blocks = convert(md.body, _Field("body", old, allow_tables=True), "body", True)
        return cast(
            ResourceContent,
            _validate(
                ResourceContent,
                {"description": md.description, "blocks": blocks, "tags": md.tags},
                ("body", "content"),
            ),
        )

    def replace_field(
        self, content: ResourceContent, field: str, blocks: list[Block]
    ) -> ResourceContent:
        data = content.model_dump(mode="json")
        data["blocks"] = blocks
        return cast(ResourceContent, _validate(ResourceContent, data, ("body", "markdown")))


_MAPPERS: dict[str, _Mapper] = {
    "personas": _PersonaMapper(),
    "playbooks": _BodyMapper(PlaybookContent, PlaybookMarkdownContent, "body"),
    "resources": _ResourceMapper(),
    # Der Template-Body ist Pflicht (min_length=1): ein leeres Dokument ist `[]`.
    "system-prompts": _BodyMapper(
        SystemPromptTemplateContent, SystemPromptMarkdownContent, "body", empty="[]"
    ),
    "external_tools": _BodyMapper(ExternalToolContent, ExternalToolMarkdownContent, "usage_notes"),
}

# Gemeinsame Sicht auf die Read-Modelle der fuenf Elementarten.
_Read = Any


class _BaseRevRepo(Protocol):
    # Positionsparameter: die Repositories benennen den zweiten Parameter
    # unterschiedlich (`entity_id`, `template_id`).
    async def fetch_base_rev(
        self, workspace_id: UUID, entity_id: UUID, /
    ) -> tuple[int, str] | None: ...


# --- Teilaenderung (ADR-0058 §6.1 B) ----------------------------------------


def _section(blocks: list[Block], anchor: str) -> tuple[int, int] | None:
    """`[start, end)` des Abschnitts ab der Top-Level-Ueberschrift `anchor`."""
    for index, block in enumerate(blocks):
        if block.get("type") == "heading" and block.get("id") == anchor:
            level = int((block.get("props") or {}).get("level", 1))
            end = index + 1
            while end < len(blocks):
                other = blocks[end]
                if (
                    other.get("type") == "heading"
                    and int((other.get("props") or {}).get("level", 1)) <= level
                ):
                    break
                end += 1
            return index, end
    return None


def _inherit_anchor(markdown: str, anchor: str) -> str:
    """Anker-Erbe bei `replace` (ADR-0058 §6.1 B): beginnt das neue Markdown mit
    einer Ueberschrift ohne Anker, behaelt sie die ID der ersetzten."""
    lines = markdown.split("\n")
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if _HEADING_LINE_RE.match(line) and not _TRAILING_ANCHOR_RE.search(line):
            lines[index] = f"{line.rstrip()} [#{anchor}]"
        break
    return "\n".join(lines)


class ContentMarkdownService:
    """Markdown-Schreibweg ueber den bestehenden Services der fuenf Elementarten."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        personas: PersonaService,
        playbooks: PlaybookService,
        resources: ResourceService,
        system_prompts: SystemPromptTemplateService,
        external_tools: ExternalToolService,
        base_rev_repos: dict[str, _BaseRevRepo],
    ) -> None:
        self._pool = pool
        self._personas = personas
        self._playbooks = playbooks
        self._resources = resources
        self._system_prompts = system_prompts
        self._external_tools = external_tools
        self._base_rev_repos = base_rev_repos

    # --- Lesen ---------------------------------------------------------------

    async def _get(self, ctx: WorkspaceContext, et: str, entity_id: UUID) -> _Read:
        getters: dict[str, Callable[[WorkspaceContext, UUID], Awaitable[Any]]] = {
            "personas": self._personas.get,
            "playbooks": self._playbooks.get,
            "resources": self._resources.get,
            "system-prompts": self._system_prompts.get,
            "external_tools": self._external_tools.get,
        }
        return await getters[et](ctx, entity_id)

    async def _base_rev(self, ctx: WorkspaceContext, et: str, entity_id: UUID) -> tuple[int, str]:
        found = await self._base_rev_repos[et].fetch_base_rev(ctx.workspace_id, entity_id)
        assert found is not None  # das Element wurde eben im Workspace gelesen
        return found

    def _source(self, et: str, read: _Read, base_rev: str | None) -> dict[str, Any]:
        return {
            "entity_type": et,
            "id": read.id,
            "name": read.name,
            "locale": read.locale,
            "version": read.current_version,
            "status": read.current_status,
            "base_rev": base_rev,
            "content": _MAPPERS[et].to_markdown_content(read.content),
        }

    async def source(
        self, ctx: WorkspaceContext, et: MarkdownEntityType, entity_id: UUID
    ) -> MarkdownSource:
        """Quellfassung (`format=source`) mit `base_rev`, sofern die gelieferte
        Version das Schreibziel ist."""
        read = await self._get(ctx, et, entity_id)
        version, rev = await self._base_rev(ctx, et, entity_id)
        return MarkdownSource(
            **self._source(et, read, rev if version == read.current_version else None)
        )

    async def version_source(
        self, ctx: WorkspaceContext, et: MarkdownEntityType, entity_id: UUID, version: int
    ) -> MarkdownSource:
        """Quellfassung eines Versions-Snapshots (Vorlage fuer eine Wiederherstellung).

        Ohne `base_rev`: ein Snapshot ist nie das Schreibziel.
        """
        getters: dict[str, Callable[[WorkspaceContext, UUID, int], Awaitable[Any]]] = {
            "personas": self._personas.get_version,
            "playbooks": self._playbooks.get_version,
            "resources": self._resources.get_version,
            "system-prompts": self._system_prompts.get_version,
            "external_tools": self._external_tools.get_version,
        }
        snapshot = await getters[et](ctx, entity_id, version)
        current = await self._get(ctx, et, entity_id)
        return MarkdownSource(
            entity_type=et,
            id=entity_id,
            name=current.name,
            locale=snapshot.locale,
            version=snapshot.version,
            status=snapshot.status,
            base_rev=None,
            content=cast(Any, _MAPPERS[et].to_markdown_content(snapshot.content)),
        )

    # --- Pill-Labels (ADR-0058 §3.2) ------------------------------------------

    async def _label(self, ctx: WorkspaceContext, kind: str, target: str) -> str | None:
        if (kind, target) in _STATIC_LABELS:
            return _STATIC_LABELS[(kind, target)]
        if kind == "playbooks-catalog":
            return f"Playbook-Katalog ({'getriggert' if target == 'triggered' else 'alle'})"
        if kind == "resources-catalog":
            tag = target.strip()
            return (
                f"Resource-Katalog (Tag: {tag})"
                if tag and tag != "all"
                else ("Resource-Katalog (alle)")
            )
        try:
            if kind == "playbook":
                return f"Playbook: {(await self._playbooks.get(ctx, UUID(target))).name}"
            if kind == "resource":
                resource_id, _, block_id = target.partition("#")
                resource = await self._resources.get(ctx, UUID(resource_id))
                if not block_id:
                    return f"Resource: {resource.name}"
                for block in _walk(_dump_blocks(resource.content.blocks)):
                    if block.get("id") == block_id:
                        return f"Resource: {resource.name} › {block_plain_text(block)}"
                return f"Resource: {resource.name}"
            if kind == "tool-ref":
                items, _ = await self._external_tools.list_all(ctx, 500, None)
                for tool in items:
                    if tool.alias == target:
                        return f"Tool: {tool.content.display_name or tool.name}"
        except (ValueError, ApiError):
            # Ungueltige UUID oder kein Leserecht: kein Name, Fallback-Label.
            return None
        return None

    async def _labels(self, ctx: WorkspaceContext, texts: list[str]) -> dict[tuple[str, str], str]:
        wanted: list[tuple[str, str]] = []
        for text in texts:
            for match in _PILL_RE.finditer(text):
                key = (match.group(1), match.group(2))
                if key not in wanted:
                    wanted.append(key)
        labels: dict[tuple[str, str], str] = {}
        for kind, target in wanted[:_MAX_LABEL_LOOKUPS]:
            label = await self._label(ctx, kind, target)
            if label is not None:
                labels[(kind, target)] = label
        return labels

    def _converter(
        self, labels: dict[tuple[str, str], str], reserved: set[str] | None = None
    ) -> _Converter:
        def new_id(existing: set[str]) -> str:
            return default_new_block_id(existing | (reserved or set()))

        def convert(md: str, base: _Field | None, field: str, allow_tables: bool) -> list[Block]:
            try:
                return from_markdown(
                    md,
                    base.blocks if base is not None else None,
                    allow_tables=allow_tables,
                    resolve_label=lambda kind, target: labels.get((kind, target)),
                    new_id=new_id,
                )
            except MarkdownConversionError as exc:
                raise _conversion_error(exc, field) from exc

        return convert

    @staticmethod
    def _markdown_texts(md: BaseModel) -> list[str]:
        data = md.model_dump()
        texts = [v for k, v in data.items() if k in {"body", "profile", "usage_notes"}]
        for mode in data.get("modes") or []:
            texts.extend(mode[attr] for attr in _MODE_FIELDS)
        return [t for t in texts if isinstance(t, str)]

    # --- Verweise auf geloeschte Ueberschriften (ADR-0058 §4.2) ---------------

    async def _dangling_refs(
        self, et: str, entity_id: UUID, ctx: WorkspaceContext, removed: set[str]
    ) -> list[DanglingRef]:
        if et != "resources" or not removed:
            return []
        rows = await self._pool.fetch(
            "SELECT 'playbook' AS source_type, playbook_id AS source_id, block_id "
            "FROM playbook_resource_link "
            "WHERE workspace_id = $1 AND resource_id = $2 AND block_id = ANY($3::text[]) "
            "UNION ALL "
            "SELECT 'resource', parent_id, block_id FROM resource_composition "
            "WHERE workspace_id = $1 AND child_id = $2 AND block_id = ANY($3::text[]) "
            "ORDER BY 1, 2, 3",
            ctx.workspace_id,
            entity_id,
            sorted(removed),
        )
        return [DanglingRef(**dict(row)) for row in rows]

    async def _result(
        self,
        ctx: WorkspaceContext,
        et: str,
        read: _Read,
        removed: set[str],
    ) -> MarkdownWriteResult:
        version, rev = await self._base_rev(ctx, et, read.id)
        return MarkdownWriteResult(
            **self._source(et, read, rev if version == read.current_version else None),
            dangling_refs=await self._dangling_refs(et, read.id, ctx, removed),
        )

    # --- Anlegen -------------------------------------------------------------

    async def create(
        self, ctx: WorkspaceContext, et: MarkdownEntityType, data: MarkdownCreate
    ) -> MarkdownWriteResult:
        """Legt ein Element aus Markdown an (Anker sind dabei immer unbekannt)."""
        if data.slug is not None and et not in {"resources", "system-prompts"}:
            raise _invalid(("body", "slug"), _extra_field_error("slug"))
        if data.alias is not None and et != "external_tools":
            raise _invalid(("body", "alias"), _extra_field_error("alias"))
        md = _validate(MARKDOWN_CONTENT_MODELS[et], data.content, ("body", "content"))
        labels = await self._labels(ctx, self._markdown_texts(md))
        content = _MAPPERS[et].from_markdown_content(md, None, self._create_converter(labels))
        loc = ("body",)
        read: _Read
        if et == "personas":
            read = await self._personas.create(
                ctx,
                _validate(
                    PersonaCreate,
                    {"name": data.name, "content": content, "locale": data.locale},
                    loc,
                ),
            )
        elif et == "playbooks":
            read = await self._playbooks.create(
                ctx,
                _validate(
                    PlaybookCreate,
                    {"name": data.name, "content": content, "locale": data.locale},
                    loc,
                ),
            )
        elif et == "resources":
            read = await self._resources.create(
                ctx,
                _validate(
                    ResourceCreate,
                    {
                        "name": data.name,
                        "slug": data.slug,
                        "content": content,
                        "locale": data.locale,
                    },
                    loc,
                ),
            )
        elif et == "system-prompts":
            # Der JSON-Weg drosselt das Template nicht; der Markdown-Weg ist ein
            # Agentenweg und drosselt wie die anderen vier (P2a-Review).
            require_write_rate(ctx)
            read = await self._system_prompts.create(
                ctx,
                _validate(
                    SystemPromptTemplateCreate,
                    {
                        "name": data.name,
                        "slug": data.slug,
                        "content": content,
                        "locale": data.locale,
                    },
                    loc,
                ),
            )
        else:
            read = await self._external_tools.create(
                ctx,
                _validate(
                    ExternalToolCreate,
                    {
                        "name": data.name,
                        "alias": data.alias,
                        "content": content,
                        "locale": data.locale,
                    },
                    loc,
                ),
            )
        return await self._result(ctx, et, read, set())

    def _create_converter(self, labels: dict[tuple[str, str], str]) -> _Converter:
        inner = self._converter(labels)

        def convert(md: str, base: _Field | None, field: str, allow_tables: bool) -> list[Block]:
            return inner(md, None, field, allow_tables)

        return convert

    # --- Schreiben ueber die Services -----------------------------------------

    async def _write(
        self,
        ctx: WorkspaceContext,
        et: str,
        entity_id: UUID,
        *,
        name: str | None,
        locale: str | None,
        content: BaseModel,
        draft: bool,
    ) -> _Read:
        payload = {"name": name, "content": content, "locale": locale}
        loc = ("body",)
        if et == "personas":
            update = _validate(PersonaUpdate, payload, loc)
            svc_p = self._personas
            return await (svc_p.update_draft if draft else svc_p.update)(ctx, entity_id, update)
        if et == "playbooks":
            update = _validate(PlaybookUpdate, payload, loc)
            svc_b = self._playbooks
            return await (svc_b.update_draft if draft else svc_b.update)(ctx, entity_id, update)
        if et == "resources":
            update = _validate(ResourceUpdate, payload, loc)
            svc_r = self._resources
            return await (svc_r.update_draft if draft else svc_r.update)(ctx, entity_id, update)
        if et == "system-prompts":
            require_write_rate(ctx)
            update = _validate(SystemPromptTemplateUpdate, payload, loc)
            svc_s = self._system_prompts
            return await (svc_s.update_draft if draft else svc_s.update)(ctx, entity_id, update)
        update = _validate(ExternalToolUpdate, payload, loc)
        svc_e = self._external_tools
        return await (svc_e.update_draft if draft else svc_e.update)(ctx, entity_id, update)

    async def _read_base(
        self, ctx: WorkspaceContext, et: str, entity_id: UUID, expected: str | None
    ) -> _Read:
        """Liest die Basis und prueft einen erwarteten `base_rev` frueh dagegen.

        Der Token wird vor und nach dem Lesen geholt; aendert er sich dazwischen,
        ist die gelesene Basis nicht sicher die, die der Token beschreibt. Gibt
        es das Element im Workspace nicht, entscheidet das Lesen (404 bzw.
        Sichtbarkeit wie im JSON-Weg), nicht die Token-Abfrage.
        """
        if expected is None:
            return await self._get(ctx, et, entity_id)
        before = await self._base_rev_repos[et].fetch_base_rev(ctx.workspace_id, entity_id)
        read = await self._get(ctx, et, entity_id)
        after = await self._base_rev(ctx, et, entity_id)
        if before != after or after[1] != expected or after[0] != read.current_version:
            raise _version_conflict(after[0], after[1])
        return read

    async def put(
        self, ctx: WorkspaceContext, et: MarkdownEntityType, entity_id: UUID, data: MarkdownWrite
    ) -> MarkdownWriteResult:
        """Vollstand per Markdown, PUT-Semantik wie `update_*` (Draft auf aktiver Version)."""
        md = _validate(MARKDOWN_CONTENT_MODELS[et], data.content, ("body", "content"))
        base = await self._read_base(ctx, et, entity_id, data.base_rev)
        labels = await self._labels(ctx, self._markdown_texts(md))
        mapper = _MAPPERS[et]
        content = mapper.from_markdown_content(md, base.content, self._converter(labels))
        removed = self._removed_headings(mapper, base.content, content)
        with _conflict_as_409(), _maybe_expected(data.base_rev):
            read = await self._write(
                ctx,
                et,
                entity_id,
                name=data.name,
                locale=data.locale,
                content=content,
                draft=False,
            )
        return await self._result(ctx, et, read, removed)

    @staticmethod
    def _removed_headings(mapper: _Mapper, old: Any, new: Any) -> set[str]:
        old_ids: set[str] = set()
        new_ids: set[str] = set()
        for f in mapper.fields(old):
            old_ids |= _heading_ids(f.blocks)
        for f in mapper.fields(new):
            new_ids |= _heading_ids(f.blocks)
        return old_ids - new_ids

    async def edit(
        self, ctx: WorkspaceContext, et: MarkdownEntityType, entity_id: UUID, edit: ContentEdit
    ) -> MarkdownWriteResult:
        """Teilaenderung an einem Anker oder Feld; schreibt in den offenen Draft."""
        base = await self._read_base(ctx, et, entity_id, edit.base_rev)
        mapper = _MAPPERS[et]
        fields = mapper.fields(base.content)
        target, section = self._locate(fields, edit)
        doc_ids: set[str] = set()
        for f in fields:
            doc_ids |= _all_ids(f.blocks)
        labels = await self._labels(ctx, [edit.markdown or ""])
        convert = self._converter(labels, reserved=doc_ids)
        blocks = target.blocks
        start, end = section if section is not None else (0, len(blocks))
        if edit.op == "delete":
            new_blocks = blocks[:start] + blocks[end:]
        elif edit.op == "insert_after":
            inserted = convert(edit.markdown or "", None, target.name, target.allow_tables)
            new_blocks = blocks[:end] + inserted + blocks[end:]
        else:
            markdown = edit.markdown or ""
            if edit.anchor is not None:
                markdown = _inherit_anchor(markdown, edit.anchor)
            replaced = convert(
                markdown,
                _Field(target.name, blocks[start:end], target.allow_tables),
                target.name,
                target.allow_tables,
            )
            new_blocks = blocks[:start] + replaced + blocks[end:]
        content = mapper.replace_field(base.content, target.name, copy.deepcopy(new_blocks))
        removed = _heading_ids(blocks) - _heading_ids(new_blocks)
        with _conflict_as_409(), expected_base_rev(edit.base_rev):
            read = await self._write(
                ctx, et, entity_id, name=None, locale=None, content=content, draft=True
            )
        return await self._result(ctx, et, read, removed)

    @staticmethod
    def _locate(fields: list[_Field], edit: ContentEdit) -> tuple[_Field, tuple[int, int] | None]:
        if edit.field is not None:
            for f in fields:
                if f.name == edit.field or (
                    f.name.startswith("modes[") and f.name.lower() == edit.field.lower()
                ):
                    return f, None
            raise _anchor_unknown(
                f"Feld {edit.field!r} gibt es in diesem Element nicht. "
                f"Felder: {', '.join(f.name for f in fields)}.",
                field=edit.field,
            )
        assert edit.anchor is not None
        for f in fields:
            section = _section(f.blocks, edit.anchor)
            if section is not None:
                return f, section
        raise _anchor_unknown(
            f"Anker {edit.anchor!r} ist keine Ueberschrift auf oberster Ebene dieses "
            "Elements. Anker stehen in der Quellfassung (format=source) an den "
            "Ueberschriften.",
            anchor=edit.anchor,
        )


def _extra_field_error(field: str) -> ValidationError:
    """Ein `extra_forbidden`-Fehler fuer ein Feld, das diese Elementart nicht kennt."""

    class _Probe(BaseModel):
        model_config = {"extra": "forbid"}

    try:
        _Probe.model_validate({field: None})
    except ValidationError as exc:
        return exc
    raise AssertionError("unreachable")  # pragma: no cover


@contextmanager
def _maybe_expected(rev: str | None) -> Iterator[None]:
    if rev is None:
        yield
        return
    with expected_base_rev(rev):
        yield


__all__ = ["ContentMarkdownService"]
