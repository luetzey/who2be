"""Placeholder-Renderer fuer BlockNote-System-Prompt-Templates.

Traversiert BlockNote-JSON, sammelt alle Inline-Elemente vom Typ
`placeholder`, ruft den passenden Resolver aus dem REGISTRY-Dict auf und
gibt den expandierten Plain-Text-String zurueck.

Saubere Trennung: _walk_blocks kummert sich ums Walking, REGISTRY ums Resolving.

Nicht-gefundene Resolver -> lokalisierter Fehler-String, kein Exception.
Der Renderer laeuft robust durch.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

from who2be_api.services.placeholders.registry import REGISTRY, RenderContext

logger = logging.getLogger(__name__)


async def render_template_body(
    body_text: str,
    body_format: str,
    ctx: RenderContext,
    db: asyncpg.Connection,
) -> str:
    """Expandiert Placeholders im Template-Body.

    Bei `body_format != 'blocknote'` wird der Body unveraendert zurueckgegeben
    (rueckwaertskompatibel mit bestehenden `plain`-Templates).

    Akzeptiert zwei BlockNote-JSON-Shapes:
    - Top-Level-Array `[{...block...}, ...]` (was `editor.document` liefert
      und was Frontend in `body` schreibt) — der Default.
    - Wrapper-Objekt `{"content": [{...block...}, ...]}` (was BlockNote bei
      anderen Export-Pfaden produziert und was die Unit-Tests bisher
      benutzten).

    Args:
        body_text:   Der rohe Template-Body-String aus der Datenbank.
        body_format: `'plain'` oder `'blocknote'`.
        ctx:         Render-Kontext (workspace_id, persona_id, jetzt).
        db:          asyncpg-Connection fuer DB-Lookups der Resolver.

    Returns:
        Expandierter Plain-Text-String.
    """
    if body_format != "blocknote":
        return body_text

    try:
        parsed: Any = json.loads(body_text)
    except json.JSONDecodeError:
        logger.error("render_template_body: Body ist kein gueltiges JSON — unveraendert zurueck")
        return body_text

    if isinstance(parsed, list):
        top_level_blocks: list[dict[str, Any]] = parsed
    elif isinstance(parsed, dict):
        nested = parsed.get("content", [])
        top_level_blocks = nested if isinstance(nested, list) else []
    else:
        logger.error(
            "render_template_body: Unbekannte JSON-Top-Level-Form %r — leerer Output",
            type(parsed).__name__,
        )
        return ""

    return await _walk_blocks(top_level_blocks, ctx, db)


async def _walk_blocks(
    top_level_blocks: list[dict[str, Any]],
    ctx: RenderContext,
    db: asyncpg.Connection,
) -> str:
    """Traversiert die Top-Level-Block-Liste und rendert sie zu Plain-Text.

    Jeder Block wird zu einem Absatz; Inline-Content innerhalb des Blocks wird
    konkateniert. Placeholder-Inline-Elemente werden ueber den REGISTRY-Dict
    expandiert. Unbekannte Placeholder-Kinds werden als lokalisierter Fehler-
    String eingefuegt; eine Exception wird nie geworfen.
    """
    parts: list[str] = []
    for block in top_level_blocks:
        block_text = await _render_block(block, ctx, db)
        if block_text:
            parts.append(block_text)
    return "\n\n".join(parts)


async def _render_block(
    block: dict[str, Any],
    ctx: RenderContext,
    db: asyncpg.Connection,
) -> str:
    """Rendert einen einzelnen Block (inkl. seiner Inline-Content-Liste) zu Text."""
    inline_parts: list[str] = []
    inline_content: list[dict[str, Any]] = block.get("content", [])
    for inline in inline_content:
        inline_text = await _render_inline(inline, ctx, db)
        inline_parts.append(inline_text)

    block_text = "".join(inline_parts).strip()

    # Kinder rekursiv prozessieren (z.B. verschachtelte Listeneintraege).
    child_parts: list[str] = []
    for child in block.get("children", []):
        child_text = await _render_block(child, ctx, db)
        if child_text:
            child_parts.append(child_text)

    all_parts: list[str] = []
    if block_text:
        all_parts.append(block_text)
    all_parts.extend(child_parts)
    return "\n".join(all_parts)


async def _render_inline(
    inline: dict[str, Any],
    ctx: RenderContext,
    db: asyncpg.Connection,
) -> str:
    """Rendert ein einzelnes Inline-Element zu Text.

    - `type='text'`: roher Text-String.
    - `type='placeholder'`: Resolver-Aufruf ueber REGISTRY.
    - Sonst: leerer String + Debug-Log.
    """
    inline_type: str = inline.get("type", "")

    if inline_type == "text":
        return str(inline.get("text", ""))

    if inline_type == "placeholder":
        props: dict[str, Any] = inline.get("props", {})
        kind: str = str(props.get("kind", ""))
        target_id: str = str(props.get("target_id", ""))

        resolver = REGISTRY.get(kind)
        if resolver is None:
            logger.warning(
                "_render_inline: unbekanntes Placeholder-Kind '%s' — Fehler-String eingesetzt",
                kind,
            )
            return f"<Unbekannter Placeholder: {kind}>"

        try:
            return await resolver.resolve(target_id, ctx, db)
        except Exception:
            logger.exception(
                "_render_inline: Resolver '%s' fuer target_id '%s' hat eine Exception geworfen",
                kind,
                target_id,
            )
            return f"<Fehler bei Placeholder: {kind}>"

    logger.debug("_render_inline: unbekannter Inline-Typ '%s' ignoriert", inline_type)
    return ""
