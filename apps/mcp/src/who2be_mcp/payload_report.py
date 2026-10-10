"""Messung des `tools/list`-Katalogs je Referenzprofil (MCP-Token T1).

Der Katalog-Guard in `tests/test_tool_payload_budget.py` misst die volle Liste
aller Werkzeuge. Beim Start eines Agenten kommt aber nur die Teilmenge an, die
der `PolicyFilterMiddleware` fuer dessen Rechte durchlaesst (ADR-0042). Dieses
Modul misst beides an einer Stelle, damit Test, Bericht und Doku dieselben
Zahlen sehen:

- `wire_tools()` holt die `tools`-Liste so, wie `tools/list` sie auf den Draht
  legt (In-Memory-Client, echter Handler, utf-8, `ensure_ascii=False`).
- `REFERENCE_PROFILES` sind die vier Profile aus der Kennzahl M2. Gefiltert
  wird mit `is_tool_visible_for`, also derselben Funktion, die die Middleware
  mit den `whoami`-Feldern aufruft.
- `first_sentence()` und `developer_refs()` sind die Grundlage der Guards fuer
  den Kurzkatalog (Hermes, Claude Code) und fuer Entwickler-Historie im Draht.

Aufruf fuer die Tabellen in `docs/mcp-payload-budget.md`:

    uv run python -m who2be_mcp.payload_report
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from fastmcp import Client, FastMCP

from who2be_mcp.instructions import ALWAYS_LOAD_KEY
from who2be_models import (
    AgentToolPolicy,
    MemoryMode,
    ReadScope,
    WorkspaceRole,
    is_tool_visible_for,
)

WireTool = dict[str, Any]

# Entwickler-Historie, die im Draht nichts erklaert: ADR-Nummern, Phasen,
# Tracks, Wellen, Arbeitspakete, Gap-Nummern. Wortgrenzen, damit etwa
# „Phasenmodell" oder „Trackpad" nicht treffen.
_DEVELOPER_REF = re.compile(
    r"\bADR-?\d+|\bPhase\b|\bTrack\b|\bWelle\b|\bWP-?\d+|\bWP-[A-Z]\b|\bGap \d"
)

# Satzende: Punkt, Ausrufe- oder Fragezeichen vor Leerraum. Der Doppelpunkt
# zaehlt nicht — „Liefert X: Y." ist ein Satz.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s")


def _bytes(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode())


async def wire_tools(server: FastMCP) -> list[WireTool]:
    """Die `tools`-Liste in Draht-Form, wie `tools/list` sie liefert."""
    async with Client(server) as client:
        result = await client.list_tools_mcp()
    tools: list[WireTool] = result.model_dump(mode="json", by_alias=True, exclude_none=True)[
        "tools"
    ]
    return tools


def payload_bytes(tools: list[WireTool]) -> int:
    """Groesse einer `tools`-Liste in Bytes (utf-8, ohne JSON-RPC-Umschlag)."""
    return _bytes(tools)


@dataclass(frozen=True)
class ReferenceProfile:
    """Ein Principal, wie ihn `whoami` an den Filter uebergibt."""

    key: str
    label: str
    unrestricted: bool
    role: WorkspaceRole
    policy: AgentToolPolicy | None

    def sees(self, name: str) -> bool:
        """Sieht dieses Profil das Werkzeug? Unbekannte Namen: fail-open wie die Middleware."""
        policy = self.policy
        visible = is_tool_visible_for(
            name,
            unrestricted=self.unrestricted,
            role=self.role,
            capabilities=None if policy is None else policy.granted_capabilities(),
            read_scopes=None if policy is None else policy.read_scopes(),
            memory_mode=None if policy is None else policy.memory_mode,
        )
        return visible is not False


_BUILDER_POLICY = AgentToolPolicy(
    playbook_read=ReadScope.all,
    resource_read=ReadScope.all,
    agent_read=ReadScope.all,
    persona_write=True,
    playbook_write=True,
    resource_write=True,
    agent_write=True,
    system_prompt_write=True,
    feedback_resolve=True,
    promote_retire=True,
    external_tool_write=True,
    workarea_write=True,
    kb_write=True,
    kb_edge_write=True,
    case_triage=True,
    memory_mode=MemoryMode.suggest,
)

REFERENCE_PROFILES: tuple[ReferenceProfile, ...] = (
    ReferenceProfile(
        key="default",
        label="Agent, Default-Policy",
        unrestricted=False,
        role=WorkspaceRole.editor,
        policy=AgentToolPolicy(),
    ),
    ReferenceProfile(
        key="default_memory",
        label="Agent, Default + Gedaechtnis `suggest`",
        unrestricted=False,
        role=WorkspaceRole.editor,
        policy=AgentToolPolicy(memory_mode=MemoryMode.suggest),
    ),
    ReferenceProfile(
        key="builder",
        label="Agent, Builder (alle Rechte, Lesen `all`)",
        unrestricted=False,
        role=WorkspaceRole.editor,
        policy=_BUILDER_POLICY,
    ),
    ReferenceProfile(
        key="editor",
        label="Mensch/JWT, Rolle editor",
        unrestricted=True,
        role=WorkspaceRole.editor,
        policy=None,
    ),
)


def visible_tools(tools: list[WireTool], profile: ReferenceProfile) -> list[WireTool]:
    """Die Teilmenge, die `tools/list` diesem Profil liefert (Reihenfolge bleibt)."""
    return [tool for tool in tools if profile.sees(tool["name"])]


def always_loaded(tools: list[WireTool]) -> list[WireTool]:
    """Werkzeuge mit `_meta["anthropic/alwaysLoad"]`: Claude Code laedt sie sofort."""
    return [tool for tool in tools if (tool.get("_meta") or {}).get(ALWAYS_LOAD_KEY) is True]


def tool_search_start_bytes(tools: list[WireTool], instructions: str | None) -> int:
    """Was Claude Code mit Tool Search beim Start laedt, in Bytes.

    Laut Claude-Code-Doku: Server-`instructions`, die Namen aller Werkzeuge
    und das volle Schema der `alwaysLoad`-Werkzeuge. Der Rest kommt erst nach
    einer Suche. Das ist eine Naeherung an den Kontext, nicht die Draht-Form:
    `tools/list` geht weiterhin vollstaendig ueber die Leitung.
    """
    eager = always_loaded(tools)
    eager_names = {tool["name"] for tool in eager}
    names = [tool["name"] for tool in tools if tool["name"] not in eager_names]
    eager_bytes = payload_bytes(eager) if eager else 0
    return len((instructions or "").encode()) + _bytes(names) + eager_bytes


def first_sentence(description: str | None) -> str:
    """Der erste Satz einer Beschreibung, Leerraum zusammengezogen.

    Das ist, was Kurzkataloge (Hermes `tool_search`, Claude Code Tool Search)
    ohne Suche zeigen. Ein Absatzwechsel beendet den Satz ebenfalls.
    """
    paragraph = (description or "").strip().split("\n\n", 1)[0]
    text = " ".join(paragraph.split())
    return _SENTENCE_END.split(text, maxsplit=1)[0]


def _descriptions(node: object) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "description" and isinstance(value, str):
                yield value
            else:
                yield from _descriptions(value)
    elif isinstance(node, list):
        for item in node:
            yield from _descriptions(item)


def developer_refs(tool: WireTool) -> list[str]:
    """Texte im `inputSchema` eines Werkzeugs, die Entwickler-Historie tragen.

    Gezaehlt werden die `description`-Texte des Schemas (Pydantic-Docstrings,
    Feldbeschreibungen), nicht die Werkzeugbeschreibung selbst — die kuerzt T3.
    Ein Text, der denselben Docstring in mehreren `$defs` wiederholt, zaehlt
    je Vorkommen: genau so oft liegt er auf dem Draht.
    """
    return [
        text for text in _descriptions(tool.get("inputSchema", {})) if _DEVELOPER_REF.search(text)
    ]


@dataclass(frozen=True)
class ToolCost:
    name: str
    total: int
    description: int
    schema: int


def tool_costs(tools: list[WireTool]) -> list[ToolCost]:
    """Kosten je Werkzeug, teuerstes zuerst."""
    costs = [
        ToolCost(
            name=tool["name"],
            total=_bytes(tool),
            description=len((tool.get("description") or "").encode()),
            schema=_bytes(tool.get("inputSchema", {})),
        )
        for tool in tools
    ]
    return sorted(costs, key=lambda cost: (-cost.total, cost.name))


def _fmt(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def report(tools: list[WireTool], instructions: str | None = None) -> str:
    """Die Tabellen fuer `docs/mcp-payload-budget.md` als Markdown.

    Je Profil: Draht-Bytes von `tools/list` und, daneben, was Claude Code mit
    Tool Search beim Start in den Kontext laedt (`tool_search_start_bytes`).
    """
    lines = [
        "| Profil | Werkzeuge | Bytes | davon sofort geladen | Start mit Tool Search |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    rows = [(profile.label, visible_tools(tools, profile)) for profile in REFERENCE_PROFILES]
    rows.append(("alle Werkzeuge (Guard)", tools))
    for label, subset in rows:
        eager = always_loaded(subset)
        lines.append(
            f"| {label} | {len(subset)} | {_fmt(payload_bytes(subset))} "
            f"| {len(eager)} / {_fmt(payload_bytes(eager))} "
            f"| {_fmt(tool_search_start_bytes(subset, instructions))} |"
        )
    lines.append("")
    lines.append(f"Server-`instructions`: {_fmt(len((instructions or '').encode()))} Bytes.")
    lines += [
        "",
        "| # | Werkzeug | gesamt | Beschreibung | Schema |",
        "| ---: | --- | ---: | ---: | ---: |",
    ]
    for rank, cost in enumerate(tool_costs(tools)[:10], start=1):
        lines.append(
            f"| {rank} | `{cost.name}` | {_fmt(cost.total)} | {_fmt(cost.description)} "
            f"| {_fmt(cost.schema)} |"
        )
    return "\n".join(lines)


def main() -> None:
    """Druckt den Bericht fuer den registrierten Server."""
    from who2be_mcp.server import mcp  # spaet: der Server-Import registriert alle Werkzeuge

    print(report(asyncio.run(wire_tools(mcp)), mcp.instructions))


if __name__ == "__main__":
    main()
