"""Unit-Tests fuer das Entitlement-Modell + die Edition-Flags."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from who2be_api.core.config import Settings
from who2be_api.licensing.edition import current_edition, is_cloud, is_onprem
from who2be_api.licensing.entitlement import (
    ALL_FEATURES,
    CLOUD_FREE_ENTITLEMENT,
    OSS_ENTITLEMENT,
    Entitlement,
    Feature,
)


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


def test_edition_flags() -> None:
    cloud = Settings(edition="cloud")
    onprem = Settings(edition="onprem")
    assert is_cloud(cloud) and not is_onprem(cloud)
    assert is_onprem(onprem) and not is_cloud(onprem)
    assert current_edition(onprem) == "onprem"


def test_default_edition_is_onprem() -> None:
    # OSS-sicherer Default: ohne gesetztes WHO2BE_EDITION ist es On-Prem (unbegrenzt).
    assert Settings().edition == "onprem"
