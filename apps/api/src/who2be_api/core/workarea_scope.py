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
"""

from __future__ import annotations

from typing import TypeAlias
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import WorkspaceContext, role_satisfies
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


def agent_not_found() -> HTTPException:
    """404 fuer unbekannte/workspace-fremde Agenten (Grant-Ziele)."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent nicht gefunden.")


def is_agent_bound(ctx: WorkspaceContext) -> bool:
    """True, wenn der Aufruf ueber einen agent-gebundenen Token kommt.

    Beide Indikatoren pruefen (Defense-in-Depth, Muster
    `memory_service._require_human`): heute impliziert `agent_id` eine Policy,
    aber die Scope-Entscheidung soll nicht an dieser DB-Invariante haengen.
    """
    return ctx.tool_policy is not None or ctx.agent_id is not None


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
