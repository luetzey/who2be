"""Integrationstest fuer die inhaltliche Suche (ADR-0037, Track 2).

`GET /v1/workspaces/{ws}/search` findet ueber die AKTIVE Version, rangsortiert,
und respektiert den Typ-Filter. Owner-JWT (unrestricted) ⇒ kein Read-Scoping.

Das agent-gebundene Read-Scoping (ADR-0046) wird hier gegen die echte Query
belegt: die Unit-Tests in `test_search_service.py` pruefen die Service-Logik
gegen ein Fake-Repo, aber nicht das SQL-Praedikat `e.id = ANY($4::uuid[])`.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

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


def _playbook_body(name: str, description: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": description,
            "body": "1. Step.",
            "type": "workflow",
            "tags": [],
            "triggers": None,
        },
    }


def _activate(client: TestClient, base: str, pid: str, auth: dict[str, str]) -> None:
    """Draft v1 → review → active (Owner ist admin)."""
    for to in ("review", "active"):
        r = client.post(f"{base}/{pid}/versions/1/transition", json={"to": to}, headers=auth)
        assert r.status_code in (200, 201), r.text


@pytest.mark.integration
def test_search_finds_active_playbook_by_content(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"
    sbase = f"/v1/workspaces/{ws}/search"

    try:
        with TestClient(app) as client:
            hit = client.post(
                pbase, json=_playbook_body("Reklamation", "Umgang mit Beschwerden"), headers=auth
            ).json()["id"]
            _activate(client, pbase, hit, auth)
            # Ein zweites, nicht aktiviertes Playbook (bleibt Draft → unsichtbar).
            client.post(
                pbase, json=_playbook_body("Versand", "Reklamation im Titel-Draft"), headers=auth
            )

            # Volltext ueber Name/Inhalt der aktiven Version.
            res = client.get(sbase, params={"q": "beschwerden"}, headers=auth)
            assert res.status_code == 200, res.text
            body = res.json()
            assert [h["id"] for h in body] == [hit]
            assert body[0]["type"] == "playbook"
            # WP5 (ADR-0045): Treffer tragen die Entity-Sprache als Metadatum
            # (Playbook ohne explizites `locale` -> Workspace-Default 'de').
            assert body[0]["locale"] == "de"

            # Typ-Filter persona → kein Playbook-Treffer.
            res2 = client.get(sbase, params={"q": "beschwerden", "types": "persona"}, headers=auth)
            assert res2.json() == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_search_finds_active_external_tool_by_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP-3: Volltext ueber Name + Content der aktiven ExternalTool-Version."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    tbase = f"/v1/workspaces/{ws}/external_tools"
    sbase = f"/v1/workspaces/{ws}/search"

    try:
        with TestClient(app) as client:
            body = {
                "name": "Todoist",
                "content": {
                    "display_name": "Todoist",
                    "usage_notes": "Fuer Aufgabenverwaltung im Alltag.",
                    "tags": [],
                },
            }
            tid = client.post(tbase, json=body, headers=auth).json()["id"]
            for to in ("review", "active"):
                r = client.post(
                    f"{tbase}/{tid}/versions/1/transition", json={"to": to}, headers=auth
                )
                assert r.status_code in (200, 201), r.text

            res = client.get(sbase, params={"q": "aufgabenverwaltung"}, headers=auth)
            assert res.status_code == 200, res.text
            hits = res.json()
            assert [h["id"] for h in hits] == [tid]
            assert hits[0]["type"] == "external_tool"

            # Default (kein types-Filter) findet es ebenfalls.
            res_default = client.get(sbase, params={"q": "todoist"}, headers=auth)
            assert tid in {h["id"] for h in res_default.json()}

            # types=persona blendet es aus.
            res_persona = client.get(
                sbase, params={"q": "aufgabenverwaltung", "types": "persona"}, headers=auth
            )
            assert res_persona.json() == []
    finally:
        cleanup_workspaces([owner])


def _persona_body(description: str) -> dict[str, object]:
    return {
        "name": "Scope-Persona",
        "content": {
            "description": description,
            "system_prompt": "Be precise.",
            "traits": ["thorough"],
            "content": {
                "description": description,
                "blocks": [
                    {
                        "id": "b1",
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description, "styles": {}}],
                    }
                ],
            },
        },
    }


@pytest.mark.integration
def test_assigned_scope_is_applied_before_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-0037 §47 / ADR-0046: Scoping als Praedikat, nicht als Nachfilter.

    Vier Playbooks matchen die Query; nur das zuletzt angelegte ist dem Agenten
    zugewiesen. Mit `limit=2` liegt es garantiert ausserhalb der globalen Top-k.
    Die frueher nachgelagerte Filterung lieferte hier `[]`.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"
    pbase = f"{prefix}/playbooks"

    try:
        with TestClient(app) as client:
            # Vier aktive Playbooks, alle mit demselben Suchbegriff im Inhalt.
            ids: list[str] = []
            for i in range(4):
                pid = client.post(
                    pbase,
                    json=_playbook_body(f"Reklamation {i}", "Umgang mit Beschwerden"),
                    headers=auth,
                ).json()["id"]
                _activate(client, pbase, pid, auth)
                ids.append(pid)
            assigned = ids[-1]

            # Persona mit genau einem zugewiesenen Playbook.
            persona_id = client.post(
                f"{prefix}/personas", json=_persona_body("Scope-Test"), headers=auth
            ).json()["id"]
            link = client.put(
                f"{prefix}/personas/{persona_id}/playbooks",
                json={"playbook_ids": [assigned]},
                headers=auth,
            )
            assert link.status_code == 200, link.text

            # Agent-gebundener Token mit `assigned`-Scope.
            agent = client.post(
                f"{prefix}/agents",
                json={
                    "name": "Scope-Agent",
                    "persona_id": persona_id,
                    "tool_policy": {"playbook_read": "assigned", "resource_read": "assigned"},
                },
                headers=auth,
            )
            assert agent.status_code == 201, agent.text
            token = client.post(
                f"{prefix}/tokens",
                json={"name": "scope", "agent_id": agent.json()["id"]},
                headers=auth,
            )
            assert token.status_code == 201, token.text
            agent_auth = {"Authorization": f"Bearer {token.json()['token']}"}

            res = client.get(
                f"{prefix}/search",
                params={"q": "beschwerden", "types": "playbook", "limit": 2},
                headers=agent_auth,
            )
            assert res.status_code == 200, res.text
            assert [h["id"] for h in res.json()] == [assigned]

            # Gegenprobe: der Owner (unrestricted) sieht die globalen Top-2.
            res_owner = client.get(
                f"{prefix}/search",
                params={"q": "beschwerden", "types": "playbook", "limit": 2},
                headers=auth,
            )
            assert len(res_owner.json()) == 2
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_none_scope_on_one_type_does_not_block_other_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`playbook_read=none` darf eine reine Persona-Suche nicht mit 403 abbrechen."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            persona_id = client.post(
                f"{prefix}/personas", json=_persona_body("Eskalation"), headers=auth
            ).json()["id"]
            for to in ("review", "active"):
                r = client.post(
                    f"{prefix}/personas/{persona_id}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )
                assert r.status_code in (200, 201), r.text

            agent = client.post(
                f"{prefix}/agents",
                json={
                    "name": "Nur-Persona",
                    "persona_id": persona_id,
                    "tool_policy": {"playbook_read": "none", "resource_read": "none"},
                },
                headers=auth,
            )
            assert agent.status_code == 201, agent.text
            token = client.post(
                f"{prefix}/tokens",
                json={"name": "nur-persona", "agent_id": agent.json()["id"]},
                headers=auth,
            )
            agent_auth = {"Authorization": f"Bearer {token.json()['token']}"}

            res = client.get(
                f"{prefix}/search",
                params={"q": "eskalation", "types": "persona"},
                headers=agent_auth,
            )
            assert res.status_code == 200, res.text
            assert [h["id"] for h in res.json()] == [persona_id]
    finally:
        cleanup_workspaces([owner])
