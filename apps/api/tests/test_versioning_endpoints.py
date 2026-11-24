"""Integrationstests fuer Track A — Versionierung-Core.

Deckt Restore (non-destruktiv → neue Draft), Diff (against=active),
Provenance (status_history-Kette einer Version) und Reset-auf-Draft
(Reaktivierung der zuletzt aktiven Version) ueber die vier versionierten
Entitaeten ab, dazu den PUT-Pfad bei offenem Review (t_1f5dae56, alle fuenf
Arten). Laeuft nur mit erreichbarer Datenbank; ohne DB → Skip.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.db import init_connection
from who2be_api.core.errors import ApiError
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.core.security import WorkspaceContext
from who2be_api.main import app
from who2be_api.repositories.external_tool_repository import PgExternalToolRepository
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.repositories.playbook_repository import PgPlaybookRepository
from who2be_api.repositories.resource_repository import PgResourceRepository
from who2be_api.repositories.system_prompt_template_repository import (
    PgSystemPromptTemplateRepository,
)
from who2be_api.services.external_tool_service import ExternalToolService
from who2be_api.services.system_prompt_template_service import SystemPromptTemplateService
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import (
    ExternalToolContent,
    ExternalToolUpdate,
    PersonaVersionContent,
    PlaybookContent,
    ResourceContent,
    SystemPromptTemplateContent,
    SystemPromptTemplateUpdate,
    WorkspaceRole,
)

if TYPE_CHECKING:
    # Starlette typisiert den TestClient auf httpx2; die Antwort kommt von dort.
    from httpx2 import Response

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


def _playbook_body(description: str, body: str = "") -> dict[str, object]:
    return {
        "name": "Onboard",
        "content": {
            "description": description,
            "body": body,
            "type": "workflow",
            "tags": ["a"],
            "triggers": "x",
        },
    }


def _to(
    client: TestClient,
    base: str,
    pid: str,
    version: int,
    status: str,
    auth: dict[str, str],
) -> Response:
    resp: Response = client.post(
        f"{base}/{pid}/versions/{version}/transition", json={"to": status}, headers=auth
    )
    return resp


@pytest.mark.integration
def test_playbook_diff_and_restore_and_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            pid = client.post(base, json=_playbook_body("v1", "body one"), headers=auth).json()[
                "id"
            ]
            assert _to(client, base, pid, 1, "review", auth).status_code == 200
            assert _to(client, base, pid, 1, "active", auth).status_code == 200

            # Edit auf Active → v2 Draft mit geaendertem Body.
            v2 = client.put(f"{base}/{pid}", json=_playbook_body("v2", "body two"), headers=auth)
            assert v2.status_code == 200
            assert v2.json()["current_version"] == 2

            # Diff v2 gegen active (=v1): description + body geaendert.
            diff = client.get(f"{base}/{pid}/versions/2/diff?against=active", headers=auth)
            assert diff.status_code == 200, diff.text
            payload = diff.json()
            assert payload["against_version"] == 1
            assert payload["identical"] is False
            paths = {c["path"]: c for c in payload["changes"]}
            assert paths["body"]["before"] == "body one"
            assert paths["body"]["after"] == "body two"
            assert "description" in paths
            # WP-C: kanonische Text-Serialisierung fuer die git-artige Diff-UI.
            # Der Body hier ist kein BlockNote-JSON -> Roh-Fallback.
            assert payload["before_text"] == "v1\n\nbody one"
            assert payload["after_text"] == "v2\n\nbody two"

            # Restore v1 bei offenem Draft (v2) → 409.
            assert client.post(f"{base}/{pid}/versions/1/restore", headers=auth).status_code == 409

            # Promote v2 → active, danach Restore v1 → v3 Draft mit v1-Body.
            assert _to(client, base, pid, 2, "review", auth).status_code == 200
            assert _to(client, base, pid, 2, "active", auth).status_code == 200
            restored = client.post(f"{base}/{pid}/versions/1/restore", headers=auth)
            assert restored.status_code == 201, restored.text
            assert restored.json()["current_version"] == 3
            assert restored.json()["current_status"] == "draft"
            assert restored.json()["content"]["body"] == "body one"

            # Provenance v1: enthaelt die Kette bis 'active' (warum aktiv).
            prov = client.get(f"{base}/{pid}/versions/1/provenance", headers=auth)
            assert prov.status_code == 200
            episodes = prov.json()
            assert any(e["to_status"] == "active" for e in episodes)
            assert all(e["version"] == 1 for e in episodes)
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_playbook_reset_reactivates_previous_active(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/playbooks"

    try:
        with TestClient(app) as client:
            pid = client.post(base, json=_playbook_body("v1", "one"), headers=auth).json()["id"]
            assert _to(client, base, pid, 1, "review", auth).status_code == 200
            assert _to(client, base, pid, 1, "active", auth).status_code == 200
            client.put(f"{base}/{pid}", json=_playbook_body("v2", "two"), headers=auth)
            assert _to(client, base, pid, 2, "review", auth).status_code == 200
            assert _to(client, base, pid, 2, "active", auth).status_code == 200

            # Reset-auf-Draft: v2 (active) → draft reaktiviert v1.
            reset = _to(client, base, pid, 2, "draft", auth)
            assert reset.status_code == 200, reset.text

            versions = {
                v["version"]: v["status"]
                for v in client.get(f"{base}/{pid}/versions", headers=auth).json()
            }
            assert versions[2] == "draft"
            assert versions[1] == "active"

            # Provenance v1 dokumentiert die Reaktivierung (inactive→active).
            prov = client.get(f"{base}/{pid}/versions/1/provenance", headers=auth).json()
            assert any(e["from_status"] == "inactive" and e["to_status"] == "active" for e in prov)
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_resource_block_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/resources"

    def block(bid: str, text: str) -> dict[str, object]:
        return {
            "id": bid,
            "type": "paragraph",
            "content": [{"type": "text", "text": text, "styles": {}}],
        }

    def body(desc: str, blocks: list[dict[str, object]]) -> dict[str, object]:
        return {"name": "Doc", "content": {"description": desc, "blocks": blocks}}

    try:
        with TestClient(app) as client:
            rid = client.post(base, json=body("v1", [block("b1", "x")]), headers=auth).json()["id"]
            assert _to(client, base, rid, 1, "review", auth).status_code == 200
            assert _to(client, base, rid, 1, "active", auth).status_code == 200
            client.put(
                f"{base}/{rid}", json=body("v1", [block("b1", "y"), block("b2", "z")]), headers=auth
            )

            diff = client.get(f"{base}/{rid}/versions/2/diff", headers=auth).json()
            ops = {c["path"]: c["op"] for c in diff["changes"]}
            assert ops["blocks[b1]"] == "changed"
            assert ops["blocks[b2]"] == "added"
            # WP-C: Klartext beider Staende fuer den Zeilen-Diff der UI.
            assert diff["before_text"] == "v1\n\nx"
            assert diff["after_text"] == "v1\n\ny\n\nz"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_persona_and_template_restore(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)

    def persona_body(desc: str) -> dict[str, object]:
        return {
            "name": "QA",
            "content": {
                "description": desc,
                "content": {
                    "description": desc,
                    "blocks": [
                        {
                            "id": "b1",
                            "type": "paragraph",
                            "content": [{"type": "text", "text": desc, "styles": {}}],
                        }
                    ],
                },
            },
        }

    try:
        with TestClient(app) as client:
            # Persona: v1 active → restore v1 → v2 Draft.
            pbase = f"/v1/workspaces/{ws}/personas"
            pid = client.post(pbase, json=persona_body("v1"), headers=auth).json()["id"]
            assert _to(client, pbase, pid, 1, "review", auth).status_code == 200
            assert _to(client, pbase, pid, 1, "active", auth).status_code == 200
            r = client.post(f"{pbase}/{pid}/versions/1/restore", headers=auth)
            assert r.status_code == 201, r.text
            assert r.json()["current_status"] == "draft"
            assert r.json()["content"]["description"] == "v1"

            # Template: v1 active → restore v1 → v2 Draft.
            tbase = f"/v1/workspaces/{ws}/system-prompts"
            tid = client.post(
                tbase,
                json={"name": "Tpl", "content": {"description": "", "body": "hello"}},
                headers=auth,
            ).json()["id"]
            assert _to(client, tbase, tid, 1, "review", auth).status_code == 200
            assert _to(client, tbase, tid, 1, "active", auth).status_code == 200
            tr = client.post(f"{tbase}/{tid}/versions/1/restore", headers=auth)
            assert tr.status_code == 201, tr.text
            assert tr.json()["current_status"] == "draft"
            assert tr.json()["content"]["body"] == "hello"
            tdiff = client.get(f"{tbase}/{tid}/versions/2/diff", headers=auth).json()
            assert tdiff["identical"] is True
    finally:
        cleanup_workspaces([owner])


def _stuck_body(kind: str, text: str) -> dict[str, object]:
    """Gueltiger (promote-faehiger) Create/PUT-Body je versioniertem Typ."""
    if kind == "playbooks":
        return _playbook_body(text, text)
    if kind == "system-prompts":
        return {"name": "Tpl", "content": {"description": "", "body": text}}
    blocks = [
        {
            "id": "b1",
            "type": "paragraph",
            "content": [{"type": "text", "text": text, "styles": {}}],
        }
    ]
    if kind == "personas":
        return {
            "name": "QA",
            "content": {"description": text, "content": {"description": text, "blocks": blocks}},
        }
    return {"name": "Doc", "content": {"description": text, "blocks": blocks}}


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["playbooks", "personas", "resources", "system-prompts"])
def test_review_plus_new_draft_does_not_deadlock(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Karte t_6ee15ca8: neben einer offenen Review liegt ein Draft.

    Vorher blockierten sich die Partial-Unique-Indizes aus 0011 gegenseitig:
    Draft→review → 409 (Review-Slot belegt), review→draft → 409
    (Draft-Slot belegt). Jetzt ersetzt das Einreichen des Drafts die offene
    Review (→ inactive) — auch fuer bereits verklemmte Bestandsdaten.

    Seit t_1f5dae56 entsteht diese Lage nicht mehr per PUT (409
    `review_conflict`); der Test baut sie ueber active→draft neben der
    offenen Review v2 auf.
    """
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    base = f"/v1/workspaces/{ws}/{kind}"

    try:
        with TestClient(app) as client:
            created = client.post(base, json=_stuck_body(kind, "v1"), headers=auth)
            assert created.status_code == 201, created.text
            eid = created.json()["id"]
            assert _to(client, base, eid, 1, "review", auth).status_code == 200
            assert _to(client, base, eid, 1, "active", auth).status_code == 200
            put = client.put(f"{base}/{eid}", json=_stuck_body(kind, "v2"), headers=auth)
            assert put.status_code == 200, put.text
            assert put.json()["current_version"] == 2
            assert _to(client, base, eid, 2, "review", auth).status_code == 200

            # PUT bei offener Review legt keine Version mehr an (t_1f5dae56).
            blocked = client.put(f"{base}/{eid}", json=_stuck_body(kind, "v3"), headers=auth)
            assert blocked.status_code == 409, blocked.text
            assert blocked.json()["reason"] == "review_conflict"

            # Draft neben offener Review: die vormals verklemmte Lage.
            assert _to(client, base, eid, 1, "draft", auth).status_code == 200
            submit = _to(client, base, eid, 1, "review", auth)
            assert submit.status_code == 200, submit.text
            assert submit.json()["status"] == "review"

            versions = {
                v["version"]: v["status"]
                for v in client.get(f"{base}/{eid}/versions", headers=auth).json()
            }
            assert versions == {1: "review", 2: "inactive"}

            # Herkunft von v2 nennt die Ersetzung; v2 bleibt wiederherstellbar.
            prov = client.get(f"{base}/{eid}/versions/2/provenance", headers=auth).json()
            assert any(
                e["from_status"] == "review"
                and e["to_status"] == "inactive"
                and "v1" in (e["note"] or "")
                for e in prov
            ), prov
            # v1 laesst sich wieder aktivieren, der Lebenszyklus laeuft weiter.
            assert _to(client, base, eid, 1, "active", auth).status_code == 200
    finally:
        cleanup_workspaces([owner])


