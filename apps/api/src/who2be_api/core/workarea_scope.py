"""Area-Scope-Aufloesung fuer die Agent-WorkArea (ADR-0047, User-Entscheidung 5).

Wer darf welche Areas sehen bzw. beschreiben? Die Antwort ist bewusst
MATERIALISIERT (`work_area_grant`, inkl. Owner-Grant der privaten Area), damit
die Filter-SQL der Read-Pfade uniform bleibt — keine Sonderfaelle fuer
„eigene private Area" zur Lesezeit.

Regeln (Plan 2026-08-13, bindend):

- **Mensch** (kein ``ctx.tool_policy``/``agent_id``): ab Rolle ``editor``
  unbeschraenkt (`None`) — AUCH private Agent-Areas. „Privat" heisst privat
  gegenueber anderen **Agenten**, nicht gegenueber den Menschen des
  Workspaces (Transparenz-Prinzip: der Betreiber sieht immer, was seine
  Agenten ablegen). ``viewer`` sieht nur shared Areas.
- **Agent** (agent-gebundener Token): genau die Areas aus `work_area_grant`;
  ``write``-Grants implizieren Lesbarkeit (read ⊆ write).

Fehlender Read-Zugriff wird als **404** beantwortet (kein Existenz-Orakel
ueber fremde private Areas — Muster `routers/_export.py`); nur der Fall
„lesbar, aber kein Write-Grant" ist ein 403 `area_forbidden` (der Agent WEISS
von der Area, ihm fehlt nur die Schreibstufe — actionable fuer den Menschen).

**Ungebundene Maschinen-Tokens** (Security-Review Phase 2, M1) sind auf
diesen Routen gesperrt (`require_agent_bound_token`, als Router-Dependency in
`main.py` verdrahtet). Grund: die beiden Regeln oben kennen nur zwei Faelle —
Mensch (unbeschraenkt ab editor) und Agent (Grant-gescoped). Ein `w2b_`-Token
OHNE `agent_id` faellt in den Menschen-Zweig und liest damit ALLE Areas
inklusive fremder privater — und weil `agent_access_log` an `agent_id`
haengt, wird davon NICHTS protokolliert. Das war ein unbeobachteter
Vollzugriff. Ihn zu loggen haette ein nullable `agent_id` im Compliance-Log
verlangt (die Auswertung „welches Modell sah was" braucht aber genau diesen
Bezug); die Sperre ist der kleinere, haertere Schnitt und deckt sich mit
ADR-0047, wo WorkArea/KB durchgehend agent-gebunden gedacht sind. Menschen
(JWT) sind nicht betroffen.
"""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

import asyncpg
from fastapi import Depends, HTTPException, status

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import WorkspaceContext, get_current_workspace, role_satisfies
from who2be_models import WorkAreaGrantLevel, WorkspaceRole

# `Pool | Connection`: Services reichen den Pool durch, Transaktions-Pfade eine
# bereits acquirte Connection — beide haben `.fetch`/`.fetchrow` (Muster
# `core/agent_scope.py`).
_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection

_SHARED_AREA_IDS_SQL = (
    "SELECT id FROM work_area WHERE workspace_id = $1 AND scope = 'shared' ORDER BY id"
)

_GRANTED_AREA_IDS_SQL = (
    "SELECT area_id FROM work_area_grant WHERE workspace_id = $1 AND agent_id = $2 ORDER BY area_id"
)

_GRANTED_WRITE_AREA_IDS_SQL = (
    "SELECT area_id FROM work_area_grant "
    "WHERE workspace_id = $1 AND agent_id = $2 AND level = 'write' ORDER BY area_id"
)

_AREA_EXISTS_SQL = "SELECT 1 FROM work_area WHERE id = $1 AND workspace_id = $2"


def area_not_found() -> HTTPException:
    """404 fuer unbekannte ODER nicht lesbare Areas (kein Existenz-Leak)."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area nicht gefunden.")


def artifact_not_found() -> HTTPException:
    """404 fuer unbekannte ODER nicht lesbare Artifacts (kein Existenz-Leak)."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact nicht gefunden.")


def agent_not_found() -> ApiError:
    """404 fuer unbekannte/workspace-fremde Agenten (Grant-Ziele)."""
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Agent nicht gefunden.",
        reason="agent_not_found",
    )


def is_agent_bound(ctx: WorkspaceContext) -> bool:
    """True, wenn der Aufruf ueber einen agent-gebundenen Token kommt.

    Beide Indikatoren pruefen (Defense-in-Depth, Muster
    `memory_service._require_human`): heute impliziert `agent_id` eine Policy,
    aber die Scope-Entscheidung soll nicht an dieser DB-Invariante haengen.
    """
    return ctx.tool_policy is not None or ctx.agent_id is not None


