"""Unit-Tests fuer das MCP-Limit-Gate (`services/mcp_limit_service.py`).

Ohne DB: ein Fake-Pool liefert die Org-Aufloesung, ein Fake-Entitlement-Port das
aufgeloeste Entitlement, ein Fake-Usage-Repo das Monatskontingent. Belegt: greift
nur Cloud + API-Token; inaktiv ⇒ 402; Rate ⇒ 429 (ohne Kontingentverbrauch);
Kontingent ⇒ 429; On-Prem/Operator passieren. Ab #537 zusaetzlich: das Rate-Ceiling
gilt auch **pro Organisation** (zweites Fenster, gleicher Wert) — inklusive
Org-Trennung, Nicht-Verbrauch bei Ablehnung und Redis-Pfad.
"""

from __future__ import annotations

import asyncio
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Request

from who2be_api.core.config import Settings
from who2be_api.core.rate_limit import (
    RedisTokenRateLimiter,
    rate_limit_key,
    token_rate_limiter,
)
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
    """Loest jede Workspace-ID auf dieselbe Org auf — oder auf eine gesetzte."""

    def __init__(self, org_id: UUID = _ORG_ID) -> None:
        self._org_id = org_id

    async def fetchval(self, _query: str, *_args: object) -> UUID:
        return self._org_id


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
    org_id: UUID = _ORG_ID,
) -> McpLimitService:
    monkeypatch.setattr(
        mcp_limit_service,
        "build_entitlement_port",
        lambda _pool, _settings: FakePort(entitlement),
    )
    return McpLimitService(FakePool(org_id), usage, Settings(edition=edition))


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


# --- Org-weites Rate-Fenster (#537, Option A) ---------------------------------
#
# Dasselbe Ceiling gilt zusaetzlich pro Organisation: mehrere Agent-Tokens
# derselben Org teilen sich ein Fenster, N Tokens ergeben nicht N × Rate.


def _key(token: str) -> str:
    """Der Token-Bucket-Schluessel, den der Service fuer diesen Token bildet."""
    return rate_limit_key(cast(Request, FakeRequest(token)))


def _ent(rate: int | None, quota: int | None = 1000) -> Entitlement:
    return Entitlement(
        status="active",
        features=frozenset({"core"}),
        mcp_monthly_quota=quota,
        mcp_rate_per_min=rate,
    )


def test_two_tokens_of_same_org_share_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jedes Token unter seinem eigenen Ceiling, zusammen darueber ⇒ 429 (AK 1)."""
    usage = FakeUsageRepo()
    service = _service(monkeypatch, _ent(rate=1), usage)
    ctx = _ctx(is_api_token=True)
    _run(service, ctx, token="w2b_token_a")
    # Token B hat sein eigenes Fenster noch frei — das Org-Fenster ist voll.
    with pytest.raises(HTTPException) as exc:
        _run(service, ctx, token="w2b_token_b")
    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": "60"}
    assert getattr(exc.value, "reason", None) == "mcp_rate_limited"


def test_tokens_of_different_orgs_do_not_interfere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Trennung, nicht nur die Ablehnung (AK 2)."""
    other_org = uuid4()
    usage_a = FakeUsageRepo()
    usage_b = FakeUsageRepo()
    service_a = _service(monkeypatch, _ent(rate=1), usage_a)
    service_b = _service(monkeypatch, _ent(rate=1), usage_b, org_id=other_org)
    ctx = _ctx(is_api_token=True)

    _run(service_a, ctx, token="w2b_org_a")
    # Org A ist am Limit …
    with pytest.raises(HTTPException):
        _run(service_a, ctx, token="w2b_org_a2")
    # … Org B ist davon unberuehrt.
    _run(service_b, ctx, token="w2b_org_b")
    assert usage_b.count == 1


def test_org_rejection_consumes_neither_quota_nor_token_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der abgewiesene Read belastet weder Kontingent noch Token-Fenster (AK 3)."""
    usage = FakeUsageRepo()
    service = _service(monkeypatch, _ent(rate=2), usage)
    ctx = _ctx(is_api_token=True)
    # Ein Token fuellt das Org-Fenster (2/min) alleine aus.
    _run(service, ctx, token="w2b_hot")
    _run(service, ctx, token="w2b_hot")
    assert usage.count == 2

    with pytest.raises(HTTPException) as exc:
        _run(service, ctx, token="w2b_cold")
    assert exc.value.status_code == 429
    # Kontingent: unveraendert.
    assert usage.count == 2
    assert usage.increments == 2
    # Token-Fenster von `w2b_cold`: unangetastet — beide Slots sind noch frei.
    cold = _key("w2b_cold")
    assert token_rate_limiter.allow(cold, 2)
    assert token_rate_limiter.allow(cold, 2)
    assert not token_rate_limiter.allow(cold, 2)


def test_unlimited_rate_passes_both_buckets(monkeypatch: pytest.MonkeyPatch) -> None:
    """`mcp_rate_per_min is None` ⇒ beide Fenster lassen durch (AK 4)."""
    usage = FakeUsageRepo()
    service = _service(monkeypatch, _ent(rate=None), usage)
    ctx = _ctx(is_api_token=True)
    for i in range(50):
        _run(service, ctx, token=f"w2b_unlimited_{i % 3}")
    assert usage.count == 50


def test_onprem_ignores_org_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """On-Prem/OSS steigt vor jedem Fenster aus — unveraendert."""
    usage = FakeUsageRepo()
    service = _service(monkeypatch, _ent(rate=1), usage, edition="onprem")
    ctx = _ctx(is_api_token=True)
    for _ in range(5):
        _run(service, ctx, token="w2b_onprem")
    assert usage.increments == 0


def test_org_window_works_on_redis_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Cloud-Edition faehrt `RedisTokenRateLimiter` — der Pfad wird belegt (AK 5).

    `limits` kennt `memory://` als voll funktionsfaehiges Storage mit derselben
    Moving-Window-Strategie; der Redis-URI unterscheidet nur die Verbindung.
    Damit wird die Redis-Klasse (nicht ihr In-Memory-Zwilling) ausgefuehrt, ohne
    dass ein Server laufen muss.
    """
    redis_like = RedisTokenRateLimiter("redis://unused:6379")
    monkeypatch.setattr(redis_like, "storage_uri", "memory://")
    monkeypatch.setattr(mcp_limit_service, "token_rate_limiter", redis_like)

    usage = FakeUsageRepo()
    service = _service(monkeypatch, _ent(rate=1), usage)
    ctx = _ctx(is_api_token=True)
    _run(service, ctx, token="w2b_redis_a")
    with pytest.raises(HTTPException) as exc:
        _run(service, ctx, token="w2b_redis_b")
    assert exc.value.status_code == 429
    assert getattr(exc.value, "reason", None) == "mcp_rate_limited"
    # Und der abgewiesene Read hat das Kontingent nicht belastet.
    assert usage.count == 1
