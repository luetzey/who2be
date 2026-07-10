"""Integrationstest fuers Workspace-Dashboard (Phase 2.1b-B + 3-Fix Track 1).

Cases:
- Leerer Workspace (KPIs/Distribution/Activity sauber leer).
- Gemischte Status-Verteilung plus Activity-Eintraege mit Mapping in das
  Frontend-DTO (`actor`, `entity_name`, `event`).
- Cross-Workspace-Isolation (Activity-leer + 403 fuer fremde Workspaces).
- `display_name`-Fallback-Kette (`raw_user_meta_data->>'name'`,
  Email-Local-Part, User-ID-Fallback).

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
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    seed_auth_user,
    setup_workspace,
)

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
def test_dashboard_seed_baseline_for_fresh_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein frischer Workspace ist NICHT leer: der Onboarding-Seed legt 1 aktive
    „Builder"-Persona + 5 aktive Builder-Playbooks an. Die KPIs/Distribution
    spiegeln genau diese Baseline; Aktivitaet bleibt leer (der Seed schreibt
    keine status_history). Aendert sich der Seed, gehoeren die Werte mit
    angepasst."""
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
                "active_personas": 1,
                "active_playbooks": 5,
                "active_resources": 0,
                "pending_reviews": 0,
            }
            assert body["activity"] == []
            empty_dist = {"draft": 0, "review": 0, "active": 0, "inactive": 0}
            assert body["status_distribution"]["persona"] == {**empty_dist, "active": 1}
            assert body["status_distribution"]["playbook"] == {**empty_dist, "active": 5}
            assert body["status_distribution"]["resource"] == empty_dist
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

    # display_name-Fallback-Kette: `raw_user_meta_data->>'name'` schlaegt
    # alles andere. Der Owner taucht hier mit beidem auf, damit die
    # Aktivitaeten in `body["activity"]` einen sprechenden Anzeigenamen
    # tragen.
    seed_auth_user(owner, email="qa-owner@example.com", name="QA Owner")

    try:
        with TestClient(app) as client:
            # Onboarding-Seed-Baseline (1 aktive Persona, 4 aktive Playbooks)
            # erfassen — die folgenden Assertions pruefen das Delta darauf.
            base = client.get(f"/v1/workspaces/{ws}/dashboard", headers=auth).json()
            base_kpi = base["kpis"]
            base_pd = base["status_distribution"]["persona"]
            base_pb = base["status_distribution"]["playbook"]

            # Persona "A": v1 inactive, v2 review.
            # Phase 3-0: neue v1 startet als Draft (Migration 0019). Damit
            # `PUT` v2 anlegen kann, seedet der Test v1 erst auf `inactive`
            # (kein Draft mehr) und re-seedet danach den gewuenschten Endstand.
            persona_a = client.post(persona_base, json=_persona_body("v1"), headers=auth).json()
            _seed_version_status(
                "persona_version", "persona_id", UUID(persona_a["id"]), 1, "inactive"
            )
            client.put(
                f"{persona_base}/{persona_a['id']}",
                json=_persona_body("v2"),
                headers=auth,
            )
            _seed_version_status(
                "persona_version", "persona_id", UUID(persona_a["id"]), 2, "review"
            )

            # Persona "B": nur v1 (manuell auf active gehoben).
            persona_b = client.post(
                persona_base, json=_persona_body("only-v1"), headers=auth
            ).json()
            _seed_version_status(
                "persona_version", "persona_id", UUID(persona_b["id"]), 1, "active"
            )

            # Playbook "P": v1 active, v2 draft.
            playbook = client.post(
                playbook_base, json=_playbook_body("Onboard", "v1"), headers=auth
            ).json()
            _seed_version_status(
                "playbook_version", "playbook_id", UUID(playbook["id"]), 1, "inactive"
            )
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
            _insert_history("playbook", UUID(playbook["id"]), "review", "active", owner)

            resp = client.get(f"/v1/workspaces/{ws}/dashboard", headers=auth)
            assert resp.status_code == 200
            body = resp.json()

            # Deltas auf die Seed-Baseline (Persona B aktiv; Playbook P v1 aktiv;
            # Persona A v2 in review).
            # KPIs leiten sich aus der (current-status-)Distribution ab. Persona B
            # ist current active → +1. Playbook P ist current DRAFT (v2 ueber der
            # aktiven v1) → zaehlt NICHT als aktiv; active_playbooks bleibt gleich.
            # Persona A ist current review → +1 pending_reviews.
            assert body["kpis"]["active_personas"] == base_kpi["active_personas"] + 1
            assert body["kpis"]["active_playbooks"] == base_kpi["active_playbooks"]
            assert body["kpis"]["pending_reviews"] == base_kpi["pending_reviews"] + 1

            # Die Distribution zaehlt jedes Aggregat GENAU EINMAL nach seinem
            # aktuellen (hoechste-Version-)Status — wie die Listen-Sicht.
            persona_dist = body["status_distribution"]["persona"]
            # Persona B (v1 active) → +1 active.
            assert persona_dist["active"] == base_pd["active"] + 1
            # Persona A: current ist v2 (review) → +1 review.
            assert persona_dist["review"] == base_pd["review"] + 1
            # Persona A v1 (inactive) ist eine ueberholte Alt-Version, NICHT
            # current → zaehlt nicht mehr in die Verteilung.
            assert persona_dist["inactive"] == base_pd["inactive"]
            assert persona_dist["draft"] == base_pd["draft"]

            playbook_dist = body["status_distribution"]["playbook"]
            # Playbook P: current ist v2 (draft) → +1 draft; die aktive v1 ist
            # nicht current, daher KEIN +1 active in der Verteilung (die KPI
            # `active_playbooks` zaehlt hingegen live-dienende Aggregate, s. o.).
            assert playbook_dist["active"] == base_pb["active"]
            assert playbook_dist["draft"] == base_pb["draft"] + 1

            activity = body["activity"]
            assert len(activity) == 2
            # ORDER BY changed_at DESC — letzter Insert (playbook) ist erster.
            first, second = activity[0], activity[1]
            assert first["entity_type"] == "playbook"
            assert first["entity_id"] == playbook["id"]
            assert first["entity_name"] == "Onboard"
            assert first["event"] == "promoted_to_active"
            assert first["actor"] == {
                "user_id": str(owner),
                "display_name": "QA Owner",
            }
            assert "ts" in first
            assert second["entity_type"] == "persona"
            assert second["entity_id"] == persona_a["id"]
            assert second["entity_name"] == "QA-Bot"
            assert second["event"] == "submitted_for_review"
            assert second["actor"]["display_name"] == "QA Owner"
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
            # Beide Workspaces starten mit identischem Onboarding-Seed. A bekommt
            # nie Nutzerdaten — seine Baseline ist die reine Seed-Baseline.
            base = client.get(f"/v1/workspaces/{ws_a}/dashboard", headers=auth_a).json()

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

            # Workspace A unveraendert: weder Bs Persona noch Bs Activity leaken.
            # (Der Seed schreibt keine status_history → As Activity bleibt leer.)
            dash_a = client.get(f"/v1/workspaces/{ws_a}/dashboard", headers=auth_a).json()
            assert dash_a["kpis"] == base["kpis"]
            assert (
                dash_a["status_distribution"]["persona"]["active"]
                == base["status_distribution"]["persona"]["active"]
            )
            assert dash_a["activity"] == []

            # Sanity-Check: Workspace B sieht die eigenen Daten (Baseline + 1) —
            # sonst koennte die Isolation auch "alles leer" sein.
            dash_b = client.get(f"/v1/workspaces/{ws_b}/dashboard", headers=auth_b).json()
            assert dash_b["kpis"]["active_personas"] == base["kpis"]["active_personas"] + 1
            assert len(dash_b["activity"]) == 1
            assert dash_b["activity"][0]["entity_id"] == persona_b["id"]

            # Cross-Workspace-Auth: User A darf B's Dashboard nicht abrufen.
            forbidden = client.get(f"/v1/workspaces/{ws_b}/dashboard", headers=auth_a)
            assert forbidden.status_code == 403
    finally:
        cleanup_workspaces([owner_a, owner_b])