# --- PUT-Pfad bei offenem Review (Kanban t_1f5dae56, ADR-0020) ----------------
#
# - Review ohne Draft: steht die hoechste Version in `review` und ist kein
#   Draft offen, lehnt der PUT-Pfad (`update`) ab wie der Auto-Save-Pfad
#   (`upsert_draft`). Er legt keine Version an und zieht `current_version`
#   nicht nach. Vorher entstand hier still eine `inactive`-Version, die kein
#   Leser sieht. Geprueft fuer alle fuenf Arten direkt am Repository.
# - Service: derselbe 409 wie beim Auto-Save (`reason=review_conflict`), der
#   Text nennt den naechsten Schritt. Geprueft fuer zwei Arten.
# - Bestand: eine `inactive`-Basis ohne Draft erzeugt weiter eine neue
#   `inactive`-Version (der Zweig bleibt unveraendert).

KINDS = ["persona", "playbook", "resource", "external_tool", "system_prompt"]

# Versions-Tabelle und Fremdschluessel je Art.
_TABLES = {
    "persona": ("persona_version", "persona_id"),
    "playbook": ("playbook_version", "playbook_id"),
    "resource": ("resource_version", "resource_id"),
    "external_tool": ("external_tool_version", "external_tool_id"),
    "system_prompt": ("system_prompt_template_version", "template_id"),
}
_ENTITY = {
    "persona": "persona",
    "playbook": "playbook",
    "resource": "resource",
    "external_tool": "external_tool",
    "system_prompt": "system_prompt_template",
}


