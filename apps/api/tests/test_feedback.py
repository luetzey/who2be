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
            assert all(
                i["id"] != fid for i in inbox_after["items"]
            ), "Feedback noch im Posteingang."
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
