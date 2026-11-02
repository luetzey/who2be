"""Sprache der festen Placeholder-Saetze (Kanban t_1ba0cf7d).

`persona-ref`, `playbooks-catalog`, `resources-catalog`, `memory` und der
Rahmen von `tools-overview` rendern ihre festen Saetze in der Sprache des
Templates (`RenderContext.locale`); fehlt sie, gilt Deutsch. Die kuratierten
Werkzeug-Beschreibungen von `tools-overview` bleiben deutsch (nicht Teil der
Karte).

Der Golden-Hash `_DE_GOLDEN_SHA256` wurde am Code VOR der Zentralisierung
(origin/main f9697fab) berechnet: er haelt den deutschen Render ueber alle
Varianten byte-identisch fest.
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import re
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from who2be_api.repositories.builder_content import get_content_pack
from who2be_api.repositories.workspace_repository import _builder_tool_policy
from who2be_api.services.agent_language import date_locale
from who2be_api.services.placeholders._core import RenderContext
from who2be_api.services.placeholders._texts import texts_for
from who2be_api.services.placeholders.renderer import render_template_body
from who2be_api.services.placeholders.resolvers import (
    MemoryPromptResolver,
    PersonaRefResolver,
    PlaybooksCatalogResolver,
    ResourcesCatalogResolver,
    ToolsOverviewResolver,
)
from who2be_api.services.placeholders.resolvers.tools import _TOOLS
from who2be_models import AgentToolPolicy, MemoryDirective, MemoryMode, ReadScope

_PID = UUID("00000000-0000-0000-0000-000000000001")
_AID = UUID("00000000-0000-0000-0000-000000000002")
_WS = UUID("00000000-0000-0000-0000-000000000099")

# Markante deutsche Woerter der festen Saetze. Treffer im EN-Render = Defekt.
_GERMAN = re.compile(
    r"\b(der|die|das|und|ist|nicht|dein|deine|dir|du|mit|fuer|ueber|wenn|oder|"
    r"Verfuegbare|Aufruf|Beschreibung|Gedaechtnis|Nutzer|Lade|Pruefe)\b",
    re.IGNORECASE,
)


def _row(data: dict[str, Any]) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda k: data[k])
    return row


def _db(fetchrow: Any = None, fetch: Any = None) -> MagicMock:
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value=fetchrow)
    db.fetch = AsyncMock(return_value=fetch or [])
    return db


def _ctx(locale: str | None, policy: AgentToolPolicy | None = None, **kw: Any) -> RenderContext:
    args: dict[str, Any] = {
        "workspace_id": _WS,
        "persona_id": _PID,
        "now": datetime(2026, 5, 31, tzinfo=UTC),
        "tool_policy": policy,
        "agent_id": _AID if policy else None,
    }
    if locale is not None:
        args["locale"] = locale
    return RenderContext(**args, **kw)


def _policies() -> list[AgentToolPolicy | None]:
    """None plus Scope x alle-Flags-an/aus x Memory-Modus x Direktive."""
    bools = [n for n, f in AgentToolPolicy.model_fields.items() if f.annotation is bool]
    out: list[AgentToolPolicy | None] = [None]
    for scope, on, mode, directive in itertools.product(
        list(ReadScope), [False, True], list(MemoryMode), list(MemoryDirective)
    ):
        out.append(
            AgentToolPolicy.model_validate(
                {
                    "playbook_read": scope,
                    "resource_read": scope,
                    "agent_read": scope,
                    "memory_mode": mode,
                    "memory_directive": directive,
                    **{b: on for b in bools},
                }
            )
        )
    return out


async def _render_all(locale: str | None) -> dict[str, str]:
    """Rendert alle betroffenen Placeholder ueber die relevanten Varianten."""
    out: dict[str, str] = {}
    out["persona-ref"] = (
        await PersonaRefResolver().resolve("", _ctx(locale), _db(_row({"name": "Lena"})))
    ).text
    playbooks = [
        _row({"id": _PID, "name": "A|B", "triggers": "x, y", "content": {"description": "d"}}),
        _row({"id": _AID, "name": "C", "triggers": None, "content": {"description": "e"}}),
    ]
    for target in ("all", "triggered"):
        out[f"pb:{target}"] = (
            await PlaybooksCatalogResolver().resolve(target, _ctx(locale), _db(fetch=playbooks))
        ).text
        out[f"pb-empty:{target}"] = (
            await PlaybooksCatalogResolver().resolve(target, _ctx(locale), _db(fetch=[]))
        ).text
    resources = [_row({"id": _PID, "name": "R", "content": {"description": "d", "tags": ["t"]}})]
    many = [
        _row({"id": _PID, "name": f"R{i}", "content": {"description": "d", "tags": []}})
        for i in range(101)
    ]
    for target in ("all", "billing"):
        out[f"res:{target}"] = (
            await ResourcesCatalogResolver().resolve(target, _ctx(locale), _db(fetch=resources))
        ).text
        out[f"res-empty:{target}"] = (
            await ResourcesCatalogResolver().resolve(target, _ctx(locale), _db(fetch=[]))
        ).text
    out["res-overflow"] = (
        await ResourcesCatalogResolver().resolve("all", _ctx(locale), _db(fetch=many))
    ).text
    for i, policy in enumerate(_policies()):
        for explicit in (False, True):
            ctx = _ctx(locale, policy, has_explicit_memory=explicit)
            out[f"tools:{i}:{explicit}"] = (
                await ToolsOverviewResolver().resolve("", ctx, _db())
            ).text
        out[f"memory:{i}"] = (
            await MemoryPromptResolver().resolve("", _ctx(locale, policy), _db())
        ).text
    return out


def _digest(renders: dict[str, str]) -> str:
    blob = json.dumps(renders, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


_DE_GOLDEN_SHA256 = "2294a4c8f209f1fac8701c1373af75f0ca9d69c36928dc75ecad769964e9ca2c"


@pytest.mark.parametrize("locale", [None, "de-DE", "de", "fr-FR"])
def test_german_render_byte_identical_to_before(locale: str | None) -> None:
    """DE, fehlende und unbekannte Sprache rendern exakt den Stand vor der Karte."""
    assert _digest(asyncio.run(_render_all(locale))) == _DE_GOLDEN_SHA256


def _strip_tool_descriptions(text: str) -> str:
    """Entfernt die kuratierten (deutschen) Werkzeug-Beschreibungen aus dem Render.

    Sie sind bewusst nicht Teil der Karte; Rahmen und Scope-Suffixe bleiben
    stehen und werden geprueft.
    """
    for tool in _TOOLS:
        text = text.replace(tool.description, "")
    return text


def test_english_render_has_no_german_fixed_sentence() -> None:
    renders = asyncio.run(_render_all("en-US"))
    offenders = {
        key: _GERMAN.findall(_strip_tool_descriptions(text))
        for key, text in renders.items()
        if _GERMAN.search(_strip_tool_descriptions(text))
    }
    assert offenders == {}


def test_english_differs_from_german_for_every_placeholder_kind() -> None:
    de = asyncio.run(_render_all("de-DE"))
    en = asyncio.run(_render_all("en-US"))
    for prefix in ("persona-ref", "pb:", "pb-empty:", "res:", "res-empty:", "res-overflow"):
        keys = [k for k in de if k.startswith(prefix)]
        assert keys, prefix
        assert all(de[k] != en[k] for k in keys), prefix
    # tools-overview: Rahmen englisch, Gedaechtnis-Auto-Append englisch.
    assert all(en[k].startswith("## Available tools") for k in en if k.startswith("tools:"))
    assert all(de[k].startswith("## Verfuegbare Werkzeuge") for k in de if k.startswith("tools:"))
    memory_on = [k for k in de if k.startswith("memory:") and de[k]]
    assert memory_on
    assert all(en[k].startswith("**Long-term memory") for k in memory_on)


def test_persona_ref_english_wording() -> None:
    text = asyncio.run(
        PersonaRefResolver().resolve("", _ctx("en-US"), _db(_row({"name": "Lena"})))
    ).text
    assert text.startswith("Your persona is **Lena**")
    assert f'get_persona("{_PID}")' in text
    assert f'get_persona("{_PID}", mode="<mode name>")' in text
    # Die Ueberschrift, auf die verwiesen wird, rendert get_persona sprachunabhaengig.
    assert "`## Modi`" in text


def test_english_scope_suffix_and_notes() -> None:
    policy = AgentToolPolicy(playbook_write=True)  # Reads `assigned`, feedback_write an
    text = asyncio.run(ToolsOverviewResolver().resolve("", _ctx("en-US", policy), _db())).text
    assert "**only the playbooks assigned to you**" in text
    assert "**Write access:**" in text
    assert "**Feedback (do this routinely):**" in text
    assert "**How playbooks are invoked:**" in text


@pytest.mark.parametrize(
    ("locale", "heading"),
    [
        (None, "## Deine Playbooks"),
        ("de-DE", "## Deine Playbooks"),
        ("en", "## Your playbooks"),
        ("en-US", "## Your playbooks"),
        ("EN-gb", "## Your playbooks"),
        ("fr", "## Deine Playbooks"),
    ],
)
def test_texts_for_resolves_language_with_german_fallback(locale: str | None, heading: str) -> None:
    assert texts_for(locale).playbooks_heading == heading


async def _render_builder(lang: str) -> str:
    """Rendert das echte Builder-Template `lang` wie der Agent-Render-Pfad.

    Locale aus der Template-Sprache (`date_locale`), Builder-Policy aus dem
    Seed. Inhalte (Persona-, Playbook-, Resource-Namen) sind neutrale
    Platzhalterwoerter, damit nur die festen Saetze geprueft werden.
    """
    template = next(t for t in get_content_pack(lang).templates if t.slug == "agent-builder")
    content = {"name": "PERSONA_NAME", "content": {"description": "PERSONA_DESC"}}
    item = {
        "id": _PID,
        "name": "CONTENT_NAME",
        "triggers": "CONTENT_TRIGGER",
        "content": {"description": "CONTENT_DESC", "tags": ["CONTENT_TAG"]},
    }
    ctx = RenderContext(
        workspace_id=_WS,
        persona_id=_PID,
        now=datetime(2026, 10, 24, tzinfo=UTC),
        locale=date_locale(lang),
        tool_policy=AgentToolPolicy.model_validate(_builder_tool_policy()),
        agent_id=_AID,
    )
    text, unresolved = await render_template_body(
        template.load_body(lang), ctx, _db(_row(content), [_row(item)])
    )
    assert unresolved == []
    return text


# sha256 des DE-Builder-Renders, berechnet am Code vor der Karte (f9697fab).
_DE_BUILDER_GOLDEN_SHA256 = "5de42df90399443da56bcb08be14328a0bfe67cba600107eea77465a4a6eeeb1"


def test_builder_template_de_render_unchanged() -> None:
    text = asyncio.run(_render_builder("de"))
    assert hashlib.sha256(text.encode()).hexdigest() == _DE_BUILDER_GOLDEN_SHA256


def test_builder_template_en_render_has_no_german_fixed_sentence() -> None:
    text = asyncio.run(_render_builder("en"))
    # Alle vier Placeholder-Arten des Builder-Templates rendern englisch.
    assert "Your persona is **PERSONA_NAME**" in text
    assert "## Your playbooks" in text
    assert "## Available resources" in text
    assert "**Long-term memory (with approval):**" in text
    assert _GERMAN.findall(text) == []
