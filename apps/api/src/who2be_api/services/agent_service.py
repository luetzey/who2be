"""Geschaeftslogik fuer Agents.

Agents sind Konfig — kein Versions-Workflow. Schreiben verlangt
`editor`-Rolle (ADR-0023), Lesen ist fuer Viewer offen. Verweise auf
Persona/Template werden DB-seitig per Composite-FK auf den Workspace
gepinnt; ein 404 statt 422 ist die korrekte Antwort, wenn die referenzierte
Persona/Template nicht (mehr) existiert oder zu einem anderen Workspace
gehoert.

Menschen-Vorbehalte (Security-Review Phase 2, H4/H5). Ein agent-gebundener
Token darf Agenten anlegen und aendern (der Builder tut genau das,
`agent_write` + `_guard_policy_escalation`) — mit zwei Ausnahmen, die keine
Konfiguration, sondern Compliance-Anker sind:

- **Modell-Config** (`model_provider`/`model_name`, H4): Sie ist die Basis
  der Frage „welche Daten gingen an welchen externen Anbieter". Duerfte ein
  Agent sie an sich selbst schreiben, koennte er seine eigene Attribution
  faelschen — erst auf 'local' stellen, lesen, zurueckstellen. Sie bleibt
  deshalb dem Menschen vorbehalten (Muster `memory_service._require_human`).
- **Loeschen** (H5): Ein Agent-Delete scheitert seit Migration 0080 an den
  Protokollzeilen (FK ohne Cascade) — es ist damit ein Retention-Vorgang,
  kein Konfigurationsschritt. Zusaetzlich greift `agent_read_restrict` auch
  hier, damit ein Agent nicht ueber fremde IDs stochern kann.

Das UPDATE bleibt bewusst agent-faehig: es komplett zu sperren wuerde den
verwalteten Builder-Pfad (MCP `update_agent`) brechen, ohne die eigentliche
Luecke — die faelschbare Attribution — enger zu schliessen als das Feld-Gate.
"""

from datetime import datetime
from uuid import UUID, uuid4

import asyncpg
from asyncpg.exceptions import ForeignKeyViolationError
from fastapi import HTTPException, status

from who2be_api.core.agent_scope import agent_read_restrict
from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_unmanaged,
)
from who2be_api.repositories.agent_repository import AgentRepository
from who2be_api.services.audit_service import AuditService
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


def _is_agent_bound(ctx: WorkspaceContext) -> bool:
    """True fuer einen agent-gebundenen Token (Defense-in-Depth, beide Indikatoren).

    Muster `memory_service._require_human` / `workarea_scope.is_agent_bound`:
    heute impliziert `agent_id` eine Policy, aber der Menschen-Vorbehalt soll
    nicht an dieser DB-Invariante haengen.
    """
    return ctx.tool_policy is not None or ctx.agent_id is not None


def _model_config_is_human_only() -> ApiGateError:
    """403 fuer den Versuch eines Agenten, Modell-Config zu schreiben (H4).

    Reason `missing_capability` folgt `memory_service._require_human`: es ist
    kein Rollen- und kein Transitions-Problem, sondern „dieser Aufrufertyp hat
    diese Befugnis nicht" — `area_forbidden` waere sachlich falsch (es geht
    um keine Area), `insufficient_role` irrefuehrend (die Rolle reicht; die
    Agent-BINDUNG ist das Hindernis).
    """
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="missing_capability",
        actionable_by="human",
        detail=(
            "Die Modell-Konfiguration (model_provider/model_name) pflegt "
            "ausschliesslich ein Mensch: sie ist die Grundlage der "
            "Compliance-Auswertung des Zugriffslogs, und ein Agent darf seine "
            "eigene Zuordnung nicht aendern koennen."
        ),
    )


def _delete_is_human_only() -> ApiGateError:
    """403 fuer den Agent-Delete durch einen agent-gebundenen Token (H5)."""
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="missing_capability",
        actionable_by="human",
        detail=(
            "Agenten loeschen ist Menschen vorbehalten — mit dem Agenten "
            "verschwindet der Bezugspunkt seines Zugriffsprotokolls."
        ),
    )


