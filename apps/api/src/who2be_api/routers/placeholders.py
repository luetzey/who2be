"""REST-Endpunkte fuer Placeholder (`/v1/workspaces/{workspace_id}/placeholders`).

Read-only:
- `GET /placeholders` — statischer Kind-Katalog (WP-A): welches `kind` mit
  welchem `target_id`-Vertrag existiert, samt Beispiel-Inline. Macht das
  Placeholder-Format fuer MCP-Agenten (`list_placeholders`) zur Laufzeit
  entdeckbar.
- `GET /placeholders/preview` — loest den Output einer einzelnen Editor-Pill
  fuer das Klick-Overlay auf. Nutzt dieselben Resolver wie der Body-Renderer
  (REGISTRY).
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.services.placeholder_preview_service import (
    PlaceholderPreviewResponse,
    PlaceholderPreviewService,
)
from who2be_api.services.placeholders.kind_catalog import placeholder_catalog
from who2be_models import PlaceholderCatalog

router = APIRouter(prefix="/placeholders", tags=["placeholders"])


def get_placeholder_preview_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PlaceholderPreviewService:
    return PlaceholderPreviewService(pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[PlaceholderPreviewService, Depends(get_placeholder_preview_service)]


@router.get("")
async def list_placeholders(_ctx: Ctx) -> PlaceholderCatalog:
    """Statischer Katalog aller Placeholder-Kinds fuer Template-Bodies.

    Pro Kind: Beschreibung, `target_id`-Semantik (+ abschliessende Werteliste,
    wo es eine gibt) und ein gueltiges Beispiel-Inline-Element. Der Katalog ist
    workspace-unabhaengig und unsensibel — das Gate ist die normale
    Workspace-Mitgliedschaft bzw. der API-Token (auch agent-gebunden lesbar,
    wie die uebrigen Reads)."""
    return placeholder_catalog()


@router.get("/preview")
async def preview_placeholder(
    ctx: Ctx,
    service: Service,
    kind: Annotated[str, Query(max_length=50)],
    target_id: Annotated[str, Query(max_length=300)] = "",
    persona_id: Annotated[UUID | None, Query()] = None,
) -> PlaceholderPreviewResponse:
    """Loest eine einzelne Pill (`kind`+`target_id`) zu ihrem Output auf.

    `target_id` kann ein Resource-Section-Anker (`<uuid>#<block_id>`) sein.
    `persona_id` ist optional — fuer `persona-field`-Pills im Agenten-Kontext;
    in den Template-Editoren fehlt er, dann liefert der Resolver einen Miss.
    """
    return await service.preview(ctx, kind, target_id, persona_id)
