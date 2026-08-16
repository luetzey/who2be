"""WorkArea-Artifact-Endpunkte (ADR-0047, WP4 — Spec A+E).

Pfade unter `/v1/workspaces/{ws_id}` (Prefix aus `main.py`):

- ``POST /work-areas/{area_id}/artifacts`` — doc-Artifact in einer Area.
- ``POST /artifacts`` — ohne Area = private Area des gebundenen Agenten
  (Auto-Anlage); Menschen-Tokens haben KEINE private Area → 422.
- ``POST /wa-artifacts/{id}/append`` — lockfreies Anhaengen (rev+1).
- ``PATCH /wa-artifacts/{id}`` — optimistisches Block-Edit (`expected_rev`).
- ``GET /wa-artifacts/{id}?anchor=`` — Markdown mit ``[#block_id]``-Ankern;
  `anchor` liefert nur den einen Block.
- ``GET /work-areas/{area_id}/artifacts`` — Metadaten-Liste.
- ``DELETE /wa-artifacts/{id}`` — 204 (Chunks via FK CASCADE).
- ``POST /wa-artifacts/{id}/promote`` — Artifact → Resource-DRAFT (Spec G,
  WP14); `?target_resource_id=` promotet in eine bestehende Resource.

Rate-Limit-Paritaet (Muster `resources.py`): Mutationen
`@limiter.limit(write_limit)` + `request` als erster Parameter; agent-Reads
`enforce_mcp_read_limit`. Autorisierung liegt im Service.
"""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from who2be_api.core.db import get_pool
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.resource_repository import PgResourceRepository
from who2be_api.repositories.status_history_repository import PgStatusHistoryRepository
from who2be_api.repositories.wa_artifact_repository import PgWaArtifactRepository
from who2be_api.repositories.work_area_repository import PgWorkAreaRepository
from who2be_api.repositories.workspace_repository import PgWorkspaceRepository
from who2be_api.services.entity_quota_service import enforce_entity_quota
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.resource_service import ResourceService
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_api.services.wa_artifacts import WaArtifactService
from who2be_api.services.wa_promote import PromoteUnsupportedArtifact, WaPromoteService
from who2be_models import (
    ArtifactAppend,
    ArtifactCreate,
    ArtifactMarkdown,
    ArtifactPatch,
    ArtifactRead,
    ResourceRead,
)

router = APIRouter(tags=["wa-artifacts"])


def get_wa_artifact_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WaArtifactService:
    return WaArtifactService(
        pool,
        PgWaArtifactRepository(),
        PgWorkAreaRepository(pool),
        workspace_repo=PgWorkspaceRepository(pool),
    )


def get_wa_promote_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WaPromoteService:
    """Verdrahtet den Promote-Service mit dem BESTEHENDEN Resource-Stack.

    `usage_repo` entfaellt bewusst — der Promote loescht nie (nur create/
    update_draft); die uebrigen Abhaengigkeiten spiegeln
    `resources.get_resource_service`.
    """
    return WaPromoteService(
        pool,
        PgWaArtifactRepository(),
        ResourceService(
            PgResourceRepository(pool),
            pool=pool,
            workspace_repo=PgWorkspaceRepository(pool),
        ),
        StatusHistoryService(PgStatusHistoryRepository()),
    )


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WaArtifactService, Depends(get_wa_artifact_service)]
PromoteService = Annotated[WaPromoteService, Depends(get_wa_promote_service)]
# Anker-Query (`?anchor=<block_id>`): liefert nur den adressierten Block.
Anchor = Annotated[str | None, Query(min_length=1, max_length=64)]


@router.post("/work-areas/{area_id}/artifacts", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_artifact(
    request: Request, area_id: UUID, data: ArtifactCreate, ctx: Ctx, service: Service
) -> ArtifactRead:
    """Legt ein doc-Artifact in der Area an; die Antwort traegt die
    serverseitig vergebenen `block_id`s (Anker fuer append/patch/read)."""
    return await service.create(ctx, area_id, data)


@router.post("/artifacts", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_artifact_in_private_area(
    request: Request, data: ArtifactCreate, ctx: Ctx, service: Service
) -> ArtifactRead:
    """Wie `create_artifact`, aber ohne Area: Ziel ist die private Area des
    gebundenen Agenten (Auto-Anlage beim ersten Zugriff)."""
    if ctx.tool_policy is None and ctx.agent_id is None:
        # Menschen (JWT/ungebundener Token) haben KEINE private Area — der
        # Aufruf ist semantisch unvollstaendig, kein Autorisierungsproblem.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Ohne area_id schreibt nur ein agent-gebundener Token (private "
                "Area). Menschen legen Artifacts ueber "
                "POST /work-areas/{area_id}/artifacts an."
            ),
        )
    return await service.create(ctx, None, data)


