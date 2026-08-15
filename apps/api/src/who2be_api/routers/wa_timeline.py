"""Timeline-Endpunkt (Spec N, ADR-0047/0049 — WP15).

Pfad unter `/v1/workspaces/{ws_id}` (Prefix aus `main.py`):

- ``GET /timeline?from_=&to=&sources=&granularity=`` — Zeitscheiben ueber
  Artifacts, KB-Nodes und Tabellen-Zeilen + separater unknown-Bucket.

Query-Parameter:

- ``from_``/``to`` (Pflicht, datetime): halboffenes Fenster ``[from_, to)``;
  ``to`` muss NACH ``from_`` liegen, das Fenster ist auf 366 Tage begrenzt
  (beides → 422, DoS-Schutz F-01-Linie). Naive Zeitstempel gelten als UTC.
- ``granularity``: ``day`` | ``week`` | ``month`` (Default ``day``).
- ``sources``: optional, CSV ODER Mehrfach-Parameter — ``artifacts``,
  ``nodes``, ``table:<table_id>``; Default ``artifacts`` + ``nodes``;
  unbekannte Tokens → 422.

Reiner Read-Pfad (`enforce_mcp_read_limit`, Muster `wa_tables.query`);
Autorisierung liegt im Service (Scope-Filter in der Repo-SQL; explizite
`table:<id>`-Quellen ohne read-Grant → 403 `area_forbidden`). Der Router
uebersetzt nur `TimelineTableNotFound` → 404.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Final
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.repositories.timeline_repository import PgTimelineRepository
from who2be_api.services.mcp_limit_service import enforce_mcp_read_limit
from who2be_api.services.tablestore_provider import get_table_store
from who2be_api.services.wa_timeline import TimelineTableNotFound, WaTimelineService
from who2be_models import TimelineGranularity, TimelineResult

router = APIRouter(tags=["wa-timeline"])

# Fenster-Obergrenze (Plan WP15): ein Jahr inkl. Schaltjahr.
TIMELINE_MAX_WINDOW_DAYS: Final = 366

_SOURCE_ARTIFACTS: Final = "artifacts"
_SOURCE_NODES: Final = "nodes"
_TABLE_SOURCE_PREFIX: Final = "table:"


def get_wa_timeline_service(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> WaTimelineService:
    return WaTimelineService(pool, PgTimelineRepository(), get_table_store())


Ctx = Annotated[WorkspaceContext, Depends(get_current_workspace)]
Service = Annotated[WaTimelineService, Depends(get_wa_timeline_service)]


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def _ensure_utc(value: datetime) -> datetime:
    """Naive Zeitstempel gelten als UTC (timestamptz-Vergleich braucht tz)."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _parse_sources(raw: list[str] | None) -> tuple[bool, bool, list[UUID]]:
    """``sources`` (CSV/Mehrfach) → (artifacts?, nodes?, Tabellen-IDs).

    Keine Angabe (oder nur Leerstrings) = Default ``artifacts`` + ``nodes``;
    Tabellen-IDs werden dedupliziert (Reihenfolge bleibt stabil).
    """
    if raw is None:
        return True, True, []
    tokens = [token.strip() for entry in raw for token in entry.split(",")]
    tokens = [token for token in tokens if token]
    if not tokens:
        return True, True, []
    include_artifacts = False
    include_nodes = False
    table_ids: list[UUID] = []
    seen: set[UUID] = set()
    for token in tokens:
        if token == _SOURCE_ARTIFACTS:
            include_artifacts = True
        elif token == _SOURCE_NODES:
            include_nodes = True
        elif token.startswith(_TABLE_SOURCE_PREFIX):
            try:
                table_id = UUID(token[len(_TABLE_SOURCE_PREFIX) :])
            except ValueError as exc:
                raise _invalid(
                    f"Ungueltige Timeline-Quelle '{token}': hinter 'table:' muss "
                    "eine Tabellen-UUID stehen."
                ) from exc
            if table_id not in seen:
                seen.add(table_id)
                table_ids.append(table_id)
        else:
            raise _invalid(
                f"Unbekannte Timeline-Quelle '{token}' — erlaubt: 'artifacts', "
                "'nodes', 'table:<table_id>'."
            )
    return include_artifacts, include_nodes, table_ids


@router.get("/timeline", dependencies=[Depends(enforce_mcp_read_limit)])
async def timeline(
    ctx: Ctx,
    service: Service,
    from_: Annotated[datetime, Query(description="Fensterbeginn (inklusiv).")],
    to: Annotated[datetime, Query(description="Fensterende (exklusiv), muss nach from_ liegen.")],
    granularity: Annotated[
        TimelineGranularity, Query(description="Bucket-Granularitaet.")
    ] = TimelineGranularity.day,
    sources: Annotated[
        list[str] | None,
        Query(description="Quellen: artifacts | nodes | table:<id> (CSV oder mehrfach)."),
    ] = None,
) -> TimelineResult:
    """Zeitscheiben ueber alle angeforderten Quellen + unknown-Bucket (Spec N);
    Buckets sind die Vereinigung der Quellen, gebuckelt wird IMMER ueber
    `occurred_at` — nie ueber das Erfassungsdatum."""
    window_start = _ensure_utc(from_)
    window_end = _ensure_utc(to)
    if window_end <= window_start:
        raise _invalid("`to` muss nach `from_` liegen.")
    if window_end - window_start > timedelta(days=TIMELINE_MAX_WINDOW_DAYS):
        raise _invalid(f"Das Zeitfenster ist auf {TIMELINE_MAX_WINDOW_DAYS} Tage begrenzt.")
    include_artifacts, include_nodes, table_ids = _parse_sources(sources)
    try:
        return await service.timeline(
            ctx,
            window_start=window_start,
            window_end=window_end,
            granularity=granularity,
            include_artifacts=include_artifacts,
            include_nodes=include_nodes,
            table_ids=table_ids,
        )
    except TimelineTableNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tabelle nicht gefunden."
        ) from exc
