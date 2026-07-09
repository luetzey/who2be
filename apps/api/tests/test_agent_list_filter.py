"""Integrationstest fuer den `?agent=`-Listenfilter (WP-B).

Deckt die drei Listen ab: `GET .../personas?agent=` (genau die Persona des
Agenten), `GET .../playbooks?agent=` (zugewiesene Playbooks inkl. Composite-
Closure, kombinierbar mit `tag`) und `GET .../resources?agent=` (erreichbare
Resources inkl. Sub-Resource-Closure). Unbekannte/workspace-fremde Agenten
liefern 404. Laeuft nur mit erreichbarer Datenbank; ohne DB wird der Test
uebersprungen.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
        except (asyncpg.PostgresError, OSError):
            return False
        await conn.close()
        return True

    return asyncio.run(_check())


def _prepare_db() -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await apply_migrations(conn, MIGRATIONS_DIR)
        finally:
            await conn.close()

    asyncio.run(_run())


def _auth(owner_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _persona_body(name: str) -> dict[str, object]:
    return {"name": name, "content": {"description": "d", "system_prompt": "s"}}


def _playbook_body(name: str, tags: list[str]) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "body": "1. Step.",
            "type": "workflow",
            "tags": tags,
            "triggers": "test",
        },
    }


def _resource_body(name: str, tags: list[str]) -> dict[str, object]:
    return {"name": name, "content": {"description": "d", "blocks": [], "tags": tags}}


def _ids(items: list[dict[str, object]]) -> set[str]:
    return {str(item["id"]) for item in items}


class _World:
    """Ein Workspace mit Agent + zugewiesener Kette (Persona → Playbooks → Resources).

    Graph: Persona P1 (verknuepft mit Playbook A) + freie Persona P2; Playbook A
    komponiert Kind-Playbook B, Playbook C bleibt unverknuepft; A verlinkt
    Resource R1, R1 haelt Sub-Resource R2, R3 bleibt unverknuepft. Der Agent
    haengt an P1 — seine „zugewiesene" Sicht ist also {P1}, {A, B}, {R1, R2}.
    """

    def __init__(self, client: TestClient, ws: UUID, auth: dict[str, str]) -> None:
        base = f"/v1/workspaces/{ws}"
        self.persona = client.post(
            f"{base}/personas", json=_persona_body("Zugewiesen"), headers=auth
        ).json()["id"]
        self.other_persona = client.post(
            f"{base}/personas", json=_persona_body("Frei"), headers=auth
        ).json()["id"]

        self.pb_parent = client.post(
            f"{base}/playbooks", json=_playbook_body("Parent", ["zugewiesen"]), headers=auth
        ).json()["id"]
        self.pb_child = client.post(
            f"{base}/playbooks", json=_playbook_body("Kind", ["kind"]), headers=auth
        ).json()["id"]
        self.pb_free = client.post(
            f"{base}/playbooks", json=_playbook_body("Frei", ["frei"]), headers=auth
        ).json()["id"]
        composed = client.put(
            f"{base}/playbooks/{self.pb_parent}/composes",
            json={"child_ids": [self.pb_child]},
            headers=auth,
        )
        assert composed.status_code == 200, composed.text
        linked = client.put(
            f"{base}/personas/{self.persona}/playbooks",
            json={"playbook_ids": [self.pb_parent]},
            headers=auth,
        )
        assert linked.status_code == 200, linked.text

        self.res_linked = client.post(
            f"{base}/resources", json=_resource_body("Verlinkt", ["zugewiesen"]), headers=auth
        ).json()["id"]
        self.res_sub = client.post(
            f"{base}/resources", json=_resource_body("Sub", ["sub"]), headers=auth
        ).json()["id"]
        self.res_free = client.post(
            f"{base}/resources", json=_resource_body("Frei", ["frei"]), headers=auth
        ).json()["id"]
        res_link = client.put(
            f"{base}/playbooks/{self.pb_parent}/resource_links",
            json={
                "links": [{"resource_id": self.res_linked, "position": 0, "link_scope": "resource"}]
            },
            headers=auth,
        )
        assert res_link.status_code == 200, res_link.text
        sub_link = client.put(
            f"{base}/resources/{self.res_linked}/sub_resources",
            json={"links": [{"child_id": self.res_sub}]},
            headers=auth,
        )
        assert sub_link.status_code == 200, sub_link.text

        agent = client.post(
            f"{base}/agents",
            json={"name": "Scoped Agent", "persona_id": self.persona},
            headers=auth,
        )
        assert agent.status_code == 201, agent.text
        self.agent = agent.json()["id"]


@pytest.mark.integration
def test_personas_list_agent_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            world = _World(client, ws, auth)

            # Ungefiltert: beide Personae sichtbar.
            unfiltered = client.get(base, headers=auth)
            assert unfiltered.status_code == 200, unfiltered.text
            assert {world.persona, world.other_persona} <= _ids(unfiltered.json())

            # ?agent= liefert genau die Persona des Agenten.
            filtered = client.get(base, params={"agent": world.agent}, headers=auth)
            assert filtered.status_code == 200, filtered.text
            assert _ids(filtered.json()) == {world.persona}

            # Unbekannter Agent → 404.
            assert client.get(base, params={"agent": str(uuid4())}, headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbooks_list_agent_filter_with_composite_and_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            world = _World(client, ws, auth)

            # ?agent= liefert Parent UND Composite-Kind, nicht das freie Playbook.
            filtered = client.get(base, params={"agent": world.agent}, headers=auth)
            assert filtered.status_code == 200, filtered.text
            assert _ids(filtered.json()) == {world.pb_parent, world.pb_child}

            # Kombinierbar mit dem bestehenden Tag-Filter (Schnittmenge).
            by_tag = client.get(
                base, params={"agent": world.agent, "tag": "zugewiesen"}, headers=auth
            )
            assert _ids(by_tag.json()) == {world.pb_parent}
            assert (
                client.get(base, params={"agent": world.agent, "tag": "frei"}, headers=auth).json()
                == []
            )

            # Workspace-fremder Agent → 404 (kein Existenz-Orakel).
            foreign_agent = client.post(
                f"/v1/workspaces/{other_ws}/agents",
                json={"name": "Fremd"},
                headers=_auth(other),
            ).json()["id"]
            assert (
                client.get(base, params={"agent": foreign_agent}, headers=auth).status_code == 404
            )
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_resources_list_agent_filter_with_sub_resource_closure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    try:
        with TestClient(app) as client:
            world = _World(client, ws, auth)

            # ?agent= liefert die verlinkte Resource UND deren Sub-Resource.
            filtered = client.get(base, params={"agent": world.agent}, headers=auth)
            assert filtered.status_code == 200, filtered.text
            assert _ids(filtered.json()) == {world.res_linked, world.res_sub}

            # Kombinierbar mit dem bestehenden Tag-Filter (Schnittmenge).
            by_tag = client.get(base, params={"agent": world.agent, "tag": "sub"}, headers=auth)
            assert _ids(by_tag.json()) == {world.res_sub}

            # Unbekannter Agent → 404.
            assert client.get(base, params={"agent": str(uuid4())}, headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner])
