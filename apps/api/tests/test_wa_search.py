"""Integrationstests fuer die WorkArea-Suche (ADR-0047, WP6 — Spec C).

Kritische Invarianten:
- Treffer = Anker + Snippet, NIE das Dokument: jeder `anchor`
  (``<artifact_id>#<block_id>``) ist direkt
  ``GET /wa-artifacts/{id}?anchor=``-faehig (End-to-End verifiziert).
- Scope-Filter IN der SQL (Spec E): Agent ohne Grants → 0 Treffer, 0 Titel,
  0 Snippets; Agent mit Grant nur auf Area A → nur A-Treffer; Mensch editor+
  sieht alles (auch private Agent-Areas); viewer nur shared Areas.
- `area_id`-Filter; ausserhalb des Lese-Scopes leer (kein Existenz-Orakel).
- Snippet-Kappung: langes Dokument → Snippet << Dokumentlaenge.
- Chunk-Sync (WP4): nach einem Patch, der den Suchbegriff entfernt, findet
  die Suche nichts mehr.
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.workspace_setup import (
    cleanup_workspaces,
    fresh_user_id,
    setup_workspace,
)

AuthFactory = Callable[[UUID], dict[str, str]]

_GHOST = "00000000-0000-0000-0000-000000000000"


def _agent_token(
    client: TestClient, prefix: str, name: str, policy: dict[str, object], auth: dict[str, str]
) -> tuple[str, dict[str, str]]:
    agent = client.post(
        f"{prefix}/agents", json={"name": name, "tool_policy": policy}, headers=auth
    )
    assert agent.status_code == 201, agent.text
    agent_id = agent.json()["id"]
    token = client.post(f"{prefix}/tokens", json={"name": name, "agent_id": agent_id}, headers=auth)
    assert token.status_code == 201, token.text
    return agent_id, {"Authorization": f"Bearer {token.json()['token']}"}


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


def _shared_area(client: TestClient, prefix: str, auth: dict[str, str], name: str) -> str:
    created = client.post(f"{prefix}/work-areas", json={"name": name}, headers=auth)
    assert created.status_code == 201, created.text
    area_id: str = created.json()["id"]
    return area_id


def _grant(
    client: TestClient, prefix: str, auth: dict[str, str], area_id: str, agent_id: str, level: str
) -> None:
    res = client.put(
        f"{prefix}/work-areas/{area_id}/grants/{agent_id}", json={"level": level}, headers=auth
    )
    assert res.status_code == 200, res.text


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


def _search(client: TestClient, prefix: str, headers: dict[str, str], q: str, **params: Any) -> Any:
    res = client.get(f"{prefix}/workarea-search", params={"q": q, **params}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_treffer_mit_anker_und_snippet_end_to_end(make_auth_headers: AuthFactory) -> None:
    """Treffer nach create_artifact traegt Anker + Titel + Snippet + Score;
    der Anker liefert via ``GET /wa-artifacts/{id}?anchor=`` GENAU den einen
    Block (End-to-End). Query-Validierung: q fehlt/leer → 422, limit > 50 → 422."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "Falterkunde")
            created = _create(
                client,
                prefix,
                auth,
                area_id,
                title="Zitronenfalter-Notiz",
                content_md="Der Zitronenfalter ueberwintert als erwachsener Falter.",
            )
            assert created.status_code == 201, created.text
            artifact_id = created.json()["id"]
            block_id = created.json()["blocks"][0]["block_id"]

            hits = _search(client, prefix, auth, "Zitronenfalter")
            assert len(hits) == 1
            hit = hits[0]
            assert hit["anchor"] == f"{artifact_id}#{block_id}"
            assert hit["artifact_id"] == artifact_id
            assert hit["block_id"] == block_id
            assert hit["title"] == "Zitronenfalter-Notiz"
            assert "Zitronenfalter" in hit["snippet"]
            assert hit["score"] > 0
            assert hit["area_id"] == area_id

            # End-to-End: der Anker aus dem Treffer liefert GENAU den Block.
            single = client.get(
                f"{prefix}/wa-artifacts/{hit['artifact_id']}",
                params={"anchor": hit["block_id"]},
                headers=auth,
            )
            assert single.status_code == 200, single.text
            assert single.json()["markdown"] == (
                f"Der Zitronenfalter ueberwintert als erwachsener Falter. [#{block_id}]"
            )

            # Nicht vorhandener Begriff: leeres Ergebnis, kein Fehler.
            assert _search(client, prefix, auth, "Blauwal") == []

            # Router-Validierung: q ist Pflicht (1..200), limit max. 50.
            assert client.get(f"{prefix}/workarea-search", headers=auth).status_code == 422
            assert (
                client.get(f"{prefix}/workarea-search", params={"q": ""}, headers=auth).status_code
                == 422
            )
            assert (
                client.get(
                    f"{prefix}/workarea-search",
                    params={"q": "Zitronenfalter", "limit": 51},
                    headers=auth,
                ).status_code
                == 422
            )
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_agent_scope_filter_in_sql(make_auth_headers: AuthFactory) -> None:
    """Spec E: Agent ohne Grants → 0 Treffer/Titel/Snippets, obwohl der
    Begriff existiert; Agent mit Grant nur auf Area A → ausschliesslich
    A-Treffer; Mensch editor+ sieht beide Areas."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_a = _shared_area(client, prefix, auth, "Alpen")
            area_b = _shared_area(client, prefix, auth, "Baltikum")
            for area_id, title in ((area_a, "Alpen-Wanderkarte"), (area_b, "Ostsee-Wanderkarte")):
                res = _create(
                    client,
                    prefix,
                    auth,
                    area_id,
                    title=title,
                    content_md="Die Wanderkarte zeigt alle markierten Routen.",
                )
                assert res.status_code == 201, res.text

            # Agent mit read-Grant NUR auf A: ausschliesslich A-Treffer.
            granted_id, granted_tok = _agent_token(client, prefix, "wa-search-a", {}, auth)
            _grant(client, prefix, auth, area_a, granted_id, "read")
            hits = _search(client, prefix, granted_tok, "Wanderkarte")
            assert {h["area_id"] for h in hits} == {area_a}
            assert {h["title"] for h in hits} == {"Alpen-Wanderkarte"}

            # Agent OHNE Grants: 0 Treffer — keine Titel, keine Snippets.
            _, none_tok = _agent_token(client, prefix, "wa-search-none", {}, auth)
            assert _search(client, prefix, none_tok, "Wanderkarte") == []

            # Mensch editor+: unbeschraenkt, beide Areas.
            editor_hits = _search(client, prefix, auth, "Wanderkarte")
            assert {h["area_id"] for h in editor_hits} == {area_a, area_b}
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_viewer_sieht_nur_shared_areas(make_auth_headers: AuthFactory) -> None:
    """viewer findet nur Material aus shared Areas; das private Artifact eines
    Agenten bleibt fuer ihn unsichtbar — der Mensch editor+ findet beides."""
    owner = fresh_user_id()
    viewer = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, role="viewer")
    auth = make_auth_headers(owner)
    viewer_auth = make_auth_headers(viewer)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            shared_id = _shared_area(client, prefix, auth, "Gemeinsam")
            res = _create(
                client,
                prefix,
                auth,
                shared_id,
                title="Team-Steinpilz",
                content_md="Der Steinpilz waechst im Fichtenwald.",
            )
            assert res.status_code == 201, res.text

            # Agent legt ohne area_id an → private Area (Auto-Anlage).
            _, agent_tok = _agent_token(
                client, prefix, "wa-search-priv", {"workarea_write": True}, auth
            )
            private = _create(
                client,
                prefix,
                agent_tok,
                None,
                title="Privater Steinpilz",
                content_md="Geheime Steinpilz-Fundstelle am Nordhang.",
            )
            assert private.status_code == 201, private.text
            private_area_id = private.json()["area_id"]

            # viewer: nur der shared Treffer.
            viewer_hits = _search(client, prefix, viewer_auth, "Steinpilz")
            assert {h["area_id"] for h in viewer_hits} == {shared_id}
            assert {h["title"] for h in viewer_hits} == {"Team-Steinpilz"}

            # editor+: beide Treffer, auch aus der privaten Agent-Area.
            owner_hits = _search(client, prefix, auth, "Steinpilz")
            assert {h["area_id"] for h in owner_hits} == {shared_id, private_area_id}
    finally:
        cleanup_workspaces([owner, viewer])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_area_id_filter_ohne_existenz_orakel(make_auth_headers: AuthFactory) -> None:
    """`area_id` schraenkt auf eine Area ein; eine unbekannte oder nicht
    lesbare Area liefert schlicht `[]` (kein Existenz-Orakel)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_a = _shared_area(client, prefix, auth, "Filter-A")
            area_b = _shared_area(client, prefix, auth, "Filter-B")
            for area_id, title in ((area_a, "Moorlehrpfad A"), (area_b, "Moorlehrpfad B")):
                res = _create(
                    client,
                    prefix,
                    auth,
                    area_id,
                    title=title,
                    content_md="Der Moorlehrpfad beginnt am Parkplatz.",
                )
                assert res.status_code == 201, res.text

            # Editor mit area_id-Filter: nur die eine Area.
            hits = _search(client, prefix, auth, "Moorlehrpfad", area_id=area_a)
            assert {h["area_id"] for h in hits} == {area_a}
            assert {h["title"] for h in hits} == {"Moorlehrpfad A"}

            # Unbekannte Area: leer, kein Fehler.
            assert _search(client, prefix, auth, "Moorlehrpfad", area_id=_GHOST) == []

            # Agent mit Grant nur auf A, Filter auf (existierende) Area B:
            # leer — von einer unbekannten Area nicht unterscheidbar.
            granted_id, granted_tok = _agent_token(client, prefix, "wa-filter", {}, auth)
            _grant(client, prefix, auth, area_a, granted_id, "read")
            assert _search(client, prefix, granted_tok, "Moorlehrpfad", area_id=area_b) == []
            in_scope = _search(client, prefix, granted_tok, "Moorlehrpfad", area_id=area_a)
            assert {h["area_id"] for h in in_scope} == {area_a}
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_snippet_kappung_und_chunk_sync_nach_patch(make_auth_headers: AuthFactory) -> None:
    """Langes Dokument → Snippet bleibt weit unter der Dokumentlaenge (Anker
    + Kostprobe, nie der Volltext). Nach einem Patch, der den Begriff
    entfernt, liefert die Suche 0 Treffer (Chunk-Sync-Wirkung, WP4)."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            area_id = _shared_area(client, prefix, auth, "Snippets")
            filler = "Der Bergwald liegt still im Morgennebel und wartet. " * 30
            long_md = f"{filler}Mitten im Text steht der Feuersalamander. {filler}".strip()
            created = _create(
                client,
                prefix,
                auth,
                area_id,
                title="Langtext",
                content_md=long_md,
            )
            assert created.status_code == 201, created.text
            artifact_id = created.json()["id"]
            block_id = created.json()["blocks"][0]["block_id"]

            hits = _search(client, prefix, auth, "Feuersalamander")
            assert len(hits) == 1
            snippet = hits[0]["snippet"]
            assert len(snippet) <= 200
            assert len(long_md) > 10 * len(snippet)

            # Patch entfernt den Begriff → der Chunk-Sync (WP4) baut die
            # Passagen neu, die Suche findet nichts mehr.
            patched = client.patch(
                f"{prefix}/wa-artifacts/{artifact_id}",
                json={
                    "anchor": block_id,
                    "op": "replace",
                    "content_md": "Nur noch harmloser Bergwald ohne Lurche.",
                    "expected_rev": 1,
                },
                headers=auth,
            )
            assert patched.status_code == 200, patched.text
            assert _search(client, prefix, auth, "Feuersalamander") == []
    finally:
        cleanup_workspaces([owner])
