"""Kanonische Klartext-/Markdown-Serialisierung von Versions-Contents (WP-C).

Liefert `before_text`/`after_text` fuer die git-artige Diff-Ansicht der
Versions-Endpunkte: pro Entity-Typ eine deterministische Serialisierung des
Content-JSON zu lesbarem Text. Die Blocks→Text-Logik ist Single-Source in
`placeholders._core` (`block_plain_text`/`blocks_plain_text`); dieser Modul
setzt sie fuer die vier Content-Formen zusammen und rendert Placeholder-Pills
als stabile `{{kind:target_id}}`-Tokens — ohne DB-Zugriff, damit derselbe
Inhalt immer denselben Text ergibt (kein Aufloesen wie im Compose-Render).

Struktur/Reihenfolge folgt dem Compose-Render der Placeholder-Resolver
(Persona: `render_persona_profile`; Playbook/Resource/System-Prompt:
description + Body/Blocks).
"""

from __future__ import annotations

import json
from typing import Any

from who2be_api.services.placeholders._core import blocks_plain_text
from who2be_api.services.placeholders.resolvers.persona import render_persona_profile


def _inline_with_pills(inline: dict[str, object]) -> str:
    """Inline-Renderer fuer die Diff-Serialisierung.

    `type='text'` liefert den Roh-Text; Placeholder-Pills werden als stabiles
    Token `{{kind:target_id}}` gerendert (nicht aufgeloest — kein DB-Zugriff,
    deterministisch). Unbekannte Inline-Typen verschwinden wie im Default.
    """
    inline_type = inline.get("type")
    if inline_type == "text":
        return str(inline.get("text", ""))
    if inline_type == "placeholder":
        raw_props = inline.get("props")
        props: dict[str, object] = raw_props if isinstance(raw_props, dict) else {}
        kind = str(props.get("kind", ""))
        target_id = str(props.get("target_id", ""))
        return f"{{{{{kind}:{target_id}}}}}"
    return ""


def blocknote_body_text(body: str) -> str:
    """Serialisiert einen stringifizierten BlockNote-Body zu Klartext.

    Akzeptiert die beiden BlockNote-JSON-Shapes (Top-Level-Array bzw.
    `{"content": [...]}`-Wrapper, analog `render_template_body`). Kein
    gueltiges JSON (Alt-Bestand/Plain-Text) → Rohwert getrimmt zurueck.
    """
    stripped = body.strip()
    if not stripped:
        return ""
    try:
        parsed: Any = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped
    if isinstance(parsed, list):
        blocks: list[Any] = parsed
    elif isinstance(parsed, dict):
        nested = parsed.get("content", [])
        blocks = nested if isinstance(nested, list) else []
    else:
        # Skalar-JSON (Zahl/String) — als Rohtext behandeln.
        return stripped
    return blocks_plain_text(blocks, _inline_with_pills)


def _join(parts: list[str]) -> str:
    return "\n\n".join(part for part in parts if part).strip()


def persona_content_text(content: dict[str, Any]) -> str:
    """Persona-Version → Text: identisch zum Compose-Profil-Render.

    Single-Source: `render_persona_profile` (description + Profil-Blocks +
    Traits + Modi-Sektion, gleiche Reihenfolge wie `persona-field:profile`).
    """
    return render_persona_profile(content)


def playbook_content_text(content: dict[str, Any]) -> str:
    """Playbook-Version → Text: description + Body (stringifiziertes BlockNote-JSON)."""
    description = str(content.get("description", "")).strip()
    body = blocknote_body_text(str(content.get("body", "")))
    return _join([description, body])


def resource_content_text(content: dict[str, Any]) -> str:
    """Resource-Version → Text: description + Block-Liste."""
    description = str(content.get("description", "")).strip()
    body = blocks_plain_text(content.get("blocks", []), _inline_with_pills)
    return _join([description, body])


def system_prompt_content_text(content: dict[str, Any]) -> str:
    """System-Prompt-Template-Version → Text: description + Body (BlockNote-JSON)."""
    description = str(content.get("description", "")).strip()
    body = blocknote_body_text(str(content.get("body", "")))
    return _join([description, body])


__all__ = [
    "blocknote_body_text",
    "persona_content_text",
    "playbook_content_text",
    "resource_content_text",
    "system_prompt_content_text",
]
