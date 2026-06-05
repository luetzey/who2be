"""Tests fuer die Plan-Tiers + Mollie-Metadaten-Konvention (`licensing/plans.py`).

Stellt sicher, dass die Code-Konstanten zu `docs/licensing/plans.md` passen
(Free 1000/30, Pro 100000/240) und dass die Checkout-Metadata die Konvention
§3.2 erfuellt (org_id, license_policy, mcp_monthly_quota, mcp_rate_per_min).
"""

from __future__ import annotations

from uuid import uuid4

from who2be_api.licensing.entitlement import Feature
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


def test_pro_tier_is_superset_of_free() -> None:
    assert Feature.CORE in PRO_PLAN.features
    assert {Feature.COMPOSITE_PLAYBOOKS, Feature.AGENTS, Feature.AUDIT_EXPORT} <= PRO_PLAN.features
    assert PRO_PLAN.mcp_monthly_quota == 100_000
    assert PRO_PLAN.mcp_rate_per_min == 240


def test_plan_metadata_follows_convention() -> None:
    org_id = uuid4()
    meta = PRO_PLAN.metadata(org_id)
    assert meta["org_id"] == str(org_id)
    # license_policy = sortierte, whitespace-separierte Feature-Liste.
    assert meta["license_policy"] == " ".join(sorted(PRO_PLAN.features))
    assert meta["mcp_monthly_quota"] == "100000"
    assert meta["mcp_rate_per_min"] == "240"
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
    )
    assert plan.code == "x"
