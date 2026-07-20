"""Gemeinsamer Einzel-Export-Dispatch fuer Persona/Playbook/Resource (ADR-0032).

Konsolidiert die vorher 3x copy-gepastete Format-/404-/Content-Disposition-
Logik der Export-Endpoints (COD-4, Standards-Review 2026-07-08) und ersetzt
deren `-> Any`-Rueckgabetypen durch den expliziten Union-Typ (COD-5):
`Response` fuer den Markdown-Download, das JSON-Bundle (Identitaet + alle
Versionen, `EntityExportService.export_json`) sonst.

Der Playbook-/Resource-Sonderfall (agent-gebundene Tokens sehen nur die ihnen
zugewiesenen Aggregate) kommt als vorberechneter `scope` herein — `None` heisst
"keine Einschraenkung" (Mensch/ungebundener Token bzw. Persona ohne Scoping).
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, Response, status

from who2be_api.core.entity_sql import EntityKind
from who2be_api.services.entity_export_service import EntityExportService

# Expliziter Rueckgabetyp der Export-Endpoints: Markdown-Download ODER das
# JSON-Bundle. FastAPI erkennt `Response` in der Union und liefert das dict
# als JSON-Body mit dem gesetzten Content-Disposition-Header aus.
ExportResult = Response | dict[str, Any]

# Anzeige-Name je Entity fuer die 404-Detail-Meldung (deutsch, wie bisher).
_LABELS: dict[EntityKind, str] = {
    "persona": "Persona",
    "playbook": "Playbook",
    "resource": "Resource",
    "external_tool": "Externes Tool",
}


async def export_entity(
    export_service: EntityExportService,
    workspace_id: UUID,
    entity: EntityKind,
    entity_id: UUID,
    format: Literal["json", "markdown"],
    response: Response,
    *,
    scope: set[UUID] | None = None,
) -> ExportResult:
    """Fuehrt den Einzel-Export aus: Scope-Check, Format-Dispatch, 404, Header.

    `scope` ist die Menge der fuer den Aufrufer sichtbaren IDs
    (`visible_playbook_ids`/`visible_resource_ids`); liegt `entity_id` nicht
    darin, antwortet der Export mit 404 (kein Existenz-Leak).
    """
    not_found = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{_LABELS[entity]} nicht gefunden.",
    )
    if scope is not None and entity_id not in scope:
        raise not_found
    if format == "markdown":
        rendered = await export_service.export_markdown(workspace_id, entity, entity_id)
        if rendered is None:
            raise not_found
        return Response(
            content=rendered,
            media_type="text/markdown",
            headers={
                "Content-Disposition": (f'attachment; filename="who2be-{entity}-{entity_id}.md"')
            },
        )
    bundle = await export_service.export_json(workspace_id, entity, entity_id)
    if bundle is None:
        raise not_found
    response.headers["Content-Disposition"] = (
        f'attachment; filename="who2be-{entity}-{entity_id}.json"'
    )
    return bundle
