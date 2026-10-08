"""Integrationstest fuer das Usage-/Feedback-Flywheel (ADR-0038, Track 3).

`POST /usage-events`, `POST /feedback` und `GET /feedback/{type}/{id}` muessen
append-only schreiben, das Aggregat korrekt zaehlen und fremde/unbekannte
Entities mit 404 ablehnen. Owner-JWT (tool_policy=None) ⇒ feedback_write-Gate ist
No-Op; get_feedback verlangt editor (Owner ist admin).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.repositories import feedback_repository
from who2be_api.testing.api_helpers import agent_token
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

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


def _add_member(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> None:
    """Fuegt einem bestehenden Workspace ein Mitglied mit `role` hinzu (RBAC-Setup)."""

    async def _run() -> None:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            await conn.execute(
                "INSERT INTO workspace_member (workspace_id, user_id, role) "
                "VALUES ($1, $2, $3) "
                "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = excluded.role",
                workspace_id,
                user_id,
                role.value,
            )
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


def _playbook_body(name: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {
            "description": "d",
            "body": "1. Step.",
            "type": "workflow",
            "tags": [],
            "triggers": None,
        },
    }


@pytest.mark.integration
def test_system_feedback_flows_into_inbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zielloses System-/MCP-Feedback (entity_type='system') landet im Posteingang
    und ist dort triagier- und loeschbar wie Inhalts-Feedback."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    fbase = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            # Note ist Pflicht: leer -> 422.
            assert (
                client.post(
                    f"{fbase}/system-feedback",
                    json={"category": "mcp", "note": ""},
                    headers=auth,
                ).status_code
                == 422
            )
            # Unbekannte Kategorie -> 422.
            assert (
                client.post(
                    f"{fbase}/system-feedback",
                    json={"category": "nope", "note": "x"},
                    headers=auth,
                ).status_code
                == 422
            )
            # Gueltiger Report -> 201; zielloses Feedback (entity_id None), die
            # Kategorie liegt im signal-Feld.
            r = client.post(
                f"{fbase}/system-feedback",
                json={"category": "mcp", "note": "fetch_playbook liefert 500"},
                headers=auth,
            )
            assert r.status_code == 201, r.text
            body = r.json()
            assert body["entity_type"] == "system"
            assert body["entity_id"] is None
            assert body["signal"] == "mcp"
            assert body["note"] == "fetch_playbook liefert 500"
            fid = body["id"]

            # Erscheint im zentralen Posteingang mit Label "System".
            inbox = client.get(f"{fbase}/feedback-items", headers=auth).json()
            entry = next(i for i in inbox["items"] if i["id"] == fid)
            assert entry["entity_type"] == "system"
            assert entry["entity_id"] is None
            assert entry["name"] == "System"
            assert entry["signal"] == "mcp"
            assert entry["resolution"] is None
            assert inbox["counts"]["open"] >= 1

            # Triagierbar wie jedes Feedback.
            tr = client.post(
                f"{fbase}/feedback/{fid}/resolution",
                json={"resolution": "addressed"},
                headers=auth,
            )
            assert tr.status_code == 201, tr.text
            assert tr.json()["resolution"] == "addressed"

            # Loeschbar (editor+).
            assert client.delete(f"{fbase}/feedback/{fid}", headers=auth).status_code == 204
            inbox2 = client.get(f"{fbase}/feedback-items", headers=auth).json()
            assert all(i["id"] != fid for i in inbox2["items"])
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_flywheel_records_usage_feedback_and_summarizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()

    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    pbase = f"/v1/workspaces/{ws}/playbooks"
    fbase = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            pid = client.post(pbase, json=_playbook_body("PB"), headers=auth).json()["id"]

            # Zwei Nutzungs-Ereignisse (applied, skipped) + ein Feedback (outdated).
            u1 = client.post(
                f"{fbase}/usage-events",
                json={"entity_type": "playbook", "entity_id": pid, "outcome": "applied"},
                headers=auth,
            )
            assert u1.status_code == 201, u1.text
            client.post(
                f"{fbase}/usage-events",
                json={"entity_type": "playbook", "entity_id": pid, "outcome": "skipped"},
                headers=auth,
            )
            fb = client.post(
                f"{fbase}/feedback",
                json={
                    "entity_type": "playbook",
                    "entity_id": pid,
                    "signal": "outdated",
                    "note": "bitte aktualisieren",
                },
                headers=auth,
            )
            assert fb.status_code == 201, fb.text

            summary = client.get(f"{fbase}/feedback/playbook/{pid}", headers=auth)
            assert summary.status_code == 200, summary.text
            body = summary.json()
            # ADR-0053 3.4: `record_usage` meldet nur Ergebnisse; Nutzungen
            # zaehlt allein die Server-Aufzeichnung (hier: keine Auslieferung).
            assert body["usage_count"] == 0
            assert body["by_outcome"] == {"applied": 1, "skipped": 1}
            assert body["by_signal"] == {"outdated": 1}
            assert body["recent_notes"] == ["bitte aktualisieren"]
            # Additiv: die juengsten Einzel-Feedbacks mit id + Triage-Status —
            # adressierbar fuer resolve_feedback; frisch gemeldet = offen (None).
            assert len(body["recent_feedback"]) == 1
            assert body["recent_feedback"][0]["id"] == fb.json()["id"]
            assert body["recent_feedback"][0]["signal"] == "outdated"
            assert body["recent_feedback"][0]["note"] == "bitte aktualisieren"
            assert body["recent_feedback"][0]["resolution"] is None

            # Drill-down: Einzel-Ereignisse (Feedback + Usage) chronologisch.
            events = client.get(f"{fbase}/feedback/playbook/{pid}/events", headers=auth)
            assert events.status_code == 200, events.text
            ev = events.json()
            assert len(ev["feedback"]) == 1
            assert ev["feedback"][0]["signal"] == "outdated"
            assert ev["feedback"][0]["note"] == "bitte aktualisieren"
            assert ev["feedback"][0]["resolution"] is None
            assert len(ev["usage"]) == 2

            # Triage (append-only): Feedback als in_progress, dann addressed
            # markieren — der juengste Status gewinnt; die Feedback-Zeile bleibt.
            fid = fb.json()["id"]
            r1 = client.post(
                f"{fbase}/feedback/{fid}/resolution",
                json={"resolution": "in_progress", "note": "schaue ich mir an"},
                headers=auth,
            )
            assert r1.status_code == 201, r1.text
            assert r1.json()["resolution"] == "in_progress"
            r2 = client.post(
                f"{fbase}/feedback/{fid}/resolution",
                json={"resolution": "addressed"},
                headers=auth,
            )
            assert r2.status_code == 201, r2.text
            # Drill-down zeigt nun den aktuellen (juengsten) Triage-Status.
            ev2 = client.get(f"{fbase}/feedback/playbook/{pid}/events", headers=auth).json()
            assert ev2["feedback"][0]["resolution"] == "addressed"
            # Auch das Aggregat spiegelt den aktuellen Status im Einzel-Feedback.
            body2 = client.get(f"{fbase}/feedback/playbook/{pid}", headers=auth).json()
            assert body2["recent_feedback"][0]["resolution"] == "addressed"

            # Zentraler Posteingang: das Feedback erscheint mit Element-Name +
            # aktuellem Status; die Zaehler spiegeln die Triage.
            inbox = client.get(f"{fbase}/feedback-items", headers=auth)
            assert inbox.status_code == 200, inbox.text
            ibody = inbox.json()
            entry = next(i for i in ibody["items"] if i["id"] == fid)
            assert entry["name"] == "PB"
            assert entry["signal"] == "outdated"
            assert entry["resolution"] == "addressed"
            assert ibody["counts"]["addressed"] >= 1
            assert ibody["counts"]["open"] == 0
            # Unbekanntes Feedback -> 404.
            assert (
                client.post(
                    f"{fbase}/feedback/00000000-0000-0000-0000-000000000000/resolution",
                    json={"resolution": "dismissed"},
                    headers=auth,
                ).status_code
                == 404
            )

            # Workspace-Uebersicht: ein Element mit 2 Ergebnisberichten (keine
            # Server-Nutzung) + 1 negativem Signal.
            overview = client.get(f"{fbase}/feedback-overview", headers=auth)
            assert overview.status_code == 200, overview.text
            items = overview.json()["items"]
            row = next(i for i in items if i["entity_id"] == pid)
            assert row["name"] == "PB"
            assert row["usage_count"] == 0
            assert row["feedback_count"] == 1
            assert row["negative_count"] == 1
            assert row["helpful_count"] == 0
            assert row["last_activity_at"] is not None

            # --- Ungenutzt-Sicht: aktive Version, aber weder ausgeliefert noch bewertet. ---
            # PB (oben) ist Draft + hat Feedback → erscheint NICHT als ungenutzt.
            # PB2 promoten wir auf active und lassen es unberuehrt → es erscheint.
            pid2 = client.post(pbase, json=_playbook_body("PB2"), headers=auth).json()["id"]
            for to in ("review", "active"):
                tr = client.post(
                    f"{pbase}/{pid2}/versions/1/transition",
                    json={"to": to},
                    headers=auth,
                )
                assert tr.status_code == 200, tr.text

            unused = client.get(f"{fbase}/feedback-unused", headers=auth)
            assert unused.status_code == 200, unused.text
            unused_ids = {i["entity_id"] for i in unused.json()["items"]}
            assert pid2 in unused_ids, "Aktives, ungenutztes Element fehlt in der Stale-Sicht."
            assert pid not in unused_ids, "Element mit Usage darf nicht als ungenutzt gelten."

            # Ein Ergebnisbericht allein ist keine Nutzung (ADR-0053 3.4) …
            client.post(
                f"{fbase}/usage-events",
                json={"entity_type": "playbook", "entity_id": pid2, "outcome": "applied"},
                headers=auth,
            )
            unused_report = client.get(f"{fbase}/feedback-unused", headers=auth)
            assert pid2 in {i["entity_id"] for i in unused_report.json()["items"]}
            # … erst die Auslieferung an einen Agenten nimmt PB2 aus der Sicht.
            _, agent_headers = agent_token(client, fbase, "leser", {"playbook_read": "all"}, auth)
            fetched = client.get(f"{pbase}/{pid2}/rendered", headers=agent_headers)
            assert fetched.status_code == 200, fetched.text
            unused2 = client.get(f"{fbase}/feedback-unused", headers=auth)
            assert pid2 not in {i["entity_id"] for i in unused2.json()["items"]}

            # Unbekannte Entity -> 404.
            unknown = "00000000-0000-0000-0000-000000000000"
            r = client.post(
                f"{fbase}/usage-events",
                json={"entity_type": "playbook", "entity_id": unknown},
                headers=auth,
            )
            assert r.status_code == 404
            assert (
                client.get(f"{fbase}/feedback/playbook/{unknown}/events", headers=auth).status_code
                == 404
            )

            # --- Hard-Delete (editor+): Feedback samt Triage-Events loeschen. ---
            # Unbekanntes Feedback -> 404 (kein Enumerieren).
            assert client.delete(f"{fbase}/feedback/{unknown}", headers=auth).status_code == 404
            # Bestehendes Feedback -> 204; danach aus dem Posteingang verschwunden.
            d = client.delete(f"{fbase}/feedback/{fid}", headers=auth)
            assert d.status_code == 204, d.text
            inbox_after = client.get(f"{fbase}/feedback-items", headers=auth).json()
            assert all(i["id"] != fid for i in inbox_after["items"]), (
                "Feedback noch im Posteingang."
            )
            # Drill-down zeigt das Feedback (und seine Triage-Events via Cascade)
            # nicht mehr; der Usage-Verlauf bleibt unberuehrt.
            ev_after = client.get(f"{fbase}/feedback/playbook/{pid}/events", headers=auth).json()
            assert len(ev_after["feedback"]) == 0
            assert len(ev_after["usage"]) == 2
            # Triage auf das geloeschte Feedback -> 404 (Zeile ist weg).
            assert (
                client.post(
                    f"{fbase}/feedback/{fid}/resolution",
                    json={"resolution": "dismissed"},
                    headers=auth,
                ).status_code
                == 404
            )
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_feedback_detail_by_id_surfaces_actor_and_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`GET /feedback/{feedback_id}` liefert den aktuellen Triage-Status, die
    vollstaendige, chronologisch aufsteigende Historie (mit actor/note/created_at),
    den menschlichen Absender (actor_id) und antwortet 404 fuer unbekannte/fremde
    ids."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    fbase = f"/v1/workspaces/{ws}"

    other_owner = fresh_user_id()
    other_ws = setup_workspace(other_owner)
    other_auth = _auth(other_owner)
    other_fbase = f"/v1/workspaces/{other_ws}"

    try:
        with TestClient(app) as client:
            pid = client.post(
                f"{fbase}/playbooks", json=_playbook_body("PB-Detail"), headers=auth
            ).json()["id"]
            fb = client.post(
                f"{fbase}/feedback",
                json={
                    "entity_type": "playbook",
                    "entity_id": pid,
                    "signal": "outdated",
                    "note": "bitte pruefen",
                },
                headers=auth,
            )
            assert fb.status_code == 201, fb.text
            fid = fb.json()["id"]

            # Zwei Triage-Events (append-only): in_progress -> addressed.
            assert (
                client.post(
                    f"{fbase}/feedback/{fid}/resolution",
                    json={"resolution": "in_progress", "note": "schaue ich an"},
                    headers=auth,
                ).status_code
                == 201
            )
            assert (
                client.post(
                    f"{fbase}/feedback/{fid}/resolution",
                    json={"resolution": "addressed", "note": "erledigt"},
                    headers=auth,
                ).status_code
                == 201
            )

            detail = client.get(f"{fbase}/feedback/{fid}", headers=auth)
            assert detail.status_code == 200, detail.text
            body = detail.json()
            # Item-Teil: Element-Name, Signal, Note, aktueller (juengster) Status.
            assert body["id"] == fid
            assert body["entity_type"] == "playbook"
            assert body["entity_id"] == pid
            assert body["name"] == "PB-Detail"
            assert body["signal"] == "outdated"
            assert body["note"] == "bitte pruefen"
            assert body["resolution"] == "addressed"
            # Menschlicher Absender: JWT-Feedback -> agent_id null, actor_id = Owner.
            assert body["agent_id"] is None
            assert body["actor_id"] == str(owner)
            # Vollstaendige Historie, aeltestes zuerst (2 Events mit actor/note/zeit).
            history = body["history"]
            assert [h["resolution"] for h in history] == ["in_progress", "addressed"]
            assert [h["note"] for h in history] == ["schaue ich an", "erledigt"]
            assert all(h["actor_id"] == str(owner) for h in history)
            assert all(h["created_at"] is not None for h in history)
            assert history[0]["created_at"] <= history[1]["created_at"]

            # Frisch gemeldetes, untriagiertes Feedback: leere Historie, offen.
            fid2 = client.post(
                f"{fbase}/feedback",
                json={"entity_type": "playbook", "entity_id": pid, "signal": "helpful"},
                headers=auth,
            ).json()["id"]
            open_detail = client.get(f"{fbase}/feedback/{fid2}", headers=auth).json()
            assert open_detail["resolution"] is None
            assert open_detail["history"] == []
            assert open_detail["actor_id"] == str(owner)

            # Unbekannte id -> 404.
            unknown = "00000000-0000-0000-0000-000000000000"
            assert client.get(f"{fbase}/feedback/{unknown}", headers=auth).status_code == 404

            # Fremdes Feedback (anderer Workspace) -> 404, kein Cross-Workspace-Read.
            other_pid = client.post(
                f"{other_fbase}/playbooks", json=_playbook_body("PB-Other"), headers=other_auth
            ).json()["id"]
            other_fid = client.post(
                f"{other_fbase}/feedback",
                json={"entity_type": "playbook", "entity_id": other_pid, "signal": "unclear"},
                headers=other_auth,
            ).json()["id"]
            assert client.get(f"{fbase}/feedback/{other_fid}", headers=auth).status_code == 404
    finally:
        cleanup_workspaces([owner, other_owner])


@pytest.mark.integration
def test_resolution_requires_feedback_resolve_for_agent_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capability-Gate der Triage: ein agent-gebundener Token braucht
    `feedback_resolve` (Default aus) — 403 ohne, 201 mit; Mensch (editor+)
    bleibt unveraendert nur rollen-gated (201)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    fbase = f"/v1/workspaces/{ws}"

    def _agent_token(client: TestClient, name: str, policy: dict[str, object]) -> dict[str, str]:
        """Kurzform ueber `prefix`/`auth` dieses Tests — Logik im Helfer."""
        _, headers = agent_token(client, fbase, name, policy, auth)
        return headers

    try:
        with TestClient(app) as client:
            pid = client.post(
                f"{fbase}/playbooks", json=_playbook_body("PB-Triage"), headers=auth
            ).json()["id"]
            fid = client.post(
                f"{fbase}/feedback",
                json={"entity_type": "playbook", "entity_id": pid, "signal": "outdated"},
                headers=auth,
            ).json()["id"]

            # Agent OHNE feedback_resolve (Default-Policy) → 403 missing_capability.
            no_cap = _agent_token(client, "triage-ohne-cap", {})
            denied = client.post(
                f"{fbase}/feedback/{fid}/resolution",
                json={"resolution": "in_progress"},
                headers=no_cap,
            )
            assert denied.status_code == 403, denied.text
            assert denied.json()["reason"] == "missing_capability"

            # Agent MIT feedback_resolve → 201; Antwort traegt den neuen Status.
            with_cap = _agent_token(client, "triage-mit-cap", {"feedback_resolve": True})
            granted = client.post(
                f"{fbase}/feedback/{fid}/resolution",
                json={"resolution": "in_progress", "note": "Draft folgt"},
                headers=with_cap,
            )
            assert granted.status_code == 201, granted.text
            assert granted.json()["resolution"] == "in_progress"

            # Mensch (JWT, editor+): weiterhin nur rollen-gated → 201.
            human = client.post(
                f"{fbase}/feedback/{fid}/resolution",
                json={"resolution": "addressed"},
                headers=auth,
            )
            assert human.status_code == 201, human.text
            assert human.json()["resolution"] == "addressed"
    finally:
        cleanup_workspaces([owner])


def _external_tool_body(name: str) -> dict[str, object]:
    return {
        "name": name,
        "content": {"display_name": name, "usage_notes": "Notiz.", "tags": []},
    }


@pytest.mark.integration
def test_flywheel_accepts_external_tool_entity(monkeypatch: pytest.MonkeyPatch) -> None:
    """WP-3: record_usage/submit_feedback/get_feedback akzeptieren
    entity_type='external_tool' (WP-4 musste den Feedback-Button weglassen,
    weil das Backend zuvor 422 warf) — und das Feedback erscheint im
    zentralen Posteingang mit dem Tool-Namen (Namens-JOIN)."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    fbase = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            tid = client.post(
                f"{fbase}/external_tools", json=_external_tool_body("Todoist"), headers=auth
            ).json()["id"]

            usage = client.post(
                f"{fbase}/usage-events",
                json={"entity_type": "external_tool", "entity_id": tid, "outcome": "applied"},
                headers=auth,
            )
            assert usage.status_code == 201, usage.text
            assert usage.json()["entity_type"] == "external_tool"

            fb = client.post(
                f"{fbase}/feedback",
                json={
                    "entity_type": "external_tool",
                    "entity_id": tid,
                    "signal": "helpful",
                    "note": "funktioniert gut",
                },
                headers=auth,
            )
            assert fb.status_code == 201, fb.text
            fid = fb.json()["id"]

            summary = client.get(f"{fbase}/feedback/external_tool/{tid}", headers=auth)
            assert summary.status_code == 200, summary.text
            body = summary.json()
            assert body["entity_type"] == "external_tool"
            # Nur ein Ergebnisbericht, keine Server-Auslieferung (ADR-0053 3.4).
            assert body["usage_count"] == 0
            assert body["by_outcome"] == {"applied": 1}
            assert body["by_signal"] == {"helpful": 1}

            # Zentraler Posteingang: der Tool-Name loest ueber den neuen
            # external_tool-JOIN auf (nicht NULL/gefiltert).
            inbox = client.get(f"{fbase}/feedback-items", headers=auth).json()
            entry = next(i for i in inbox["items"] if i["id"] == fid)
            assert entry["entity_type"] == "external_tool"
            assert entry["name"] == "Todoist"

            # Uebersicht + Ungenutzt-Sicht kennen external_tool ebenfalls.
            overview = client.get(f"{fbase}/feedback-overview", headers=auth).json()
            row = next(i for i in overview["items"] if i["entity_id"] == tid)
            assert row["name"] == "Todoist"
            assert row["usage_count"] == 0
            assert row["feedback_count"] == 1

            # Unbekanntes external_tool -> 404 (kein Enumerieren).
            unknown = "00000000-0000-0000-0000-000000000000"
            assert (
                client.post(
                    f"{fbase}/usage-events",
                    json={"entity_type": "external_tool", "entity_id": unknown},
                    headers=auth,
                ).status_code
                == 404
            )
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_submit_feedback_requires_editor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inhalts-Feedback ist eine Kurations-Handlung → editor+: ein viewer bekommt
    403, ein editor darf einreichen (201). Das Ziel-Element gehoert zum
    Workspace, sodass das Rollen-Gate (und nicht der belongs-to-Check) greift."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()  # Workspace-Eigner (admin via setup_workspace)
    viewer = fresh_user_id()
    editor = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, viewer, WorkspaceRole.viewer)
    _add_member(ws, editor, WorkspaceRole.editor)
    admin_auth = _auth(owner)
    viewer_auth = _auth(viewer)
    editor_auth = _auth(editor)
    fbase = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            pid = client.post(
                f"{fbase}/playbooks", json=_playbook_body("PB-Gate"), headers=admin_auth
            ).json()["id"]
            body = {
                "entity_type": "playbook",
                "entity_id": pid,
                "signal": "helpful",
                "note": "danke",
            }

            # viewer darf kein Inhalts-Feedback einreichen -> 403.
            denied = client.post(f"{fbase}/feedback", json=body, headers=viewer_auth)
            assert denied.status_code == 403, denied.text

            # editor darf -> 201.
            allowed = client.post(f"{fbase}/feedback", json=body, headers=editor_auth)
            assert allowed.status_code == 201, allowed.text
            assert allowed.json()["signal"] == "helpful"
    finally:
        cleanup_workspaces([owner, viewer, editor])


