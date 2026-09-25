"""Speicher-Quota-Gate fuer den WorkArea-Ingest (Issue #536).

Zwilling zu `entity_quota_service`, aber fuer **Bytes** statt Zeilen: bevor ein
neuer Ingest Inhalt ablegt, prueft dieses Gate, ob das Org-Entitlement noch
Luft in der Speichergrenze hat.

Greift **ausschliesslich** in der **Cloud**-Edition (`is_cloud()`); On-Prem/OSS
ist unbegrenzt (`storage_quota_bytes is None`).

Anders als `Entitlement.entity_limit()` ist die Grenze hier ein echtes
Entitlement-**Feld** und keine Ableitung, und genau deshalb braucht sie einen
**Cloud-Rueckfall** (`effective_storage_quota_bytes`): `None` heisst nur
ausserhalb der Cloud „unbegrenzt". Innerhalb der Cloud heisst es „kein Wert
gesetzt" — und den Zustand stellt der Billing-Pfad selbst her:
`webhook.map_event_to_entitlement` schreibt beim Revoke
(`customer.subscription.deleted`, `invoice.payment_failed`) ein
`Entitlement(status="inactive", features=frozenset())` **ohne**
`storage_quota_bytes`, der Upsert persistiert das als NULL. Ohne Rueckfall waere
eine gekuendigte Org unbegrenzt — das Gegenteil des Zwecks. Dasselbe gilt fuer
jede Bestands-Zeile vor Migration 0084 und fuer jede vor #536 angelegte
Mollie-Subscription, deren Metadata den Key nicht traegt. Belegt vom Kettentest
`test_storage_quota_downgrade_chain.py`.

Derselbe Vertrag wie beim Entity-Limit: **kein Datenverlust.** Bestand bleibt
les- und herunterladbar — das Gate haengt nur an den Ingest-Routen, nicht an
Read-, Export- oder Download-Pfaden. Nur NEUE Ingests oberhalb der Grenze
werden mit `402` + Upgrade-Hinweis abgewiesen.

Drei bewusste Grenzen der Zaehlung, alle sichtbar statt stillschweigend:

1. **Gezaehlt wird je Workspace, nicht je Org.** `STORAGE_USED_SQL` summiert
   die Blobs *eines* Workspace; das Gate laeuft im `tenant_scope` des
   Requests, unter dem RLS nur den aktuellen Workspace sichtbar macht. Anders
   als beim Entity-Zwilling (dort ist Pro unbegrenzt) ist die Grenze hier
   auch fuer Pro endlich — eine Org mit n Workspaces hat also n-mal das
   Kontingent, solange die Zahl der Workspaces nicht gedeckelt ist
   (`POST /organizations/{id}/workspaces` kennt heute kein Limit). Das ist
   eine Owner-Entscheidung: gedeckelt wird stattdessen die **Zahl** der
   Workspaces, als eigene Karte. Org-weites Zaehlen (Summe ueber alle
   Workspaces samt RLS-Frage) ist bewusst nicht Teil dieser Stufe. Fuer den
   Free-Tier (Personal-Org mit genau einem Workspace) faellt beides zusammen.
2. **Der Tabellen-Store zaehlt NICHT mit.** Die SQLite-Dateien je WorkArea
   (`{WHO2BE_TABLESTORE_DIR}/{workspace_id}/{area_id}.sqlite`, ADR-0049)
   liegen im Dateisystem, nicht in Postgres; ihre Groesse waere nur ueber
   einen `stat()`-Aufruf je Datei bekannt. Dieses Gate deckelt `wa_blob`.
3. **Vorab-Check, keine Nachkalkulation.** Als FastAPI-Dependency kennt das
   Gate den Request-Body nicht; es prueft `summe >= limit`, nicht
   `summe + neue_bytes > limit`. Ein einzelner Ingest kann die Grenze also um
   bis zu `WHO2BE_INGEST_MAX_BYTES` (Default 20 MiB, `core/config.py`)
   ueberschreiten — der naechste wird abgewiesen. Dieselbe Toleranz hat der
   Entity-Zwilling; sie ist der Preis dafuer, dass das Gate vor der teuren
   Pipeline (Download/Extraktion) laeuft statt danach.
"""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

