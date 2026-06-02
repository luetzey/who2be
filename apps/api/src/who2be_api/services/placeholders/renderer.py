"""Placeholder-Renderer fuer BlockNote-System-Prompt-Templates.

Traversiert BlockNote-JSON, sammelt alle Inline-Elemente vom Typ
`placeholder`, ruft den passenden Resolver aus dem REGISTRY-Dict auf und
gibt den expandierten Plain-Text-String plus eine Liste der nicht aufgeloesten
Placeholder-Keys zurueck.

Saubere Trennung: _walk_blocks kummert sich ums Walking, REGISTRY ums Resolving.

Nicht-gefundene Resolver -> lokalisierter Fehler-String, kein Exception.
Der Renderer laeuft robust durch.

Welle 6: `render_template_body` gibt `tuple[str, list[str]]` zurueck.
  - Index 0: gerenderter Plain-Text
  - Index 1: deduplizierte, lexikografisch sortierte Liste der Miss-Keys
    (z.B. ``["persona-field:name", "playbook:abc-uuid"]``).
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
    ctx: RenderContext,
    db: asyncpg.Connection,
) -> tuple[str, list[str]]:
    """Expandiert Placeholders im BlockNote-Template-Body (Track B: Nur-BlockNote).

    `body_text` ist immer ein stringifiziertes BlockNote-JSON-Dokument. Leere
    oder ungueltige Bodies (z. B. frische Drafts) liefern den Rohwert + leere
    unresolved-Liste — kein Fehler.

    Akzeptiert zwei BlockNote-JSON-Shapes:
    - Top-Level-Array `[{...block...}, ...]` (was `editor.document` liefert
      und was Frontend in `body` schreibt) — der Default.
    - Wrapper-Objekt `{"content": [{...block...}, ...]}` (was BlockNote bei
      anderen Export-Pfaden produziert und was die Unit-Tests bisher
      benutzten).

    Args:
        body_text: Der rohe BlockNote-Body-String aus der Datenbank.
        ctx:       Render-Kontext (workspace_id, persona_id, jetzt).
        db:        asyncpg-Connection fuer DB-Lookups der Resolver.

    Returns:
        Tuple (expanded_text, unresolved_keys) — unresolved_keys ist
        dedupliziert und lexikografisch sortiert.
    """
    try:
        parsed: Any = json.loads(body_text)
    except json.JSONDecodeError:
        logger.error("render_template_body: Body ist kein gueltiges JSON — unveraendert zurueck")
        return body_text, []

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
        return "", []

    unresolved: list[str] = []
    text = await _walk_blocks(top_level_blocks, ctx, db, unresolved)
    # Deduplizieren + lexikografisch sortieren fuer deterministischen Output.
    seen: set[str] = set()
    deduped: list[str] = []
    for key in sorted(unresolved):
        if key not in seen:
            seen.add(key)
            deduped.append(key)
    return text, deduped


async def _walk_blocks(
    top_level_blocks: list[dict[str, Any]],
    ctx: RenderContext,
    db: asyncpg.Connection,
    unresolved: list[str],
) -> str:
    """Traversiert die Top-Level-Block-Liste und rendert sie zu Plain-Text.

    Jeder Block wird zu einem Absatz; Inline-Content innerhalb des Blocks wird
    konkateniert. Placeholder-Inline-Elemente werden ueber den REGISTRY-Dict
    expandiert. Unbekannte Placeholder-Kinds werden als lokalisierter Fehler-
    String eingefuegt; eine Exception wird nie geworfen.

    Miss-Keys werden in `unresolved` (Akkumulator) gesammelt.
    """
    parts: list[str] = []
    for block in top_level_blocks:
        block_text = await _render_block(block, ctx, db, unresolved)
        if block_text:
            parts.append(block_text)
    return "\n\n".join(parts)


async def _render_block(
    block: dict[str, Any],
    ctx: RenderContext,
    db: asyncpg.Connection,
    unresolved: list[str],
) -> str:
    """Rendert einen einzelnen Block (inkl. seiner Inline-Content-Liste) zu Text."""
    inline_parts: list[str] = []
    inline_content: list[dict[str, Any]] = block.get("content", [])
    for inline in inline_content:
        inline_text = await _render_inline(inline, ctx, db, unresolved)
        inline_parts.append(inline_text)

    block_text = "".join(inline_parts).strip()

    # Kinder rekursiv prozessieren (z.B. verschachtelte Listeneintraege).
    child_parts: list[str] = []
    for child in block.get("children", []):
        child_text = await _render_block(child, ctx, db, unresolved)
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
    unresolved: list[str],
) -> str:
    """Rendert ein einzelnes Inline-Element zu Text.

    - `type='text'`: roher Text-String.
    - `type='placeholder'`: Resolver-Aufruf ueber REGISTRY.
    - Sonst: leerer String + Debug-Log.

    Miss-Keys (aus `ResolveResult.unresolved_key`) werden in `unresolved`
    akkumuliert.
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
            result = await resolver.resolve(target_id, ctx, db)
        except Exception:
            logger.exception(
                "_render_inline: Resolver '%s' fuer target_id '%s' hat eine Exception geworfen",
                kind,
                target_id,
            )
            return f"<Fehler bei Placeholder: {kind}>"

        if result.unresolved_key is not None:
            unresolved.append(result.unresolved_key)
        return result.text

    logger.debug("_render_inline: unbekannter Inline-Typ '%s' ignoriert", inline_type)
    return ""
