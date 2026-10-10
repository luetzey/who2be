"""Integrationstests fuer die Agent- und Arbeitsbereich-Zaehler (Nutzung U2).

Kritische Invarianten (Plan 2026-10-10-0930, Konzept W5 §7 U2, Owner Z2a):
- Agent: Auslieferungen an DIESEN Agenten (`usage_event.agent_id`, nur
  `source='server'`), Fenster als Kalendertage UTC wie U1, je Elementart,
  aktive Tage = Tage mit mindestens einer Auslieferung; `last_used_at` ueber
  die ganze Zeit; `last_active_at` = `max(api_token.last_used_at)` des Agenten.
- Arbeitsbereich: Eintraege aus `agent_access_log` auf Artifacts und Tabellen
  des Bereichs; Zugriffstage, Lese-/Schreibzugriffe, Agentenzahl, zuletzt am
  (Datum). Blobs, KB-Knoten und Eintraege anderer Bereiche zaehlen nicht.
- Agent-Zaehler nennt die Bereiche mit Zugriffen; viewer sieht nur geteilte.
- Rechte wie U1: ab viewer, agent-gebundene Tokens 403, keine Agent-Namen.
- Unbekannt oder fremd: 404 `agent_not_found` bzw. `area_not_found`; eine
  private Area ist fuer viewer ebenfalls 404.
- Unter der Laufzeitrolle `who2be_app` (RLS) dieselben Zahlen.

Telemetrie wird direkt (Superuser) mit gesetzten Tagen geschrieben.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from test_rls_control_plane_api import app_role_client  # type: ignore[import-not-found]

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute, db_fetchval
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("patched_jwt_secret", "migrated_db"),
]

__all__ = ["app_role_client"]


def _usage(
    ws: UUID, agent: str, etype: str, days_ago: int, n: int = 1, source: str = "server"
) -> None:
    for _ in range(n):
        db_execute(
            "INSERT INTO usage_event (workspace_id, agent_id, entity_type, entity_id, "
            "version, outcome, source, created_at) VALUES ($1, $2, $3, gen_random_uuid(), 1, "
            "NULL, $4, now() - make_interval(days => $5))",
            ws,
            UUID(agent),
            etype,
            source,
            days_ago,
        )


def _area(ws: UUID, name: str, private_for: str | None = None) -> str:
    area = db_fetchval(
        "INSERT INTO work_area (workspace_id, scope, owner_agent_id, name) "
        "VALUES ($1, $2, $3, $4) RETURNING id::text",
        ws,
        "private" if private_for else "shared",
        UUID(private_for) if private_for else None,
        name,
    )
    return str(area)


def _artifact(ws: UUID, area: str) -> str:
    return str(
        db_fetchval(
            "INSERT INTO wa_artifact (workspace_id, area_id, type, title, occurred_at, "
            "occurred_precision) VALUES ($1, $2, 'doc', 't', now(), 'day') RETURNING id::text",
            ws,
            UUID(area),
        )
    )


def _table(ws: UUID, area: str, name: str) -> str:
    return str(
        db_fetchval(
            "INSERT INTO wa_table (workspace_id, area_id, name, schema_json) "
            "VALUES ($1, $2, $3, '{}'::jsonb) RETURNING id::text",
            ws,
            UUID(area),
            name,
        )
    )


def _access(ws: UUID, agent: str, kind: str, ref: str, op: str, days_ago: int) -> None:
    db_execute(
        "INSERT INTO agent_access_log (workspace_id, agent_id, ref_kind, ref_id, operation, "
        "sensitivity_at_access, access_date) "
        "VALUES ($1, $2, $3, $4, $5, 'general', CURRENT_DATE - $6::int)",
        ws,
        UUID(agent),
        kind,
        ref,
        op,
        days_ago,
    )


def _setup(client: TestClient, ws: UUID, auth: dict[str, str]) -> dict[str, str]:
    """Agenten A, B; geteilter Bereich T, private Area P von A, Bereich X leer.

    Auslieferungen an A: heute 2 Playbook, vor 6 Tagen 1 Persona, vor 7 Tagen
    1 Resource, vor 29 Tagen 1 Resource, vor 30 Tagen 1 (ausserhalb), dazu
    Selbstauskuenfte (zaehlen nicht). An B: heute 1.
    Zugriffe: A auf T (Artifact gelesen heute + geschrieben heute, Tabelle vor
    3 Tagen, Artifact vor 40 Tagen), A auf P (vor 2 Tagen), B auf T (vor 1
    Tag), A auf einen Blob und einen KB-Knoten (zaehlen nicht).
    """
    prefix = f"/v1/workspaces/{ws}"
    a, _ = agent_token(client, prefix, "Alpha", {}, auth)
    b, _ = agent_token(client, prefix, "Beta", {}, auth)
    _usage(ws, a, "playbook", 0, n=2)
    _usage(ws, a, "persona", 6)
    _usage(ws, a, "resource", 7)
    _usage(ws, a, "resource", 29)
    _usage(ws, a, "resource", 30)
    _usage(ws, a, "playbook", 0, n=4, source="agent_report")
    _usage(ws, b, "resource", 0)

    team = _area(ws, "Team")
    private = _area(ws, "Alpha", private_for=a)
    empty = _area(ws, "Leer")
    art = _artifact(ws, team)
    tab = _table(ws, team, "zahlen")
    art_p = _artifact(ws, private)
    _access(ws, a, "artifact", art, "read", 0)
    _access(ws, a, "artifact", art, "write", 0)
    _access(ws, a, "table", tab, "read", 3)
    _access(ws, a, "artifact", art, "read", 40)
    _access(ws, a, "artifact", art_p, "write", 2)
    _access(ws, b, "artifact", art, "read", 1)
    _access(ws, a, "blob", "f" * 64, "read", 0)
    _access(ws, a, "node", str(UUID(int=7)), "read", 0)
    return {"a": a, "b": b, "team": team, "private": private, "empty": empty}


def _today() -> date:
    return datetime.now(UTC).date()


def _db_today() -> date:
    # `access_date` setzt die DB mit CURRENT_DATE (Zeitzone der Sitzung).
    today: date = db_fetchval("SELECT CURRENT_DATE")
    return today


def test_agent_kennzahlen(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    try:
        with TestClient(app) as client:
            ids = _setup(client, ws, auth)
            stamp = datetime.now(UTC) - timedelta(hours=5)
            db_execute(
                "UPDATE api_token SET last_used_at = $1 WHERE agent_id = $2",
                stamp,
                UUID(ids["a"]),
            )
            res = client.get(f"/v1/workspaces/{ws}/agents/{ids['a']}/usage", headers=auth)
            assert res.status_code == 200, res.text
            body = res.json()

            assert body["agent_id"] == ids["a"]
            assert body["uses_7d"] == 3  # 2 heute + 1 vor 6 Tagen
            assert body["uses_30d"] == 5  # + vor 7 und vor 29 Tagen
            assert body["uses_by_type_30d"] == {"persona": 1, "playbook": 2, "resource": 2}
            assert body["active_days_30d"] == 4
            assert body["counting_since"] == "2026-10-08"
            assert datetime.now(UTC) - datetime.fromisoformat(body["last_used_at"]) < timedelta(
                hours=1
            )
            assert datetime.fromisoformat(body["last_active_at"]) == stamp

            daily = body["daily"]
            assert len(daily) == 30
            assert daily[-1] == {"day": _today().isoformat(), "uses": 2}
            assert sum(d["uses"] for d in daily) == body["uses_30d"]

            # editor+ sieht auch die private Area; zuletzt genutzt zuerst.
            areas = body["work_areas"]
            assert [w["area_id"] for w in areas] == [ids["team"], ids["private"]]
            team = areas[0]
            # Tage im Fenster: heute und vor 3 Tagen; vor 40 Tagen nur als Datum.
            assert team["access_days_30d"] == 2
            assert team["last_access_on"] == _db_today().isoformat()
            assert areas[1] == {
                "area_id": ids["private"],
                "access_days_30d": 1,
                "last_access_on": (_db_today() - timedelta(days=2)).isoformat(),
            }
            # Keine Agent-Namen in der Antwort.
            assert "Alpha" not in res.text and "Beta" not in res.text

            # Agent ohne Auslieferung und ohne Zugriff: alles 0 bzw. leer.
            c, _ = agent_token(client, f"/v1/workspaces/{ws}", "Gamma", {}, auth)
            none = client.get(f"/v1/workspaces/{ws}/agents/{c}/usage", headers=auth).json()
            assert (none["uses_30d"], none["active_days_30d"], none["work_areas"]) == (0, 0, [])
            assert none["last_used_at"] is None and none["last_active_at"] is None
    finally:
        cleanup_workspaces([owner])


def test_agent_zuletzt_aktiv_aus_echtem_token_aufruf(make_auth_headers: AuthFactory) -> None:
    """Ein Aufruf mit dem Agent-Token setzt `last_active_at`, ohne Auslieferung."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    prefix = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            agent, agent_auth = agent_token(client, prefix, "Leser", {}, auth)
            before = client.get(f"{prefix}/agents/{agent}/usage", headers=auth).json()
            assert before["last_active_at"] is None
            assert client.get(f"{prefix}/whoami", headers=agent_auth).status_code == 200
            after = client.get(f"{prefix}/agents/{agent}/usage", headers=auth).json()
            assert after["last_active_at"] is not None
            assert after["uses_30d"] == 0  # kein Abruf eines Bausteins
    finally:
        cleanup_workspaces([owner])


