"""Unit-Tests fuer das Speicher-Quota-Gate (`services/storage_quota_service.py`).

Ohne DB: ein Fake-Pool liefert die Org-Aufloesung + die Byte-Summe, ein
Fake-Entitlement-Port das aufgeloeste Entitlement. Belegt (Issue #536):
greift nur Cloud; Free am Limit ⇒ 402 mit `storage_quota_exceeded` + `params`;
Free unter Limit ⇒ frei; unbegrenzt (On-Prem/OSS, `cloud=False`) ⇒ frei
OHNE Summen-Roundtrip; On-Prem ⇒ no-op. Seit W8/P2 zusaetzlich der
**Cloud-Rueckfall** (`effective_storage_quota_bytes`): ein leeres Feld heisst in
der Cloud „nicht gesetzt", nicht „unbegrenzt" — gekuendigt ⇒ Free-Wert, aktives
Paid-Abo ⇒ Pro-Wert.

Der „kein Datenverlust\"-Vertrag hat einen eigenen Test (`test_wa_ingest.py`):
das Gate haengt an den Ingest-Routen und
NICHT an Read-/Export-Routen — Bestand bleibt ueber der Grenze lesbar.
"""

from __future__ import annotations

import asyncio
from typing import Literal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.config import Settings
from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext
from who2be_api.licensing.entitlement import (
    CLOUD_FREE_ENTITLEMENT,
    FREE_STORAGE_QUOTA_BYTES,
    OSS_ENTITLEMENT,
    PRO_STORAGE_QUOTA_BYTES,
    Entitlement,
    Feature,
)
from who2be_api.services import storage_quota_service
from who2be_api.services.storage_quota_service import StorageQuotaService
from who2be_models import WorkspaceRole

_ORG_ID = uuid4()


class FakePool:
    """Beantwortet die Workspace→Org-Aufloesung und die Byte-Summe."""

    def __init__(self, used_bytes: int) -> None:
        self._used = used_bytes
        self.sum_calls = 0

    async def fetchval(self, query: str, *_args: object) -> object:
        if "FROM workspace WHERE" in query:
            return _ORG_ID
        # Sonst: die Summen-Query.
        self.sum_calls += 1
        return self._used


class FakePort:
    def __init__(self, entitlement: Entitlement) -> None:
        self._entitlement = entitlement

    async def resolve(self, _org_id: UUID) -> Entitlement:
        return self._entitlement


def _ctx() -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=False,
    )


def _service(
    monkeypatch: pytest.MonkeyPatch,
    entitlement: Entitlement,
    pool: FakePool,
    edition: Literal["cloud", "onprem"] = "cloud",
) -> StorageQuotaService:
    monkeypatch.setattr(
        storage_quota_service,
        "build_entitlement_port",
        lambda _pool, _settings: FakePort(entitlement),
    )
    return StorageQuotaService(pool, Settings(edition=edition))


def _run(service: StorageQuotaService) -> None:
    asyncio.run(service.enforce(_ctx()))


def test_onprem_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(used_bytes=PRO_STORAGE_QUOTA_BYTES * 10)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool, edition="onprem")
    _run(service)
    assert pool.sum_calls == 0


def test_onprem_license_without_quota_is_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    """`storage_quota_bytes=None` heisst NUR ausserhalb der Cloud „unbegrenzt".

    In der Cloud bedeutet dasselbe `None` „kein Wert gesetzt" und faellt auf den
    Tarifwert zurueck (siehe `test_inactive_without_quota_falls_back_to_free`).
    Wortgleich zum Test gleichen Namens bei beiden Zwillingen.
    """
    assert OSS_ENTITLEMENT.storage_quota_bytes is None  # Ausgangslage, nicht Annahme
    pool = FakePool(used_bytes=PRO_STORAGE_QUOTA_BYTES * 10)
    service = _service(monkeypatch, OSS_ENTITLEMENT, pool, edition="onprem")
    _run(service)
    assert pool.sum_calls == 0
    assert OSS_ENTITLEMENT.effective_storage_quota_bytes(cloud=False) is None


def test_free_under_limit_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(used_bytes=FREE_STORAGE_QUOTA_BYTES - 1)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool)
    _run(service)
    assert pool.sum_calls == 1


def test_free_at_limit_blocks_402(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(used_bytes=FREE_STORAGE_QUOTA_BYTES)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool)
    with pytest.raises(HTTPException) as exc:
        _run(service)
    assert exc.value.status_code == 402
    assert "Upgrade" in exc.value.detail


