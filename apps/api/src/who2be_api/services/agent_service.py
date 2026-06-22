"""Geschaeftslogik fuer Agents.

Agents sind Konfig — kein Versions-Workflow. Schreiben verlangt
`editor`-Rolle (ADR-0023), Lesen ist fuer Viewer offen. Verweise auf
Persona/Template werden DB-seitig per Composite-FK auf den Workspace
gepinnt; ein 404 statt 422 ist die korrekte Antwort, wenn die referenzierte
Persona/Template nicht (mehr) existiert oder zu einem anderen Workspace
gehoert.
"""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.agent_scope import require_read_flag
from who2be_api.core.security import WorkspaceContext, require_capability, require_role
from who2be_api.repositories.agent_repository import AgentRepository
from who2be_models import (
    AgentCapability,
    AgentCopy,
    AgentCreate,
    AgentRead,
    AgentStatus,
    AgentToolPolicy,
    AgentUpdate,
    WorkspaceRole,
    encode_cursor,
)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent nicht gefunden.")


_MISSING_LABELS = {
    "persona": "Persona verknuepfen",
    "template": "System-Prompt-Template verknuepfen",
    "persona_active": "verknuepfte Persona aktiv schalten",
}


def _not_activatable(missing: list[str]) -> HTTPException:
    """409 mit Klartext, was dem Agenten zur Aktivierbarkeit fehlt."""
    todo = ", ".join(_MISSING_LABELS.get(item, item) for item in missing)
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Agent ist noch nicht vollstaendig — fehlt: {todo}. "
            "Aktivieren und Kopieren sind erst moeglich, wenn Persona und Template "
            "gesetzt sind und die Persona eine aktive Version hat."
        ),
    )


def _invalid_reference() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=("Persona oder Template existiert nicht in diesem Workspace."),
    )


def _guard_policy_escalation(ctx: WorkspaceContext, target: AgentToolPolicy) -> None:
    """Verhindert, dass ein agent-gebundener Aufrufer Rechte „nach oben" vererbt.

    Ein menschlicher/ungebundener Aufrufer (`ctx.tool_policy is None`) darf jede
    Policy setzen. Ein agent-gebundener Aufrufer (z. B. ein Agent mit
    `agent_write`) darf hingegen keinen Agenten anlegen/aendern/kopieren, dessen
    Tool-Policy die eigene uebersteigt — sonst koennte er sich selbst (per
    Update der eigenen Zeile) oder einen neuen Agenten mit mehr Rechten
    ausstatten und so die Einschraenkung umgehen.
    """
    if ctx.tool_policy is None:
        return
    if not target.is_within(ctx.tool_policy):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Ein Agent darf keinen Agenten mit mehr Rechten als seinen eigenen "
                "anlegen oder aendern."
            ),
        )