# --------------------------------------------------------------------------
# D3 — Serverseitige Nutzungsaufzeichnung (ADR-0053 3.4, Migration 0101)
# --------------------------------------------------------------------------

# Leserechte fuer die drei Abrufpfade; Inhalte sind `active`, ein Agent ohne
# Schreibrecht sieht nur die aktive Version.
_READER_POLICY: dict[str, object] = {"playbook_read": "all", "resource_read": "all"}


def _db_fetch(sql: str, *args: object) -> list[asyncpg.Record]:
    async def _run() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    return asyncio.run(_run())


def _server_rows(entity_id: str) -> list[asyncpg.Record]:
    return _db_fetch(
        "SELECT agent_id, entity_type, version, outcome FROM usage_event "
        "WHERE entity_id = $1 AND source = 'server' ORDER BY created_at",
        UUID(entity_id),
    )


def _activate(client: TestClient, base: str, auth: dict[str, str]) -> None:
    for to in ("review", "active"):
        tr = client.post(f"{base}/versions/1/transition", json={"to": to}, headers=auth)
        assert tr.status_code == 200, tr.text


class _Elements:
    """Je eine aktive Persona, ein Playbook und eine Resource (Version 1)."""

    def __init__(self, client: TestClient, ws: UUID, auth: dict[str, str]) -> None:
        base = f"/v1/workspaces/{ws}"
        self.persona = client.post(
            f"{base}/personas",
            json={
                "name": "P-D3",
                "content": {
                    "description": "d",
                    "content": {
                        "blocks": [
                            {
                                "id": "b1",
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Profil.", "styles": {}}],
                            }
                        ]
                    },
                },
            },
            headers=auth,
        ).json()["id"]
        self.playbook = client.post(
            f"{base}/playbooks", json=_playbook_body("PB-D3"), headers=auth
        ).json()["id"]
        self.resource = client.post(
            f"{base}/resources",
            json={
                "name": "R-D3",
                "content": {
                    "description": "d",
                    "blocks": [
                        {
                            "id": "r1",
                            "type": "heading",
                            "props": {"level": 2},
                            "content": [{"type": "text", "text": "Abschnitt", "styles": {}}],
                        }
                    ],
                    "tags": [],
                },
            },
            headers=auth,
        ).json()["id"]
        _activate(client, f"{base}/personas/{self.persona}", auth)
        _activate(client, f"{base}/playbooks/{self.playbook}", auth)
        _activate(client, f"{base}/resources/{self.resource}", auth)
        # (entity_type, Element-ID, Abruf-URL) — die drei Schreibstellen.
        self.fetches = [
            ("persona", self.persona, f"{base}/personas/{self.persona}/rendered"),
            ("playbook", self.playbook, f"{base}/playbooks/{self.playbook}/rendered"),
            ("resource", self.resource, f"{base}/resources/{self.resource}"),
        ]


