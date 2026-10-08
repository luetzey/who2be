"""Pruefaelle, Prueflaeufe und Pruefbericht (ADR-0053 3.2, 3.2.1, 6.2; Paket B2).

Drei Aufgaben:

1. **Pruefaelle** anlegen, lesen, zurueckziehen — mit den Rechten aus ADR 3.2
   (Tabelle „Rechte"). Menschen brauchen `editor`; agent-gebundene Tokens
   lesen den eigenen Agenten, mit `case_triage` alle, legen nur mit
   `case_triage` an und ziehen nie zurueck.
2. **Ergebnisse melden** (`POST /test-runs`). `attestation` setzt der Server
   aus dem Aufrufweg (`attestation_for`), nie aus dem Body:
   agent-gebundener Token -> `client_self_report`, Web-Session eines
   Menschen -> `human_rating` mit `reported_by_user_id`. Die n/n-Regel prueft
   `verdict_consistent` vorab und antwortet mit 422
   `test_run_verdict_inconsistent` statt mit einem DB-Fehler.
3. **Pruefbericht** einer Elementversion nach 3.2.1 (Weiche P4, Option (a)):
   `build_test_report` ist die EINE Funktion, die Bericht (6.2) und
   Aktivierung (6.3, Paket B5a) gemeinsam nutzen. Sie prueft keine Rechte —
   das tun ihre Aufrufer (`get_test_report` hier, die Transition in
   `version_status`).

Rechte-Zuschnitt fuer Agenten: Die ADR nennt fuer Agent-Tokens eine
Capability statt einer Rolle. Agent-Pfade pruefen deshalb die Capability
(`case_triage`, `test_report`) und die Sichtbarkeit, nicht die Rolle; der
Rollen-Snapshot eines Agent-Tokens ist ohnehin auf `editor` gedeckelt.
"""

from __future__ import annotations

from typing import ClassVar, Literal
from uuid import UUID

from fastapi import status
from pydantic import BaseModel, ConfigDict, Field

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    is_agent_bound,
    require_capability,
    require_role,
    require_write_rate,
)
from who2be_api.repositories.test_case_repository import TestCaseRepository
from who2be_models import (
    AgentCapability,
    EntityType,
    ProblemReason,
    TestAttestation,
    TestCaseCreate,
    TestCaseCreatedByKind,
    TestCaseRead,
    TestCaseStatus,
    TestRunCreate,
    TestRunRead,
    TestVerdict,
    WorkspaceRole,
    verdict_consistent,
)

# Obergrenze Ergebnisse je Meldung — eine Charge wird atomar geschrieben.
TEST_RUN_BATCH_MAX = 200

# Weg, ueber den ein Pruefall zur Menge gehoert, wenn er direkt am Element
# haengt und sein Agent das Element nicht (auch) ueber eine Verknuepfung
# erreicht.
VIA_DIRECT = "direct"

TestReportState = Literal["pass", "fail", "error", "missing"]
TestReportScopeNote = Literal["no_reference_index"]

_STATE_BY_VERDICT: dict[TestVerdict, TestReportState] = {
    TestVerdict.pass_: "pass",
    TestVerdict.fail: "fail",
    TestVerdict.error: "error",
}


class TestCaseCreateRequest(TestCaseCreate):
    """`POST /test-cases`: ein neuer Pruefall, optional als Korrektur.

    `supersedes_id` macht aus dem Anlegen eine Korrektur (ADR 3.2): neuer
    Pruefall mit Verweis auf den alten plus `retired` am alten, beides in
    einer Transaktion. Weil das den alten zurueckzieht, verlangt es dieselben
    Rechte wie `retire` (Mensch mit `editor`).
    """

    __test__: ClassVar[bool] = False
    model_config = ConfigDict(extra="forbid")

    supersedes_id: UUID | None = None


