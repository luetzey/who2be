"""Unit-Tests fuer das Entitlement-Modell + die Edition-Flags."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from who2be_api.core.config import Settings
from who2be_api.licensing.edition import current_edition, is_cloud, is_onprem
from who2be_api.licensing.entitlement import (
    ALL_FEATURES,
    CLOUD_FREE_ENTITLEMENT,
    FREE_ENTITY_QUOTA,
    FREE_STORAGE_QUOTA_BYTES,
    OSS_ENTITLEMENT,
    PRO_STORAGE_QUOTA_BYTES,
    Entitlement,
    Feature,
)


def test_oss_entitlement_has_unlimited_entity_limit() -> None:
    assert OSS_ENTITLEMENT.entity_limit() is None


def test_cloud_free_entitlement_has_free_entity_limit() -> None:
    assert CLOUD_FREE_ENTITLEMENT.entity_limit() == FREE_ENTITY_QUOTA


def test_paid_features_lift_entity_limit() -> None:
    pro = Entitlement(status="active", features=frozenset({Feature.CORE, Feature.AGENTS}))
    assert pro.entity_limit() is None


def test_inactive_entitlement_falls_back_to_free_entity_limit() -> None:
    ent = Entitlement(status="inactive", features=frozenset({Feature.CORE, Feature.AGENTS}))
    assert ent.entity_limit() == FREE_ENTITY_QUOTA


def test_oss_entitlement_is_unlimited_and_all_features() -> None:
    assert OSS_ENTITLEMENT.is_active()
    assert OSS_ENTITLEMENT.mcp_monthly_quota is None
    assert OSS_ENTITLEMENT.mcp_rate_per_min is None
    assert OSS_ENTITLEMENT.features == ALL_FEATURES
    assert OSS_ENTITLEMENT.has_feature(Feature.SSO)


def test_inactive_status_blocks_features() -> None:
    ent = Entitlement(status="inactive", features=frozenset({Feature.CORE}))
    assert not ent.is_active()
    assert not ent.has_feature(Feature.CORE)


def test_expired_entitlement_is_inactive() -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    ent = Entitlement(status="active", features=frozenset({Feature.CORE}), expires_at=past)
    assert not ent.is_active()


def test_future_expiry_is_active() -> None:
    future = datetime.now(UTC) + timedelta(days=1)
    ent = Entitlement(status="active", features=frozenset({Feature.CORE}), expires_at=future)
    assert ent.is_active()
    assert ent.has_feature(Feature.CORE)


def test_cloud_free_entitlement_has_quota() -> None:
    assert CLOUD_FREE_ENTITLEMENT.is_active()
    assert CLOUD_FREE_ENTITLEMENT.mcp_monthly_quota is not None
    assert CLOUD_FREE_ENTITLEMENT.mcp_rate_per_min is not None


# --- Speicher-Quota (Issue #536) --------------------------------------------


def test_free_storage_quota_is_100_mib() -> None:
    """Owner-Entscheidung Option A — die Zahl steht auch in docs/licensing/plans.md."""
    assert FREE_STORAGE_QUOTA_BYTES == 100 * 1024 * 1024


def test_pro_storage_quota_is_10_gib() -> None:
    assert PRO_STORAGE_QUOTA_BYTES == 10 * 1024 * 1024 * 1024


def test_oss_entitlement_storage_is_unlimited() -> None:
    """AK 1: `None` = unbegrenzt und ist der On-Prem-Default."""
    assert OSS_ENTITLEMENT.storage_quota_bytes is None


def test_cloud_free_entitlement_carries_free_storage_quota() -> None:
    assert CLOUD_FREE_ENTITLEMENT.storage_quota_bytes == FREE_STORAGE_QUOTA_BYTES


def test_storage_quota_defaults_to_unlimited() -> None:
    """Ein Entitlement ohne das Feld (Bestandszeile vor Migration 0084) ist
    unbegrenzt — dieselbe Semantik wie bei den beiden MCP-Feldern."""
    assert Entitlement().storage_quota_bytes is None


def test_edition_flags() -> None:
    cloud = Settings(edition="cloud")
    onprem = Settings(edition="onprem")
    assert is_cloud(cloud) and not is_onprem(cloud)
    assert is_onprem(onprem) and not is_cloud(onprem)
    assert current_edition(onprem) == "onprem"


def test_default_edition_is_onprem() -> None:
    # OSS-sicherer Default: ohne gesetztes WHO2BE_EDITION ist es On-Prem (unbegrenzt).
    assert Settings().edition == "onprem"
