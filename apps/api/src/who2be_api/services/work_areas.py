"""Geschaeftslogik fuer WorkArea-Areas + Grants (ADR-0047, WP4).

Gate-Stack (Plan 2026-08-13):

- **Shared-Anlage** (Security-Review 2026-08-13 H1): IMMER zuerst
  `require_role(editor)` — die Rolle ist auch bei agent-gebundenen Tokens am
  Token gepinnt (ein viewer-Token legt nie Areas an) —; agent-gebundene
  Tokens brauchen ZUSAETZLICH die Capability `workarea_write` + Schreib-Rate
  (Muster `resource_service.create`).
- **Grant-Vergabe/-Entzug**: NUR Menschen (editor+). Ein Agent darf sich oder
  anderen Agenten niemals Zugriff verschaffen — sonst waere das Grant-Modell
  eine Selbstbedienung. Grants gibt es nur auf SHARED Areas: der Owner-Grant
  einer privaten Area ist systemverwaltet (Auto-Anlage) und die Privatheit
  gegenueber anderen Agenten waere sonst aufweichbar.
- **Grant-Liste**: ebenfalls nur Menschen, aber ab `viewer` — der Grant-Editor
  der Web-UI braucht den Ist-Stand, und eine reine Anzeige veraendert nichts.
  Agent-gebundene Tokens bleiben aussen vor: welche ANDEREN Agenten Zugriff
  auf eine Area haben, ist keine Information fuer einen Agenten.
- **Liste**: sichtbare Areas gemaess `core/workarea_scope.readable_area_ids`;
  fuer agent-gebundene Tokens wird vorher die private Area auto-angelegt
  (erster Zugriff zaehlt — Plan-Entscheidung 5).

ARC-3: kein SQL, keine HTTPException — Fehler als `ApiGateError` bzw. ueber
die 404-Helper aus `core/workarea_scope`.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_write_rate,
)
from who2be_api.core.workarea_scope import (
    agent_not_found,
    area_not_found,
    is_agent_bound,
    readable_area_ids,
)
from who2be_api.repositories.work_area_repository import WorkAreaRepository
from who2be_models import (
    AgentCapability,
    WorkAreaCreate,
    WorkAreaGrantRead,
    WorkAreaGrantSet,
    WorkAreaRead,
    WorkAreaScope,
    WorkspaceRole,
)

_GRANT_WRITE_HUMAN_ONLY = (
    "Die Grant-Verwaltung von Work-Areas ist Menschen vorbehalten — "
    "agent-gebundene Tokens koennen Area-Zugriffe nicht selbst vergeben."
)

_GRANT_READ_HUMAN_ONLY = (
    "Die Grant-Liste einer Work-Area ist Menschen vorbehalten — ein Agent "
    "erfaehrt nicht, welche anderen Agenten Zugriff auf die Area haben."
)


class WorkAreaService:
    """Area-Verwaltung: Anlage, Sichtbarkeit, Grants."""

    def __init__(self, repo: WorkAreaRepository, pool: asyncpg.Pool) -> None:
        self._repo = repo
        self._pool = pool

    def _require_write(self, ctx: WorkspaceContext) -> None:
        """Schreib-Gate (H1, Muster `resource_service.create`): IMMER zuerst
        `require_role(editor)` — die Rolle ist auch bei agent-gebundenen
        Tokens am Token gepinnt (ein viewer-Token schreibt nie) —, danach
        Capability + Rate (fuer Menschen/JWT No-Ops)."""
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.workarea_write)
        require_write_rate(ctx)

    def _require_human(self, ctx: WorkspaceContext, detail: str) -> None:
        """Weist agent-gebundene Tokens ab (Rolle bleibt Sache des Aufrufers).

        Beide Agent-Indikatoren pruefen (Defense-in-Depth, Muster
        `memory_service._require_human`): ein Agent hat auf den Grant-Routen
        nichts verloren — weder schreibend noch lesend (s. Modul-Kopf).
        """
        if is_agent_bound(ctx):
            raise ApiGateError(
                status=status.HTTP_403_FORBIDDEN,
                reason="missing_capability",
                actionable_by="human",
                detail=detail,
            )

    def _require_human_editor(self, ctx: WorkspaceContext) -> None:
        """Grant-Verwaltung ist Menschen vorbehalten (editor+).

        Ein Agent darf das Grant-Modell, das IHN beschraenkt, nie selbst
        veraendern.
        """
        self._require_human(ctx, _GRANT_WRITE_HUMAN_ONLY)
        require_role(ctx, WorkspaceRole.editor)

    async def create_shared(self, ctx: WorkspaceContext, data: WorkAreaCreate) -> WorkAreaRead:
        self._require_write(ctx)
        created = await self._repo.create_shared(ctx.workspace_id, data.name, data.retention_days)
        if created is None:
            # Partieller UNIQUE-Index (0073): Name im Workspace bereits vergeben.
            raise ApiGateError(
                status=status.HTTP_409_CONFLICT,
                reason="concurrent_conflict",
                actionable_by="agent",
                detail=(
                    f"Eine shared Area mit dem Namen '{data.name}' existiert bereits "
                    "in diesem Workspace."
                ),
            )
        return created

    async def list_visible(self, ctx: WorkspaceContext) -> list[WorkAreaRead]:
        """Sichtbare Areas; agent-gebundene Tokens loesen die private Auto-Anlage aus."""
        if is_agent_bound(ctx) and ctx.agent_id is not None:
            # Erster Zugriff zaehlt: get-or-create ist idempotent; ein
            # verschwundener Agent (Race mit Delete) liefert schlicht keine Area.
            await self._repo.get_or_create_private_area(ctx.workspace_id, ctx.agent_id)
        restrict = await readable_area_ids(self._pool, ctx)
        return await self._repo.list_areas(ctx.workspace_id, restrict)

    async def _require_shared_area(self, ctx: WorkspaceContext, area_id: UUID) -> WorkAreaRead:
        area = await self._repo.get(ctx.workspace_id, area_id)
        if area is None:
            raise area_not_found()
        if area.scope == WorkAreaScope.private:
            # Private Areas sind nicht grantbar (s. Modul-Kopf) — der Zustand
            # ist endgueltig, kein Mensch kann ihn freischalten.
            raise ApiGateError(
                status=status.HTTP_403_FORBIDDEN,
                reason="area_forbidden",
                actionable_by="none",
                detail=(
                    "Private Areas sind nicht grantbar — sie gehoeren genau einem "
                    "Agenten. Fuer Team-Zugriff eine shared Area anlegen."
                ),
            )
        return area

    async def set_grant(
        self, ctx: WorkspaceContext, area_id: UUID, agent_id: UUID, data: WorkAreaGrantSet
    ) -> WorkAreaGrantRead:
        self._require_human_editor(ctx)
        await self._require_shared_area(ctx, area_id)
        if not await self._repo.agent_exists(ctx.workspace_id, agent_id):
            raise agent_not_found()
        return await self._repo.set_grant(ctx.workspace_id, area_id, agent_id, data.level)

    async def list_grants(self, ctx: WorkspaceContext, area_id: UUID) -> list[WorkAreaGrantRead]:
        """Ist-Stand der Grants einer shared Area (Grant-Editor der Web-UI).

        Bewusst OHNE `require_role(editor)`: Lesen ist auch fuer `viewer` in
        Ordnung (die Anzeige veraendert nichts). Agent-gebundene Tokens
        bekommen 403 — s. Modul-Kopf. `_require_shared_area` liefert danach
        404 (unbekannte Area) bzw. 403 `area_forbidden` (private Area).
        """
        self._require_human(ctx, _GRANT_READ_HUMAN_ONLY)
        await self._require_shared_area(ctx, area_id)
        return await self._repo.list_grants(ctx.workspace_id, area_id)

    async def delete_grant(self, ctx: WorkspaceContext, area_id: UUID, agent_id: UUID) -> None:
        self._require_human_editor(ctx)
        await self._require_shared_area(ctx, area_id)
        if not await self._repo.delete_grant(ctx.workspace_id, area_id, agent_id):
            raise agent_not_found()