class TestRunSubmit(BaseModel):
    """`POST /test-runs`: eine Ergebnis-Charge fuer eine Elementversion.

    Kein `attestation`-Feld und `extra="forbid"`: ein mitgeschicktes
    `attestation` wird mit 422 abgewiesen statt still verworfen.
    """

    __test__: ClassVar[bool] = False
    model_config = ConfigDict(extra="forbid")

    subject_entity_type: EntityType
    subject_version_id: UUID
    results: list[TestRunCreate] = Field(min_length=1, max_length=TEST_RUN_BATCH_MAX)
    model_provider: str | None = Field(default=None, max_length=100)
    model_name: str | None = Field(default=None, max_length=200)


class TestReportEntry(BaseModel):
    """Ein Pruefall im Bericht mit seinem letzten Ergebnis fuer die Version."""

    __test__: ClassVar[bool] = False

    test_case: TestCaseRead
    # True, wenn der Pruefall direkt am Element haengt (Teil 1 der Regel).
    direct: bool
    state: TestReportState
    result: TestRunRead | None


class TestReportAgentGroup(BaseModel):
    """Alle Pruefaelle eines Agenten, mit den Wegen, ueber die er betroffen ist.

    `via` nennt die Verknuepfungswege aus 3.2.1 (`persona`,
    `system_prompt_template`, `persona_playbook`, `playbook_composite`,
    `resource_link`, `resource_composite`) und zusaetzlich `direct`, wenn in
    der Gruppe ein direkt gebundener Pruefall steht. Ein betroffener Agent
    ohne Pruefall erscheint mit leerer `entries`-Liste — die Luecke soll
    sichtbar sein.
    """

    __test__: ClassVar[bool] = False

    agent_id: UUID
    agent_name: str
    via: list[str]
    entries: list[TestReportEntry]


class TestReportCounts(BaseModel):
    __test__: ClassVar[bool] = False

    total: int
    passed: int
    failed: int
    error: int
    missing: int


class TestReport(BaseModel):
    """Pruefbericht einer Elementversion (ADR 6.2, Menge nach 3.2.1)."""

    __test__: ClassVar[bool] = False

    entity_type: EntityType
    entity_id: UUID
    version_id: UUID
    # Zahl der Agenten, die das Element HEUTE ueber eine Verknuepfung
    # erreichen — die Breite der Aenderung, unabhaengig von Pruefaellen.
    affected_agent_count: int
    scope_note: TestReportScopeNote | None
    counts: TestReportCounts
    agents: list[TestReportAgentGroup]


_ENTITY_NOT_FOUND: dict[str, tuple[ProblemReason, str]] = {
    "persona": ("persona_not_found", "Persona nicht gefunden."),
    "playbook": ("playbook_not_found", "Playbook nicht gefunden."),
    "resource": ("resource_not_found", "Resource nicht gefunden."),
    "external_tool": ("external_tool_not_found", "Externes Tool nicht gefunden."),
    "system_prompt_template": (
        "system_prompt_template_not_found",
        "System-Prompt-Template nicht gefunden.",
    ),
}


def _case_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Pruefall nicht gefunden.",
        reason="test_case_not_found",
    )


def _case_retired(case_id: UUID) -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail="Der Pruefall ist zurueckgezogen; dafuer werden keine Ergebnisse mehr angenommen.",
        reason="test_case_retired",
        params={"test_case_id": str(case_id)},
    )


def _version_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Die gepruefte Version gehoert nicht zu diesem Workspace.",
        reason="test_subject_version_not_found",
    )


def _agent_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Agent nicht gefunden.",
        reason="agent_not_found",
    )


def _entity_not_found(entity_type: EntityType) -> ApiError:
    reason, detail = _ENTITY_NOT_FOUND[entity_type]
    return ApiError(status_code=status.HTTP_404_NOT_FOUND, detail=detail, reason=reason)


