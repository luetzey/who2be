"""DB-freie Unit-Tests fuer das `agent_read`-Scoping auf den Agent-Read-Pfaden.

`AgentService.list_all`/`get` scopen ueber `agent_read_restrict(ctx)`:
- ungebundener Token / Mensch (`tool_policy is None`) -> kein Scoping (alle),
- Scope `all` -> ganzer Workspace,
- Scope `assigned` -> NUR der eigene Agent (fremde ID => 404),
- Scope `none` -> Tool aus (403).

Zusaetzlich gesichert: die Liste filtert NICHT auf `enabled` — ein frisch
angelegter (=`disabled`) Agent muss fuer einen Verwalter (`all`) sichtbar
bleiben (sonst kaeme das urspruengliche „404 nach dem Anlegen" zurueck).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.agent_repository import AgentListMeta
from who2be_api.services.agent_service import AgentService
from who2be_models import AgentRead, AgentStatus, AgentToolPolicy, ReadScope, WorkspaceRole

_WS = uuid4()
_OWNER = uuid4()


def _agent(agent_id: UUID, name: str, status: AgentStatus) -> AgentRead:
    now = datetime(2026, 6, 22, tzinfo=UTC)
    return AgentRead(
        id=agent_id,
        workspace_id=_WS,
        owner_id=_OWNER,
        name=name,
        description="",
        persona_id=None,
        system_prompt_template_id=None,
        status=status,
        created_at=now,
        updated_at=now,
    )


class _FakeAgentRepo:
    """Minimaler Fake — nur die von list/get genutzten Methoden."""

    def __init__(self, agents: list[AgentRead]) -> None:
        self._agents = agents
        # Card-Pill-Meta pro Agent-ID (vom Test gesetzt); ohne Eintrag bleibt das
        # Read auf den Feld-Defaults (None/0).
        self.meta: dict[UUID, AgentListMeta] = {}
        self.favorites: set[tuple[UUID, UUID]] = set()
        self.last_meta_user_id: UUID | None = _OWNER

    async def list_by_workspace(
        self, workspace_id: UUID, limit: int, cursor: object
    ) -> list[AgentRead]:
        return self._agents[:limit]

    async def fetch(self, workspace_id: UUID, agent_id: UUID) -> AgentRead | None:
        return next((a for a in self._agents if a.id == agent_id), None)

    async def list_meta(
        self, workspace_id: UUID, agent_ids: list[UUID], user_id: UUID | None
    ) -> dict[UUID, AgentListMeta]:
        self.last_meta_user_id = user_id
        return {aid: self.meta[aid] for aid in agent_ids if aid in self.meta}

    async def add_favorite(self, workspace_id: UUID, agent_id: UUID, user_id: UUID) -> None:
        self.favorites.add((agent_id, user_id))

    async def remove_favorite(self, workspace_id: UUID, agent_id: UUID, user_id: UUID) -> None:
        self.favorites.discard((agent_id, user_id))


# Zwei Agenten im Workspace: der "eigene" (= ctx.agent_id) ist disabled (frisch
# angelegt), ein fremder ist enabled.
_OWN_ID = uuid4()
_OTHER_ID = uuid4()


def _service() -> AgentService:
    own = _agent(_OWN_ID, "Eigener (frisch)", AgentStatus.disabled)
    other = _agent(_OTHER_ID, "Fremder", AgentStatus.enabled)
    return AgentService(_FakeAgentRepo([own, other]))  # type: ignore[arg-type]


def _ctx(agent_read: ReadScope | None) -> WorkspaceContext:
    """`None` = Mensch/JWT (keine Policy). Sonst agent-gebunden mit gegebenem Scope."""
    bound = agent_read is not None
    return WorkspaceContext(
        workspace_id=_WS,
        user_id=_OWNER,
        role=WorkspaceRole.editor,
        is_api_token=bound,
        agent_id=_OWN_ID if bound else None,
        tool_policy=(AgentToolPolicy(agent_read=agent_read) if agent_read is not None else None),
    )


def test_human_token_sees_all_agents() -> None:
    items, _cursor = asyncio.run(_service().list_all(_ctx(None), limit=50, cursor=None))
    assert {a.id for a in items} == {_OWN_ID, _OTHER_ID}


def test_scope_all_sees_all_agents() -> None:
    ctx = _ctx(ReadScope.all)
    items, _cursor = asyncio.run(_service().list_all(ctx, limit=50, cursor=None))
    assert {a.id for a in items} == {_OWN_ID, _OTHER_ID}
    # Fremden Agenten lesen ist erlaubt.
    assert asyncio.run(_service().get(ctx, _OTHER_ID)).id == _OTHER_ID


def test_scope_assigned_sees_only_self() -> None:
    ctx = _ctx(ReadScope.assigned)
    # Liste enthaelt NUR den eigenen Agenten — auch wenn er disabled ist.
    items, _cursor = asyncio.run(_service().list_all(ctx, limit=50, cursor=None))
    assert [a.id for a in items] == [_OWN_ID]
    # Eigenen Agenten lesen: ok.
    assert asyncio.run(_service().get(ctx, _OWN_ID)).id == _OWN_ID
    # Fremden Agenten lesen: 404 (verraet nicht mal Existenz).
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_service().get(ctx, _OTHER_ID))
    assert exc.value.status_code == 404


def test_list_enriches_card_pills() -> None:
    """List-Card-Pills: `list_all` joint Persona-/Template-Namen, aktive
    Template-Version und Playbook-Anzahl in die Reads (Human-Scope = alle)."""
    own = _agent(_OWN_ID, "Eigener (frisch)", AgentStatus.disabled)
    other = _agent(_OTHER_ID, "Fremder", AgentStatus.enabled)
    repo = _FakeAgentRepo([own, other])
    repo.meta[_OWN_ID] = AgentListMeta(
        persona_name="Coach Carla",
        template_name="Support-Template",
        template_version=2,
        playbook_count=3,
        pending_memory_count=2,
        is_favorite=True,
    )
    service = AgentService(repo)  # type: ignore[arg-type]
    items, _cursor = asyncio.run(service.list_all(_ctx(None), limit=50, cursor=None))
    by_id = {a.id: a for a in items}
    assert by_id[_OWN_ID].persona_name == "Coach Carla"
    assert by_id[_OWN_ID].template_name == "Support-Template"
    assert by_id[_OWN_ID].template_version == 2
    assert by_id[_OWN_ID].playbook_count == 3
    assert by_id[_OWN_ID].pending_memory_count == 2
    # Der Stern kommt aus demselben Batch-Aggregat wie die Pills (#427).
    assert by_id[_OWN_ID].is_favorite is True
    # Ohne Meta-Eintrag bleibt das Read auf dem konservativen Default.
    assert by_id[_OTHER_ID].is_favorite is False
    # Ohne Meta-Eintrag bleibt der fremde Agent auf den Defaults.
    assert by_id[_OTHER_ID].persona_name is None
    assert by_id[_OTHER_ID].playbook_count == 0
    assert by_id[_OTHER_ID].pending_memory_count == 0


def test_scope_none_blocks_with_403() -> None:
    ctx = _ctx(ReadScope.none)
    with pytest.raises(HTTPException) as exc_list:
        asyncio.run(_service().list_all(ctx, limit=50, cursor=None))
    assert exc_list.value.status_code == 403
    with pytest.raises(HTTPException) as exc_get:
        asyncio.run(_service().get(ctx, _OWN_ID))
    assert exc_get.value.status_code == 403


# ---------------------------------------------------------------------------
# Favoriten sind Menschen-Daten — auch beim LESEN (#427, Security-Review M-1).
# ---------------------------------------------------------------------------
def test_human_list_resolves_own_favorites() -> None:
    """Fuer einen Menschen fragt das Batch-Aggregat seine eigenen Sterne ab."""
    repo = _FakeAgentRepo([_agent(_OWN_ID, "Eigener", AgentStatus.enabled)])
    service = AgentService(repo)  # type: ignore[arg-type]

    asyncio.run(service.list_all(_ctx(None), limit=50, cursor=None))

    assert repo.last_meta_user_id == _OWNER


def test_agent_bound_token_gets_no_favorites() -> None:
    """Ein agent-gebundener Token bekommt KEINE Favoritenliste.

    `ctx.user_id` ist dort der Mensch, dem der Token gehoert. Wuerde er
    durchgereicht, saehe der Agent — bei einem Remote-Connector ein fremder
    LLM-Anbieter — dessen private Markierungen, und `list_agents` antwortete
    pro Token-Besitzer unterschiedlich. Der Schreibpfad ist aus demselben Grund
    Menschen vorbehalten.
    """
    repo = _FakeAgentRepo([_agent(_OWN_ID, "Eigener", AgentStatus.enabled)])
    repo.meta[_OWN_ID] = AgentListMeta(
        persona_name=None,
        template_name=None,
        template_version=None,
        playbook_count=0,
        pending_memory_count=0,
        is_favorite=True,
    )
    service = AgentService(repo)  # type: ignore[arg-type]

    items, _cursor = asyncio.run(service.list_all(_ctx(ReadScope.assigned), limit=50, cursor=None))

    assert repo.last_meta_user_id is None
    # Selbst wenn das Aggregat `True` liefern wuerde: die Query fragt gar nicht
    # erst nach den Sternen eines Menschen.
    assert items != []
