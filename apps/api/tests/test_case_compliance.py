"""Compliance-Naben fuer Faelle (ADR-0053 Anhang A.1/A.2, Paket D1b).

Belegt gegen die echte DB, was Migration 0100 fuer Art. 15/17/20 bedeutet:

- **Auskunft (Art. 15/20):** der GDPR-Export liefert je Workspace `cases`,
  jeder Fall mit Verlauf (`events`), Zuordnung (`elements`) und
  Schilderungen (`statements`). Sichtregel nach 3.3 (Rechte): ab `editor`
  alle Faelle, darunter nur die selbst gemeldeten. Kind-Zeilen werden nur
  fuer exportierte Faelle GELADEN.
- **Loeschung (Art. 17), Account:** `purge_account_data` setzt
  `agent_case.reporter_user_id`, menschliche `agent_case_event.actor_id` und
  menschliche `agent_case_element.assigned_by` auf den Sentinel — auch in
  einem FREMDEN Workspace. Agent-Zeilen mit zufaellig gleicher UUID bleiben.
  Die Personal-Org faellt auch dann, wenn dort ein Lernvorschlag in einen
  Fall umgewandelt wurde (FK NO ACTION).
- **Loeschen eines Falls (Q6):** gelingt auch mit umgewandeltem
  Lernvorschlag; der faellt mit, je Zeile eine inhaltsfreie Spur.

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated, Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from test_agent_case_schema import (  # type: ignore[import-not-found]
    _human_report,
    _insert_lesson,
    _with_repo,
)

from who2be_api.core.config import get_settings
from who2be_api.core.db import get_pool
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.repositories.account_repository import (
    ANONYMIZED_USER_ID,
    PgAccountPurgeRepository,
)
from who2be_api.repositories.case_repository import CASE_DELETED_AUDIT_ACTION
from who2be_api.repositories.memory_repository import MEMORY_DELETED_AUDIT_ACTION
from who2be_api.routers.gdpr import get_export_service
from who2be_api.services.gdpr_export_service import GdprExportService
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import WorkspaceRole

pytestmark = pytest.mark.integration

AuthFactory = Callable[[UUID], dict[str, str]]

_CHILD_TABLES = ("agent_case_event", "agent_case_element", "agent_case_statement")


async def _insert_case(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    agent_id: UUID,
    *,
    reporter_user_id: UUID | None,
    situation: str,
) -> UUID:
    """Fall als Mensch (`reporter_user_id`) oder als der Agent selbst gemeldet."""
    human = reporter_user_id is not None
    case_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case (workspace_id, agent_id, reporter_kind, reporter_user_id, "
        " reporter_agent_id, situation, behavior, expected_behavior) "
        "VALUES ($1, $2, $3, $4, $5, $6, 'Keine Frist genannt.', 'Nennt die Frist.') "
        "RETURNING id",
        workspace_id,
        agent_id,
        "human" if human else "agent",
        reporter_user_id,
        None if human else agent_id,
        situation,
    )
    return case_id


async def _insert_event(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    case_id: UUID,
    event: str,
    *,
    actor_kind: str,
    actor_id: UUID | None,
    note: str | None = None,
) -> UUID:
    event_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case_event (workspace_id, case_id, event, actor_kind, actor_id, note) "
        "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
        workspace_id,
        case_id,
        event,
        actor_kind,
        actor_id,
        note,
    )
    return event_id


async def _insert_element(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    case_id: UUID,
    *,
    assigned_by_kind: str,
    assigned_by: UUID,
    target: str = "model_limit",
) -> UUID:
    element_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case_element "
        "(workspace_id, case_id, target, entity_id, assigned_by_kind, assigned_by) "
        "VALUES ($1, $2, $3, NULL, $4, $5) RETURNING id",
        workspace_id,
        case_id,
        target,
        assigned_by_kind,
        assigned_by,
    )
    return element_id


async def _insert_statement(
    conn: asyncpg.Connection, workspace_id: UUID, case_id: UUID, agent_id: UUID, conflict: str
) -> UUID:
    statement_id: UUID = await conn.fetchval(
        "INSERT INTO agent_case_statement "
        "(workspace_id, case_id, agent_id, followed_instruction, missing_information, conflict) "
        "VALUES ($1, $2, $3, 'Playbook Kuendigung', 'Die Frist', $4) RETURNING id",
        workspace_id,
        case_id,
        agent_id,
        conflict,
    )
    return statement_id


# --- Auskunft (Art. 15/20) ---------------------------------------------------


def _target_workspace(bundle: dict[str, Any], ws: UUID) -> dict[str, Any]:
    workspaces = [
        w for org in bundle["organizations"] for w in org["workspaces"] if w["id"] == str(ws)
    ]
    assert len(workspaces) == 1, workspaces
    target: dict[str, Any] = workspaces[0]
    return target


def _add_member(workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> None:
    """Zweites Mitglied direkt setzen (Muster `test_memory_compliance`)."""

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


class _CaseSpyPool:
    """Reicht alles an den echten Pool durch und merkt sich die GELADENEN
    Kind-Zeilen der Faelle — belegt, was der Export liest, nicht nur, was er
    ausliefert."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self.child_case_ids: set[UUID] = set()

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        rows: list[asyncpg.Record] = await self._pool.fetch(query, *args)
        if any(table in query for table in _CHILD_TABLES):
            self.child_case_ids.update(row["case_id"] for row in rows)
        return rows

    def __getattr__(self, name: str) -> Any:
        return getattr(self._pool, name)


