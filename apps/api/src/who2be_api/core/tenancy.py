"""Request-scoped Tenant-Kontext fuer Postgres-RLS (Cloud-Defense-in-Depth).

Ein einziger Choke-Point setzt pro Request den Mandanten: die Dependency
`get_current_workspace` (core/security.py) betritt `tenant_scope(...)` und legt
`workspace_id` + `org_id` in einen ContextVar. Der asyncpg-Pool ist mit
`apply_tenant_settings` als `setup`-Callback konfiguriert (core/db.py): bei
*jedem* Connection-Checkout liest der Callback den ContextVar und setzt
`app.current_tenant` / `app.current_org` als Session-GUC auf der Connection.

Damit gilt:
- Repos/Services brauchen KEINE Aenderung: jedes `pool.acquire()` bzw.
  `pool.fetch()` bekommt automatisch eine mandantengebundene Connection, auch
  bei nebenlaeufigen `asyncio.gather`-Abfragen (jede Coroutine zieht eine
  eigene Connection mit eigenem Setup).
- Die App-seitigen `WHERE workspace_id = ...`-Filter BLEIBEN als erste
  Verteidigungslinie; RLS ist die zweite (Plan R1).
- Kontext-Reset bei Connection-Release uebernimmt asyncpg (`RESET ALL` im
  Pool-Reset), sodass kein Mandant in eine fremde Checkout-Phase leakt. Der
  `setup`-Callback setzt die GUCs nur, wenn ein Kontext vorhanden ist —
  control-plane-Requests (kein Workspace) laufen ohne gesetzten Mandanten.

On-Prem (Plan R2): `APP_DATABASE_URL` ist nicht gesetzt, die App verbindet als
Owner/Superuser, der RLS ohnehin umgeht — `tenant_scope` laeuft identisch, die
GUCs sind dort folgenlos. Kein App-SQL-Unterschied zwischen Cloud und On-Prem.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

import asyncpg

# Session-GUC-Namen. Die RLS-Policies (Migration 0037) lesen sie via
# `current_setting('app.current_tenant', true)` (missing_ok ⇒ NULL, kein Fehler).
TENANT_SETTING = "app.current_tenant"
ORG_SETTING = "app.current_org"


@dataclass(frozen=True)
class TenantContext:
    """Mandant des aktuellen Requests."""

    workspace_id: UUID
    org_id: UUID | None


_tenant_context: ContextVar[TenantContext | None] = ContextVar(
    "who2be_tenant_context", default=None
)


def current_tenant_context() -> TenantContext | None:
    """Liefert den Mandanten des aktuellen Requests (oder `None`)."""
    return _tenant_context.get()


async def apply_tenant_settings(conn: asyncpg.Connection) -> None:
    """asyncpg-`setup`-Callback: setzt die Tenant-GUCs auf einer frischen Connection.

    Wird vom Pool bei jedem Checkout aufgerufen. Ohne gesetzten Kontext
    (control-plane-Request) passiert nichts — die Connection wurde beim
    vorherigen Release per `RESET ALL` bereinigt, traegt also keinen Mandanten.

    Bewusst Session-Level (`is_local = false`): die GUC muss ueber alle Queries
    desselben Checkouts hinweg gelten, auch ausserhalb einer expliziten
    Transaktion (viele Repos lesen ohne `BEGIN`). Der Pool-Reset bei Release
    raeumt sie wieder ab.
    """
    ctx = _tenant_context.get()
    if ctx is None:
        return
    if ctx.org_id is not None:
        await conn.execute(
            "SELECT set_config($1, $3, false), set_config($2, $4, false)",
            TENANT_SETTING,
            ORG_SETTING,
            str(ctx.workspace_id),
            str(ctx.org_id),
        )
    else:
        await conn.execute(
            "SELECT set_config($1, $2, false)",
            TENANT_SETTING,
            str(ctx.workspace_id),
        )


@asynccontextmanager
async def tenant_scope(workspace_id: UUID, org_id: UUID | None) -> AsyncIterator[None]:
    """Setzt den Mandanten des Requests fuer die Dauer des `with`-Blocks.

    Reine ContextVar-Verwaltung; die eigentliche GUC-Belegung passiert lazy im
    Pool-`setup`-Callback bei jedem Connection-Checkout. So ist der Mandant auch
    fuer nebenlaeufige Queries (eigene Connections) korrekt gesetzt.
    """
    token = _tenant_context.set(TenantContext(workspace_id=workspace_id, org_id=org_id))
    try:
        yield
    finally:
        _tenant_context.reset(token)