@pytest.mark.integration
def test_dashboard_display_name_falls_back_through_meta_email_userid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drei Owner, ein Workspace, drei Aktivitaeten — eine pro Fallback-Stufe.

    Damit ein zweiter Owner ohne eigenen Workspace Aktivitaeten in `ws_owner`
    erzeugen darf, muss er Member sein. Wir tragen die beiden Helfer
    direkt als Editor in den Workspace ein (umgeht den Invitation-Flow).
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    user_email_only = fresh_user_id()
    user_none = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    async def _add_members() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.executemany(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, 'editor') "
                "ON CONFLICT (workspace_id, user_id) DO NOTHING",
                [(ws, user_email_only), (ws, user_none)],
            )
        finally:
            await conn.close()

    asyncio.run(_add_members())

    # Drei Fallback-Stufen vorbereiten: Meta-Name, Email-Local-Part, gar nichts.
    seed_auth_user(owner, email="meta@example.com", name="Meta Name")
    seed_auth_user(user_email_only, email="local-part@example.com", name=None)
    # `user_none` taucht in auth.users gar nicht auf — LEFT JOIN liefert NULL,
    # Service-Fallback ist die User-ID-String-Repraesentation.

    try:
        with TestClient(app) as client:
            persona = client.post(
                f"/v1/workspaces/{ws}/personas",
                json=_persona_body("display-fallback"),
                headers=auth,
            ).json()
            persona_id = UUID(persona["id"])
            _seed_version_status("persona_version", "persona_id", persona_id, 1, "draft")

            # Drei History-Eintraege in fester Reihenfolge.
            _insert_history("persona", persona_id, "draft", "review", owner)
            _insert_history("persona", persona_id, "review", "draft", user_email_only)
            _insert_history("persona", persona_id, "draft", "review", user_none)

            body = client.get(f"/v1/workspaces/{ws}/dashboard", headers=auth).json()
            activity = body["activity"]
            assert len(activity) == 3

            # ORDER BY DESC: zuerst der letzte Insert (`user_none`).
            assert activity[0]["actor"]["display_name"] == str(user_none)
            assert activity[1]["actor"]["display_name"] == "local-part"
            assert activity[2]["actor"]["display_name"] == "Meta Name"
            assert activity[1]["event"] == "rejected"
    finally:
        cleanup_workspaces([owner, user_email_only, user_none])
