"""Dev-/Betreiber-CLI: Org-Entitlement ohne Mollie-Pfad setzen.

Manuelles Override-Werkzeug fuer lokale Tests und Betreiber-Eingriffe (Plan
`2026-06-03-2030_cloud-launch-readiness.md`, Track Cloud-Local-Dev-Tooling).
Hebt eine Org direkt auf `free` oder `pro` und schreibt den Stand via
`EntitlementRepository.upsert` (`source='manual'`) — ohne Mollie-Test-Key,
ohne Webhook.

Bewusst **kein HTTP-Endpoint**: das ist ein Betreiber-/Dev-Tool. Verbindet als
Owner (`DATABASE_URL`, RLS-Bypass) wie der Migrations-Runner / `who2be-purge`.

Plan-Defaults kommen aus `licensing/plans.py` (Single Source of Truth: siehe
auch `docs/licensing/plans.md`). `--quota` / `--rate` ueberschreiben die
Plan-Defaults; nuetzlich z. B. um den 429-Fall mit `--quota 2` schnell zu
provozieren. CLI: `uv run who2be-set-entitlement`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg

from who2be_api.core.config import get_settings
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.licensing.plans import FREE_PLAN, PRO_PLAN, Plan
from who2be_api.repositories.entitlement_repository import (
    EntitlementRepository,
    PgEntitlementRepository,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_SOURCE = "manual"
# Beide Tiers sind hier abgebildet — `free` ist abo-frei und kein Eintrag in
# `PAID_PLANS`, daher die explizite Map (statt `plan_by_code`).
_PLANS: Mapping[str, Plan] = {FREE_PLAN.code: FREE_PLAN, PRO_PLAN.code: PRO_PLAN}


def _plan_to_entitlement(plan: Plan, *, quota: int | None, rate: int | None) -> Entitlement:
    """Baut das Entitlement aus dem Plan + optionalen Overrides."""
    return Entitlement(
        status="active",
        features=plan.features,
        expires_at=None,
        mcp_monthly_quota=quota if quota is not None else plan.mcp_monthly_quota,
        mcp_rate_per_min=rate if rate is not None else plan.mcp_rate_per_min,
        grace_until=None,
    )


def _format_entitlement(org_id: UUID, plan_code: str, entitlement: Entitlement) -> str:
    features = ", ".join(sorted(entitlement.features)) or "(keine)"
    return (
        f"Org {org_id} → {plan_code} (manual)\n"
        f"  status:            {entitlement.status}\n"
        f"  features:          {features}\n"
        f"  mcp_monthly_quota: {entitlement.mcp_monthly_quota}\n"
        f"  mcp_rate_per_min:  {entitlement.mcp_rate_per_min}"
    )


async def set_entitlement(
    repo: EntitlementRepository,
    *,
    org_id: UUID,
    plan_code: str,
    quota: int | None,
    rate: int | None,
) -> Entitlement:
    """Schreibt das Entitlement fuer eine Org. Liefert den resultierenden Stand."""
    plan = _PLANS.get(plan_code.strip().lower())
    if plan is None:
        raise ValueError(f"Unbekannter Plan-Code: {plan_code!r} (erlaubt: free, pro)")

    entitlement = _plan_to_entitlement(plan, quota=quota, rate=rate)
    await repo.upsert(org_id, entitlement, source=_SOURCE, external_ref=None)
    return entitlement


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="who2be-set-entitlement",
        description=(
            "Setzt das Org-Entitlement manuell (Dev-/Betreiber-Tool, ohne Mollie). "
            "Liest die Tier-Defaults aus licensing/plans.py."
        ),
    )
    parser.add_argument("org_id", type=UUID, help="Ziel-Organisation (UUID).")
    parser.add_argument(
        "plan",
        choices=sorted(_PLANS.keys()),
        help="Plan-Tier: free oder pro (Defaults aus licensing/plans.py).",
    )
    parser.add_argument(
        "--quota",
        type=int,
        default=None,
        help="Override fuer mcp_monthly_quota (z. B. --quota 2, um 429 zu provozieren).",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=None,
        help="Override fuer mcp_rate_per_min.",
    )
    return parser.parse_args(argv)


async def _register_jsonb_codec(conn: asyncpg.Connection) -> None:
    """Repo serialisiert `features` als Liste in eine jsonb-Spalte. Ohne Codec
    weist asyncpg das Argument zurueck (`expected str, got list`). Identisch
    zum Laufzeit-Pool (`core/db.py:_init_connection`), hier minimal inline."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def _run(args: argparse.Namespace) -> Entitlement:
    # Kleiner Single-Connection-Pool, damit `PgEntitlementRepository` (Pool-typisiert)
    # ohne Cast laufen kann. Der CLI-Aufruf ist kurzlebig — kein DI/State noetig.
    try:
        pool = await asyncpg.create_pool(
            get_settings().database_url,
            min_size=1,
            max_size=1,
            init=_register_jsonb_codec,
        )
    except (asyncpg.PostgresError, OSError) as exc:
        raise SystemExit(f"Datenbank nicht erreichbar: {exc}") from exc
    assert pool is not None
    try:
        return await set_entitlement(
            PgEntitlementRepository(pool),
            org_id=args.org_id,
            plan_code=args.plan,
            quota=args.quota,
            rate=args.rate,
        )
    finally:
        await pool.close()


def cli() -> None:
    """Console-Entrypoint fuer `who2be-set-entitlement`."""
    args = _parse_args()
    try:
        entitlement = asyncio.run(_run(args))
    except ValueError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    print(_format_entitlement(args.org_id, args.plan, entitlement))


if __name__ == "__main__":
    cli()
