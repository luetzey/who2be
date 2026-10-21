"""Integrationstests fuer die Nutzungszaehler (Nutzung U1, Konzept W5 §7).

Kritische Invarianten (Plan 2026-10-10-0740):
- Gezaehlt werden nur Auslieferungen an Agenten (`source = 'server'`, Z1a);
  Selbstauskuenfte (`agent_report`) zaehlen nicht.
- Fenster sind Kalendertage (UTC) einschliesslich heute: 7 Tage = heute und
  die sechs Tage davor, 30 Tage entsprechend; `uses_30d == sum(daily)`.
- `last_used_at` ist die juengste Auslieferung ueberhaupt, auch ausserhalb
  des Fensters; `distinct_agents_30d` zaehlt verschiedene Agenten im Fenster.
- Die Liste nennt jedes Element des Workspace, auch ungenutzte (0).
- Zaehlbeginn `counting_since = 2026-10-08` steht in jeder Antwort.
- Rechte ab viewer; agent-gebundene Tokens 403; fremdes Element 404.
- `feedback-overview` trennt `last_used_at` und `last_feedback_at`.
- Unter der Laufzeitrolle `who2be_app` (RLS) dieselben Zahlen.

Telemetrie wird direkt (Superuser) mit gesetztem `created_at` geschrieben —
nur so lassen sich Ereignisse in bestimmten Tagen erzeugen.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from test_rls_control_plane_api import app_role_client  # type: ignore[import-not-found]

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("patched_jwt_secret", "migrated_db"),
]

__all__ = ["app_role_client"]

# Ein Block, damit sich eine Resource aktivieren laesst (Promote-Pflichtfeld).
_BLOCK = {
    "id": "r1",
    "type": "heading",
    "props": {"level": 2},
    "content": [{"type": "text", "text": "Abschnitt", "styles": {}}],
}


def _create(client: TestClient, prefix: str, auth: dict[str, str], kind: str, name: str) -> str:
    bodies: dict[str, dict[str, Any]] = {
        "resources": {"name": name, "content": {"description": "d", "blocks": [], "tags": []}},
        "playbooks": {
            "name": name,
            "content": {
                "description": "d",
                "body": "1. Step.",
                "type": "workflow",
                "tags": [],
                "triggers": None,
            },
        },
        "personas": {"name": name, "content": {"description": "d", "system_prompt": "s"}},
    }
    res = client.post(f"{prefix}/{kind}", json=bodies[kind], headers=auth)
    assert res.status_code == 201, res.text
    eid: str = res.json()["id"]
    return eid


def _usage(
    ws: UUID,
    agent: str | None,
    etype: str,
    eid: str,
    days_ago: int,
    n: int = 1,
    source: str = "server",
) -> None:
    for _ in range(n):
        db_execute(
            "INSERT INTO usage_event (workspace_id, agent_id, entity_type, entity_id, "
            "version, outcome, source, created_at) VALUES ($1, $2, $3, $4, 1, NULL, $5, "
            "now() - make_interval(days => $6))",
            ws,
            UUID(agent) if agent else None,
            etype,
            UUID(eid),
            source,
            days_ago,
        )


def _setup(client: TestClient, ws: UUID, auth: dict[str, str]) -> dict[str, str]:
    """Agenten A, B; Resource R (genutzt), Playbook P (genutzt), Persona Q (nie)."""
    prefix = f"/v1/workspaces/{ws}"
    a, _ = agent_token(client, prefix, "Alpha", {}, auth)
    b, _ = agent_token(client, prefix, "Beta", {}, auth)
    r = _create(client, prefix, auth, "resources", "R")
    p = _create(client, prefix, auth, "playbooks", "P")
    q = _create(client, prefix, auth, "personas", "Q")
    _usage(ws, a, "resource", r, 0, n=2)  # heute
    _usage(ws, b, "resource", r, 6)  # letzter Tag im 7-Tage-Fenster
    _usage(ws, a, "resource", r, 7)  # erster Tag ausserhalb 7, innerhalb 30
    _usage(ws, b, "resource", r, 29)  # letzter Tag im 30-Tage-Fenster
    _usage(ws, a, "resource", r, 30)  # ausserhalb 30 Tage
    _usage(ws, a, "resource", r, 0, n=3, source="agent_report")  # Selbstauskunft
    _usage(ws, a, "playbook", p, 40)  # nur alt: 0 im Fenster, aber zuletzt genutzt
    return {"a": a, "b": b, "r": r, "p": p, "q": q}


def _today() -> datetime:
    return datetime.now(UTC)


def test_einzelsicht_fenster_tagesreihe_und_zaehlbeginn(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    try:
        with TestClient(app) as client:
            ids = _setup(client, ws, auth)
            res = client.get(f"/v1/workspaces/{ws}/usage/resource/{ids['r']}", headers=auth)
            assert res.status_code == 200, res.text
            body = res.json()

            assert body["entity_type"] == "resource"
            assert body["entity_id"] == ids["r"]
            assert body["uses_7d"] == 3  # 2 heute + 1 vor 6 Tagen
            assert body["uses_30d"] == 5  # + vor 7 und vor 29 Tagen
            assert body["distinct_agents_30d"] == 2
            assert body["counting_since"] == "2026-10-08"

            # Juengste Auslieferung ist von heute (Selbstauskunft zaehlt nicht,
            # liegt aber ebenfalls heute — entscheidend ist, dass es ein
            # Zeitstempel und kein Fehler ist).
            last = datetime.fromisoformat(body["last_used_at"])
            assert _today() - last < timedelta(hours=1)

            daily = body["daily"]
            assert len(daily) == 30
            today = _today().date()
            assert daily[-1]["day"] == today.isoformat()
            assert daily[0]["day"] == (today - timedelta(days=29)).isoformat()
            assert sum(d["uses"] for d in daily) == body["uses_30d"]
            by_day = {d["day"]: d["uses"] for d in daily}
            assert by_day[today.isoformat()] == 2
            assert by_day[(today - timedelta(days=6)).isoformat()] == 1
            assert by_day[(today - timedelta(days=29)).isoformat()] == 1

            # Nur alte Nutzung: Fenster leer, `last_used_at` trotzdem gesetzt.
            old = client.get(f"/v1/workspaces/{ws}/usage/playbook/{ids['p']}", headers=auth)
            assert old.status_code == 200, old.text
            ob = old.json()
            assert (ob["uses_7d"], ob["uses_30d"], ob["distinct_agents_30d"]) == (0, 0, 0)
            assert ob["last_used_at"] is not None
            assert [d["uses"] for d in ob["daily"]] == [0] * 30

            never = client.get(f"/v1/workspaces/{ws}/usage/persona/{ids['q']}", headers=auth)
            assert never.status_code == 200, never.text
            assert never.json()["last_used_at"] is None
            assert never.json()["uses_30d"] == 0
    finally:
        cleanup_workspaces([owner])


def test_liste_alle_elemente_und_typfilter(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    try:
        with TestClient(app) as client:
            ids = _setup(client, ws, auth)
            res = client.get(f"/v1/workspaces/{ws}/usage", headers=auth)
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["counting_since"] == "2026-10-08"
            rows = {i["entity_id"]: i for i in body["items"]}
            # Neue Workspaces bringen Startinhalte mit: die drei Testelemente
            # sind enthalten, alle uebrigen ungenutzt (0) — aber gelistet.
            assert {ids["r"], ids["p"], ids["q"]} <= set(rows)
            others = [i for k, i in rows.items() if k not in (ids["r"], ids["p"])]
            assert all(i["uses_30d"] == 0 and i["last_used_at"] is None for i in others)

            r = rows[ids["r"]]
            assert (r["uses_7d"], r["uses_30d"], r["distinct_agents_30d"]) == (3, 5, 2)
            assert r["name"] == "R"
            assert r["daily"] == []  # Tagesreihe nur in der Einzelsicht
            p = rows[ids["p"]]
            assert (p["uses_7d"], p["uses_30d"]) == (0, 0)
            assert p["last_used_at"] is not None
            assert rows[ids["q"]]["last_used_at"] is None

            # Sortierung: zuletzt genutzt zuerst, nie genutzt danach.
            order = [i["entity_id"] for i in body["items"]]
            assert order[:2] == [ids["r"], ids["p"]]

            # Die Liste stimmt mit der Einzelsicht ueberein.
            single = client.get(
                f"/v1/workspaces/{ws}/usage/resource/{ids['r']}", headers=auth
            ).json()
            for key in ("uses_7d", "uses_30d", "distinct_agents_30d", "last_used_at"):
                assert r[key] == single[key], key

            only = client.get(f"/v1/workspaces/{ws}/usage?entity_type=playbook", headers=auth)
            assert only.status_code == 200, only.text
            only_items = only.json()["items"]
            assert ids["p"] in {i["entity_id"] for i in only_items}
            assert {i["entity_type"] for i in only_items} == {"playbook"}

            bad = client.get(f"/v1/workspaces/{ws}/usage?entity_type=agent", headers=auth)
            assert bad.status_code == 422, bad.text
    finally:
        cleanup_workspaces([owner])


def test_echte_auslieferung_wird_gezaehlt(make_auth_headers: AuthFactory) -> None:
    """Ein Abruf durch einen Agent-Token erhoeht den Zaehler, ein Mensch nicht."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            created = client.post(
                f"{prefix}/resources",
                json={
                    "name": "Live",
                    "content": {"description": "d", "blocks": [_BLOCK], "tags": []},
                },
                headers=auth,
            )
            assert created.status_code == 201, created.text
            r = created.json()["id"]
            # Konsum-Agenten sehen nur aktive Versionen; Promote verlangt Inhalt.
            for to in ("review", "active"):
                tr = client.post(
                    f"{prefix}/resources/{r}/versions/1/transition", json={"to": to}, headers=auth
                )
                assert tr.status_code == 200, tr.text
            _, agent_auth = agent_token(client, prefix, "Leser", {"resource_read": "all"}, auth)
            assert client.get(f"{prefix}/resources/{r}", headers=auth).status_code == 200
            fetched = client.get(f"{prefix}/resources/{r}", headers=agent_auth)
            assert fetched.status_code == 200, fetched.text

            body = client.get(f"{prefix}/usage/resource/{r}", headers=auth).json()
            assert (body["uses_7d"], body["uses_30d"], body["distinct_agents_30d"]) == (1, 1, 1)
            assert body["daily"][-1]["uses"] == 1
    finally:
        cleanup_workspaces([owner])


