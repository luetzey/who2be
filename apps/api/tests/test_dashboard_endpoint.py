"""Integrationstest fuers Workspace-Dashboard (Phase 2.1b-B).

Drei Cases: leerer Workspace, gemischte Status-Verteilung mit
Status-History-Eintraegen und Cross-Workspace-Isolation. Der zweite Case
fuettert `persona_version.status`/`playbook_version.status` und
`status_history` direkt per SQL — der Transition-Endpoint kommt erst in
Prompt A. Der dritte Case prueft zusaetzlich die "Activity bleibt leer ohne
History"-Variante explizit.

Laeuft nur mit erreichbarer Datenbank; ohne DB wird der Test uebersprungen.
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


def _persona_body(description: str) -> dict[str, object]:
    return {
        "name": "QA-Bot",
        "content": {
            "description": description,
            "system_prompt": "Be precise.",
            "traits": ["thorough"],
        },
    }


def _playbook_body(name: str, description: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": description,
            "body": "1. Step.",
            "type": "workflow",
            "tags": ["alpha"],
            "triggers": "trigger",
        },
    }


def _seed_version_status(
    table: str, entity_column: str, entity_id: UUID, version: int, status: str
) -> None:
    """Setzt `status` einer existierenden Version. Die DB-Constraints (partial
    unique indices) bleiben aktiv — Tests muessen Konfliktstati vermeiden."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                f"UPDATE {table} SET status = $1 WHERE {entity_column} = $2 AND version = $3",
                status,
                entity_id,
                version,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _insert_history(
    entity_type: str,
    entity_id: UUID,
    from_status: str | None,
    to_status: str,
    changed_by: UUID,
) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO status_history "
                "(entity_type, entity_id, from_status, to_status, changed_by) "
                "VALUES ($1, $2, $3, $4, $5)",
                entity_type,
                entity_id,
                from_status,
                to_status,
                changed_by,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


