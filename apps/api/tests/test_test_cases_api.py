"""Integrationstests Lernschleife B2: Pruefaelle, Prueflaeufe, Pruefbericht.

Deckt ADR-0053 3.2 (Rechte), 3.2.1 (Pruefall-Menge) und 6.2 (Endpunkte) ab:
Menge ueber direkte Bindung + Verknuepfungswege, `attestation` aus dem
Aufrufweg (nie aus dem Body), die n/n-Regel als 422 und die Rechte-Matrix
fuer Menschen und agent-gebundene Tokens. Laeuft nur mit erreichbarer
Datenbank; ohne DB wird uebersprungen.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import jwt
import pytest
from fastapi.testclient import TestClient

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.testing.api_helpers import agent_token
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"

_VERSION_TABLES = {
    "persona": ("persona_version", "persona_id"),
    "playbook": ("playbook_version", "playbook_id"),
    "resource": ("resource_version", "resource_id"),
    "external_tool": ("external_tool_version", "external_tool_id"),
    "system_prompt_template": ("system_prompt_template_version", "template_id"),
}


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


def _auth(user_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


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


def _version_id(entity_type: str, entity_id: str, version: int = 1) -> str:
    table, fk = _VERSION_TABLES[entity_type]

    async def _run() -> str:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            found = await conn.fetchval(
                f"SELECT id FROM {table} WHERE {fk} = $1 AND version = $2",
                UUID(entity_id),
                version,
            )
        finally:
            await conn.close()
        assert found is not None
        return str(found)

    return asyncio.run(_run())


def _persona(client: TestClient, base: str, auth: dict[str, str], name: str) -> str:
    res = client.post(
        f"{base}/personas",
        json={"name": name, "content": {"description": "d", "system_prompt": "s"}},
        headers=auth,
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


def _playbook(client: TestClient, base: str, auth: dict[str, str], name: str) -> str:
    res = client.post(
        f"{base}/playbooks",
        json={
            "name": name,
            "content": {
                "description": "d",
                "body": "1. Schritt.",
                "type": "workflow",
                "tags": [],
                "triggers": "test",
            },
        },
        headers=auth,
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


def _resource(client: TestClient, base: str, auth: dict[str, str], name: str) -> str:
    res = client.post(
        f"{base}/resources",
        json={"name": name, "content": {"description": "d", "blocks": [], "tags": []}},
        headers=auth,
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


def _agent(client: TestClient, base: str, auth: dict[str, str], name: str, **extra: Any) -> str:
    res = client.post(f"{base}/agents", json={"name": name, **extra}, headers=auth)
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


def _case_body(agent_id: str, title: str, **extra: Any) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "title": title,
        "input": "Eingabe",
        "expected_behavior": "Erwartet",
        **extra,
    }


def _create_case(
    client: TestClient, base: str, auth: dict[str, str], body: dict[str, Any]
) -> dict[str, Any]:
    res = client.post(f"{base}/test-cases", json=body, headers=auth)
    assert res.status_code == 201, res.text
    created: dict[str, Any] = res.json()
    return created


def _run(case_id: str, total: int, passed: int, verdict: str) -> dict[str, Any]:
    return {
        "test_case_id": case_id,
        "runs_total": total,
        "runs_passed": passed,
        "verdict": verdict,
    }


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    if not _db_reachable():
        pytest.skip("Keine erreichbare Datenbank — Integrationstest uebersprungen.")
    _prepare_db()
    monkeypatch.setattr(security, "get_settings", lambda: Settings(jwt_secret=_TEST_SECRET))
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    try:
        with TestClient(app) as client:
            yield client, ws, owner, _auth(owner), f"/v1/workspaces/{ws}"
    finally:
        cleanup_workspaces([owner])


@pytest.mark.integration
def test_report_set_covers_direct_and_linked_cases(world) -> None:  # type: ignore[no-untyped-def]
    """3.2.1: direkt gebundene + alle Pruefaelle betroffener Agenten, nie mehr."""
    client, _ws, _owner, auth, base = world

    # Graph: Persona P verlinkt Playbook PARENT, PARENT komponiert CHILD.
    persona = _persona(client, base, auth, "P")
    parent = _playbook(client, base, auth, "Parent")
    child = _playbook(client, base, auth, "Child")
    assert (
        client.put(
            f"{base}/playbooks/{parent}/composes", json={"child_ids": [child]}, headers=auth
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"{base}/personas/{persona}/playbooks",
            json={"playbook_ids": [parent]},
            headers=auth,
        ).status_code
        == 200
    )
    linked = _agent(client, base, auth, "A-linked", persona_id=persona)
    outsider = _agent(client, base, auth, "B-outsider")
    idle = _agent(client, base, auth, "C-idle", persona_id=_persona(client, base, auth, "Q"))

    # (2) Pruefall des betroffenen Agenten ohne Elementbindung -> in der Menge.
    general = _create_case(client, base, auth, _case_body(linked, "Allgemein"))
    # (1) Direkt am Element, Agent erreicht das Element NICHT -> in der Menge.
    direct = _create_case(
        client,
        base,
        auth,
        _case_body(outsider, "Direkt", entity_type="playbook", entity_id=child),
    )
    # Nicht betroffener Agent ohne Bindung -> NICHT in der Menge.
    _create_case(client, base, auth, _case_body(idle, "Fremd"))
    # Zurueckgezogen -> NICHT in der Menge.
    retired = _create_case(client, base, auth, _case_body(linked, "Alt"))
    assert client.post(f"{base}/test-cases/{retired['id']}/retire", headers=auth).status_code == 200

    version = _version_id("playbook", child)
    report_url = f"{base}/versions/playbook/{version}/test-report"
    report = client.get(report_url, headers=auth)
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["entity_id"] == child
    assert body["affected_agent_count"] == 1
    assert body["scope_note"] is None
    assert body["counts"] == {"total": 2, "passed": 0, "failed": 0, "error": 0, "missing": 2}
    groups = {g["agent_id"]: g for g in body["agents"]}
    assert set(groups) == {linked, outsider}
    assert groups[linked]["via"] == ["playbook_composite"]
    assert groups[outsider]["via"] == ["direct"]
    assert groups[outsider]["agent_name"] == "B-outsider"
    entry = groups[outsider]["entries"][0]
    assert entry["test_case"]["id"] == direct["id"]
    assert entry["direct"] is True
    assert entry["state"] == "missing"

    # Ergebnis melden -> letztes Ergebnis erscheint im Bericht.
    runs = client.post(
        f"{base}/test-runs",
        json={
            "subject_entity_type": "playbook",
            "subject_version_id": version,
            "results": [_run(general["id"], 3, 3, "pass"), _run(direct["id"], 2, 1, "fail")],
        },
        headers=auth,
    )
    assert runs.status_code == 201, runs.text
    body = client.get(report_url, headers=auth).json()
    assert body["counts"] == {"total": 2, "passed": 1, "failed": 1, "error": 0, "missing": 0}
    states = {e["test_case"]["id"]: e["state"] for g in body["agents"] for e in g["entries"]}
    assert states == {general["id"]: "pass", direct["id"]: "fail"}

    # Die Menge fuer das Parent-Playbook: Agent erreicht es direkt ueber die Persona.
    parent_report = client.get(
        f"{base}/versions/playbook/{_version_id('playbook', parent)}/test-report", headers=auth
    ).json()
    assert [g["agent_id"] for g in parent_report["agents"]] == [linked]
    assert parent_report["agents"][0]["via"] == ["persona_playbook"]
    # Ergebnisse gelten je Version: fuer PARENT fehlt noch alles.
    assert parent_report["counts"]["missing"] == 1


@pytest.mark.integration
def test_report_persona_template_and_shared_playbook(world) -> None:  # type: ignore[no-untyped-def]
    """3.2.1-Zeilen persona, system_prompt_template und geteiltes Playbook."""
    client, _ws, _owner, auth, base = world
    persona_a = _persona(client, base, auth, "PA")
    persona_b = _persona(client, base, auth, "PB")
    shared = _playbook(client, base, auth, "Geteilt")
    for persona in (persona_a, persona_b):
        assert (
            client.put(
                f"{base}/personas/{persona}/playbooks",
                json={"playbook_ids": [shared]},
                headers=auth,
            ).status_code
            == 200
        )
    template = client.post(
        f"{base}/system-prompts",
        json={"name": "Tpl", "content": {"body": "Du bist ein Test-Agent."}},
        headers=auth,
    )
    assert template.status_code == 201, template.text
    template_id = template.json()["id"]
    # Zwei Agenten teilen Persona A, einer davon zusaetzlich das Template.
    a1 = _agent(
        client, base, auth, "A1", persona_id=persona_a, system_prompt_template_id=template_id
    )
    a2 = _agent(client, base, auth, "A2", persona_id=persona_a)
    b1 = _agent(client, base, auth, "B1", persona_id=persona_b)
    cases = {
        agent: _create_case(client, base, auth, _case_body(agent, f"Fall {agent}"))["id"]
        for agent in (a1, a2, b1)
    }

    def report(entity_type: str, entity_id: str) -> dict[str, Any]:
        res = client.get(
            f"{base}/versions/{entity_type}/{_version_id(entity_type, entity_id)}/test-report",
            headers=auth,
        )
        assert res.status_code == 200, res.text
        body: dict[str, Any] = res.json()
        return body

    def by_agent(body: dict[str, Any]) -> dict[str, tuple[list[str], set[str]]]:
        return {
            g["agent_id"]: (g["via"], {e["test_case"]["id"] for e in g["entries"]})
            for g in body["agents"]
        }

    persona_report = report("persona", persona_a)
    assert persona_report["affected_agent_count"] == 2
    assert by_agent(persona_report) == {
        a1: (["persona"], {cases[a1]}),
        a2: (["persona"], {cases[a2]}),
    }

    template_report = report("system_prompt_template", template_id)
    assert template_report["affected_agent_count"] == 1
    assert by_agent(template_report) == {a1: (["system_prompt_template"], {cases[a1]})}

    shared_report = report("playbook", shared)
    assert shared_report["affected_agent_count"] == 3
    assert by_agent(shared_report) == {
        a1: (["persona_playbook"], {cases[a1]}),
        a2: (["persona_playbook"], {cases[a2]}),
        b1: (["persona_playbook"], {cases[b1]}),
    }
    assert shared_report["counts"]["missing"] == 3


@pytest.mark.integration
def test_report_resource_composite_and_affected_agent_without_cases(world) -> None:  # type: ignore[no-untyped-def]
    client, _ws, _owner, auth, base = world
    persona = _persona(client, base, auth, "P")
    playbook = _playbook(client, base, auth, "PB")
    top = _resource(client, base, auth, "Top")
    sub = _resource(client, base, auth, "Sub")
    client.put(
        f"{base}/personas/{persona}/playbooks", json={"playbook_ids": [playbook]}, headers=auth
    )
    assert (
        client.put(
            f"{base}/playbooks/{playbook}/resource_links",
            json={"links": [{"resource_id": top, "position": 0, "link_scope": "resource"}]},
            headers=auth,
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"{base}/resources/{top}/sub_resources",
            json={"links": [{"child_id": sub}]},
            headers=auth,
        ).status_code
        == 200
    )
    agent = _agent(client, base, auth, "R-Agent", persona_id=persona)

    body = client.get(
        f"{base}/versions/resource/{_version_id('resource', sub)}/test-report", headers=auth
    ).json()
    # Betroffen, aber ohne Pruefall: Gruppe mit leerer Liste (Luecke sichtbar).
    assert body["affected_agent_count"] == 1
    assert body["counts"]["total"] == 0
    assert body["agents"] == [
        {
            "agent_id": agent,
            "agent_name": "R-Agent",
            "via": ["persona_playbook", "resource_composite"],
            "entries": [],
        }
    ]


@pytest.mark.integration
def test_report_external_tool_scope_note_and_unknown_version(world) -> None:  # type: ignore[no-untyped-def]
    client, _ws, _owner, auth, base = world
    tool = client.post(
        f"{base}/external_tools",
        json={
            "name": "Todoist",
            "content": {
                "display_name": "Todoist",
                "mcp_server_name": "Todoist MCP",
                "tool_names": ["add_task"],
                "usage_notes": "n",
                "fallback_note": None,
                "tags": [],
            },
        },
        headers=auth,
    )
    assert tool.status_code == 201, tool.text
    body = client.get(
        f"{base}/versions/external_tool/"
        f"{_version_id('external_tool', tool.json()['id'])}/test-report",
        headers=auth,
    ).json()
    assert body["scope_note"] == "no_reference_index"
    assert body["affected_agent_count"] == 0

    missing = client.get(f"{base}/versions/playbook/{uuid4()}/test-report", headers=auth)
    assert missing.status_code == 404
    assert missing.json()["reason"] == "test_subject_version_not_found"


@pytest.mark.integration
def test_attestation_comes_from_call_path_not_body(world) -> None:  # type: ignore[no-untyped-def]
    client, _ws, owner, auth, base = world
    playbook = _playbook(client, base, auth, "PB")
    version = _version_id("playbook", playbook)
    agent_id, agent_auth = agent_token(client, base, "Reporter", {}, auth)
    case = _create_case(client, base, auth, _case_body(agent_id, "Fall"))

    def submit(headers: dict[str, str], **extra: Any) -> Any:
        return client.post(
            f"{base}/test-runs",
            json={
                "subject_entity_type": "playbook",
                "subject_version_id": version,
                "results": [_run(case["id"], 1, 1, "pass")],
                **extra,
            },
            headers=headers,
        )

    human = submit(auth)
    assert human.status_code == 201, human.text
    assert human.json()[0]["attestation"] == "human_rating"
    assert human.json()[0]["reported_by_user_id"] == str(owner)
    assert human.json()[0]["reported_by_agent_id"] is None

    by_agent = submit(agent_auth, model_provider="anthropic", model_name="m")
    assert by_agent.status_code == 201, by_agent.text
    assert by_agent.json()[0]["attestation"] == "client_self_report"
    assert by_agent.json()[0]["reported_by_agent_id"] == agent_id
    assert by_agent.json()[0]["model_name"] == "m"

    # Ein mitgeschicktes attestation-Feld wird abgewiesen, nicht verworfen.
    forged = submit(agent_auth, attestation="human_rating")
    assert forged.status_code == 422
    forged_item = client.post(
        f"{base}/test-runs",
        json={
            "subject_entity_type": "playbook",
            "subject_version_id": version,
            "results": [{**_run(case["id"], 1, 1, "pass"), "attestation": "human_rating"}],
        },
        headers=agent_auth,
    )
    assert forged_item.status_code == 422


@pytest.mark.integration
def test_run_verdict_rule_and_batch_is_atomic(world) -> None:  # type: ignore[no-untyped-def]
    client, _ws, _owner, auth, base = world
    playbook = _playbook(client, base, auth, "PB")
    version = _version_id("playbook", playbook)
    agent = _agent(client, base, auth, "A")
    case = _create_case(client, base, auth, _case_body(agent, "Fall"))
    retired = _create_case(client, base, auth, _case_body(agent, "Alt"))
    client.post(f"{base}/test-cases/{retired['id']}/retire", headers=auth)

    def submit(results: list[dict[str, Any]], entity_type: str = "playbook") -> Any:
        return client.post(
            f"{base}/test-runs",
            json={
                "subject_entity_type": entity_type,
                "subject_version_id": version,
                "results": results,
            },
            headers=auth,
        )

    for bad in (_run(case["id"], 3, 2, "pass"), _run(case["id"], 0, 0, "fail")):
        res = submit([_run(case["id"], 1, 1, "pass"), bad])
        assert res.status_code == 422, res.text
        assert res.json()["reason"] == "test_run_verdict_inconsistent"
        assert res.json()["params"]["index"] == 1

    gone = submit([_run(retired["id"], 1, 0, "fail")])
    assert gone.status_code == 409
    assert gone.json()["reason"] == "test_case_retired"

    unknown = submit([_run(str(uuid4()), 1, 0, "fail")])
    assert unknown.status_code == 404
    assert unknown.json()["reason"] == "test_case_not_found"

    # Version gehoert zu einer anderen Elementart -> 404.
    wrong_kind = submit([_run(case["id"], 1, 1, "pass")], entity_type="resource")
    assert wrong_kind.status_code == 404
    assert wrong_kind.json()["reason"] == "test_subject_version_not_found"

    # Nichts davon wurde geschrieben (alles oder nichts).
    report = client.get(f"{base}/versions/playbook/{version}/test-report", headers=auth).json()
    assert report["counts"]["total"] == 0


@pytest.mark.integration
def test_rights_for_humans(world) -> None:  # type: ignore[no-untyped-def]
    client, ws, _owner, auth, base = world
    agent = _agent(client, base, auth, "A")
    case = _create_case(client, base, auth, _case_body(agent, "Fall"))

    viewer = fresh_user_id()
    _add_member(ws, viewer, WorkspaceRole.viewer)
    viewer_auth = _auth(viewer)
    try:
        assert client.get(f"{base}/test-cases", headers=viewer_auth).status_code == 403
        assert (
            client.post(
                f"{base}/test-cases", json=_case_body(agent, "X"), headers=viewer_auth
            ).status_code
            == 403
        )
    finally:
        cleanup_workspaces([viewer])

    # Unbekannter Agent / unbekanntes Element -> 404 mit Grund.
    no_agent = client.post(f"{base}/test-cases", json=_case_body(str(uuid4()), "X"), headers=auth)
    assert no_agent.status_code == 404
    assert no_agent.json()["reason"] == "agent_not_found"
    no_entity = client.post(
        f"{base}/test-cases",
        json=_case_body(agent, "X", entity_type="resource", entity_id=str(uuid4())),
        headers=auth,
    )
    assert no_entity.status_code == 404
    assert no_entity.json()["reason"] == "resource_not_found"

    # Korrektur: neuer Pruefall mit supersedes_id, alter wird retired.
    fixed = _create_case(client, base, auth, _case_body(agent, "Fall v2", supersedes_id=case["id"]))
    assert fixed["supersedes_id"] == case["id"]
    old = client.get(f"{base}/test-cases/{case['id']}", headers=auth).json()
    assert old["status"] == "retired"
    again = client.post(
        f"{base}/test-cases", json=_case_body(agent, "v3", supersedes_id=case["id"]), headers=auth
    )
    assert again.status_code == 409
    assert again.json()["reason"] == "test_case_retired"

    active = client.get(f"{base}/test-cases", params={"status": "active"}, headers=auth).json()
    assert [c["id"] for c in active] == [fixed["id"]]


@pytest.mark.integration
def test_rights_for_agent_tokens(world) -> None:  # type: ignore[no-untyped-def]
    client, _ws, _owner, auth, base = world
    playbook = _playbook(client, base, auth, "PB")
    version = _version_id("playbook", playbook)
    plain_id, plain_auth = agent_token(client, base, "Plain", {}, auth)
    triage_id, triage_auth = agent_token(client, base, "Triage", {"case_triage": True}, auth)
    silent_id, silent_auth = agent_token(client, base, "Silent", {"test_report": False}, auth)
    own = _create_case(client, base, auth, _case_body(plain_id, "Eigen"))
    foreign = _create_case(client, base, auth, _case_body(triage_id, "Fremd"))
    _create_case(client, base, auth, _case_body(silent_id, "Stumm"))

    # Ohne case_triage: nur der eigene Agent.
    listed = client.get(f"{base}/test-cases", headers=plain_auth)
    assert listed.status_code == 200, listed.text
    assert [c["id"] for c in listed.json()] == [own["id"]]
    assert client.get(f"{base}/test-cases/{own['id']}", headers=plain_auth).status_code == 200
    hidden = client.get(f"{base}/test-cases/{foreign['id']}", headers=plain_auth)
    assert hidden.status_code == 404
    other = client.get(f"{base}/test-cases", params={"agent_id": triage_id}, headers=plain_auth)
    assert other.status_code == 403
    assert other.json()["reason"] == "missing_capability"
    create = client.post(f"{base}/test-cases", json=_case_body(plain_id, "X"), headers=plain_auth)
    assert create.status_code == 403
    assert create.json()["reason"] == "missing_capability"
    report = client.get(f"{base}/versions/playbook/{version}/test-report", headers=plain_auth)
    assert report.status_code == 403
    # Ergebnis zu einem fremden Pruefall melden: nicht lesbar = nicht vorhanden.
    foreign_run = client.post(
        f"{base}/test-runs",
        json={
            "subject_entity_type": "playbook",
            "subject_version_id": version,
            "results": [_run(foreign["id"], 1, 1, "pass")],
        },
        headers=plain_auth,
    )
    assert foreign_run.status_code == 404

    # Mit case_triage: alle lesen, anlegen (created_by_kind=agent), nie retire.
    assert len(client.get(f"{base}/test-cases", headers=triage_auth).json()) == 3
    made = client.post(
        f"{base}/test-cases", json=_case_body(plain_id, "Vom Agenten"), headers=triage_auth
    )
    assert made.status_code == 201, made.text
    assert made.json()["created_by_kind"] == "agent"
    assert made.json()["created_by"] == triage_id
    assert (
        client.get(
            f"{base}/versions/playbook/{version}/test-report", headers=triage_auth
        ).status_code
        == 200
    )
    for forbidden in (
        client.post(f"{base}/test-cases/{own['id']}/retire", headers=triage_auth),
        client.post(
            f"{base}/test-cases",
            json=_case_body(plain_id, "v2", supersedes_id=own["id"]),
            headers=triage_auth,
        ),
    ):
        assert forbidden.status_code == 403
        assert forbidden.json()["reason"] == "missing_capability"

    # test_report abgeschaltet -> keine Meldungen.
    silent_run = client.post(
        f"{base}/test-runs",
        json={
            "subject_entity_type": "playbook",
            "subject_version_id": version,
            "results": [_run(own["id"], 1, 1, "pass")],
        },
        headers=silent_auth,
    )
    assert silent_run.status_code == 403


def _report_case(client: TestClient, base: str, auth: dict[str, str], agent_id: str) -> str:
    res = client.post(
        f"{base}/cases",
        json={
            "agent_id": agent_id,
            "situation": "Situation",
            "behavior": "Verhalten",
            "expected_behavior": "Erwartet",
        },
        headers=auth,
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


@pytest.mark.integration
def test_list_filters_by_origin_case(world) -> None:  # type: ignore[no-untyped-def]
    """`GET /test-cases?origin_case_id=` (D6-API2): die Pruefaelle eines Falls."""
    client, _ws, _owner, auth, base = world
    agent = _agent(client, base, auth, "A")
    case_a = _report_case(client, base, auth, agent)
    case_b = _report_case(client, base, auth, agent)
    from_a = _create_case(client, base, auth, _case_body(agent, "Aus A", origin_case_id=case_a))
    from_a_2 = _create_case(client, base, auth, _case_body(agent, "Aus A 2", origin_case_id=case_a))
    from_b = _create_case(client, base, auth, _case_body(agent, "Aus B", origin_case_id=case_b))
    plain = _create_case(client, base, auth, _case_body(agent, "Ohne Fall"))

    def ids(params: dict[str, str]) -> list[str]:
        res = client.get(f"{base}/test-cases", params=params, headers=auth)
        assert res.status_code == 200, res.text
        return [c["id"] for c in res.json()]

    unfiltered = ids({})
    assert unfiltered == [from_a["id"], from_a_2["id"], from_b["id"], plain["id"]]
    by_a = ids({"origin_case_id": case_a})
    assert by_a == [from_a["id"], from_a_2["id"]]
    assert by_a != unfiltered
    assert ids({"origin_case_id": case_b}) == [from_b["id"]]
    assert ids({"origin_case_id": str(uuid4())}) == []

    # Kombinierbar: ein abgeloester Pruefall faellt mit status=active heraus.
    client.post(f"{base}/test-cases/{from_a_2['id']}/retire", headers=auth)
    assert ids({"origin_case_id": case_a, "status": "active"}) == [from_a["id"]]
    assert ids({"origin_case_id": case_a, "agent_id": str(uuid4())}) == []

    # Isolationsprobe: Fall und Pruefall eines fremden Workspace bleiben dort.
    stranger = fresh_user_id()
    foreign_ws = setup_workspace(stranger)
    try:
        foreign_base = f"/v1/workspaces/{foreign_ws}"
        foreign_auth = _auth(stranger)
        foreign_agent = _agent(client, foreign_base, foreign_auth, "Fremd")
        foreign_case = _report_case(client, foreign_base, foreign_auth, foreign_agent)
        foreign_test = _create_case(
            client,
            foreign_base,
            foreign_auth,
            _case_body(foreign_agent, "Fremder Pruefall", origin_case_id=foreign_case),
        )
        seen_there = client.get(
            f"{foreign_base}/test-cases",
            params={"origin_case_id": foreign_case},
            headers=foreign_auth,
        ).json()
        assert [c["id"] for c in seen_there] == [foreign_test["id"]]
        assert ids({"origin_case_id": foreign_case}) == []
    finally:
        cleanup_workspaces([stranger])
