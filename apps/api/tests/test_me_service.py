"""Unit-Tests fuer `MeService` — ohne DB (Fake-Repository).

Kern ist die Trennung der beiden Workspace-Felder (Issue #413):
`default_workspace_id` ist die erste Membership des *Menschen*,
`token_workspace_id` die Bindung der *Credential*. Wer beides gleichsetzt,
schickt einen an Workspace B gepinnten Token nach Workspace A.
"""

import asyncio
from uuid import UUID, uuid4

from who2be_api.services.me_service import MeService
from who2be_models import MeRead


class _FakeMeRepository:
    """Liefert eine feste `MeRead` — die Membership-Abfrage ist hier nicht der Test."""

    def __init__(self, default_workspace_id: UUID) -> None:
        self._default_workspace_id = default_workspace_id
        self.calls: list[UUID] = []

    async def fetch(self, user_id: UUID) -> MeRead:
        self.calls.append(user_id)
        return MeRead(
            user_id=user_id,
            default_workspace_id=self._default_workspace_id,
            organizations=[],
            has_password=True,
        )


def test_fetch_reports_token_workspace_alongside_default() -> None:
    default_ws, token_ws = uuid4(), uuid4()
    repo = _FakeMeRepository(default_ws)
    service = MeService(repo)

    me = asyncio.run(service.fetch(uuid4(), token_workspace_id=token_ws))

    # Beide Felder stehen nebeneinander — `default_workspace_id` bleibt, was das
    # Web fuer seinen `/w/{id}`-Redirect erwartet.
    assert me.token_workspace_id == token_ws
    assert me.default_workspace_id == default_ws


def test_fetch_without_token_binding_leaves_field_none() -> None:
    """JWT-Pfad: die Credential ist an keinen Workspace gepinnt."""
    default_ws = uuid4()
    service = MeService(_FakeMeRepository(default_ws))

    me = asyncio.run(service.fetch(uuid4()))

    assert me.token_workspace_id is None
    assert me.default_workspace_id == default_ws
