"""Workspace-Deckel je Organisation (Issue #576).

Dritter Zwilling neben `entity_quota_service`, `storage_quota_service` (#536)
und `token_quota_service` (#538) — mit einem Unterschied, der der Zweck dieser
Stufe ist: **gezaehlt wird je Organisation, nicht je Workspace.**

Die beiden anderen Tarif-Grenzen zaehlen je Workspace
(`STORAGE_USED_SQL`/`TOKEN_COUNT_SQL` filtern auf `workspace_id`). Ohne eine
Obergrenze fuer die *Zahl* der Workspaces vervielfacht eine Org ihre Kontingente
schlicht durch Anlegen weiterer Workspaces — bei Pro n x 10 GiB Speicher. Dieses
Gate deckelt n. Bei Pro 5 liegt die maximale Speicherzusage einer zahlenden Org
damit bei 50 GiB.

Greift **ausschliesslich** in der **Cloud**-Edition (`is_cloud()`); On-Prem/OSS
ist unbegrenzt. Derselbe Vertrag wie bei den Zwillingen: **kein Datenverlust** —
bestehende Workspaces bleiben vollstaendig nutzbar, auch oberhalb der Grenze;
nur NEUE Anlagen werden mit `402` + Upgrade-Hinweis abgewiesen. Sonst sperrte
ein Downgrade laufende Arbeit aus, und zwar unwiederbringlich: der letzte
Workspace einer Org ist unloeschbar (`LastWorkspaceError`), ein Bestand ueber
der Grenze laesst sich also nicht einmal freiwillig abbauen, ohne Inhalte zu
verlieren.

**Kein Statusfilter in der Zaehlung.** `workspace` hat kein Soft-Delete
(Migration 0006 definiert weder `deleted_at` noch `archived_at`); eine Loeschung
ist hart bzw. laeuft per `ON DELETE CASCADE` an der Org. `count(*)` ist damit
bereits die Zahl der existierenden Workspaces — geloeschte koennen gar nicht
mitzaehlen, und eine Loeschung gibt den Platz sofort wieder frei.

**Nicht gegatete Anlagepfade** (bewusst, nicht vergessen):

* `OrganizationRepository.create` legt in derselben Transaktion einen
  Default-Workspace an, ebenso `bootstrap_service` (On-Prem) und
  `ensure_personal_workspace`. Keiner dieser Pfade laeuft ueber
  `WorkspaceService.create`, keiner ist gegatet — und das muss so bleiben: eine
  Org ohne Workspace waere ein kaputter Zustand, und bei Free-Limit 1 wuerde ein
  Gate dort **jede** Org-Anlage abweisen. Die so entstandenen Workspaces
  **zaehlen** aber im Kontingent mit; nur ihre Anlage wird nicht abgewiesen.
  Dieselbe Trennung wie bei `oauth_service._issue` im Token-Zwilling.

Bekannte Grenze: `count` und `insert` laufen nicht in einer Transaktion — zwei
zeitgleiche Creates am Limit kommen beide durch. Identisch bei beiden
Zwillingen; die Grenze ist eine Tarif-Obergrenze, kein Sicherheits-Gate.

Die zweite bekannte Grenze steht in `docs/licensing/plans.md`: `POST
/organizations` ist selbst unbegrenzt, der Deckel verschiebt den Multiplikator
also auf „Orgs je Nutzer", statt ihn absolut zu schliessen. Das ist eine
Owner-Entscheidung vom 2026-09-22, keine uebersehene Luecke — die Begruendung
steht dort.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.config import Settings, get_settings
from who2be_api.core.errors import ApiError
from who2be_api.licensing.edition import is_cloud
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.licensing.service import build_entitlement_port

# Zahl der Workspaces einer Org. Ohne Statusfilter, weil `workspace` kein
# Soft-Delete kennt (Migration 0006) — jede existierende Zeile ist ein nutzbarer
# Workspace. Kein RLS-Sonderfall: `workspace` traegt keine `tenant_isolation`-
# Policy (weder 0037 noch 0068), und die Org-Endpunkte betreten ohnehin nie
# `tenant_scope`.
WORKSPACE_COUNT_SQL = "SELECT count(*) FROM workspace WHERE org_id = $1"


class WorkspaceQuotaService:
    """Setzt den Workspace-Deckel des Org-Entitlements an der Anlage durch."""

    def __init__(self, pool: asyncpg.Pool, settings: Settings | None = None) -> None:
        self._pool = pool
        self._settings = settings or get_settings()

    async def _count_workspaces(self, org_id: UUID) -> int:
        return cast(int, await self._pool.fetchval(WORKSPACE_COUNT_SQL, org_id))

    async def enforce(self, org_id: UUID) -> None:
        """Wirft `402`, wenn ein weiterer Workspace den Deckel sprengt.

        Nimmt die `org_id` direkt entgegen statt eines `WorkspaceContext`: die
        Anlage laeuft org-scoped (`POST /organizations/{id}/workspaces`), es gibt
        zu diesem Zeitpunkt noch keinen Workspace-Kontext. Damit entfaellt auch
        die Workspace→Org-Aufloesung, die die Zwillinge brauchen.
        """
        if not is_cloud(self._settings):
            return

        port = build_entitlement_port(self._pool, self._settings)
        entitlement: Entitlement = await port.resolve(org_id)

        limit = entitlement.effective_workspace_quota(cloud=True)
        if limit is None:  # pragma: no cover - in der Cloud liefert der Rueckfall immer eine Zahl
            return

        current = await self._count_workspaces(org_id)
        if current >= limit:
            # `params` statt eines Grundes je Grenze: die erreichte Zahl gehoert
            # in die Daten, nicht in den Locale-Key (ADR-0051). Steigt der
            # Deckel, aendert sich hier nichts und keine Uebersetzung.
            raise ApiError(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Der Tarif erlaubt {limit} Workspaces je Organisation. "
                    "Wechsle den Tarif oder loesche einen bestehenden Workspace — "
                    "vorhandene Workspaces bleiben vollstaendig nutzbar."
                ),
                reason="workspace_quota_exceeded",
                params={"limit": limit},
            )
