"""Extraktion von Inline-Pills aus einem BlockNote-Playbook-Body (Aufgabe B3).

Der Save-Sync-Pfad ("Body treibt") liest die im BlockNote-JSON eingebetteten
Placeholder-Pills aus und uebersetzt sie in:

* Composition-Refs (kind=='playbook') — die `target_id` ist eine Playbook-UUID.
* Resource-Block-Refs (kind=='resource') — die `target_id` ist eine
  Resource-UUID, optional mit `#<block_id>`-Suffix fuer Block-Scope.

Die Parser-Shape-Logik spiegelt `renderer.py` (Top-Level-Array ODER
`{"content": [...]}`-Wrapper). Iteriert wird in Dokumentreihenfolge ueber
Top-Level-Blocks, deren `content[]`-Inlines und rekursiv die `children`.

Robust gegen kaputtes JSON: bei einem Parse-Fehler oder unbekannter Top-Level-
Form liefert `extract_pills` leere Listen statt zu crashen.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from who2be_models import ResourceLinkItem

logger = logging.getLogger(__name__)


def extract_pills(body_text: str) -> tuple[list[UUID], list[ResourceLinkItem]]:
    """Sammelt Playbook- und Resource-Pills aus einem BlockNote-Body-String.

    Returns:
        Tuple ``(child_ids, resource_links)``:
        - ``child_ids``: deduplizierte Playbook-UUIDs in Dokumentreihenfolge
          (kind=='playbook'). Dedup ueber ``dict.fromkeys`` (Reihenfolge bleibt).
        - ``resource_links``: ``ResourceLinkItem`` je Resource-Pill mit
          fortlaufender ``position`` in Dokumentreihenfolge. Mit ``#<block_id>``
          → ``link_scope='block'``; ohne → ``link_scope='resource'``.

    Bei kaputtem JSON oder unbekannter Top-Level-Form: ``([], [])``.
    """
    try:
        parsed: Any = json.loads(body_text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("extract_pills: Body ist kein gueltiges JSON — keine Pills extrahiert")
        return [], []

    if isinstance(parsed, list):
        top_level_blocks: list[Any] = parsed
    elif isinstance(parsed, dict):
        nested = parsed.get("content", [])
        top_level_blocks = nested if isinstance(nested, list) else []
    else:
        logger.warning(
            "extract_pills: Unbekannte JSON-Top-Level-Form %r — keine Pills",
            type(parsed).__name__,
        )
        return [], []

    raw_playbook_ids: list[UUID] = []
    resource_links: list[ResourceLinkItem] = []
    # `position` ist der laufende Index der Resource-Pills in Dokumentreihenfolge.
    counter = _Counter()
    for block in top_level_blocks:
        _walk_block(block, raw_playbook_ids, resource_links, counter)

    # Dedup der Playbook-IDs reihenfolge-erhaltend.
    child_ids = list(dict.fromkeys(raw_playbook_ids))
    return child_ids, resource_links


class _Counter:
    """Mutierbarer Zaehler fuer die laufende Resource-Pill-Position."""

    def __init__(self) -> None:
        self.value = 0

    def next(self) -> int:
        current = self.value
        self.value += 1
        return current


def _walk_block(
    block: Any,
    playbook_ids: list[UUID],
    resource_links: list[ResourceLinkItem],
    counter: _Counter,
) -> None:
    """Verarbeitet einen Block: Inline-Content + rekursiv die Children."""
    if not isinstance(block, dict):
        return
    content = block.get("content", [])
    if isinstance(content, list):
        for inline in content:
            _handle_inline(inline, playbook_ids, resource_links, counter)
    for child in block.get("children", []):
        _walk_block(child, playbook_ids, resource_links, counter)


def _handle_inline(
    inline: Any,
    playbook_ids: list[UUID],
    resource_links: list[ResourceLinkItem],
    counter: _Counter,
) -> None:
    """Verarbeitet ein einzelnes Inline-Element; nur Placeholder-Pills zaehlen."""
    if not isinstance(inline, dict) or inline.get("type") != "placeholder":
        return
    props = inline.get("props", {})
    if not isinstance(props, dict):
        return
    kind = props.get("kind")
    target_id = props.get("target_id")
    if not isinstance(target_id, str) or not target_id:
        return

    if kind == "playbook":
        try:
            playbook_ids.append(UUID(target_id))
        except ValueError:
            logger.warning(
                "extract_pills: ungueltige Playbook-UUID '%s' — uebersprungen", target_id
            )
        return

    if kind == "resource":
        resource_id_str, _, block_id = target_id.partition("#")
        try:
            resource_id = UUID(resource_id_str)
        except ValueError:
            logger.warning(
                "extract_pills: ungueltige Resource-UUID '%s' — uebersprungen", resource_id_str
            )
            return
        position = counter.next()
        if block_id:
            resource_links.append(
                ResourceLinkItem(
                    resource_id=resource_id,
                    block_id=block_id,
                    position=position,
                    link_scope="block",
                )
            )
        else:
            resource_links.append(
                ResourceLinkItem(
                    resource_id=resource_id,
                    block_id=None,
                    position=position,
                    link_scope="resource",
                )
            )
