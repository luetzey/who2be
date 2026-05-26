"""REST-Endpunkte fuer API-Token (`/v1/tokens`)."""

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request, Response, status

from who2be_api.core.db import get_pool
from who2be_api.core.pagination import DEFAULT_LIMIT, PageCursor, PageLimit
from who2be_api.core.rate_limit import limiter, write_limit
from who2be_api.core.security import get_current_user
from who2be_api.repositories.token_repository import PgTokenRepository
from who2be_api.services.token_service import TokenService
from who2be_models import TokenCreate, TokenCreated, TokenRead

router = APIRouter(prefix="/v1/tokens", tags=["tokens"])


def get_token_service(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> TokenService:
    """FastAPI-Dependency: verdrahtet den Service mit der Pg-Implementierung."""
    return TokenService(PgTokenRepository(pool))


OwnerId = Annotated[UUID, Depends(get_current_user)]
Service = Annotated[TokenService, Depends(get_token_service)]


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(write_limit)
async def create_token(
    request: Request, data: TokenCreate, owner_id: OwnerId, service: Service
) -> TokenCreated:
    return await service.create(owner_id, data)


@router.get("")
async def list_tokens(
    owner_id: OwnerId,
    service: Service,
    response: Response,
    cursor: PageCursor,
    limit: PageLimit = DEFAULT_LIMIT,
) -> list[TokenRead]:
    items, next_cursor = await service.list_all(owner_id, limit, cursor)
    if next_cursor is not None:
        response.headers["X-Next-Cursor"] = next_cursor
    return items


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(token_id: UUID, owner_id: OwnerId, service: Service) -> None:
    await service.revoke(owner_id, token_id)
