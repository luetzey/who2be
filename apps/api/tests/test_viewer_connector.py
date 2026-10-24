"""Kollege mit Rolle `viewer` nutzt einen Agenten per OAuth-Connector (Karte t_b36bf77f).

Der ganze Weg laeuft echt: der Kollege ist `viewer` im Workspace, verbindet
per DCR → authorize (Hard-Lock auf den Agenten) → consent (seine Web-Session)
→ token einen Connector und ruft dann die MCP-Werkzeuge ueber den echten
`ApiClient` gegen dieselbe App auf (`httpx.ASGITransport`, Muster
`test_memory_mcp_c4b.py`). Die Policy-Middleware loest `whoami` mit genau
diesem Token auf.

Agent ist der mitgelieferte Builder: er hat eine schreibfaehige Policy und
`memory_mode=suggest`. Gerade deshalb zeigt der Test, dass die Rolle des
Kollegen das Schreiben verhindert, nicht eine knappe Agent-Policy.

Festgehaltenes Verhalten:

- Der Connector-Token traegt die Rolle `viewer` (keine Anhebung).
- Lesen geht: `whoami`, `get_persona`, `fetch_playbook`, `search`.
- Schreibwerkzeuge sind unsichtbar oder verboten: jeder Aufruf endet mit
  `insufficient_role`, und es entsteht nichts (Agent unveraendert, kein
  neues Playbook, keine neue Persona).
- Gedaechtnis (Owner-Entscheidung A, 2026-10-24; ADR-0023 Nachtrag 2026-10-24,
  ADR-0053 6.4.2): `search_memory`/`list_memories` liefern auch das
  Agentengedaechtnis; `save_memory` und `propose_memory_change` legen einen
  Vorschlag `pending` an, der erst nach Freigabe durch einen Menschen wirkt.
  Ueber REST bleibt das Agentengedaechtnis fuer viewer unsichtbar (bewusst).

Rot-Probe: in `playbook_service.create` `require_role(ctx, WorkspaceRole.editor)`
auf `WorkspaceRole.viewer` setzen — `create_playbook` geht dann durch und der
Test wird rot.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import asyncpg
import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from who2be_api.core import security
from who2be_api.core.config import Settings, get_settings
from who2be_api.main import app
from who2be_api.services import oauth_service
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_mcp import policy_filter, server
from who2be_mcp.client import ApiClient
from who2be_mcp.config import Settings as McpSettings
from who2be_mcp.server import mcp

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("migrated_db")]

_SECRET = "integration-test-jwt-secret-padding-0123456789"
_RESOURCE = "http://testserver/mcp"
_REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def _settings() -> Settings:
    return Settings(
        jwt_secret=_SECRET,
        mcp_resource_url=_RESOURCE,
        oauth_consent_url="http://localhost:5173/oauth/consent",
        oauth_issuer_url="http://testserver",
    )


def _session(user_id: UUID) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "aud": "authenticated",
            "role": "authenticated",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        _SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


async def _fetch(sql: str, *args: object) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(get_settings().database_url)
    try:
        return list(await conn.fetch(sql, *args))
    finally:
        await conn.close()


def _db(sql: str, *args: object) -> list[asyncpg.Record]:
    return asyncio.run(_fetch(sql, *args))


def _connect_as(client: TestClient, user_id: UUID, agent_id: UUID) -> str:
    """Voller Connector-Flow als `user_id`, Hard-Lock auf `agent_id`; liefert den Access-Token."""
    resource = f"{_RESOURCE}/a/{agent_id}"
    reg = client.post(
        "/oauth/register", json={"redirect_uris": [_REDIRECT], "client_name": "Claude"}
    )
    assert reg.status_code == 201, reg.text
    client_id = reg.json()["client_id"]
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    authorize = client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": _REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,
            "state": "s",
        },
        follow_redirects=False,
    )
    assert authorize.status_code == 302, authorize.text
    blob = parse_qs(urlparse(authorize.headers["location"]).query)["request"][0]
    consent = client.post(
        "/oauth/consent", json={"request": blob, "approve": True}, headers=_session(user_id)
    )
    assert consent.status_code == 200, consent.text
    code = parse_qs(urlparse(consent.json()["redirect"]).query)["code"][0]
    token = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
            "resource": resource,
        },
    )
    assert token.status_code == 200, token.text
    access: str = token.json()["access_token"]
    return access


def test_viewer_nutzt_agent_per_connector_aendert_aber_nichts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(security, "get_settings", _settings)
    monkeypatch.setattr(oauth_service, "get_settings", _settings)

    owner = fresh_user_id()
    colleague = fresh_user_id()
    ws = setup_workspace(owner)
    _db(
        "INSERT INTO workspace_member (workspace_id, user_id, role) VALUES ($1, $2, 'viewer')",
        ws,
        colleague,
    )
    builder = _db(
        "SELECT id, name, persona_id FROM agent WHERE workspace_id = $1 AND is_managed", ws
    )[0]
    agent_id: UUID = builder["id"]
    persona_id: UUID = builder["persona_id"]
    playbook_id: UUID = _db(
        "SELECT playbook_id FROM persona_playbook WHERE persona_id = $1 LIMIT 1", persona_id
    )[0]["playbook_id"]
    memory_id: UUID = _db(
        "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, fact, "
        " category, importance, kind, scope, origin, source, confirmed_at) "
        "VALUES ($1, $2, $2, 'active', 'Team trinkt Assam-Tee.', 'preference', 6, "
        " 'user_fact', 'agent', 'user_stated', 'agent', now()) RETURNING id",
        ws,
        agent_id,
    )[0]["id"]
    counts_sql = (
        "SELECT (SELECT count(*) FROM playbook WHERE workspace_id = $1) AS playbooks, "
        "       (SELECT count(*) FROM persona WHERE workspace_id = $1) AS personas"
    )

    try:
        with TestClient(app) as client:
            access = _connect_as(client, colleague, agent_id)
        pinned = _db(
            "SELECT role, agent_id FROM api_token WHERE token_hash = $1",
            security.hash_token(access),
        )[0]
        assert (pinned["role"], pinned["agent_id"]) == ("viewer", agent_id)
        before = dict(_db(counts_sql, ws)[0])

        mcp_settings = McpSettings(
            api_base_url="http://testserver", api_token=access, transport="stdio"
        )
        monkeypatch.setattr(policy_filter, "get_settings", lambda: mcp_settings)
        results: dict[str, tuple[bool, str]] = {}
        visible: set[str] = set()

        async def _go() -> None:
            async with app.router.lifespan_context(app):
                transport = httpx.ASGITransport(app=app)

                async def _build() -> ApiClient:
                    return ApiClient("http://testserver", access, ws, transport=transport)

                monkeypatch.setattr(server, "build_client", _build)
                calls: dict[str, dict[str, Any]] = {
                    # Lesen
                    "whoami": {},
                    "get_persona": {"identifier": str(persona_id)},
                    "fetch_playbook": {"playbook_id": str(playbook_id)},
                    "search": {"query": "Agent"},
                    # Schreiben
                    "update_agent": {"agent_id": str(agent_id), "data": {"name": "Gekapert"}},
                    "create_playbook": {
                        "data": {"name": "Vom Kollegen", "content": {"body": "1. Schritt"}}
                    },
                    "create_persona": {
                        "data": {"name": "Vom Kollegen", "content": {"description": "x"}}
                    },
                    "submit_feedback": {
                        "data": {
                            "entity_type": "playbook",
                            "entity_id": str(playbook_id),
                            "signal": "helpful",
                        }
                    },
                    # Gedaechtnis
                    "search_memory": {"query": "Assam"},
                    "list_memories": {},
                    "save_memory": {
                        "fact": "Kollege bevorzugt kurze Antworten.",
                        "origin": "user_stated",
                        "importance": 6,
                    },
                    "propose_memory_change": {
                        "memory_id": str(memory_id),
                        "action": "delete",
                        "reason": "Stimmt nicht mehr.",
                    },
                }
                async with Client(mcp) as mcp_client:
                    visible.update(t.name for t in await mcp_client.list_tools())
                    for name, args in calls.items():
                        if name not in visible:
                            continue
                        res = await mcp_client.call_tool(name, args, raise_on_error=False)
                        text = " ".join(getattr(block, "text", "") for block in res.content)
                        results[name] = (res.is_error, text)

        asyncio.run(_go())

        # Lesen: sichtbar und erfolgreich.
        for name in ("whoami", "get_persona", "fetch_playbook", "search"):
            assert name in results, f"{name} fehlt in tools/list"
            assert results[name][0] is False, f"{name}: {results[name][1][:300]}"
        assert '"role":"viewer"' in results["whoami"][1]
        assert "Persona:" in results["get_persona"][1]
        assert "Playbook:" in results["fetch_playbook"][1]

        # Schreiben: unsichtbar ODER verboten — nie erfolgreich.
        for name in ("update_agent", "create_playbook", "create_persona", "submit_feedback"):
            if name not in results:
                continue  # unsichtbar ist ebenfalls in Ordnung
            is_error, text = results[name]
            assert is_error, f"viewer konnte {name} ausfuehren: {text[:300]}"
            assert "insufficient_role" in text, f"{name}: {text[:300]}"
        assert _db("SELECT name FROM agent WHERE id = $1", agent_id)[0]["name"] == builder["name"]
        assert dict(_db(counts_sql, ws)[0]) == before

        # Gedaechtnis (Owner-Entscheidung A): lesen inkl. Agentengedaechtnis, Vorschlaege `pending`.
        for name in ("search_memory", "list_memories"):
            assert results[name][0] is False, results[name][1][:300]
            assert str(memory_id) in results[name][1]
        assert results["save_memory"][0] is False, results["save_memory"][1][:300]
        assert results["propose_memory_change"][0] is False, results["propose_memory_change"][1]
        saved = _db(
            "SELECT status FROM agent_memory WHERE workspace_id = $1 AND fact = $2",
            ws,
            "Kollege bevorzugt kurze Antworten.",
        )
        assert [r["status"] for r in saved] == ["pending"]
        proposals = _db("SELECT status FROM agent_memory_proposal WHERE memory_id = $1", memory_id)
        assert [r["status"] for r in proposals] == ["pending"]
        # Der Vorschlag aendert den Eintrag nicht.
        assert (
            _db("SELECT status FROM agent_memory WHERE id = $1", memory_id)[0]["status"] == "active"
        )
    finally:
        cleanup_workspaces([owner, colleague])
