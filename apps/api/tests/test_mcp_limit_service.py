"""Unit-Tests fuer das MCP-Limit-Gate (`services/mcp_limit_service.py`).

Ohne DB: ein Fake-Pool liefert die Org-Aufloesung, ein Fake-Entitlement-Port das
aufgeloeste Entitlement, ein Fake-Usage-Repo das Monatskontingent. Belegt: greift
nur Cloud + API-Token; inaktiv ⇒ 402; Rate ⇒ 429 (ohne Kontingentverbrauch);
Kontingent ⇒ 429; On-Prem/Operator passieren.
"""

from __future__ import annotations

import asyncio
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request

from who2be_api.core.config import Settings
from who2be_api.core.rate_limit import token_rate_limiter
from who2be_api.core.security import WorkspaceContext
from who2be_api.licensing.entitlement import Entitlement
from who2be_api.services import mcp_limit_service
from who2be_api.services.mcp_limit_service import McpLimitService
from who2be_models import WorkspaceRole

_ORG_ID = uuid4()


class FakeRequest:
    """Minimaler Request-Stub: `rate_limit_key` liest nur `headers.get`."""

    def __init__(self, token: str) -> None:
        self.headers = {"authorization": f"Bearer {token}"}


class FakePool:
    async def fetchval(self, _query: str, *_args: object) -> UUID:
        return _ORG_ID


class FakeUsageRepo:
    def __init__(self, start: int = 0) -> None:
        self.count = start
        self.increments = 0

    async def increment_if_allowed(self, _org_id: UUID, _period: str, quota: int) -> int | None:
        if self.count >= quota:
            return None
        self.increments += 1
        self.count += 1
        return self.count

    async def current(self, _org_id: UUID, _period: str) -> int:
        return self.count


class FakePort:
    def __init__(self, entitlement: Entitlement) -> None:
        self._entitlement = entitlement

    async def resolve(self, _org_id: UUID) -> Entitlement:
        return self._entitlement


def _ctx(*, is_api_token: bool) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.viewer,
        is_api_token=is_api_token,
    )


def _service(
    monkeypatch: pytest.MonkeyPatch,
    entitlement: Entitlement,
    usage: FakeUsageRepo,
    edition: Literal["cloud", "onprem"] = "cloud",
) -> McpLimitService:
    monkeypatch.setattr(
        mcp_limit_service,
        "build_entitlement_port",
        lambda _pool, _settings: FakePort(entitlement),
    )
    return McpLimitService(FakePool(), usage, Settings(edition=edition))


def _run(service: McpLimitService, ctx: WorkspaceContext, token: str = "w2b_unit") -> None:
    asyncio.run(service.enforce(cast(Request, FakeRequest(token)), ctx))


def setup_function() -> None:
    token_rate_limiter.reset()


def test_onprem_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    usage = FakeUsageRepo()
    service = _service(monkeypatch, Entitlement(status="inactive"), usage, edition="onprem")
    _run(service, _ctx(is_api_token=True))
    assert usage.increments == 0


def test_operator_jwt_read_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    usage = FakeUsageRepo()
    service = _service(monkeypatch, Entitlement(status="inactive"), usage)
    _run(service, _ctx(is_api_token=False))
    assert usage.increments == 0


def test_inactive_entitlement_blocks_402(monkeypatch: pytest.MonkeyPatch) -> None:
    usage = FakeUsageRepo()
    service = _service(monkeypatch, Entitlement(status="inactive"), usage)
    with pytest.raises(HTTPException) as exc:
        _run(service, _ctx(is_api_token=True))
    assert exc.value.status_code == 402
    assert usage.increments == 0


def test_quota_exceeded_returns_429_without_inflating_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ent = Entitlement(status="active", features=frozenset({"core"}), mcp_monthly_quota=2)
    usage = FakeUsageRepo(start=2)  # bereits am Limit
    service = _service(monkeypatch, ent, usage)
    with pytest.raises(HTTPException) as exc:
        _run(service, _ctx(is_api_token=True))
    assert exc.value.status_code == 429
    # Harter Check-and-Increment: der abgewiesene Read treibt den Zaehler NICHT hoch (M-2).
    assert usage.count == 2
    assert usage.increments == 0


def test_zero_quota_blocks_all_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    ent = Entitlement(status="active", features=frozenset({"core"}), mcp_monthly_quota=0)
    usage = FakeUsageRepo()
    service = _service(monkeypatch, ent, usage)
    with pytest.raises(HTTPException) as exc:
        _run(service, _ctx(is_api_token=True))
    assert exc.value.status_code == 429
    assert usage.increments == 0


def test_within_quota_passes_and_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    ent = Entitlement(status="active", features=frozenset({"core"}), mcp_monthly_quota=100)
    usage = FakeUsageRepo()
    service = _service(monkeypatch, ent, usage)
    _run(service, _ctx(is_api_token=True))
    assert usage.count == 1


def test_unlimited_quota_does_not_count(monkeypatch: pytest.MonkeyPatch) -> None:
    ent = Entitlement(status="active", features=frozenset({"core"}), mcp_monthly_quota=None)
    usage = FakeUsageRepo()
    service = _service(monkeypatch, ent, usage)
    _run(service, _ctx(is_api_token=True))
    assert usage.increments == 0


def test_rate_limit_returns_429_without_consuming_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    ent = Entitlement(
        status="active",
        features=frozenset({"core"}),
        mcp_monthly_quota=1000,
        mcp_rate_per_min=1,
    )
    usage = FakeUsageRepo()
    service = _service(monkeypatch, ent, usage)
    ctx = _ctx(is_api_token=True)
    # Erster Read: ok (zaehlt 1 fuer das Kontingent).
    _run(service, ctx, token="w2b_same")
    # Zweiter Read mit demselben Token im selben Fenster: Rate-Limit ⇒ 429.
    with pytest.raises(HTTPException) as exc:
        _run(service, ctx, token="w2b_same")
    assert exc.value.status_code == 429
    # Das Kontingent wurde durch den abgewiesenen Read NICHT weiter belastet.
    assert usage.count == 1
