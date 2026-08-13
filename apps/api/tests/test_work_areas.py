"""Integrationstests fuer WorkArea-Areas + Grants (ADR-0047, WP4).

Kritische Invarianten:
- Shared-Anlage: editor+ (viewer 403), Namens-Kollision → 409.
- Sichtbarkeit (User-Entscheidung 5): Mensch editor+ sieht ALLE Areas (auch
  private Agent-Areas — „privat" gilt gegenueber anderen AGENTEN), viewer nur
  shared, Agenten nur ihre Grant-Areas.
- Private Auto-Anlage beim ersten Agent-Zugriff (whoami/Liste) inkl.
  materialisiertem Owner-Grant.
- Grant-Verwaltung ist Menschen vorbehalten (Agent-Token → 403); private
  Areas sind nicht grantbar; unbekannte Ziele → 404.
- whoami traegt `work_areas` fuer agent-gebundene Tokens, `None` fuer Menschen.
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]


def _agent_token(
    client: TestClient, prefix: str, name: str, policy: dict[str, object], auth: dict[str, str]
) -> tuple[str, dict[str, str]]:
    agent = client.post(
        f"{prefix}/agents", json={"name": name, "tool_policy": policy}, headers=auth
    )
    assert agent.status_code == 201, agent.text
    agent_id = agent.json()["id"]
    token = client.post(f"{prefix}/tokens", json={"name": name, "agent_id": agent_id}, headers=auth)
    assert token.status_code == 201, token.text
    return agent_id, {"Authorization": f"Bearer {token.json()['token']}"}


def _add_member(workspace_id: UUID, user_id: UUID, role: str = "editor") -> None:
    """Fuegt dem Workspace ein Mitglied mit gegebener Rolle hinzu (Gate-Tests)."""
    import asyncio

    import asyncpg

    from who2be_api.core.config import get_settings

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, $3) "
                "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role",
                workspace_id,
                user_id,
                role,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _area(client: TestClient, prefix: str, auth: dict[str, str], name: str) -> Any:
    return client.post(f"{prefix}/work-areas", json={"name": name}, headers=auth)


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_shared_area_anlage_und_sichtbarkeit(make_auth_headers: AuthFactory) -> None:
    """Shared-Anlage (editor+, 409 bei Namens-Kollision, viewer 403); Mensch
    editor sieht private Agent-Areas, viewer nur shared, Agent seine Grants."""
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, role="viewer")
    auth = make_auth_headers(owner)
    viewer_auth = make_auth_headers(viewer)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            created = _area(client, prefix, auth, "Team-Recherche")
            assert created.status_code == 201, created.text
            body = created.json()
            assert body["scope"] == "shared"
            assert body["owner_agent_id"] is None
            shared_id = body["id"]

            # Namens-Kollision → 409 mit Taxonomie-Reason.
            duplicate = _area(client, prefix, auth, "Team-Recherche")
            assert duplicate.status_code == 409
            assert duplicate.json()["reason"] == "concurrent_conflict"

            # Viewer darf keine Areas anlegen.
            assert _area(client, prefix, viewer_auth, "Viewer-Area").status_code == 403

            # Agent-Zugriff (Liste) loest die private Auto-Anlage aus.
            agent_id, agent_tok = _agent_token(
                client, prefix, "wa-sicht", {"workarea_write": True}, auth
            )
            agent_areas = client.get(f"{prefix}/work-areas", headers=agent_tok)
            assert agent_areas.status_code == 200
            agent_view = agent_areas.json()
            assert [a["scope"] for a in agent_view] == ["private"]
            private_area = agent_view[0]
            assert private_area["owner_agent_id"] == agent_id
            assert private_area["name"] == "wa-sicht"
            # Auto-Anlage ist idempotent: zweiter Aufruf, gleiche Area.
            again = client.get(f"{prefix}/work-areas", headers=agent_tok).json()
            assert [a["id"] for a in again] == [private_area["id"]]

            # Mensch editor+ sieht ALLES — auch die private Agent-Area.
            owner_view = client.get(f"{prefix}/work-areas", headers=auth).json()
            assert {a["id"] for a in owner_view} == {shared_id, private_area["id"]}

            # Viewer sieht NUR shared.
            viewer_view = client.get(f"{prefix}/work-areas", headers=viewer_auth).json()
            assert [a["id"] for a in viewer_view] == [shared_id]

            # Agent ohne Grant sieht die shared Area nicht.
            assert shared_id not in {a["id"] for a in agent_view}
    finally:
        cleanup_workspaces([owner, viewer])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_grant_verwaltung_human_only(make_auth_headers: AuthFactory) -> None:
    """Grants vergibt nur der Mensch (editor+): Agent-Token → 403; private
    Areas sind nicht grantbar; unbekannte Ziele → 404; Upsert + Entzug."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            shared_id = _area(client, prefix, auth, "Grant-Area").json()["id"]
            agent_id, agent_tok = _agent_token(
                client, prefix, "wa-grant", {"workarea_write": True}, auth
            )
            grant_url = f"{prefix}/work-areas/{shared_id}/grants/{agent_id}"

            # Agent-Token darf keine Grants vergeben — auch nicht fuer sich selbst.
            self_grant = client.put(grant_url, json={"level": "write"}, headers=agent_tok)
            assert self_grant.status_code == 403
            assert self_grant.json()["reason"] == "missing_capability"

            # Mensch: Grant setzen + per Upsert hochstufen.
            granted = client.put(grant_url, json={"level": "read"}, headers=auth)
            assert granted.status_code == 200, granted.text
            assert granted.json()["level"] == "read"
            upgraded = client.put(grant_url, json={"level": "write"}, headers=auth)
            assert upgraded.status_code == 200
            assert upgraded.json()["level"] == "write"

            # Der Grant macht die shared Area fuer den Agenten sichtbar.
            agent_view = client.get(f"{prefix}/work-areas", headers=agent_tok).json()
            assert shared_id in {a["id"] for a in agent_view}

            # Private Areas sind nicht grantbar (auch nicht vom Menschen).
            private_id = next(
                a["id"]
                for a in client.get(f"{prefix}/work-areas", headers=auth).json()
                if a["scope"] == "private"
            )
            other_agent_id, _ = _agent_token(
                client, prefix, "wa-grant-2", {"workarea_write": True}, auth
            )
            private_grant = client.put(
                f"{prefix}/work-areas/{private_id}/grants/{other_agent_id}",
                json={"level": "read"},
                headers=auth,
            )
            assert private_grant.status_code == 403
            assert private_grant.json()["reason"] == "area_forbidden"

            # Unbekannte Ziele: Area bzw. Agent → 404.
            ghost = "00000000-0000-0000-0000-000000000000"
            assert (
                client.put(
                    f"{prefix}/work-areas/{ghost}/grants/{agent_id}",
                    json={"level": "read"},
                    headers=auth,
                ).status_code
                == 404
            )
            assert (
                client.put(
                    f"{prefix}/work-areas/{shared_id}/grants/{ghost}",
                    json={"level": "read"},
                    headers=auth,
                ).status_code
                == 404
            )

            # Entzug: 204, danach 404; Agent sieht die Area nicht mehr.
            assert client.delete(grant_url, headers=auth).status_code == 204
            assert client.delete(grant_url, headers=auth).status_code == 404
            assert client.delete(grant_url, headers=agent_tok).status_code == 403
            after = client.get(f"{prefix}/work-areas", headers=agent_tok).json()
            assert shared_id not in {a["id"] for a in after}
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_whoami_traegt_work_areas(make_auth_headers: AuthFactory) -> None:
    """whoami: agent-gebundener Token bekommt `work_areas` (inkl. privater
    Auto-Anlage BEIM whoami-Aufruf und Grant-Level); Mensch bekommt None."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            shared_id = _area(client, prefix, auth, "Whoami-Area").json()["id"]
            agent_id, agent_tok = _agent_token(
                client, prefix, "wa-whoami", {"workarea_write": True}, auth
            )
            grant = client.put(
                f"{prefix}/work-areas/{shared_id}/grants/{agent_id}",
                json={"level": "read"},
                headers=auth,
            )
            assert grant.status_code == 200, grant.text

            # Erster Kontakt des Agenten ueberhaupt: whoami legt die private
            # Area an und liefert beide Zuordnungen.
            who = client.get(f"{prefix}/whoami", headers=agent_tok)
            assert who.status_code == 200, who.text
            areas = who.json()["work_areas"]
            assert areas is not None
            by_scope = {a["scope"]: a for a in areas}
            assert by_scope["private"]["level"] == "write"
            assert by_scope["private"]["name"] == "wa-whoami"
            assert by_scope["shared"]["id"] == shared_id
            assert by_scope["shared"]["level"] == "read"

            # Mensch/JWT: keine Grant-Menge — `work_areas` ist null.
            human = client.get(f"{prefix}/whoami", headers=auth)
            assert human.status_code == 200
            assert human.json()["work_areas"] is None
    finally:
        cleanup_workspaces([owner])
