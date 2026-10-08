"""Faelle: melden, lesen, Uebergaenge, Zuordnung, Schilderung, Loeschen.

ADR-0053 Abschnitt 3.3 (Zustaende, Uebergaenge, Rechte), 6.1 und 6.5;
Lernschleife Phase D, Pakete D2a und D2c-1. Nur die Service-Schicht — Router
und OpenAPI kommen mit D2b bzw. D2c-2, MCP mit D4.

Rechte (3.3, Tabelle „Rechte“; Weiche F2 = a):

- **Melden:** Mensch ab `viewer`; Agent-Token mit `feedback_write` — fuer
  den eigenen und fuer andere Agenten des Workspace.
- **Lesen:** Mensch `viewer` nur selbst gemeldete Faelle, ab `editor` alle.
  Agent-Token ohne `case_triage` die Faelle ueber sich selbst (6.5
  `list_cases`: „case_triage; ohne: eigene“, Parallele zu den Pruefaellen
  in 3.2 „eigener Agent“; die Schilderung des betroffenen Agenten setzt
  voraus, dass er seinen Fall lesen kann), mit `case_triage` alle. Was der
  Aufrufer nicht lesen darf, gibt es fuer ihn nicht (`case_not_found`, kein
  Enumerieren).
- **Triagieren, zuordnen:** Mensch ab `editor`; Agent-Token mit
  `case_triage`.
- **Schilderung:** nur der betroffene Agent (`agent_id` des Falls).
- **Loeschen:** Mensch ab `editor` (PM-Entscheidung Q6); Agent-Tokens nie.
- **Umwandeln/Uebernehmen** (convert 6.4, promote 6.5): Mensch ab `editor`;
  Agent-Tokens nie.

Agent-Tokens — auch der Builder — setzen nie `addressed`, `verified` oder
`dismissed` (F-W7, „Partei, nicht Richter“). Das prueft `is_agent_bound`,
bewusst KEINE Capability, damit es sich nicht freischalten laesst. `reopened`
gehoert in D2 ebenfalls dazu: 3.3 nennt dafuer nur den Menschen und das
System (Nachschau, Phase E).

Umfang in D2 (PM-Entscheidung zur Karte, innerhalb ADR 3.3): `in_progress`
und `verified` verlangen eine Massnahme bzw. deren Nachschau-Ergebnis.
Massnahmen gibt es erst mit Phase E (E2/E3); beide Ziele enden hier mit
`case_transition_forbidden` und `params.requires = "phase_e"`. Damit
`addressed` (und danach `reopened`) ohne Massnahme erreichbar ist, gilt
uebergangsweise die Kante `triaged -> addressed` — der Mensch-Pfad aus 3.3
(„sonst Mensch `editor`“, Pflicht Version). Phase E prueft, ob sie bleibt.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from fastapi import status
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    is_agent_bound,
    require_capability,
    require_role,
    require_write_rate,
    role_satisfies,
)
from who2be_api.repositories.case_repository import (
    CaseRepository,
    NotConvertible,
    NotPromotable,
)
from who2be_models import (
    AgentCapability,
    CaseActorKind,
    CaseAssignedByKind,
    CaseCreate,
    CaseDetail,
    CaseElementInput,
    CaseElementRead,
    CaseEventCreate,
    CaseEventKind,
    CaseRead,
    CaseReporterKind,
    CaseStatementCreate,
    CaseStatementRead,
    CaseStatus,
    CaseTarget,
    EntityType,
    ProblemReason,
    WorkspaceRole,
)
from who2be_models.case import CASE_NOTE_MAX_LENGTH, CaseConvertRequest

# Erlaubte Kanten nach 3.3 (Zustandsdiagramm). `in_progress` und `verified`
# stehen drin, sind in D2 aber gesperrt (`_PHASE_E_TARGETS`).
_EDGES: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.open: frozenset({CaseStatus.triaged, CaseStatus.dismissed}),
    CaseStatus.triaged: frozenset(
        # `addressed` direkt: Uebergangskante bis Phase E (Modul-Docstring).
        {CaseStatus.in_progress, CaseStatus.addressed, CaseStatus.dismissed}
    ),
    CaseStatus.in_progress: frozenset({CaseStatus.addressed, CaseStatus.dismissed}),
    CaseStatus.addressed: frozenset({CaseStatus.verified, CaseStatus.reopened}),
    CaseStatus.reopened: frozenset({CaseStatus.triaged}),
    CaseStatus.verified: frozenset(),
    CaseStatus.dismissed: frozenset(),
}

# Ziele, die eine Massnahme (3.6) voraussetzen — kommen mit Phase E (E2/E3).
_PHASE_E_TARGETS: frozenset[CaseStatus] = frozenset({CaseStatus.in_progress, CaseStatus.verified})

# Ziele, die kein Agent-Token setzt (F-W7; `reopened` siehe Modul-Docstring).
_HUMAN_ONLY_TARGETS: frozenset[CaseStatus] = frozenset(
    {CaseStatus.addressed, CaseStatus.verified, CaseStatus.dismissed, CaseStatus.reopened}
)

# Ziele mit Begruendungspflicht (3.3; DB-CHECK `agent_case_event_reason_check`).
_NOTE_REQUIRED: frozenset[CaseStatus] = frozenset({CaseStatus.dismissed, CaseStatus.reopened})

_ELEMENT_NOT_FOUND: dict[CaseTarget, tuple[ProblemReason, str]] = {
    CaseTarget.persona: ("persona_not_found", "Persona nicht gefunden."),
    CaseTarget.playbook: ("playbook_not_found", "Playbook nicht gefunden."),
    CaseTarget.resource: ("resource_not_found", "Resource nicht gefunden."),
    CaseTarget.external_tool: ("external_tool_not_found", "Externes Tool nicht gefunden."),
    CaseTarget.system_prompt_template: (
        "system_prompt_template_not_found",
        "System-Prompt-Template nicht gefunden.",
    ),
    CaseTarget.memory: ("memory_not_found", "Memory nicht gefunden."),
}


class CaseTransitionRequest(BaseModel):
    """`POST /cases/{id}/transition` (6.5): Zielstatus plus Pflichtfelder.

    `measure_id` ist Teil des Vertrags (6.5), wird in D2 aber abgewiesen —
    Massnahmen gibt es erst mit Phase E.
    """

    __test__: ClassVar[bool] = False
    model_config = ConfigDict(extra="forbid")

    to: CaseStatus
    note: str | None = Field(default=None, min_length=1, max_length=CASE_NOTE_MAX_LENGTH)
    measure_id: UUID | None = None
    version_entity_type: EntityType | None = None
    version_id: UUID | None = None

    @model_validator(mode="after")
    def _check_version_pair(self) -> CaseTransitionRequest:
        if (self.version_entity_type is None) != (self.version_id is None):
            raise ValueError("version_entity_type und version_id nur gemeinsam angeben.")
        return self


def _case_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Fall nicht gefunden.",
        reason="case_not_found",
    )


def _agent_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Agent nicht gefunden.",
        reason="agent_not_found",
    )


def _version_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Die genannte Version gehoert nicht zu diesem Workspace.",
        reason="entity_version_not_found",
        params={"label": "Version"},
    )


def _transition_forbidden(
    current: CaseStatus, to: CaseStatus, detail: str, **extra: JsonValue
) -> ApiError:
    params: dict[str, JsonValue] = {"from": current.value, "to": to.value, **extra}
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
        reason="case_transition_forbidden",
        params=params,
    )


def _human_only(to: CaseStatus) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="case_transition_human_only",
        actionable_by="none",
        detail=(
            f"Den Status '{to.value}' setzt nur ein Mensch. Ein Agent ist Partei, "
            "nicht Richter — das laesst sich nicht freischalten."
        ),
    )


def _statement_not_subject() -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="case_statement_not_subject",
        actionable_by="none",
        detail="Eine Schilderung gibt nur der Agent ab, um dessen Verhalten es im Fall geht.",
    )


def _delete_forbidden_for_agents() -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="missing_capability",
        actionable_by="none",
        detail="Faelle loeschen ist Menschen ab der Rolle 'editor' vorbehalten.",
    )


def _triage_without_policy() -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="missing_capability",
        actionable_by="human",
        detail=(
            "Fuer diesen Agenten ist keine Tool-Policy geladen; ohne 'case_triage' "
            "kein Einordnen und kein Zuordnen."
        ),
    )


def _actor(ctx: WorkspaceContext) -> tuple[CaseActorKind, UUID]:
    """Akteur eines Events bzw. Urheber einer Zuordnung aus dem Aufrufweg."""
    if is_agent_bound(ctx) and ctx.agent_id is not None:
        return CaseActorKind.agent, ctx.agent_id
    return CaseActorKind.human, ctx.user_id


class CaseService:
    """Geschaeftslogik fuer Faelle (ADR-0053 3.3)."""

    __test__: ClassVar[bool] = False

    def __init__(self, repo: CaseRepository) -> None:
        self._repo = repo

    # --- Sichtbarkeit ------------------------------------------------------

    @staticmethod
    def _has_triage(ctx: WorkspaceContext) -> bool:
        return ctx.tool_policy is not None and ctx.tool_policy.allows(AgentCapability.case_triage)

    def _sees_all(self, ctx: WorkspaceContext) -> bool:
        """Alle Faelle: Mensch ab `editor`, Agent-Token mit `case_triage`."""
        if is_agent_bound(ctx):
            return self._has_triage(ctx)
        return role_satisfies(ctx.role, WorkspaceRole.editor)

    def _can_read(self, ctx: WorkspaceContext, case: CaseRead) -> bool:
        if self._sees_all(ctx):
            return True
        if is_agent_bound(ctx):
            return ctx.agent_id is not None and case.agent_id == ctx.agent_id
        return case.reporter_user_id == ctx.user_id

    async def _get_readable(self, ctx: WorkspaceContext, case_id: UUID) -> CaseRead:
        case = await self._repo.get_case(ctx.workspace_id, case_id)
        if case is None or not self._can_read(ctx, case):
            raise _case_not_found()
        return case

    def _scope(
        self, ctx: WorkspaceContext, agent_id: UUID | None
    ) -> tuple[UUID | None, UUID | None]:
        """Filter `(agent_id, reporter_user_id)` fuer Liste und Zaehler."""
        if self._sees_all(ctx):
            return agent_id, None
        if is_agent_bound(ctx):
            # Ein ausdruecklich anderer Agent ist eine Rechtefrage, kein
            # leeres Ergebnis (Muster `TestCaseService.list_cases`).
            if agent_id is not None and agent_id != ctx.agent_id:
                require_capability(ctx, AgentCapability.case_triage)
            return ctx.agent_id, None
        return agent_id, ctx.user_id

    # --- Melden ------------------------------------------------------------

    async def report_case(self, ctx: WorkspaceContext, data: CaseCreate) -> CaseRead:
        """`POST /cases`: ab `viewer` bzw. mit `feedback_write` (F2 = a)."""
        if is_agent_bound(ctx):
            require_capability(ctx, AgentCapability.feedback_write)
        else:
            require_role(ctx, WorkspaceRole.viewer)
        if not await self._repo.agent_exists(ctx.workspace_id, data.agent_id):
            raise _agent_not_found()
        if is_agent_bound(ctx):
            require_write_rate(ctx)
            # Builder = Agent mit `case_triage` (3.3 Rechte, 3.8 „im Builder-Seed an“).
            kind = CaseReporterKind.builder if self._has_triage(ctx) else CaseReporterKind.agent
            return await self._repo.create_case(
                ctx.workspace_id,
                data,
                reporter_kind=kind,
                reporter_user_id=None,
                reporter_agent_id=ctx.agent_id,
            )
        return await self._repo.create_case(
            ctx.workspace_id,
            data,
            reporter_kind=CaseReporterKind.human,
            reporter_user_id=ctx.user_id,
            reporter_agent_id=None,
        )

    # --- Lesen -------------------------------------------------------------

    async def list_cases(
        self,
        ctx: WorkspaceContext,
        *,
        agent_id: UUID | None = None,
        status_filter: CaseStatus | None = None,
        target: CaseTarget | None = None,
        limit: int = 50,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> list[CaseRead]:
        scoped_agent, reporter_user_id = self._scope(ctx, agent_id)
        return await self._repo.list_cases(
            ctx.workspace_id,
            agent_id=scoped_agent,
            status=status_filter,
            target=target,
            reporter_user_id=reporter_user_id,
            limit=limit,
            cursor=cursor,
        )

    async def count_by_status(
        self, ctx: WorkspaceContext, *, agent_id: UUID | None = None
    ) -> dict[CaseStatus, int]:
        scoped_agent, reporter_user_id = self._scope(ctx, agent_id)
        return await self._repo.count_by_status(
            ctx.workspace_id, agent_id=scoped_agent, reporter_user_id=reporter_user_id
        )

    async def get_case(self, ctx: WorkspaceContext, case_id: UUID) -> CaseDetail:
        await self._get_readable(ctx, case_id)
        detail = await self._repo.get_detail(ctx.workspace_id, case_id)
        if detail is None:  # zwischen den Lesezugriffen geloescht
            raise _case_not_found()
        return detail

    # --- Uebergaenge -------------------------------------------------------

    def _require_triage_right(self, ctx: WorkspaceContext) -> None:
        if is_agent_bound(ctx):
            # `require_capability` ist ohne Policy ein No-Op. Ein agent-gebundener
            # Token ohne geladene Policy (Race mit Agent-Delete, siehe
            # `is_agent_bound`) darf deshalb ausdruecklich nicht triagieren.
            if ctx.tool_policy is None:
                raise _triage_without_policy()
            require_capability(ctx, AgentCapability.case_triage)
        else:
            require_role(ctx, WorkspaceRole.editor)

    async def transition(
        self, ctx: WorkspaceContext, case_id: UUID, req: CaseTransitionRequest
    ) -> CaseRead:
        """`POST /cases/{id}/transition` nach 3.3.

        Reihenfolge: lesbar (404) -> kein Agent als Richter (403, vor jeder
        Kantenpruefung, damit die Regel nicht vom Status abhaengt) -> Rolle
        bzw. Capability (403) -> Kante und Phase E (409) -> Pflichtfelder.
        """
        case = await self._get_readable(ctx, case_id)
        to = req.to
        if is_agent_bound(ctx) and to in _HUMAN_ONLY_TARGETS:
            raise _human_only(to)
        self._require_triage_right(ctx)
        current = case.status

        if to in _PHASE_E_TARGETS or req.measure_id is not None:
            # D2 ohne Massnahmen (PM-Entscheidung): `in_progress` und
            # `verified` haengen an einer Massnahme bzw. deren Nachschau —
            # beides kommt mit Phase E (E2/E3).
            raise _transition_forbidden(
                current,
                to,
                "Dieser Statuswechsel braucht eine Massnahme; Massnahmen kommen mit Phase E.",
                requires="phase_e",
            )
        if to not in _EDGES[current]:
            raise _transition_forbidden(
                current, to, f"Von '{current.value}' fuehrt kein Weg nach '{to.value}'."
            )
        if to in _NOTE_REQUIRED and req.note is None:
            raise _transition_forbidden(
                current, to, "Dieser Statuswechsel braucht eine Begruendung.", missing="note"
            )
        if to is CaseStatus.addressed:
            if req.version_entity_type is None or req.version_id is None:
                raise _transition_forbidden(
                    current,
                    to,
                    "'addressed' braucht die Version, die den Fall behebt.",
                    missing="version",
                )
            if not await self._repo.version_exists(
                ctx.workspace_id, req.version_entity_type, req.version_id
            ):
                raise _version_not_found()
        elif req.version_id is not None:
            raise _transition_forbidden(
                current, to, "Eine Version gehoert nur zu 'addressed'.", unexpected="version"
            )

        actor_kind, actor_id = _actor(ctx)
        event = await self._repo.append_transition(
            ctx.workspace_id,
            case_id,
            CaseEventCreate(
                event=CaseEventKind(to.value),
                note=req.note,
                version_entity_type=req.version_entity_type,
                version_id=req.version_id,
            ),
            expected_status=current,
            # Pflicht nach 3.3: Zuordnung zu >= 1 Element oder `model_limit`.
            # Unter der Fall-Sperre geprueft, nicht vorab (Check-then-act).
            require_element=to is CaseStatus.triaged,
            actor_kind=actor_kind,
            actor_id=actor_id,
        )
        if event is None:
            raise await self._stale_transition(ctx, case_id, current, to)
        updated = await self._repo.get_case(ctx.workspace_id, case_id)
        if updated is None:
            raise _case_not_found()
        return updated

    async def _stale_transition(
        self, ctx: WorkspaceContext, case_id: UUID, expected: CaseStatus, to: CaseStatus
    ) -> ApiError:
        """Fehler, wenn `append_transition` nicht geschrieben hat: was galt nicht mehr?"""
        case = await self._repo.get_case(ctx.workspace_id, case_id)
        if case is None:
            return _case_not_found()
        if case.status is not expected:
            return _transition_forbidden(
                case.status, to, "Der Fall hat inzwischen einen anderen Status."
            )
        return _transition_forbidden(
            case.status,
            to,
            "'triaged' braucht mindestens eine Zuordnung (ein Element oder 'model_limit').",
            missing="element",
        )

    # --- Zuordnung ---------------------------------------------------------

    async def set_elements(
        self, ctx: WorkspaceContext, case_id: UUID, elements: Sequence[CaseElementInput]
    ) -> list[CaseElementRead]:
        """`PUT /cases/{id}/elements` (Replace): `editor` bzw. `case_triage`."""
        await self._get_readable(ctx, case_id)
        self._require_triage_right(ctx)
        for element in dict.fromkeys(elements):
            if element.entity_id is None:
                continue
            if not await self._repo.element_exists(
                ctx.workspace_id, element.target, element.entity_id
            ):
                reason, detail = _ELEMENT_NOT_FOUND[element.target]
                raise ApiError(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=detail,
                    reason=reason,
                    params={"target": element.target.value},
                )
        if is_agent_bound(ctx):
            require_write_rate(ctx)
        actor_kind, actor_id = _actor(ctx)
        result = await self._repo.set_elements(
            ctx.workspace_id,
            case_id,
            elements,
            assigned_by_kind=CaseAssignedByKind(actor_kind.value),
            assigned_by=actor_id,
        )
        if result is None:
            raise _case_not_found()
        return result

    # --- Schilderung -------------------------------------------------------

    async def add_statement(
        self, ctx: WorkspaceContext, case_id: UUID, data: CaseStatementCreate
    ) -> CaseStatementRead:
        """`POST /cases/{id}/statement`: nur der betroffene Agent, append-only."""
        case = await self._get_readable(ctx, case_id)
        if not is_agent_bound(ctx) or ctx.agent_id is None or ctx.agent_id != case.agent_id:
            raise _statement_not_subject()
        require_write_rate(ctx)
        statement = await self._repo.add_statement(ctx.workspace_id, case_id, ctx.agent_id, data)
        if statement is None:
            raise _case_not_found()
        return statement

    # --- Umwandeln / Uebernehmen (D2c) -----------------------------------

    @staticmethod
    def _require_human_editor(ctx: WorkspaceContext, action: str) -> None:
        """convert/promote: Mensch ab `editor`; Agent-Tokens nie (Muster `_require_human`).

        Ueber `is_agent_bound`, bewusst KEINE Capability: aus einem
        Lernvorschlag oder Alt-Feedback einen Fall zu machen, ist Kuration —
        ein Agent wuerde sonst ueber die Einordnung seines eigenen Verhaltens
        entscheiden („Partei, nicht Richter“).
        """
        if is_agent_bound(ctx):
            raise ApiGateError(
                status=status.HTTP_403_FORBIDDEN,
                reason="missing_capability",
                actionable_by="none",
                detail=f"{action} ist Menschen ab der Rolle 'editor' vorbehalten.",
            )
        require_role(ctx, WorkspaceRole.editor)

    async def convert_lesson(
        self,
        ctx: WorkspaceContext,
        agent_id: UUID,
        memory_id: UUID,
        data: CaseConvertRequest,
    ) -> CaseRead:
        """`POST /agents/{agent_id}/memories/{id}/convert` (6.4): `lesson` -> Fall.

        Nur `lesson` mit `status='pending'`. Eine spaetere Wiederholung
        derselben Lektion trifft den `converted`-Eintrag und laesst ihn
        `converted` (3.1.6, `merge_lesson`); ein zweites convert endet mit
        `memory_not_convertible`.
        """
        self._require_human_editor(ctx, "Einen Lernvorschlag in einen Fall umwandeln")
        if not await self._repo.agent_exists(ctx.workspace_id, agent_id):
            raise _agent_not_found()
        result = await self._repo.convert_lesson(
            ctx.workspace_id, agent_id, memory_id, data, actor_id=ctx.user_id
        )
        if result is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory nicht gefunden.",
                reason="memory_not_found",
            )
        if isinstance(result, NotConvertible):
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nur ein offener Lernvorschlag (lesson, pending) wird ein Fall.",
                reason="memory_not_convertible",
                params={"kind": result.kind.value, "status": result.status.value},
            )
        return result

    async def promote_feedback(
        self, ctx: WorkspaceContext, feedback_id: UUID, data: CaseCreate
    ) -> CaseRead:
        """`POST /feedback/{feedback_id}/promote` (6.5, 5.2): Alt-Feedback -> Fall.

        Einzeln durch einen Menschen (Owner F1 = a, kein Massen-Umbau). Nur
        offenes Feedback; das Alt-Feedback bekommt `addressed` mit Verweis.
        Ein Alt-Feedback betrifft ein Element, nicht zwingend einen Agenten —
        den Agenten des Falls nennt deshalb der Mensch (`data.agent_id`).
        """
        self._require_human_editor(ctx, "Ein Feedback in einen Fall uebernehmen")
        if not await self._repo.agent_exists(ctx.workspace_id, data.agent_id):
            raise _agent_not_found()
        result = await self._repo.promote_feedback(
            ctx.workspace_id, feedback_id, data, actor_id=ctx.user_id
        )
        if result is None:
            # Gleicher Grund wie `FeedbackService` fuer ein unbekanntes Feedback.
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Element nicht gefunden.",
                reason="feedback_element_not_found",
            )
        if isinstance(result, NotPromotable):
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nur ein offenes Feedback (noch nicht triagiert) wird ein Fall.",
                reason="feedback_not_promotable",
                params={"resolution": result.resolution},
            )
        return result

    # --- Loeschen ----------------------------------------------------------

    async def delete_case(self, ctx: WorkspaceContext, case_id: UUID) -> None:
        """Hard-Delete samt Verlauf (Q6), Logik aus D1b (`delete_case` im Repository)."""
        if is_agent_bound(ctx):
            raise _delete_forbidden_for_agents()
        require_role(ctx, WorkspaceRole.editor)
        if not await self._repo.delete_case(ctx.workspace_id, case_id, ctx.user_id):
            raise _case_not_found()
