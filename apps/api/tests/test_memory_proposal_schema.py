"""Schema-Tests fuer Aenderungs-/Loeschvorschlaege (ADR-0053 3.1.4, 6.4.1, Migration 0096, C3a).

Belegt auf der Laufzeitrolle `who2be_app` (NOBYPASSRLS) im isolierten Schema
der 0091-Tests (`test_memory_v2_schema._with_env`):

- **Unveraenderlich:** die App-Rolle darf am Vorschlag nur `status`,
  `decided_by`, `decided_at` schreiben, nie Text, Begruendung, Ziel oder
  Agent — und nichts loeschen.
- **Invarianten (DB-CHECK):** `new_fact` genau bei `change`; Begruendung
  1..200 Zeichen; Entscheidungs-Spalten genau dann, wenn entschieden.
- **Bindung:** Eintrag und Agent desselben Workspace (Composite-FK); faellt
  der Eintrag, fallen seine Vorschlaege mit — auch bei Loeschung durch die
  App-Rolle.
- **RLS:** ein Workspace sieht die Vorschlaege des anderen nicht.
- **Historie:** der Event-CHECK kennt `auto_revoked` (6.4.1).
- **Repository auf der App-Rolle:** Vorschlag anlegen und Loeschvorschlag
  annehmen laufen unter RLS durch.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
import pytest
from test_memory_v2_schema import (  # type: ignore[import-not-found]
    _Env,
    _insert_event,
    _insert_memory,
    _with_env,
    _with_repo,
)

from who2be_api.repositories.memory_repository import MemoryOwner, PgMemoryRepository
from who2be_models.memory import (
    MemoryProposalAction,
    MemoryProposalCreate,
    MemoryProposalStatus,
)

pytestmark = pytest.mark.integration


async def _insert_proposal(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    memory_id: UUID,
    agent_id: UUID,
    *,
    action: str = "change",
    new_fact: str | None = "Neuer Fakt",
    reason: str = "Korrigiert",
) -> UUID:
    proposal_id: UUID = await conn.fetchval(
        "INSERT INTO agent_memory_proposal "
        "(workspace_id, memory_id, agent_id, action, new_fact, reason) "
        "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
        workspace_id,
        memory_id,
        agent_id,
        action,
        new_fact,
        reason,
    )
    return proposal_id


def test_proposal_is_immutable_except_decision() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        memory = await _insert_memory(env.app, s.ws_a, s.agent_a, status="active")
        proposal = await _insert_proposal(env.app, s.ws_a, memory, s.agent_a)

        for column, value in (
            ("new_fact", "'umgeschrieben'"),
            ("reason", "'andere Begruendung'"),
            ("action", "'delete'"),
            ("agent_id", f"'{s.agent_a2}'::uuid"),
            ("memory_id", "memory_id"),
            ("created_at", "now()"),
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await env.app.execute(
                    f"UPDATE agent_memory_proposal SET {column} = {value} WHERE id = $1",  # noqa: S608
                    proposal,
                )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await env.app.execute("DELETE FROM agent_memory_proposal WHERE id = $1", proposal)

        # Die Entscheidung selbst ist schreibbar.
        await env.app.execute(
            "UPDATE agent_memory_proposal SET status = 'rejected', decided_by = $2, "
            "decided_at = now() WHERE id = $1",
            proposal,
            s.user,
        )
        assert (
            await env.app.fetchval(
                "SELECT status FROM agent_memory_proposal WHERE id = $1", proposal
            )
            == "rejected"
        )

    _with_env(body)


def test_proposal_invariants() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        memory = await _insert_memory(env.app, s.ws_a, s.agent_a, status="active")
        bad: list[dict[str, str | None]] = [
            {"action": "change", "new_fact": None},  # change ohne Text
            {"action": "delete", "new_fact": "x"},  # delete mit Text
            {"action": "merge", "new_fact": None},  # geschlossene Menge
            {"action": "delete", "new_fact": None, "reason": ""},
            {"action": "delete", "new_fact": None, "reason": "r" * 201},
            {"action": "change", "new_fact": "f" * 301},
        ]
        for case in bad:
            with pytest.raises(asyncpg.CheckViolationError):
                await _insert_proposal(
                    env.app,
                    s.ws_a,
                    memory,
                    s.agent_a,
                    action=str(case["action"]),
                    new_fact=case["new_fact"],
                    reason=str(case.get("reason", "Grund")),
                )
        ok = await _insert_proposal(
            env.app, s.ws_a, memory, s.agent_a, action="delete", new_fact=None, reason="r" * 200
        )
        # Entschieden ohne Entscheider / offen mit Zeitpunkt: beides verboten.
        for sql in (
            "UPDATE agent_memory_proposal SET status = 'accepted', decided_at = now() "
            "WHERE id = $1",
            "UPDATE agent_memory_proposal SET decided_at = now() WHERE id = $1",
        ):
            with pytest.raises(asyncpg.CheckViolationError):
                await env.app.execute(sql, ok)

    _with_env(body)


def test_proposal_bound_to_same_workspace_and_cascades() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        memory = await _insert_memory(env.app, s.ws_a, s.agent_a, status="active")
        # Agent aus einem anderen Workspace: Composite-FK greift.
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await _insert_proposal(env.app, s.ws_a, memory, s.agent_b)
        proposal = await _insert_proposal(env.app, s.ws_a, memory, s.agent_a)
        # Die App-Rolle loescht den Eintrag — der Vorschlag faellt mit.
        await env.app.execute("DELETE FROM agent_memory WHERE id = $1", memory)
        assert (
            await env.owner.fetchval(
                "SELECT count(*) FROM agent_memory_proposal WHERE id = $1", proposal
            )
            == 0
        )

    _with_env(body)


def test_proposal_rls_isolates_workspaces() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        memory = await _insert_memory(env.app, s.ws_a, s.agent_a, status="active")
        await _insert_proposal(env.app, s.ws_a, memory, s.agent_a)
        await env.as_tenant(s.ws_b)
        assert await env.app.fetchval("SELECT count(*) FROM agent_memory_proposal") == 0
        # Schreiben in einen fremden Workspace scheitert an WITH CHECK.
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await _insert_proposal(env.app, s.ws_a, memory, s.agent_a)

    _with_env(body)


def test_event_check_knows_auto_revoked() -> None:
    async def body(env: _Env) -> None:
        s = env.seed
        await env.as_tenant(s.ws_a)
        memory = await _insert_memory(env.app, s.ws_a, s.agent_a, status="active")
        event = await _insert_event(
            env.app, s.ws_a, memory, event="auto_revoked", actor_kind="human"
        )
        assert (
            await env.app.fetchval("SELECT event FROM agent_memory_event WHERE id = $1", event)
            == "auto_revoked"
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await _insert_event(env.app, s.ws_a, memory, event="auto_revived")

    _with_env(body)


def test_repository_proposal_flow_under_app_role() -> None:
    async def body(repo: PgMemoryRepository, env: _Env) -> None:
        s = env.seed
        owner = MemoryOwner(agent_id=s.agent_a)
        memory = await _insert_memory(env.owner, s.ws_a, s.agent_a, status="active")
        target = await repo.get_owned(s.ws_a, owner, memory)
        assert target is not None
        proposal = await repo.insert_proposal(
            s.ws_a,
            s.agent_a,
            target,
            MemoryProposalCreate(
                memory_id=memory, action=MemoryProposalAction.delete, reason="Veraltet"
            ),
        )
        assert proposal.status == MemoryProposalStatus.pending
        decided = await repo.decide_proposal(
            s.ws_a, owner, proposal.id, accept=True, actor_id=s.user, note=None
        )
        assert decided is not None
        assert decided.status == MemoryProposalStatus.accepted
        assert (
            await env.owner.fetchval("SELECT count(*) FROM agent_memory WHERE id = $1", memory) == 0
        )

    _with_repo(body)
