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
    FREE_TOKEN_QUOTA,
    FREE_WORKSPACE_QUOTA,
    OSS_ENTITLEMENT,
    PRO_STORAGE_QUOTA_BYTES,
    PRO_TOKEN_QUOTA,
    PRO_WORKSPACE_QUOTA,
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


def test_oss_entitlement_has_unlimited_token_quota() -> None:
    """Issue #538: On-Prem/OSS ist unbegrenzt — `None`, nicht eine grosse Zahl."""
    assert OSS_ENTITLEMENT.token_quota is None


def test_cloud_free_entitlement_carries_free_token_quota() -> None:
    assert CLOUD_FREE_ENTITLEMENT.token_quota == FREE_TOKEN_QUOTA == 3


def test_token_quota_defaults_to_unlimited() -> None:
    """Bestandszeilen vor Migration 0085 tragen `NULL`; das Modell liest sie als
    unbegrenzt. Das ist die Zusage „kein stiller Deckel auf Bestand"."""
    assert Entitlement().token_quota is None


def test_token_quota_is_a_field_not_a_derivation() -> None:
    """Der Unterschied zum Entity-Zwilling, festgehalten statt kommentiert.

    `entity_limit()` leitet aus den Feature-Codes ab und kennt nur „Free-Zahl
    oder unbegrenzt". Pro braucht beim Token-Kontingent aber eine eigene
    endliche Zahl — Paid-Features duerfen den Wert deshalb NICHT anheben.
    """
    paid = Entitlement(
        status="active",
        features=frozenset({Feature.CORE, Feature.AGENTS}),
        token_quota=PRO_TOKEN_QUOTA,
    )
    assert paid.entity_limit() is None  # Ableitung: Paid ⇒ unbegrenzt
    assert paid.token_quota == PRO_TOKEN_QUOTA == 25  # Feld: bleibt endlich


# --- Speicher-Quota (Issue #536) --------------------------------------------


def test_free_storage_quota_is_100_mib() -> None:
    """Owner-Entscheidung Option A — die Zahl steht auch in docs/licensing/plans.md."""
    assert FREE_STORAGE_QUOTA_BYTES == 100 * 1024 * 1024


def test_pro_storage_quota_is_10_gib() -> None:
    assert PRO_STORAGE_QUOTA_BYTES == 10 * 1024 * 1024 * 1024


def test_oss_entitlement_storage_is_unlimited() -> None:
    """AK 1: `None` = unbegrenzt und ist der On-Prem-Default."""
    assert OSS_ENTITLEMENT.storage_quota_bytes is None
    assert OSS_ENTITLEMENT.effective_storage_quota_bytes(cloud=False) is None


def test_cloud_free_entitlement_carries_free_storage_quota() -> None:
    assert CLOUD_FREE_ENTITLEMENT.storage_quota_bytes == FREE_STORAGE_QUOTA_BYTES
    assert (
        CLOUD_FREE_ENTITLEMENT.effective_storage_quota_bytes(cloud=True) == FREE_STORAGE_QUOTA_BYTES
    )


def test_storage_quota_defaults_to_unlimited() -> None:
    """Ein Entitlement ohne das Feld (Bestandszeile vor Migration 0084) ist auf
    Modell-Ebene unbegrenzt — dieselbe Semantik wie bei den beiden MCP-Feldern.
    Dass die Cloud daraus trotzdem eine Zahl macht, ist die Aufgabe von
    `effective_storage_quota_bytes` (siehe unten)."""
    assert Entitlement().storage_quota_bytes is None


def test_effective_storage_quota_bytes_falls_back_in_cloud() -> None:
    """Der Rueckfall aus W8/P2, wortgleich zu beiden Zwillingen.

    Der Revoke-Pfad des Webhooks schreibt das Feld gar nicht; ohne Rueckfall
    haette ausgerechnet eine gekuendigte Org unbegrenzten Speicher — genau der
    Zustand, den die Karte behebt.
    """
    revoked = Entitlement(status="inactive", features=frozenset())
    assert revoked.storage_quota_bytes is None
    assert revoked.effective_storage_quota_bytes(cloud=True) == FREE_STORAGE_QUOTA_BYTES
    # Ausserhalb der Cloud bleibt `None` unbegrenzt (On-Prem-Lizenz).
    assert revoked.effective_storage_quota_bytes(cloud=False) is None

    paid = Entitlement(status="active", features=frozenset({Feature.CORE, Feature.AGENTS}))
    assert paid.effective_storage_quota_bytes(cloud=True) == PRO_STORAGE_QUOTA_BYTES

    free = Entitlement(status="active", features=frozenset({Feature.CORE}))
    assert free.effective_storage_quota_bytes(cloud=True) == FREE_STORAGE_QUOTA_BYTES