def test_rechte_404_und_validierung(make_auth_headers: AuthFactory) -> None:
    owner, viewer, stranger = fresh_user_id(), fresh_user_id(), fresh_user_id()
    ws, foreign = setup_workspace(owner), setup_workspace(stranger)
    db_execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'viewer')",
        ws,
        viewer,
    )
    auth = make_auth_headers(owner)
    base = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            ids = _setup(client, ws, auth)

            # viewer liest die Zaehler (Spec §3.2: Nutzung ab viewer).
            viewer_auth = make_auth_headers(viewer)
            seen = client.get(f"{base}/usage/resource/{ids['r']}", headers=viewer_auth)
            assert seen.status_code == 200, seen.text
            assert seen.json()["uses_30d"] == 5
            assert client.get(f"{base}/usage", headers=viewer_auth).status_code == 200

            # Agent-gebundene Tokens: 403, auch fuer die Liste.
            _, agent_auth = agent_token(client, base, "Neugierig", {}, auth)
            for url in (f"{base}/usage", f"{base}/usage/resource/{ids['r']}"):
                denied = client.get(url, headers=agent_auth)
                assert denied.status_code == 403, (url, denied.text)
                assert denied.json()["reason"] == "missing_capability"

            # Unbekanntes oder fremdes Element, falscher Typ: 404.
            ghost = "00000000-0000-0000-0000-000000000000"
            other = _create(
                client, f"/v1/workspaces/{foreign}", make_auth_headers(stranger), "resources", "X"
            )
            for path in (
                f"resource/{ghost}",
                f"resource/{other}",
                f"playbook/{ids['r']}",
            ):
                missing = client.get(f"{base}/usage/{path}", headers=auth)
                assert missing.status_code == 404, (path, missing.text)
                assert missing.json()["reason"] == "feedback_element_not_found"

            # External Tools haben (noch) keine Server-Aufzeichnung: 422.
            tool = client.get(f"{base}/usage/external_tool/{ghost}", headers=auth)
            assert tool.status_code == 422, tool.text
    finally:
        cleanup_workspaces([owner, viewer, stranger])


