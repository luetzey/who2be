"""Integrationstest fuer ExternalTools unter `/v1/workspaces/{ws_id}/external_tools`.

Deckt WP-1 (Blueprint `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`)
ab: CRUD + Versionierung, Alias-Auto-Ableitung + Kollision (409), Status-
Workflow inkl. Restore, Draft-on-Edit, Workspace-Isolation, Einzel-Export
sowie den Purge-Cascade (Org-Delete raeumt `external_tool`/`external_tool_version`
mit ab). Nutzt die zentralen Fixtures aus dem Root-`conftest.py`
(`patched_jwt_secret`, `migrated_db`, `make_auth_headers`) — kein inline
`_db_reachable` (Review-Regel TST-10).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)
from who2be_models import WorkspaceRole

AuthFactory = Callable[[UUID], dict[str, str]]

_UNKNOWN = "00000000-0000-0000-0000-000000000000"


def _tool_body(
    name: str = "Todoist",
    *,
    alias: str | None = None,
    display_name: str = "Todoist",
    mcp_server_name: str = "Todoist MCP",
    tool_names: list[str] | None = None,
    usage_notes: str = "Nutze fuer To-dos.",
    fallback_note: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "name": name,
        "content": {
            "display_name": display_name,
            "mcp_server_name": mcp_server_name,
            "tool_names": tool_names if tool_names is not None else ["add_task", "list_tasks"],
            "usage_notes": usage_notes,
            "fallback_note": fallback_note,
            "tags": tags if tags is not None else [],
        },
    }
    if alias is not None:
        body["alias"] = alias
    return body


def _add_member(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> None:
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


def _promote(
    client: TestClient, base: str, tool_id: str, auth: dict[str, str], version: int = 1
) -> None:
    """Draft-`version` -> review -> active."""
    for to in ("review", "active"):
        res = client.post(
            f"{base}/{tool_id}/versions/{version}/transition", json={"to": to}, headers=auth
        )
        assert res.status_code == 200, res.text


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_crud_roundtrip_and_workspace_isolation(
    make_auth_headers: AuthFactory,
) -> None:
    owner = fresh_user_id()
    other_owner = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other_owner)
    auth = make_auth_headers(owner)
    other_auth = make_auth_headers(other_owner)
    base = f"/v1/workspaces/{ws}/external_tools"
    try:
        with TestClient(app) as client:
            assert client.get(base).status_code == 401

            created = client.post(base, json=_tool_body("Todoist"), headers=auth)
            assert created.status_code == 201, created.text
            body = created.json()
            tid = body["id"]
            assert body["current_version"] == 1
            assert body["current_status"] == "draft"
            assert body["workspace_id"] == str(ws)
            assert body["alias"] == "todoist"
            assert body["content"]["display_name"] == "Todoist"
            assert body["content"]["mcp_server_name"] == "Todoist MCP"
            assert body["content"]["tool_names"] == ["add_task", "list_tasks"]

            fetched = client.get(f"{base}/{tid}", headers=auth)
            assert fetched.status_code == 200
            assert fetched.json()["alias"] == "todoist"

            listed = client.get(base, headers=auth).json()
            assert any(t["id"] == tid for t in listed)

            # Workspace-Isolation: eigener (legitimer) Workspace des anderen
            # Users, aber fremde tool_id -> 404 (kein Existenz-Leak, kein 403 --
            # der Aufrufer IST Mitglied von `other_ws`, nur das Tool lebt anderswo).
            foreign = client.get(
                f"/v1/workspaces/{other_ws}/external_tools/{tid}", headers=other_auth
            )
            assert foreign.status_code == 404
    finally:
        cleanup_workspaces([owner, other_owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_alias_auto_derived_explicit_and_conflict(
    make_auth_headers: AuthFactory,
) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/external_tools"
    try:
        with TestClient(app) as client:
            # Auto-Ableitung aus dem Namen.
            auto = client.post(base, json=_tool_body("Things 3!"), headers=auth)
            assert auto.status_code == 201, auto.text
            assert auto.json()["alias"] == "things-3"

            # Expliziter Alias wird uebernommen.
            explicit = client.post(base, json=_tool_body("Kalender", alias="cal"), headers=auth)
            assert explicit.status_code == 201, explicit.text
            assert explicit.json()["alias"] == "cal"

            # Kollision (gleicher abgeleiteter Alias) -> 409.
            dup = client.post(base, json=_tool_body("Things 3!"), headers=auth)
            assert dup.status_code == 409, dup.text

            # Kollision mit explizitem Alias -> 409.
            dup_explicit = client.post(
                base, json=_tool_body("Anderer Kalender", alias="cal"), headers=auth
            )
            assert dup_explicit.status_code == 409, dup_explicit.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_status_workflow_restore_and_draft_on_edit(
    make_auth_headers: AuthFactory,
) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/external_tools"
    try:
        with TestClient(app) as client:
            tid = client.post(base, json=_tool_body("Todoist"), headers=auth).json()["id"]

            # v1 startet als Draft (Migration-Default 'draft', Muster 0019).
            assert client.get(f"{base}/{tid}", headers=auth).json()["current_status"] == "draft"
            _promote(client, base, tid, auth)
            assert client.get(f"{base}/{tid}", headers=auth).json()["current_status"] == "active"

            # Verbotener Uebergang active -> review.
            forbidden = client.post(
                f"{base}/{tid}/versions/1/transition", json={"to": "review"}, headers=auth
            )
            assert forbidden.status_code == 409, forbidden.text

            # Edit auf Active -> neuer Draft (Draft-on-Edit).
            updated = client.put(
                f"{base}/{tid}",
                json=_tool_body("Todoist", display_name="Todoist v2"),
                headers=auth,
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["current_version"] == 2
            assert updated.json()["current_status"] == "draft"
            assert updated.json()["has_pending_draft"] is True

            # Zweiter PUT -> 409 (Draft existiert bereits).
            assert (
                client.put(
                    f"{base}/{tid}",
                    json=_tool_body("Todoist", display_name="Todoist v3"),
                    headers=auth,
                ).status_code
                == 409
            )

            # PATCH .../draft upsertet in-place, ohne Versions-Increment.
            patched = client.patch(
                f"{base}/{tid}/draft",
                json=_tool_body("Todoist", display_name="Todoist v2-autosave"),
                headers=auth,
            )
            assert patched.status_code == 200, patched.text
            assert patched.json()["current_version"] == 2
            assert patched.json()["content"]["display_name"] == "Todoist v2-autosave"

            versions = client.get(f"{base}/{tid}/versions", headers=auth).json()
            assert [v["version"] for v in versions] == [2, 1]
            v1 = client.get(f"{base}/{tid}/versions/1", headers=auth).json()
            assert v1["content"]["display_name"] == "Todoist"
            assert v1["status"] == "active"

            # Promotion v2 -> active inactiviert v1 (Invariante "max. 1 Active").
            client.post(f"{base}/{tid}/versions/2/transition", json={"to": "review"}, headers=auth)
            client.post(f"{base}/{tid}/versions/2/transition", json={"to": "active"}, headers=auth)
            versions_after = client.get(f"{base}/{tid}/versions", headers=auth).json()
            assert {v["version"]: v["status"] for v in versions_after} == {
                1: "inactive",
                2: "active",
            }

            # Restore v1 als neue (non-destruktive) Draft-Version 3.
            restored = client.post(f"{base}/{tid}/versions/1/restore", headers=auth)
            assert restored.status_code == 201, restored.text
            assert restored.json()["current_version"] == 3
            assert restored.json()["current_status"] == "draft"
            assert restored.json()["content"]["display_name"] == "Todoist"

            # Provenance-Kette der Version 2 ("warum aktiv").
            provenance = client.get(f"{base}/{tid}/versions/2/provenance", headers=auth)
            assert provenance.status_code == 200, provenance.text
            assert any(entry["to_status"] == "active" for entry in provenance.json())
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_delete_happy_path_viewer_forbidden_and_unknown(
    make_auth_headers: AuthFactory,
) -> None:
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, WorkspaceRole.viewer)
    auth = make_auth_headers(owner)
    viewer_auth = make_auth_headers(viewer)
    base = f"/v1/workspaces/{ws}/external_tools"
    try:
        with TestClient(app) as client:
            tid = client.post(base, json=_tool_body("Todoist"), headers=auth).json()["id"]

            # Viewer darf nicht loeschen.
            assert client.delete(f"{base}/{tid}", headers=viewer_auth).status_code == 403
            assert client.get(f"{base}/{tid}", headers=auth).status_code == 200

            deleted = client.delete(f"{base}/{tid}", headers=auth)
            assert deleted.status_code == 204, deleted.text
            assert client.get(f"{base}/{tid}", headers=auth).status_code == 404

            assert client.delete(f"{base}/{_UNKNOWN}", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner, viewer])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_export_json_and_markdown(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, WorkspaceRole.viewer)
    auth = make_auth_headers(owner)
    viewer_auth = make_auth_headers(viewer)
    base = f"/v1/workspaces/{ws}/external_tools"
    try:
        with TestClient(app) as client:
            tid = client.post(
                base,
                json=_tool_body("Todoist", usage_notes="Immer fuer To-dos nutzen."),
                headers=auth,
            ).json()["id"]

            res = client.get(f"{base}/{tid}/export", headers=auth)
            assert res.status_code == 200, res.text
            assert f"who2be-external_tool-{tid}.json" in res.headers["content-disposition"]
            exported = res.json()
            assert exported["entity"] == "external_tool"
            assert exported["external_tool"]["id"] == tid
            assert "workspace_id" not in exported["external_tool"]
            assert len(exported["external_tool"]["versions"]) == 1

            md = client.get(f"{base}/{tid}/export?format=markdown", headers=auth)
            assert md.status_code == 200, md.text
            assert md.headers["content-type"].startswith("text/markdown")
            assert f"who2be-external_tool-{tid}.md" in md.headers["content-disposition"]
            assert "Immer fuer To-dos nutzen." in md.text

            # Export ist fuer Viewer offen (kein require_role).
            assert client.get(f"{base}/{tid}/export", headers=viewer_auth).status_code == 200
            assert client.get(f"{base}/{_UNKNOWN}/export", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner, viewer])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_org_delete_cascades_tables(make_auth_headers: AuthFactory) -> None:
    """GDPR-Purge-Abdeckung: Org-Hard-Delete (Muster `purge_organization`) raeumt
    `external_tool`/`external_tool_version` per FK-CASCADE mit ab — kein
    dediziertes Purge-Code-Update noetig (0035-Trigger-Muster, wie die drei
    Geschwister-Tabellen)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/external_tools"
    try:
        with TestClient(app) as client:
            tid = client.post(base, json=_tool_body("Todoist"), headers=auth).json()["id"]

            async def _cascade_delete_and_count() -> tuple[int, int]:
                conn = await asyncpg.connect(get_settings().database_url)
                try:
                    org_id = await conn.fetchval("SELECT org_id FROM workspace WHERE id = $1", ws)
                    await conn.execute("DELETE FROM organization WHERE id = $1", org_id)
                    tool_count = await conn.fetchval(
                        "SELECT count(*) FROM external_tool WHERE id = $1", UUID(tid)
                    )
                    version_count = await conn.fetchval(
                        "SELECT count(*) FROM external_tool_version WHERE external_tool_id = $1",
                        UUID(tid),
                    )
                    return tool_count, version_count
                finally:
                    await conn.close()

            tool_count, version_count = asyncio.run(_cascade_delete_and_count())
            assert tool_count == 0
            assert version_count == 0
    finally:
        # Die Org ist bereits geloescht — cleanup_workspaces ist idempotent
        # gegenueber bereits entfernten Rows.
        cleanup_workspaces([owner])


