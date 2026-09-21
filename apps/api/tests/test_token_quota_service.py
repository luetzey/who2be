"""Unit-Tests fuer das Token-Quota-Gate (`services/token_quota_service.py`).

Ohne DB: ein Fake-Pool liefert die Org-Aufloesung + den Token-Zaehler, ein
Fake-Entitlement-Port das aufgeloeste Entitlement. Belegt: greift nur Cloud;
am Limit ⇒ 402 mit `reason` + `params` (ADR-0051); unter dem Limit frei;
`token_quota=None` in der Cloud ⇒ Rueckfall auf den Tarifwert (der Webhook
schreibt beim Downgrade NULL); On-Prem ⇒ no-op.
Dazu die Zaehl-Bedingung selbst (Issue #538, AK4): widerrufene und abgelaufene
Tokens duerfen keinen Slot belegen.
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
    FREE_TOKEN_QUOTA,
    OSS_ENTITLEMENT,
    PRO_TOKEN_QUOTA,
    Entitlement,
)
from who2be_api.services import token_quota_service
from who2be_api.services.token_quota_service import TOKEN_COUNT_SQL, TokenQuotaService
from who2be_models import WorkspaceRole

_ORG_ID = uuid4()


class FakePool:
    """Beantwortet die Workspace→Org-Aufloesung und den Token-Count."""

    def __init__(self, count: int) -> None:
        self._count = count
        self.count_calls = 0
        self.count_query: str | None = None

    async def fetchval(self, query: str, *_args: object) -> object:
        if "FROM workspace WHERE" in query:
            return _ORG_ID
        # Sonst: die Count-Query.
        self.count_calls += 1
        self.count_query = query
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
) -> TokenQuotaService:
    monkeypatch.setattr(
        token_quota_service,
        "build_entitlement_port",
        lambda _pool, _settings: FakePort(entitlement),
    )
    return TokenQuotaService(pool, Settings(edition=edition))


def _run(service: TokenQuotaService) -> None:
    asyncio.run(service.enforce(_ctx()))


def test_onprem_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """On-Prem/OSS ist unbegrenzt — das Gate zaehlt dort nicht einmal."""
    pool = FakePool(count=10_000)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool, edition="onprem")
    _run(service)
    assert pool.count_calls == 0


def test_onprem_license_without_quota_is_unlimited(monkeypatch: pytest.MonkeyPatch) -> None:
    """`token_quota=None` heisst NUR ausserhalb der Cloud „unbegrenzt".

    In der Cloud bedeutet dasselbe `None` „kein Wert gesetzt" und faellt auf den
    Tarifwert zurueck (siehe `test_inactive_without_quota_falls_back_to_free`) —
    sonst haette ein Downgrade die Grenze aufgehoben statt sie durchzusetzen.
    """
    pool = FakePool(count=10_000)
    service = _service(monkeypatch, OSS_ENTITLEMENT, pool, edition="onprem")
    _run(service)
    assert pool.count_calls == 0
    assert OSS_ENTITLEMENT.effective_token_quota(cloud=False) is None


def test_free_under_limit_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(count=FREE_TOKEN_QUOTA - 1)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool)
    _run(service)
    assert pool.count_calls == 1


def test_free_at_limit_blocks_402(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool(count=FREE_TOKEN_QUOTA)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool)
    with pytest.raises(HTTPException) as exc:
        _run(service)
    assert exc.value.status_code == 402


def test_402_carries_reason_and_limit_param(monkeypatch: pytest.MonkeyPatch) -> None:
    """AK1: stabiler `reason` (ADR-0051) UND die Grenze in `params`.

    Die Zahl gehoert in die Daten, nicht in den Locale-Key: sonst braeuchte
    jede Grenze (Free 3, Pro 25, morgen ein dritter Tarif) einen eigenen Key.
    """
    pool = FakePool(count=FREE_TOKEN_QUOTA)
    service = _service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool)
    with pytest.raises(ApiError) as exc:
        _run(service)
    assert exc.value.reason == "token_quota_exceeded"
    assert exc.value.params == {"limit": FREE_TOKEN_QUOTA}
    assert "rotierbar" in exc.value.detail


def test_pro_limit_is_its_own_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pro hat eine EIGENE endliche Zahl — anders als beim Entity-Limit, wo
    jeder Paid-Plan schlicht unbegrenzt ist. Deshalb ein Feld statt einer
    Ableitung aus den Feature-Codes."""
    entitlement = CLOUD_FREE_ENTITLEMENT.model_copy(update={"token_quota": PRO_TOKEN_QUOTA})
    pool = FakePool(count=PRO_TOKEN_QUOTA - 1)
    _run(_service(monkeypatch, entitlement, pool))

    pool_at_limit = FakePool(count=PRO_TOKEN_QUOTA)
    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, entitlement, pool_at_limit))
    assert exc.value.params == {"limit": PRO_TOKEN_QUOTA}