def _delete_blocked_by_access_log() -> ApiGateError:
    """409, wenn Protokollzeilen den Agent-Delete blockieren (H5, Migration 0080).

    Gewollte Konsequenz des FK ohne Cascade: das Compliance-Log ueberlebt den
    Agenten. Reason `concurrent_conflict` ist die bestehende Wahl fuer „der
    aktuelle Datenbestand laesst diese Aktion nicht zu" (Muster
    `wa_tables._name_conflict`) — ein neuer Reason waere Vokabular ohne Not.
    """
    return ApiGateError(
        status=status.HTTP_409_CONFLICT,
        reason="concurrent_conflict",
        actionable_by="human",
        detail=(
            "Agent hat protokollierte Zugriffe — Loeschung nur ueber den "
            "Retention-/Purge-Pfad. Das Zugriffsprotokoll ist append-only und "
            "ueberlebt den Agenten bewusst; wer den Agenten stilllegen will, "
            "setzt ihn auf 'disabled'."
        ),
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
    """Agent-CRUD ohne Versionierung.

    `audit_service` + `pool` sind optional (aeltere Test-Fakes laufen ohne):
    sind beide gesetzt, protokolliert der Update-Pfad Aenderungen an der
    betreiber-gepflegten Modell-Config (`model_provider`/`model_name`,
    User-Entscheidung 6/ADR-0047) als `audit_log`-Eintrag
    ``agent.model_config_changed`` mit altem UND neuem Wert.
    """

    def __init__(
        self,
        repo: AgentRepository,
        audit_service: AuditService | None = None,
        pool: asyncpg.Pool | None = None,
    ) -> None:
        self._repo = repo
        self._audit = audit_service
        self._pool = pool

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
        # `agent_read`-Scope (No-Op fuer Menschen/JWT). `none` => 403; `assigned`
        # => nur der eigene Agent; `all` => ganzer Workspace. Bewusst KEIN
        # `enabled`-only-Filter: ein Verwalter muss auch frisch erstellte
        # (=disabled) und deaktivierte Agenten sehen, um sie zu vervollstaendigen.
        restrict = agent_read_restrict(ctx)
        if restrict is not None:
            # Self-Scope: hoechstens der eigene Agent, keine Pagination noetig.
            own = await self._repo.fetch(ctx.workspace_id, ctx.agent_id) if ctx.agent_id else None
            items = [own] if own is not None else []
            return await self._enrich(ctx.workspace_id, items), None
        rows = await self._repo.list_by_workspace(ctx.workspace_id, limit + 1, cursor)
        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            tail = rows[-1]
            next_cursor = encode_cursor(tail.created_at, tail.id)
        return await self._enrich(ctx.workspace_id, rows), next_cursor

    async def _enrich(self, workspace_id: UUID, items: list[AgentRead]) -> list[AgentRead]:
        """Joint die List-Card-Pills (Batch-Aggregat) in die Reads (kein N+1).

        Ein einziger `list_meta`-Roundtrip fuer alle Agenten der Seite; fehlt ein
        Meta-Eintrag (theoretisch — Zeile zwischen List und Aggregat geloescht),
        bleibt das Read auf den Feld-Defaults.
        """
        if not items:
            return items
        meta = await self._repo.list_meta(workspace_id, [a.id for a in items])
        enriched: list[AgentRead] = []
        for agent in items:
            found = meta.get(agent.id)
            if found is None:
                enriched.append(agent)
                continue
            enriched.append(
                agent.model_copy(
                    update={
                        "persona_name": found.persona_name,
                        "template_name": found.template_name,
                        "template_version": found.template_version,
                        "playbook_count": found.playbook_count,
                        "pending_memory_count": found.pending_memory_count,
                    }
                )
            )
        return enriched

    async def get(self, ctx: WorkspaceContext, agent_id: UUID) -> AgentRead:
        # `none` => 403; `assigned` => nur der eigene Agent (fremde ID => 404,
        # verraet nicht mal Existenz); `all`/Mensch => jeder Agent im Workspace.
        restrict = agent_read_restrict(ctx)
        if restrict is not None and agent_id not in restrict:
            raise _not_found()
        agent = await self._repo.fetch(ctx.workspace_id, agent_id)
        if agent is None:
            raise _not_found()
        return agent

    async def update(self, ctx: WorkspaceContext, agent_id: UUID, data: AgentUpdate) -> AgentRead:
        """Konfig-Update in-place (None = Feld bleibt unangetastet).

        `model_provider`/`model_name` (User-Entscheidung 6, ADR-0047) laufen
        mit derselben None-Semantik durch; explizites Leeren (zurueck auf
        NULL) ist dadurch bewusst (noch) nicht moeglich — dokumentierter
        offener Punkt. Sie sind das EINZIGE Feld-Paar, das ein
        agent-gebundener Token nicht setzen darf (H4, s. Modul-Kopf). Eine
        tatsaechliche Aenderung der Modell-Config wird im `audit_log`
        protokolliert (`agent.model_config_changed`, alter + neuer Wert +
        `agent_id` des Aufrufers im detail).
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.agent_write)
        if (data.model_provider is not None or data.model_name is not None) and _is_agent_bound(
            ctx
        ):
            # VOR jedem Repo-Zugriff: der Versuch soll nichts anfassen (H4).
            raise _model_config_is_human_only()
        if data.tool_policy is not None:
            _guard_policy_escalation(ctx, data.tool_policy)
        existing = await self._repo.fetch(ctx.workspace_id, agent_id)
        if existing is None:
            raise _not_found()
        require_unmanaged(existing.is_managed)
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
            data.model_provider,
            data.model_name,
        )
        if agent is None:
            # Existenz oben bereits bestaetigt → der Composite-FK auf
            # persona/template war das Problem.
            raise _invalid_reference()
        await self._audit_model_config_change(ctx, existing, agent)
        return agent

    async def _audit_model_config_change(
        self, ctx: WorkspaceContext, before: AgentRead, after: AgentRead
    ) -> None:
        """Auditiert eine Aenderung der Modell-Config (ADR-0047, WP14).

        Vergleich auf dem persistierten Stand (vorher/nachher, nie auf dem
        Client-Input): nur wenn sich `model_provider` oder `model_name`
        tatsaechlich geaendert hat, entsteht ein `audit_log`-Eintrag
        ``agent.model_config_changed`` mit altem + neuem Wert (Muster
        `token_service`). Ohne Audit-Verdrahtung (Test-Fakes) No-op.

        `agent_id` steht zusaetzlich im detail (Security-Review H4):
        `actor_id` ist im Token-Pfad der BESITZER des Tokens, nicht der
        aufrufende Agent — ohne das Feld liesse sich hinterher nicht
        unterscheiden, ob ein Mensch oder eine Maschine unter seinem Namen
        gehandelt hat. Bei einem Menschen ist der Wert `None`.
        """
        if self._audit is None or self._pool is None:
            return
        if before.model_provider == after.model_provider and before.model_name == after.model_name:
            return
        await self._audit.record(
            self._pool,
            action="agent.model_config_changed",
            actor_id=ctx.user_id,
            workspace_id=ctx.workspace_id,
            target=after.id,
            detail={
                "model_provider": {"old": before.model_provider, "new": after.model_provider},
                "model_name": {"old": before.model_name, "new": after.model_name},
                "agent_id": str(ctx.agent_id) if ctx.agent_id is not None else None,
            },
        )

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
        # `activatable` garantiert Persona + Template (mit aktiver Persona-Version).
        if source.persona_id is None or source.system_prompt_template_id is None:
            raise _not_activatable(source.missing)
        if source.is_managed:
            # Voll-Klon: ein verwalteter Agent (Builder) wird mit unverwalteten,
            # editierbaren Kopien von Persona + Playbooks + Template dupliziert —
            # so erhaelt der User einen frei anpassbaren eigenen Builder.
            agent = await self._repo.deep_copy(
                ctx.workspace_id,
                ctx.user_id,
                source.persona_id,
                source.system_prompt_template_id,
                f"agent-builder-copy-{uuid4().hex[:8]}",
                name,
                source.description,
                source.status,
                source.tool_policy,
            )
        else:
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
        """Loescht einen Agenten — Menschen vorbehalten (H5, s. Modul-Kopf).

        Seit Migration 0080 haelt der FK des Zugriffslogs dagegen (NO ACTION
        statt CASCADE): hat der Agent je etwas gelesen oder geschrieben,
        scheitert der Delete mit 409. Das ist der gewollte Zustand — das
        Protokoll ist append-only und wird nur ueber den Retention-/Purge-Pfad
        (Owner-Connection, DSGVO-Erasure) abgeraeumt.
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.agent_write)
        if _is_agent_bound(ctx):
            raise _delete_is_human_only()
        # Scope-Gate wie in `list_all`/`get` (Review H5). Heute unerreichbar —
        # der Menschen-Vorbehalt darueber hat jeden agent-gebundenen Aufrufer
        # schon abgewiesen, und fuer Menschen liefert `agent_read_restrict`
        # immer `None`. Bewusst trotzdem hier: es ist das zweite Schloss, das
        # haelt, falls der Vorbehalt je gelockert wird (der Delete-Pfad war
        # der einzige Agent-Pfad OHNE Scope-Pruefung).
        restrict = agent_read_restrict(ctx)
        if restrict is not None and agent_id not in restrict:
            raise _not_found()
        existing = await self._repo.fetch(ctx.workspace_id, agent_id)
        if existing is None:
            raise _not_found()
        require_unmanaged(existing.is_managed)
        try:
            deleted = await self._repo.delete(ctx.workspace_id, agent_id)
        except ForeignKeyViolationError as exc:
            raise _delete_blocked_by_access_log() from exc
        if not deleted:
            raise _not_found()

    @staticmethod
    def is_disabled(agent: AgentRead) -> bool:
        return agent.status == AgentStatus.disabled
