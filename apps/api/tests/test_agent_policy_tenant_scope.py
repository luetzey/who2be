"""DB-freier Regressionstest fuer den Tenant-Scope beim Agent-Policy-Read.

Sicherheits-Befund (HIGH): `get_current_workspace` lud die Tool-Policy eines
agent-gebundenen Tokens (`SELECT tool_policy FROM agent ...`) BEVOR es den
`tenant_scope` betrat. Die Tabelle `agent` traegt strikte RLS (Migration 0037);
unter der Cloud-Rolle `who2be_app` (NOBYPASSRLS) liefert der Read OHNE gesetzten
`app.current_tenant` 0 Zeilen (fail-closed) → die Policy waere faelschlicher-
weise `None` (= „keine Pro-Agent-Restriktion") und die gesamte Least-Privilege-
Schicht (Capabilities, Read-Scoping, Tag-/Rate-Limits) fiele in der Cloud aus.

Dieser Test reproduziert die URSACHE DB-frei: ein Fake-Pool zeichnet den
`current_tenant_context()` zum Zeitpunkt des `agent`-Reads auf. Vor dem Fix ist
er `None` (Scope nicht betreten); nach dem Fix ist der Mandant gesetzt. Der
volle RLS-Beweis (0-Zeilen unter `who2be_app`) laeuft in `test_rls_isolation.py`
und ist ohne erreichbare DB skip-guarded.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any, cast
from uuid import UUID, uuid4

from who2be_api.core import security as sec
from who2be_api.core.security import WorkspaceContext
from who2be_api.core.tenancy import TenantContext, current_tenant_context
from who2be_models import WorkspaceRole

_UNSET = object()


class _RecordingPool:
    """Fake-Pool, der den Tenant-Kontext beim `agent`-Policy-Read festhaelt."""

    def __init__(self, policy_json: dict[str, Any]) -> None:
        self._policy_json = policy_json
        self.tenant_at_agent_read: object = _UNSET

    async def fetchval(self, query: str, *_args: object) -> object:
        if "FROM agent" in query:
            self.tenant_at_agent_read = current_tenant_context()
            return self._policy_json
        return None

    async def fetchrow(self, _query: str, *_args: object) -> object:
        # Org-Lookup (control-plane, ohne RLS) — hier nicht relevant.
        return None


def _run_dependency(pool: _RecordingPool, ws: UUID, agent_id: UUID) -> Any:
    principal = sec.CurrentPrincipal(
        user_id=uuid4(),
        token_workspace_id=ws,
        token_role=WorkspaceRole.editor,
        token_agent_id=agent_id,
    )

    async def _run() -> Any:
        gen = cast(
            "AsyncGenerator[WorkspaceContext, None]",
            sec.get_current_workspace(ws, principal),
        )
        try:
            return await gen.__anext__()
        finally:
            await gen.aclose()

    return asyncio.run(_run())


def test_agent_policy_read_runs_inside_tenant_scope(monkeypatch: Any) -> None:
    ws = uuid4()
    agent_id = uuid4()
    pool = _RecordingPool(
        {
            "playbook_read": "assigned",
            "resource_read": "assigned",
            "persona_read": True,
            "agent_read": "all",
        }
    )
    monkeypatch.setattr(sec, "get_pool", lambda: cast(Any, pool))

    ctx = _run_dependency(pool, ws, agent_id)

    # Kern der Regression: der `agent`-Read fand mit gesetztem Mandanten statt —
    # sonst filtert RLS ihn in der Cloud auf 0 Zeilen und die Policy waere None.
    assert pool.tenant_at_agent_read is not _UNSET, "agent-Read wurde nie ausgefuehrt"
    assert isinstance(pool.tenant_at_agent_read, TenantContext), (
        "Agent-Policy-Read lief OHNE Tenant-Scope — RLS wuerde ihn in der Cloud "
        "fail-closed auf 0 Zeilen filtern (Policy faelschlich None)."
    )
    assert pool.tenant_at_agent_read.workspace_id == ws
    # Folge: die Policy wird korrekt geladen (nicht None → Restriktionen greifen).
    assert ctx.tool_policy is not None
