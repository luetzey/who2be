"""RBAC-Matrix (Phase 2.3-A): Rolle x Mutating-Action -> erlaubt / 403.

Zwei Ebenen:

1. **Policy-Matrix (ohne DB, laeuft ueberall).** Die maßgebliche Tabelle aus
   ADR-0023 (`_MATRIX`) wird gegen die Autorisierungs-Primitiven
   (`require_role` + `required_role_for_transition`) geprueft. Sie deckt alle
   neun Actions aus dem Plan ab — auch die, deren HTTP-Endpoint erst in
   Prompt B verdrahtet wird (`delete_persona`, `list_members`,
   `create_invitation`): fuer sie ist die Soll-Mindestrolle hier festgezurrt.

2. **Endpoint-Enforcement (Integration, skip ohne DB).** Belegt am echten
   HTTP-Endpoint, dass die Gates tatsaechlich verdrahtet sind und dass der
   Token-Role-Snapshot greift (Stil `test_tokens.py`).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.security import WorkspaceContext, require_role
from who2be_api.main import app
from who2be_api.services.version_status import required_role_for_transition
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)
from who2be_models import VersionStatus, WorkspaceRole

_ROLES = [WorkspaceRole.viewer, WorkspaceRole.editor, WorkspaceRole.admin]

# Maßgebliche Permission-Matrix (ADR-0023). True = erlaubt (kein 403).
_MATRIX: dict[str, dict[WorkspaceRole, bool]] = {
    "create_persona": {
        WorkspaceRole.viewer: False,
        WorkspaceRole.editor: True,
        WorkspaceRole.admin: True,
    },
    "update_persona": {
        WorkspaceRole.viewer: False,
        WorkspaceRole.editor: True,
        WorkspaceRole.admin: True,
    },
    "delete_persona": {
        WorkspaceRole.viewer: False,
        WorkspaceRole.editor: True,
        WorkspaceRole.admin: True,
    },
    "transition_to_review": {
        WorkspaceRole.viewer: False,
        WorkspaceRole.editor: True,
        WorkspaceRole.admin: True,
    },
    "transition_to_active": {
        WorkspaceRole.viewer: False,
        WorkspaceRole.editor: False,
        WorkspaceRole.admin: True,
    },
    "list_members": {
        WorkspaceRole.viewer: True,
        WorkspaceRole.editor: True,
        WorkspaceRole.admin: True,
    },
    "create_invitation": {
        WorkspaceRole.viewer: False,
        WorkspaceRole.editor: False,
        WorkspaceRole.admin: True,
    },
    "create_token": {
        WorkspaceRole.viewer: False,
        WorkspaceRole.editor: True,
        WorkspaceRole.admin: True,
    },
    "list_dashboard": {
        WorkspaceRole.viewer: True,
        WorkspaceRole.editor: True,
        WorkspaceRole.admin: True,
    },
}

# Mindestrolle je Action, wie der Produktionscode sie durchsetzt. Die
# Transition-Eintraege kommen aus dem Produktions-Helper, nicht aus einer
# Test-Konstanten — so faellt eine geaenderte Transition-Policy hier auf.
_ACTION_GATE: dict[str, WorkspaceRole] = {
    "create_persona": WorkspaceRole.editor,
    "update_persona": WorkspaceRole.editor,
    "delete_persona": WorkspaceRole.editor,
    "transition_to_review": required_role_for_transition(VersionStatus.draft, VersionStatus.review),
    "transition_to_active": required_role_for_transition(
        VersionStatus.review, VersionStatus.active
    ),
    "list_members": WorkspaceRole.viewer,
    "create_invitation": WorkspaceRole.admin,
    "create_token": WorkspaceRole.editor,
    "list_dashboard": WorkspaceRole.viewer,
}


def _ctx(role: WorkspaceRole) -> WorkspaceContext:
    return WorkspaceContext(workspace_id=uuid4(), user_id=uuid4(), role=role)


@pytest.mark.parametrize("role", _ROLES)
@pytest.mark.parametrize("action", list(_MATRIX))
def test_rbac_matrix(action: str, role: WorkspaceRole) -> None:
    """Jede Rolle x Action ergibt das in `_MATRIX` festgezurrte 200/403."""
    expected_allowed = _MATRIX[action][role]
    gate = _ACTION_GATE[action]
    ctx = _ctx(role)
    if expected_allowed:
        require_role(ctx, gate)  # darf nicht werfen
    else:
        with pytest.raises(HTTPException) as exc:
            require_role(ctx, gate)
        assert exc.value.status_code == 403


def test_required_role_for_transition_table() -> None:
    """Promote/Retire = admin, alle uebrigen erlaubten Uebergaenge = editor."""
    assert (
        required_role_for_transition(VersionStatus.draft, VersionStatus.review)
        is WorkspaceRole.editor
    )
    assert (
        required_role_for_transition(VersionStatus.review, VersionStatus.draft)
        is WorkspaceRole.editor
    )
    assert (
        required_role_for_transition(VersionStatus.inactive, VersionStatus.draft)
        is WorkspaceRole.editor
    )
    assert (
        required_role_for_transition(VersionStatus.review, VersionStatus.active)
        is WorkspaceRole.admin
    )
    assert (
        required_role_for_transition(VersionStatus.active, VersionStatus.inactive)
        is WorkspaceRole.admin
    )


# --------------------------------------------------------------------------
# Integration: Enforcement am echten Endpoint (skip ohne DB), Stil test_tokens.
# --------------------------------------------------------------------------

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


def _add_member(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> None:
    """Fuegt einem bestehenden Workspace ein Mitglied mit `role` hinzu."""

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


def _jwt(owner_id: UUID) -> str:
    return jwt.encode(
        {
            "sub": str(owner_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )


def _persona_body(name: str = "tester") -> dict[str, object]:
    return {
        "name": name,
        "content": {"description": "d", "system_prompt": "Be helpful."},
    }


@pytest.mark.integration
def test_endpoint_gates_per_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Viewer = read-only; editor mutiert; nur admin promotet nach active."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))

    owner = fresh_user_id()  # Workspace-Eigner (admin via setup_workspace)
    viewer = fresh_user_id()
    editor = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, WorkspaceRole.viewer)
    _add_member(ws, editor, WorkspaceRole.editor)

    admin_auth = {"Authorization": f"Bearer {_jwt(owner)}"}
    viewer_auth = {"Authorization": f"Bearer {_jwt(viewer)}"}
    editor_auth = {"Authorization": f"Bearer {_jwt(editor)}"}
    personas = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            # create_persona: viewer 403, editor 201.
            assert (
                client.post(personas, json=_persona_body(), headers=viewer_auth).status_code == 403
            )
            created = client.post(personas, json=_persona_body(), headers=editor_auth)
            assert created.status_code == 201
            pid = created.json()["id"]
            ver = created.json()["current_version"]

            # Lesen darf der viewer.
            assert client.get(personas, headers=viewer_auth).status_code == 200
            assert (
                client.get(f"/v1/workspaces/{ws}/dashboard", headers=viewer_auth).status_code == 200
            )

            # Token-CRUD ist editor+ (ADR-0023): viewer 403 auf create UND list.
            tokens = f"/v1/workspaces/{ws}/tokens"
            assert client.post(tokens, json={"name": "t"}, headers=viewer_auth).status_code == 403
            assert client.get(tokens, headers=viewer_auth).status_code == 403
            assert client.post(tokens, json={"name": "t"}, headers=editor_auth).status_code == 201

            # Transition draft->review darf der editor; review->active nur admin.
            tr = f"{personas}/{pid}/versions/{ver}/transition"
            assert client.post(tr, json={"to": "review"}, headers=editor_auth).status_code == 200
            assert client.post(tr, json={"to": "active"}, headers=editor_auth).status_code == 403
            assert client.post(tr, json={"to": "active"}, headers=admin_auth).status_code == 200
    finally:
        cleanup_workspaces([owner, viewer, editor])


@pytest.mark.integration
def test_token_role_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Token erbt die Ersteller-Rolle; ein editor kann kein admin-Token bauen,
    und der editor-Token kann nicht nach active promoten."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))

    owner = fresh_user_id()
    editor = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, editor, WorkspaceRole.editor)
    editor_auth = {"Authorization": f"Bearer {_jwt(editor)}"}
    tokens = f"/v1/workspaces/{ws}/tokens"
    personas = f"/v1/workspaces/{ws}/personas"

    try:
        with TestClient(app) as client:
            # Editor darf keinen admin-Token erzeugen (hoeher als Ersteller).
            assert (
                client.post(
                    tokens, json={"name": "up", "role": "admin"}, headers=editor_auth
                ).status_code
                == 403
            )

            # Ohne explizite Rolle: Snapshot = editor.
            created = client.post(tokens, json={"name": "t"}, headers=editor_auth)
            assert created.status_code == 201
            assert created.json()["role"] == "editor"
            token = created.json()["token"]
            token_auth = {"Authorization": f"Bearer {token}"}

            # Editor-Token darf Personas anlegen + in Review schieben ...
            created_p = client.post(personas, json=_persona_body(), headers=token_auth)
            assert created_p.status_code == 201
            pid = created_p.json()["id"]
            ver = created_p.json()["current_version"]
            tr = f"{personas}/{pid}/versions/{ver}/transition"
            assert client.post(tr, json={"to": "review"}, headers=token_auth).status_code == 200
            # ... aber nicht nach active promoten (Snapshot-Rolle = editor).
            assert client.post(tr, json={"to": "active"}, headers=token_auth).status_code == 403
    finally:
        cleanup_workspaces([owner, editor])
