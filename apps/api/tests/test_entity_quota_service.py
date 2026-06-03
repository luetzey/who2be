"""Unit-Tests fuer das Entity-Quota-Gate (`services/entity_quota_service.py`).

Ohne DB: ein Fake-Pool liefert die Org-Aufloesung + den Entity-Zaehler, ein
Fake-Entitlement-Port das aufgeloeste Entitlement. Belegt: greift nur Cloud;
Free am Limit ⇒ 402; Free unter Limit ⇒ frei; Paid/unbegrenzt ⇒ frei (ohne
Zaehl-Roundtrip); On-Prem ⇒ no-op.
"""

from __future__ import annotations

import asyncio
from typing import Literal
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.config import Settings
from who2be_api.core.security import WorkspaceContext
from who2be_api.licensing.entitlement import (
    CLOUD_FREE_ENTITLEMENT,
    FREE_ENTITY_QUOTA,
    OSS_ENTITLEMENT,
    Entitlement,
)
from who2be_api.services import entity_quota_service
from who2be_api.services.entity_quota_service import EntityQuotaService
from who2be_models import WorkspaceRole

_ORG_ID = uuid4()


class FakePool:
    """Beantwortet die Workspace→Org-Aufloesung und den Entity-Count."""

    def __init__(self, count: int) -> None:
        self._count = count
        self.count_calls = 0

    async def fetchval(self, query: str, *_args: object) -> object:
        if "FROM workspace WHERE" in query:
            return _ORG_ID
        # Sonst: die Count-Query.
        self.count_calls += 1
        return self._count


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
) -> EntityQuotaService:
    monkeypatch.setattr(
        entity_quota_service,
        "build_entitlement_port",
        lambda _pool, _settings: FakePort(entitlement),
    )
    return EntityQuotaService(pool, Settings(edition=edition))


def _run(service: EntityQuotaService) -> None:
    asyncio.run(service.enforce(_ctx()))


def test_onprem_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(count=10_000)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool, edition="onprem")
    _run(service)
    assert pool.count_calls == 0


def test_unlimited_paid_skips_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # OSS_ENTITLEMENT hat Paid-Features ⇒ entity_limit() None ⇒ kein Count noetig.
    pool = FakePool(count=10_000)
    service = _service(monkeypatch, OSS_ENTITLEMENT, pool)
    _run(service)
    assert pool.count_calls == 0


def test_free_under_limit_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(count=FREE_ENTITY_QUOTA - 1)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool)
    _run(service)
    assert pool.count_calls == 1


def test_free_at_limit_blocks_402(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(count=FREE_ENTITY_QUOTA)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool)
    with pytest.raises(HTTPException) as exc:
        _run(service)
    assert exc.value.status_code == 402
    assert "Upgrade" in exc.value.detail


def test_inactive_entitlement_uses_free_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    # Inaktiv (gekuendigt/Fehlzahlung) ⇒ Free-Limit greift trotzdem.
    pool = FakePool(count=FREE_ENTITY_QUOTA)
    service = _service(monkeypatch, Entitlement(status="inactive"), pool)
    with pytest.raises(HTTPException) as exc:
        _run(service)
    assert exc.value.status_code == 402
