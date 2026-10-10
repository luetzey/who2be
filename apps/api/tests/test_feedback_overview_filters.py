"""Integrationstests fuer die Filter von `GET /feedback-overview` (Navigation A6).

Kritische Invarianten (Plan 2026-10-10-0600, PM-Weichen W2/W3):
- Ohne Parameter: unveraendert die Gesamtsumme des Workspace.
- `agent_id` filtert `usage_event` UND `agent_feedback` auf diesen Agenten.
- `days` (1..365) filtert beide Tabellen auf die letzten N Tage; ausserhalb → 422.
- Beide Filter kombinierbar.
- Unbekannter oder workspace-fremder Agent → 404 `agent_not_found`.
- Rechte editor+ wie bisher; viewer 403 auch mit `agent_id` (kein Enumerieren).
- Unter der Laufzeitrolle `who2be_app` (RLS) dasselbe Ergebnis.

Die Telemetrie wird direkt (Superuser) mit gesetztem `created_at` geschrieben —
nur so lassen sich Ereignisse ausserhalb des Zeitfensters erzeugen.
"""

from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from test_rls_control_plane_api import app_role_client  # type: ignore[import-not-found]

from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token, db_execute
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

AuthFactory = Callable[[UUID], dict[str, str]]
# entity_id -> (usage_count, feedback_count, negative_count, helpful_count)
Counts = dict[str, tuple[int, int, int, int]]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("patched_jwt_secret", "migrated_db"),
]

__all__ = ["app_role_client"]


def _resource(client: TestClient, prefix: str, auth: dict[str, str], name: str) -> str:
    res = client.post(
        f"{prefix}/resources",
        json={"name": name, "content": {"description": "d", "blocks": [], "tags": []}},
        headers=auth,
    )
    assert res.status_code == 201, res.text
    rid: str = res.json()["id"]
    return rid


def _usage(ws: UUID, agent: str | None, rid: str, days_ago: int, n: int = 1) -> None:
    for _ in range(n):
        db_execute(
            "INSERT INTO usage_event (workspace_id, agent_id, entity_type, entity_id, "
            "version, outcome, source, created_at) VALUES ($1, $2, 'resource', $3, 1, NULL, "
            "'server', now() - make_interval(days => $4))",
            ws,
            UUID(agent) if agent else None,
            UUID(rid),
            days_ago,
        )


def _feedback(ws: UUID, agent: str | None, rid: str, signal: str, days_ago: int) -> None:
    db_execute(
        "INSERT INTO agent_feedback (workspace_id, agent_id, entity_type, entity_id, "
        "version, signal, created_at) VALUES ($1, $2, 'resource', $3, 1, $4, "
        "now() - make_interval(days => $5))",
        ws,
        UUID(agent) if agent else None,
        UUID(rid),
        signal,
        days_ago,
    )


def _setup(client: TestClient, ws: UUID, auth: dict[str, str]) -> dict[str, str]:
    """Agenten A, B; Resources R1, R2; Ereignisse innerhalb und ausserhalb 30 Tage."""
    prefix = f"/v1/workspaces/{ws}"
    a, _ = agent_token(client, prefix, "Alpha", {}, auth)
    b, _ = agent_token(client, prefix, "Beta", {}, auth)
    r1 = _resource(client, prefix, auth, "R1")
    r2 = _resource(client, prefix, auth, "R2")
    _usage(ws, a, r1, 0, n=2)
    _usage(ws, a, r1, 40)  # ausserhalb 30 Tage
    _usage(ws, b, r1, 1)
    _usage(ws, None, r2, 0)  # Mensch/ungebunden: keinem Agenten zugeordnet
    _feedback(ws, a, r1, "outdated", 0)
    _feedback(ws, a, r2, "helpful", 100)  # ausserhalb 30 Tage
    _feedback(ws, b, r2, "unclear", 2)
    return {"a": a, "b": b, "r1": r1, "r2": r2}


def _counts(client: TestClient, ws: UUID, auth: dict[str, str], query: str = "") -> Counts:
    res = client.get(f"/v1/workspaces/{ws}/feedback-overview{query}", headers=auth)
    assert res.status_code == 200, res.text
    return {
        i["entity_id"]: (
            i["usage_count"],
            i["feedback_count"],
            i["negative_count"],
            i["helpful_count"],
        )
        for i in res.json()["items"]
    }


def _add_viewer(workspace_id: UUID, user_id: UUID) -> None:
    db_execute(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'viewer')",
        workspace_id,
        user_id,
    )


