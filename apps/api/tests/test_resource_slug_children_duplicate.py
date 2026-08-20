"""Integrationstests fuer die Design-Refresh-Erweiterungen des Backends:

- Resource-`slug` (auto-abgeleitet, workspace-eindeutig, Backfill-Migration 0064).
- Sub-Resource-Kinder als List-Card-Summary (`sub_resources` mit Status/Version).
- Token-`expires_at` im Read-Modell.
- Duplicate-Endpunkte fuer Persona/Resource/System-Prompt (Deep-Copy → Draft-v1).

Laeuft nur mit erreichbarer DB (zentraler conftest-Skip fuer `integration`).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR
from who2be_api.main import app
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = pytest.mark.integration


def _block(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": {},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _resource_body(
    name: str, description: str = "d", blocks: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "name": name,
        "content": {"description": description, "blocks": blocks or [], "tags": []},
    }


def _persona_body(name: str, description: str = "d") -> dict[str, object]:
    return {"name": name, "content": {"description": description, "system_prompt": "s"}}


def _template_body(name: str, body: str = "Hallo {{ persona.name }}") -> dict[str, object]:
    return {"name": name, "content": {"description": "", "body": body}}


def _promote(client: TestClient, base: str, rid: str, auth: dict[str, str]) -> None:
    """Draft-v1 → review → active (fuer variable Kind-Status im List-Test)."""
    for to in ("review", "active"):
        res = client.post(f"{base}/{rid}/versions/1/transition", json={"to": to}, headers=auth)
        assert res.status_code == 200, res.text


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_resource_slug_auto_derived_unique_and_roundtrip(
    make_auth_headers: AuthFactory,
) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/resources"
    try:
        with TestClient(app) as client:
            # Auto-Ableitung aus dem Namen (Umlaute/Sonderzeichen → Slug-Form).
            created = client.post(base, json=_resource_body("Mein Rünbook!"), headers=auth)
            assert created.status_code == 201, created.text
            assert created.json()["slug"] == "mein-runbook"

            # Slug rundtrippt ueber Get + List.
            rid = created.json()["id"]
            assert client.get(f"{base}/{rid}", headers=auth).json()["slug"] == "mein-runbook"
            listed = client.get(base, headers=auth).json()
            assert any(r["id"] == rid and r["slug"] == "mein-runbook" for r in listed)

            # Expliziter Slug wird uebernommen.
            explicit = client.post(
                base,
                json={**_resource_body("Anderer Name"), "slug": "eigener-slug"},
                headers=auth,
            )
            assert explicit.status_code == 201, explicit.text
            assert explicit.json()["slug"] == "eigener-slug"

            # Kollision (gleicher abgeleiteter Slug) → 409.
            dup = client.post(base, json=_resource_body("Mein Rünbook!"), headers=auth)
            assert dup.status_code == 409, dup.text
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_resource_list_exposes_sub_resource_children(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}/resources"
    try:
        with TestClient(app) as client:
            parent = client.post(base, json=_resource_body("Parent"), headers=auth).json()["id"]
            child_a = client.post(
                base, json=_resource_body("Kind A", blocks=[_block("a1", "Inhalt A")]), headers=auth
            ).json()["id"]
            child_b = client.post(base, json=_resource_body("Kind B"), headers=auth).json()["id"]
            # Kind A auf active promoten → variabler Status gegenueber Kind B (draft).
            _promote(client, base, child_a, auth)

            linked = client.put(
                f"{base}/{parent}/sub_resources",
                json={
                    "links": [
                        {"child_id": child_a, "position": 0, "link_scope": "resource"},
                        {"child_id": child_b, "position": 1, "link_scope": "resource"},
                    ]
                },
                headers=auth,
            )
            assert linked.status_code == 200, linked.text

            listed = client.get(base, headers=auth).json()
            parent_row = next(r for r in listed if r["id"] == parent)
            assert parent_row["sub_resource_count"] == 2
            subs = parent_row["sub_resources"]
            assert [s["id"] for s in subs] == [child_a, child_b]
            assert [s["name"] for s in subs] == ["Kind A", "Kind B"]
            # Status + Version der jeweils aktuellen Kind-Version.
            assert subs[0]["status"] == "active" and subs[0]["version"] == 1
            assert subs[1]["status"] == "draft" and subs[1]["version"] == 1
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_token_read_exposes_expires_at(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent = client.post(f"{base}/agents", json={"name": "Bound"}, headers=auth)
            assert agent.status_code == 201, agent.text
            agent_id = agent.json()["id"]

            expires = datetime.now(UTC) + timedelta(days=7)
            created = client.post(
                f"{base}/tokens",
                json={
                    "name": "befristet",
                    "agent_id": agent_id,
                    "expires_at": expires.isoformat(),
                },
                headers=auth,
            )
            assert created.status_code == 201, created.text
            assert created.json()["expires_at"] is not None

            # expires_at rundtrippt auch ueber die Liste.
            tokens = client.get(f"{base}/tokens", headers=auth).json()
            row = next(t for t in tokens if t["id"] == created.json()["id"])
            assert row["expires_at"] is not None
            assert datetime.fromisoformat(row["expires_at"]).date() == expires.date()

            # Ein ungebundener/ablaufloser Token traegt expires_at=None.
            agent2 = client.post(f"{base}/agents", json={"name": "NoExp"}, headers=auth).json()
            plain = client.post(
                f"{base}/tokens",
                json={"name": "ohne", "agent_id": agent2["id"]},
                headers=auth,
            )
            assert plain.status_code == 201, plain.text
            assert plain.json()["expires_at"] is None
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_duplicate_persona_resource_and_system_prompt(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            # --- Persona (kein Slug) -----------------------------------------
            persona = client.post(
                f"{base}/personas", json=_persona_body("Coach", "orig-profil"), headers=auth
            ).json()
            dup_p = client.post(f"{base}/personas/{persona['id']}/duplicate", headers=auth)
            assert dup_p.status_code == 201, dup_p.text
            body_p = dup_p.json()
            assert body_p["id"] != persona["id"]
            assert body_p["name"] == "Coach (Kopie)"
            assert body_p["current_version"] == 1
            assert body_p["current_status"] == "draft"
            assert body_p["content"]["description"] == "orig-profil"

            # --- Resource (frischer eindeutiger Slug) ------------------------
            resource = client.post(
                f"{base}/resources", json=_resource_body("Doku", "orig-doku"), headers=auth
            ).json()
            dup_r = client.post(f"{base}/resources/{resource['id']}/duplicate", headers=auth)
            assert dup_r.status_code == 201, dup_r.text
            body_r = dup_r.json()
            assert body_r["id"] != resource["id"]
            assert body_r["name"] == "Doku (Kopie)"
            assert body_r["current_status"] == "draft" and body_r["current_version"] == 1
            assert body_r["content"]["description"] == "orig-doku"
            assert body_r["slug"] != resource["slug"]
            assert re.match(r"^[a-z0-9][a-z0-9-]*$", body_r["slug"])

            # --- System-Prompt-Template (frischer eindeutiger Slug) ----------
            tpl = client.post(
                f"{base}/system-prompts",
                json=_template_body("Support", "Body-Original"),
                headers=auth,
            ).json()
            dup_t = client.post(f"{base}/system-prompts/{tpl['id']}/duplicate", headers=auth)
            assert dup_t.status_code == 201, dup_t.text
            body_t = dup_t.json()
            assert body_t["id"] != tpl["id"]
            assert body_t["name"] == "Support (Kopie)"
            assert body_t["current_status"] == "draft" and body_t["current_version"] == 1
            assert body_t["content"]["body"] == "Body-Original"
            assert body_t["slug"] != tpl["slug"]
            assert re.match(r"^[a-z0-9][a-z0-9-]*$", body_t["slug"])
    finally:
        cleanup_workspaces([owner])


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_migration_0064_backfill_dedups_within_workspace() -> None:
    """Backfill (Migration 0064) fuellt slug-lose Bestandsrows eindeutig auf.

    Simuliert den Vor-Migrations-Zustand in einer zurueckgerollten Transaktion:
    Constraints loesen, drei gleichnamige + eine sonderzeichen-only Row ohne Slug
    einfuegen, die ECHTE Migration ausfuehren und die Slug-Invarianten pruefen.
    Die Transaktion wird verworfen — die geteilte Test-DB bleibt unveraendert.
    """
    owner = fresh_user_id()
    ws = setup_workspace(owner)

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.execute("DROP INDEX IF EXISTS resource_workspace_slug_uniq")
            await conn.execute("ALTER TABLE resource ALTER COLUMN slug DROP NOT NULL")
            for _ in range(3):
                await conn.execute(
                    "INSERT INTO resource (workspace_id, owner_id, name, slug) "
                    "VALUES ($1, $2, $3, NULL)",
                    ws,
                    owner,
                    "Meine Notiz!!!",
                )
            await conn.execute(
                "INSERT INTO resource (workspace_id, owner_id, name, slug) "
                "VALUES ($1, $2, $3, NULL)",
                ws,
                owner,
                "***",  # slugifiziert leer → Fallback 'resource'
            )
            sql = (MIGRATIONS_DIR / "0064_resource_slug.sql").read_text()
            await conn.execute(sql)

            rows = await conn.fetch(
                "SELECT slug FROM resource WHERE workspace_id = $1 AND slug IS NOT NULL",
                ws,
            )
            slugs = [r["slug"] for r in rows]
            # Alle valide + workspace-eindeutig (sonst waere die UNIQUE-Recreate
            # oben schon gescheitert).
            assert all(re.match(r"^[a-z0-9][a-z0-9-]*$", s) for s in slugs), slugs
            assert len(slugs) == len(set(slugs)), slugs
            assert "meine-notiz" in slugs  # erster Treffer behaelt den Basis-Slug
            assert sum(s.startswith("meine-notiz-") for s in slugs) == 2  # Duplikate suffigiert
            assert "resource" in slugs  # Sonderzeichen-only → Fallback
        finally:
            await tx.rollback()
            await conn.close()

    try:
        asyncio.run(_run())
    finally:
        cleanup_workspaces([owner])
