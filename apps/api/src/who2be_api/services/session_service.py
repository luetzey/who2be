"""Gespraechsprotokolle: einreichen und lesen (ADR-0053 3.5, 3.6, 6.6; Paket E2b-1).

Nur die Service-Schicht — Router (`POST/GET /feedback-sessions`) und MCP
(`submit_session_protocol`) folgen in eigenen Paketen. Der Lebenszyklus einer
Massnahme (link-draft, follow-up, review, withdraw) ist E2b-2.

Rechte (6.6, Tabelle; Muster `case_service.require_triage_right`):

- **Einreichen:** Mensch ab `editor`; Agent-Token mit `case_triage` (der
  Builder, Weiche E4 = a). Ein agent-gebundener Token ohne geladene Policy
  darf nicht.
- **Lesen** je ID und je Agent: dieselbe Pruefung. 6.6 nennt fuer das Lesen
  nur `editor`; die Karte E2b-1 erweitert es auf Agenten mit `case_triage`,
  weil der Builder ein eingereichtes Protokoll korrigieren koennen muss
  (neues Protokoll mit `supersedes_id`). Was der Aufrufer nicht lesen darf,
  gibt es fuer ihn nicht (`session_not_found`, QE3 = a).

Pruefungen vor dem Schreiben, in DERSELBEN Transaktion wie das Schreiben:

- Der besprochene Agent gehoert zum Workspace (`agent_not_found`).
- Alle Faelle des Protokolls gehoeren zum Workspace und zu diesem Agenten,
  und die Faelle jeder Massnahme sind eine Teilmenge davon
  (`session_cases_invalid`, 422). Nicht leer haelt schon `MeasureCreate`.
- Der Pruefall jeder Massnahme existiert im Workspace und gehoert zu diesem
  Agenten (`measure_test_case_required`, 422; der Composite-FK der Migration
  0103 verlangt denselben Agenten).
- `supersedes_id` verweist auf ein Protokoll desselben Agenten
  (`session_not_found`, `params.field = "supersedes_id"`).

Faelle auf `in_progress` (Weiche W-E2 = a): In derselben Transaktion gehen
alle Faelle, die in einer Massnahme stehen, auf `in_progress`; das Event
traegt die `measure_id` der ersten Massnahme des Protokolls, die den Fall
enthaelt. Die Kanten folgen 3.3: `triaged -> in_progress` direkt; `open` und
`reopened` nur ueber `triaged`, das eine Zuordnung verlangt — mit Zuordnung
entstehen beide Events, ohne bleibt der Fall. Wer einreichen darf, darf nach
3.3 beides setzen (`-> triaged` und `-> in_progress`: „Mensch `editor`;
Builder mit `case_triage`“). Faelle in jedem anderen Status bleiben, wie sie
sind; das Ergebnis nennt sie mit ihrem Status (`cases_unchanged`).
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from fastapi import status
from pydantic import BaseModel, JsonValue

from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext, is_agent_bound, require_write_rate
from who2be_api.repositories.session_repository import SessionRepository
from who2be_api.services.case_service import require_triage_right
from who2be_models import (
    CaseActorKind,
    CaseStatus,
    SessionCreate,
    SessionDetail,
    SessionRead,
    SessionSubmitterKind,
)


class CaseUnchanged(BaseModel):
    """Ein Fall einer Massnahme, der nicht auf `in_progress` ging, mit seinem Status."""

    case_id: UUID
    status: CaseStatus


class SessionSubmitResult(BaseModel):
    """Ergebnis des Einreichens: das Protokoll und was mit den Faellen geschah (W-E2 = a)."""

    detail: SessionDetail
    cases_started: list[UUID]
    cases_unchanged: list[CaseUnchanged]


def _agent_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Agent nicht gefunden.",
        reason="agent_not_found",
    )


def _session_not_found(field: str | None = None) -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Protokoll nicht gefunden.",
        reason="session_not_found",
        params={"field": field} if field is not None else None,
    )


def _cases_invalid(case_ids: list[UUID], measure_index: int | None = None) -> ApiError:
    params: dict[str, JsonValue] = {"case_ids": [str(c) for c in case_ids]}
    if measure_index is None:
        detail = "Das Protokoll nennt Faelle, die es fuer diesen Agenten nicht gibt."
    else:
        params["measure_index"] = measure_index
        detail = "Eine Massnahme nennt Faelle, die nicht im Protokoll stehen."
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail,
        reason="session_cases_invalid",
        params=params,
    )


def _test_case_required(measure_index: int) -> ApiError:
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=(
            "Eine Massnahme braucht einen Pruefall dieses Agenten. Lege ihn zuerst aus dem Fall an."
        ),
        reason="measure_test_case_required",
        params={"measure_index": measure_index},
    )


def _submitter(ctx: WorkspaceContext) -> tuple[SessionSubmitterKind, CaseActorKind, UUID]:
    """Einreicher und Akteur der Fall-Events aus dem Aufrufweg."""
    if is_agent_bound(ctx) and ctx.agent_id is not None:
        return SessionSubmitterKind.agent, CaseActorKind.agent, ctx.agent_id
    return SessionSubmitterKind.human, CaseActorKind.human, ctx.user_id


class SessionService:
    """Geschaeftslogik fuer Gespraechsprotokolle (ADR-0053 3.5, 3.6)."""

    __test__: ClassVar[bool] = False

    def __init__(self, repo: SessionRepository) -> None:
        self._repo = repo

    # --- Einreichen ----------------------------------------------------------

    async def submit_protocol(
        self, ctx: WorkspaceContext, data: SessionCreate
    ) -> SessionSubmitResult:
        """`POST /feedback-sessions` (6.6): Protokoll + Faelle + Massnahmen, eine Transaktion.

        Reihenfolge: Recht (403) -> Schreibrate des Agenten (429, wie
        `report_case`) -> Verweise (404/422) -> Schreiben -> Faelle auf
        `in_progress`. Jeder Fehler nach dem Oeffnen der Transaktion rollt
        alles zurueck.
        """
        require_triage_right(ctx)
        if is_agent_bound(ctx):
            require_write_rate(ctx)
        submitted_kind, actor_kind, actor_id = _submitter(ctx)
        workspace_id = ctx.workspace_id

        async with self._repo.begin() as conn:
            refs = await self._repo.submit_refs(
                conn,
                workspace_id,
                data.agent_id,
                case_ids=data.case_ids,
                test_case_ids=[m.test_case_id for m in data.measures],
                supersedes_id=data.supersedes_id,
            )
            if not refs.agent_exists:
                raise _agent_not_found()
            unknown = [c for c in data.case_ids if c not in refs.case_ids]
            if unknown:
                raise _cases_invalid(unknown)
            session_cases = set(data.case_ids)
            for index, measure in enumerate(data.measures):
                outside = [c for c in measure.case_ids if c not in session_cases]
                if outside:
                    raise _cases_invalid(outside, index)
                if measure.test_case_id not in refs.test_case_ids:
                    raise _test_case_required(index)
            if not refs.supersedes_ok:
                raise _session_not_found("supersedes_id")

            detail = await self._repo.insert_session(
                conn,
                workspace_id,
                data,
                submitted_by_kind=submitted_kind,
                submitted_by=actor_id,
            )
            # Je Fall die erste Massnahme des Protokolls, die ihn enthaelt.
            first_measure: dict[UUID, UUID] = {}
            for created in detail.measures:
                for case_id in created.case_ids:
                    first_measure.setdefault(case_id, created.id)
            starts = await self._repo.start_cases(
                conn,
                workspace_id,
                list(first_measure.items()),
                actor_kind=actor_kind,
                actor_id=actor_id,
            )
        return SessionSubmitResult(
            detail=detail,
            cases_started=[s.case_id for s in starts if s.started],
            cases_unchanged=[
                CaseUnchanged(case_id=s.case_id, status=s.status_before)
                for s in starts
                if not s.started
            ],
        )

    # --- Lesen ---------------------------------------------------------------

    async def get_session(self, ctx: WorkspaceContext, session_id: UUID) -> SessionDetail:
        """`GET /feedback-sessions/{id}`: Protokoll mit Massnahmen (QE1 = a)."""
        require_triage_right(ctx)
        detail = await self._repo.get_session(ctx.workspace_id, session_id)
        if detail is None:
            raise _session_not_found()
        return detail

    async def list_sessions(
        self,
        ctx: WorkspaceContext,
        *,
        agent_id: UUID | None = None,
        case_id: UUID | None = None,
        limit: int = 50,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> list[SessionRead]:
        """`GET /feedback-sessions?agent_id&case_id` (6.6, QE1/QE2): neueste zuerst."""
        require_triage_right(ctx)
        return await self._repo.list_sessions(
            ctx.workspace_id, agent_id=agent_id, case_id=case_id, limit=limit, cursor=cursor
        )