def test_arbeitsbereich_zugriffe(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    try:
        with TestClient(app) as client:
            ids = _setup(client, ws, auth)
            res = client.get(f"/v1/workspaces/{ws}/work-areas/{ids['team']}/usage", headers=auth)
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["area_id"] == ids["team"]
            # A: read+write heute, Tabelle vor 3 Tagen; B: vor 1 Tag. Vor 40
            # Tagen liegt ausserhalb; Blob/Knoten/private Area zaehlen nicht.
            assert body["accesses_30d"] == 4
            assert (body["reads_30d"], body["writes_30d"]) == (3, 1)
            assert body["access_days_30d"] == 3
            assert body["distinct_agents_30d"] == 2
            assert body["last_access_on"] == _db_today().isoformat()
            daily = body["daily"]
            assert len(daily) == 30
            assert daily[-1] == {"day": _db_today().isoformat(), "accesses": 2}
            assert daily[-2]["accesses"] == 1
            assert sum(d["accesses"] for d in daily) == body["accesses_30d"]
            assert "Alpha" not in res.text and "Beta" not in res.text

            leer = client.get(
                f"/v1/workspaces/{ws}/work-areas/{ids['empty']}/usage", headers=auth
            ).json()
            assert (leer["accesses_30d"], leer["access_days_30d"]) == (0, 0)
            assert leer["last_access_on"] is None
            assert [d["accesses"] for d in leer["daily"]] == [0] * 30
    finally:
        cleanup_workspaces([owner])


def test_rechte_sichtbarkeit_und_404(make_auth_headers: AuthFactory) -> None:
    owner, viewer, stranger = fresh_user_id(), fresh_user_id(), fresh_user_id()
    ws, foreign = setup_workspace(owner), setup_workspace(stranger)
    db_execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'viewer')",
        ws,
        viewer,
    )
    auth, viewer_auth = make_auth_headers(owner), make_auth_headers(viewer)
    base = f"/v1/workspaces/{ws}"
    try:
        with TestClient(app) as client:
            ids = _setup(client, ws, auth)

            # viewer: Zaehler lesbar, aber nur geteilte Bereiche.
            seen = client.get(f"{base}/agents/{ids['a']}/usage", headers=viewer_auth)
            assert seen.status_code == 200, seen.text
            assert seen.json()["uses_30d"] == 5
            assert [w["area_id"] for w in seen.json()["work_areas"]] == [ids["team"]]
            team = client.get(f"{base}/work-areas/{ids['team']}/usage", headers=viewer_auth)
            assert team.status_code == 200, team.text
            hidden = client.get(f"{base}/work-areas/{ids['private']}/usage", headers=viewer_auth)
            assert hidden.status_code == 404, hidden.text
            assert hidden.json()["reason"] == "area_not_found"

            # Agent-gebundene Tokens: 403, auch fuer den eigenen Agenten.
            own, own_auth = agent_token(client, base, "Neugierig", {}, auth)
            for url in (
                f"{base}/agents/{own}/usage",
                f"{base}/agents/{ids['a']}/usage",
                f"{base}/work-areas/{ids['team']}/usage",
            ):
                denied = client.get(url, headers=own_auth)
                assert denied.status_code == 403, (url, denied.text)
                assert denied.json()["reason"] == "missing_capability"

            # Unbekannt oder fremd: 404.
            ghost = "00000000-0000-0000-0000-000000000000"
            other_agent, _ = agent_token(
                client, f"/v1/workspaces/{foreign}", "X", {}, make_auth_headers(stranger)
            )
            other_area = _area(foreign, "Fremd")
            for agent in (ghost, other_agent):
                missing = client.get(f"{base}/agents/{agent}/usage", headers=auth)
                assert missing.status_code == 404, missing.text
                assert missing.json()["reason"] == "agent_not_found"
            for area in (ghost, other_area):
                missing = client.get(f"{base}/work-areas/{area}/usage", headers=auth)
                assert missing.status_code == 404, missing.text
                assert missing.json()["reason"] == "area_not_found"
    finally:
        cleanup_workspaces([owner, viewer, stranger])


