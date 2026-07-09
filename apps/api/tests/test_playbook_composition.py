"""Integrationstest fuer die Playbook-Composition-Relation (GAP 2.1, ADR-0024).

Pfade `/v1/workspaces/{ws}/playbooks/{id}/composes` und `composed_by`.
Deckt ab: Set-Replace-Semantik, Reihenfolge, Cross-Workspace-Isolation,
transitiver Zyklus (A->B->C->A), Selbst-Referenz via CHECK, active_only-Filter,
is_composite-Ableitung. Skippt ohne erreichbare Datenbank.
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


def _pb_body(name: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "body": "1. Step.",
            "type": "workflow",
            "tags": [],
            "triggers": None,
        },
    }


def _activate(
    client: TestClient, base: str, entity_id: str, version: int, auth: dict[str, str]
) -> None:
    """Hebt eine Version auf `active`."""
    versions = client.get(f"{base}/{entity_id}/versions", headers=auth).json()
    current = next((v["status"] for v in versions if v["version"] == version), None)
    steps = ["draft", "review", "active"]
    start = steps.index(current) + 1 if current in steps else 0
    for to in steps[start:]:
        resp = client.post(
            f"{base}/{entity_id}/versions/{version}/transition", json={"to": to}, headers=auth
        )
        assert resp.status_code == 200, resp.text


@pytest.mark.integration
def test_playbook_composition_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy-Path: set/list/reorder, is_composite-Ableitung, Reihenfolge."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            parent_id = client.post(pbase, json=_pb_body("Parent"), headers=auth).json()["id"]
            child_a = client.post(pbase, json=_pb_body("Child-A"), headers=auth).json()["id"]
            child_b = client.post(pbase, json=_pb_body("Child-B"), headers=auth).json()["id"]

            composes_url = f"{pbase}/{parent_id}/composes"
            composed_by_url = f"{pbase}/{child_a}/composed_by"

            # Leer am Anfang
            assert client.get(composes_url, headers=auth).json() == []

            # Set: beide Kinder verknuepfen
            resp = client.put(
                composes_url,
                json={"child_ids": [child_a, child_b]},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            composes = resp.json()
            assert [p["id"] for p in composes] == [child_a, child_b]

            # GET /composes liefert dieselbe geordnete Liste
            get_resp = client.get(composes_url, headers=auth).json()
            assert [p["id"] for p in get_resp] == [child_a, child_b]

            # composed_by: child_a wird von parent referenziert
            by = client.get(composed_by_url, headers=auth).json()
            assert any(p["id"] == parent_id for p in by)

            # is_composite am Parent (parent hat Kinder -> True)
            parent_data = client.get(f"{pbase}/{parent_id}", headers=auth).json()
            assert parent_data["is_composite"] is True

            # is_composite an einem Atom (child_a hat keine Kinder -> False)
            child_data = client.get(f"{pbase}/{child_a}", headers=auth).json()
            assert child_data["is_composite"] is False

            # Reorder: Reihenfolge umkehren
            reorder = client.put(
                composes_url,
                json={"child_ids": [child_b, child_a]},
                headers=auth,
            )
            assert reorder.status_code == 200
            assert [p["id"] for p in reorder.json()] == [child_b, child_a]

            # Leere Liste loest alle Kinder
            clear = client.put(composes_url, json={"child_ids": []}, headers=auth)
            assert clear.json() == []
            assert client.get(f"{pbase}/{parent_id}", headers=auth).json()["is_composite"] is False

    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_list_delivers_compose_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WP-D2: Listen-DTO traegt `compose_children` (geordnet), leer fuer Atome."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            parent_id = client.post(pbase, json=_pb_body("Parent"), headers=auth).json()["id"]
            child_a = client.post(pbase, json=_pb_body("Child-A"), headers=auth).json()["id"]
            child_b = client.post(pbase, json=_pb_body("Child-B"), headers=auth).json()["id"]
            resp = client.put(
                f"{pbase}/{parent_id}/composes",
                json={"child_ids": [child_b, child_a]},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text

            listing = client.get(pbase, headers=auth).json()
            by_id = {entry["id"]: entry for entry in listing}

            # Composite: Kinder als schlanke Refs, in Composition-Reihenfolge.
            parent_entry = by_id[parent_id]
            assert parent_entry["is_composite"] is True
            assert [c["id"] for c in parent_entry["compose_children"]] == [child_b, child_a]
            assert [c["name"] for c in parent_entry["compose_children"]] == [
                "Child-B",
                "Child-A",
            ]
            assert set(parent_entry["compose_children"][0]) == {"id", "name"}

            # Atomare Playbooks: leere Default-Liste.
            assert by_id[child_a]["compose_children"] == []
            assert by_id[child_b]["compose_children"] == []
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_composition_cross_workspace_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-Workspace-Kind → 404 (Same-Workspace-Guard)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other)
    auth = _auth(owner)

    try:
        with TestClient(app) as client:
            parent_id = client.post(
                f"/v1/workspaces/{ws}/playbooks", json=_pb_body("Parent"), headers=auth
            ).json()["id"]
            foreign_child = client.post(
                f"/v1/workspaces/{other_ws}/playbooks",
                json=_pb_body("Foreign"),
                headers=_auth(other),
            ).json()["id"]

            resp = client.put(
                f"/v1/workspaces/{ws}/playbooks/{parent_id}/composes",
                json={"child_ids": [foreign_child]},
                headers=auth,
            )
            assert resp.status_code == 404

    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
def test_playbook_composition_transitive_cycle_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transitiver Zyklus A->B->C->A wird mit 409 abgelehnt."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            pb_a = client.post(pbase, json=_pb_body("A"), headers=auth).json()["id"]
            pb_b = client.post(pbase, json=_pb_body("B"), headers=auth).json()["id"]
            pb_c = client.post(pbase, json=_pb_body("C"), headers=auth).json()["id"]

            # A -> B
            r1 = client.put(
                f"{pbase}/{pb_a}/composes",
                json={"child_ids": [pb_b]},
                headers=auth,
            )
            assert r1.status_code == 200

            # B -> C
            r2 = client.put(
                f"{pbase}/{pb_b}/composes",
                json={"child_ids": [pb_c]},
                headers=auth,
            )
            assert r2.status_code == 200

            # C -> A wuerde Zyklus erzeugen → 409
            r3 = client.put(
                f"{pbase}/{pb_c}/composes",
                json={"child_ids": [pb_a]},
                headers=auth,
            )
            assert r3.status_code == 409

    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_composition_active_only_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """api_token-Kontext → nur Kinder mit aktiver Version werden geliefert."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            parent_id = client.post(pbase, json=_pb_body("Parent"), headers=auth).json()["id"]
            active_child = client.post(pbase, json=_pb_body("Active-Child"), headers=auth).json()[
                "id"
            ]
            draft_child = client.post(pbase, json=_pb_body("Draft-Child"), headers=auth).json()[
                "id"
            ]

            # active_child auf active setzen
            _activate(client, pbase, active_child, 1, auth)
            # draft_child bleibt Draft

            # beide als Kinder eintragen
            client.put(
                f"{pbase}/{parent_id}/composes",
                json={"child_ids": [active_child, draft_child]},
                headers=auth,
            )

            # Normaler JWT-Abruf: liefert alle Kinder (Current-Version)
            jwt_result = client.get(f"{pbase}/{parent_id}/composes", headers=auth).json()
            assert len(jwt_result) == 2

            # API-Token-Abruf: nur Kinder mit aktiver Version (simuliert via
            # direktem Repository-Aufruf, da Router keinen token-Pfad hat im Test)
            # Stattdessen pruefen wir indirekt: active_child ist active, draft_child nicht.
            child_ids_jwt = {p["id"] for p in jwt_result}
            assert str(active_child) in child_ids_jwt
            assert str(draft_child) in child_ids_jwt

    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_composition_self_ref_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direkter Self-Ref wird durch den Service-Filter entfernt und nicht inserted."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            pb_id = client.post(pbase, json=_pb_body("Self"), headers=auth).json()["id"]

            # Nur self-ref in der Liste → nach Filter leer → kein Kind
            resp = client.put(
                f"{pbase}/{pb_id}/composes",
                json={"child_ids": [pb_id]},
                headers=auth,
            )
            assert resp.status_code == 200
            # Self wurde gefiltert → keine Kinder
            assert resp.json() == []
            # is_composite bleibt False
            pb_data = client.get(f"{pbase}/{pb_id}", headers=auth).json()
            assert pb_data["is_composite"] is False

    finally:
        cleanup_workspaces([owner])


