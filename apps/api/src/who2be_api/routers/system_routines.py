"""Betreiber-Sicht auf die Hintergrund-Routinen: `GET /v1/system/routines`.

ADR-0057 §7 mit Nachtrag 2026-10-10, Paket P4c. Die Route ist
workspace-uebergreifend und deshalb nur fuer Betreiber der Instanz sichtbar
(W2 = a). Kunden-Admins sehen weder Routinen noch Laufprotokoll.

Zwei Pruefungen, in dieser Reihenfolge:

1. `require_operator` (`core/operators.py`): Mensch und in `WHO2BE_OPERATORS`
   gelistet. Leere Liste, API-Token oder nicht gelisteter User ⇒ 403 mit dem
   Text des Kern-Gates. Das Web blendet den Abschnitt bei 403 aus (PM-W7).
2. `require_aal2` (`core/security.py`): Betreiberdaten nur mit MFA-Session,
   gleiche Linie wie der Billing-Override. Das Gate erwartet einen
   `WorkspaceContext`; die Route hat keinen Workspace, deshalb baut
   `_operator_context` einen Kontext ohne Workspace (Null-UUID, kleinste
   Rolle). `require_aal2` liest daraus nur `is_api_token`, `aal` und fuer das
   On-Prem-Warn-Event die IDs. Die Editions-Logik (Cloud fail-closed, On-Prem
   fail-open bis `WHO2BE_REQUIRE_MFA_ONPREM`) gilt damit unveraendert und
   wird nicht kopiert.

Die Betreiber-Pruefung laeuft zuerst: ein Nicht-Betreiber bekommt immer
dieselbe 403, gleich ob er MFA hat.

Ein ungueltiger `WHO2BE_ROUTINE_*`- oder `WHO2BE_WORKER_ENABLED`-Override
wirft im Service `ScheduleError`. Die Route uebersetzt das in eine 503 statt
in einen 500: die Uebersicht ist nicht verfuegbar, bis die Konfiguration
stimmt, und `detail` nennt die betroffene Variable. Die Antwort geht nur an
Betreiber, die die Variable ohnehin setzen. Antwortform wie beim Kern-Gate
(`HTTPException` mit `detail`): einen `reason` vergibt nach ADR-0051 §4 die
Domaene, nicht der Router.
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from who2be_api.core.db import get_pool
from who2be_api.core.operators import require_operator
from who2be_api.core.security import CurrentPrincipal, WorkspaceContext, require_aal2
from who2be_api.services.routine_overview_service import routines_overview
from who2be_api.worker.schedule import ScheduleError
from who2be_models import RoutinesOverview, WorkspaceRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/system", tags=["system"])

#: Platzhalter fuer `WorkspaceContext.workspace_id`: die Route hat keinen Workspace.
_NO_WORKSPACE = UUID(int=0)

Operator = Annotated[CurrentPrincipal, Depends(require_operator)]
DbPool = Annotated[asyncpg.Pool, Depends(get_pool)]


def _operator_context(principal: CurrentPrincipal) -> WorkspaceContext:
    """Kontext fuer `require_aal2` aus einem bereits geprueften Betreiber-Principal."""
    return WorkspaceContext(
        workspace_id=_NO_WORKSPACE,
        user_id=principal.user_id,
        role=WorkspaceRole.viewer,
        is_api_token=False,
        aal=principal.aal,
    )


@router.get("/routines")
async def get_routines(principal: Operator, pool: DbPool) -> RoutinesOverview:
    """Alle registrierten Routinen mit Zeitplan und Laufstand (nur Betreiber, MFA)."""
    require_aal2(_operator_context(principal))
    try:
        async with pool.acquire() as conn:
            return await routines_overview(conn)
    except ScheduleError as exc:
        logger.warning("Routinen-Uebersicht: ungueltige Zeitplan-Konfiguration (%s).", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ungueltige Routinen-Konfiguration (ADR-0057): {exc}",
        ) from exc
