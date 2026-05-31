"""Placeholder-Registry und -Renderer fuer BlockNote-System-Prompt-Templates.

Welle 5 (Phase 3 Runde 3): Templates koennen `body_format='blocknote'`
tragen. Der Body ist dann Stringified-BlockNote-JSON mit Custom-Inline-Blocks
vom Typ `placeholder`. Diese werden hier expandiert, bevor der fertige Text
an MCP-Konsumenten geliefert wird.

Welle 6 (Phase 3 Runde 3 Followup): `render_template_body` liefert jetzt
`tuple[str, list[str]]` — (expanded_text, unresolved_keys).

Oeffentliche API:
    render_template_body(body_text, body_format, ctx, db) -> tuple[str, list[str]]
    RenderContext
    ResolveResult
"""

from who2be_api.services.placeholders.registry import REGISTRY, RenderContext, ResolveResult
from who2be_api.services.placeholders.renderer import render_template_body

__all__ = ["REGISTRY", "RenderContext", "ResolveResult", "render_template_body"]
