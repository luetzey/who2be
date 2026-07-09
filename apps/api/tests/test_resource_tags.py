"""Integrationstest fuer `GET /v1/workspaces/{ws}/resources/tags` (ADR-0041, Phase 3).

Belegt die in Phase 3 vom Web-Contract-Test aufgedeckte und behobene Luecke:
das Frontend (`ResourceEditorForm` → TagInput) ruft `resources/tags` auf, der
Endpoint fehlte serverseitig. DISTINCT-sortierte, workspace-isolierte Tag-Liste —
Quelle ist `resource_version.content->'tags'` der jeweils aktuellen Version.

Nutzt bewusst die **zentralen conftest-Fixtures** (``patched_jwt_secret``,
``migrated_db``, ``make_auth_headers``) statt des frueher duplizierten Bootstraps
(ADR-0041, Phase 0).
"""

from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace


def _block(block_id: str, text: str) -> dict[str, object]:
    return {
        "id": block_id,
        "type": "paragraph",
        "props": {},
        "content": [{"type": "text", "text": text, "styles": {}}],
        "children": [],
    }


def _resource_body(name: str, tags: list[str]) -> dict[str, object]:
    return {
        "name": name,
        "content": {"description": name, "blocks": [_block("b1", name)], "tags": tags},
    }


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_resource_tags_distinct_sorted_and_workspace_scoped(
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = fresh_user_id()
    other = fresh_user_id()
    ws = setup_workspace(owner)
    other_ws = setup_workspace(other)
    auth = make_auth_headers(owner)
    other_auth = make_auth_headers(other)
    base = f"/v1/workspaces/{ws}/resources"
    other_base = f"/v1/workspaces/{other_ws}/resources"

    try:
        with TestClient(app) as client:
            for tags in [["beta", "alpha"], ["beta", "gamma"], [], ["alpha"]]:
                resp = client.post(
                    base,
                    json=_resource_body(f"R-{','.join(tags) or 'none'}", tags),
                    headers=auth,
                )
                assert resp.status_code == 201, resp.text

            # Fremder Workspace: eigener Tag, darf nicht durchschlagen.
            client.post(other_base, json=_resource_body("Other", ["delta"]), headers=other_auth)

            resp = client.get(f"{base}/tags", headers=auth)
            assert resp.status_code == 200, resp.text
            assert resp.json() == ["alpha", "beta", "gamma"]

            # Workspace-Isolation: fremder Workspace sieht nur seine Tags.
            assert client.get(f"{other_base}/tags", headers=other_auth).json() == ["delta"]

            # Nicht-Mitglied wird vor dem Lookup geblockt (403).
            assert client.get(f"{base}/tags", headers=other_auth).status_code == 403
    finally:
        cleanup_workspaces([owner, other])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_resource_tags_empty_for_fresh_workspace(
    make_auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)

    try:
        with TestClient(app) as client:
            resp = client.get(f"/v1/workspaces/{ws}/resources/tags", headers=auth)
            assert resp.status_code == 200
            assert resp.json() == []
    finally:
        cleanup_workspaces([owner])
