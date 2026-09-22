"""Tests fuer die Plan-Tiers + Mollie-Metadaten-Konvention (`licensing/plans.py`).

Stellt sicher, dass die Code-Konstanten zu `docs/licensing/plans.md` passen
(Free 1000/30, Pro 100000/240) und dass die Checkout-Metadata die Konvention
§3.2 erfuellt (org_id, license_policy, mcp_monthly_quota, mcp_rate_per_min,
token_quota, storage_quota_bytes).
"""

from __future__ import annotations

from uuid import uuid4

from who2be_api.licensing.entitlement import (
    CLOUD_FREE_ENTITLEMENT,
    FREE_STORAGE_QUOTA_BYTES,
    FREE_TOKEN_QUOTA,
    PRO_STORAGE_QUOTA_BYTES,
    PRO_TOKEN_QUOTA,
    Feature,
)
from who2be_billing.plans import (
    FREE_PLAN,
    PRO_PLAN,
    Plan,
    plan_by_code,
)


def test_free_tier_matches_cloud_free_entitlement() -> None:
    assert FREE_PLAN.features == frozenset({Feature.CORE})
    assert FREE_PLAN.mcp_monthly_quota == 1_000
    assert FREE_PLAN.mcp_rate_per_min == 30
    # Issue #538: der Free-Plan und der Cloud-Default muessen dieselbe
    # Token-Grenze tragen — sonst haette eine Org je nach Herkunft ihres
    # Entitlements (Webhook vs. Default) ein anderes Kontingent.
    assert FREE_PLAN.token_quota == FREE_TOKEN_QUOTA == 3
    assert CLOUD_FREE_ENTITLEMENT.token_quota == FREE_TOKEN_QUOTA
    # Issue #536: Free 100 MB — dieselbe Zahl wie `CLOUD_FREE_ENTITLEMENT`.
    assert FREE_PLAN.storage_quota_bytes == FREE_STORAGE_QUOTA_BYTES
    assert FREE_PLAN.storage_quota_bytes == 100 * 1024 * 1024


def test_pro_tier_is_superset_of_free() -> None:
    assert Feature.CORE in PRO_PLAN.features
    assert {Feature.COMPOSITE_PLAYBOOKS, Feature.AGENTS, Feature.AUDIT_EXPORT} <= PRO_PLAN.features
    assert PRO_PLAN.mcp_monthly_quota == 100_000
    assert PRO_PLAN.mcp_rate_per_min == 240
    # Pro ist beim Token-Kontingent NICHT unbegrenzt (anders als beim
    # Entity-Limit) — es hat eine eigene endliche Zahl.
    assert PRO_PLAN.token_quota == PRO_TOKEN_QUOTA == 25
    assert PRO_PLAN.token_quota > FREE_PLAN.token_quota
    # Issue #536: Pro 10 GB.
    assert PRO_PLAN.storage_quota_bytes == PRO_STORAGE_QUOTA_BYTES
    assert PRO_PLAN.storage_quota_bytes == 10 * 1024 * 1024 * 1024


def test_plan_metadata_follows_convention() -> None:
    org_id = uuid4()
    meta = PRO_PLAN.metadata(org_id)
    assert meta["org_id"] == str(org_id)
    # license_policy = sortierte, whitespace-separierte Feature-Liste.
    assert meta["license_policy"] == " ".join(sorted(PRO_PLAN.features))
    assert meta["mcp_monthly_quota"] == "100000"
    assert meta["mcp_rate_per_min"] == "240"
    assert meta["token_quota"] == "25"
    # Issue #536: der Pull-Adapter liest diesen Key ohne Sonderfall zurueck.
    assert meta["storage_quota_bytes"] == str(PRO_STORAGE_QUOTA_BYTES)
    assert meta["plan_code"] == "pro"


def test_plan_by_code_only_returns_paid_plans() -> None:
    assert plan_by_code("pro") is PRO_PLAN
    assert plan_by_code("PRO") is PRO_PLAN  # case-insensitiv
    # Free ist abo-frei und damit nicht ueber den Checkout buchbar.
    assert plan_by_code("free") is None
    assert plan_by_code("enterprise") is None


def test_plan_is_frozen() -> None:
    plan = Plan(
        code="x",
        name="X",
        price_eur="1.00",
        interval="1 month",
        features=frozenset(),
        mcp_monthly_quota=1,
        mcp_rate_per_min=1,
        token_quota=1,
        storage_quota_bytes=1,
    )
    assert plan.code == "x"
