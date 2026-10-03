"""MCP-Gedaechtniswerkzeuge gegen die echte API (ADR-0053 C4b).

Die MCP-Werkzeuge `save_memory`, `propose_memory_change`, `search_memory`
und `list_memories` laufen ueber ihren echten `ApiClient` per
`httpx.ASGITransport` gegen DIESELBE App (Muster und Begruendung des
Ein-Loop-Aufbaus: `test_rest_mcp_parity.py`). Damit ist belegt, was das
Werkzeug dem Agenten zusagt — nicht nur, was es an die API schickt.

Zusicherungen (Rot-Probe = genannte Stelle geaendert, Test wird rot):

- Ohne `origin` antwortet `save_memory` mit `memory_origin_required`.
  (Rot-Probe: in `server.save_memory` wieder `MemoryOrigin.inferred` als
  Ersatzwert einsetzen.)
- Abruf-Treffer tragen die Rahmung je Treffer, `unbestaetigt` genau bei
  `confirmed=false`; `lesson` erscheint nie.
  (Rot-Probe: `frame_hits` setzt immer `MEMORY_FRAMING`.)
- `propose_memory_change` entsteht immer `pending`, auch wenn jede
  schaltbare Zelle der Freigabematrix an ist, und aendert den Eintrag nicht.
- Fremde (anderer Agent) und nicht abrufbare (`lesson`) Eintraege werden mit
  `memory_not_found` abgewiesen, ohne dass ein Vorschlag entsteht.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
import httpx
import pytest
from fastmcp.exceptions import ToolError

from who2be_api.core.config import get_settings
from who2be_api.main import app
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.tools.learning import (
    MEMORY_FRAMING,
    MEMORY_FRAMING_UNCONFIRMED,
    propose_memory_change,
)
from who2be_models.memory import MemoryProposalAction

AuthFactory = Callable[[UUID], dict[str, str]]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("patched_jwt_secret", "migrated_db"),
]


async def _fetchval(sql: str, *args: object) -> Any:
    # `api_helpers.db_fetchval` nutzt `asyncio.run` — hier laeuft schon ein Loop.
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        return await conn.fetchval(sql, *args)
    finally:
        await conn.close()


@dataclass
class Env:
    rest: httpx.AsyncClient
    prefix: str
    admin_h: dict[str, str]
    ws: UUID
    owner: UUID
    agent: UUID
    other: UUID

    async def memory(
        self,
        fact: str,
        *,
        agent: UUID | None = None,
        kind: str = "user_fact",
        status: str = "active",
        confirmed: bool = True,
    ) -> UUID:
        """Eintrag direkt in der DB (Fixture, an der Service-Logik vorbei)."""
        owner = agent or self.agent
        memory_id: UUID = await _fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, source, "
            " confirmed_at, confirmed_by, expires_at) "
            "VALUES ($1, $2, $2, $3, $4, 'preference', 6, $5, 'agent', 'user_stated', "
            "        'agent', CASE WHEN $6 THEN now() END, CASE WHEN $6 THEN $7::uuid END, "
            "        CASE WHEN NOT $6 AND $3 = 'active' THEN now() + interval '30 days' END) "
            "RETURNING id",
            self.ws,
            owner,
            status,
            fact,
            kind,
            confirmed,
            self.owner,
        )
        return memory_id


Scenario = Callable[[Env], Awaitable[None]]


def _run(make_auth: AuthFactory, scenario: Scenario, memory_mode: str) -> None:
    """Workspace, zwei Agenten (Token nur am ersten), MCP-Client auf ASGI, Szenario."""
    owner = fresh_user_id()
    ws = setup_workspace(owner)
    admin_h = make_auth(owner)

    async def _go() -> None:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as rest:
                prefix = f"/v1/workspaces/{ws}"
                agents: list[UUID] = []
                for name in ("C4b-Agent", "C4b-Fremd"):
                    created = await rest.post(
                        f"{prefix}/agents",
                        json={"name": name, "tool_policy": {"memory_mode": memory_mode}},
                        headers=admin_h,
                    )
                    assert created.status_code == 201, created.text
                    agents.append(UUID(created.json()["id"]))
                tok = await rest.post(
                    f"{prefix}/tokens",
                    json={"name": "C4b", "agent_id": str(agents[0])},
                    headers=admin_h,
                )
                assert tok.status_code == 201, tok.text
                token: str = tok.json()["token"]

                async def _build() -> ApiClient:
                    return ApiClient("http://testserver", token, ws, transport=transport)

                original = server.build_client
                server.build_client = _build
                try:
                    await scenario(Env(rest, prefix, admin_h, ws, owner, agents[0], agents[1]))
                finally:
                    server.build_client = original

    try:
        asyncio.run(_go())
    finally:
        cleanup_workspaces([owner])


def test_save_memory_ohne_origin_meldet_memory_origin_required(
    make_auth_headers: AuthFactory,
) -> None:
    async def scenario(env: Env) -> None:
        with pytest.raises(ToolError, match="memory_origin_required"):
            await server.save_memory("Nutzer trinkt gern Earl Grey.", importance=6)
        saved = await server.save_memory(
            "Nutzer trinkt gern Earl Grey.", origin="user_stated", importance=6
        )
        assert saved.origin == "user_stated"
        assert saved.status == "pending"
        assert saved.auto_activated is False

    _run(make_auth_headers, scenario, "suggest")


def test_abruf_rahmt_je_treffer_und_zeigt_nie_lesson(make_auth_headers: AuthFactory) -> None:
    async def scenario(env: Env) -> None:
        sure = await env.memory("Teesorte bestaetigt: Assam")
        unsure = await env.memory("Teesorte unbestaetigt: Darjeeling", confirmed=False)
        lesson = await env.memory(
            "Teesorte Lernvorschlag: Rooibos", kind="lesson", status="pending", confirmed=False
        )
        for hits in (await server.search_memory("Teesorte", k=20), await server.list_memories(50)):
            framing = {str(h.id): h.framing for h in hits}
            assert framing[str(sure)] == MEMORY_FRAMING
            assert framing[str(unsure)] == MEMORY_FRAMING_UNCONFIRMED
            assert str(lesson) not in framing
            assert all(h.kind != "lesson" for h in hits)

    _run(make_auth_headers, scenario, "read_only")


def test_vorschlag_bleibt_pending_auch_unter_vollautomatik(make_auth_headers: AuthFactory) -> None:
    async def scenario(env: Env) -> None:
        # Jede schaltbare Zelle an: ein Vorschlag darf trotzdem nie
        # automatisch wirken (ADR-0053 3.1.4, Matrix-Zeile „proposal“).
        policy = await env.rest.get(f"{env.prefix}/memory-auto-policy", headers=env.admin_h)
        assert policy.status_code == 200, policy.text
        cells = policy.json()["switchable_cells"]
        put = await env.rest.put(
            f"{env.prefix}/memory-auto-policy",
            json={"enabled_cells": cells},
            headers=env.admin_h,
        )
        assert put.status_code == 200, put.text

        memory = await env.memory("Nutzer arbeitet mit npm.")
        proposal = await propose_memory_change(
            str(memory),
            MemoryProposalAction.change,
            "Nutzer hat auf pnpm gewechselt.",
            "Nutzer arbeitet mit pnpm.",
        )
        assert proposal.status == "pending"
        assert proposal.memory_id == memory
        assert proposal.agent_id == env.agent
        fact = await _fetchval("SELECT fact FROM agent_memory WHERE id = $1", memory)
        assert fact == "Nutzer arbeitet mit npm."

    _run(make_auth_headers, scenario, "auto")


@pytest.mark.parametrize("target", ["fremder_agent", "lesson"])
def test_vorschlag_zu_fremdem_oder_nicht_abrufbarem_eintrag_abgewiesen(
    make_auth_headers: AuthFactory, target: str
) -> None:
    async def scenario(env: Env) -> None:
        if target == "fremder_agent":
            memory = await env.memory("Fremdagent: Nutzer mag Jazz.", agent=env.other)
        else:
            memory = await env.memory(
                "Lernvorschlag: kuerzer antworten.",
                kind="lesson",
                status="pending",
                confirmed=False,
            )
        with pytest.raises(ToolError, match="memory_not_found"):
            await propose_memory_change(str(memory), MemoryProposalAction.delete, "veraltet")
        count = await _fetchval(
            "SELECT count(*) FROM agent_memory_proposal WHERE memory_id = $1", memory
        )
        assert count == 0

    _run(make_auth_headers, scenario, "suggest")