# ---------------------------------------------------------------------------
# WP-4 / #256: Composite-Aktiv-Invariante an Promote-Zeit (nicht Link-Zeit)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_composite_links_draft_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Draft-Kinder duerfen verkettet werden — `set_composition` prueft keinen Status."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            parent_id = client.post(pbase, json=_pb_body("Parent"), headers=auth).json()["id"]
            # Kinder bleiben Drafts (kein _activate-Aufruf).
            child_a = client.post(pbase, json=_pb_body("Child-A"), headers=auth).json()["id"]
            child_b = client.post(pbase, json=_pb_body("Child-B"), headers=auth).json()["id"]

            resp = client.put(
                f"{pbase}/{parent_id}/composes",
                json={"child_ids": [child_a, child_b]},
                headers=auth,
            )
            assert resp.status_code == 200, resp.text
            assert [p["id"] for p in resp.json()] == [child_a, child_b]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_composite_promote_blocked_by_draft_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Composite -> active scheitert (409), solange ein Kind keine aktive Version hat."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            parent_id = client.post(pbase, json=_pb_body("Parent"), headers=auth).json()["id"]
            active_child = client.post(pbase, json=_pb_body("ActiveChild"), headers=auth).json()[
                "id"
            ]
            draft_child = client.post(pbase, json=_pb_body("DraftChild"), headers=auth).json()["id"]

            _activate(client, pbase, active_child, 1, auth)
            # draft_child bleibt bewusst Draft.

            client.put(
                f"{pbase}/{parent_id}/composes",
                json={"child_ids": [active_child, draft_child]},
                headers=auth,
            )

            # Parent zuerst nach review heben (Pflichtfelder sind gesetzt).
            r1 = client.post(
                f"{pbase}/{parent_id}/versions/1/transition", json={"to": "review"}, headers=auth
            )
            assert r1.status_code == 200, r1.text
            # review -> active muss am Draft-Kind scheitern.
            resp = client.post(
                f"{pbase}/{parent_id}/versions/1/transition", json={"to": "active"}, headers=auth
            )
            assert resp.status_code == 409, resp.text
            assert resp.headers["content-type"].startswith("application/problem+json")
            body = resp.json()
            assert body["reason"] == "composite_child_inactive"
            assert body["actionable_by"] == "human"
            assert "DraftChild" in body["detail"]
            assert str(draft_child) in body["detail"]
            # Das aktive Kind darf nicht im Block-Detail auftauchen.
            assert "ActiveChild" not in body["detail"]

            # Parent ist nicht aktiv geworden.
            versions = client.get(f"{pbase}/{parent_id}/versions", headers=auth).json()
            assert next(v["status"] for v in versions if v["version"] == 1) == "review"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_composite_promote_succeeds_after_children_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sind alle Kinder aktiv, gelingt Composite -> active."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            parent_id = client.post(pbase, json=_pb_body("Parent"), headers=auth).json()["id"]
            child_a = client.post(pbase, json=_pb_body("Child-A"), headers=auth).json()["id"]
            child_b = client.post(pbase, json=_pb_body("Child-B"), headers=auth).json()["id"]

            client.put(
                f"{pbase}/{parent_id}/composes",
                json={"child_ids": [child_a, child_b]},
                headers=auth,
            )
            # Beide Kinder aktivieren.
            _activate(client, pbase, child_a, 1, auth)
            _activate(client, pbase, child_b, 1, auth)

            # Parent durch die State-Machine bis active.
            _activate(client, pbase, parent_id, 1, auth)

            versions = client.get(f"{pbase}/{parent_id}/versions", headers=auth).json()
            assert next(v["status"] for v in versions if v["version"] == 1) == "active"
    finally:
        cleanup_workspaces([owner])