def test_unter_laufzeitrolle_who2be_app(
    app_role_client: TestClient, make_auth_headers: AuthFactory
) -> None:
    """RLS: unter `who2be_app` dieselben Zahlen; ein fremder Workspace sieht nichts."""
    owner, stranger = fresh_user_id(), fresh_user_id()
    ws, foreign = setup_workspace(owner), setup_workspace(stranger)
    auth, foreign_auth = make_auth_headers(owner), make_auth_headers(stranger)
    try:
        ids = _setup(app_role_client, ws, auth)
        agent = app_role_client.get(f"/v1/workspaces/{ws}/agents/{ids['a']}/usage", headers=auth)
        assert agent.status_code == 200, agent.text
        body = agent.json()
        assert (body["uses_7d"], body["uses_30d"], body["active_days_30d"]) == (3, 5, 4)
        assert len(body["work_areas"]) == 2
        area = app_role_client.get(
            f"/v1/workspaces/{ws}/work-areas/{ids['team']}/usage", headers=auth
        ).json()
        assert (area["accesses_30d"], area["distinct_agents_30d"]) == (4, 2)

        for url in (
            f"/v1/workspaces/{foreign}/agents/{ids['a']}/usage",
            f"/v1/workspaces/{foreign}/work-areas/{ids['team']}/usage",
        ):
            cross = app_role_client.get(url, headers=foreign_auth)
            assert cross.status_code == 404, cross.text
    finally:
        cleanup_workspaces([owner, stranger])
