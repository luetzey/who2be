"""Integrationstests fuer `GET /agents/{agent_id}/work-areas` (Navigation A4).

Kritische Invarianten (Plan 2026-10-10-0500, PM-Weiche W1):
- Antwort je Grant-Area des Agenten: Stufe des Agenten, `owner` nur fuer
  seine private Area, `agent_count` = Zahl der Grants an der Area.
- Sichtbarkeit wie `GET /work-areas`: editor+ sieht auch die private Area,
  viewer nur geteilte.
- Nur Menschen: agent-gebundene Tokens 403 (auch fuer den eigenen Agenten),
  ungebundene Maschinen-Tokens 403 ueber die Router-Sperre.
- Unbekannter oder workspace-fremder Agent: 404 `agent_not_found`.
- Unter der Laufzeitrolle `who2be_app` (RLS) dasselbe Ergebnis.
"""

from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from test_rls_control_plane_api import app_role_client  # type: ignore[import-not-found]

from who2be_api.core.security import WorkspaceContext, get_current_workspace
from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute, grant, shared_area
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("patched_jwt_secret", "migrated_db"),
]

__all__ = ["app_role_client"]


def _add_viewer(workspace_id: UUID, user_id: UUID) -> None:
    db_execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'viewer')",
        workspace_id,
        user_id,
    )


def _setup(client: TestClient, prefix: str, auth: dict[str, str]) -> dict[str, str]:
    """Agent A (privat + 2 geteilte), Agent B (teilt eine Area mit A).

    Liefert die IDs und den Header des agent-gebundenen Tokens von A.
    """
    a_id, a_tok = agent_token(client, prefix, "Alpha", {"workarea_write": True}, auth)
    b_id, b_tok = agent_token(client, prefix, "Beta", {"workarea_write": True}, auth)
    # Private Areas entstehen erst beim ersten Agent-Zugriff.
    assert client.get(f"{prefix}/work-areas", headers=a_tok).status_code == 200
    assert client.get(f"{prefix}/work-areas", headers=b_tok).status_code == 200
    team = shared_area(client, prefix, auth, "Team")
    solo = shared_area(client, prefix, auth, "Solo")
    shared_area(client, prefix, auth, "Fremd")  # ohne Grant fuer A
    grant(client, prefix, auth, team, a_id, "write")
    grant(client, prefix, auth, team, b_id, "read")
    grant(client, prefix, auth, solo, a_id, "read")
    return {"a": a_id, "b": b_id, "team": team, "solo": solo, "a_tok": a_tok["Authorization"]}


def test_arbeitsbereiche_je_agent_rollen_und_felder(make_auth_headers: AuthFactory) -> None:
    owner, viewer = fresh_user_id(), fresh_user_id()
    ws = setup_workspace(owner)
    _add_viewer(ws, viewer)
    auth, viewer_auth = make_auth_headers(owner), make_auth_headers(viewer)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            ids = _setup(client, prefix, auth)
            url = f"{prefix}/agents/{ids['a']}/work-areas"

            res = client.get(url, headers=auth)
            assert res.status_code == 200, res.text
            rows = [
                (r["name"], r["scope"], r["level"], r["owner"], r["agent_count"])
                for r in res.json()
            ]
            # privat zuerst, dann geteilt nach Name; "Fremd" fehlt (kein Grant).
            assert rows == [
                ("Alpha", "private", "write", True, 1),
                ("Solo", "shared", "read", False, 1),
                ("Team", "shared", "write", False, 2),
            ]
            assert {r["id"] for r in res.json()} >= {ids["team"], ids["solo"]}

            # Agent B: Team (read, 2 Agenten) + eigene private Area.
            b_rows = client.get(f"{prefix}/agents/{ids['b']}/work-areas", headers=auth).json()
            assert [(r["name"], r["level"], r["agent_count"]) for r in b_rows] == [
                ("Beta", "write", 1),
                ("Team", "read", 2),
            ]

            # viewer: nur geteilte Bereiche, die private Area bleibt verborgen.
            v = client.get(url, headers=viewer_auth)
            assert v.status_code == 200, v.text
            assert [r["name"] for r in v.json()] == ["Solo", "Team"]

            # Agent ohne Zugriff bisher: leere Liste, keine Auto-Anlage.
            c_id, _ = agent_token(client, prefix, "Gamma", {}, auth)
            empty = client.get(f"{prefix}/agents/{c_id}/work-areas", headers=auth)
            assert empty.status_code == 200, empty.text
            assert empty.json() == []
            again = client.get(f"{prefix}/agents/{c_id}/work-areas", headers=auth)
            assert again.json() == []
    finally:
        cleanup_workspaces([owner, viewer])