def _agent_token(
    client: TestClient, base_prefix: str, name: str, policy: dict[str, object], auth: dict[str, str]
) -> dict[str, str]:
    agent = client.post(
        f"{base_prefix}/agents", json={"name": name, "tool_policy": policy}, headers=auth
    )
    assert agent.status_code == 201, agent.text
    token = client.post(
        f"{base_prefix}/tokens",
        json={"name": name, "agent_id": agent.json()["id"]},
        headers=auth,
    )
    assert token.status_code == 201, token.text
    return {"Authorization": f"Bearer {token.json()['token']}"}


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_write_gates_require_capability(make_auth_headers: AuthFactory) -> None:
    """WP-3: agent-gebundene Tokens brauchen `external_tool_write` fuer Create/
    Update/Restore/Delete — 403 ohne, 2xx mit (analog Resource)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/external_tools"
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            tid = client.post(base, json=_tool_body("Todoist"), headers=auth).json()["id"]
            _promote(client, base, tid, auth)

            no_cap = _agent_token(client, prefix, "et-no-cap", {}, auth)
            with_cap = _agent_token(
                client, prefix, "et-with-cap", {"external_tool_write": True}, auth
            )

            # Create ohne Capability -> 403; mit -> 201.
            denied_create = client.post(base, json=_tool_body("Dienst-Ohne"), headers=no_cap)
            assert denied_create.status_code == 403, denied_create.text
            assert denied_create.json()["reason"] == "missing_capability"
            allowed_create = client.post(base, json=_tool_body("Dienst-Mit"), headers=with_cap)
            assert allowed_create.status_code == 201, allowed_create.text

            # Update ohne Capability -> 403; mit -> 200.
            denied_update = client.put(
                f"{base}/{tid}", json=_tool_body("Todoist", display_name="v2"), headers=no_cap
            )
            assert denied_update.status_code == 403, denied_update.text
            allowed_update = client.put(
                f"{base}/{tid}", json=_tool_body("Todoist", display_name="v2"), headers=with_cap
            )
            assert allowed_update.status_code == 200, allowed_update.text
            # v2 muss erst aktiv sein, sonst kollidiert restore() mit dem noch
            # offenen v2-Draft (409 draft_exists).
            _promote(client, base, tid, auth, version=2)

            # Restore ohne Capability -> 403; mit -> 201.
            denied_restore = client.post(f"{base}/{tid}/versions/1/restore", headers=no_cap)
            assert denied_restore.status_code == 403, denied_restore.text
            allowed_restore = client.post(f"{base}/{tid}/versions/1/restore", headers=with_cap)
            assert allowed_restore.status_code == 201, allowed_restore.text

            # Delete ohne Capability -> 403; mit -> 204 (auf dem zweiten Tool).
            other_tid = allowed_create.json()["id"]
            denied_delete = client.delete(f"{base}/{other_tid}", headers=no_cap)
            assert denied_delete.status_code == 403, denied_delete.text
            allowed_delete = client.delete(f"{base}/{other_tid}", headers=with_cap)
            assert allowed_delete.status_code == 204, allowed_delete.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_transition_requires_promote_retire_for_active(
    make_auth_headers: AuthFactory,
) -> None:
    """draft->review genuegt `external_tool_write`; review->active braucht
    zusaetzlich `promote_retire` (WP-3-Luecke geschlossen: vorher war
    `external_tool` NICHT in `version_status._WRITE_CAPABILITY`, jeder
    agent-gebundene Token bekam dort hart 403/`none`)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/external_tools"
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            tid = client.post(base, json=_tool_body("Todoist"), headers=auth).json()["id"]

            write_only = _agent_token(
                client, prefix, "et-write-only", {"external_tool_write": True}, auth
            )
            # draft -> review erlaubt mit external_tool_write.
            to_review = client.post(
                f"{base}/{tid}/versions/1/transition", json={"to": "review"}, headers=write_only
            )
            assert to_review.status_code == 200, to_review.text

            # review -> active NICHT erlaubt ohne promote_retire.
            denied_active = client.post(
                f"{base}/{tid}/versions/1/transition", json={"to": "active"}, headers=write_only
            )
            assert denied_active.status_code == 403, denied_active.text
            assert denied_active.json()["reason"] == "missing_capability"

            with_promote = _agent_token(
                client,
                prefix,
                "et-promote",
                {"external_tool_write": True, "promote_retire": True},
                auth,
            )
            allowed_active = client.post(
                f"{base}/{tid}/versions/1/transition", json={"to": "active"}, headers=with_promote
            )
            assert allowed_active.status_code == 200, allowed_active.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_draft_visibility_follows_write_capability(
    make_auth_headers: AuthFactory,
) -> None:
    """`sees_drafts(external_tool_write)`: ein Konsum-Agent (keine Writes) sieht
    nur `active`; ein Agent MIT `external_tool_write` sieht die Current-Version
    (inkl. Draft) — schliesst die `_active_only`-WP-1-Luecke."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/external_tools"
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            tid = client.post(
                base, json=_tool_body("Todoist", display_name="Aktiv"), headers=auth
            ).json()["id"]
            _promote(client, base, tid, auth)
            client.put(
                f"{base}/{tid}", json=_tool_body("Todoist", display_name="Draft-v2"), headers=auth
            )

            consumer = _agent_token(client, prefix, "et-consumer", {}, auth)
            editor_agent = _agent_token(
                client, prefix, "et-editor", {"external_tool_write": True}, auth
            )

            # Konsum-Agent: sieht nur die aktive v1 (kein Draft-Leak).
            consumer_view = client.get(f"{base}/{tid}", headers=consumer)
            assert consumer_view.status_code == 200, consumer_view.text
            assert consumer_view.json()["current_version"] == 1
            assert consumer_view.json()["content"]["display_name"] == "Aktiv"

            # Agent mit external_tool_write: sieht die Current-Version (Draft v2).
            editor_view = client.get(f"{base}/{tid}", headers=editor_agent)
            assert editor_view.status_code == 200, editor_view.text
            assert editor_view.json()["current_version"] == 2
            assert editor_view.json()["content"]["display_name"] == "Draft-v2"

            # Gleiches gilt fuer die Liste.
            consumer_list = client.get(base, headers=consumer).json()
            listed = next(t for t in consumer_list if t["id"] == tid)
            assert listed["current_version"] == 1
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_read_scope_none_blocks_agent(make_auth_headers: AuthFactory) -> None:
    """`external_tool_read=none` sperrt Reads fuer den gebundenen Agenten (403);
    `assigned` verhaelt sich wie `all` (kein Leak-Risiko, aber auch keine
    kuenstliche Restriktion — es gibt keine Zuweisungs-Semantik)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/external_tools"
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            tid = client.post(base, json=_tool_body("Todoist"), headers=auth).json()["id"]
            _promote(client, base, tid, auth)

            blocked = _agent_token(
                client, prefix, "et-blocked", {"external_tool_read": "none"}, auth
            )
            denied = client.get(f"{base}/{tid}", headers=blocked)
            assert denied.status_code == 403, denied.text
            denied_list = client.get(base, headers=blocked)
            assert denied_list.status_code == 403, denied_list.text

            assigned = _agent_token(
                client, prefix, "et-assigned", {"external_tool_read": "assigned"}, auth
            )
            allowed = client.get(f"{base}/{tid}", headers=assigned)
            assert allowed.status_code == 200, allowed.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_external_tool_gdpr_export_includes_tool(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/external_tools"
    try:
        with TestClient(app) as client:
            tid = client.post(base, json=_tool_body("Todoist"), headers=auth).json()["id"]

            export = client.get("/v1/gdpr/export", headers=auth)
            assert export.status_code == 200, export.text
            body = export.json()
            workspace_block = next(
                w for org in body["organizations"] for w in org["workspaces"] if w["id"] == str(ws)
            )
            tool_ids = {t["id"] for t in workspace_block["external_tools"]}
            assert tid in tool_ids
    finally:
        cleanup_workspaces([owner])
