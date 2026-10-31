"""Geschaeftslogik der Werkzeug-Profile pro Agent (ADR-0059 §7, Paket Q2b).

Zwei Wege mit unterschiedlichen Rechten (W59-2, Owner 2026-10-21):

* **Profile pflegen** (anlegen, aendern, auf Lieferstand setzen, loeschen) darf
  nur ``admin``. Ein Profil wirkt auf jeden Agenten, der es nutzt, es ist
  Workspace-Konfiguration (§7.2). Lesen (Liste, Katalog) darf jedes Mitglied,
  damit ein editor sieht, was er zuordnet.
* **Zuordnen am Agenten** darf ``editor``, und zwar **nur ein Mensch** (§7.3).
  Ein agent-gebundener Token bekommt 403 ``human_only``, auch der Builder: der
  Agent meldet einen Bedarf (P3a), ein Mensch passt an. Der Weg gilt bewusst
  auch fuer verwaltete Agenten (kein ``require_unmanaged``), sonst koennte
  niemand dem Builder ein fehlendes Werkzeug freigeben.

Ein Profil ist **kein Recht** (§3.3): Der Service prueft Namen gegen den
Katalog und Rollen, aber nie Capabilities, und die API setzt Profile nirgends
durch. Gruppen, Kern-Werkzeuge und Pruef-Helfer kommen ausschliesslich aus
``who2be_models.tool_profiles`` (Single Source of Truth, §11).

Jede Aenderung landet im ``audit_log`` (§7.4): ``tool_profile.created``,
``tool_profile.updated``, ``tool_profile.reset``, ``tool_profile.deleted`` und
``agent.tool_profile_changed`` mit altem und neuem Stand (Muster
``agent.model_config_changed``). Kein SQL hier, das liegt im Repository
(Leitplanke DECISIONS 2026-07-20). Fehlertexte bewusst ohne Umlaute, wie die
uebrigen API-Texte.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import WorkspaceContext, is_agent_bound, require_role
from who2be_api.repositories.agent_repository import AgentRepository
from who2be_api.repositories.tool_profile_repository import (
    ToolProfileBuiltinError,
    ToolProfileInUseError,
    ToolProfileNameTakenError,
    ToolProfileRepository,
)
from who2be_api.services.audit_service import AuditService
from who2be_models import DEFAULT_LOCALE, AgentRead, WorkspaceRead, WorkspaceRole
from who2be_models.tool_profiles import (
    AgentToolProfileUpdate,
    ToolCatalogRead,
    ToolProfileCreate,
    ToolProfileRead,
    ToolProfileUpdate,
    core_tools_in,
    tool_catalog,
    unknown_groups,
    unknown_tools,
)


class _WorkspaceLookup(Protocol):
    """Was der Service vom Workspace-Repository braucht (Content-Sprache)."""

    async def fetch(self, workspace_id: UUID) -> WorkspaceRead | None: ...


# ---------------------------------------------------------------- Fehler


def _profile_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Werkzeug-Profil nicht gefunden.",
        reason="tool_profile_not_found",
    )


def _agent_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Agent nicht gefunden.",
        reason="agent_not_found",
    )


def _name_conflict(name: str) -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Ein Werkzeug-Profil mit dem Namen '{name}' gibt es in diesem Workspace schon.",
        reason="tool_profile_name_conflict",
        params={"name": name},
    )


def _in_use(agent_count: int) -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Das Werkzeug-Profil ist noch {agent_count} Agent(en) zugeordnet. "
            "Erst die Agenten auf ein anderes Profil stellen, dann loeschen."
        ),
        reason="tool_profile_in_use",
        params={"agent_count": agent_count},
    )


def _builtin_undeletable() -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Mitgelieferte Werkzeug-Profile lassen sich nicht loeschen, nur anpassen "
            "oder auf den Lieferstand zuruecksetzen."
        ),
        reason="tool_profile_builtin",
    )


def _not_builtin() -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail="Nur mitgelieferte Werkzeug-Profile haben einen Lieferstand.",
        reason="tool_profile_not_builtin",
    )


def _unknown_tools(names: list[str]) -> ApiError:
    listed = ", ".join(names)
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unbekannte Werkzeuge: {listed}.",
        reason="unknown_tool",
        params={"tools": listed},
    )


def _unknown_groups(names: list[str]) -> ApiError:
    listed = ", ".join(names)
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Unbekannte Werkzeuggruppen: {listed}.",
        reason="unknown_tool_group",
        params={"groups": listed},
    )


def _core_not_removable(names: list[str]) -> ApiError:
    listed = ", ".join(names)
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=(
            f"Kern-Werkzeuge lassen sich nicht sperren: {listed}. "
            "ping, whoami und report_problem bleiben in jedem Profil."
        ),
        reason="core_tool_not_removable",
        params={"tools": listed},
    )


def _human_only() -> ApiGateError:
    """403 fuer einen agent-gebundenen Token an der Zuordnung (§7.3).

    Gate-Fehler (RFC 7807) wie die Modell-Konfiguration: Die Rolle reicht,
    die Agent-BINDUNG ist das Hindernis, und nur ein Mensch kann es beheben.
    """
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="human_only",
        actionable_by="human",
        detail=(
            "Das Werkzeug-Profil eines Agenten stellt nur ein Mensch ein. "
            "Fehlt dir ein Werkzeug, melde es mit report_problem und "
            "category='tool_request'."
        ),
    )


# ---------------------------------------------------------------- Service


def _check_profile_names(groups: list[str], tools: list[str]) -> None:
    """422, wenn ein Profil Gruppen oder Werkzeuge ausserhalb des Katalogs nennt."""
    bad_groups = unknown_groups(groups)
    if bad_groups:
        raise _unknown_groups(bad_groups)
    bad_tools = unknown_tools(tools)
    if bad_tools:
        raise _unknown_tools(bad_tools)


def _profile_state(agent: AgentRead) -> dict[str, Any]:
    """Profil-Stand eines Agenten fuer das Audit-Detail (alt/neu)."""
    return {
        "tool_profile_id": str(agent.tool_profile_id) if agent.tool_profile_id else None,
        "tools_added": list(agent.tools_added),
        "tools_removed": list(agent.tools_removed),
    }


class ToolProfileService:
    """CRUD der Profile, Zuordnung am Agenten, Audit und Fehlercodes."""

    def __init__(
        self,
        repo: ToolProfileRepository,
        agent_repo: AgentRepository,
        workspace_repo: _WorkspaceLookup,
        *,
        audit_service: AuditService | None = None,
        pool: asyncpg.Pool | None = None,
    ) -> None:
        self._repo = repo
        self._agents = agent_repo
        self._workspaces = workspace_repo
        self._audit = audit_service
        self._pool = pool

    # ------------------------------------------------------------ Lesen

    async def list_all(self, ctx: WorkspaceContext) -> list[ToolProfileRead]:
        """Alle Profile des Workspace (jedes Mitglied)."""
        require_role(ctx, WorkspaceRole.viewer)
        return await self._repo.list_by_workspace(ctx.workspace_id)

    async def catalog(self, ctx: WorkspaceContext) -> ToolCatalogRead:
        """Gruppen und Kern-Werkzeuge aus dem Code (jedes Mitglied)."""
        require_role(ctx, WorkspaceRole.viewer)
        return tool_catalog()

    # ------------------------------------------------------------ Pflegen (admin)

    async def create(self, ctx: WorkspaceContext, data: ToolProfileCreate) -> ToolProfileRead:
        require_role(ctx, WorkspaceRole.admin)
        _check_profile_names(data.groups, data.tools)
        try:
            profile = await self._repo.insert(
                ctx.workspace_id, data.name, data.description, data.groups, data.tools
            )
        except ToolProfileNameTakenError as exc:
            raise _name_conflict(data.name) from exc
        await self._record(ctx, "tool_profile.created", profile.id, {"name": profile.name})
        return profile

    async def update(
        self, ctx: WorkspaceContext, profile_id: UUID, data: ToolProfileUpdate
    ) -> ToolProfileRead:
        """Ersetzt Name, Beschreibung, Gruppen und Werkzeuge, auch bei mitgelieferten."""
        require_role(ctx, WorkspaceRole.admin)
        _check_profile_names(data.groups, data.tools)
        before = await self._repo.fetch(ctx.workspace_id, profile_id)
        if before is None:
            raise _profile_not_found()
        try:
            profile = await self._repo.update(
                ctx.workspace_id,
                profile_id,
                data.name,
                data.description,
                data.groups,
                data.tools,
            )
        except ToolProfileNameTakenError as exc:
            raise _name_conflict(data.name) from exc
        if profile is None:
            raise _profile_not_found()
        await self._record(
            ctx,
            "tool_profile.updated",
            profile.id,
            {
                "name": {"old": before.name, "new": profile.name},
                "groups": {"old": before.groups, "new": profile.groups},
                "tools": {"old": before.tools, "new": profile.tools},
            },
        )
        return profile

    async def reset(self, ctx: WorkspaceContext, profile_id: UUID) -> ToolProfileRead:
        """Setzt ein mitgeliefertes Profil auf den Lieferstand (§7.1)."""
        require_role(ctx, WorkspaceRole.admin)
        before = await self._repo.fetch(ctx.workspace_id, profile_id)
        if before is None:
            raise _profile_not_found()
        if before.builtin_key is None:
            raise _not_builtin()
        workspace = await self._workspaces.fetch(ctx.workspace_id)
        locale = workspace.content_locale if workspace is not None else DEFAULT_LOCALE
        try:
            profile = await self._repo.reset_builtin(ctx.workspace_id, profile_id, locale)
        except ToolProfileNameTakenError as exc:
            raise _name_conflict(str(exc)) from exc
        if profile is None:
            raise _profile_not_found()
        await self._record(
            ctx,
            "tool_profile.reset",
            profile.id,
            {"name": profile.name, "builtin_key": before.builtin_key.value},
        )
        return profile

    async def delete(self, ctx: WorkspaceContext, profile_id: UUID) -> None:
        """Loescht ein eigenes Profil; mitgeliefert oder zugeordnet ergibt 409."""
        require_role(ctx, WorkspaceRole.admin)
        before = await self._repo.fetch(ctx.workspace_id, profile_id)
        if before is None:
            raise _profile_not_found()
        try:
            deleted = await self._repo.delete(ctx.workspace_id, profile_id)
        except ToolProfileBuiltinError as exc:
            raise _builtin_undeletable() from exc
        except ToolProfileInUseError as exc:
            raise _in_use(exc.agent_count) from exc
        if not deleted:
            raise _profile_not_found()
        await self._record(ctx, "tool_profile.deleted", profile_id, {"name": before.name})

    # ------------------------------------------------------------ Zuordnen (editor, Mensch)

    async def assign(
        self, ctx: WorkspaceContext, agent_id: UUID, data: AgentToolProfileUpdate
    ) -> AgentRead:
        """Setzt Profil und Ausnahmen am Agenten; ``tool_profile_id=None`` heisst „Alle“.

        Reihenfolge: Rolle, dann Mensch, dann Eingabe, dann Existenz. So
        erfaehrt ein Agent-Token nichts ueber fremde IDs, bevor er abgewiesen
        ist. Gilt auch fuer verwaltete Agenten (§7.3).
        """
        require_role(ctx, WorkspaceRole.editor)
        if is_agent_bound(ctx):
            raise _human_only()
        core = core_tools_in(data.tools_removed)
        if core:
            raise _core_not_removable(core)
        bad = unknown_tools([*data.tools_added, *data.tools_removed])
        if bad:
            raise _unknown_tools(bad)
        before = await self._agents.fetch(ctx.workspace_id, agent_id)
        if before is None:
            raise _agent_not_found()
        if (
            data.tool_profile_id is not None
            and await self._repo.fetch(ctx.workspace_id, data.tool_profile_id) is None
        ):
            raise _profile_not_found()
        assigned = await self._repo.assign_agent(
            ctx.workspace_id,
            agent_id,
            data.tool_profile_id,
            data.tools_added,
            data.tools_removed,
        )
        if not assigned:
            # Zwischen Pruefung und Schreiben verschwunden: mit Profil hat der
            # zusammengesetzte FK abgelehnt, ohne Profil fehlt der Agent.
            raise _profile_not_found() if data.tool_profile_id is not None else _agent_not_found()
        after = await self._agents.fetch(ctx.workspace_id, agent_id)
        if after is None:
            raise _agent_not_found()
        old, new = _profile_state(before), _profile_state(after)
        if old != new:
            await self._record(
                ctx,
                "agent.tool_profile_changed",
                after.id,
                {"old": old, "new": new},
            )
        return after

    # ------------------------------------------------------------ Audit

    async def _record(
        self, ctx: WorkspaceContext, action: str, target: UUID, detail: dict[str, Any]
    ) -> None:
        """Audit-Eintrag; ohne Verdrahtung (Test-Fakes) No-op."""
        if self._audit is None or self._pool is None:
            return
        await self._audit.record(
            self._pool,
            action=action,
            actor_id=ctx.user_id,
            workspace_id=ctx.workspace_id,
            target=target,
            detail=detail,
        )


__all__ = ["ToolProfileService"]