class AgentService:
    """Agent-CRUD ohne Versionierung."""

    def __init__(self, repo: AgentRepository) -> None:
        self._repo = repo

    async def _missing_for_enable(
        self,
        workspace_id: UUID,
        persona_id: UUID | None,
        template_id: UUID | None,
    ) -> list[str]:
        """Was dem (effektiven) Agenten zur Aktivierbarkeit fehlt.

        Spiegelt `AgentRead.missing`, aber fuer die *geplanten* Refs eines
        Create/Update — die Persona-Aktivitaet wird live aus der DB gelesen,
        damit wir vor dem Schreiben gaten koennen (kein Enable-then-Rollback).
        """
        gaps: list[str] = []
        if persona_id is None:
            gaps.append("persona")
        if template_id is None:
            gaps.append("template")
        persona_active = persona_id is not None and await self._repo.persona_has_active_version(
            workspace_id, persona_id
        )
        if not persona_active:
            gaps.append("persona_active")
        return gaps

    async def create(self, ctx: WorkspaceContext, data: AgentCreate) -> AgentRead:
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.agent_write)
        _guard_policy_escalation(ctx, data.tool_policy)
        if data.status == AgentStatus.enabled:
            missing = await self._missing_for_enable(
                ctx.workspace_id, data.persona_id, data.system_prompt_template_id
            )
            if missing:
                raise _not_activatable(missing)
        agent = await self._repo.insert(
            ctx.workspace_id,
            ctx.user_id,
            data.name,
            data.description,
            data.persona_id,
            data.system_prompt_template_id,
            data.status,
            data.tool_policy,
        )
        if agent is None:
            raise _invalid_reference()
        return agent

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[AgentRead], str | None]:
        # An/Aus-Gate „Agenten lesen" (No-Op fuer Menschen/JWT). Bewusst KEIN
        # `enabled`-only-Filter: ein Builder muss auch frisch erstellte (=disabled)
        # und deaktivierte Agenten sehen, um sie zu vervollstaendigen.
        require_read_flag(ctx, "agent_read", "Agenten")
        rows = await self._repo.list_by_workspace(ctx.workspace_id, limit + 1, cursor)
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(self, ctx: WorkspaceContext, agent_id: UUID) -> AgentRead:
        require_read_flag(ctx, "agent_read", "Agenten")
        agent = await self._repo.fetch(ctx.workspace_id, agent_id)
        if agent is None:
            raise _not_found()
        return agent

    async def update(self, ctx: WorkspaceContext, agent_id: UUID, data: AgentUpdate) -> AgentRead:
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.agent_write)
        if data.tool_policy is not None:
            _guard_policy_escalation(ctx, data.tool_policy)
        existing = await self._repo.fetch(ctx.workspace_id, agent_id)
        if existing is None:
            raise _not_found()
        # Enable-Gate auf den *effektiven* Stand nach dem Update (None = unveraendert).
        # Greift auch, wenn ein bereits aktiver Agent durch Ref-Wechsel
        # unvollstaendig wuerde — so bleibt die Invariante „enabled ⇒ aktivierbar".
        effective_status = data.status if data.status is not None else existing.status
        if effective_status == AgentStatus.enabled:
            persona_id = data.persona_id if data.persona_id is not None else existing.persona_id
            template_id = (
                data.system_prompt_template_id
                if data.system_prompt_template_id is not None
                else existing.system_prompt_template_id
            )
            missing = await self._missing_for_enable(ctx.workspace_id, persona_id, template_id)
            if missing:
                raise _not_activatable(missing)
        agent = await self._repo.update(
            ctx.workspace_id,
            agent_id,
            data.name,
            data.description,
            data.persona_id,
            data.system_prompt_template_id,
            data.status,
            data.tool_policy,
        )
        if agent is None:
            # Existenz oben bereits bestaetigt → der Composite-FK auf
            # persona/template war das Problem.
            raise _invalid_reference()
        return agent

    async def copy(self, ctx: WorkspaceContext, agent_id: UUID, data: AgentCopy) -> AgentRead:
        """Dupliziert einen Agent unter neuem Namen.

        Gesperrt (409), solange die Quelle nicht aktivierbar ist (Persona oder
        Template fehlt ODER die Persona hat keine aktive Version) — eine solche
        Kopie waere selbst nicht einsetzbar. Die Kopie uebernimmt Persona,
        Template, Beschreibung und Status und gehoert dem kopierenden User.
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.agent_write)
        source = await self._repo.fetch(ctx.workspace_id, agent_id)
        if source is None:
            raise _not_found()
        if not source.activatable:
            raise _not_activatable(source.missing)
        # Die Kopie uebernimmt die Quell-Policy — fuer agent-gebundene Aufrufer
        # nur, soweit sie ihre eigene nicht uebersteigt.
        _guard_policy_escalation(ctx, source.tool_policy)
        name = data.name if data.name is not None else f"{source.name} (Kopie)"
        agent = await self._repo.insert(
            ctx.workspace_id,
            ctx.user_id,
            name,
            source.description,
            source.persona_id,
            source.system_prompt_template_id,
            source.status,
            source.tool_policy,
        )
        if agent is None:
            # Persona/Template wurde zwischen fetch und insert geloescht.
            raise _invalid_reference()
        return agent

    async def delete(self, ctx: WorkspaceContext, agent_id: UUID) -> None:
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.agent_write)
        deleted = await self._repo.delete(ctx.workspace_id, agent_id)
        if not deleted:
            raise _not_found()

    @staticmethod
    def is_disabled(agent: AgentRead) -> bool:
        return agent.status == AgentStatus.disabled
