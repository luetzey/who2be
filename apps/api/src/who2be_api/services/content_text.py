"""Kanonische Klartext-/Markdown-Serialisierung von Versions-Contents (WP-C).

Liefert `before_text`/`after_text` fuer die git-artige Diff-Ansicht der
Versions-Endpunkte: pro Entity-Typ eine deterministische Serialisierung des
Content-JSON zu lesbarem Text. Die Blocks→Text-Logik ist Single-Source in
`who2be_models.blocknote_text` (ADR-0056; auch der MCP nutzt sie); dieses
Modul setzt sie fuer die vier Content-Formen zusammen und rendert
Placeholder-Pills als stabile `{{kind:target_id}}`-Tokens — ohne DB-Zugriff,
damit derselbe Inhalt immer denselben Text ergibt (kein Aufloesen wie im
Compose-Render).

Struktur/Reihenfolge folgt dem Compose-Render der Placeholder-Resolver
(Persona: `render_persona_profile`; Playbook/Resource/System-Prompt:
description + Body/Blocks).
"""

from __future__ import annotations

from typing import Any

from who2be_api.services.placeholders.resolvers.persona import render_persona_profile
from who2be_models.blocknote_text import blocknote_body_text as blocknote_body_text
from who2be_models.blocknote_text import blocks_plain_text, placeholder_token_inline
from who2be_models.blocknote_text import parse_blocknote_blocks as parse_blocknote_blocks


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
    body = blocks_plain_text(content.get("blocks", []), placeholder_token_inline)
    return _join([description, body])


def system_prompt_content_text(content: dict[str, Any]) -> str:
    """System-Prompt-Template-Version → Text: description + Body (BlockNote-JSON)."""
    description = str(content.get("description", "")).strip()
    body = blocknote_body_text(str(content.get("body", "")))
    return _join([description, body])


__all__ = [
    "blocknote_body_text",
    "parse_blocknote_blocks",
    "persona_content_text",
    "playbook_content_text",
    "resource_content_text",
    "system_prompt_content_text",
]