def _make_repo(kind: str, pool: asyncpg.Pool) -> tuple[Any, Callable[[str], Any]]:
    if kind == "persona":
        return PgPersonaRepository(pool), lambda t: PersonaVersionContent(description=t)
    if kind == "playbook":
        return PgPlaybookRepository(pool), lambda t: PlaybookContent(description=t)
    if kind == "resource":
        return PgResourceRepository(pool), lambda t: ResourceContent(description=t)
    if kind == "external_tool":
        return PgExternalToolRepository(pool), lambda t: ExternalToolContent(display_name=t)
    return PgSystemPromptTemplateRepository(pool), lambda t: SystemPromptTemplateContent(body=t)


async def _insert(kind: str, repo: Any, ws: UUID, user: UUID, content: Any) -> Any:
    tag = f"{kind[:2]}-{fresh_user_id().hex[:8]}"
    if kind == "resource":
        return await repo.insert(ws, user, "E", content, "de", slug=tag)
    if kind == "external_tool":
        return await repo.insert(ws, user, "E", content, "de", alias=tag)
    if kind == "system_prompt":
        return await repo.insert(ws, user, "E", tag, content, "de")
    return await repo.insert(ws, user, "E", content, "de")


async def _versions(pool: asyncpg.Pool, kind: str, entity_id: UUID) -> list[tuple[int, str]]:
    table, fk = _TABLES[kind]
    rows = await pool.fetch(
        f"SELECT version, status FROM {table} WHERE {fk} = $1 ORDER BY version", entity_id
    )
    return [(r["version"], r["status"]) for r in rows]


