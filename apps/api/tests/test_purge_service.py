"""Unit-Tests fuer den Hard-Purge-Job (`core/purge.py`).

Ohne DB: ein Fake-Purge-Repo zaehlt die Aufrufe, `delete_auth_user` ist
monkeypatcht. Belegt: faellige Orgs werden geloescht; ein Account wird nur
finalisiert (`purged_at`), wenn die GoTrue-Identitaet erfolgreich entfernt ist —
sonst bleibt er pending fuer den naechsten Lauf (DSGVO-Erasure-Retry).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from who2be_api.core import purge as purge_module
from who2be_api.core.purge import purge_expired


class FakePurgeRepo:
    def __init__(self, org_ids: list[UUID], user_ids: list[UUID]) -> None:
        self._org_ids = org_ids
        self._user_ids = user_ids
        self.purged_orgs: list[UUID] = []
        self.purged_data: list[UUID] = []
        self.marked: list[UUID] = []

    async def expired_organizations(self, _now: datetime) -> list[UUID]:
        return self._org_ids

    async def purge_organization(self, org_id: UUID) -> None:
        self.purged_orgs.append(org_id)

    async def expired_accounts(self, _now: datetime) -> list[UUID]:
        return self._user_ids

    async def purge_account_data(self, user_id: UUID) -> None:
        self.purged_data.append(user_id)

    async def mark_account_purged(self, user_id: UUID) -> None:
        self.marked.append(user_id)


def test_purge_deletes_orgs_and_finalizes_accounts_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(purge_module, "delete_auth_user", _const(True))
    org, user = uuid4(), uuid4()
    repo = FakePurgeRepo([org], [user])

    result = asyncio.run(purge_expired(repo, now=datetime.now(UTC)))

    assert repo.purged_orgs == [org]
    assert repo.purged_data == [user]
    assert repo.marked == [user]
    assert result.organizations == 1
    assert result.accounts == 1


def test_account_not_finalized_when_gotrue_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(purge_module, "delete_auth_user", _const(False))
    user = uuid4()
    repo = FakePurgeRepo([], [user])

    result = asyncio.run(purge_expired(repo, now=datetime.now(UTC)))

    # Daten weg, aber NICHT finalisiert ⇒ naechster Lauf versucht erneut.
    assert repo.purged_data == [user]
    assert repo.marked == []
    assert result.accounts == 0


def _const(value: bool):  # type: ignore[no-untyped-def]
    async def _fn(_user_id: UUID) -> bool:
        return value

    return _fn
