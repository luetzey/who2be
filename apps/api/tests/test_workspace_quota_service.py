"""Unit-Tests fuer den Workspace-Deckel (`services/workspace_quota_service.py`).

Ohne DB: ein Fake-Pool liefert den Workspace-Zaehler, ein Fake-Entitlement-Port
das aufgeloeste Entitlement. Belegt: greift nur Cloud; am Limit ⇒ 402 mit
`reason` + `params` (ADR-0051); unter dem Limit frei; `workspace_quota=None` in
der Cloud ⇒ Rueckfall auf den Tarifwert (der Webhook schreibt beim Downgrade
NULL); On-Prem ⇒ no-op.

Dazu die Zaehl-Bedingung selbst (Issue #576): sie traegt bewusst KEINEN
Statusfilter, weil `workspace` kein Soft-Delete kennt.
"""

from __future__ import annotations

import asyncio
from typing import Literal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.config import Settings
from who2be_api.core.errors import ApiError
from who2be_api.licensing.entitlement import (
    CLOUD_FREE_ENTITLEMENT,
    FREE_WORKSPACE_QUOTA,
    OSS_ENTITLEMENT,
    PRO_WORKSPACE_QUOTA,
    Entitlement,
)
from who2be_api.services import workspace_quota_service
from who2be_api.services.workspace_quota_service import (
    WORKSPACE_COUNT_SQL,
    WorkspaceQuotaService,
)

_ORG_ID = uuid4()


class FakePool:
    """Beantwortet die Zaehl-Query; zaehlt mit, wie oft sie lief."""

    def __init__(self, count: int) -> None:
        self._count = count
        self.count_calls = 0
        self.count_query: str | None = None

    async def fetchval(self, query: str, *_args: object) -> object:
        self.count_calls += 1
        self.count_query = query
        return self._count


class FakePort:
    def __init__(self, entitlement: Entitlement) -> None:
        self._entitlement = entitlement

    async def resolve(self, _org_id: UUID) -> Entitlement:
        return self._entitlement


def _service(
    monkeypatch: pytest.MonkeyPatch,
    entitlement: Entitlement,
    pool: FakePool,
    edition: Literal["cloud", "onprem"] = "cloud",
) -> WorkspaceQuotaService:
    monkeypatch.setattr(
        workspace_quota_service,
        "build_entitlement_port",
        lambda _pool, _settings: FakePort(entitlement),
    )
    return WorkspaceQuotaService(pool, Settings(edition=edition))


def _run(service: WorkspaceQuotaService) -> None:
    asyncio.run(service.enforce(_ORG_ID))


def test_onprem_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """On-Prem/OSS ist unbegrenzt — das Gate zaehlt dort nicht einmal."""
    pool = FakePool(count=10_000)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool, edition="onprem")
    _run(service)
    assert pool.count_calls == 0


def test_onprem_license_without_quota_is_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    """`workspace_quota=None` heisst NUR ausserhalb der Cloud „unbegrenzt".

    In der Cloud bedeutet dasselbe `None` „kein Wert gesetzt" und faellt auf den
    Tarifwert zurueck (siehe `test_inactive_without_quota_falls_back_to_free`).
    """
    pool = FakePool(count=10_000)
    service = _service(monkeypatch, OSS_ENTITLEMENT, pool, edition="onprem")
    _run(service)
    assert pool.count_calls == 0
    assert OSS_ENTITLEMENT.effective_workspace_quota(cloud=False) is None


def test_free_under_limit_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(count=FREE_WORKSPACE_QUOTA - 1)
    _run(_service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool))
    assert pool.count_calls == 1


def test_free_at_limit_blocks_402(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(count=FREE_WORKSPACE_QUOTA)
    with pytest.raises(HTTPException) as exc:
        _run(_service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool))
    assert exc.value.status_code == 402


