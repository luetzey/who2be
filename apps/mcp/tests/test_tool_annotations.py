"""`readOnlyHint` auf dem Draht: Lesewerkzeuge ja, Schreibwerkzeuge nie.

Die Klassifikation kommt aus `MCP_TOOL_REQUIREMENTS` (`is_read_only`). Damit
der Test nicht nur die Quelle gegen sich selbst prueft, haelt er sie gegen eine
unabhaengige Regel: das Verb im Werkzeugnamen. Jedes Werkzeug muss genau
einer Verbgruppe angehoeren; ein Lese-Verb ohne `readOnlyHint` oder ein
Schreib-Verb mit `readOnlyHint` ist ein Fehler. Die einzige bewusste Ausnahme
steht in `_VERB_EXCEPTIONS` mit Begruendung.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest
from fastmcp import Client

from who2be_mcp import tool_annotations
from who2be_mcp.server import mcp
from who2be_models import MCP_TOOL_REQUIREMENTS, AgentCapability, ToolRequirement

_READ_VERBS = re.compile(
    r"^(ping|whoami|search|timeline|neighbors"
    r"|(get|list|fetch|find|diff|describe|query|read|search)_.+)$"
)
_WRITE_VERBS = re.compile(
    r"^(ingest|(create|update|delete|restore|transition|set|submit|save|insert|append"
    r"|patch|upsert|assign|link|convert|triage|promote|record|report|resolve|propose"
    r"|copy|edit)_.+)$"
)
# Lese-Verb, aber schreibend: fuer einen Agenten kann beim Abruf ein
# `follow_up_prepared`-Ereignis entstehen (Massnahmen-Nachschau).
_VERB_EXCEPTIONS = {"get_follow_up": False}


async def _wire() -> list[dict[str, Any]]:
    async with Client(mcp) as client:
        result = await client.list_tools_mcp()
    tools: list[dict[str, Any]] = result.model_dump(mode="json", by_alias=True, exclude_none=True)[
        "tools"
    ]
    return tools


def _hint(tool: dict[str, Any]) -> bool:
    return bool((tool.get("annotations") or {}).get("readOnlyHint"))


def _expected_read_only(name: str) -> bool | None:
    """Erwartung aus dem Verb; `None`, wenn der Name keiner Gruppe angehoert."""
    if name in _VERB_EXCEPTIONS:
        return _VERB_EXCEPTIONS[name]
    is_read, is_write = bool(_READ_VERBS.match(name)), bool(_WRITE_VERBS.match(name))
    if is_read == is_write:
        return None
    return is_read


def _offenders(tools: list[dict[str, Any]]) -> dict[str, str]:
    found: dict[str, str] = {}
    for tool in tools:
        name = tool["name"]
        if name not in MCP_TOOL_REQUIREMENTS:
            found[name] = "fehlt in MCP_TOOL_REQUIREMENTS"
            continue
        expected = _expected_read_only(name)
        if expected is None:
            found[name] = "Verb keiner Gruppe zuzuordnen"
        elif _hint(tool) != expected:
            found[name] = f"readOnlyHint={_hint(tool)}, erwartet {expected}"
        elif _hint(tool) != MCP_TOOL_REQUIREMENTS[name].is_read_only:
            found[name] = "Draht weicht von MCP_TOOL_REQUIREMENTS ab"
    return found


def test_every_tool_is_classified_and_hinted_by_its_verb() -> None:
    tools = asyncio.run(_wire())
    assert len(tools) == len(MCP_TOOL_REQUIREMENTS)
    offenders = _offenders(tools)
    assert not offenders, (
        f"readOnlyHint stimmt nicht: {offenders}. Lesend/schreibend kommt aus "
        "`ToolRequirement.is_read_only` (bei Lesewerkzeugen hinter einer Capability "
        "`read_only=True` setzen)."
    )
    read_only = {tool["name"] for tool in tools if _hint(tool)}
    assert {"ping", "whoami", "search", "query_table", "get_dossier"} <= read_only
    assert not {"create_persona", "delete_artifact", "save_memory", "get_follow_up"} & read_only


def test_write_tools_carry_no_annotations_at_all() -> None:
    """Schreibwerkzeuge bleiben ohne Annotation (Spec-Default: nicht lesend)."""
    tools = asyncio.run(_wire())
    annotated = sorted(t["name"] for t in tools if t.get("annotations") and not _hint(t))
    assert annotated == []


def test_red_probe_write_tool_marked_read_only_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rot-Probe: ein Schreibwerkzeug als lesend markiert faellt auf."""
    fake = dict(MCP_TOOL_REQUIREMENTS)
    fake["create_persona"] = ToolRequirement(
        capabilities=(AgentCapability.persona_write,), read_only=True
    )
    monkeypatch.setattr(tool_annotations, "MCP_TOOL_REQUIREMENTS", fake)
    assert "create_persona" in _offenders(asyncio.run(_wire()))


def test_red_probe_read_tool_without_hint_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gegenrichtung: ein Lesewerkzeug ohne Hinweis faellt ebenfalls auf."""
    fake = dict(MCP_TOOL_REQUIREMENTS)
    fake["get_dossier"] = ToolRequirement(capabilities=(AgentCapability.case_triage,))
    monkeypatch.setattr(tool_annotations, "MCP_TOOL_REQUIREMENTS", fake)
    assert "get_dossier" in _offenders(asyncio.run(_wire()))


def test_get_tool_path_carries_the_hint_too() -> None:
    """Auch der Einzelabruf (`get_tool`, vor `tools/call`) traegt die Annotation."""
    read = asyncio.run(mcp.get_tool("search_kb"))
    write = asyncio.run(mcp.get_tool("create_node"))
    assert read is not None and read.annotations is not None
    assert read.annotations.read_only_hint is True
    assert write is not None and write.annotations is None