def _verdict_inconsistent(index: int, result: TestRunCreate) -> ApiError:
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=(
            "Laufzahlen und Urteil passen nicht zusammen: runs_total >= 1, "
            "0 <= runs_passed <= runs_total, und 'pass' nur bei runs_passed = runs_total."
        ),
        reason="test_run_verdict_inconsistent",
        params={
            "index": index,
            "test_case_id": str(result.test_case_id),
            "runs_total": result.runs_total,
            "runs_passed": result.runs_passed,
            "verdict": result.verdict.value,
        },
    )


def _retire_forbidden_for_agents() -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="missing_capability",
        actionable_by="none",
        detail=(
            "Pruefaelle zurueckziehen oder korrigieren ist Menschen vorbehalten — "
            "ein Agent kann Pruefaelle nur anlegen (mit case_triage)."
        ),
    )


def attestation_for(ctx: WorkspaceContext) -> tuple[TestAttestation, UUID | None, UUID | None]:
    """Herkunft eines Ergebnisses aus dem Aufrufweg (ADR 3.2, 6.2).

    Rueckgabe `(attestation, reported_by_agent_id, reported_by_user_id)`.
    Nur eine Web-Session eines Menschen (kein API-Token) ist `human_rating`;
    jeder Token-Aufruf ist Selbstauskunft des Clients. Der Request-Body hat
    darauf keinen Einfluss.
    """
    if ctx.is_api_token or is_agent_bound(ctx):
        return TestAttestation.client_self_report, ctx.agent_id, None
    return TestAttestation.human_rating, None, ctx.user_id


