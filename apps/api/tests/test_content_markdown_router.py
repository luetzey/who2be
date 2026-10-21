"""Integrationstest Markdown-Schreibweg (ADR-0058 §6, §9 P2).

Belegt ueber HTTP gegen die echte DB:

- **Pflichtfall §9 P2.6:** `source` lesen, Autosave ueber PATCH `…/draft`,
  danach PATCH `…/markdown` mit altem `base_rev` → 409 `version_conflict`,
  der Draft bleibt unveraendert. Dasselbe fuer PUT.
- **RBAC:** Viewer liest `format=source`, schreibt nicht (403); ein Agent ohne
  Schreib-Capability schreibt nicht; Editor/Owner schreibt.
- **Tag-Scope (ADR-0039):** ein auf `support` beschraenkter Agent legt per
  Markdown kein `legal`-Playbook an und uebernimmt kein bestehendes.
- **Verwaltete Inhalte:** lesbar, Schreiben 403 `managed_aggregate`.
- **Anker:** unbekannter Anker 422 `anchor_unknown` (PUT und PATCH), doppelter
  Anker 422 `anchor_duplicate`, Ueberschrift ohne Anker bekommt eine neue ID.
- **Zuordnung:** Bloecke ohne Anker gehoeren zum vorangehenden Abschnitt.
- **`usage_notes`** des externen Tools ueberstehen Schreiben und Lesen.
- **Anlegen per Markdown** inkl. System-Prompt (eigene Route, Write-Rate).
- **`format=full`/`format=text`:** der JSON-GET bleibt bitgleich ueber
  einen Markdown-Lesevorgang; ein unveraenderter PUT laesst den Body
  bitgleich.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Iterator
from typing import Any
from uuid import UUID

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.db import init_connection
from who2be_api.main import app
from who2be_api.repositories.external_tool_repository import PgExternalToolRepository
from who2be_api.repositories.persona_repository import PgPersonaRepository
from who2be_api.repositories.playbook_repository import PgPlaybookRepository
from who2be_api.repositories.resource_repository import PgResourceRepository
from who2be_api.repositories.system_prompt_template_repository import (
    PgSystemPromptTemplateRepository,
)
from who2be_api.repositories.versioned_repository import (
    BaseRevConflictError,
    expected_base_rev,
)
from who2be_api.testing.api_helpers import agent_token
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import (
    ExternalToolContent,
    PersonaVersionContent,
    PlaybookContent,
    ResourceContent,
    SystemPromptTemplateContent,
    WorkspaceRole,
)

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = pytest.mark.integration

_BODY = "# Titel\n\nEinleitung.\n\n## Schritte\n\n- eins\n- zwei\n\n## Ende\n\nSchluss."


def _anchor(markdown: str, heading: str) -> str:
    match = re.search(rf"^#+ {re.escape(heading)} \[#([^\]]+)\]$", markdown, re.M)
    assert match is not None, markdown
    return match.group(1)


def _add_member(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> None:
    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, $3) "
                "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role",
                workspace_id,
                user_id,
                role.value,
            )
        finally:
            await conn.close()

    asyncio.run(_run())


def _managed_playbook_id(ws: UUID) -> str:
    async def _run() -> str:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return str(
                await conn.fetchval(
                    "SELECT id FROM playbook WHERE workspace_id = $1 AND is_managed "
                    "ORDER BY created_at LIMIT 1",
                    ws,
                )
            )
        finally:
            await conn.close()

    return asyncio.run(_run())


class _Env:
    def __init__(self, client: TestClient, ws: UUID, owner: dict[str, str]) -> None:
        self.client = client
        self.ws = ws
        self.owner = owner
        self.base = f"/v1/workspaces/{ws}"

    def create(self, et: str, body: dict[str, Any], auth: dict[str, str] | None = None) -> Any:
        res = self.client.post(f"{self.base}/{et}/markdown", json=body, headers=auth or self.owner)
        assert res.status_code == 201, res.text
        return res.json()

    def source(self, et: str, eid: str, auth: dict[str, str] | None = None) -> Any:
        res = self.client.get(
            f"{self.base}/{et}/{eid}/markdown?format=source", headers=auth or self.owner
        )
        assert res.status_code == 200, res.text
        return res.json()

    def activate(self, et: str, eid: str, version: int = 1) -> None:
        url = f"{self.base}/{et}/{eid}/versions/{version}/transition"
        for target in ("review", "active"):
            res = self.client.post(url, json={"to": target}, headers=self.owner)
            assert res.status_code == 200, res.text


@pytest.fixture
def env(
    patched_jwt_secret: str, migrated_db: None, make_auth_headers: AuthFactory
) -> Iterator[_Env]:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    try:
        with TestClient(app) as client:
            yield _Env(client, ws, make_auth_headers(owner))
    finally:
        cleanup_workspaces([owner])


def _playbook(name: str = "Markdown-Playbook", tags: list[str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "content": {"description": "d", "body": _BODY, "type": "workflow", "tags": tags or []},
    }


# --- Konfliktschutz (ADR-0058 §6.3, Pflichtfall §9 P2.6) ----------------------


def test_patch_with_stale_base_rev_after_autosave_is_409_and_draft_unchanged(env: _Env) -> None:
    created = env.create("playbooks", _playbook())
    pid = created["id"]
    src = env.source("playbooks", pid)
    anchor = _anchor(src["content"]["body"], "Schritte")

    # Ein Mensch speichert im Web-Editor (Autosave, gleiche Versionsnummer).
    full = env.client.get(f"{env.base}/playbooks/{pid}", headers=env.owner).json()
    full["content"]["description"] = "vom Menschen"
    autosave = env.client.patch(
        f"{env.base}/playbooks/{pid}/draft",
        json={"content": full["content"]},
        headers=env.owner,
    )
    assert autosave.status_code == 200, autosave.text
    before = env.client.get(f"{env.base}/playbooks/{pid}", headers=env.owner).json()
    assert before["current_version"] == src["version"]

    stale = env.client.patch(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"base_rev": src["base_rev"], "op": "delete", "anchor": anchor},
        headers=env.owner,
    )
    assert stale.status_code == 409, stale.text
    problem = stale.json()
    assert problem["reason"] == "version_conflict"
    assert problem["params"]["current_version"] == src["version"]
    assert problem["params"]["current_base_rev"] == env.source("playbooks", pid)["base_rev"]
    after = env.client.get(f"{env.base}/playbooks/{pid}", headers=env.owner).json()
    assert after["content"] == before["content"]


def test_put_with_stale_base_rev_is_409_version_conflict(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    env.activate("playbooks", pid)
    src = env.source("playbooks", pid)
    assert src["status"] == "active"

    # Jemand schreibt dazwischen (neuer Draft auf der aktiven Version).
    first = env.client.put(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"base_rev": src["base_rev"], "content": {**src["content"], "description": "a"}},
        headers=env.owner,
    )
    assert first.status_code == 200, first.text
    assert first.json()["base_rev"] != src["base_rev"]

    stale = env.client.put(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"base_rev": src["base_rev"], "content": {**src["content"], "description": "b"}},
        headers=env.owner,
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["reason"] == "version_conflict"
    assert env.source("playbooks", pid)["content"]["description"] == "a"


def test_successive_patches_chain_on_returned_base_rev(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    src = env.source("playbooks", pid)
    rev = src["base_rev"]
    for text in ("Erste Aenderung.", "Zweite Aenderung."):
        res = env.client.patch(
            f"{env.base}/playbooks/{pid}/markdown",
            json={
                "base_rev": rev,
                "op": "replace",
                "anchor": _anchor(src["content"]["body"], "Ende"),
                "markdown": f"## Ende\n\n{text}",
            },
            headers=env.owner,
        )
        assert res.status_code == 200, res.text
        rev = res.json()["base_rev"]
    final = env.source("playbooks", pid)
    assert final["base_rev"] == rev
    assert final["version"] == 1  # Teilaenderung arbeitet auf dem offenen Draft
    assert "Zweite Aenderung." in final["content"]["body"]
    assert "Erste Aenderung." not in final["content"]["body"]


# --- Anker und Zuordnung (ADR-0058 §4.2, §4.3, §6.1 B) ------------------------


def test_section_replace_keeps_anchor_and_owns_following_blocks(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    src = env.source("playbooks", pid)
    body = src["content"]["body"]
    steps = _anchor(body, "Schritte")
    end = _anchor(body, "Ende")

    res = env.client.patch(
        f"{env.base}/playbooks/{pid}/markdown",
        json={
            "base_rev": src["base_rev"],
            "op": "replace",
            "anchor": steps,
            # Ueberschrift ohne Anker erbt die ID der ersetzten.
            "markdown": "## Neue Schritte\n\nNur noch ein Absatz.",
        },
        headers=env.owner,
    )
    assert res.status_code == 200, res.text
    new_body = res.json()["content"]["body"]
    # Liste ohne Anker gehoerte zum Abschnitt und ist mit ihm ersetzt.
    assert "- eins" not in new_body
    assert _anchor(new_body, "Neue Schritte") == steps
    # Der Folgeabschnitt bleibt mit Anker und Inhalt stehen.
    assert _anchor(new_body, "Ende") == end
    assert "Schluss." in new_body
    assert "Einleitung." in new_body


def test_delete_section_removes_heading_and_its_blocks(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    src = env.source("playbooks", pid)
    res = env.client.patch(
        f"{env.base}/playbooks/{pid}/markdown",
        json={
            "base_rev": src["base_rev"],
            "op": "delete",
            "anchor": _anchor(src["content"]["body"], "Schritte"),
        },
        headers=env.owner,
    )
    assert res.status_code == 200, res.text
    body = res.json()["content"]["body"]
    assert "Schritte" not in body and "- zwei" not in body
    assert "Schluss." in body


def test_unknown_anchor_is_422_on_put_and_patch(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    src = env.source("playbooks", pid)
    put = env.client.put(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"content": {**src["content"], "body": "# Erfunden [#erfunden1]\n\nText."}},
        headers=env.owner,
    )
    # Vollstand auf offenem Draft waere 409 draft_conflict; die Anker-Pruefung
    # laeuft vorher, das 422 kommt also vor jedem Schreibversuch.
    assert put.status_code == 422, put.text
    assert put.json()["reason"] == "anchor_unknown"
    assert put.json()["params"]["field"] == "body"

    patch = env.client.patch(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"base_rev": src["base_rev"], "op": "delete", "anchor": "erfunden1"},
        headers=env.owner,
    )
    assert patch.status_code == 422, patch.text
    assert patch.json()["reason"] == "anchor_unknown"

    field = env.client.patch(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"base_rev": src["base_rev"], "op": "replace", "field": "gibtsnicht", "markdown": "x"},
        headers=env.owner,
    )
    assert field.status_code == 422, field.text
    assert field.json()["reason"] == "anchor_unknown"


def test_anchor_on_create_is_unknown_and_duplicate_is_rejected(env: _Env) -> None:
    created = env.client.post(
        f"{env.base}/playbooks/markdown",
        json={"name": "Kopie", "content": {"body": "# Kopiert [#abc123]\n\nText."}},
        headers=env.owner,
    )
    assert created.status_code == 422, created.text
    assert created.json()["reason"] == "anchor_unknown"

    pid = env.create("playbooks", _playbook())["id"]
    src = env.source("playbooks", pid)
    steps = _anchor(src["content"]["body"], "Schritte")
    dup = env.client.patch(
        f"{env.base}/playbooks/{pid}/markdown",
        json={
            "base_rev": src["base_rev"],
            "op": "replace",
            "field": "body",
            "markdown": f"## A [#{steps}]\n\nx\n\n## B [#{steps}]\n\ny",
        },
        headers=env.owner,
    )
    assert dup.status_code == 422, dup.text
    assert dup.json()["reason"] == "anchor_duplicate"


def test_heading_without_anchor_gets_new_id(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    src = env.source("playbooks", pid)
    old_ids = set(re.findall(r"\[#([^\]]+)\]", src["content"]["body"]))
    res = env.client.patch(
        f"{env.base}/playbooks/{pid}/markdown",
        json={
            "base_rev": src["base_rev"],
            "op": "insert_after",
            "anchor": _anchor(src["content"]["body"], "Ende"),
            "markdown": "## Anhang\n\nNeu.",
        },
        headers=env.owner,
    )
    assert res.status_code == 200, res.text
    new_anchor = _anchor(res.json()["content"]["body"], "Anhang")
    assert new_anchor not in old_ids


def test_unsupported_markdown_is_422(env: _Env) -> None:
    res = env.client.post(
        f"{env.base}/playbooks/markdown",
        json={"name": "Tabelle", "content": {"body": "| a | b |\n| --- | --- |\n| 1 | 2 |"}},
        headers=env.owner,
    )
    assert res.status_code == 422, res.text
    assert res.json()["reason"] == "markdown_unsupported"


# --- RBAC und Tag-Scope -------------------------------------------------------


def test_viewer_reads_source_but_cannot_write(env: _Env, make_auth_headers: AuthFactory) -> None:
    viewer = fresh_user_id()
    _add_member(env.ws, viewer, WorkspaceRole.viewer)
    vauth = make_auth_headers(viewer)
    editor = fresh_user_id()
    _add_member(env.ws, editor, WorkspaceRole.editor)
    eauth = make_auth_headers(editor)
    try:
        pid = env.create("playbooks", _playbook())["id"]
        src = env.source("playbooks", pid, vauth)
        assert src["base_rev"] is not None

        denied = [
            env.client.post(f"{env.base}/playbooks/markdown", json=_playbook("V"), headers=vauth),
            env.client.put(
                f"{env.base}/playbooks/{pid}/markdown",
                json={"content": src["content"]},
                headers=vauth,
            ),
            env.client.patch(
                f"{env.base}/playbooks/{pid}/markdown",
                json={"base_rev": src["base_rev"], "op": "delete", "field": "body"},
                headers=vauth,
            ),
        ]
        assert [r.status_code for r in denied] == [403, 403, 403], [r.text for r in denied]

        ok = env.client.patch(
            f"{env.base}/playbooks/{pid}/markdown",
            json={
                "base_rev": src["base_rev"],
                "op": "replace",
                "field": "body",
                "markdown": "# Vom Editor",
            },
            headers=eauth,
        )
        assert ok.status_code == 200, ok.text
    finally:
        cleanup_workspaces([viewer, editor])


def test_agent_without_write_capability_cannot_write(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    env.activate("playbooks", pid)  # Agenten sehen Entwuerfe nicht
    _, tok = agent_token(
        env.client, env.base, "Leser", {"playbook_read": "all"}, env.owner, role="editor"
    )
    src = env.source("playbooks", pid, tok)
    assert src["status"] == "active"
    res = env.client.patch(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"base_rev": src["base_rev"], "op": "delete", "field": "body"},
        headers=tok,
    )
    assert res.status_code == 403, res.text
    created = env.client.post(f"{env.base}/playbooks/markdown", json=_playbook("A"), headers=tok)
    assert created.status_code == 403, created.text


def test_agent_read_scope_hides_unassigned_playbook(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    _, tok = agent_token(
        env.client, env.base, "Eng", {"playbook_read": "assigned"}, env.owner, role="editor"
    )
    res = env.client.get(f"{env.base}/playbooks/{pid}/markdown?format=source", headers=tok)
    assert res.status_code in {403, 404}, res.text
    # Gleiche Antwort wie der JSON-GET: der Markdown-Weg oeffnet nichts zusaetzlich.
    json_get = env.client.get(f"{env.base}/playbooks/{pid}", headers=tok)
    assert json_get.status_code == res.status_code


def test_write_tags_scope_applies_to_markdown_writes(env: _Env) -> None:
    _, tok = agent_token(
        env.client,
        env.base,
        "Support",
        {"playbook_read": "all", "playbook_write": True, "write_tags": {"playbook": ["support"]}},
        env.owner,
        role="editor",
    )
    ok = env.client.post(
        f"{env.base}/playbooks/markdown", json=_playbook("S", ["support"]), headers=tok
    )
    assert ok.status_code == 201, ok.text
    blocked = env.client.post(
        f"{env.base}/playbooks/markdown", json=_playbook("L", ["legal"]), headers=tok
    )
    assert blocked.status_code == 403, blocked.text

    legal = env.create("playbooks", _playbook("Owner-Legal", ["legal"]))["id"]
    src = env.source("playbooks", legal, tok)
    takeover = env.client.patch(
        f"{env.base}/playbooks/{legal}/markdown",
        json={"base_rev": src["base_rev"], "op": "replace", "field": "body", "markdown": "x"},
        headers=tok,
    )
    assert takeover.status_code == 403, takeover.text
    put = env.client.put(
        f"{env.base}/playbooks/{legal}/markdown",
        json={"content": {**src["content"], "tags": ["support"]}},
        headers=tok,
    )
    assert put.status_code == 403, put.text


# --- Verwaltete Inhalte -------------------------------------------------------


def test_managed_content_is_readable_but_not_writable(env: _Env) -> None:
    pid = _managed_playbook_id(env.ws)
    src = env.source("playbooks", pid)
    assert src["content"]["body"]
    patch = env.client.patch(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"base_rev": src["base_rev"], "op": "replace", "field": "body", "markdown": "x"},
        headers=env.owner,
    )
    assert patch.status_code == 403, patch.text
    assert patch.json()["reason"] == "managed_aggregate"
    put = env.client.put(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"content": src["content"]},
        headers=env.owner,
    )
    assert put.status_code == 403, put.text
    assert put.json()["reason"] == "managed_aggregate"


# --- Elementarten -------------------------------------------------------------


def test_external_tool_usage_notes_roundtrip(env: _Env) -> None:
    notes = "## Wann [#placeholder]\n\nVor jedem **Termin** pruefen.\n\n- Liste\n- zwei"
    created = env.client.post(
        f"{env.base}/external_tools/markdown",
        json={
            "name": "Kalender",
            "content": {
                "display_name": "Kalender",
                "tool_names": ["list_events"],
                "usage_notes": notes.replace(" [#placeholder]", ""),
            },
        },
        headers=env.owner,
    )
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    src = env.source("external_tools", tid)
    written = src["content"]["usage_notes"]
    anchor = _anchor(written, "Wann")
    assert written == notes.replace("placeholder", anchor).replace("- Liste\n", "- Liste\n\n")

    # Zurueckschreiben (Vollstand ueber einen Patch auf das Feld) und erneut lesen.
    res = env.client.patch(
        f"{env.base}/external_tools/{tid}/markdown",
        json={
            "base_rev": src["base_rev"],
            "op": "replace",
            "field": "usage_notes",
            "markdown": written,
        },
        headers=env.owner,
    )
    assert res.status_code == 200, res.text
    assert res.json()["base_rev"] == src["base_rev"]  # unveraendert = bitgleich
    assert env.source("external_tools", tid)["content"]["usage_notes"] == written


def test_persona_mode_field_edit(env: _Env) -> None:
    created = env.create(
        "personas",
        {
            "name": "Markdown-Persona",
            "content": {
                "profile": "# Rolle\n\nHilft.",
                "modes": [{"name": "Recherche", "is_default": True, "anti_patterns": "Raten."}],
            },
        },
    )
    pid = created["id"]
    src = env.source("personas", pid)
    res = env.client.patch(
        f"{env.base}/personas/{pid}/markdown",
        json={
            "base_rev": src["base_rev"],
            "op": "replace",
            "field": "modes[Recherche].anti_patterns",
            "markdown": "Nie raten.",
        },
        headers=env.owner,
    )
    assert res.status_code == 200, res.text
    mode = res.json()["content"]["modes"][0]
    assert mode["anti_patterns"] == "Nie raten."
    assert res.json()["content"]["profile"].startswith("# Rolle [#")


def test_resource_allows_tables_and_reports_dangling_refs_shape(env: _Env) -> None:
    created = env.create(
        "resources",
        {"name": "Tabelle", "content": {"body": "# Daten\n\n| a | b |\n| --- | --- |\n| 1 | 2 |"}},
    )
    assert "| a | b |" in created["content"]["body"]
    assert created["dangling_refs"] == []


def test_deleted_heading_reports_dangling_refs_from_playbook_and_resource(env: _Env) -> None:
    child = env.create(
        "resources",
        {"name": "Kind", "content": {"body": "# Bleibt\n\nA.\n\n## Weg\n\nB."}},
    )
    cid = child["id"]
    gone = _anchor(child["content"]["body"], "Weg")
    kept = _anchor(child["content"]["body"], "Bleibt")
    playbook = env.create("playbooks", _playbook("Verweist"))
    parent = env.create("resources", {"name": "Eltern", "content": {"body": "# X\n\nY."}})

    # Gespeicherte Verweise auf die Ueberschrift, die gleich verschwindet,
    # plus einer auf eine bleibende (darf nicht gemeldet werden).
    links = env.client.put(
        f"{env.base}/playbooks/{playbook['id']}/resource_links",
        json={
            "links": [
                {"resource_id": cid, "block_id": gone, "position": 0},
                {"resource_id": cid, "block_id": kept, "position": 1},
            ]
        },
        headers=env.owner,
    )
    assert links.status_code == 200, links.text
    subs = env.client.put(
        f"{env.base}/resources/{parent['id']}/sub_resources",
        json={"links": [{"child_id": cid, "block_id": gone, "link_scope": "block"}]},
        headers=env.owner,
    )
    assert subs.status_code == 200, subs.text

    src = env.source("resources", cid)
    res = env.client.patch(
        f"{env.base}/resources/{cid}/markdown",
        json={"base_rev": src["base_rev"], "op": "delete", "anchor": gone},
        headers=env.owner,
    )
    assert res.status_code == 200, res.text
    refs = sorted(
        (r["source_type"], r["source_id"], r["block_id"]) for r in res.json()["dangling_refs"]
    )
    assert refs == [("playbook", playbook["id"], gone), ("resource", parent["id"], gone)]


def test_system_prompt_create_and_patch(env: _Env) -> None:
    created = env.client.post(
        f"{env.base}/system-prompts/markdown",
        json={"name": "MD-Prompt", "content": {"body": "# Rolle\n\nDu hilfst."}},
        headers=env.owner,
    )
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    src = env.source("system-prompts", tid)
    res = env.client.patch(
        f"{env.base}/system-prompts/{tid}/markdown",
        json={
            "base_rev": src["base_rev"],
            "op": "insert_after",
            "anchor": _anchor(src["content"]["body"], "Rolle"),
            "markdown": "## Ton\n\nKnapp.",
        },
        headers=env.owner,
    )
    assert res.status_code == 200, res.text
    assert "## Ton [#" in res.json()["content"]["body"]


def test_unknown_id_with_base_rev_is_404_not_500(env: _Env) -> None:
    missing = "00000000-0000-0000-0000-000000000001"
    patch = env.client.patch(
        f"{env.base}/playbooks/{missing}/markdown",
        json={"base_rev": "0" * 16, "op": "replace", "field": "body", "markdown": "x"},
        headers=env.owner,
    )
    assert patch.status_code == 404, patch.text
    put = env.client.put(
        f"{env.base}/playbooks/{missing}/markdown",
        json={"base_rev": "0" * 16, "content": {"body": "x"}},
        headers=env.owner,
    )
    assert put.status_code == 404, put.text


def test_unknown_entity_type_is_422(env: _Env) -> None:
    res = env.client.get(
        f"{env.base}/agents/00000000-0000-0000-0000-000000000000/markdown", headers=env.owner
    )
    assert res.status_code == 422, res.text


# --- format=full / format=text bleiben unveraendert ---------------------------


def test_json_get_is_bytewise_unchanged_by_markdown_read_and_noop_put(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    env.activate("playbooks", pid)
    before = env.client.get(f"{env.base}/playbooks/{pid}", headers=env.owner).content
    src = env.source("playbooks", pid)
    assert env.client.get(f"{env.base}/playbooks/{pid}", headers=env.owner).content == before

    # Unveraenderter Vollstand: der Draft traegt den gespeicherten Body bitgleich.
    res = env.client.put(
        f"{env.base}/playbooks/{pid}/markdown",
        json={"base_rev": src["base_rev"], "content": src["content"]},
        headers=env.owner,
    )
    assert res.status_code == 200, res.text
    active = env.client.get(f"{env.base}/playbooks/{pid}/versions/1", headers=env.owner).json()
    draft = env.client.get(f"{env.base}/playbooks/{pid}/versions/2", headers=env.owner).json()
    assert draft["content"]["body"] == active["content"]["body"]


def test_version_source_has_no_base_rev(env: _Env) -> None:
    pid = env.create("playbooks", _playbook())["id"]
    res = env.client.get(
        f"{env.base}/playbooks/{pid}/versions/1/markdown?format=source", headers=env.owner
    )
    assert res.status_code == 200, res.text
    assert res.json()["base_rev"] is None
    assert res.json()["content"]["body"].startswith("# Titel [#")


# --- base_rev im Repository jeder Art (ADR-0058 §6.3 A) ----------------------
#
# Direkt am Repository, ohne Service und damit ohne dessen Frueh-Check:
# Ueberschreibt eine Art `update`/`upsert_draft` des Kerns und laesst die
# Pruefung unter der Sperre aus, wird genau ihr Fall rot.


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


@pytest.mark.parametrize(
    "kind", ["persona", "playbook", "resource", "external_tool", "system_prompt"]
)
def test_every_kind_checks_base_rev_under_lock_in_repository(migrated_db: None, kind: str) -> None:
    user = fresh_user_id()
    ws = setup_workspace(user)

    async def body() -> None:
        pool = await asyncpg.create_pool(
            get_settings().database_url, min_size=1, max_size=2, init=init_connection
        )
        assert pool is not None
        try:
            repo, make = _make_repo(kind, pool)
            created = await _insert(kind, repo, ws, user, make("start"))
            state = await repo.fetch_base_rev(ws, created.id)
            assert state is not None

            # Autosave- und PUT-Pfad lehnen einen veralteten Token ab, bevor
            # etwas geschrieben wird (PUT: vor der draft_exists-Pruefung).
            with pytest.raises(BaseRevConflictError), expected_base_rev("0" * 16):
                await repo.upsert_draft(ws, user, created.id, None, make("verloren"))
            with pytest.raises(BaseRevConflictError), expected_base_rev("0" * 16):
                await repo.update(ws, user, created.id, None, make("verloren"))
            assert await repo.fetch_base_rev(ws, created.id) == state

            # Passender Token: Autosave geht durch, der Token aendert sich.
            with expected_base_rev(state[1]):
                await repo.upsert_draft(ws, user, created.id, None, make("neu"))
            after = await repo.fetch_base_rev(ws, created.id)
            assert after is not None
            assert after[1] != state[1]

            # Der alte Token ist jetzt veraltet: der Autosave-Fall aus §6.3.
            with pytest.raises(BaseRevConflictError) as exc, expected_base_rev(state[1]):
                await repo.upsert_draft(ws, user, created.id, None, make("verloren"))
            assert exc.value.current_base_rev == after[1]
            assert await repo.fetch_base_rev(ws, created.id) == after
        finally:
            await pool.close()

    try:
        asyncio.run(body())
    finally:
        cleanup_workspaces([user])
