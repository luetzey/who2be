"""Waechter: agent-gebundene Tokens fuehren keine Workspace-Administration aus.

**Warum dieser Test existiert.** Eine Messung gegen einen laufenden Stack (Karte
`t_ea83420c`, Review-Befund `t_06b1d160`) hat gezeigt: ein agent-gebundener Token
mit Rollen-Snapshot `admin` und einer Policy *ohne* `agent_write` kam an **allen
sieben** `require_role(ctx, WorkspaceRole.admin)`-Stellen der workspace-scoped
Router durch — `POST /invitations` legte eine Admin-Einladung samt Klartext-Token
an, `PATCH /v1/workspaces/{ws}` aenderte den Namen (in der DB verifiziert). Das
ist derselbe Umweg, den `token_service` seit je verbaut: ein eingeschraenkter
Agent, der sich selbst Rechte beschafft und damit seine Pro-Agent-Policy komplett
umgeht.

**Die Falle, an der ein zu schwacher Test gruen bleibt.** Drei der sieben Routen
antworteten in der Messung mit 404/409 (`workspace_member_not_found`,
`last_workspace_undeletable`) — das ist **keine** Abwehr: das
Autorisierungs-Gate war da schon durchlaufen, nur das Zielobjekt fehlte. Mit
echter `user_id` bzw. in einer Org mit zwei Workspaces haetten diese Aufrufe
gegriffen. Dieser Test fordert deshalb ausdruecklich **403** und den `reason` —
nicht „nicht 2xx".

**Ohne DB, mit Absicht** (Muster von `test_entity_quota_duplicate_routes.py`):
`get_current_workspace` und `get_pool` kommen per `dependency_overrides`, der
Fake-Pool beantwortet keine Frage, sondern wirft `_ReachedService`. Damit messen
die Tests nur das Gate, nicht die Persistenz — und die Gegenprobe bekommt ein
positives Signal: die Exception IST die Zusicherung „das Gate hat
durchgelassen".

**Tabellengetrieben, damit eine neu hinzugefuegte Admin-Route nicht
stillschweigend ungeschuetzt bleibt:** die sieben Zeilen in `_ADMIN_ROUTES` sind
das Inventar. Wer eine achte `require_role(ctx, admin)`-Route in einem
workspace-scoped Router anlegt, traegt sie hier ein.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from who2be_api.core.db import get_pool
from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.main import app
from who2be_models import AgentToolPolicy, WorkspaceRole

_WORKSPACE_ID = uuid4()
_GHOST_USER = uuid4()
_GHOST_INVITATION = uuid4()
_PREFIX = f"/v1/workspaces/{_WORKSPACE_ID}"

# Die sieben `require_role(ctx, WorkspaceRole.admin)`-Stellen der Klasse 1
# (workspace-scoped Router mit `WorkspaceContext`). `POST
# /v1/invitations/{token}/accept` gehoert bewusst NICHT dazu: anderer Pfad
# (`get_current_principal`, kein `WorkspaceContext`).
_ADMIN_ROUTES: list[tuple[str, str, str, dict[str, Any] | None]] = [
    (
        "creates invitation",
        "post",
        f"{_PREFIX}/invitations",
        {"email": "x@example.com", "role": "admin"},
    ),
    ("lists invitations", "get", f"{_PREFIX}/invitations", None),
    ("revokes invitation", "delete", f"{_PREFIX}/invitations/{_GHOST_INVITATION}", None),
    ("updates member role", "patch", f"{_PREFIX}/members/{_GHOST_USER}", {"role": "admin"}),
    ("removes member", "delete", f"{_PREFIX}/members/{_GHOST_USER}", None),
    ("updates workspace", "patch", f"/v1/workspaces/{_WORKSPACE_ID}", {"name": "Umbenannt"}),
    ("deletes workspace", "delete", f"/v1/workspaces/{_WORKSPACE_ID}", None),
]


class _ReachedService(RuntimeError):
    """Das Gate hat durchgelassen und der Request ist im Service angekommen."""


class _FakePool:
    """Jeder DB-Zugriff heisst: das Gate hat schon durchgelassen."""

    async def fetchval(self, *_args: object, **_kwargs: object) -> object:
        raise _ReachedService

    async def fetchrow(self, *_args: object, **_kwargs: object) -> object:
        raise _ReachedService

    async def fetch(self, *_args: object, **_kwargs: object) -> object:
        raise _ReachedService

    async def execute(self, *_args: object, **_kwargs: object) -> object:
        raise _ReachedService

    def acquire(self) -> object:
        raise _ReachedService


def _ctx(
    *,
    tool_policy: AgentToolPolicy | None,
    agent_id: UUID | None,
    is_api_token: bool = True,
    aal: str | None = None,
) -> WorkspaceContext:
    """Admin-Kontext; die Agent-Bindung ist der einzige Freiheitsgrad.

    `role=admin` in allen Faellen — der Befund ist ja gerade, dass die
    Rollen-Pruefung allein nicht genuegt. `aal` bleibt im Token-Pfad `None`
    (`require_aal2` exemptet Maschinen-Tokens), im JWT-Pfad `aal2`.
    """
    return WorkspaceContext(
        workspace_id=_WORKSPACE_ID,
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=is_api_token,
        aal=aal,
        agent_id=agent_id,
        tool_policy=tool_policy,
    )


def _client(ctx: WorkspaceContext) -> Iterator[TestClient]:
    app.dependency_overrides[get_current_workspace] = lambda: ctx
    app.dependency_overrides[get_pool] = _FakePool
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_workspace, None)
        app.dependency_overrides.pop(get_pool, None)


# Die Policy des gemessenen Befunds: Schreibrechte auf Personas/Feedback/
# Versionen, aber ausdruecklich KEIN `agent_write` — genau der eingeschraenkte
# Agent, der sich ueber die Admin-Routen alles beschaffen konnte.
_MEASURED_POLICY = AgentToolPolicy(
    persona_write=True, feedback_write=True, promote_retire=True, agent_write=False
)


@pytest.fixture
def agent_bound_client() -> Iterator[TestClient]:
    """Agent-gebundener Token: Policy UND `agent_id` gesetzt (der Normalfall)."""
    yield from _client(_ctx(tool_policy=_MEASURED_POLICY, agent_id=uuid4()))


@pytest.fixture
def agent_bound_without_policy_client() -> Iterator[TestClient]:
    """Agent-Bindung ohne geladene Policy — der Race mit Agent-Delete.

    `_load_agent_tool_policy` (`core/security.py`) faellt defensiv auf `None`
    zurueck, wenn der gebundene Agent zwischen Token-Auth und Policy-Load
    verschwindet. Ein Gate, das nur `tool_policy` prueft, waere in diesem
    Fenster offen; deshalb ist `agent_id` der zweite Indikator (dasselbe
    Muster wie `memory_service._require_human`).
    """
    yield from _client(_ctx(tool_policy=None, agent_id=uuid4()))


@pytest.fixture
def unbound_token_client() -> Iterator[TestClient]:
    """Ungebundener Admin-API-Token — muss weiter durchkommen."""
    yield from _client(_ctx(tool_policy=None, agent_id=None))


@pytest.fixture
def human_client() -> Iterator[TestClient]:
    """Mensch/JWT mit aal2 — muss weiter durchkommen (Web-UI)."""
    yield from _client(_ctx(tool_policy=None, agent_id=None, is_api_token=False, aal="aal2"))


def _call(client: TestClient, method: str, path: str, body: dict[str, Any] | None) -> Any:  # noqa: ANN401
    return client.request(method.upper(), path, json=body)


# --- 1. Das Loch: agent-gebunden ⇒ 403 auf allen sieben Routen ---------------


@pytest.mark.parametrize(
    ("label", "method", "path", "body"), _ADMIN_ROUTES, ids=[r[0] for r in _ADMIN_ROUTES]
)
def test_agent_bound_token_is_denied(
    agent_bound_client: TestClient, label: str, method: str, path: str, body: dict[str, Any] | None
) -> None:
    """403 — nicht 404, nicht 409, nicht „irgendwas ausser 2xx"."""
    res = _call(agent_bound_client, method, path, body)
    assert res.status_code == 403, (
        f"{label} ({method.upper()} {path}): {res.status_code} {res.text}"
    )
    assert res.json()["reason"] == "workspace_administration_forbidden", res.text