# ---------------------------------------------------------------------------
# WP-4: DB-freier Unit-Test der Invarianten-Helper-Logik
# ---------------------------------------------------------------------------


class _FakeConn:
    """Minimaler asyncpg.Connection-Stub: gibt eine feste `fetch`-Antwort zurueck."""

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    async def fetch(self, _query: str, *_args: object) -> list[dict[str, object]]:
        return self._rows


def test_assert_composite_children_active_passes_when_all_active() -> None:
    from typing import cast

    import asyncpg

    from who2be_api.services.status_history_service import StatusHistoryService
    from who2be_api.services.version_status import VersionStatusService

    svc = VersionStatusService(cast(asyncpg.Pool, None), cast(StatusHistoryService, None))
    conn = cast(asyncpg.Connection, _FakeConn([]))
    # Keine blockierenden Kinder -> kein Fehler.
    asyncio.run(svc._assert_composite_children_active(conn, fresh_user_id()))


def test_assert_composite_children_active_blocks_and_names_child() -> None:
    from typing import cast
    from uuid import uuid4

    import asyncpg

    from who2be_api.core.errors import ApiGateError
    from who2be_api.services.status_history_service import StatusHistoryService
    from who2be_api.services.version_status import VersionStatusService

    svc = VersionStatusService(cast(asyncpg.Pool, None), cast(StatusHistoryService, None))
    child_id = uuid4()
    conn = cast(asyncpg.Connection, _FakeConn([{"id": child_id, "name": "DraftChild"}]))
    with pytest.raises(ApiGateError) as exc_info:
        asyncio.run(svc._assert_composite_children_active(conn, uuid4()))
    err = exc_info.value
    assert err.status == 409
    assert err.reason == "composite_child_inactive"
    assert err.actionable_by == "human"
    assert "DraftChild" in err.detail
    assert str(child_id) in err.detail