def test_nur_menschen_und_404(make_auth_headers: AuthFactory) -> None:
    owner, stranger = fresh_user_id(), fresh_user_id()
    ws, foreign = setup_workspace(owner), setup_workspace(stranger)
    auth, foreign_auth = make_auth_headers(owner), make_auth_headers(stranger)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            ids = _setup(client, prefix, auth)
            url = f"{prefix}/agents/{ids['a']}/work-areas"

            # Agent-gebundener Token: 403, auch fuer den eigenen Agenten.
            own = client.get(url, headers={"Authorization": ids["a_tok"]})
            assert own.status_code == 403, own.text
            assert own.json()["reason"] == "missing_capability"

            # Ungebundener Maschinen-Kontext: Router-Sperre. Ein solcher Token
            # laesst sich nicht mehr ausstellen (DB-CHECK 0048), deshalb per
            # Override wie `test_m1_gate_is_wired_to_every_workarea_route`.
            unbound_ctx = WorkspaceContext(
                workspace_id=ws,
                user_id=owner,
                role=WorkspaceRole.admin,
                is_api_token=True,
                agent_id=None,
                tool_policy=None,
            )
            app.dependency_overrides[get_current_workspace] = lambda: unbound_ctx
            try:
                unbound = client.get(url)
            finally:
                app.dependency_overrides.pop(get_current_workspace, None)
            assert unbound.status_code == 403, unbound.text
            assert unbound.json()["reason"] == "missing_capability"
            assert "agent-gebundenen Token" in unbound.json()["detail"]

            # Unbekannter Agent → 404.
            ghost = "00000000-0000-0000-0000-000000000000"
            missing = client.get(f"{prefix}/agents/{ghost}/work-areas", headers=auth)
            assert missing.status_code == 404, missing.text
            assert missing.json()["reason"] == "agent_not_found"

            # Workspace-fremder Agent im eigenen Workspace → 404, kein Leak.
            other_agent, _ = agent_token(
                client, f"/v1/workspaces/{foreign}", "Fremdagent", {}, foreign_auth
            )
            cross = client.get(f"{prefix}/agents/{other_agent}/work-areas", headers=auth)
            assert cross.status_code == 404, cross.text
            assert cross.json()["reason"] == "agent_not_found"

            # Fremder Workspace im Pfad → kein Zugriff.
            alien = client.get(
                f"/v1/workspaces/{foreign}/agents/{ids['a']}/work-areas", headers=auth
            )
            assert alien.status_code in (403, 404), alien.text
    finally:
        cleanup_workspaces([owner, stranger])


def test_unter_laufzeitrolle_who2be_app(
    app_role_client: TestClient, make_auth_headers: AuthFactory
) -> None:
    """RLS: unter `who2be_app` dieselbe Antwort; ein zweiter Workspace sieht
    den Agenten nicht (404)."""
    owner, stranger = fresh_user_id(), fresh_user_id()
    ws, foreign = setup_workspace(owner), setup_workspace(stranger)
    auth, foreign_auth = make_auth_headers(owner), make_auth_headers(stranger)
    prefix = f"/v1/workspaces/{ws}"
    try:
        ids = _setup(app_role_client, prefix, auth)
        res = app_role_client.get(f"{prefix}/agents/{ids['a']}/work-areas", headers=auth)
        assert res.status_code == 200, res.text
        assert [(r["name"], r["agent_count"]) for r in res.json()] == [
            ("Alpha", 1),
            ("Solo", 1),
            ("Team", 2),
        ]
        other = app_role_client.get(
            f"/v1/workspaces/{foreign}/agents/{ids['a']}/work-areas", headers=foreign_auth
        )
        assert other.status_code == 404, other.text
    finally:
        cleanup_workspaces([owner, stranger])