def test_overview_trennt_genutzt_und_feedback(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    try:
        with TestClient(app) as client:
            ids = _setup(client, ws, auth)
            db_execute(
                "INSERT INTO agent_feedback (workspace_id, agent_id, entity_type, entity_id, "
                "version, signal, created_at) VALUES ($1, $2, 'playbook', $3, 1, 'helpful', "
                "now() - make_interval(days => 3))",
                ws,
                UUID(ids["a"]),
                UUID(ids["p"]),
            )
            # Nur eine Selbstauskunft an Q: Aktivitaet ja, Nutzung nein.
            _usage(ws, ids["a"], "persona", ids["q"], 1, source="agent_report")
            res = client.get(f"/v1/workspaces/{ws}/feedback-overview", headers=auth)
            assert res.status_code == 200, res.text
            rows = {i["entity_id"]: i for i in res.json()["items"]}
            now = _today()

            p = rows[ids["p"]]
            used = now - datetime.fromisoformat(p["last_used_at"])
            fed = now - datetime.fromisoformat(p["last_feedback_at"])
            assert timedelta(days=39) < used < timedelta(days=41)
            assert timedelta(days=2) < fed < timedelta(days=4)
            assert p["last_activity_at"] == p["last_feedback_at"]  # Back-Compat: das Maximum

            q = rows[ids["q"]]
            assert q["last_used_at"] is None
            assert q["last_feedback_at"] is None
            assert q["last_activity_at"] is not None

            assert rows[ids["r"]]["last_feedback_at"] is None
    finally:
        cleanup_workspaces([owner])


def test_unter_laufzeitrolle_who2be_app(
    app_role_client: TestClient, make_auth_headers: AuthFactory
) -> None:
    """RLS: unter `who2be_app` dieselben Zahlen; ein fremder Workspace sieht nichts."""
    owner, stranger = fresh_user_id(), fresh_user_id()
    ws, foreign = setup_workspace(owner), setup_workspace(stranger)
    auth, foreign_auth = make_auth_headers(owner), make_auth_headers(stranger)
    try:
        ids = _setup(app_role_client, ws, auth)
        body = app_role_client.get(
            f"/v1/workspaces/{ws}/usage/resource/{ids['r']}", headers=auth
        ).json()
        assert (body["uses_7d"], body["uses_30d"], body["distinct_agents_30d"]) == (3, 5, 2)
        listed = app_role_client.get(f"/v1/workspaces/{ws}/usage", headers=auth).json()
        listed_ids = {i["entity_id"] for i in listed["items"]}
        assert {ids["r"], ids["p"], ids["q"]} <= listed_ids

        cross = app_role_client.get(
            f"/v1/workspaces/{foreign}/usage/resource/{ids['r']}", headers=foreign_auth
        )
        assert cross.status_code == 404, cross.text
        empty = app_role_client.get(f"/v1/workspaces/{foreign}/usage", headers=foreign_auth)
        assert empty.status_code == 200, empty.text
        foreign_items = empty.json()["items"]
        assert not listed_ids & {i["entity_id"] for i in foreign_items}
        assert all(i["uses_30d"] == 0 for i in foreign_items)
    finally:
        cleanup_workspaces([owner, stranger])