@pytest.mark.parametrize(
    ("label", "method", "path", "body"), _ADMIN_ROUTES, ids=[r[0] for r in _ADMIN_ROUTES]
)
def test_agent_bound_without_policy_is_denied(
    agent_bound_without_policy_client: TestClient,
    label: str,
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    """Auch ohne geladene Policy greift das Gate (zweiter Indikator `agent_id`)."""
    res = _call(agent_bound_without_policy_client, method, path, body)
    assert res.status_code == 403, (
        f"{label} ({method.upper()} {path}): {res.status_code} {res.text}"
    )
    assert res.json()["reason"] == "workspace_administration_forbidden", res.text


def test_denial_is_a_gate_problem_json_answer(agent_bound_client: TestClient) -> None:
    """Die Ablehnung ist eine Gate-Antwort (RFC 7807, `actionable_by: human`).

    `human` ist richtig: der Agent kann es nicht selbst beheben — der
    Workspace-Besitzer kann einen ungebundenen Token verwenden.
    """
    res = agent_bound_client.get(f"{_PREFIX}/invitations")
    assert res.status_code == 403
    assert res.headers["content-type"].startswith("application/problem+json")
    body = res.json()
    assert body["reason"] == "workspace_administration_forbidden"
    assert body["actionable_by"] == "human"


# --- 2. Gegenprobe: der Fix bricht die Bestandspfade nicht ------------------


@pytest.mark.parametrize(
    ("label", "method", "path", "body"), _ADMIN_ROUTES, ids=[r[0] for r in _ADMIN_ROUTES]
)
def test_unbound_admin_token_still_passes(
    unbound_token_client: TestClient,
    label: str,
    method: str,
    path: str,
    body: dict[str, Any] | None,
) -> None:
    """Ohne Gegenprobe waere ein Gate, das *immer* blockt, oben ebenso gruen."""
    with pytest.raises(_ReachedService):
        _call(unbound_token_client, method, path, body)


@pytest.mark.parametrize(
    ("label", "method", "path", "body"), _ADMIN_ROUTES, ids=[r[0] for r in _ADMIN_ROUTES]
)
def test_human_jwt_still_passes(
    human_client: TestClient, label: str, method: str, path: str, body: dict[str, Any] | None
) -> None:
    """Die Web-UI (Mensch/JWT, aal2) bleibt unberuehrt."""
    with pytest.raises(_ReachedService):
        _call(human_client, method, path, body)