def require_agent_bound_token(
    ctx: Annotated[WorkspaceContext, Depends(get_current_workspace)],
) -> None:
    """Sperrt ungebundene Maschinen-Tokens auf WorkArea-/KB-/Tabellen-Routen (M1).

    Router-Dependency (Muster `enforce_mcp_read_limit`), in `main.py` an die
    betroffenen Router gehaengt — nicht an einzelne Endpunkte, damit auch
    kuenftige Routen dieser Router sie erben. JWT-Aufrufe (Menschen) und
    agent-gebundene Tokens passieren; nur `is_api_token` OHNE Agent-Bindung
    wird abgewiesen. Begruendung im Modul-Kopf.
    """
    if not ctx.is_api_token or is_agent_bound(ctx):
        return
    raise ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="missing_capability",
        actionable_by="human",
        detail=(
            "Diese Routen verlangen einen agent-gebundenen Token. Ein Token "
            "ohne `agent_id` hat weder Area-Grants noch einen Eintrag im "
            "Zugriffsprotokoll — der Workspace-Besitzer kann einen Token mit "
            "Agent-Bindung ausstellen."
        ),
    )


async def readable_area_ids(pool: _Fetcher, ctx: WorkspaceContext) -> list[UUID] | None:
    """Lesbare Area-IDs des Aufrufers; `None` = unbeschraenkt.

    Mensch mit editor+ liest ALLES (auch private Agent-Areas, s. Modul-Kopf);
    viewer nur shared. Agenten lesen genau ihre Grant-Areas — `write`-Grants
    zaehlen mit (read ⊆ write). Leere Liste = nichts sichtbar.
    """
    if not is_agent_bound(ctx):
        if role_satisfies(ctx.role, WorkspaceRole.editor):
            return None
        rows = await pool.fetch(_SHARED_AREA_IDS_SQL, ctx.workspace_id)
        return [row["id"] for row in rows]
    if ctx.agent_id is None:
        # Defensiv: Policy ohne Agent-Bindung — es gibt keine Grant-Basis.
        return []
    rows = await pool.fetch(_GRANTED_AREA_IDS_SQL, ctx.workspace_id, ctx.agent_id)
    return [row["area_id"] for row in rows]


async def writable_area_ids(pool: _Fetcher, ctx: WorkspaceContext) -> list[UUID] | None:
    """Beschreibbare Area-IDs des Aufrufers; `None` = unbeschraenkt.

    Mensch mit editor+ schreibt ueberall (das Rollen-Gate der Services hat
    viewer bereits abgewiesen — hier liefert viewer defensiv `[]`). Agenten
    schreiben nur in Areas mit explizitem `write`-Grant.
    """
    if not is_agent_bound(ctx):
        if role_satisfies(ctx.role, WorkspaceRole.editor):
            return None
        return []
    if ctx.agent_id is None:
        return []
    rows = await pool.fetch(_GRANTED_WRITE_AREA_IDS_SQL, ctx.workspace_id, ctx.agent_id)
    return [row["area_id"] for row in rows]


async def ensure_area_access(
    pool: _Fetcher, ctx: WorkspaceContext, area_id: UUID, level: WorkAreaGrantLevel
) -> None:
    """Erzwingt Zugriff der Stufe `level` auf `area_id` — oder wirft.

    Drei Stufen (Reihenfolge ist Absicht):

    1. Area existiert nicht im Workspace → 404.
    2. Area ist fuer den Aufrufer nicht LESBAR → ebenfalls 404 (eine fremde
       private Area ist von einer nicht existierenden nicht unterscheidbar —
       kein Existenz-Leak).
    3. Lesbar, aber `level='write'` ohne Write-Grant → 403 `area_forbidden`
       (der Aufrufer kennt die Area; der Workspace-Besitzer kann den
       Write-Grant vergeben).
    """
    exists = await pool.fetchval(_AREA_EXISTS_SQL, area_id, ctx.workspace_id)
    if exists is None:
        raise area_not_found()
    readable = await readable_area_ids(pool, ctx)
    if readable is not None and area_id not in readable:
        raise area_not_found()
    if level != WorkAreaGrantLevel.write:
        return
    writable = await writable_area_ids(pool, ctx)
    if writable is not None and area_id not in writable:
        raise ApiGateError(
            status=status.HTTP_403_FORBIDDEN,
            reason="area_forbidden",
            actionable_by="human",
            detail=(
                "Kein Schreibzugriff auf diese Area. Der Workspace-Besitzer kann "
                "dem Agenten einen write-Grant fuer die Area vergeben."
            ),
        )