async def _pointer(pool: asyncpg.Pool, kind: str, entity_id: UUID) -> int:
    value = await pool.fetchval(
        f"SELECT current_version FROM {_ENTITY[kind]} WHERE id = $1", entity_id
    )
    assert isinstance(value, int)
    return value


async def _set_status(
    pool: asyncpg.Pool, kind: str, entity_id: UUID, version: int, status: str
) -> None:
    table, fk = _TABLES[kind]
    await pool.execute(
        f"UPDATE {table} SET status = $1 WHERE {fk} = $2 AND version = $3",
        status,
        entity_id,
        version,
    )


async def _active_then_review(pool: asyncpg.Pool, kind: str, ws: UUID, user: UUID) -> Any:
    """v1 aktiv, v2 in Review, kein Draft offen. Gibt `(repo, make, id)` zurueck."""
    repo, make = _make_repo(kind, pool)
    created = await _insert(kind, repo, ws, user, make("eins"))
    await _set_status(pool, kind, created.id, 1, "active")
    await repo.update(ws, user, created.id, None, make("zwei"))
    await _set_status(pool, kind, created.id, 2, "review")
    assert await _versions(pool, kind, created.id) == [(1, "active"), (2, "review")]
    return repo, make, created.id


def _run(ws_user: tuple[UUID, UUID], body: Callable[[asyncpg.Pool], Awaitable[None]]) -> None:
    async def _go() -> None:
        pool = await asyncpg.create_pool(
            get_settings().database_url, min_size=1, max_size=2, init=init_connection
        )
        assert pool is not None
        try:
            await body(pool)
        finally:
            await pool.close()

    asyncio.run(_go())


