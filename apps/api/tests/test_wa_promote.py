"""Integrationstests fuer den Promote-Pfad (ADR-0047, WP14 — Spec G).

Spec-Akzeptanzen:
- Promote erzeugt eine Resource-DRAFT, nie direkt Active.
- Die Resource traegt Artifact-ID und Zeitpunkt (Herkunfts-Note in der
  Description + `status_history`-Eintrag).
- Nur doc-Artifacts sind promotebar; Agent braucht `resource_write`.
"""

import asyncio
from collections.abc import Callable
from typing import Any
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

AuthFactory = Callable[[UUID], dict[str, str]]


def _db_fetchval(sql: str, *args: object) -> Any:
    async def _run() -> Any:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return await conn.fetchval(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def _shared_area(client: TestClient, prefix: str, auth: dict[str, str], name: str) -> str:
    created = client.post(f"{prefix}/work-areas", json={"name": name}, headers=auth)
    assert created.status_code == 201, created.text
    area_id: str = created.json()["id"]
    return area_id


def _artifact(
    client: TestClient,
    prefix: str,
    auth: dict[str, str],
    area_id: str,
    content_md: str = "# Titelzeile\n\nInhalt aus der WorkArea.",
) -> dict[str, Any]:
    created = client.post(
        f"{prefix}/work-areas/{area_id}/artifacts",
        json={
            "title": "Wochenbericht KW32",
            "content_md": content_md,
            "occurred_at": "2026-08-04T09:00:00Z",
        },
        headers=auth,
    )
    assert created.status_code == 201, created.text
    body: dict[str, Any] = created.json()
    return body


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_promote_creates_draft_with_provenance(make_auth_headers: AuthFactory) -> None:
    """Promote → neue Resource als Draft v1 mit Artifact-ID + Zeitpunkt."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Team")
            artifact = _artifact(client, prefix, auth, area)
            promoted = client.post(f"{prefix}/wa-artifacts/{artifact['id']}/promote", headers=auth)
            assert promoted.status_code == 201, promoted.text
            resource = promoted.json()
            # Spec G: nie direkt Active — Draft v1 mit offenem Draft.
            assert resource["current_status"] == "draft"
            assert resource["current_version"] == 1
            assert resource["has_pending_draft"] is True
            assert resource["name"] == "Wochenbericht KW32"
            # Herkunft: Artifact-ID + fachlicher Zeitpunkt in der Description …
            detail = client.get(f"{prefix}/resources/{resource['id']}", headers=auth)
            description = detail.json()["content"]["description"]
            assert artifact["id"] in description
            assert "2026-08-04" in description
            # … und als status_history-Note (append-only).
            note = _db_fetchval(
                "SELECT note FROM status_history WHERE entity_type = 'resource' "
                "AND entity_id = $1 ORDER BY changed_at DESC LIMIT 1",
                UUID(resource["id"]),
            )
            assert note is not None and artifact["id"] in note
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_promote_into_existing_resource_updates_draft(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Team")
            artifact = _artifact(client, prefix, auth, area, content_md="Neuer Stand.")
            first = client.post(f"{prefix}/wa-artifacts/{artifact['id']}/promote", headers=auth)
            assert first.status_code == 201, first.text
            target_id = first.json()["id"]
            second_artifact = _artifact(
                client, prefix, auth, area, content_md="Ueberarbeiteter Stand."
            )
            second = client.post(
                f"{prefix}/wa-artifacts/{second_artifact['id']}/promote",
                params={"target_resource_id": target_id},
                headers=auth,
            )
            assert second.status_code == 201, second.text
            assert second.json()["id"] == target_id
            assert second.json()["current_status"] == "draft"
            detail = client.get(f"{prefix}/resources/{target_id}", headers=auth)
            blocks_text = str(detail.json()["content"]["blocks"])
            assert "Ueberarbeiteter Stand." in blocks_text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_promote_rejects_non_doc_and_gates(make_auth_headers: AuthFactory) -> None:
    """blob-Artifacts sind nicht promotebar; Agenten brauchen resource_write."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area = _shared_area(client, prefix, auth, "Team")
            digest = "cd" * 32
            # blob-Artifact direkt anlegen (Superuser, an der API vorbei).
            asyncio.run(_insert_blob_artifact(ws, UUID(area), digest))
            blob_id = _db_fetchval(
                "SELECT id FROM wa_artifact WHERE workspace_id = $1 AND type = 'blob'", ws
            )
            rejected = client.post(f"{prefix}/wa-artifacts/{blob_id}/promote", headers=auth)
            assert rejected.status_code == 422, rejected.text
            # Agent mit workarea_write, aber OHNE resource_write → 403.
            agent = client.post(
                f"{prefix}/agents",
                json={"name": "capture", "tool_policy": {"workarea_write": True}},
                headers=auth,
            )
            token = client.post(
                f"{prefix}/tokens",
                json={"name": "capture", "agent_id": agent.json()["id"]},
                headers=auth,
            )
            agent_headers = {"Authorization": f"Bearer {token.json()['token']}"}
            # Read-Grant, damit das Artifact SICHTBAR ist — erst dann greift
            # das Capability-Gate (ohne Grant korrekt 404, kein Existenz-Leak).
            grant = client.put(
                f"{prefix}/work-areas/{area}/grants/{agent.json()['id']}",
                json={"level": "read"},
                headers=auth,
            )
            assert grant.status_code == 200, grant.text
            doc = _artifact(client, prefix, auth, area)
            forbidden = client.post(
                f"{prefix}/wa-artifacts/{doc['id']}/promote", headers=agent_headers
            )
            assert forbidden.status_code == 403, forbidden.text
            # Fremdes/unsichtbares Artifact → 404.
            ghost = client.post(
                f"{prefix}/wa-artifacts/00000000-0000-0000-0000-000000000000/promote",
                headers=auth,
            )
            assert ghost.status_code == 404
    finally:
        cleanup_workspaces([owner])


async def _insert_blob_artifact(ws: UUID, area_id: UUID, digest: str) -> None:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        await conn.execute(
            "INSERT INTO wa_artifact (workspace_id, area_id, type, title, occurred_at, "
            "occurred_precision, content_ref) "
            "VALUES ($1, $2, 'blob', 'Original', now(), 'minute', $3)",
            ws,
            area_id,
            digest,
        )
    finally:
        await conn.close()