def test_persisted_storage_quota_wins_over_fallback() -> None:
    """Ein gesetztes Feld schlaegt die Ableitung — sonst koennte ein
    `manual_override` mit individueller Zahl (ADR-0028) nicht wirken."""
    ent = Entitlement(status="active", features=frozenset({Feature.CORE}), storage_quota_bytes=42)
    assert ent.effective_storage_quota_bytes(cloud=True) == 42
    assert ent.effective_storage_quota_bytes(cloud=False) == 42


# --- Workspace-Deckel je Org (Issue #576) -----------------------------------


def test_free_workspace_quota_is_one() -> None:
    """Owner-Entscheidung Option A. 0 waere zum Bestand inkonsistent: jede
    Org-Anlage erzeugt atomar einen Default-Workspace, und der letzte Workspace
    einer Org ist unloeschbar (`LastWorkspaceError`)."""
    assert FREE_WORKSPACE_QUOTA == 1


def test_pro_workspace_quota_is_five() -> None:
    """5 x `PRO_STORAGE_QUOTA_BYTES` = 50 GiB maximale Speicherzusage je
    Pro-Org — die Zahl, auf der die Entscheidung beruht."""
    assert PRO_WORKSPACE_QUOTA == 5
    assert PRO_WORKSPACE_QUOTA * PRO_STORAGE_QUOTA_BYTES == 50 * 1024**3


def test_oss_entitlement_workspace_quota_is_unlimited() -> None:
    assert OSS_ENTITLEMENT.workspace_quota is None
    assert OSS_ENTITLEMENT.effective_workspace_quota(cloud=False) is None


def test_cloud_free_entitlement_carries_free_workspace_quota() -> None:
    assert CLOUD_FREE_ENTITLEMENT.workspace_quota == FREE_WORKSPACE_QUOTA
    assert CLOUD_FREE_ENTITLEMENT.effective_workspace_quota(cloud=True) == FREE_WORKSPACE_QUOTA


def test_workspace_quota_defaults_to_unlimited() -> None:
    """Bestandszeilen vor Migration 0086 tragen `NULL` — auf Modell-Ebene
    unbegrenzt. Dass die Cloud daraus trotzdem eine Zahl macht, ist die Aufgabe
    von `effective_workspace_quota` (siehe unten)."""
    assert Entitlement().workspace_quota is None


def test_effective_workspace_quota_falls_back_in_cloud() -> None:
    """Derselbe Rueckfall, den `token_quota` nachtraeglich bekommen musste und
    `storage_quota_bytes` in W8/P2 nachgezogen hat: `None` heisst in der Cloud
    „nicht gesetzt".

    Ohne ihn duerfte ausgerechnet eine gekuendigte Org (der Revoke-Pfad des
    Webhooks schreibt das Feld gar nicht) unbegrenzt Workspaces anlegen.
    """
    revoked = Entitlement(status="inactive", features=frozenset())
    assert revoked.workspace_quota is None
    assert revoked.effective_workspace_quota(cloud=True) == FREE_WORKSPACE_QUOTA
    # Ausserhalb der Cloud bleibt `None` unbegrenzt (On-Prem-Lizenz).
    assert revoked.effective_workspace_quota(cloud=False) is None

    paid = Entitlement(status="active", features=frozenset({Feature.CORE, Feature.AGENTS}))
    assert paid.effective_workspace_quota(cloud=True) == PRO_WORKSPACE_QUOTA

    free = Entitlement(status="active", features=frozenset({Feature.CORE}))
    assert free.effective_workspace_quota(cloud=True) == FREE_WORKSPACE_QUOTA


def test_persisted_workspace_quota_wins_over_fallback() -> None:
    """Ein gesetztes Feld schlaegt die Ableitung — sonst koennte ein
    `manual_override` mit individueller Zahl (ADR-0028) nicht wirken."""
    ent = Entitlement(status="active", features=frozenset({Feature.CORE}), workspace_quota=42)
    assert ent.effective_workspace_quota(cloud=True) == 42
    assert ent.effective_workspace_quota(cloud=False) == 42


def test_edition_flags() -> None:
    cloud = Settings(edition="cloud")
    onprem = Settings(edition="onprem")
    assert is_cloud(cloud) and not is_onprem(cloud)
    assert is_onprem(onprem) and not is_cloud(onprem)
    assert current_edition(onprem) == "onprem"


def test_default_edition_is_onprem() -> None:
    # OSS-sicherer Default: ohne gesetztes WHO2BE_EDITION ist es On-Prem (unbegrenzt).
    assert Settings().edition == "onprem"