@pytest.mark.integration
def test_agent_fetch_records_exactly_one_server_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Je Abruf durch ein Agent-Token genau eine Zeile `source='server'` mit
    Agent, ausgelieferter Version und `outcome=NULL`; ein Mensch erzeugt keine;
    interne Lesepfade (Anker-Liste) zaehlen nicht."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            elements = _Elements(client, ws, auth)
            agent_id, agent_headers = agent_token(client, prefix, "leser", _READER_POLICY, auth)

            # Mensch: Abruf gelingt, aber keine Nutzungszeile.
            for _, entity_id, url in elements.fetches:
                assert client.get(url, headers=auth).status_code == 200
                assert _server_rows(entity_id) == []

            # Agent: genau eine Zeile je Abruf.
            for entity_type, entity_id, url in elements.fetches:
                r = client.get(url, headers=agent_headers)
                assert r.status_code == 200, r.text
                rows = _server_rows(entity_id)
                assert len(rows) == 1, (entity_type, rows)
                assert rows[0]["agent_id"] == UUID(agent_id)
                assert rows[0]["entity_type"] == entity_type
                assert rows[0]["version"] == 1
                assert rows[0]["outcome"] is None

            # Jede Auslieferung eine Zeile (Owner-Weiche N2 = a): zweiter Abruf.
            again = client.get(elements.fetches[0][2], headers=agent_headers)
            assert again.status_code == 200
            assert len(_server_rows(elements.persona)) == 2

            # Interner Lesepfad ist kein Abruf: Anker-Liste der Resource.
            blocks = client.get(
                f"{prefix}/resources/{elements.resource}/blocks", headers=agent_headers
            )
            assert blocks.status_code == 200, blocks.text
            assert len(_server_rows(elements.resource)) == 1

            # Die Selbstauskunft traegt weiter `agent_report`.
            client.post(
                f"{prefix}/usage-events",
                json={
                    "entity_type": "playbook",
                    "entity_id": elements.playbook,
                    "outcome": "applied",
                },
                headers=agent_headers,
            )
            sources = _db_fetch(
                "SELECT source, COUNT(*)::int AS n FROM usage_event "
                "WHERE entity_id = $1 GROUP BY source ORDER BY source",
                UUID(elements.playbook),
            )
            assert [(s["source"], s["n"]) for s in sources] == [
                ("agent_report", 1),
                ("server", 1),
            ]
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_server_usage_write_failure_never_breaks_the_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Best-effort: scheitert die Aufzeichnung, liefert der Abruf trotzdem 200
    — und der Verlust ist im Prozess-Zaehler sichtbar."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    async def _broken(*args: object, **kwargs: object) -> None:
        raise asyncpg.PostgresError("usage_event nicht beschreibbar")

    try:
        with TestClient(app) as client:
            elements = _Elements(client, ws, auth)
            _, agent_headers = agent_token(client, prefix, "leser", _READER_POLICY, auth)
            feedback_repository.reset_failed_usage_writes()
            monkeypatch.setattr(feedback_repository, "_insert_server_usage", _broken)

            for entity_type, entity_id, url in elements.fetches:
                r = client.get(url, headers=agent_headers)
                assert r.status_code == 200, (entity_type, r.text)
                assert _server_rows(entity_id) == []
            assert feedback_repository.failed_usage_writes() == 3
    finally:
        feedback_repository.reset_failed_usage_writes()
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_aggregates_count_usage_and_outcomes_by_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`summarize`/`overview` zaehlen Nutzungen nur aus `server`, Ergebnisse
    nur aus `agent_report` (ADR-0053 3.4) — Fixture mit beiden Quellen."""
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = _auth(owner)
    prefix = f"/v1/workspaces/{ws}"

    try:
        with TestClient(app) as client:
            elements = _Elements(client, ws, auth)
            _, agent_headers = agent_token(client, prefix, "leser", _READER_POLICY, auth)
            pid = elements.playbook
            url = f"{prefix}/playbooks/{pid}/rendered"
            # Drei Auslieferungen (server) …
            for _ in range(3):
                assert client.get(url, headers=agent_headers).status_code == 200
            # … und zwei Ergebnisberichte (agent_report).
            for outcome in ("applied", "error"):
                r = client.post(
                    f"{prefix}/usage-events",
                    json={"entity_type": "playbook", "entity_id": pid, "outcome": outcome},
                    headers=agent_headers,
                )
                assert r.status_code == 201, r.text

            summary = client.get(f"{prefix}/feedback/playbook/{pid}", headers=auth).json()
            assert summary["usage_count"] == 3
            assert summary["by_outcome"] == {"applied": 1, "error": 1}

            overview = client.get(f"{prefix}/feedback-overview", headers=auth).json()
            row = next(i for i in overview["items"] if i["entity_id"] == pid)
            assert row["usage_count"] == 3

            # Ungenutzt-Sicht: das ausgelieferte Playbook nicht, die nur von
            # Menschen gelesene Resource schon.
            client.get(f"{prefix}/resources/{elements.resource}", headers=auth)
            unused = client.get(f"{prefix}/feedback-unused", headers=auth).json()
            unused_ids = {i["entity_id"] for i in unused["items"]}
            assert pid not in unused_ids
            assert elements.resource in unused_ids
    finally:
        cleanup_workspaces([owner])
