"""REST-Endpunkt fuer Placeholder-Preview (`/v1/workspaces/{workspace_id}/placeholders`).

Read-only: liefert den aufgeloesten Output einer einzelnen Editor-Pill fuer das
Klick-Overlay. Nutzt dieselben Resolver wie der Body-Renderer (REGISTRY).
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

router = APIRouter(prefix="/placeholders", tags=["placeholders"])


def get_placeholder_preview_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> PlaceholderPreviewService:
    return PlaceholderPreviewService(pool)


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[PlaceholderPreviewService, Depends(get_placeholder_preview_service)]


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
