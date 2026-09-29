"""Compliance-Naben fuer Pruefall + Prueflauf (ADR-0053 Anhang A.1, Paket B1c).

Belegt gegen die echte DB, was Migration 0089 fuer Art. 15/17/20 bedeutet:

- **Auskunft (Art. 15/20):** `test_cases` und `test_runs` stehen im
  GDPR-Export des Workspace, ohne die interne Mandanten-Spalte.
- **Loeschung (Art. 17), Account:** `purge_account_data` setzt
  `test_case.created_by` (nur `created_by_kind = 'human'`) und
  `test_run.reported_by_user_id` auf den Sentinel — auch in einem FREMDEN
  Workspace, den keine Personal-Org-CASCADE erreicht. Ein vom Agenten
  angelegter Pruefall bleibt unberuehrt, selbst wenn seine `created_by`
  zufaellig dieselbe UUID traegt.
- **Loeschung (Art. 17), Org:** `purge_organization` raeumt beide Tabellen
  ueber die FK-CASCADE ab (anders als `agent_access_log`, FK NO ACTION);
  fremde Organisationen bleiben unberuehrt.

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient

from who2be_api.core.config import get_settings
from who2be_api.core.migrations import MIGRATIONS_DIR, apply_migrations
from who2be_api.main import app
from who2be_api.repositories.account_repository import (
    ANONYMIZED_USER_ID,
    PgAccountPurgeRepository,
)
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace

pytestmark = pytest.mark.integration

AuthFactory = Callable[[UUID], dict[str, str]]


async def _insert_case(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    agent_id: UUID,
    *,
    created_by: UUID,
    created_by_kind: str = "human",
    title: str = "Kuendigung",
) -> UUID:
    case_id: UUID = await conn.fetchval(
        "INSERT INTO test_case "
        "(workspace_id, agent_id, title, input, expected_behavior, check_kind, "
        " created_by_kind, created_by) "
        "VALUES ($1, $2, $3, 'Ich will kuendigen.', 'Nennt die Frist.', 'human_rule', "
        "        $4, $5) RETURNING id",
        workspace_id,
        agent_id,
        title,
        created_by_kind,
        created_by,
    )
    return case_id


async def _insert_run(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    case_id: UUID,
    *,
    reported_by_user_id: UUID,
) -> UUID:
    run_id: UUID = await conn.fetchval(
        "INSERT INTO test_run "
        "(workspace_id, test_case_id, subject_entity_type, subject_version_id, "
        " runs_total, runs_passed, verdict, output_excerpt, attestation, reported_by_user_id) "
        "VALUES ($1, $2, 'playbook', $3, 1, 0, 'fail', 'Antwort ohne Frist.', "
        "        'human_rating', $4) RETURNING id",
        workspace_id,
        case_id,
        uuid4(),
        reported_by_user_id,
    )
    return run_id


# --- Auskunft (Art. 15/20) ---------------------------------------------------


@pytest.mark.usefixtures("patched_jwt_secret", "migrated_db")
def test_gdpr_export_contains_test_cases_and_runs(make_auth_headers: AuthFactory) -> None:
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    try:
        with TestClient(app) as client:
            agent = client.post(
                f"/v1/workspaces/{ws}/agents",
                json={"name": "Pruefling"},
                headers=make_auth_headers(owner),
            )
            assert agent.status_code == 201, agent.text
            agent_id = UUID(agent.json()["id"])

            # Es gibt noch keinen Endpunkt (B2) — Seed direkt als Owner.
            async def _seed() -> tuple[UUID, UUID]:
                conn = await asyncpg.connect(get_settings().database_url)
                try:
                    case_id = await _insert_case(conn, ws, agent_id, created_by=owner)
                    run_id = await _insert_run(conn, ws, case_id, reported_by_user_id=owner)
                    return case_id, run_id
                finally:
                    await conn.close()

            case_id, run_id = asyncio.run(_seed())

            exported = client.get("/v1/gdpr/export", headers=make_auth_headers(owner))
            assert exported.status_code == 200, exported.text
            bundle = exported.json()

        workspaces = [
            w for org in bundle["organizations"] for w in org["workspaces"] if w["id"] == str(ws)
        ]
        assert len(workspaces) == 1, workspaces
        target = workspaces[0]

        assert [row["id"] for row in target["test_cases"]] == [str(case_id)]
        case = target["test_cases"][0]
        assert case["input"] == "Ich will kuendigen."
        assert case["expected_behavior"] == "Nennt die Frist."
        assert case["created_by"] == str(owner)
        assert "workspace_id" not in case

        assert [row["id"] for row in target["test_runs"]] == [str(run_id)]
        run = target["test_runs"][0]
        assert run["test_case_id"] == str(case_id)
        assert run["output_excerpt"] == "Antwort ohne Frist."
        assert run["reported_by_user_id"] == str(owner)
        assert "workspace_id" not in run
    finally:
        cleanup_workspaces([owner])


# --- Loeschung (Art. 17) -----------------------------------------------------


def _in_isolated_schema(body: Callable[[asyncpg.Connection], Awaitable[None]]) -> None:
    """Owner-Verbindung (wie der Purge-Job) auf einem frisch migrierten Schema."""
    schema = f"tc_erasure_{secrets.token_hex(6)}"

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


async def _company_workspace(owner: asyncpg.Connection, user: UUID) -> tuple[UUID, UUID, UUID]:
    """Org + Workspace + Agent; liefert (org_id, workspace_id, agent_id)."""
    org_id: UUID = await owner.fetchval(
        "INSERT INTO organization (name, slug, kind) VALUES ('o', $1, 'company') RETURNING id",
        f"o-{secrets.token_hex(4)}",
    )
    ws_id: UUID = await owner.fetchval(
        "INSERT INTO workspace (org_id, name, slug) VALUES ($1, 'w', 'w') RETURNING id",
        org_id,
    )
    agent_id: UUID = await owner.fetchval(
        "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, 'a') RETURNING id",
        ws_id,
        user,
    )
    return org_id, ws_id, agent_id


def test_account_purge_anonymises_test_case_and_run_actors() -> None:
    async def body(owner: asyncpg.Connection) -> None:
        user, other_user = uuid4(), uuid4()
        # Company-Workspace, keine Personal-Org: hier greift KEINE CASCADE,
        # nur die Anonymisierung kann die Person entfernen.
        _, ws_id, agent_id = await _company_workspace(owner, other_user)

        case_user = await _insert_case(owner, ws_id, agent_id, created_by=user, title="u")
        case_other = await _insert_case(owner, ws_id, agent_id, created_by=other_user, title="o")
        # Agent-Pruefall, dessen `created_by` zufaellig die User-UUID traegt:
        # das ist eine Agent-ID, keine Person — der Purge darf sie nicht anfassen.
        case_agent = await _insert_case(
            owner, ws_id, agent_id, created_by=user, created_by_kind="agent", title="a"
        )
        run_user = await _insert_run(owner, ws_id, case_other, reported_by_user_id=user)
        run_other = await _insert_run(owner, ws_id, case_user, reported_by_user_id=other_user)

        anonymized = await PgAccountPurgeRepository(owner).purge_account_data(user)
        # Genau ein menschlicher Pruefall + ein Lauf gehoeren dem User.
        assert anonymized == 2

        creators = {
            row["id"]: row["created_by"]
            for row in await owner.fetch("SELECT id, created_by FROM test_case")
        }
        assert creators == {
            case_user: ANONYMIZED_USER_ID,
            case_other: other_user,
            case_agent: user,
        }
        reporters = {
            row["id"]: row["reported_by_user_id"]
            for row in await owner.fetch("SELECT id, reported_by_user_id FROM test_run")
        }
        assert reporters == {run_user: ANONYMIZED_USER_ID, run_other: other_user}

        # Idempotent: ein zweiter Lauf findet nichts mehr.
        assert await PgAccountPurgeRepository(owner).purge_account_data(user) == 0

    _in_isolated_schema(body)


def test_org_purge_cascades_test_cases_and_runs() -> None:
    async def body(owner: asyncpg.Connection) -> None:
        user = uuid4()
        org_gone, ws_gone, agent_gone = await _company_workspace(owner, user)
        _, ws_kept, agent_kept = await _company_workspace(owner, user)
        for ws_id, agent_id in ((ws_gone, agent_gone), (ws_kept, agent_kept)):
            case_id = await _insert_case(owner, ws_id, agent_id, created_by=user)
            await _insert_run(owner, ws_id, case_id, reported_by_user_id=user)

        await PgAccountPurgeRepository(owner).purge_organization(org_gone)

        for table in ("test_case", "test_run"):
            by_ws = {
                row["workspace_id"]: row["n"]
                for row in await owner.fetch(
                    f"SELECT workspace_id, count(*) AS n FROM {table} GROUP BY workspace_id"  # noqa: S608
                )
            }
            assert by_ws == {ws_kept: 1}, table

    _in_isolated_schema(body)