def test_inactive_entitlement_with_persisted_quota_keeps_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gekuendigt/Fehlzahlung mit gesetztem Feld: der persistierte Deckel gilt.

    Das ist der einfache Fall. Den gefaehrlichen — Feld NICHT gesetzt, weil der
    Revoke-Pfad des Webhooks es gar nicht schreibt — deckt
    `test_inactive_without_quota_falls_back_to_free` ab, und Ende-zu-Ende gegen
    das echte `map_event_to_entitlement`
    `packages/billing/tests/test_token_quota_downgrade_chain.py`.
    """
    entitlement = Entitlement(status="inactive", token_quota=FREE_TOKEN_QUOTA)
    pool = FakePool(count=FREE_TOKEN_QUOTA)
    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, entitlement, pool))
    assert exc.value.reason == "token_quota_exceeded"


def test_inactive_without_quota_falls_back_to_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Kern des Rueckfalls: `None` heisst in der Cloud NICHT „unbegrenzt".

    Genau diese Zeile schreibt der Webhook beim Revoke (`webhook.py:441`:
    `Entitlement(status="inactive", features=frozenset())`) und genau so steht
    jede Bestands-Zeile vor Migration 0085 da. Ohne Rueckfall liefe das Gate
    hier ohne Zaehl-Roundtrip durch.
    """
    entitlement = Entitlement(status="inactive", features=frozenset())
    assert entitlement.token_quota is None  # Ausgangslage, nicht Annahme
    pool = FakePool(count=FREE_TOKEN_QUOTA)
    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, entitlement, pool))
    assert exc.value.params == {"limit": FREE_TOKEN_QUOTA}
    assert pool.count_calls == 1


def test_active_paid_without_quota_falls_back_to_pro(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zahlender Bestandskunde ohne das neue Metadatum: Pro-Wert, nicht Free.

    Ein Rueckfall, der jede leere Zeile auf 3 deckelt, wuerde Pro-Kunden bis zum
    naechsten Checkout aussperren — deshalb entscheidet dasselbe Signal wie bei
    `entity_limit()`: Paid-Features vorhanden ⇒ Pro-Wert.
    """
    entitlement = Entitlement(status="active", features=frozenset({"core", "agents"}))
    assert entitlement.token_quota is None
    pool = FakePool(count=PRO_TOKEN_QUOTA - 1)
    _run(_service(monkeypatch, entitlement, pool))

    pool_at_limit = FakePool(count=PRO_TOKEN_QUOTA)
    with pytest.raises(ApiError) as exc:
        _run(_service(monkeypatch, entitlement, pool_at_limit))
    assert exc.value.params == {"limit": PRO_TOKEN_QUOTA}


def test_count_query_excludes_revoked_and_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    """AK4: widerrufene Tokens zaehlen nicht mit — abgelaufene ebenso wenig.

    Gegen die Query selbst statt gegen eine DB, weil die Bedingung hier die
    eigentliche Zusage ist: sie ist wortgleich zu der, unter der
    `PgTokenRepository.fetch_auth_by_hash` einen Token ueberhaupt akzeptiert.
    Ein Token, der sich nicht mehr authentifizieren kann, darf keinen Slot
    blockieren.
    """
    pool = FakePool(count=0)
    _run(_service(monkeypatch, CLOUD_FREE_ENTITLEMENT, pool))
    assert pool.count_query == TOKEN_COUNT_SQL
    assert "revoked_at IS NULL" in TOKEN_COUNT_SQL
    assert "expires_at IS NULL OR expires_at > now()" in TOKEN_COUNT_SQL
    assert "FROM api_token" in TOKEN_COUNT_SQL
