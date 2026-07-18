"""REST↔MCP-Paritaets-Contract an der Adapter-Naht (ADR-0041 Phase 3 Punkt 8; Audit TST-4).

Der MCP-Server ist ein duenner httpx-Adapter (`who2be_mcp.client.ApiClient`)
ueber dieselbe REST-API. Der Vertrag an der Naht: der MCP-Tool-Pfad
(agent-gebundener `w2b_`-Token ohne Write-Capabilities) sieht ausschliesslich
die `status='active'`-Version — nie Draft/Review — und liefert feldweise exakt
das, was der REST-Endpoint auf demselben Token-Pfad liefert.

Aufbau je Kernelement (Persona / Playbook / Resource):

1. Seed ueber die REST-API: v1 anlegen, draft→review→active promoten, dann
   PUT → Draft v2 mit abweichendem Inhalt (active UND draft existieren).
2. Kontroll-Read REST als Mensch (JWT): sieht die Current-Version = Draft v2.
3. Read REST (`w2b_`-Token) und MCP-Tool-Pfad (`ApiClient.get_*`, wie ihn
   `fetch_playbook`/`fetch_resource`/`get_persona` im MCP-Server nutzen) —
   feldweiser Vergleich der beiden Antworten.
4. Active-only-Vertrag: der MCP-Pfad liefert v1/active mit dem v1-Inhalt,
   verankert gegen den REST-Versions-Snapshot; der Draft leakt nicht.

Beide Pfade laufen gegen DIESELBE App-Instanz via `httpx.ASGITransport` auf
EINEM Event-Loop (App-Lifespan manuell ueber `app.router.lifespan_context`):
`TestClient` wuerde den asyncpg-Pool auf dem Loop seines Portal-Threads
erzeugen, waehrend der MCP-Client auf dem Test-Loop laeuft — der geteilte
Loop vermeidet den Cross-Loop-Konflikt.

Nutzt die zentralen conftest-Fixtures (``patched_jwt_secret``, ``migrated_db``,
``make_auth_headers``) statt Inline-Bootstrap (Audit TST-10).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

import httpx
import pytest

from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_mcp.client import ApiClient
from who2be_models import (
    ExternalToolContent,
    ExternalToolCreate,
    ExternalToolRead,
    ExternalToolUpdate,
    PersonaRead,
    PlaybookRead,
    ResourceRead,
    VersionStatus,
    VersionTransitionRequest,
)

# Unterschiedliche Inhalte fuer active v1 und draft v2 — daran haengt der
# Nachweis, dass der MCP-Pfad den Draft nicht sieht.
_ACTIVE_DESC = "Paritaet: aktiver v1-Inhalt"
_DRAFT_DESC = "Paritaet: Draft-v2-Inhalt (darf via MCP nie sichtbar sein)"

# BlockNote-kompatible Bodies (Pflichtfelder laut Promote-Validator).
_PERSONA_BLOCKS = [
    {
        "id": "b1",
        "type": "paragraph",
        "content": [{"type": "text", "text": "Parity persona body.", "styles": {}}],
    }
]
_RESOURCE_BLOCKS = [
    {
        "id": "h1",
        "type": "heading",
        "props": {"level": 1},
        "content": [{"type": "text", "text": "Parity Section", "styles": {}}],
    },
    {
        "id": "p1",
        "type": "paragraph",
        "content": [{"type": "text", "text": "Parity resource content.", "styles": {}}],
    },
]


def _persona_body(description: str) -> dict[str, object]:
    return {
        "name": "[Parity] Persona",
        "content": {
            "description": description,
            "system_prompt": "Be precise.",
            "traits": ["thorough"],
            "content": {"description": description, "blocks": _PERSONA_BLOCKS},
        },
    }


def _playbook_body(description: str) -> dict[str, object]:
    return {
        "name": "[Parity] Playbook",
        "content": {
            "description": description,
            "body": "1. Step one. 2. Step two.",
            "type": "workflow",
            "tags": ["parity"],
            "triggers": "parity-trigger",
        },
    }


def _resource_body(description: str) -> dict[str, object]:
    return {
        "name": "[Parity] Resource",
        "content": {"description": description, "blocks": _RESOURCE_BLOCKS},
    }


_AnyRead = PersonaRead | PlaybookRead | ResourceRead


@dataclass(frozen=True)
class _Case:
    """Ein Kernelement der Naht: REST-Pfad, Seed-Body, Read-Model, MCP-Read."""

    plural: str
    make_body: Callable[[str], dict[str, object]]
    read_model: type[PersonaRead] | type[PlaybookRead] | type[ResourceRead]
    # Der MCP-Tool-Pfad: exakt die ApiClient-Methode, die das jeweilige
    # MCP-Tool (get_persona / fetch_playbook / fetch_resource) aufruft.
    mcp_read: Callable[[ApiClient, UUID], Awaitable[_AnyRead]]


_CASES: dict[str, _Case] = {
    "persona": _Case(
        plural="personas",
        make_body=_persona_body,
        read_model=PersonaRead,
        mcp_read=lambda mcp, eid: mcp.get_persona(str(eid)),
    ),
    "playbook": _Case(
        plural="playbooks",
        make_body=_playbook_body,
        read_model=PlaybookRead,
        mcp_read=lambda mcp, eid: mcp.get_playbook(eid),
    ),
    "resource": _Case(
        plural="resources",
        make_body=_resource_body,
        read_model=ResourceRead,
        mcp_read=lambda mcp, eid: mcp.get_resource(eid),
    ),
}


@pytest.mark.contract
@pytest.mark.integration
@pytest.mark.parametrize("kind", sorted(_CASES))
def test_mcp_read_matches_rest_and_sees_only_active(
    kind: str,
    patched_jwt_secret: str,
    migrated_db: None,
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    case = _CASES[kind]
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    jwt_headers = make_auth_headers(owner_id)

    async def _run() -> None:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as rest:
                prefix = f"/v1/workspaces/{ws}"
                base = f"{prefix}/{case.plural}"

                # 1. Seed via REST: v1 → active, danach PUT → Draft v2.
                created = await rest.post(
                    base, json=case.make_body(_ACTIVE_DESC), headers=jwt_headers
                )
                assert created.status_code == 201, created.text
                eid = UUID(created.json()["id"])
                for target in ("review", "active"):
                    moved = await rest.post(
                        f"{base}/{eid}/versions/1/transition",
                        json={"to": target},
                        headers=jwt_headers,
                    )
                    assert moved.status_code == 200, moved.text
                drafted = await rest.put(
                    f"{base}/{eid}", json=case.make_body(_DRAFT_DESC), headers=jwt_headers
                )
                assert drafted.status_code in (200, 201), drafted.text

                # 2. Kontrolle: der Mensch (JWT) arbeitet auf der Current-Version
                #    und sieht den Draft v2 — der Unterschied zum MCP-Pfad unten
                #    ist der eigentliche Vertrag.
                human = await rest.get(f"{base}/{eid}", headers=jwt_headers)
                assert human.status_code == 200, human.text
                human_body = human.json()
                assert human_body["current_version"] == 2
                assert human_body["current_status"] == "draft"
                assert human_body["content"]["description"] == _DRAFT_DESC

                # 3. Konsum-Agent + agent-gebundener Token = der MCP-Auth-Pfad.
                #    Read-Scope `all` (sonst 404 fuer Unzugewiesenes), Writes
                #    bleiben Default-aus → `sees_drafts` ist False.
                agent = await rest.post(
                    f"{prefix}/agents",
                    json={
                        "name": "[Parity] Konsum-Agent",
                        "tool_policy": {"playbook_read": "all", "resource_read": "all"},
                    },
                    headers=jwt_headers,
                )
                assert agent.status_code == 201, agent.text
                token_resp = await rest.post(
                    f"{prefix}/tokens",
                    json={"name": "parity", "agent_id": agent.json()["id"]},
                    headers=jwt_headers,
                )
                assert token_resp.status_code == 201, token_resp.text
                token: str = token_resp.json()["token"]

                # 4. Dieselbe Entitaet auf beiden Pfaden lesen: roher
                #    REST-Endpoint vs. MCP-Tool-Pfad (ApiClient).
                rest_read = await rest.get(
                    f"{base}/{eid}", headers={"Authorization": f"Bearer {token}"}
                )
                assert rest_read.status_code == 200, rest_read.text
                mcp = ApiClient(
                    base_url="http://testserver",
                    token=token,
                    workspace_id=ws,
                    transport=transport,
                )
                mcp_read = await case.mcp_read(mcp, eid)

                # 5. Feldweiser Vergleich ueber ALLE Model-Felder — jede
                #    Abweichung nennt das driftende Feld.
                rest_model = case.read_model.model_validate(rest_read.json())
                assert type(mcp_read) is case.read_model
                for field in case.read_model.model_fields:
                    assert getattr(mcp_read, field) == getattr(rest_model, field), (
                        f"REST↔MCP-Drift im Feld '{field}' ({kind})"
                    )

                # 6. Active-only-Vertrag: der MCP-Pfad sieht NUR v1/active —
                #    verankert gegen den unveraenderlichen Versions-Snapshot.
                assert mcp_read.current_version == 1
                assert mcp_read.current_status == VersionStatus.active
                assert mcp_read.content.description == _ACTIVE_DESC
                assert mcp_read.content.description != human_body["content"]["description"]
                versions = await rest.get(f"{base}/{eid}/versions", headers=jwt_headers)
                assert versions.status_code == 200, versions.text
                active_snapshot = next(v for v in versions.json() if v["status"] == "active")
                assert active_snapshot["version"] == 1
                assert mcp_read.content.description == (active_snapshot["content"]["description"])

    try:
        asyncio.run(_run())
    finally:
        cleanup_workspaces([owner_id])


# ---------------------------------------------------------------------------
# ExternalTool-Aggregat (WP-3): eigener Contract-Test statt Aufnahme in
# `_CASES` oben — `ExternalToolContent` hat kein `description`-Feld, an dem
# der generische `test_mcp_read_matches_rest_and_sees_only_active`-Koerper
# hart haengt. Deckt Read-Paritaet (UUID UND Alias) + den Write-Pfad
# (create/update/transition/restore) beidseitig ab.
# ---------------------------------------------------------------------------


def _external_tool_body(usage_notes: str) -> dict[str, object]:
    return {
        "name": "[Parity] Todoist",
        "alias": "parity-todo",
        "content": {
            "display_name": "Todoist",
            "mcp_server_name": "Todoist MCP",
            "tool_names": ["add_task", "list_tasks"],
            "usage_notes": usage_notes,
            "tags": ["parity"],
        },
    }


def _external_tool_update_body(usage_notes: str) -> dict[str, object]:
    # `ExternalToolUpdate` (PUT) hat KEIN `alias`-Feld (extra="forbid", Alias ist
    # nach dem Create unveraenderlich) — eigener Body ohne den Create-Schluessel.
    body = _external_tool_body(usage_notes)
    del body["alias"]
    return body


@pytest.mark.contract
@pytest.mark.integration
def test_mcp_external_tool_read_matches_rest_and_sees_only_active(
    patched_jwt_secret: str,
    migrated_db: None,
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    jwt_headers = make_auth_headers(owner_id)

    async def _run() -> None:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as rest:
                prefix = f"/v1/workspaces/{ws}"
                base = f"{prefix}/external_tools"

                created = await rest.post(
                    base, json=_external_tool_body("Aktive Hinweise."), headers=jwt_headers
                )
                assert created.status_code == 201, created.text
                eid = UUID(created.json()["id"])
                for target in ("review", "active"):
                    moved = await rest.post(
                        f"{base}/{eid}/versions/1/transition",
                        json={"to": target},
                        headers=jwt_headers,
                    )
                    assert moved.status_code == 200, moved.text
                drafted = await rest.put(
                    f"{base}/{eid}",
                    json=_external_tool_update_body(
                        "Draft-Hinweise (darf via MCP nie sichtbar sein)."
                    ),
                    headers=jwt_headers,
                )
                assert drafted.status_code in (200, 201), drafted.text

                # Konsum-Agent: external_tool_read='all' (Default), keine Writes
                # -> sees_drafts=False -> MCP-Pfad sieht nur die aktive Version.
                agent = await rest.post(
                    f"{prefix}/agents",
                    json={"name": "[Parity] ExternalTool-Konsum-Agent", "tool_policy": {}},
                    headers=jwt_headers,
                )
                assert agent.status_code == 201, agent.text
                token_resp = await rest.post(
                    f"{prefix}/tokens",
                    json={"name": "parity-external-tool", "agent_id": agent.json()["id"]},
                    headers=jwt_headers,
                )
                assert token_resp.status_code == 201, token_resp.text
                token: str = token_resp.json()["token"]

                rest_read = await rest.get(
                    f"{base}/{eid}", headers={"Authorization": f"Bearer {token}"}
                )
                assert rest_read.status_code == 200, rest_read.text
                mcp = ApiClient(
                    base_url="http://testserver", token=token, workspace_id=ws, transport=transport
                )
                # UUID-Pfad (get_external_tool) UND Alias-Pfad (resolve_external_tool)
                # muessen identisch zum REST-Read sein.
                mcp_by_id = await mcp.get_external_tool(eid)
                mcp_by_alias = await mcp.resolve_external_tool("parity-todo")

                rest_model = ExternalToolRead.model_validate(rest_read.json())
                for field in ExternalToolRead.model_fields:
                    assert getattr(mcp_by_id, field) == getattr(rest_model, field), (
                        f"REST↔MCP-Drift im Feld '{field}' (external_tool, UUID-Pfad)"
                    )
                    assert getattr(mcp_by_alias, field) == getattr(rest_model, field), (
                        f"REST↔MCP-Drift im Feld '{field}' (external_tool, Alias-Pfad)"
                    )

                # Active-only-Vertrag: der Draft-Inhalt (v2) leakt nicht.
                assert mcp_by_id.current_version == 1
                assert mcp_by_id.current_status == VersionStatus.active
                assert mcp_by_id.content.usage_notes == "Aktive Hinweise."

    try:
        asyncio.run(_run())
    finally:
        cleanup_workspaces([owner_id])


@pytest.mark.contract
@pytest.mark.integration
def test_mcp_external_tool_write_path_matches_rest(
    patched_jwt_secret: str,
    migrated_db: None,
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    """Write-Pfad (create/update/transition/restore) via MCP-`ApiClient`, spiegelt
    denselben Zustand wie der aequivalente REST-Aufruf (editor-Token mit
    `external_tool_write` + `promote_retire`)."""
    owner_id = fresh_user_id()
    ws = setup_workspace(owner_id)
    jwt_headers = make_auth_headers(owner_id)

    async def _run() -> None:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as rest:
                prefix = f"/v1/workspaces/{ws}"
                base = f"{prefix}/external_tools"

                agent = await rest.post(
                    f"{prefix}/agents",
                    json={
                        "name": "[Parity] ExternalTool-Builder-Agent",
                        "tool_policy": {"external_tool_write": True, "promote_retire": True},
                    },
                    headers=jwt_headers,
                )
                assert agent.status_code == 201, agent.text
                token_resp = await rest.post(
                    f"{prefix}/tokens",
                    json={"name": "parity-external-tool-write", "agent_id": agent.json()["id"]},
                    headers=jwt_headers,
                )
                assert token_resp.status_code == 201, token_resp.text
                token: str = token_resp.json()["token"]
                mcp = ApiClient(
                    base_url="http://testserver", token=token, workspace_id=ws, transport=transport
                )

                created = await mcp.create_external_tool(
                    ExternalToolCreate(
                        name="[Parity] MCP-Write Todoist",
                        content=ExternalToolContent(display_name="Todoist", usage_notes="v1"),
                    )
                )
                rest_get = await rest.get(f"{base}/{created.id}", headers=jwt_headers)
                assert rest_get.status_code == 200, rest_get.text
                assert rest_get.json()["content"]["usage_notes"] == "v1"

                # v1 muss erst aktiv sein, bevor PUT eine neue Draft (v2) anlegt
                # (`draft_exists`-409, solange v1 selbst noch draft ist).
                for target in (VersionStatus.review, VersionStatus.active):
                    await mcp.transition_external_tool_version(
                        created.id, 1, VersionTransitionRequest(to=target)
                    )

                updated = await mcp.update_external_tool(
                    created.id,
                    ExternalToolUpdate(
                        content=ExternalToolContent(display_name="Todoist", usage_notes="v2")
                    ),
                )
                assert updated.content.usage_notes == "v2"
                assert updated.current_version == 2
                rest_get = await rest.get(f"{base}/{created.id}", headers=jwt_headers)
                assert rest_get.json()["content"]["usage_notes"] == "v2"
                assert rest_get.json()["current_status"] == "draft"

                for target in (VersionStatus.review, VersionStatus.active):
                    await mcp.transition_external_tool_version(
                        created.id, 2, VersionTransitionRequest(to=target)
                    )
                rest_get = await rest.get(f"{base}/{created.id}", headers=jwt_headers)
                assert rest_get.json()["current_status"] == "active"
                assert rest_get.json()["current_version"] == 2

                restored = await mcp.restore_external_tool_version(created.id, 1)
                assert restored.content.usage_notes == "v1"
                assert restored.current_version == 3
                rest_get = await rest.get(f"{base}/{created.id}", headers=jwt_headers)
                assert rest_get.json()["content"]["usage_notes"] == "v1"
                assert rest_get.json()["current_status"] == "draft"
                assert rest_get.json()["current_version"] == 3

    try:
        asyncio.run(_run())
    finally:
        cleanup_workspaces([owner_id])
