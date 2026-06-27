"""DB-freie Regressionstests fuer das Read-Scoping der RENDER-/PREVIEW-Pfade.

Schliesst die Render-Findings des Security-Reviews (HIGH-1 + MEDIUM-1/2/3) ab:
Mehrere Pfade bauten den `RenderContext` OHNE `tool_policy`/`agent_id`. Da
`render_visible_*_ids` bei `tool_policy is None` *unrestricted* (`None`)
zurueckgibt, expandierten eingebettete Inhalts-/Katalog-Pills workspace-weit —
ein an einen `assigned`/`none`-Agenten gebundener Token konnte so nicht
zugewiesene Playbooks/Resources lesen (Bruch des Least-Privilege-Vertrags der
Tool-Policy, KEIN Cross-Tenant-Leak).

Geprueft wird, dass jeder Render-Pfad den Scope des AUFRUFERS (`ctx.tool_policy`
+ `ctx.agent_id`) in den `RenderContext` durchreicht — bzw. fuer fetch_agent,
dass ein agent-gebundener Token nur den EIGENEN Agenten rendern darf.

Der eigentliche Render (`render_template_body` / Resolver) wird gestubbt und
faengt den `RenderContext`; so bleibt der Test DB-frei und prueft genau die
Durchreichung, nicht die (anderweitig getestete) Resolver-Logik.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.services.placeholders._core import RenderContext
from who2be_models import AgentToolPolicy, ReadScope, WorkspaceRole


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _agent_ctx(scope: ReadScope = ReadScope.assigned) -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.editor,
        is_api_token=True,
        agent_id=uuid4(),
        tool_policy=AgentToolPolicy(
            playbook_read=scope,
            resource_read=scope,
            persona_read=True,
            agent_read=ReadScope.all,
        ),
    )


def _human_ctx() -> WorkspaceContext:
    # Ungebundener Token / Mensch: keine Policy → kein Scoping (unrestricted).
    return WorkspaceContext(
        workspace_id=uuid4(),
        user_id=uuid4(),
        role=WorkspaceRole.admin,
        is_api_token=False,
    )


class _FakeAcquire:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_a: object) -> bool:
        return False


class _FakePool:
    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire()


def _pool() -> Any:
    return cast(Any, _FakePool())


# --- PersonaService.render --------------------------------------------------


def _persona_service(captured: list[RenderContext], monkeypatch: pytest.MonkeyPatch) -> Any:
    from who2be_api.services import persona_service as mod

    async def _capture(_body: str, ctx: RenderContext, _conn: object) -> tuple[str, list[str]]:
        captured.append(ctx)
        return "", []

    monkeypatch.setattr(mod, "render_template_body", _capture)
    svc = mod.PersonaService(cast(Any, object()), pool=_pool())
    persona = SimpleNamespace(id=uuid4(), content=SimpleNamespace(content=None, skills=[]))

    async def _get(*_a: object, **_k: object) -> Any:
        return persona

    monkeypatch.setattr(svc, "get", _get)
    return svc


def test_persona_render_propagates_agent_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[RenderContext] = []
    ctx = _agent_ctx()
    _run(_persona_service(captured, monkeypatch).render(ctx, uuid4()))
    assert captured[0].tool_policy is ctx.tool_policy
    assert captured[0].agent_id == ctx.agent_id


def test_persona_render_human_unrestricted(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[RenderContext] = []
    _run(_persona_service(captured, monkeypatch).render(_human_ctx(), uuid4()))
    assert captured[0].tool_policy is None
    assert captured[0].agent_id is None


# --- PlaybookService.render -------------------------------------------------


def _playbook_service(captured: list[RenderContext], monkeypatch: pytest.MonkeyPatch) -> Any:
    from who2be_api.services import playbook_service as mod

    async def _capture(_body: str, ctx: RenderContext, _conn: object) -> tuple[str, list[str]]:
        captured.append(ctx)
        return "", []

    monkeypatch.setattr(mod, "render_template_body", _capture)
    svc = mod.PlaybookService(
        cast(Any, object()), _pool(), cast(Any, object()), cast(Any, object())
    )
    playbook = SimpleNamespace(content=SimpleNamespace(body="[]"))

    async def _get(*_a: object, **_k: object) -> Any:
        return playbook

    monkeypatch.setattr(svc, "get", _get)
    return svc


def test_playbook_render_propagates_agent_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[RenderContext] = []
    ctx = _agent_ctx()
    _run(_playbook_service(captured, monkeypatch).render(ctx, uuid4()))
    assert captured[0].tool_policy is ctx.tool_policy
    assert captured[0].agent_id == ctx.agent_id


def test_playbook_render_human_unrestricted(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[RenderContext] = []
    _run(_playbook_service(captured, monkeypatch).render(_human_ctx(), uuid4()))
    assert captured[0].tool_policy is None
    assert captured[0].agent_id is None


# --- PlaceholderPreviewService.preview --------------------------------------


def _preview_service(captured: list[RenderContext], monkeypatch: pytest.MonkeyPatch) -> Any:
    from who2be_api.services import placeholder_preview_service as mod
    from who2be_api.services.placeholders.registry import REGISTRY

    class _FakeResolver:
        async def resolve(self, _tid: str, ctx: RenderContext, _conn: object) -> Any:
            captured.append(ctx)
            return SimpleNamespace(text="x", unresolved_key=None)

    monkeypatch.setitem(REGISTRY, "playbook", cast(Any, _FakeResolver()))
    return mod.PlaceholderPreviewService(_pool())


def test_preview_propagates_agent_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[RenderContext] = []
    ctx = _agent_ctx()
    _run(_preview_service(captured, monkeypatch).preview(ctx, "playbook", str(uuid4()), None))
    assert captured[0].tool_policy is ctx.tool_policy
    assert captured[0].agent_id == ctx.agent_id


def test_preview_human_unrestricted(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[RenderContext] = []
    _run(_preview_service(captured, monkeypatch).preview(_human_ctx(), "playbook", "", None))
    assert captured[0].tool_policy is None
    assert captured[0].agent_id is None


# --- fetch_agent_rendered: agent-gebundener Token nur auf eigenen Agenten ----


class _FakeFetchRendered:
    sentinel = object()

    async def fetch_rendered(self, _ws: UUID, _agent_id: UUID) -> object:
        return self.sentinel


def test_fetch_agent_rendered_foreign_agent_404() -> None:
    from who2be_api.routers.agents import fetch_agent_rendered

    ctx = _agent_ctx()  # gebunden an ctx.agent_id
    with pytest.raises(HTTPException) as exc:
        _run(fetch_agent_rendered(uuid4(), ctx, cast(Any, _FakeFetchRendered())))
    assert exc.value.status_code == 404


def test_fetch_agent_rendered_own_agent_ok() -> None:
    from who2be_api.routers.agents import fetch_agent_rendered

    ctx = _agent_ctx()
    assert ctx.agent_id is not None
    result = _run(fetch_agent_rendered(ctx.agent_id, ctx, cast(Any, _FakeFetchRendered())))
    assert result is _FakeFetchRendered.sentinel


def test_fetch_agent_rendered_human_any_agent_ok() -> None:
    from who2be_api.routers.agents import fetch_agent_rendered

    result = _run(fetch_agent_rendered(uuid4(), _human_ctx(), cast(Any, _FakeFetchRendered())))
    assert result is _FakeFetchRendered.sentinel
