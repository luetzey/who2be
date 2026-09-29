"""Versions-UUID in den fuenf `*VersionRead` (Lernschleife B5-Vorarbeit, ADR-0053 3.2/6.2).

Pruefbericht (`GET /versions/{entity_type}/{version_id}/test-report`) und
Prueflaeufe (`POST /test-runs`, `subject_version_id`) adressieren eine Version
ueber ihre UUID. Die Web-App bekommt Versionen aber nur ueber die Versions-
Endpunkte der Elemente — die muessen die UUID also mitliefern.

Je Elementart geprueft: Liste, Detail und die Transition-Antwort tragen `id`,
und sie ist exakt die UUID der DB-Zeile `<entity>_version.id` (nicht die der
Identitaets-Zeile). Zum Schluss adressiert die gelieferte `id` den
Pruefbericht — der Pfad, fuer den das Feld existiert.
"""

import asyncio
from collections.abc import Callable, Iterator
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

# entity_type -> (URL-Segment, Versionstabelle, FK-Spalte, Create-Body ohne Namen).
# Die Bodies fuellen die Promote-Pflichtfelder, damit `draft -> review` geht.
_BLOCKS = [{"id": "b1", "type": "paragraph", "content": [{"type": "text", "text": "Inhalt"}]}]
_KINDS: dict[str, tuple[str, str, str, dict[str, Any]]] = {
    "persona": (
        "personas",
        "persona_version",
        "persona_id",
        {"content": {"description": "d", "content": {"blocks": _BLOCKS}}},
    ),
    "playbook": (
        "playbooks",
        "playbook_version",
        "playbook_id",
        {
            "content": {
                "description": "d",
                "body": "1. Schritt.",
                "type": "workflow",
                "tags": [],
                "triggers": "t",
            }
        },
    ),
    "resource": (
        "resources",
        "resource_version",
        "resource_id",
        {"content": {"description": "d", "blocks": _BLOCKS, "tags": []}},
    ),
    "system_prompt_template": (
        "system-prompts",
        "system_prompt_template_version",
        "template_id",
        {"content": {"description": "d", "body": "Du bist ein Test-Agent."}},
    ),
    "external_tool": ("external_tools", "external_tool_version", "external_tool_id", {}),
}
_TYPES = list(_KINDS)


def _db_version_ids(table: str, fk: str, entity_id: str) -> dict[int, str]:
    """`version -> id` direkt aus der Versionstabelle (die Wahrheit)."""

    sql = f"SELECT version, id FROM {table} WHERE {fk} = $1"

    async def _run() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return list(await conn.fetch(sql, UUID(entity_id)))
        finally:
            await conn.close()

    return {int(r["version"]): str(r["id"]) for r in asyncio.run(_run())}


class _Ws:
    def __init__(self, client: TestClient, ws: UUID, auth: dict[str, str]) -> None:
        self.client = client
        self.base = f"/v1/workspaces/{ws}"
        self.auth = auth

    def get(self, path: str) -> Any:
        res = self.client.get(f"{self.base}{path}", headers=self.auth)
        assert res.status_code == 200, res.text
        return res.json()

    def post(self, path: str, body: dict[str, Any], expected: int = 200) -> Any:
        res = self.client.post(f"{self.base}{path}", json=body, headers=self.auth)
        assert res.status_code == expected, res.text
        return res.json()


@pytest.fixture
def ws(
    migrated_db: None,
    patched_jwt_secret: str,
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> Iterator[_Ws]:
    owner = fresh_user_id()
    workspace = setup_workspace(owner)
    try:
        with TestClient(app) as client:
            yield _Ws(client, workspace, make_auth_headers(owner))
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.parametrize("entity_type", _TYPES)
def test_version_endpoints_carry_the_version_row_uuid(ws: _Ws, entity_type: str) -> None:
    segment, table, fk, body = _KINDS[entity_type]
    entity_id = str(ws.post(f"/{segment}", {"name": f"V-{uuid4().hex[:6]}", **body}, 201)["id"])
    truth = _db_version_ids(table, fk, entity_id)
    assert set(truth) == {1}

    listed = ws.get(f"/{segment}/{entity_id}/versions")
    assert [(v["version"], v["id"]) for v in listed] == [(1, truth[1])]
    # Die Versions-UUID ist NICHT die Element-UUID — genau die Verwechslung,
    # die der Pruefbericht mit 404 quittieren wuerde.
    assert truth[1] != entity_id

    detail = ws.get(f"/{segment}/{entity_id}/versions/1")
    assert detail["id"] == truth[1]
    # Additiv: die bisherigen Felder bleiben unveraendert da.
    assert {"version", "status", "locale", "content", "created_by", "created_at"} <= set(detail)

    moved = ws.post(f"/{segment}/{entity_id}/versions/1/transition", {"to": "review"})
    assert moved["status"] == "review"
    assert moved["id"] == truth[1]

    report = ws.get(f"/versions/{entity_type}/{detail['id']}/test-report")
    assert report["version_id"] == truth[1]
    assert report["entity_type"] == entity_type
