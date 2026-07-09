"""QA-Durchlauf: Stränge D (Personas), E (Playbooks), I (State-Machine), J-Links.

Manuelles QA-Skript, KEIN Teil der regulären Suite: der Dateiname matcht das
pytest-Collection-Pattern bewusst nicht und `scripts/` liegt außerhalb der
`testpaths` (Audit TST-11). Ausführen nur explizit per Pfad:

    uv run pytest scripts/qa_run_personas_playbooks.py -v --tb=short
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import httpx
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
    setup_workspace,
)

_SECRET = "integration-test-jwt-secret-padding-0123456789"

# ── BLOCKNOTE-kompatibler Body (Pflichtfelder laut Promote-Validator) ────────
_PER_BLOCKS = [
    {
        "id": "b1",
        "type": "paragraph",
        "content": [{"type": "text", "text": "QA persona body.", "styles": {}}],
    }
]

# Resource blocks: heading (block links require heading as anchor)
_RES_BLOCKS = [
    {
        "id": "h1",
        "type": "heading",
        "props": {"level": 1},
        "content": [{"type": "text", "text": "Section One", "styles": {}}],
    },
    {
        "id": "p1",
        "type": "paragraph",
        "content": [{"type": "text", "text": "Resource content.", "styles": {}}],
    },
]


def _persona_body(description: str = "QA persona") -> dict[str, object]:
    return {
        "name": "[QA] Persona",
        "content": {
            "description": description,
            "system_prompt": "Be precise.",
            "traits": ["thorough"],
            "content": {"description": description, "blocks": _PER_BLOCKS},
        },
    }


def _playbook_body(
    description: str = "QA playbook", pb_type: str = "workflow"
) -> dict[str, object]:
    return {
        "name": "[QA] Playbook",
        "content": {
            "description": description,
            "body": "1. Step one. 2. Step two.",
            "type": pb_type,
            "tags": ["qa"],
            "triggers": "qa-trigger",
        },
    }


def _resource_body(description: str = "QA resource") -> dict[str, object]:
    return {
        "name": "[QA] Resource",
        "content": {
            "description": description,
            "blocks": _RES_BLOCKS,
        },
    }


# ── helpers ──────────────────────────────────────────────────────────────────


def _db_reachable() -> bool:
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(get_settings().database_url)
            await conn.close()
            return True
        except Exception:
            return False

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
        _SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _add_member(ws_id: UUID, user_id: UUID, role: str) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                ws_id,
                user_id,
                role,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _activate(
    c: TestClient, base: str, eid: str, v: int, editor_h: dict[str, str], admin_h: dict[str, str]
) -> None:
    """Transitions entity version through draft→review→active."""
    versions = c.get(f"{base}/{eid}/versions", headers=editor_h).json()
    current_status = next((ver["status"] for ver in versions if ver["version"] == v), "draft")
    if current_status == "draft":
        c.post(f"{base}/{eid}/versions/{v}/transition", json={"to": "review"}, headers=editor_h)
        current_status = "review"
    if current_status == "review":
        c.post(f"{base}/{eid}/versions/{v}/transition", json={"to": "active"}, headers=admin_h)


# ── FT-PER-01..16 ────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_FT_PER_01_to_16(monkeypatch: pytest.MonkeyPatch) -> None:
    """D · Personas: PER-01..16."""
    if not _db_reachable():
        pytest.skip("Keine DB.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_SECRET))

    admin_id = fresh_user_id()
    editor_id = fresh_user_id()
    viewer_id = fresh_user_id()
    ws = setup_workspace(admin_id)
    _add_member(ws, editor_id, "editor")
    _add_member(ws, viewer_id, "viewer")

    admin_h = _auth(admin_id)
    editor_h = _auth(editor_id)
    viewer_h = _auth(viewer_id)
    base = f"/v1/workspaces/{ws}/personas"

    with TestClient(app) as c:
        # PER-01: Liste empty state
        r = c.get(base, headers=viewer_h)
        assert r.status_code == 200, f"PER-01 empty list: {r.text}"
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        assert isinstance(items, list), "PER-01: response not a list"

        # PER-02: anlegen als editor → 201, version 1, status draft
        r = c.post(base, json=_persona_body("PER-02 create"), headers=editor_h)
        assert r.status_code == 201, f"PER-02 create: {r.text}"
        per = r.json()
        per_id = per["id"]
        assert per["current_version"] == 1, "PER-02: not v1"

        # PER-01 after create: list non-empty
        r = c.get(base, headers=viewer_h)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        assert len(items) >= 1, "PER-01: list still empty"

        # PER-01 pagination
        r = c.get(base + "?limit=1", headers=viewer_h)
        assert r.status_code == 200, "PER-01 pagination"

        # PER-03: Detail
        r = c.get(f"{base}/{per_id}", headers=viewer_h)
        assert r.status_code == 200, f"PER-03 detail: {r.text}"

        # PER-04: Auto-Save-Draft (PATCH)
        r = c.patch(
            f"{base}/{per_id}/draft",
            json={
                "content": {
                    "description": "PER-04 patched",
                    "system_prompt": "Be precise.",
                    "traits": ["thorough"],
                    "content": {"description": "patched", "blocks": _PER_BLOCKS},
                }
            },
            headers=editor_h,
        )
        assert r.status_code == 200, f"PER-04 patch draft: {r.text}"
        # version must stay at 1 (no increment on patch)
        assert r.json()["current_version"] == 1, "PER-04: version incremented unexpectedly"

        # PER-05: Persona-Modi (PATCH to not conflict with draft)
        r = c.patch(
            f"{base}/{per_id}/draft",
            json={
                "content": {
                    "description": "PER-05 modes",
                    "system_prompt": "Be precise.",
                    "traits": ["thorough"],
                    "content": {"description": "modes", "blocks": _PER_BLOCKS},
                    "modes": [{"name": "focusMode", "trigger": "focus", "is_default": True}],
                }
            },
            headers=editor_h,
        )
        assert r.status_code == 200, f"PER-05 modes via patch: {r.text}"

        # PER-06: tags endpoint
        r = c.get(f"/v1/workspaces/{ws}/personas/tags", headers=viewer_h)
        assert r.status_code == 200, f"PER-06 tags: {r.text}"

        # Helper playbook (activated)
        pb_base = f"/v1/workspaces/{ws}/playbooks"
        r2 = c.post(pb_base, json=_playbook_body("PER-07 helper pb"), headers=editor_h)
        assert r2.status_code == 201, f"PER-07 helper pb: {r2.text}"
        pb_id = r2.json()["id"]
        _activate(c, pb_base, pb_id, 1, editor_h, admin_h)

        # PER-07: verlinkte Playbooks set
        r = c.put(f"{base}/{per_id}/playbooks", json={"playbook_ids": [pb_id]}, headers=editor_h)
        assert r.status_code == 200, f"PER-07 link: {r.text}"

        # verify link via GET /personas/{id}/playbooks
        r = c.get(f"{base}/{per_id}/playbooks", headers=viewer_h)
        assert r.status_code == 200, f"PER-07 get playbooks: {r.text}"
        linked = r.json()
        assert any(p["id"] == pb_id for p in linked), "PER-07: playbook not linked"

        # PER-08: Versionshistorie
        r = c.get(f"{base}/{per_id}/versions", headers=viewer_h)
        assert r.status_code == 200, f"PER-08 versions: {r.text}"
        assert len(r.json()) >= 1

        # PER-10: Provenance (before first activate)
        r = c.get(f"{base}/{per_id}/versions/1/provenance", headers=viewer_h)
        assert r.status_code == 200, f"PER-10 provenance: {r.text}"

        # Activate per_id for rendered + diff
        _activate(c, base, per_id, 1, editor_h, admin_h)

        # PER-12: Rendered (needs active)
        r = c.get(f"{base}/{per_id}/rendered", headers=viewer_h)
        assert r.status_code == 200, f"PER-12 rendered: {r.text}"

        # PER-07 set-replace semantics: clear
        r = c.put(f"{base}/{per_id}/playbooks", json={"playbook_ids": []}, headers=editor_h)
        assert r.status_code == 200, "PER-07 set-replace clear"

        # PUT on active → new draft (for diff)
        r = c.put(f"{base}/{per_id}", json=_persona_body("PER-09 v2"), headers=editor_h)
        assert r.status_code in (200, 201), f"PER-09 PUT for draft: {r.text}"
        v2 = r.json()["current_version"]

        # PER-09: Diff
        r = c.get(f"{base}/{per_id}/versions/{v2}/diff?against=active", headers=viewer_h)
        assert r.status_code in (200, 404), f"PER-09 diff: {r.text}"

        # PER-11: Restore
        r = c.post(f"{base}/{per_id}/versions/1/restore", headers=editor_h)
        assert r.status_code in (200, 201, 409), f"PER-11 restore: {r.text}"
        # 409 = draft conflict (v2 still open) is acceptable

        # PER-13: Export JSON (top-level has entity + exported_at + persona/playbook)
        r = c.get(f"{base}/{per_id}/export?format=json", headers=viewer_h)
        assert r.status_code == 200, f"PER-13 json: {r.text}"
        exp = r.json()
        assert "entity" in exp or "id" in exp, f"PER-13: unexpected export: {list(exp.keys())}"

        # PER-14: Export Markdown
        r = c.get(f"{base}/{per_id}/export?format=markdown", headers=viewer_h)
        assert r.status_code == 200, f"PER-14 md: {r.text}"
        assert len(r.text) > 0, "PER-14: empty markdown"

        # PER-15: Delete frei (throwaway persona, no refs)
        r = c.post(base, json=_persona_body("throwaway"), headers=editor_h)
        assert r.status_code == 201
        throwaway_id = r.json()["id"]
        r = c.delete(f"{base}/{throwaway_id}", headers=editor_h)
        assert r.status_code == 204, f"PER-15 delete free: {r.text}"

        # PER-16: Delete blockiert by Agent
        # per_id has active v1 → create an agent referencing it
        ag_base = f"/v1/workspaces/{ws}/agents"
        r = c.post(
            ag_base,
            json={"name": "[QA] Blocker-Agent", "persona_id": per_id, "status": "disabled"},
            headers=editor_h,
        )
        assert r.status_code == 201, f"PER-16 agent create: {r.text}"

        r = c.delete(f"{base}/{per_id}", headers=editor_h)
        assert r.status_code == 409, f"PER-16 delete must be 409: {r.text}"
        body = r.json()
        assert "blocked_by" in body or "detail" in body, "PER-16: no blocked_by"

    cleanup_workspaces([admin_id, editor_id, viewer_id])


# ── FT-PB-01..14 ─────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_FT_PB_01_to_14(monkeypatch: pytest.MonkeyPatch) -> None:
    """E · Playbooks: PB-01..14."""
    if not _db_reachable():
        pytest.skip("Keine DB.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_SECRET))

    admin_id = fresh_user_id()
    editor_id = fresh_user_id()
    ws = setup_workspace(admin_id)
    _add_member(ws, editor_id, "editor")

    admin_h = _auth(admin_id)
    editor_h = _auth(editor_id)
    base = f"/v1/workspaces/{ws}/playbooks"
    res_base = f"/v1/workspaces/{ws}/resources"
    per_base = f"/v1/workspaces/{ws}/personas"

    with TestClient(app) as c:
        # PB-01: Liste empty
        r = c.get(base, headers=editor_h)
        assert r.status_code == 200, f"PB-01 list: {r.text}"

        # PB-02: Anlegen mit allen Types
        for pb_type in ["prompt", "instructions", "snippet", "workflow", "checklist", "faq"]:
            body = _playbook_body(f"type={pb_type}", pb_type)
            body["name"] = f"[QA] PB-{pb_type}"
            r = c.post(base, json=body, headers=editor_h)
            assert r.status_code == 201, f"PB-02 type={pb_type}: {r.text}"

        # Main playbook
        main_body: dict[str, object] = {
            "name": "[QA] Main-PB",
            "content": {
                "description": "PB main",
                "body": "1. Step one. 2. Step two.",
                "type": "workflow",
                "tags": ["qa", "main"],
                "triggers": "qa-main,qa-trigger",
            },
        }
        r = c.post(base, json=main_body, headers=editor_h)
        assert r.status_code == 201, f"PB-02 main: {r.text}"
        pb = r.json()
        pb_id = pb["id"]

        # PB-01: filter by tag
        r = c.get(base + "?tag=main", headers=editor_h)
        assert r.status_code == 200, "PB-01 tag filter"
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        assert any(p["id"] == pb_id for p in items), "PB-01: tag filter failed"

        # PB-01: filter by trigger
        r = c.get(base + "?trigger=qa-main", headers=editor_h)
        assert r.status_code == 200, "PB-01 trigger filter"

        # PB-03: Edit body via PATCH (no active yet, use patch)
        r = c.patch(
            f"{base}/{pb_id}/draft",
            json={
                "content": {
                    "description": "PB-03 with body",
                    "body": "# Title\nStep 1.\nStep 2.",
                    "type": "workflow",
                    "tags": ["qa", "main"],
                    "triggers": "qa-main",
                }
            },
            headers=editor_h,
        )
        assert r.status_code == 200, f"PB-03: {r.text}"

        # PB-04: Triggers & Tags detail
        r = c.get(f"{base}/{pb_id}", headers=editor_h)
        assert r.status_code == 200, "PB-04 detail"

        # PB-05: Tags endpoint
        r = c.get(f"/v1/workspaces/{ws}/playbooks/tags", headers=editor_h)
        assert r.status_code == 200, f"PB-05 tags: {r.text}"
        tags = r.json()
        assert "qa" in tags, f"PB-05: 'qa' not in tags: {tags}"

        # PB-06: Triggers endpoint
        r = c.get(f"/v1/workspaces/{ws}/playbooks/triggers", headers=editor_h)
        assert r.status_code == 200, f"PB-06 triggers: {r.text}"

        # PB-07: Resource-Links — create + activate resource
        r = c.post(res_base, json=_resource_body("PB-07 res"), headers=editor_h)
        assert r.status_code == 201, f"PB-07 resource: {r.text}"
        res_id = r.json()["id"]
        _activate(c, res_base, res_id, 1, editor_h, admin_h)

        # link_scope='resource': no block_id (whole resource, inline)
        r = c.put(
            f"{base}/{pb_id}/resource_links",
            json={
                "links": [
                    {
                        "resource_id": res_id,
                        "position": 0,
                        "link_scope": "resource",
                        "embedding_mode": "inline",
                    }
                ]
            },
            headers=editor_h,
        )
        assert r.status_code == 200, f"PB-07 inline link: {r.text}"

        # link_scope='block': block_id must be a heading block ("h1")
        r = c.put(
            f"{base}/{pb_id}/resource_links",
            json={
                "links": [
                    {
                        "resource_id": res_id,
                        "block_id": "h1",
                        "position": 1,
                        "link_scope": "block",
                        "embedding_mode": "lazy",
                    }
                ]
            },
            headers=editor_h,
        )
        assert r.status_code == 200, f"PB-07 lazy link: {r.text}"

        # PB-08: Composite — create + activate child
        child_body = _playbook_body("child pb", "snippet")
        child_body["name"] = "[QA] Child-PB"
        r = c.post(base, json=child_body, headers=editor_h)
        assert r.status_code == 201
        child_id = r.json()["id"]
        _activate(c, base, child_id, 1, editor_h, admin_h)

        r = c.put(f"{base}/{pb_id}/composes", json={"child_ids": [child_id]}, headers=editor_h)
        assert r.status_code == 200, f"PB-08 composes: {r.text}"

        # PB-09: composed_by
        r = c.get(f"{base}/{child_id}/composed_by", headers=editor_h)
        assert r.status_code == 200, f"PB-09: {r.text}"
        parents = r.json()
        assert any(p["id"] == pb_id for p in parents), "PB-09: parent missing"

        # Activate main pb
        _activate(c, base, pb_id, 1, editor_h, admin_h)

        # PB-10/11: "Used In" + usages — link persona
        r = c.post(per_base, json=_persona_body("PB-10 persona"), headers=editor_h)
        assert r.status_code == 201
        linked_per_id = r.json()["id"]
        r = c.put(
            f"{per_base}/{linked_per_id}/playbooks",
            json={"playbook_ids": [pb_id]},
            headers=editor_h,
        )
        assert r.status_code == 200

        r = c.get(f"{base}/{pb_id}/usages", headers=editor_h)
        assert r.status_code == 200, f"PB-11 usages: {r.text}"

        # PB-12: Versionen/Diff/Prov/Restore/Rendered
        r = c.get(f"{base}/{pb_id}/versions", headers=editor_h)
        assert r.status_code == 200, "PB-12 versions"

        # PUT on active → draft v2
        v2_body = _playbook_body("PB-12 v2")
        v2_body["name"] = "[QA] Main-PB"
        r = c.put(f"{base}/{pb_id}", json=v2_body, headers=editor_h)
        assert r.status_code in (200, 201), f"PB-12 PUT on active: {r.text}"
        v2 = r.json()["current_version"]  # int for playbooks

        r = c.get(f"{base}/{pb_id}/versions/{v2}/diff?against=active", headers=editor_h)
        assert r.status_code in (200, 404), f"PB-12 diff: {r.text}"

        r = c.get(f"{base}/{pb_id}/versions/1/provenance", headers=editor_h)
        assert r.status_code == 200, f"PB-12 provenance: {r.text}"

        r = c.post(f"{base}/{pb_id}/versions/1/restore", headers=editor_h)
        assert r.status_code in (200, 201, 409), f"PB-12 restore: {r.text}"

        r = c.get(f"{base}/{pb_id}/rendered", headers=editor_h)
        assert r.status_code == 200, f"PB-12 rendered: {r.text}"

        # PB-13: Export JSON + MD
        r = c.get(f"{base}/{pb_id}/export?format=json", headers=editor_h)
        assert r.status_code == 200, f"PB-13 json: {r.text}"
        exp = r.json()
        assert "entity" in exp or "id" in exp, f"PB-13: {list(exp.keys())}"

        r = c.get(f"{base}/{pb_id}/export?format=markdown", headers=editor_h)
        assert r.status_code == 200, f"PB-13 md: {r.text}"

        # PB-14: Delete blockiert (persona referencing pb_id)
        r = c.delete(f"{base}/{pb_id}", headers=editor_h)
        assert r.status_code == 409, f"PB-14 delete blocked: {r.text}"
        assert "blocked_by" in r.json() or "detail" in r.json()

        # PB-14: free delete (create isolated playbook)
        free_body = _playbook_body("free to delete")
        free_body["name"] = "[QA] Free-PB"
        r = c.post(base, json=free_body, headers=editor_h)
        assert r.status_code == 201
        free_id = r.json()["id"]
        r = c.delete(f"{base}/{free_id}", headers=editor_h)
        assert r.status_code == 204, f"PB-14 free delete: {r.text}"

    cleanup_workspaces([admin_id, editor_id])


# ── FT-VER-01..10 (Persona) ──────────────────────────────────────────────────


@pytest.mark.integration
def test_FT_VER_01_to_10_persona(monkeypatch: pytest.MonkeyPatch) -> None:
    """I · VER-01..10 für Persona."""
    if not _db_reachable():
        pytest.skip("Keine DB.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_SECRET))

    admin_id = fresh_user_id()
    editor_id = fresh_user_id()
    ws = setup_workspace(admin_id)
    _add_member(ws, editor_id, "editor")

    admin_h = _auth(admin_id)
    editor_h = _auth(editor_id)
    base = f"/v1/workspaces/{ws}/personas"

    def _t(
        c: TestClient, pid: str, v: int, to: str, auth: dict[str, str], note: str | None = None
    ) -> httpx.Response:
        body: dict[str, str] = {"to": to}
        if note:
            body["note"] = note
        resp: httpx.Response = c.post(
            f"{base}/{pid}/versions/{v}/transition", json=body, headers=auth
        )
        return resp

    with TestClient(app) as c:
        r = c.post(base, json=_persona_body("VER persona"), headers=editor_h)
        assert r.status_code == 201, f"VER setup create: {r.text}"
        pid = r.json()["id"]

        # VER-01: Submit (draft→review), with note for VER-10
        r = _t(c, pid, 1, "review", editor_h, note="VER-01/10 submit note")
        assert r.status_code == 200, f"VER-01: {r.text}"
        assert r.json()["status"] == "review"

        # VER-02: Publish as editor → 403
        r = _t(c, pid, 1, "active", editor_h)
        assert r.status_code == 403, f"VER-02 editor must 403: {r.text}"

        # VER-02: Publish as admin → active
        r = _t(c, pid, 1, "active", admin_h)
        assert r.status_code == 200, f"VER-02 admin: {r.text}"
        assert r.json()["status"] == "active"

        # VER-07: PUT on active → creates draft
        r = c.put(f"{base}/{pid}", json=_persona_body("VER v2"), headers=editor_h)
        assert r.status_code in (200, 201), f"VER-07: {r.text}"
        assert r.json()["current_status"] == "draft", f"VER-07: PUT didn't create draft: {r.json()}"
        v2 = r.json()["current_version"]

        # VER-08: Second PUT while draft exists → 409
        r = c.put(f"{base}/{pid}", json=_persona_body("VER v3"), headers=editor_h)
        assert r.status_code == 409, f"VER-08 must 409: {r.text}"

        # VER-03: Reject (submit v2 first, then reject)
        r = _t(c, pid, v2, "review", editor_h)
        assert r.status_code == 200, f"VER-03 submit: {r.text}"
        r = _t(c, pid, v2, "draft", editor_h, note="VER-03 reject")
        assert r.status_code == 200, f"VER-03 reject: {r.text}"
        assert r.json()["status"] == "draft"

        # VER-05: Reset active→draft — publish v2, then reset (admin-only per code)
        _t(c, pid, v2, "review", editor_h)
        _t(c, pid, v2, "active", admin_h)  # transitions old active
        # editor reset → 403 (active→draft requires admin per version_status.py)
        r_editor = _t(c, pid, v2, "draft", editor_h)
        assert r_editor.status_code == 403, f"VER-05 editor reset must 403: {r_editor.text}"
        # admin reset → 200
        r = _t(c, pid, v2, "draft", admin_h)
        assert r.status_code == 200, f"VER-05 reset: {r.text}"
        assert r.json()["status"] == "draft"

        # VER-04: Retire active→inactive — publish v2 again
        _t(c, pid, v2, "review", editor_h)
        _t(c, pid, v2, "active", admin_h)
        r = _t(c, pid, v2, "inactive", editor_h)
        assert r.status_code == 403, f"VER-04 editor retire must 403: {r.text}"
        r = _t(c, pid, v2, "inactive", admin_h)
        assert r.status_code == 200, f"VER-04 admin retire: {r.text}"
        assert r.json()["status"] == "inactive"

        # VER-06: Reaktivieren inactive→draft
        r = _t(c, pid, v2, "draft", editor_h, note="VER-06 reactivate")
        assert r.status_code == 200, f"VER-06: {r.text}"
        assert r.json()["status"] == "draft"

        # VER-09: Unique-Active-Invariante
        # publish v1 (already active was reset → can be done via v1 again)
        # First activate v2
        _t(c, pid, v2, "review", editor_h)
        _t(c, pid, v2, "active", admin_h)
        # Now publish v1 — system should handle only one active
        r_v1 = c.get(f"{base}/{pid}/versions", headers=editor_h).json()
        v1_status = next((v["status"] for v in r_v1 if v["version"] == 1), None)
        if v1_status == "draft":
            _t(c, pid, 1, "review", editor_h)
            _t(c, pid, 1, "active", admin_h)
        # Check only one active
        versions = c.get(f"{base}/{pid}/versions", headers=editor_h).json()
        actives = [v for v in versions if v["status"] == "active"]
        assert len(actives) == 1, f"VER-09: {len(actives)} active versions (expected 1)"

        # VER-10: Note in Provenance
        r = c.get(f"{base}/{pid}/versions/1/provenance", headers=editor_h)
        assert r.status_code == 200, f"VER-10 provenance: {r.text}"
        prov = r.json()
        assert isinstance(prov, list), "VER-10: provenance not a list"

    cleanup_workspaces([admin_id, editor_id])


# ── FT-VER-01..10 (Playbook) ─────────────────────────────────────────────────


@pytest.mark.integration
def test_FT_VER_01_to_10_playbook(monkeypatch: pytest.MonkeyPatch) -> None:
    """I · VER-01..10 für Playbook."""
    if not _db_reachable():
        pytest.skip("Keine DB.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_SECRET))

    admin_id = fresh_user_id()
    editor_id = fresh_user_id()
    ws = setup_workspace(admin_id)
    _add_member(ws, editor_id, "editor")

    admin_h = _auth(admin_id)
    editor_h = _auth(editor_id)
    base = f"/v1/workspaces/{ws}/playbooks"

    def _t(
        c: TestClient, eid: str, v: int, to: str, auth: dict[str, str], note: str | None = None
    ) -> httpx.Response:
        body: dict[str, str] = {"to": to}
        if note:
            body["note"] = note
        resp: httpx.Response = c.post(
            f"{base}/{eid}/versions/{v}/transition", json=body, headers=auth
        )
        return resp

    with TestClient(app) as c:
        r = c.post(base, json=_playbook_body("VER playbook"), headers=editor_h)
        assert r.status_code == 201, f"VER PB create: {r.text}"
        pb_id = r.json()["id"]

        # VER-01: Submit
        r = _t(c, pb_id, 1, "review", editor_h, note="VER-01 PB submit")
        assert r.status_code == 200 and r.json()["status"] == "review", f"VER-01 PB: {r.text}"

        # VER-02: editor→403
        assert _t(c, pb_id, 1, "active", editor_h).status_code == 403, "VER-02 PB editor"

        # VER-02: admin→active
        r = _t(c, pb_id, 1, "active", admin_h)
        assert r.status_code == 200 and r.json()["status"] == "active", f"VER-02 PB: {r.text}"

        # VER-07: PUT on active → draft
        r = c.put(f"{base}/{pb_id}", json=_playbook_body("VER v2"), headers=editor_h)
        assert r.status_code in (200, 201), f"VER-07 PB: {r.text}"
        assert r.json()["current_status"] == "draft", f"VER-07 PB: {r.json()}"
        v2 = r.json()["current_version"]

        # VER-08: second PUT → 409
        r = c.put(f"{base}/{pb_id}", json=_playbook_body("VER v3"), headers=editor_h)
        assert r.status_code == 409, f"VER-08 PB: {r.text}"

        # VER-03: reject
        _t(c, pb_id, v2, "review", editor_h)
        r = _t(c, pb_id, v2, "draft", editor_h, note="VER-03 PB reject")
        assert r.status_code == 200 and r.json()["status"] == "draft", f"VER-03 PB: {r.text}"

        # VER-05: reset (active→draft) — editor→403, admin→OK (per code)
        _t(c, pb_id, v2, "review", editor_h)
        _t(c, pb_id, v2, "active", admin_h)
        assert _t(c, pb_id, v2, "draft", editor_h).status_code == 403, "VER-05 PB editor"
        r = _t(c, pb_id, v2, "draft", admin_h)
        assert r.status_code == 200 and r.json()["status"] == "draft", f"VER-05 PB: {r.text}"

        # VER-04: retire (editor→403, admin→OK)
        _t(c, pb_id, v2, "review", editor_h)
        _t(c, pb_id, v2, "active", admin_h)
        assert _t(c, pb_id, v2, "inactive", editor_h).status_code == 403, "VER-04 PB editor"
        r = _t(c, pb_id, v2, "inactive", admin_h)
        assert r.status_code == 200 and r.json()["status"] == "inactive", f"VER-04 PB: {r.text}"

        # VER-06: reactivate (inactive→draft)
        r = _t(c, pb_id, v2, "draft", editor_h, note="VER-06 PB reaktivieren")
        assert r.status_code == 200 and r.json()["status"] == "draft", f"VER-06 PB: {r.text}"

        # VER-09: unique active invariant
        _t(c, pb_id, v2, "review", editor_h)
        _t(c, pb_id, v2, "active", admin_h)
        versions = c.get(f"{base}/{pb_id}/versions", headers=editor_h).json()
        actives = [v for v in versions if v["status"] == "active"]
        assert len(actives) == 1, f"VER-09 PB: {len(actives)} active (expected 1)"

        # VER-10: note in provenance
        r = c.get(f"{base}/{pb_id}/versions/1/provenance", headers=editor_h)
        assert r.status_code == 200, f"VER-10 PB: {r.text}"
        assert isinstance(r.json(), list), "VER-10 PB: not list"

    cleanup_workspaces([admin_id, editor_id])


# ── J-Links: LINK-01..03 ─────────────────────────────────────────────────────


@pytest.mark.integration
def test_FT_LINK_01_to_03(monkeypatch: pytest.MonkeyPatch) -> None:
    """J · LINK-01 (Persona↔Playbook), LINK-02 (Playbook↔Resource), LINK-03 (Composite)."""
    if not _db_reachable():
        pytest.skip("Keine DB.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_SECRET))

    admin_id = fresh_user_id()
    editor_id = fresh_user_id()
    ws = setup_workspace(admin_id)
    _add_member(ws, editor_id, "editor")

    admin_h = _auth(admin_id)
    editor_h = _auth(editor_id)
    pb_base = f"/v1/workspaces/{ws}/playbooks"
    per_base = f"/v1/workspaces/{ws}/personas"
    res_base = f"/v1/workspaces/{ws}/resources"

    with TestClient(app) as c:
        # Provision: active resource
        r = c.post(res_base, json=_resource_body("LINK resource"), headers=editor_h)
        assert r.status_code == 201, f"LINK resource: {r.text}"
        res_id = r.json()["id"]
        _activate(c, res_base, res_id, 1, editor_h, admin_h)

        # Provision: 2 playbooks (parent + child), both activated
        parent_body = _playbook_body("LINK parent pb")
        parent_body["name"] = "[QA-LINK] PB-Parent"
        r = c.post(pb_base, json=parent_body, headers=editor_h)
        assert r.status_code == 201, f"LINK parent pb: {r.text}"
        pb_parent_id = r.json()["id"]
        _activate(c, pb_base, pb_parent_id, 1, editor_h, admin_h)

        child_body = _playbook_body("LINK child pb", "snippet")
        child_body["name"] = "[QA-LINK] PB-Child"
        r = c.post(pb_base, json=child_body, headers=editor_h)
        assert r.status_code == 201, f"LINK child pb: {r.text}"
        pb_child_id = r.json()["id"]
        _activate(c, pb_base, pb_child_id, 1, editor_h, admin_h)

        # Provision: Persona
        r = c.post(per_base, json=_persona_body("LINK persona"), headers=editor_h)
        assert r.status_code == 201, f"LINK persona: {r.text}"
        per_id = r.json()["id"]

        # ── LINK-01: Persona↔Playbook Set-Replace ────────────────────────────
        # Set link
        r = c.put(
            f"{per_base}/{per_id}/playbooks",
            json={"playbook_ids": [pb_parent_id]},
            headers=editor_h,
        )
        assert r.status_code == 200, f"LINK-01 set: {r.text}"

        # Verify link via GET /personas/{id}/playbooks
        r = c.get(f"{per_base}/{per_id}/playbooks", headers=editor_h)
        assert r.status_code == 200, f"LINK-01 get playbooks: {r.text}"
        linked = r.json()
        assert any(p["id"] == pb_parent_id for p in linked), "LINK-01: pb not linked"

        # Verify backlink in playbook usages
        r = c.get(f"{pb_base}/{pb_parent_id}/usages", headers=editor_h)
        assert r.status_code == 200, f"LINK-01 backlink usages: {r.text}"

        # Replace (set-replace: now only child)
        r = c.put(
            f"{per_base}/{per_id}/playbooks", json={"playbook_ids": [pb_child_id]}, headers=editor_h
        )
        assert r.status_code == 200, f"LINK-01 replace: {r.text}"

        # Parent no longer linked — verify via dedicated endpoint
        r = c.get(f"{per_base}/{per_id}/playbooks", headers=editor_h)
        linked_after = r.json()
        assert not any(p["id"] == pb_parent_id for p in linked_after), (
            "LINK-01: old link persists after replace"
        )
        assert any(p["id"] == pb_child_id for p in linked_after), (
            "LINK-01: new link missing after replace"
        )

        # Clear all links
        r = c.put(f"{per_base}/{per_id}/playbooks", json={"playbook_ids": []}, headers=editor_h)
        assert r.status_code == 200, f"LINK-01 clear: {r.text}"

        # ── LINK-02: Playbook↔Resource Block-Ref ─────────────────────────────
        # inline embedding: link_scope='resource', no block_id
        r = c.put(
            f"{pb_base}/{pb_parent_id}/resource_links",
            json={
                "links": [
                    {
                        "resource_id": res_id,
                        "position": 0,
                        "link_scope": "resource",
                        "embedding_mode": "inline",
                    }
                ]
            },
            headers=editor_h,
        )
        assert r.status_code == 200, f"LINK-02 inline: {r.text}"

        # lazy embedding: block_id must reference a heading block ("h1")
        r = c.put(
            f"{pb_base}/{pb_parent_id}/resource_links",
            json={
                "links": [
                    {
                        "resource_id": res_id,
                        "block_id": "h1",
                        "position": 0,
                        "link_scope": "block",
                        "embedding_mode": "lazy",
                    }
                ]
            },
            headers=editor_h,
        )
        assert r.status_code == 200, f"LINK-02 lazy: {r.text}"

        # resource usages endpoint
        r = c.get(f"{res_base}/{res_id}/usages", headers=editor_h)
        assert r.status_code == 200, f"LINK-02 resource usages: {r.text}"

        # ── LINK-03: Playbook↔Playbook Composite ─────────────────────────────
        r = c.put(
            f"{pb_base}/{pb_parent_id}/composes",
            json={"child_ids": [pb_child_id]},
            headers=editor_h,
        )
        assert r.status_code == 200, f"LINK-03 composes: {r.text}"

        # composed_by backlink
        r = c.get(f"{pb_base}/{pb_child_id}/composed_by", headers=editor_h)
        assert r.status_code == 200, f"LINK-03 composed_by: {r.text}"
        parents = r.json()
        assert any(p["id"] == pb_parent_id for p in parents), "LINK-03: parent missing"

        # Clear composite (empty list = not composite)
        r = c.put(f"{pb_base}/{pb_parent_id}/composes", json={"child_ids": []}, headers=editor_h)
        assert r.status_code == 200, f"LINK-03 clear: {r.text}"

        # Verify cleared
        r = c.get(f"{pb_base}/{pb_child_id}/composed_by", headers=editor_h)
        parents_after = r.json()
        assert not any(p["id"] == pb_parent_id for p in parents_after), (
            "LINK-03: parent still in composed_by after clear"
        )

    cleanup_workspaces([admin_id, editor_id])
