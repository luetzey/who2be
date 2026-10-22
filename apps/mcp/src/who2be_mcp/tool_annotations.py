"""MCP-Annotation `readOnlyHint` je Werkzeug aus `MCP_TOOL_REQUIREMENTS`.

Clients entscheiden an `readOnlyHint`, ob sie vor einem Aufruf nachfragen:
ChatGPT behandelt ein Werkzeug ohne den Hinweis als Schreibaktion und fragt bei
jedem Aufruf, auch Claude wertet ihn aus. Die Klassifikation lesen/schreiben
kommt aus derselben Quelle wie die Sichtbarkeit (`ToolRequirement.is_read_only`),
damit es keine zweite, von Hand gepflegte Liste gibt.

Gesetzt wird nur `readOnlyHint: true` an Lesewerkzeugen. Schreibwerkzeuge und
Werkzeuge ohne Eintrag im Mapping bekommen keine Annotation; laut MCP-Spezifikation
gilt dann `readOnlyHint: false`, ein Client fragt also nach. `destructiveHint`
bleibt ungesetzt (Default der Spezifikation: `true` fuer Schreibwerkzeuge).

Umgesetzt als fastmcp-`Transform` auf dem Server: er sieht alle Werkzeuge, auch
die aus `tools/*.register`, und gilt fuer `tools/list` wie fuer `get_tool`.
"""

from __future__ import annotations

from collections.abc import Sequence

from fastmcp.server.transforms import GetToolNext, Transform
from fastmcp.tools.base import Tool
from fastmcp.utilities.versions import VersionSpec
from mcp.types import ToolAnnotations

from who2be_models import MCP_TOOL_REQUIREMENTS


def is_read_only_tool(name: str) -> bool:
    """Lesewerkzeug laut Mapping? Unbekannte Namen gelten als schreibend."""
    requirement = MCP_TOOL_REQUIREMENTS.get(name)
    return requirement is not None and requirement.is_read_only


def annotate(tool: Tool) -> Tool:
    """Gleicht `readOnlyHint` an `tool` mit dem Mapping ab.

    Bewusst am Objekt selbst statt an einer Kopie: wer ein Werkzeug aus
    `list_tools()` veraendert (die Rot-Probe im Payload-Budget-Test setzt
    `title`/`meta`), veraendert weiter das, was auf den Draht geht. Damit ein
    einmal gesetzter Hinweis nicht kleben bleibt, nimmt der Abgleich ihn auch
    wieder zurueck, wenn das Mapping „schreibend“ sagt.
    """
    wanted = is_read_only_tool(tool.name)
    current = tool.annotations
    if wanted:
        if current is None:
            tool.annotations = ToolAnnotations(read_only_hint=True)
        elif current.read_only_hint is not True:
            tool.annotations = current.model_copy(update={"read_only_hint": True})
    elif current is not None and current.read_only_hint is not None:
        rest = current.model_copy(update={"read_only_hint": None})
        tool.annotations = rest if rest.model_dump(exclude_none=True) else None
    return tool


class ReadOnlyHintTransform(Transform):
    """Setzt `readOnlyHint` an jedem Lesewerkzeug (siehe Modul-Docstring)."""

    async def list_tools(self, tools: Sequence[Tool]) -> Sequence[Tool]:
        return [annotate(tool) for tool in tools]

    async def get_tool(
        self, name: str, call_next: GetToolNext, *, version: VersionSpec | None = None
    ) -> Tool | None:
        tool = await call_next(name, version=version)
        return None if tool is None else annotate(tool)