@router.post("/wa-artifacts/{artifact_id}/append")
@limiter.limit(write_limit)
async def append_artifact(
    request: Request, artifact_id: UUID, data: ArtifactAppend, ctx: Ctx, service: Service
) -> ArtifactRead:
    """Haengt Markdown als neue Bloecke an (lockfrei, ohne `expected_rev` —
    nebenlaeufige Appends kollidieren nie)."""
    return await service.append(ctx, artifact_id, data)


@router.patch("/wa-artifacts/{artifact_id}")
@limiter.limit(write_limit)
async def patch_artifact(
    request: Request, artifact_id: UUID, data: ArtifactPatch, ctx: Ctx, service: Service
) -> ArtifactRead:
    """Block-Edit am Anker (replace/insert_after/delete); veraltete
    `expected_rev` → 409 `rev_conflict` mit aktueller rev im detail."""
    return await service.patch(ctx, artifact_id, data)


@router.get("/wa-artifacts/{artifact_id}", dependencies=[Depends(enforce_mcp_read_limit)])
async def read_artifact(
    artifact_id: UUID, ctx: Ctx, service: Service, anchor: Anchor = None
) -> ArtifactMarkdown:
    """Markdown-Read mit ``[#block_id]``-Ankern; `?anchor=` nur der eine Block."""
    return await service.read(ctx, artifact_id, anchor)


@router.get("/work-areas/{area_id}/artifacts", dependencies=[Depends(enforce_mcp_read_limit)])
async def list_artifacts(area_id: UUID, ctx: Ctx, service: Service) -> list[ArtifactRead]:
    """Metadaten-Liste einer Area. NICHT der Einstieg fuer Agenten — die
    WorkArea-Suche (WP6) liefert Anker + Snippet statt ganzer Dokumente."""
    return await service.list_for_area(ctx, area_id)


@router.delete("/wa-artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(write_limit)
async def delete_artifact(request: Request, artifact_id: UUID, ctx: Ctx, service: Service) -> None:
    await service.delete(ctx, artifact_id)


@router.post(
    "/wa-artifacts/{artifact_id}/promote",
    status_code=status.HTTP_201_CREATED,
    # Promote ERZEUGT eine Resource — dasselbe Entity-Quota-Gate wie
    # `POST /resources` (Cloud-Edition; On-Prem No-op). Konservativ feuert es
    # auch auf dem `target_resource_id`-Pfad (dort entsteht nichts Neues).
    dependencies=[Depends(enforce_entity_quota)],
)
@limiter.limit(write_limit)
async def promote_artifact(
    request: Request,
    artifact_id: UUID,
    ctx: Ctx,
    promote_service: PromoteService,
    target_resource_id: Annotated[UUID | None, Query()] = None,
) -> ResourceRead:
    """Promotet ein doc-Artifact zu einer Resource-DRAFT — nie Active (Spec G).

    Ohne `target_resource_id` entsteht eine neue Resource (Draft v1) mit
    Herkunfts-Note (`status_history`) + Herkunftszeile in der Description;
    mit `target_resource_id` ersetzt der Draft-Pfad die Bloecke der
    bestehenden Resource (Review-Konflikt → 409). Nicht-doc-Artifacts → 422
    (Domain-Validation, Muster `wa_tables`).

    `target_resource_id` ist ein QUERY-Parameter — die Route nimmt bewusst
    KEINEN Body entgegen (der MCP-Client in `apps/mcp/.../clients/kb.py`
    ruft entsprechend body-los mit `params` auf). Ein Body-Feld daneben waere
    eine zweite, undokumentierte Eingabe fuer dieselbe Angabe.
    """
    try:
        return await promote_service.promote_artifact(ctx, artifact_id, target_resource_id)
    except PromoteUnsupportedArtifact as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
