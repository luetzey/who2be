"""Area-Referenzen aufloesen — die EINE Stelle fuer `area_id=None`.

Mehrere Tool-Familien nehmen eine optionale `area_id` und meinen mit
`None` „meine private Area" (`list_artifacts`, `list_tables`, …). Die
Aufloesung gehoert deshalb nicht in eine der Familien, sondern hierher:
zwei Kopien derselben Regel driften auseinander, und die Folge waere ein
Tool, das in eine andere Area schreibt oder liest als sein Nachbar.
"""

from __future__ import annotations

from uuid import UUID

from fastmcp.exceptions import ToolError

from who2be_mcp.client import ApiClient
from who2be_mcp.clients import workarea as wa_api
from who2be_models import WorkAreaScope


def parse_area_id(area_id: str | None) -> UUID | None:
    """`None` bleibt `None`; sonst UUID oder lesbarer `ToolError`."""
    if area_id is None:
        return None
    try:
        return UUID(area_id)
    except ValueError as exc:
        raise ToolError(f"Ungueltige Area-UUID: '{area_id}'.") from exc


async def resolve_private_area_id(client: ApiClient) -> UUID:
    """Loest `area_id=None` auf die private Area des Aufrufers auf.

    `GET .../work-areas` legt die private Area eines agent-gebundenen Tokens
    beim ersten Zugriff automatisch an (ADR-0047). Menschen/ungebundene
    Tokens haben keine (bzw. editor+ sieht mehrere fremde private Areas) —
    dann ist eine explizite `area_id` gefordert.
    """
    areas = await wa_api.list_work_areas(client)
    private = [area for area in areas if area.scope == WorkAreaScope.private]
    if len(private) == 1:
        return private[0].id
    if not private:
        raise ToolError(
            "Keine private Area aufloesbar — nur agent-gebundene Tokens haben eine. "
            "Gib `area_id` explizit an (sichtbare Areas: `whoami.work_areas`)."
        )
    raise ToolError("Mehrere private Areas sichtbar (Mensch/editor+) — gib `area_id` explizit an.")