def test_filter_einzeln_und_kombiniert(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    auth = make_auth_headers(owner)
    try:
        with TestClient(app) as client:
            ids = _setup(client, ws, auth)
            r1, r2 = ids["r1"], ids["r2"]

            # Ohne Parameter: Gesamtsumme wie bisher (alle Agenten, alle Zeiten).
            assert _counts(client, ws, auth) == {r1: (4, 1, 1, 0), r2: (1, 2, 1, 1)}

            # Nur agent_id: beide Tabellen auf Agent A.
            assert _counts(client, ws, auth, f"?agent_id={ids['a']}") == {
                r1: (3, 1, 1, 0),
                r2: (0, 1, 0, 1),
            }
            assert _counts(client, ws, auth, f"?agent_id={ids['b']}") == {
                r1: (1, 0, 0, 0),
                r2: (0, 1, 1, 0),
            }

            # Nur days: beide Tabellen auf die letzten 30 Tage.
            assert _counts(client, ws, auth, "?days=30") == {
                r1: (3, 1, 1, 0),
                r2: (1, 1, 1, 0),
            }
            # Obergrenze 365 schliesst alles ein — gleich der Gesamtsumme.
            assert _counts(client, ws, auth, "?days=365") == _counts(client, ws, auth)

            # Kombination: Agent A, 30 Tage — R2 hat dann kein Ereignis mehr.
            assert _counts(client, ws, auth, f"?agent_id={ids['a']}&days=30") == {
                r1: (2, 1, 1, 0),
            }
            assert _counts(client, ws, auth, f"?agent_id={ids['b']}&days=1") == {}
    finally:
        cleanup_workspaces([owner])


def test_validierung_404_und_rechte(make_auth_headers: AuthFactory) -> None:
    owner, viewer, stranger = fresh_user_id(), fresh_user_id(), fresh_user_id()
    ws, foreign = setup_workspace(owner), setup_workspace(stranger)
    _add_viewer(ws, viewer)
    auth = make_auth_headers(owner)
    url = f"/v1/workspaces/{ws}/feedback-overview"
    try:
        with TestClient(app) as client:
            ids = _setup(client, ws, auth)

            for bad in ("days=0", "days=366", "days=abc", "agent_id=kein-uuid"):
                res = client.get(f"{url}?{bad}", headers=auth)
                assert res.status_code == 422, (bad, res.text)

            ghost = "00000000-0000-0000-0000-000000000000"
            missing = client.get(f"{url}?agent_id={ghost}", headers=auth)
            assert missing.status_code == 404, missing.text
            assert missing.json()["reason"] == "agent_not_found"

            other, _ = agent_token(
                client, f"/v1/workspaces/{foreign}", "Fremd", {}, make_auth_headers(stranger)
            )
            cross = client.get(f"{url}?agent_id={other}&days=30", headers=auth)
            assert cross.status_code == 404, cross.text
            assert cross.json()["reason"] == "agent_not_found"

            # viewer: 403 wie bisher — auch mit unbekanntem Agenten kein 404
            # (die Rolle wird vor dem Agent-Lookup geprueft).
            viewer_auth = make_auth_headers(viewer)
            for query in ("", f"?agent_id={ids['a']}", f"?agent_id={ghost}"):
                denied = client.get(f"{url}{query}", headers=viewer_auth)
                assert denied.status_code == 403, (query, denied.text)
    finally:
        cleanup_workspaces([owner, viewer, stranger])


def test_unter_laufzeitrolle_who2be_app(
    app_role_client: TestClient, make_auth_headers: AuthFactory
) -> None:
    """RLS: unter `who2be_app` dieselben Zahlen; ein fremder Workspace kennt
    den Agenten nicht (404) und sieht dessen Ereignisse nicht."""
    owner, stranger = fresh_user_id(), fresh_user_id()
    ws, foreign = setup_workspace(owner), setup_workspace(stranger)
    auth, foreign_auth = make_auth_headers(owner), make_auth_headers(stranger)
    try:
        ids = _setup(app_role_client, ws, auth)
        assert _counts(app_role_client, ws, auth, f"?agent_id={ids['a']}&days=30") == {
            ids["r1"]: (2, 1, 1, 0),
        }
        assert _counts(app_role_client, ws, auth) == {
            ids["r1"]: (4, 1, 1, 0),
            ids["r2"]: (1, 2, 1, 1),
        }
        other = app_role_client.get(
            f"/v1/workspaces/{foreign}/feedback-overview?agent_id={ids['a']}",
            headers=foreign_auth,
        )
        assert other.status_code == 404, other.text
        assert _counts(app_role_client, foreign, foreign_auth) == {}
    finally:
        cleanup_workspaces([owner, stranger])