class TestCaseService:
    """Geschaeftslogik fuer Pruefaelle, Prueflaeufe und den Pruefbericht."""

    __test__: ClassVar[bool] = False

    def __init__(self, repo: TestCaseRepository) -> None:
        self._repo = repo

    # --- Sichtbarkeit ------------------------------------------------------

    def _require_reader(self, ctx: WorkspaceContext) -> None:
        """Menschen brauchen `editor`; Agenten sehen mindestens sich selbst."""
        if not is_agent_bound(ctx):
            require_role(ctx, WorkspaceRole.editor)

    def _sees_all_agents(self, ctx: WorkspaceContext) -> bool:
        if not is_agent_bound(ctx):
            return True
        return ctx.tool_policy is not None and ctx.tool_policy.allows(AgentCapability.case_triage)

    def _can_read(self, ctx: WorkspaceContext, case: TestCaseRead) -> bool:
        return self._sees_all_agents(ctx) or case.agent_id == ctx.agent_id

    async def _get_readable(self, ctx: WorkspaceContext, case_id: UUID) -> TestCaseRead:
        case = await self._repo.get_case(ctx.workspace_id, case_id)
        # Nicht lesbar = nicht vorhanden (kein Enumerieren fremder Pruefaelle).
        if case is None or not self._can_read(ctx, case):
            raise _case_not_found()
        return case

    # --- Pruefaelle --------------------------------------------------------

    async def list_cases(
        self,
        ctx: WorkspaceContext,
        *,
        agent_id: UUID | None,
        entity_type: EntityType | None,
        entity_id: UUID | None,
        status_filter: TestCaseStatus | None,
        origin_case_id: UUID | None,
    ) -> list[TestCaseRead]:
        self._require_reader(ctx)
        if not self._sees_all_agents(ctx):
            # Ohne case_triage: nur der eigene Agent. Ein ausdruecklich
            # anderer Agent ist eine Rechtefrage, kein leeres Ergebnis.
            if agent_id is not None and agent_id != ctx.agent_id:
                require_capability(ctx, AgentCapability.case_triage)
            agent_id = ctx.agent_id
        return await self._repo.list_cases(
            ctx.workspace_id,
            agent_id=agent_id,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status_filter,
            origin_case_id=origin_case_id,
        )

    async def get_case(self, ctx: WorkspaceContext, case_id: UUID) -> TestCaseRead:
        self._require_reader(ctx)
        return await self._get_readable(ctx, case_id)

    async def create_case(self, ctx: WorkspaceContext, data: TestCaseCreateRequest) -> TestCaseRead:
        if is_agent_bound(ctx):
            require_capability(ctx, AgentCapability.case_triage)
            if data.supersedes_id is not None:
                raise _retire_forbidden_for_agents()
            require_write_rate(ctx)
        else:
            require_role(ctx, WorkspaceRole.editor)
        if not await self._repo.agent_exists(ctx.workspace_id, data.agent_id):
            raise _agent_not_found()
        if data.entity_type is not None and data.entity_id is not None:
            if not await self._repo.entity_exists(
                ctx.workspace_id, data.entity_type, data.entity_id
            ):
                raise _entity_not_found(data.entity_type)
        kind, created_by = self._creator(ctx)
        payload = TestCaseCreate.model_validate(data.model_dump(exclude={"supersedes_id"}))
        if data.supersedes_id is None:
            return await self._repo.create_case(
                ctx.workspace_id, payload, created_by_kind=kind, created_by=created_by
            )
        old = await self._repo.get_case(ctx.workspace_id, data.supersedes_id)
        if old is None:
            raise _case_not_found()
        created = await self._repo.supersede_case(
            ctx.workspace_id,
            data.supersedes_id,
            payload,
            created_by_kind=kind,
            created_by=created_by,
        )
        if created is None:
            # Zwischen Lesen und Sperren zurueckgezogen (oder schon vorher).
            raise _case_retired(data.supersedes_id)
        return created

    async def retire_case(self, ctx: WorkspaceContext, case_id: UUID) -> TestCaseRead:
        if is_agent_bound(ctx):
            raise _retire_forbidden_for_agents()
        require_role(ctx, WorkspaceRole.editor)
        retired = await self._repo.retire_case(ctx.workspace_id, case_id)
        if retired is None:
            raise _case_not_found()
        return retired

    @staticmethod
    def _creator(ctx: WorkspaceContext) -> tuple[TestCaseCreatedByKind, UUID]:
        if is_agent_bound(ctx) and ctx.agent_id is not None:
            return TestCaseCreatedByKind.agent, ctx.agent_id
        return TestCaseCreatedByKind.human, ctx.user_id

    # --- Prueflaeufe -------------------------------------------------------

    async def submit_runs(self, ctx: WorkspaceContext, data: TestRunSubmit) -> list[TestRunRead]:
        if is_agent_bound(ctx):
            require_capability(ctx, AgentCapability.test_report)
        else:
            require_role(ctx, WorkspaceRole.editor)
        # Erst die billige Formpruefung, dann die DB — und die ganze Charge,
        # bevor irgendetwas geschrieben wird (alles oder nichts).
        for index, result in enumerate(data.results):
            if not verdict_consistent(result.runs_total, result.runs_passed, result.verdict):
                raise _verdict_inconsistent(index, result)
        if (
            await self._repo.version_entity_id(
                ctx.workspace_id, data.subject_entity_type, data.subject_version_id
            )
            is None
        ):
            raise _version_not_found()
        case_ids = list(dict.fromkeys(r.test_case_id for r in data.results))
        cases = {c.id: c for c in await self._repo.get_cases(ctx.workspace_id, case_ids)}
        for case_id in case_ids:
            case = cases.get(case_id)
            if case is None or not self._can_read(ctx, case):
                raise _case_not_found()
            if case.status is TestCaseStatus.retired:
                raise _case_retired(case_id)
        if is_agent_bound(ctx):
            require_write_rate(ctx)
        attestation, agent_id, user_id = attestation_for(ctx)
        return await self._repo.insert_runs(
            ctx.workspace_id,
            data.subject_entity_type,
            data.subject_version_id,
            data.results,
            attestation=attestation,
            reported_by_agent_id=agent_id,
            reported_by_user_id=user_id,
            model_provider=data.model_provider,
            model_name=data.model_name,
        )

    # --- Pruefbericht ------------------------------------------------------

    async def get_test_report(
        self, ctx: WorkspaceContext, entity_type: EntityType, version_id: UUID
    ) -> TestReport:
        """`GET /versions/{entity_type}/{version_id}/test-report`.

        Menschen brauchen `editor` (ADR 6.2). Ein agent-gebundener Token
        braucht zusaetzlich `case_triage`: der Bericht zeigt Pruefaelle ALLER
        betroffenen Agenten, und das Lesen fremder Pruefaelle ist nach ADR 3.2
        an genau diese Capability gebunden.
        """
        require_role(ctx, WorkspaceRole.editor)
        if is_agent_bound(ctx):
            require_capability(ctx, AgentCapability.case_triage)
        entity_id = await self._repo.version_entity_id(ctx.workspace_id, entity_type, version_id)
        if entity_id is None:
            raise _version_not_found()
        return await self.build_test_report(ctx.workspace_id, entity_type, entity_id, version_id)

    async def build_test_report(
        self,
        workspace_id: UUID,
        entity_type: EntityType,
        entity_id: UUID,
        version_id: UUID,
    ) -> TestReport:
        """Pruefall-Menge nach ADR 3.2.1 mit letztem Ergebnis je Pruefall.

        Die EINE Aufloesung fuer Bericht (6.2) und Aktivierung (6.3): die
        Vereinigung aus (1) aktiven Pruefaellen direkt am Element und (2)
        aktiven Pruefaellen aller Agenten, die das Element heute erreichen.
        Prueft KEINE Rechte und nicht, ob `version_id` zu `entity_id`
        gehoert — beides ist Sache des Aufrufers.
        """
        affected = await self._repo.affected_agents(workspace_id, entity_type, entity_id)
        cases = await self._repo.list_active_for_element(
            workspace_id, entity_type, entity_id, [a.agent_id for a in affected]
        )
        latest = await self._repo.latest_runs_for_version(
            workspace_id, version_id, [c.id for c in cases]
        )

        groups: dict[UUID, TestReportAgentGroup] = {
            a.agent_id: TestReportAgentGroup(
                agent_id=a.agent_id, agent_name=a.agent_name, via=list(a.via), entries=[]
            )
            for a in affected
        }
        # Direkt gebundene Pruefaelle an Agenten, die das Element nicht ueber
        # eine Verknuepfung erreichen, bekommen eine eigene Gruppe.
        missing_names = [c.agent_id for c in cases if c.agent_id not in groups]
        names = await self._repo.agent_names(workspace_id, missing_names) if missing_names else {}

        counts: dict[TestReportState, int] = {"pass": 0, "fail": 0, "error": 0, "missing": 0}
        for case in cases:
            group = groups.get(case.agent_id)
            if group is None:
                group = TestReportAgentGroup(
                    agent_id=case.agent_id,
                    agent_name=names.get(case.agent_id, ""),
                    via=[],
                    entries=[],
                )
                groups[case.agent_id] = group
            direct = case.entity_type == entity_type and case.entity_id == entity_id
            if direct and VIA_DIRECT not in group.via:
                group.via.append(VIA_DIRECT)
            result = latest.get(case.id)
            state: TestReportState = (
                _STATE_BY_VERDICT[result.verdict] if result is not None else "missing"
            )
            counts[state] += 1
            group.entries.append(
                TestReportEntry(test_case=case, direct=direct, state=state, result=result)
            )

        ordered = sorted(groups.values(), key=lambda g: (g.agent_name, str(g.agent_id)))
        for group in ordered:
            group.via.sort()
        return TestReport(
            entity_type=entity_type,
            entity_id=entity_id,
            version_id=version_id,
            affected_agent_count=len(affected),
            scope_note="no_reference_index" if entity_type == "external_tool" else None,
            counts=TestReportCounts(
                total=len(cases),
                passed=counts["pass"],
                failed=counts["fail"],
                error=counts["error"],
                missing=counts["missing"],
            ),
            agents=ordered,
        )