def _seed_cases(ws: UUID, agent_id: UUID, owner: UUID, member: UUID) -> dict[str, UUID]:
    """Je ein Fall von Mitglied und Owner, ein Fall des Agenten; alle mit Kindern."""

    async def _run() -> dict[str, UUID]:
        conn = await asyncpg.connect(get_settings().database_url)
        try:
            ids: dict[str, UUID] = {}
            for key, reporter in (("own", member), ("foreign", owner), ("agent", None)):
                case = await _insert_case(
                    conn, ws, agent_id, reporter_user_id=reporter, situation=f"Situation {key}"
                )
                ids[key] = case
                ids[f"{key}_reported"] = await _insert_event(
                    conn,
                    ws,
                    case,
                    "reported",
                    actor_kind="human" if reporter else "agent",
                    actor_id=reporter or agent_id,
                )
                ids[f"{key}_triaged"] = await _insert_event(
                    conn,
                    ws,
                    case,
                    "triaged",
                    actor_kind="human",
                    actor_id=owner,
                    note=f"Notiz {key}",
                )
                ids[f"{key}_element"] = await _insert_element(
                    conn, ws, case, assigned_by_kind="human", assigned_by=owner
                )
                ids[f"{key}_statement"] = await _insert_statement(
                    conn, ws, case, agent_id, f"Schilderung {key}"
                )
            return ids
        finally:
            await conn.close()

    return asyncio.run(_run())


@pytest.mark.parametrize(
    ("member_role", "sees_all"),
    [(WorkspaceRole.viewer, False), (WorkspaceRole.editor, True)],
)
@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_gdpr_export_cases_follow_role_and_load_only_exported_children(
    make_auth_headers: AuthFactory, member_role: WorkspaceRole, sees_all: bool
) -> None:
    """viewer: nur selbst gemeldete Faelle; editor: alle des Workspace. Jeder
    Fall traegt Verlauf, Zuordnung und Schilderungen; Kind-Zeilen fremder
    Faelle werden fuer den viewer weder ausgeliefert noch geladen."""
    owner = fresh_user_id()
    member = fresh_user_id()
    ws = setup_workspace(owner)
    _add_member(ws, member, member_role)
    spy: dict[str, _CaseSpyPool] = {}

    def _spied_service(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> GdprExportService:
        spy["pool"] = _CaseSpyPool(pool)
        return GdprExportService(spy["pool"])

    try:
        with TestClient(app) as client:
            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={"name": "Berater"},
                headers=make_auth_headers(owner),
            )
            assert agent.status_code == 201, agent.text
            ids = _seed_cases(ws, UUID(agent.json()["id"]), owner, member)

            app.dependency_overrides[get_export_service] = _spied_service
            try:
                exported = client.get("/v1/gdpr/export", headers=make_auth_headers(member))
            finally:
                app.dependency_overrides.pop(get_export_service, None)
            assert exported.status_code == 200, exported.text
            bundle = exported.json()

        target = _target_workspace(bundle, ws)
        assert target["role"] == member_role.value
        expected = ["own", "foreign", "agent"] if sees_all else ["own"]
        assert [c["id"] for c in target["cases"]] == [str(ids[key]) for key in expected]

        # Eigener Fall immer vollstaendig: Inhalt, Verlauf, Zuordnung, Schilderung.
        own = target["cases"][0]
        assert own["situation"] == "Situation own"
        assert own["reporter_user_id"] == str(member)
        assert "workspace_id" not in own
        assert [e["id"] for e in own["events"]] == [
            str(ids["own_reported"]),
            str(ids["own_triaged"]),
        ]
        assert own["events"][1]["note"] == "Notiz own"
        assert "workspace_id" not in own["events"][0]
        assert [e["id"] for e in own["elements"]] == [str(ids["own_element"])]
        assert [s["conflict"] for s in own["statements"]] == ["Schilderung own"]

        dumped = json.dumps(bundle, default=str)
        loaded = spy["pool"].child_case_ids
        if sees_all:
            assert loaded == {ids["own"], ids["foreign"], ids["agent"]}
            foreign = target["cases"][1]
            assert [s["conflict"] for s in foreign["statements"]] == ["Schilderung foreign"]
            assert target["export_manifest"]["cases"] == {"included": True, "scope": "workspace"}
        else:
            # Fremde Faelle: weder Fall noch Verlauf, Zuordnung oder Schilderung.
            for key in ("foreign", "agent"):
                assert str(ids[key]) not in dumped
                assert f"Situation {key}" not in dumped
                assert f"Notiz {key}" not in dumped
                assert f"Schilderung {key}" not in dumped
                assert str(ids[f"{key}_element"]) not in dumped
            assert loaded == {ids["own"]}
            manifest = target["export_manifest"]["cases"]
            assert manifest["scope"] == "own_reports"
            assert "editor" in manifest["reason"]
    finally:
        cleanup_workspaces([owner])