def test_402_carries_reason_and_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """AK 2: stabiler `reason` (ADR-0051) + Grenze in `params`, nicht im Key."""
    pool = FakePool(used_bytes=FREE_STORAGE_QUOTA_BYTES + 5)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool)
    with pytest.raises(ApiError) as exc:
        _run(service)
    assert exc.value.reason == "storage_quota_exceeded"
    assert exc.value.params == {
        "limit": FREE_STORAGE_QUOTA_BYTES,
        "used": FREE_STORAGE_QUOTA_BYTES + 5,
    }
    # Die Zahl steht in den Daten; `detail` bleibt der uebersetzbare Fallback.
    assert str(FREE_STORAGE_QUOTA_BYTES) in exc.value.detail


def test_pro_limit_is_enforced_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pro ist nicht unbegrenzt — nur groesser (Owner-Entscheidung Option A)."""
    pro = Entitlement(
        status="active",
        features=frozenset({Feature.CORE, Feature.AGENTS}),
        mcp_monthly_quota=100_000,
        mcp_rate_per_min=240,
        storage_quota_bytes=PRO_STORAGE_QUOTA_BYTES,
    )
    under = FakePool(used_bytes=PRO_STORAGE_QUOTA_BYTES - 1)
    _run(_service(monkeypatch, pro, under))

    over = FakePool(used_bytes=PRO_STORAGE_QUOTA_BYTES)
    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, pro, over))
    assert exc.value.params == {
        "limit": PRO_STORAGE_QUOTA_BYTES,
        "used": PRO_STORAGE_QUOTA_BYTES,
    }


def test_inactive_entitlement_keeps_its_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gekuendigt/Fehlzahlung: die gespeicherte Grenze gilt weiter.

    Anders als `entity_limit()` ist `storage_quota_bytes` kein abgeleiteter
    Wert — ein inaktives Entitlement traegt weiterhin seine Zahl. Das ist
    gewollt: die Ablage soll durch eine ausbleibende Zahlung nicht plötzlich
    einen ANDEREN Deckel bekommen; der Zugriff selbst wird bereits ueber
    `is_active()` an den gated Reads gesteuert.
    """
    inactive = Entitlement(status="inactive", storage_quota_bytes=FREE_STORAGE_QUOTA_BYTES)
    pool = FakePool(used_bytes=FREE_STORAGE_QUOTA_BYTES)
    with pytest.raises(HTTPException) as exc:
        _run(_service(monkeypatch, inactive, pool))
    assert exc.value.status_code == 402


def test_inactive_without_quota_falls_back_to_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Kern des Rueckfalls: `None` heisst in der Cloud NICHT „unbegrenzt".

    Genau diese Zeile schreibt der Webhook beim Revoke
    (`Entitlement(status="inactive", features=frozenset())`) und genau so steht
    jede Bestands-Zeile vor Migration 0084 da. Ohne Rueckfall duerfte
    ausgerechnet eine gekuendigte Org unbegrenzt Bytes ablegen — und das Gate
    wuerde die Summe nicht einmal abfragen (`sum_calls == 0`).
    """
    entitlement = Entitlement(status="inactive", features=frozenset())
    assert entitlement.storage_quota_bytes is None  # Ausgangslage, nicht Annahme
    pool = FakePool(used_bytes=FREE_STORAGE_QUOTA_BYTES)
    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, entitlement, pool))
    assert exc.value.params == {
        "limit": FREE_STORAGE_QUOTA_BYTES,
        "used": FREE_STORAGE_QUOTA_BYTES,
    }
    assert pool.sum_calls == 1


def test_active_paid_without_quota_falls_back_to_pro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zahlender Bestandskunde ohne das Metadatum: Pro-Wert, nicht Free.

    Ein Rueckfall, der jede leere Zeile auf 100 MiB deckelt, wuerde Pro-Kunden
    bis zum naechsten Checkout an ihrem naechsten Ingest aussperren.
    """
    entitlement = Entitlement(status="active", features=frozenset({Feature.CORE, Feature.AGENTS}))
    assert entitlement.storage_quota_bytes is None
    _run(_service(monkeypatch, entitlement, FakePool(used_bytes=PRO_STORAGE_QUOTA_BYTES - 1)))

    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, entitlement, FakePool(used_bytes=PRO_STORAGE_QUOTA_BYTES)))
    assert exc.value.params == {
        "limit": PRO_STORAGE_QUOTA_BYTES,
        "used": PRO_STORAGE_QUOTA_BYTES,
    }