@pytest.mark.integration
def test_dashboard_empty_workspace_returns_zeroes_and_empty_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            resp = client.get(f"/v1/workspaces/{ws}/dashboard", headers=auth)
            assert resp.status_code == 200
            body = resp.json()
            assert body["kpis"] == {
                "active_personas": 0,
                "active_playbooks": 0,
                "active_resources": 0,
                "pending_reviews": 0,
            }
            assert body["activity"] == []
            assert body["status_distribution"]["persona"] == {
                "draft": 0,
                "review": 0,
                "active": 0,
                "inactive": 0,
            }
            assert body["status_distribution"]["playbook"] == {
                "draft": 0,
                "review": 0,
                "active": 0,
                "inactive": 0,
            }
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_dashboard_aggregates_status_and_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    persona_base = f"/v1/workspaces/{ws}/personas"
    playbook_base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            # Persona "A": v1 (Backfill -> active), Update auf v2.
            # Migration 0011 setzt current_version auf 'active', alle anderen
            # auf 'inactive' — neu erstellte Versionen erben den Default
            # 'inactive'. Wir lassen das v1 als active stehen und schieben v2
            # nach 'review', um einen Pending-Review zu erzeugen.
            persona_a = client.post(persona_base, json=_persona_body("v1"), headers=auth).json()
            client.put(
                f"{persona_base}/{persona_a['id']}",
                json=_persona_body("v2"),
                headers=auth,
            )
            _seed_version_status(
                "persona_version", "persona_id", UUID(persona_a["id"]), 2, "review"
            )

            # Persona "B": nur v1 (active via Backfill — wir lassen Default).
            persona_b = client.post(
                persona_base, json=_persona_body("only-v1"), headers=auth
            ).json()
            # Neu erzeugte Personas haben v1 auf Default 'inactive' (der
            # Trigger setzt 'active' nur fuer Backfill in 0011). Wir promoten
            # explizit auf 'active', damit die KPI > 0 ist.
            _seed_version_status(
                "persona_version", "persona_id", UUID(persona_b["id"]), 1, "active"
            )

            # Playbook "P": v1 active, v2 draft.
            playbook = client.post(
                playbook_base, json=_playbook_body("Onboard", "v1"), headers=auth
            ).json()
            client.put(
                f"{playbook_base}/{playbook['id']}",
                json=_playbook_body("Onboard", "v2"),
                headers=auth,
            )
            _seed_version_status(
                "playbook_version", "playbook_id", UUID(playbook["id"]), 1, "active"
            )
            _seed_version_status(
                "playbook_version", "playbook_id", UUID(playbook["id"]), 2, "draft"
            )

            # Activity: zwei Eintraege, neuester zuerst.
            _insert_history("persona", UUID(persona_a["id"]), "draft", "review", owner)
            _insert_history("playbook", UUID(playbook["id"]), "draft", "active", owner)

            resp = client.get(f"/v1/workspaces/{ws}/dashboard", headers=auth)
            assert resp.status_code == 200
            body = resp.json()

            assert body["kpis"]["active_personas"] == 1  # Persona B
            assert body["kpis"]["active_playbooks"] == 1  # Playbook P v1
            assert body["kpis"]["pending_reviews"] == 1  # Persona A v2

            persona_dist = body["status_distribution"]["persona"]
            assert persona_dist["active"] == 1
            assert persona_dist["review"] == 1
            # Persona A v1 ist nach UPDATE durch den API-Endpoint zwar nicht
            # mehr current — Status bleibt jedoch 'inactive' (Default), weil
            # `update` keine Status-Logik kennt. Macht insgesamt 1 inactive.
            assert persona_dist["inactive"] == 1
            assert persona_dist["draft"] == 0

            playbook_dist = body["status_distribution"]["playbook"]
            assert playbook_dist["active"] == 1
            assert playbook_dist["draft"] == 1

            activity = body["activity"]
            assert len(activity) == 2
            # ORDER BY changed_at DESC — letzter Insert (playbook) ist erster.
            assert activity[0]["entity_type"] == "playbook"
            assert activity[0]["entity_id"] == playbook["id"]
            assert activity[0]["to_status"] == "active"
            assert activity[1]["entity_type"] == "persona"
            assert activity[1]["entity_id"] == persona_a["id"]
            assert activity[1]["to_status"] == "review"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_dashboard_isolates_other_workspace_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner_a = fresh_user_id()
    owner_b = fresh_user_id()
    ws_a = setup_workspace(owner_a)
    ws_b = setup_workspace(owner_b)
    auth_a = _auth(owner_a)
    auth_b = _auth(owner_b)

    try:
        with TestClient(app) as client:
            # Workspace B: eine active Persona + ein History-Eintrag.
            persona_b = client.post(
                f"/v1/workspaces/{ws_b}/personas",
                json=_persona_body("ws-b"),
                headers=auth_b,
            ).json()
            _seed_version_status(
                "persona_version", "persona_id", UUID(persona_b["id"]), 1, "active"
            )
            _insert_history("persona", UUID(persona_b["id"]), "draft", "active", owner_b)

            # Workspace A bleibt leer — Activity-Empty-Case ist hier
            # explizit Teil der Isolation: B hat eine Activity, A muss
            # trotzdem `[]` sehen.
            dash_a = client.get(f"/v1/workspaces/{ws_a}/dashboard", headers=auth_a).json()
            assert dash_a["kpis"] == {
                "active_personas": 0,
                "active_playbooks": 0,
                "active_resources": 0,
                "pending_reviews": 0,
            }
            assert dash_a["status_distribution"]["persona"]["active"] == 0
            assert dash_a["activity"] == []

            # Sanity-Check: Workspace B sieht die eigenen Daten — sonst
            # koennte die Isolation auch "alles leer" sein.
            dash_b = client.get(f"/v1/workspaces/{ws_b}/dashboard", headers=auth_b).json()
            assert dash_b["kpis"]["active_personas"] == 1
            assert len(dash_b["activity"]) == 1
            assert dash_b["activity"][0]["entity_id"] == persona_b["id"]

            # Cross-Workspace-Auth: User A darf B's Dashboard nicht abrufen.
            forbidden = client.get(f"/v1/workspaces/{ws_b}/dashboard", headers=auth_a)
            assert forbidden.status_code == 403
    finally:
        cleanup_workspaces([owner_a, owner_b])
