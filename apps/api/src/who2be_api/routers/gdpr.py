"""GDPR-Router (`/v1/gdpr`) — Datenexport des aktuellen Users (Track O).

`GET /v1/gdpr/export` liefert das vollstaendige, maschinenlesbare Daten-Buendel
(DSGVO Art. 20). Rate-limitiert wie ein Schreibpfad (`write_limit`), weil der
Export ueber alle Workspaces des Users laeuft und entsprechend teuer ist.
"""

from typing import Annotated, Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, Response

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import get_current_user
from who2be_api.services.gdpr_export_service import GdprExportService

router = APIRouter(prefix="/v1/gdpr", tags=["gdpr"])


def get_export_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> GdprExportService:
    return GdprExportService(pool)


UserId = Annotated[UUID, Depends(get_current_user)]
Service = Annotated[GdprExportService, Depends(get_export_service)]


@router.get("/export")
@limiter.limit(write_limit)
async def export_my_data(
    request: Request, response: Response, user_id: UserId, service: Service
) -> dict[str, Any]:
    """Exportiert alle Daten des Users als JSON-Buendel (Download-Header gesetzt)."""
    response.headers["Content-Disposition"] = f'attachment; filename="who2be-export-{user_id}.json"'
    return await service.export(user_id)
