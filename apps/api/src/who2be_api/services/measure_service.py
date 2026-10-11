"""Lebenszyklus einer Massnahme: link-draft, follow-up, review, withdraw (ADR-0053 3.6, 6.6; E2b-2).

Nur die Service-Schicht — Router (`/measures/{id}/...`) und MCP
(`link_measure_draft`, `get_follow_up`) folgen in eigenen Paketen.

Rechte (6.6, Tabelle):

- **link-draft, follow-up:** Mensch ab `editor`; Agent-Token mit
  `case_triage` (Muster `case_service.require_triage_right`).
- **review, withdraw:** nur Mensch ab `editor`. Ein agent-gebundener Token
  bekommt immer 403, auch mit `case_triage` — geprueft ueber
  `is_agent_bound` VOR jeder Rollenpruefung (Weiche E4 = a: der Builder
  entscheidet nie). Die DB haelt dasselbe per CHECK
  `measure_event_human_only_check`.

Event-Folge (QE4 a, Owner/PM 2026-10-09):

- **link-draft** in `agreed` und `draft_linked`, beliebig oft; der juengste
  Eintrag gilt (`measures_for_version`). Ab `activated` 409.
- **review** genau einmal und erst nach `activated` (`activated` oder
  `follow_up_prepared`). Ausnahme QE6 a: Ziele ohne Versionen (`tool_policy`,
  `memory`) duerfen ab dem Nachschau-Datum auch ohne `activated` eingestuft
  werden. `not_measurable` schliesst ab. Fallstatus-Folgen (E3, 3.6):
  effective -> verified, ineffective -> reopened, je aus `addressed`.
- **withdraw** in jedem offenen Zustand.
- Nach `reviewed` oder `withdrawn` nur noch Lesen.

Falsche Folge: 409 `measure_transition_forbidden` mit `params.state` und
`params.action` (QE3 a). Jede Pruefung laeuft unter einer Sperre je
Massnahme in derselben Transaktion wie das Schreiben — „genau einmal“ haelt
auch bei zwei gleichzeitigen Aufrufen.

Zurueckziehen (QE5 a, Owner 2026-10-09): In derselben Transaktion gehen die
Faelle der Massnahme von `in_progress` auf `triaged` zurueck, sofern keine
andere offene Massnahme sie enthaelt. Akteur ist das System, das Event
traegt die `measure_id` und die Begruendung.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import ClassVar
from uuid import UUID

from fastapi import status
from pydantic import BaseModel, ConfigDict

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    is_agent_bound,
    require_role,
    require_write_rate,
)
from who2be_api.repositories.case_repository import apply_system_status
from who2be_api.repositories.session_repository import (
    FollowUpFigures,
    SessionRepository,
    VersionFigures,
    measure_target_versioned,
)
from who2be_api.services.case_service import require_triage_right
from who2be_models import (
    MEASURE_CLOSED_STATES,
    CaseEventKind,
    CaseStatus,
    EntityType,
    MeasureActorKind,
    MeasureEventCreate,
    MeasureEventKind,
    MeasureEventRead,
    MeasureRead,
    MeasureState,
    MeasureVerdict,
    WorkspaceRole,
)

# Mindestnutzung der neuen Version fuer einen Vergleich (QE8 a: der Server
# liefert die Schwelle, die UI kodiert keine). Gesetzte Annahme: die einzige
# Zahl der Spec S9d („nach weiteren 50 Nutzungen“).
FOLLOW_UP_MIN_USES = 50

# Zustaende, in denen ein Entwurf (neu) verknuepft werden darf (QE4 a).
_LINKABLE: frozenset[MeasureState] = frozenset({MeasureState.agreed, MeasureState.draft_linked})
# Zustaende nach `activated` — hier ist eine versionierte Massnahme einstufbar.
_ACTIVE: frozenset[MeasureState] = frozenset(
    {MeasureState.activated, MeasureState.follow_up_prepared}
)
# Fallstatus-Folge einer Einstufung (3.6, E3); `not_measurable` hat keine.
_REVIEW_CASE_EVENT: dict[MeasureVerdict, CaseEventKind] = {
    MeasureVerdict.effective: CaseEventKind.verified,
    MeasureVerdict.ineffective: CaseEventKind.reopened,
}


class RunRate(BaseModel):
    """Juengster Pruefall-Lauf einer Version (3.2: „Es zaehlt das letzte Ergebnis“)."""

    runs_total: int
    runs_passed: int
    verdict: str
    attestation: str
    created_at: datetime


class VersionReport(BaseModel):
    """Rohzahlen einer Version: Pruefall-Lauf, Nutzungen, Faelle (QE8 a, keine Raten)."""

    version_id: UUID | None
    version: int
    test_run: RunRate | None
    uses: int
    # None: fuer diese Version gibt es (noch) kein Zeitfenster (vor `activated`).
    cases: int | None


class FollowUpReport(BaseModel):
    """`GET /measures/{id}/follow-up` (6.6): drei Kennzahlen als Rohzahlen (QE8 a)."""

    model_config = ConfigDict(extra="forbid")

    measure_id: UUID
    state: MeasureState
    follow_up_at: date
    due: bool
    # Darf jetzt eingestuft werden (QE4 a / QE6 a)?
    reviewable: bool
    before: VersionReport | None
    after: VersionReport | None
    # Neue Faelle des Agenten am selben Element nach der Aktivierung (bzw. bei
    # Zielen ohne Versionen nach Anlage der Massnahme); None = noch nicht messbar.
    recurrence: int | None
    min_uses: int
    insufficient: bool


def _measure_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Massnahme nicht gefunden.",
        reason="measure_not_found",
    )


def _version_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Die Version gehoert nicht zum Element dieser Massnahme.",
        reason="test_subject_version_not_found",
    )


def _transition_forbidden(state: MeasureState, action: str, detail: str) -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
        reason="measure_transition_forbidden",
        params={"state": state.value, "action": action},
    )


def _human_only(action: str) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="missing_capability",
        actionable_by="none",
        detail=(
            f"'{action}' ist Menschen ab der Rolle 'editor' vorbehalten. Ein Agent "
            "entscheidet nicht ueber Massnahmen — das laesst sich nicht freischalten."
        ),
    )


def require_human_editor(ctx: WorkspaceContext, action: str) -> None:
    """review/withdraw: Agent-Token immer 403 (vor jeder Capability), sonst Rolle `editor`."""
    if is_agent_bound(ctx):
        raise _human_only(action)
    require_role(ctx, WorkspaceRole.editor)


def _actor(ctx: WorkspaceContext) -> tuple[MeasureActorKind, UUID]:
    if is_agent_bound(ctx) and ctx.agent_id is not None:
        return MeasureActorKind.agent, ctx.agent_id
    return MeasureActorKind.human, ctx.user_id


def is_reviewable(measure: MeasureRead, due_at: date, today: date) -> bool:
    """QE4 a: nach `activated`, genau einmal; QE6 a: ohne Versionen ab Faelligkeit."""
    if measure.state in MEASURE_CLOSED_STATES:
        return False
    if measure_target_versioned(measure.target):
        return measure.state in _ACTIVE
    return today >= due_at


def _version_report(figures: VersionFigures | None) -> VersionReport | None:
    if figures is None:
        return None
    run = figures.run
    return VersionReport(
        version_id=figures.version_id,
        version=figures.version,
        test_run=(
            RunRate(
                runs_total=run.runs_total,
                runs_passed=run.runs_passed,
                verdict=run.verdict,
                attestation=run.attestation,
                created_at=run.created_at,
            )
            if run is not None
            else None
        ),
        uses=figures.uses,
        cases=figures.cases,
    )


def _insufficient(measure: MeasureRead, figures: FollowUpFigures) -> bool:
    """Kein Vergleich moeglich: ohne Versionen nur ohne Wiederauftreten-Zahl, sonst
    ohne beide Seiten oder unter der Mindestnutzung der neuen Version."""
    if not measure_target_versioned(measure.target):
        return figures.recurrence is None
    if figures.before is None or figures.after is None:
        return True
    return figures.after.uses < FOLLOW_UP_MIN_USES


def _metrics(report: FollowUpReport) -> dict[str, object]:
    """Schnappschuss fuer `follow_up_prepared.metrics` (ohne Zustandsfelder)."""
    return report.model_dump(
        mode="json", include={"before", "after", "recurrence", "min_uses", "insufficient"}
    )


def _today_utc() -> date:
    """Heutiges Datum fuer die Faelligkeit (Muster `inbox_service`)."""
    return datetime.now(UTC).date()


class MeasureService:
    """Geschaeftslogik fuer den Verlauf einer Massnahme (ADR-0053 3.6)."""

    __test__: ClassVar[bool] = False

    def __init__(self, repo: SessionRepository, *, today: Callable[[], date] = _today_utc) -> None:
        self._repo = repo
        self._today = today

    # --- Entwurf verknuepfen ---------------------------------------------------

    async def link_draft(
        self,
        ctx: WorkspaceContext,
        measure_id: UUID,
        version_entity_type: EntityType,
        version_id: UUID,
    ) -> MeasureEventRead:
        """`POST /measures/{id}/link-draft` (6.6): Event `draft_linked` (Weiche E2 = a).

        Die Version muss zum Ziel-Element der Massnahme gehoeren (gleiche Art,
        gleiche `entity_id`), sonst `test_subject_version_not_found`. Die
        Versions-Tabellen bleiben unberuehrt.
        """
        require_triage_right(ctx)
        if is_agent_bound(ctx):
            require_write_rate(ctx)
        actor_kind, actor_id = _actor(ctx)
        ref = await self._repo.version_ref(ctx.workspace_id, version_entity_type, version_id)
        async with self._repo.begin() as conn:
            locked = await self._repo.lock_measure(conn, ctx.workspace_id, measure_id)
            if locked is None:
                raise _measure_not_found()
            measure, _ = locked
            if (
                ref is None
                or measure.target.value != version_entity_type
                or measure.entity_id != ref[0]
            ):
                raise _version_not_found()
            if measure.state not in _LINKABLE:
                raise _transition_forbidden(
                    measure.state,
                    "link_draft",
                    "Ein Entwurf laesst sich nur verknuepfen, bis die Version aktiv ist.",
                )
            event = await self._repo.append_measure_event(
                ctx.workspace_id,
                measure_id,
                MeasureEventCreate(
                    event=MeasureEventKind.draft_linked,
                    version_entity_type=version_entity_type,
                    version_id=version_id,
                ),
                actor_kind=actor_kind,
                actor_id=actor_id,
                conn=conn,
            )
        assert event is not None
        return event

    # --- Nachschau -------------------------------------------------------------

    async def follow_up(self, ctx: WorkspaceContext, measure_id: UUID) -> FollowUpReport:
        """`GET /measures/{id}/follow-up` (6.6): Kennzahlen als Rohzahlen (QE8 a).

        Ruft ein Agent auf (der Builder bereitet die Nachschau vor, 3.6) und ist
        die Massnahme einstufbar, entsteht ein `follow_up_prepared` mit den
        Kennzahlen — aber nur, wenn sie sich seit dem letzten Schnappschuss
        geaendert haben. Ein Mensch liest nur.
        """
        require_triage_right(ctx)
        today = self._today()
        report, measure = await self._report(ctx, measure_id, today)
        if not (is_agent_bound(ctx) and report.reviewable):
            return report
        metrics = _metrics(report)
        last = next(
            (e for e in reversed(measure.events) if e.event is MeasureEventKind.follow_up_prepared),
            None,
        )
        if last is not None and last.metrics == metrics:
            return report
        require_write_rate(ctx)
        actor_kind, actor_id = _actor(ctx)
        async with self._repo.begin() as conn:
            locked = await self._repo.lock_measure(conn, ctx.workspace_id, measure_id)
            if locked is None:
                raise _measure_not_found()
            current, due_at = locked
            # Zwischen Lesen und Sperre eingestuft/zurueckgezogen: nur lesen.
            if not is_reviewable(current, due_at, today):
                return report
            await self._repo.append_measure_event(
                ctx.workspace_id,
                measure_id,
                MeasureEventCreate(event=MeasureEventKind.follow_up_prepared, metrics=metrics),
                actor_kind=actor_kind,
                actor_id=actor_id,
                conn=conn,
            )
        return report.model_copy(update={"state": MeasureState.follow_up_prepared})

    async def _report(
        self, ctx: WorkspaceContext, measure_id: UUID, today: date
    ) -> tuple[FollowUpReport, MeasureRead]:
        """Massnahme samt Nachschau-Datum lesen (kurze Sperre: konsistenter Stand) und rechnen."""
        async with self._repo.begin() as conn:
            locked = await self._repo.lock_measure(conn, ctx.workspace_id, measure_id)
        if locked is None:
            raise _measure_not_found()
        measure, due_at = locked
        figures = await self._repo.follow_up_figures(ctx.workspace_id, measure)
        report = FollowUpReport(
            measure_id=measure.id,
            state=measure.state,
            follow_up_at=due_at,
            due=today >= due_at,
            reviewable=is_reviewable(measure, due_at, today),
            before=_version_report(figures.before),
            after=_version_report(figures.after),
            recurrence=figures.recurrence,
            min_uses=FOLLOW_UP_MIN_USES,
            insufficient=_insufficient(measure, figures),
        )
        return report, measure

    # --- Einstufen und Zurueckziehen -------------------------------------------

    async def review(
        self,
        ctx: WorkspaceContext,
        measure_id: UUID,
        verdict: MeasureVerdict,
        note: str | None = None,
    ) -> MeasureEventRead:
        """`POST /measures/{id}/review` (6.6): Event `reviewed`, nur Mensch ab `editor`.

        `ineffective` verlangt eine Begruendung (`MeasureEventCreate`, CHECK
        `measure_event_reason_check`). Fallstatus-Folgen (3.6, E3) in derselben
        Transaktion, Akteur System mit `measure_id`: `effective` setzt die
        Faelle von `addressed` auf `verified`, `ineffective` auf `reopened`
        (Begruendung = `note`), `not_measurable` aendert nichts. Nur ueber die
        Kanten aus 3.3 — ein Fall ausserhalb von `addressed` bleibt.
        """
        require_human_editor(ctx, "review")
        today = self._today()
        data = MeasureEventCreate(event=MeasureEventKind.reviewed, verdict=verdict, note=note)
        async with self._repo.begin() as conn:
            locked = await self._repo.lock_measure(conn, ctx.workspace_id, measure_id)
            if locked is None:
                raise _measure_not_found()
            measure, due_at = locked
            if not is_reviewable(measure, due_at, today):
                raise _transition_forbidden(
                    measure.state,
                    "review",
                    "Eingestuft wird genau einmal und erst, wenn die verknuepfte Version aktiv "
                    "ist (bei Zielen ohne Versionen ab dem Nachschau-Datum).",
                )
            event = await self._repo.append_measure_event(
                ctx.workspace_id,
                measure_id,
                data,
                actor_kind=MeasureActorKind.human,
                actor_id=ctx.user_id,
                conn=conn,
            )
            follow = _REVIEW_CASE_EVENT.get(verdict)
            if follow is not None:
                await apply_system_status(
                    conn,
                    ctx.workspace_id,
                    measure.case_ids,
                    event=follow,
                    sources=(CaseStatus.addressed,),
                    measure_id=measure_id,
                    note=note if follow is CaseEventKind.reopened else None,
                )
        assert event is not None
        return event

    async def withdraw(
        self,
        ctx: WorkspaceContext,
        measure_id: UUID,
        note: str,
    ) -> tuple[MeasureEventRead, list[UUID]]:
        """`POST /measures/{id}/withdraw` (6.6): Event `withdrawn` + QE5 a.

        Ergebnis: das Event und die Faelle, die auf `triaged` zurueckgingen.
        """
        require_human_editor(ctx, "withdraw")
        data = MeasureEventCreate(event=MeasureEventKind.withdrawn, note=note)
        async with self._repo.begin() as conn:
            locked = await self._repo.lock_measure(conn, ctx.workspace_id, measure_id)
            if locked is None:
                raise _measure_not_found()
            measure, _ = locked
            if measure.state in MEASURE_CLOSED_STATES:
                raise _transition_forbidden(
                    measure.state,
                    "withdraw",
                    "Die Massnahme ist abgeschlossen und laesst sich nicht mehr zurueckziehen.",
                )
            event = await self._repo.append_measure_event(
                ctx.workspace_id,
                measure_id,
                data,
                actor_kind=MeasureActorKind.human,
                actor_id=ctx.user_id,
                conn=conn,
            )
            reset = await self._repo.reset_cases_after_withdraw(
                conn, ctx.workspace_id, measure_id, measure.case_ids, note=note
            )
        assert event is not None
        return event, reset