import asyncpg
from fastapi import Depends, status

from who2be_api.core.config import Settings, get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.licensing.edition import is_cloud
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.licensing.service import build_entitlement_port

# Summe der abgelegten Blob-Bytes eines Workspaces. `wa_blob` ist der
# Postgres-Katalog der binaeren Originale (Migration 0075); `size_bytes` traegt
# jede Zeile. Der App-seitige `workspace_id`-Filter bleibt erste
# Verteidigungslinie (RLS ist die zweite). Oeffentlich, weil der
# Entitlement-Read (`routers/entitlement.py`) denselben Verbrauch anzeigt —
# importiert statt kopiert, damit Anzeige und Gate nicht auseinanderlaufen.
STORAGE_USED_SQL = "SELECT coalesce(sum(size_bytes), 0) FROM wa_blob WHERE workspace_id = $1"


class StorageQuotaService:
    """Setzt die Speichergrenze des Entitlements je Workspace an den Ingest-Routen durch."""

    def __init__(self, pool: asyncpg.Pool, settings: Settings | None = None) -> None:
        self._pool = pool
        self._settings = settings or get_settings()

    async def _resolve_org_id(self, workspace_id: UUID) -> UUID:
        org_id = await self._pool.fetchval(
            "SELECT org_id FROM workspace WHERE id = $1",
            workspace_id,
        )
        if org_id is None:
            # Sollte nie passieren — die Workspace-Membership ist bereits geprueft.
            # Wortgleich zu `entity_quota_service`/`mcp_limit_service`.
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace ohne Organisation.",
                reason="workspace_org_missing",
            )
        return cast(UUID, org_id)

    async def _used_bytes(self, workspace_id: UUID) -> int:
        return int(cast(int, await self._pool.fetchval(STORAGE_USED_SQL, workspace_id)))

    async def enforce(self, ctx: WorkspaceContext) -> None:
        """Wirft `402`, wenn die abgelegten Bytes die Tarifgrenze erreicht haben."""
        if not is_cloud(self._settings):
            return

        org_id = await self._resolve_org_id(ctx.workspace_id)
        port = build_entitlement_port(self._pool, self._settings)
        entitlement: Entitlement = await port.resolve(org_id)

        limit = entitlement.effective_storage_quota_bytes(cloud=True)
        if limit is None:  # pragma: no cover - in der Cloud liefert der Rueckfall immer eine Zahl
            return  # Unbegrenzt — kein Summen-Roundtrip noetig.

        used = await self._used_bytes(ctx.workspace_id)
        if used >= limit:
            # Die Grenze gehoert in `params`, nicht in den Locale-Key (ADR-0051):
            # sonst braeuchte jeder Tarif eine eigene Uebersetzung. `used` faehrt
            # mit, damit die UI den Abstand zeigen kann, ohne nachzufragen.
            raise ApiError(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Speichergrenze von {limit} Bytes erreicht. Upgrade auf Pro hebt "
                    "die Grenze an — Abgelegtes bleibt les- und herunterladbar."
                ),
                reason="storage_quota_exceeded",
                params={"limit": limit, "used": used},
            )


async def enforce_storage_quota(
    ctx: Annotated[WorkspaceContext, Depends(get_current_workspace)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> None:
    """FastAPI-Dependency: haengt an den Ingest-Routen (`routers/wa_ingest.py`).

    Bewusst NICHT an allen Creates: Bytes entstehen nur beim Ingest (Blob-PUT
    + `wa_blob`-Zeile); ein Artifact ohne Blob traegt Text, der vom
    Entity-Kontingent gedeckelt wird.
    """
    service = StorageQuotaService(pool)
    await service.enforce(ctx)