# --- Loeschung (Art. 17), Account ----------------------------------------------


def _in_isolated_schema(body: Callable[[asyncpg.Connection], Awaitable[None]]) -> None:
    """Owner-Verbindung (wie der Purge-Job) auf einem frisch migrierten Schema."""
    schema = f"case_erasure_{secrets.token_hex(6)}"

    async def _run() -> None:
        owner = await asyncpg.connect(get_settings().database_url)
        try:
            await owner.execute(f'CREATE SCHEMA "{schema}"')
            await owner.execute(f'SET search_path TO "{schema}"')
            await apply_migrations(owner, MIGRATIONS_DIR)
            await body(owner)
        finally:
            await owner.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await owner.close()

    asyncio.run(_run())


async def _workspace(
    owner: asyncpg.Connection, member: UUID, *, kind: str = "company", slug: str | None = None
) -> tuple[UUID, UUID]:
    """Org + Workspace + Agent; liefert (workspace_id, agent_id)."""
    org_id: UUID = await owner.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, $2) RETURNING id",
        slug or f"o-{secrets.token_hex(4)}",
        kind,
    )
    ws_id: UUID = await owner.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
        org_id,
    )
    agent_id: UUID = await owner.fetchval(
        "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, 'a') RETURNING id",
        ws_id,
        member,
    )
    return ws_id, agent_id


