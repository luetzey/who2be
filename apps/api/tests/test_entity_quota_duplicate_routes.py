"""Waechter: die Kopier-Routen tragen dasselbe Entity-Gate wie ihre Create-Geschwister.

**Warum dieser Test existiert.** `POST /personas/{id}/duplicate`,
`POST /resources/{id}/duplicate` und `POST /agents/{id}/copy` legen ueber
`_repo.insert` echte neue `persona`/`resource`/`agent`-Zeilen an, und genau
diese Typen zaehlt `entity_quota_service._COUNT_QUERY` mit. Sie gehoeren damit
unter dasselbe Gate wie ihre Create-Geschwister, und dieser Test haelt das fest.

`test_gate_inventory.py` friert das Gate-Inventar als Golden ein und faengt
damit das *Verschwinden* eines Gates. Dieser Test hier prueft die andere
Richtung, an der lebenden Route: dass am Limit wirklich ein `402` mit
`entity_quota_exceeded` zurueckkommt, und — die Gegenprobe — dass das Gate
unter dem Limit nicht blockt, sondern in den Service durchlaesst.

**Ohne DB, mit Absicht.** Der Fake-Pool beantwortet genau die zwei Fragen des
Gates (Workspace→Org, Entity-Count); `get_current_workspace` und `get_pool`
kommen per `dependency_overrides`. So laeuft der Test auch ohne Docker und
misst nur das Gate, nicht die Persistenz.

**Die Gegenprobe braucht ein Signal.** Laesst das Gate durch, laeuft der
Request in den Service und trifft dort auf den Fake-Pool. Statt eines diffusen
`AttributeError` wirft `_FakePool.fetchrow` deshalb `_ReachedService` — die
Exception IST die Zusicherung „das Gate hat durchgelassen".
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import Settings
from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.licensing.entitlement import CLOUD_FREE_ENTITLEMENT, FREE_ENTITY_QUOTA, Entitlement
from who2be_api.main import app
from who2be_api.services import entity_quota_service
from who2be_models import WorkspaceRole

_WORKSPACE_ID = uuid4()
_ORG_ID = uuid4()
_GHOST = uuid4()
_PREFIX = f"/v1/workspaces/{_WORKSPACE_ID}"


class _ReachedService(RuntimeError):
    """Das Gate hat durchgelassen und der Request ist im Service angekommen."""


class _FakePool:
    """Beantwortet die zwei Gate-Fragen; alles Weitere ist schon „durchgelassen"."""

    def __init__(self, count: int) -> None:
        self._count = count

    async def fetchval(self, query: str, *_args: object) -> object:
        if "FROM workspace WHERE" in query:
            return _ORG_ID
        return self._count

    async def fetchrow(self, *_args: object, **_kwargs: object) -> object:
        raise _ReachedService

    async def fetch(self, *_args: object, **_kwargs: object) -> object:
        raise _ReachedService

    def acquire(self) -> object:
        raise _ReachedService


class _FakePort:
    def __init__(self, entitlement: Entitlement) -> None:
        self._entitlement = entitlement

    async def resolve(self, _org_id: UUID) -> Entitlement:
        return self._entitlement


# Alle POST-Routen, die eine in `_COUNT_QUERY` gezaehlte Entity anlegen:
# die drei Creates (seit je gegatet, hier als Regressionsanker) und die drei
# Kopier-Routen, um die es geht. `playbook` und `external_tool` haben keine
# Kopier-Route — ihre Creates stehen der Vollstaendigkeit halber mit drin.
_QUOTA_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("creates persona", f"{_PREFIX}/personas", {"name": "Neu"}),
    ("creates playbook", f"{_PREFIX}/playbooks", {"name": "Neu"}),
    ("creates resource", f"{_PREFIX}/resources", {"name": "Neu"}),
    ("creates agent", f"{_PREFIX}/agents", {"name": "Neu"}),
    ("creates external_tool", f"{_PREFIX}/external_tools", {"name": "Neu"}),
    ("copies persona", f"{_PREFIX}/personas/{_GHOST}/duplicate", None),
    ("copies resource", f"{_PREFIX}/resources/{_GHOST}/duplicate", None),
    ("copies agent", f"{_PREFIX}/agents/{_GHOST}/copy", {"name": "Kopie"}),
]


@pytest.fixture
def client(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: ANN401
    """TestClient mit Cloud-Edition, Free-Entitlement und Fake-Pool.

    Der Entity-Count kommt aus dem indirekten Fixture-Parameter, damit derselbe
    Aufbau die „am Limit"- und die „unter dem Limit"-Probe traegt.
    """
    count: int = request.param
    monkeypatch.setattr(entity_quota_service, "get_settings", lambda: Settings(edition="cloud"))
    monkeypatch.setattr(
        entity_quota_service,
        "build_entitlement_port",
        lambda _pool, _settings: _FakePort(CLOUD_FREE_ENTITLEMENT),
    )
    ctx = WorkspaceContext(
        workspace_id=_WORKSPACE_ID,
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=False,
    )
    pool = _FakePool(count)
    app.dependency_overrides[get_current_workspace] = lambda: ctx
    app.dependency_overrides[get_pool] = lambda: pool
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_current_workspace, None)
        app.dependency_overrides.pop(get_pool, None)


@pytest.mark.parametrize("client", [FREE_ENTITY_QUOTA], indirect=True)
@pytest.mark.parametrize(
    ("label", "path", "body"), _QUOTA_ROUTES, ids=[r[0] for r in _QUOTA_ROUTES]
)
def test_route_blocks_at_free_limit(
    client: TestClient, label: str, path: str, body: dict[str, Any] | None
) -> None:
    """Am Free-Limit antwortet jede kontingentierte Schreib-Route mit 402."""
    res = client.post(path, json=body)
    assert res.status_code == 402, f"{label} ({path}): {res.status_code} {res.text}"
    assert res.json()["reason"] == "entity_quota_exceeded", res.text


@pytest.mark.parametrize("client", [FREE_ENTITY_QUOTA - 1], indirect=True)
@pytest.mark.parametrize(
    ("label", "path", "body"), _QUOTA_ROUTES, ids=[r[0] for r in _QUOTA_ROUTES]
)
def test_route_passes_below_free_limit(
    client: TestClient, label: str, path: str, body: dict[str, Any] | None
) -> None:
    """Unter dem Limit laesst das Gate durch — sonst waere der 402 oben wertlos.

    Ohne diese Gegenprobe wuerde ein Gate, das *immer* blockt, den Test oben
    ebenso gruen faerben.
    """
    with pytest.raises(_ReachedService):
        client.post(path, json=body)