@pytest.fixture
def workspace(migrated_db: None) -> Any:
    user = fresh_user_id()
    ws = setup_workspace(user)
    yield user, ws
    cleanup_workspaces([user])


@pytest.mark.integration
@pytest.mark.parametrize("kind", KINDS)
def test_put_on_open_review_is_rejected_without_new_version(
    workspace: tuple[UUID, UUID], kind: str
) -> None:
    user, ws = workspace

    async def body(pool: asyncpg.Pool) -> None:
        repo, make, eid = await _active_then_review(pool, kind, ws, user)
        pointer = await _pointer(pool, kind, eid)

        outcome = await repo.update(ws, user, eid, None, make("unsichtbar"))

        assert outcome.conflict == "review_pending"
        assert await _versions(pool, kind, eid) == [(1, "active"), (2, "review")]
        assert await _pointer(pool, kind, eid) == pointer
        # Gleiches Urteil wie der Auto-Save-Pfad.
        draft = await repo.upsert_draft(ws, user, eid, None, make("unsichtbar"))
        assert draft.conflict == "review_pending"

    _run(workspace, body)


@pytest.mark.integration
@pytest.mark.parametrize("kind", KINDS)
def test_put_on_inactive_base_still_creates_inactive_version(
    workspace: tuple[UUID, UUID], kind: str
) -> None:
    """Bestandszweig: Basis weder aktiv noch in Review → neue Version `inactive`."""
    user, ws = workspace

    async def body(pool: asyncpg.Pool) -> None:
        repo, make = _make_repo(kind, pool)
        created = await _insert(kind, repo, ws, user, make("eins"))
        await _set_status(pool, kind, created.id, 1, "inactive")

        outcome = await repo.update(ws, user, created.id, None, make("zwei"))

        assert outcome.conflict is None
        assert await _versions(pool, kind, created.id) == [(1, "inactive"), (2, "inactive")]

    _run(workspace, body)


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["system_prompt", "external_tool"])
def test_service_put_on_open_review_returns_same_409_as_autosave(
    workspace: tuple[UUID, UUID], kind: str
) -> None:
    user, ws = workspace
    ctx = WorkspaceContext(workspace_id=ws, user_id=user, role=WorkspaceRole.editor)

    async def body(pool: asyncpg.Pool) -> None:
        repo, make, eid = await _active_then_review(pool, kind, ws, user)
        service: Any
        update: Any
        if kind == "system_prompt":
            service = SystemPromptTemplateService(repo)
            update = SystemPromptTemplateUpdate(content=make("unsichtbar"))
        else:
            service = ExternalToolService(repo)
            update = ExternalToolUpdate(content=make("unsichtbar"))

        with pytest.raises(ApiError) as put_exc:
            await service.update(ctx, eid, update)
        with pytest.raises(ApiError) as draft_exc:
            await service.update_draft(ctx, eid, update)

        assert put_exc.value.status_code == 409
        assert put_exc.value.reason == "review_conflict"
        assert put_exc.value.reason == draft_exc.value.reason
        assert put_exc.value.detail == draft_exc.value.detail
        # Der Text nennt den naechsten Schritt.
        assert "transition" in str(put_exc.value.detail)
        assert await _versions(pool, kind, eid) == [(1, "active"), (2, "review")]

    _run(workspace, body)