def test_account_purge_anonymizes_case_person_references() -> None:
    async def body(owner: asyncpg.Connection) -> None:
        user, other_user = uuid4(), uuid4()
        # Fremder Company-Workspace: hier greift KEINE CASCADE.
        ws, agent = await _workspace(owner, other_user)
        # Personal-Org des Users mit Fall UND darin umgewandeltem
        # Lernvorschlag: die Org-CASCADE muss trotz FK NO ACTION durchgehen.
        ws_personal, agent_personal = await _workspace(owner, user, kind="personal", slug=str(user))

        case_user = await _insert_case(owner, ws, agent, reporter_user_id=user, situation="S1")
        ev_human = await _insert_event(
            owner, ws, case_user, "reported", actor_kind="human", actor_id=user
        )
        # Agent-Event/-Zuordnung mit zufaellig gleicher UUID: keine Person.
        ev_agent_same_id = await _insert_event(
            owner, ws, case_user, "triaged", actor_kind="agent", actor_id=user
        )
        el_human = await _insert_element(
            owner, ws, case_user, assigned_by_kind="human", assigned_by=user
        )
        el_agent_same_id = await _insert_element(
            owner, ws, case_user, assigned_by_kind="agent", assigned_by=user, target="tool_policy"
        )
        case_other = await _insert_case(
            owner, ws, agent, reporter_user_id=other_user, situation="S2"
        )
        ev_other = await _insert_event(
            owner, ws, case_other, "reported", actor_kind="human", actor_id=other_user
        )
        el_other = await _insert_element(
            owner, ws, case_other, assigned_by_kind="human", assigned_by=other_user
        )

        case_personal = await _insert_case(
            owner, ws_personal, agent_personal, reporter_user_id=user, situation="S3"
        )
        await _insert_lesson(owner, ws_personal, agent_personal, converted_case_id=case_personal)

        anonymized = await PgAccountPurgeRepository(owner).purge_account_data(user)
        # reporter_user_id + ein menschliches Event + eine menschliche Zuordnung.
        assert anonymized == 3

        # Personal-Org samt Fall und Lernvorschlag ist weg.
        assert (
            await owner.fetchval("SELECT count(*) FROM workspace WHERE id = $1", ws_personal) == 0
        )
        assert (
            await owner.fetchval("SELECT count(*) FROM agent_case WHERE id = $1", case_personal)
            == 0
        )

        # Keine Personen-Spalte traegt den User mehr (ausser Agent-Zeilen).
        assert (
            await owner.fetchval(
                "SELECT count(*) FROM agent_case WHERE reporter_user_id = $1", user
            )
            == 0
        )
        reporters = {
            row["id"]: row["reporter_user_id"]
            for row in await owner.fetch("SELECT id, reporter_user_id FROM agent_case")
        }
        assert reporters == {case_user: ANONYMIZED_USER_ID, case_other: other_user}
        actors = {
            row["id"]: row["actor_id"]
            for row in await owner.fetch("SELECT id, actor_id FROM agent_case_event")
        }
        assert actors == {
            ev_human: ANONYMIZED_USER_ID,
            ev_agent_same_id: user,
            ev_other: other_user,
        }
        assigners = {
            row["id"]: row["assigned_by"]
            for row in await owner.fetch("SELECT id, assigned_by FROM agent_case_element")
        }
        assert assigners == {
            el_human: ANONYMIZED_USER_ID,
            el_agent_same_id: user,
            el_other: other_user,
        }
        # Inhalt des Falls bleibt als Inhalt des Workspace stehen.
        assert (
            await owner.fetchval("SELECT situation FROM agent_case WHERE id = $1", case_user)
            == "S1"
        )

        # Idempotent: ein zweiter Lauf findet nichts mehr.
        assert await PgAccountPurgeRepository(owner).purge_account_data(user) == 0
        assert (
            await owner.fetchval("SELECT reporter_user_id FROM agent_case WHERE id = $1", case_user)
            == ANONYMIZED_USER_ID
        )

    _in_isolated_schema(body)


# --- Loeschen eines Falls (Q6) -------------------------------------------------


def test_delete_case_with_converted_lesson_removes_both_without_content() -> None:
    """Rot-Probe aus #843: vor D1b brach das Loeschen am FK NO ACTION ab."""

    async def body(repo: Any, env: Any) -> None:
        s = env.seed
        case = await _human_report(repo, s, s.agent_a)
        lesson = await _insert_lesson(env.owner, s.ws_a, s.agent_a, converted_case_id=case)
        await env.owner.execute(
            "INSERT INTO agent_memory_event (workspace_id, memory_id, event, actor_kind, agent_id) "
            "VALUES ($1, $2, 'converted', 'system', NULL)",
            s.ws_a,
            lesson,
        )
        untouched = await _insert_lesson(env.owner, s.ws_a, s.agent_a)

        assert await repo.delete_case(s.ws_a, case, s.user) is True
        assert await repo.get_case(s.ws_a, case) is None
        remaining = {row["id"] for row in await env.owner.fetch("SELECT id FROM agent_memory")}
        assert remaining == {untouched}
        assert (
            await env.owner.fetchval(
                "SELECT count(*) FROM agent_memory_event WHERE memory_id = $1", lesson
            )
            == 0
        )

        audit = await env.owner.fetch(
            "SELECT actor_id, action, target, detail FROM audit_log ORDER BY action"
        )
        assert [(r["action"], r["target"], r["actor_id"]) for r in audit] == [
            (CASE_DELETED_AUDIT_ACTION, str(case), s.user),
            (MEMORY_DELETED_AUDIT_ACTION, str(lesson), s.user),
        ]
        assert all(r["detail"] in ("{}", {}) for r in audit)  # inhaltsfrei

        # Zweiter Aufruf: nichts mehr da, keine weitere Spur.
        assert await repo.delete_case(s.ws_a, case, s.user) is False
        assert await env.owner.fetchval("SELECT count(*) FROM audit_log") == 2

    _with_repo(body)
