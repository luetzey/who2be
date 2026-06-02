"""Placeholder-Registry und -Renderer fuer BlockNote-System-Prompt-Templates.

Track B (Nur-BlockNote): Der Body ist immer Stringified-BlockNote-JSON mit
Custom-Inline-Blocks vom Typ `placeholder`. Diese werden hier expandiert, bevor
der fertige Text an MCP-/Agent-Konsumenten geliefert wird.

`render_template_body` liefert `tuple[str, list[str]]` —
(expanded_text, unresolved_keys).

Oeffentliche API:
    render_template_body(body_text, ctx, db) -> tuple[str, list[str]]
    RenderContext
    ResolveResult
"""

from who2be_api.services.placeholders.registry import (
    REGISTRY,
    RenderContext,
    ResolveResult,
    render_skills_table,
)
from who2be_api.services.placeholders.renderer import render_template_body

__all__ = [
    "REGISTRY",
    "RenderContext",
    "ResolveResult",
    "render_skills_table",
    "render_template_body",
]
