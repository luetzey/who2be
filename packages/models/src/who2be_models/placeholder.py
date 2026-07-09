"""Placeholder-Katalog-Models (WP-A, praezisiert ADR-0025/0040).

Vertrag fuer `GET /v1/workspaces/{ws_id}/placeholders` und das MCP-Tool
`list_placeholders`: ein statischer, zur Laufzeit entdeckbarer Katalog der
Placeholder-Kinds, die in System-Prompt-Template-Bodies (BlockNote-Inline-
Elemente `{"type": "placeholder", "props": {...}}`) verwendet werden koennen.
Die Daten kommen aus der Resolver-Registry der API (`services/placeholders`);
dieses Modul definiert nur die Form.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PlaceholderInlineProps(BaseModel):
    """`props` eines Placeholder-Inline-Elements im BlockNote-Body."""

    kind: str
    target_id: str
    # Sichtbares Label der Pill im Editor, z. B. "Playbook: Reset-Mail".
    label: str


class PlaceholderInlineExample(BaseModel):
    """Ein vollstaendiges Placeholder-Inline-Element, wie es im stringifizierten
    BlockNote-Body eines Templates steht (innerhalb `content` eines Blocks)."""

    type: Literal["placeholder"] = "placeholder"
    props: PlaceholderInlineProps


class PlaceholderKindInfo(BaseModel):
    """Ein Placeholder-Kind des Katalogs mit `target_id`-Vertrag und Beispiel."""

    kind: str
    # Was der Placeholder beim Agent-Rendern expandiert.
    description: str
    # Semantik des `target_id`-Felds (Freitext, z. B. "UUID eines Playbooks").
    target_id_semantics: str
    # Abschliessende Aufzaehlung erlaubter Werte; leer = freie Werte gemaess
    # `target_id_semantics` (z. B. UUIDs oder Tag-Namen).
    target_id_values: list[str] = Field(default_factory=list)
    example: PlaceholderInlineExample


class PlaceholderCatalog(BaseModel):
    """Antwort von `GET /v1/workspaces/{ws_id}/placeholders`."""

    kinds: list[PlaceholderKindInfo]