def test_402_carries_reason_and_limit_param(monkeypatch: pytest.MonkeyPatch) -> None:
    """AK: stabiler `reason` (ADR-0051) UND die Grenze in `params`.

    Die Zahl gehoert in die Daten, nicht in den Locale-Key: sonst braeuchte
    jede Grenze (Free 1, Pro 5, morgen ein dritter Tarif) einen eigenen Key.
    """
    pool = FakePool(count=FREE_WORKSPACE_QUOTA)
    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool))
    assert exc.value.reason == "workspace_quota_exceeded"
    assert exc.value.params == {"limit": FREE_WORKSPACE_QUOTA}
    # Der Text sagt zu, dass Bestand nutzbar bleibt — die Kern-Zusage des Issues.
    assert "nutzbar" in exc.value.detail


def test_pro_limit_is_its_own_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pro hat eine EIGENE endliche Zahl — anders als beim Entity-Limit, wo
    jeder Paid-Plan schlicht unbegrenzt ist."""
    entitlement = CLOUD_FREE_ENTITLEMENT.model_copy(update={"workspace_quota": PRO_WORKSPACE_QUOTA})
    _run(_service(monkeypatch, entitlement, FakePool(count=PRO_WORKSPACE_QUOTA - 1)))

    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, entitlement, FakePool(count=PRO_WORKSPACE_QUOTA)))
    assert exc.value.params == {"limit": PRO_WORKSPACE_QUOTA}


def test_inactive_without_quota_falls_back_to_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Kern des Rueckfalls: `None` heisst in der Cloud NICHT „unbegrenzt".

    Genau diese Zeile schreibt der Webhook beim Revoke
    (`Entitlement(status="inactive", features=frozenset())`) und genau so steht
    jede Bestands-Zeile vor Migration 0086 da. Ohne Rueckfall duerfte
    ausgerechnet eine gekuendigte Org unbegrenzt Workspaces anlegen.
    """
    entitlement = Entitlement(status="inactive", features=frozenset())
    assert entitlement.workspace_quota is None  # Ausgangslage, nicht Annahme
    pool = FakePool(count=FREE_WORKSPACE_QUOTA)
    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, entitlement, pool))
    assert exc.value.params == {"limit": FREE_WORKSPACE_QUOTA}
    assert pool.count_calls == 1


def test_active_paid_without_quota_falls_back_to_pro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zahlender Bestandskunde ohne das neue Metadatum: Pro-Wert, nicht Free.

    Ein Rueckfall, der jede leere Zeile auf 1 deckelt, wuerde Pro-Kunden bis zum
    naechsten Checkout an ihrem zweiten Workspace aussperren.
    """
    entitlement = Entitlement(status="active", features=frozenset({"core", "agents"}))
    assert entitlement.workspace_quota is None
    _run(_service(monkeypatch, entitlement, FakePool(count=PRO_WORKSPACE_QUOTA - 1)))

    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, entitlement, FakePool(count=PRO_WORKSPACE_QUOTA)))
    assert exc.value.params == {"limit": PRO_WORKSPACE_QUOTA}


def test_count_query_is_org_scoped_and_has_no_status_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die beiden Eigenheiten dieser Zaehlung, gegen die Query festgehalten.

    1. `org_id`, nicht `workspace_id` — das ist der Unterschied zu beiden
       Zwillingen und der Zweck dieser Stufe.
    2. Kein Statusfilter: `workspace` hat kein Soft-Delete (Migration 0006),
       eine geloeschte Zeile existiert schlicht nicht mehr. Ein Filter hier
       waere toter Code, der eine nicht vorhandene Spalte suggeriert.
    """
    pool = FakePool(count=0)
    _run(_service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool))
    assert pool.count_query == WORKSPACE_COUNT_SQL
    assert "FROM workspace" in WORKSPACE_COUNT_SQL
    assert "org_id = $1" in WORKSPACE_COUNT_SQL
    assert "deleted_at" not in WORKSPACE_COUNT_SQL
    assert "archived" not in WORKSPACE_COUNT_SQL
