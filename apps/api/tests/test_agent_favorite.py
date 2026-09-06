"""Integrationstest fuer persoenliche Agent-Favoriten (Issue #427).

Deckt die Zusagen ab, die nur gegen eine echte DB pruefbar sind: Persistenz
ueber den Request hinaus, die **Pro-User**-Trennung im selben Workspace, die
Tenancy-Grenze (fremder Workspace => 404), der `viewer`-Fall (Weiche 7) und
die beiden Aufraeumpfade (Agent-Delete per FK-CASCADE, Konto-Loeschung per
`purge_account_data`).

Nutzt die zentralen Fixtures aus `conftest.py` (`patched_jwt_secret`,
`migrated_db`, `make_auth_headers`) statt eigener Boilerplate — Review-Regel
im conftest-Kopf (Audit TST-10). Ohne erreichbare DB greift der zentrale Skip;
mit `WHO2BE_REQUIRE_DB=1` schlaegt er stattdessen hart fehl.
"""

import asyncio
from collections.abc import Callable
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

pytestmark = pytest.mark.integration

AuthFactory = Callable[[UUID], dict[str, str]]


def _add_member(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> None:
    """Zweites Mitglied direkt setzen — es gibt keinen POST-Endpunkt fuer
    Mitglieder (Beitritt laeuft ueber Invitations), Muster `test_external_tools`."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, $3) "
                "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role",
                workspace_id,
                user_id,
                role.value,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _favorite_flags(client: TestClient, ws: UUID, auth: dict[str, str]) -> dict[str, bool]:
    """`is_favorite` je Agent aus der Liste des ANFRAGENDEN Users.

    Jeder Workspace traegt zusaetzlich die beiden gesetzten Builder-Agenten
    (`_seed_default_agents`), deshalb pruefen die Tests gezielt die IDs, die
    sie selbst angelegt haben, statt die ganze Liste zu vergleichen.
    """
    listed = client.get(f"/v1/workspaces/{ws}/agents", headers=auth)
    assert listed.status_code == 200, listed.text
    return {str(item["id"]): item["is_favorite"] for item in listed.json()}


def _favorite_row_count(*, agent_id: UUID | None = None, user_id: UUID | None = None) -> int:
    """Zeilen in `agent_favorite`, gefiltert nach Agent und/oder User.

    Beide Filter werden UND-verknuepft angewendet — eine fruehere Fassung nahm
    nur das erste kwarg, womit ein Aufruf mit beiden Argumenten kommentarlos
    die halbe Bedingung geprueft und faelschlich gruen werden koennte.
    """

    async def _run() -> int:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM agent_favorite "
                "WHERE ($1::uuid IS NULL OR agent_id = $1) "
                "  AND ($2::uuid IS NULL OR user_id = $2)",
                agent_id,
                user_id,
            )
            return int(count)
        finally:
            await conn.close()

    return asyncio.run(_run())


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_favorite_roundtrip_is_per_user(make_auth_headers: AuthFactory) -> None:
    """Der Stern ueberlebt den Request und gehoert genau einem User.

    Zwei Mitglieder desselben Workspace markieren unterschiedliche Agenten —
    haette der Favorit an `agent` gehangen (verworfene Weiche B), saehen beide
    dasselbe. Beide Richtungen des Toggles sind idempotent.
    """
    user_a, user_b = fresh_user_id(), fresh_user_id()
    ws = setup_workspace(user_a)
    _add_member(ws, user_b, WorkspaceRole.editor)
    auth_a, auth_b = make_auth_headers(user_a), make_auth_headers(user_b)
    try:
        with TestClient(app) as client:
            base = f"/v1/workspaces/{ws}"
            first = client.post(f"{base}/agents", json={"name": "Erster"}, headers=auth_a).json()
            second = client.post(f"{base}/agents", json={"name": "Zweiter"}, headers=auth_a).json()

            before = _favorite_flags(client, ws, auth_a)
            assert before[first["id"]] is False
            assert before[second["id"]] is False

            put = client.put(f"{base}/agents/{first['id']}/favorite", headers=auth_a)
            assert put.status_code == 204, put.text
            # Idempotent: derselbe PUT ein zweites Mal aendert nichts.
            again = client.put(f"{base}/agents/{first['id']}/favorite", headers=auth_a)
            assert again.status_code == 204, again.text
            assert _favorite_row_count(agent_id=UUID(first["id"])) == 1

            put_b = client.put(f"{base}/agents/{second['id']}/favorite", headers=auth_b)
            assert put_b.status_code == 204, put_b.text

            # Kern der Zusage: A sieht seinen Stern, B seinen — nicht den des anderen.
            seen_a = _favorite_flags(client, ws, auth_a)
            seen_b = _favorite_flags(client, ws, auth_b)
            assert (seen_a[first["id"]], seen_a[second["id"]]) == (True, False)
            assert (seen_b[first["id"]], seen_b[second["id"]]) == (False, True)

            delete = client.delete(f"{base}/agents/{first['id']}/favorite", headers=auth_a)
            assert delete.status_code == 204, delete.text
            # Auch das Entfernen ist idempotent (0 Zeilen sind kein Fehler).
            once_more = client.delete(f"{base}/agents/{first['id']}/favorite", headers=auth_a)
            assert once_more.status_code == 204, once_more.text

            assert _favorite_flags(client, ws, auth_a)[first["id"]] is False
            # B bleibt davon unberuehrt.
            assert _favorite_flags(client, ws, auth_b)[second["id"]] is True
    finally:
        cleanup_workspaces([user_a, user_b])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_favorite_on_foreign_agent_is_404(make_auth_headers: AuthFactory) -> None:
    """Tenancy: ein Agent aus einem fremden Workspace existiert nicht — 404, nicht 403.

    403 waere ein Existenz-Orakel: es verriete, dass es die ID gibt.
    """
    owner, stranger = fresh_user_id(), fresh_user_id()
    ws_owner = setup_workspace(owner)
    ws_stranger = setup_workspace(stranger)
    try:
        with TestClient(app) as client:
            agent = client.post(
                f"/v1/workspaces/{ws_owner}/agents",
                json={"name": "Fremder"},
                headers=make_auth_headers(owner),
            ).json()
            for method in (client.put, client.delete):
                resp = method(
                    f"/v1/workspaces/{ws_stranger}/agents/{agent['id']}/favorite",
                    headers=make_auth_headers(stranger),
                )
                assert resp.status_code == 404, resp.text
            # Auch eine frei erfundene ID im eigenen Workspace ist 404.
            unknown = client.put(
                f"/v1/workspaces/{ws_owner}/agents/{uuid4()}/favorite",
                headers=make_auth_headers(owner),
            )
            assert unknown.status_code == 404, unknown.text
            assert _favorite_row_count(agent_id=UUID(agent["id"])) == 0
    finally:
        cleanup_workspaces([owner, stranger])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_viewer_may_favorite(make_auth_headers: AuthFactory) -> None:
    """Weiche 7: auch ein `viewer` darf markieren.

    Ein Favorit ist ein privates User-Datum, kein Workspace-Inhalt — „viewer =
    lesen, nicht schreiben" (ADR-0023) meint Inhalte.
    """
    owner, viewer = fresh_user_id(), fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, WorkspaceRole.viewer)
    try:
        with TestClient(app) as client:
            base = f"/v1/workspaces/{ws}"
            agent = client.post(
                f"{base}/agents", json={"name": "Gelesen"}, headers=make_auth_headers(owner)
            ).json()

            resp = client.put(
                f"{base}/agents/{agent['id']}/favorite", headers=make_auth_headers(viewer)
            )
            assert resp.status_code == 204, resp.text
            assert _favorite_flags(client, ws, make_auth_headers(viewer))[agent["id"]] is True
            # Der Stern des viewers bleibt fuer den owner unsichtbar.
            assert _favorite_flags(client, ws, make_auth_headers(owner))[agent["id"]] is False
    finally:
        cleanup_workspaces([owner, viewer])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_agent_delete_removes_favorites(make_auth_headers: AuthFactory) -> None:
    """FK CASCADE: mit dem Agenten verschwinden seine Favoriten-Zeilen."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    try:
        with TestClient(app) as client:
            base = f"/v1/workspaces/{ws}"
            agent = client.post(f"{base}/agents", json={"name": "Kurzlebig"}, headers=auth).json()
            marked = client.put(f"{base}/agents/{agent['id']}/favorite", headers=auth)
            assert marked.status_code == 204, marked.text
            assert _favorite_row_count(agent_id=UUID(agent["id"])) == 1

            deleted = client.delete(f"{base}/agents/{agent['id']}", headers=auth)
            assert deleted.status_code == 204, deleted.text

        assert _favorite_row_count(agent_id=UUID(agent["id"])) == 0
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_purge_account_data_removes_favorites(make_auth_headers: AuthFactory) -> None:
    """Konto-Loeschung raeumt die Sterne des Users ab.

    Es gibt keinen FK auf den GoTrue-User (kein Schema hat einen), also kann
    das nur `purge_account_data` erledigen. Geprueft wird deshalb in einem
    FREMDEN Workspace, den die Personal-Org-CASCADE nicht mitnimmt — dort haette
    ein fehlender Purge-Schritt die Zeile ueberleben lassen.
    """
    owner, guest = fresh_user_id(), fresh_user_id()
    ws = setup_workspace(owner)
    setup_workspace(guest)
    _add_member(ws, guest, WorkspaceRole.editor)
    try:
        with TestClient(app) as client:
            base = f"/v1/workspaces/{ws}"
            agent = client.post(
                f"{base}/agents", json={"name": "Geteilt"}, headers=make_auth_headers(owner)
            ).json()
            marked = client.put(
                f"{base}/agents/{agent['id']}/favorite", headers=make_auth_headers(guest)
            )
            assert marked.status_code == 204, marked.text
            assert _favorite_row_count(user_id=guest) == 1

        async def _purge() -> None:
            from who2be_api.repositories.account_repository import PgAccountPurgeRepository

            conn = await asyncpg.connect(get_settings().database_url)
            try:
                await PgAccountPurgeRepository(conn).purge_account_data(guest)
            finally:
                await conn.close()

        asyncio.run(_purge())
        assert _favorite_row_count(user_id=guest) == 0
    finally:
        cleanup_workspaces([owner, guest])
