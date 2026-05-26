"""FastAPI-Dependencies fuer Keyset-Pagination.

Bewusst klein: ein `Query`-Validator fuer `limit` und ein `Depends` fuer
`cursor`, der den `(created_at, id)`-Tupel liefert oder 422 wirft.
Konstanten und Codec liegen in `who2be_models.pagination`, damit MCP-/
sonstige Konsumenten denselben Vertrag haben.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status

from who2be_models import DEFAULT_LIMIT, MAX_LIMIT, decode_cursor

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "PageCursor",
    "PageLimit",
    "parse_cursor",
]


def parse_cursor(
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> tuple[datetime, UUID] | None:
    """Decodiert den `?cursor`-Query-Parameter oder wirft 422."""
    if cursor is None:
        return None
    decoded = decode_cursor(cursor)
    if decoded is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Ungueltiger Cursor.",
        )
    return decoded


PageLimit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
PageCursor = Annotated[tuple[datetime, UUID] | None, Depends(parse_cursor)]
