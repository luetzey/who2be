"""Integrationstests fuer WorkArea-Artifacts (ADR-0047, WP4 — Spec A+E).

Kritische Invarianten:
- CRUD-Roundtrip: Block-Split mit serverseitigen 8-stelligen Ankern,
  Markdown-Read mit ``[#block_id]``-Annotation, `?anchor=` liefert nur den
  Block, Delete raeumt auch die Chunks ab (FK CASCADE).
- Nebenlaeufigkeit (Spec A): zwei Patches mit derselben `expected_rev` —
  der zweite bekommt 409 `rev_conflict` MIT der aktuellen rev im detail;
  Appends sind lockfrei (beide gewinnen, rev +2).
- Privat-Isolation (Spec E): das private Artifact eines Agenten ist fuer
  einen zweiten Agenten unsichtbar (GET 404, Area-Liste ohne die Area),
  fuer den Menschen (editor+) voll sichtbar, fuer viewer nicht.
- Capability-Gate: Agent ohne `workarea_write` → 403 `missing_capability`;
  Read-Grant ohne Write-Grant → 403 `area_forbidden`;
  Mensch ohne area_id → 422 (keine private Area).
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, grant, shared_area
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

_GHOST = "00000000-0000-0000-0000-000000000000"


def _add_member(workspace_id: UUID, user_id: UUID, role: str = "editor") -> None:
    import asyncio

    import asyncpg

    from who2be_api.core.config import get_settings

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, $3) "
                "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role",
                workspace_id,
                user_id,
                role,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _create(
    client: TestClient,
    prefix: str,
    headers: dict[str, str],
    area_id: str | None,
    **overrides: Any,
) -> Any:
    body: dict[str, Any] = {
        "title": "Notiz",
        "content_md": "# Kapitel\n\nErster Absatz.",
        "occurred_at": "2026-08-01T12:00:00Z",
    }
    body.update(overrides)
    url = f"{prefix}/artifacts" if area_id is None else f"{prefix}/work-areas/{area_id}/artifacts"
    return client.post(url, json=body, headers=headers)


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_crud_roundtrip_mit_ankern(make_auth_headers: AuthFactory) -> None:
    """create → read (Anker-Markdown) → anchor-Read → append → patch → list →
    delete; unbekannter Anker → 422 `anchor_unresolvable`."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Roundtrip")

            created = _create(client, prefix, auth, area_id)
            assert created.status_code == 201, created.text
            artifact = created.json()
            assert artifact["type"] == "doc" and artifact["rev"] == 1
            blocks = artifact["blocks"]
            assert [b["kind"] for b in blocks] == ["heading", "paragraph"]
            assert all(len(b["block_id"]) == 8 for b in blocks)
            artifact_id = artifact["id"]
            heading_id, paragraph_id = blocks[0]["block_id"], blocks[1]["block_id"]

            # Read: Markdown mit Anker-Annotation.
            read = client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=auth)
            assert read.status_code == 200, read.text
            markdown = read.json()["markdown"]
            assert f"# Kapitel [#{heading_id}]" in markdown
            assert f"Erster Absatz. [#{paragraph_id}]" in markdown

            # Anchor-Read: NUR der adressierte Block.
            single = client.get(
                f"{prefix}/wa-artifacts/{artifact_id}",
                params={"anchor": paragraph_id},
                headers=auth,
            )
            assert single.status_code == 200
            assert single.json()["markdown"] == f"Erster Absatz. [#{paragraph_id}]"
            assert "# Kapitel" not in single.json()["markdown"]

            # Unbekannter Anker → 422 mit Taxonomie-Reason.
            missing = client.get(
                f"{prefix}/wa-artifacts/{artifact_id}", params={"anchor": "gibtsnich"}, headers=auth
            )
            assert missing.status_code == 422
            assert missing.json()["reason"] == "anchor_unresolvable"

            # Append: rev+1, neue Bloecke hinten dran.
            appended = client.post(
                f"{prefix}/wa-artifacts/{artifact_id}/append",
                json={"content_md": "Angehaengter Absatz."},
                headers=auth,
            )
            assert appended.status_code == 200, appended.text
            assert appended.json()["rev"] == 2
            assert [b["md"] for b in appended.json()["blocks"]][-1] == "Angehaengter Absatz."

            # Patch (replace): Anker-ID bleibt stabil, rev+1.
            patched = client.patch(
                f"{prefix}/wa-artifacts/{artifact_id}",
                json={
                    "anchor": paragraph_id,
                    "op": "replace",
                    "content_md": "Ersetzter Absatz.",
                    "expected_rev": 2,
                },
                headers=auth,
            )
            assert patched.status_code == 200, patched.text
            assert patched.json()["rev"] == 3
            replaced = [b for b in patched.json()["blocks"] if b["block_id"] == paragraph_id]
            assert [b["md"] for b in replaced] == ["Ersetzter Absatz."]

            # Patch mit unbekanntem Anker → 422.
            bad_patch = client.patch(
                f"{prefix}/wa-artifacts/{artifact_id}",
                json={"anchor": "gibtsnich", "op": "delete", "expected_rev": 3},
                headers=auth,
            )
            assert bad_patch.status_code == 422
            assert bad_patch.json()["reason"] == "anchor_unresolvable"

            # Liste: Metadaten ohne Blocks.
            listed = client.get(f"{prefix}/work-areas/{area_id}/artifacts", headers=auth)
            assert listed.status_code == 200
            assert [a["id"] for a in listed.json()] == [artifact_id]
            assert listed.json()[0]["blocks"] is None

            # Delete: 204, danach 404 (Chunks raeumt der FK CASCADE ab).
            assert (
                client.delete(f"{prefix}/wa-artifacts/{artifact_id}", headers=auth).status_code
                == 204
            )
            assert (
                client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=auth).status_code == 404
            )
            assert client.get(f"{prefix}/wa-artifacts/{_GHOST}", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_parallele_patches_und_lockfreie_appends(make_auth_headers: AuthFactory) -> None:
    """Spec A: zwei Patches mit derselben `expected_rev` — der zweite bekommt
    409 `rev_conflict` mit der AKTUELLEN rev im detail. Appends sind lockfrei:
    beide gewinnen (rev +2), die Reihenfolge ist egal."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Nebenlaeufigkeit")
            created = _create(client, prefix, auth, area_id, content_md="Basis-Absatz.")
            artifact_id = created.json()["id"]
            anchor = created.json()["blocks"][0]["block_id"]

            def patch(md: str) -> Any:
                return client.patch(
                    f"{prefix}/wa-artifacts/{artifact_id}",
                    json={
                        "anchor": anchor,
                        "op": "replace",
                        "content_md": md,
                        "expected_rev": 1,
                    },
                    headers=auth,
                )

            first = patch("Gewinner-Absatz.")
            assert first.status_code == 200, first.text
            assert first.json()["rev"] == 2

            second = patch("Verlierer-Absatz.")
            assert second.status_code == 409, second.text
            problem = second.json()
            assert problem["reason"] == "rev_conflict"
            # Die AKTUELLE rev steht im detail — der Agent kann direkt neu
            # lesen und aufsetzen.
            assert "aktuelle rev=2" in problem["detail"]

            # Appends brauchen keine expected_rev und kollidieren nie.
            for md in ("Append eins.", "Append zwei."):
                res = client.post(
                    f"{prefix}/wa-artifacts/{artifact_id}/append",
                    json={"content_md": md},
                    headers=auth,
                )
                assert res.status_code == 200, res.text
            after = client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=auth).json()
            assert after["rev"] == 4  # 2 (Patch) + 2 Appends
            assert "Append eins." in after["markdown"]
            assert "Append zwei." in after["markdown"]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_private_isolation_zwischen_agenten(make_auth_headers: AuthFactory) -> None:
    """Spec E: privates Artifact von Agent A ist fuer Agent B unsichtbar
    (GET 404, Area unsichtbar, Area-Liste der Artifacts 404 — kein
    Existenz-Leak); Mensch editor+ sieht alles, viewer nichts Privates."""
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, role="viewer")
    auth = make_auth_headers(owner)
    viewer_auth = make_auth_headers(viewer)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            _, a_tok = agent_token(client, prefix, "wa-priv-a", {"workarea_write": True}, auth)
            _, b_tok = agent_token(client, prefix, "wa-priv-b", {"workarea_write": True}, auth)

            # A legt ohne area_id an → private Area (Auto-Anlage).
            created = _create(client, prefix, a_tok, None, content_md="Privates Material.")
            assert created.status_code == 201, created.text
            artifact_id = created.json()["id"]
            private_area_id = created.json()["area_id"]

            # A liest sein eigenes Artifact.
            assert (
                client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=a_tok).status_code == 200
            )

            # B: GET → 404 (nicht 403 — kein Existenz-Orakel).
            assert (
                client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=b_tok).status_code == 404
            )
            # B: Artifact-Liste der fremden privaten Area → 404, Area-Liste leer.
            assert (
                client.get(
                    f"{prefix}/work-areas/{private_area_id}/artifacts", headers=b_tok
                ).status_code
                == 404
            )
            b_areas = client.get(f"{prefix}/work-areas", headers=b_tok).json()
            assert private_area_id not in {a["id"] for a in b_areas}
            # B darf das fremde private Artifact auch nicht veraendern/loeschen.
            assert (
                client.post(
                    f"{prefix}/wa-artifacts/{artifact_id}/append",
                    json={"content_md": "B war hier."},
                    headers=b_tok,
                ).status_code
                == 404
            )
            assert (
                client.delete(f"{prefix}/wa-artifacts/{artifact_id}", headers=b_tok).status_code
                == 404
            )

            # Mensch editor+ sieht das private Artifact (Transparenz-Prinzip).
            owner_read = client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=auth)
            assert owner_read.status_code == 200
            assert "Privates Material." in owner_read.json()["markdown"]
            owner_list = client.get(
                f"{prefix}/work-areas/{private_area_id}/artifacts", headers=auth
            )
            assert owner_list.status_code == 200
            assert [a["id"] for a in owner_list.json()] == [artifact_id]

            # Viewer: nur shared Areas lesbar → 404 auf privates Material.
            assert (
                client.get(f"{prefix}/wa-artifacts/{artifact_id}", headers=viewer_auth).status_code
                == 404
            )
            assert (
                client.get(
                    f"{prefix}/work-areas/{private_area_id}/artifacts", headers=viewer_auth
                ).status_code
                == 404
            )
    finally:
        cleanup_workspaces([owner, viewer])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_capability_und_grant_gates(make_auth_headers: AuthFactory) -> None:
    """Agent ohne `workarea_write` → 403 `missing_capability`; Read-Grant ohne
    Write-Grant → 403 `area_forbidden`; ohne Grant → 404; Mensch ohne
    area_id → 422 (keine private Area); viewer darf nicht schreiben."""
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, role="viewer")
    auth = make_auth_headers(owner)
    viewer_auth = make_auth_headers(viewer)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = shared_area(client, prefix, auth, "Gate-Area")

            # Agent OHNE workarea_write: Schreiben 403 — auch in die (nicht
            # existente) private Area, das Capability-Gate feuert zuerst.
            no_cap_id, no_cap = agent_token(client, prefix, "wa-nocap", {}, auth)
            grant(client, prefix, auth, area_id, no_cap_id, "write")
            blocked = _create(client, prefix, no_cap, area_id)
            assert blocked.status_code == 403
            assert blocked.json()["reason"] == "missing_capability"
            assert _create(client, prefix, no_cap, None).status_code == 403

            # Agent MIT Capability, aber nur Read-Grant: 403 area_forbidden.
            ro_id, ro_tok = agent_token(client, prefix, "wa-ro", {"workarea_write": True}, auth)
            grant(client, prefix, auth, area_id, ro_id, "read")
            forbidden = _create(client, prefix, ro_tok, area_id)
            assert forbidden.status_code == 403
            assert forbidden.json()["reason"] == "area_forbidden"
            # Lesen darf er: die Liste der Area ist erreichbar (leer).
            listed = client.get(f"{prefix}/work-areas/{area_id}/artifacts", headers=ro_tok)
            assert listed.status_code == 200 and listed.json() == []

            # Agent MIT Capability, aber ganz ohne Grant: 404 (kein Leak).
            _, no_grant = agent_token(client, prefix, "wa-nogrant", {"workarea_write": True}, auth)
            assert _create(client, prefix, no_grant, area_id).status_code == 404

            # Mensch ohne area_id: 422 — Menschen haben keine private Area.
            human_private = _create(client, prefix, auth, None)
            assert human_private.status_code == 422

            # Viewer (Mensch) darf nirgends schreiben: 403 via Rollen-Gate.
            assert _create(client, prefix, viewer_auth, area_id).status_code == 403
    finally:
        cleanup_workspaces([owner, viewer])
