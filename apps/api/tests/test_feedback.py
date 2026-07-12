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
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

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
            assert body["usage_count"] == 2
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

            # Workspace-Uebersicht: ein Element mit 2 Usages + 1 negativem Signal.
            overview = client.get(f"{fbase}/feedback-overview", headers=auth)
            assert overview.status_code == 200, overview.text
            items = overview.json()["items"]
            row = next(i for i in items if i["entity_id"] == pid)
            assert row["name"] == "PB"
            assert row["usage_count"] == 2
            assert row["feedback_count"] == 1
            assert row["negative_count"] == 1
            assert row["helpful_count"] == 0
            assert row["last_activity_at"] is not None

            # --- Ungenutzt-Sicht: aktive Version, aber kein Usage/Feedback. ---
            # PB (oben) ist Draft + hat Usage → erscheint NICHT als ungenutzt.
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

            # Sobald PB2 genutzt wird, faellt es aus der Ungenutzt-Sicht.
            client.post(
                f"{fbase}/usage-events",
                json={"entity_type": "playbook", "entity_id": pid2, "outcome": "applied"},
                headers=auth,
            )
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
        agent = client.post(
            f"{fbase}/agents", json={"name": name, "tool_policy": policy}, headers=auth
        )
        assert agent.status_code == 201, agent.text
        token = client.post(
            f"{fbase}/tokens",
            json={"name": name, "agent_id": agent.json()["id"]},
            headers=auth,
        )
        assert token.status_code == 201, token.text
        return {"Authorization": f"Bearer {token.json()['token']}"}

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
