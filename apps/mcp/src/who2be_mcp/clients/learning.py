"""Lernschleifen-REST-Aufrufe des MCP-Servers (ADR-0053 6.2, Paket B3).

Freie Funktionen nach dem Muster von `clients/kb.py` (Architektur-
Entscheidung 3.2): paket-internes Friend-Modul des `ApiClient`, nutzt dessen
`_get`/`_write` und damit dieselbe Fehler-Uebersetzung in `ToolError`
(`problem_message`: `detail` + `reason`).

Pfade: Router `test_cases.py`, `memory.py` und `cases.py` unter
`/v1/workspaces/{ws_id}`.
"""

from __future__ import annotations

from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from who2be_mcp.client import ApiClient
from who2be_models import (
    CaseCreate,
    CaseDetail,
    CaseElementInput,
    CaseElementRead,
    CaseRead,
    CaseStatementCreate,
    CaseStatementRead,
    CaseStatus,
    EntityType,
    MemoryRead,
    TestCaseCreate,
    TestCaseRead,
    TestRunCreate,
    TestRunRead,
)
from who2be_models.case import CASE_NOTE_MAX_LENGTH, CaseConvertRequest
from who2be_models.memory import MemoryProposalCreate, MemoryProposalRead
from who2be_models.pattern import PatternList


class TestRunBatch(BaseModel):
    """Body von `POST /test-runs` aus Sicht des MCP-Clients.

    Spiegelt `TestRunSubmit` der API — bewusst OHNE `attestation`: die setzt
    der Server aus dem Aufrufweg (Agent-Token -> `client_self_report`).
    `extra="forbid"` wie auf der API-Seite, damit auch hier nichts
    unbemerkt mitreist. Die n/n-Regel prueft der Server (422
    `test_run_verdict_inconsistent`), nicht dieses Modell.
    """

    __test__: ClassVar[bool] = False
    model_config = ConfigDict(extra="forbid")

    subject_entity_type: EntityType
    subject_version_id: UUID
    results: list[TestRunCreate] = Field(min_length=1)
    model_provider: str | None = None
    model_name: str | None = None


async def list_test_cases(
    client: ApiClient,
    agent_id: UUID | None = None,
    entity_type: EntityType | None = None,
    entity_id: UUID | None = None,
) -> list[TestCaseRead]:
    """`GET .../test-cases?agent_id=&entity_type=&entity_id=`.

    Ohne `agent_id` begrenzt der Server einen Agenten ohne `case_triage` auf
    sich selbst; ein fremder `agent_id` ohne `case_triage` endet in 403
    `missing_capability` (als `ToolError` durchgereicht).
    """
    params: dict[str, str] = {}
    if agent_id is not None:
        params["agent_id"] = str(agent_id)
    if entity_type is not None:
        params["entity_type"] = entity_type
    if entity_id is not None:
        params["entity_id"] = str(entity_id)
    payload = await client._get(f"{client._workspace_prefix}/test-cases", params=params or None)
    return [TestCaseRead.model_validate(item) for item in payload]


async def submit_test_results(client: ApiClient, data: TestRunBatch) -> list[TestRunRead]:
    """`POST .../test-runs` — eine Ergebnis-Charge, alles oder nichts."""
    payload = await client._write("POST", f"{client._workspace_prefix}/test-runs", data)
    return [TestRunRead.model_validate(item) for item in payload]


async def propose_memory_change(
    client: ApiClient, data: MemoryProposalCreate
) -> MemoryProposalRead:
    """`POST .../agent-memory-proposals` (ADR-0053 3.1.4) — immer `pending`.

    Fremde oder nicht abrufbare Eintraege beantwortet der Server mit 404
    `memory_not_found` (als `ToolError` durchgereicht), ohne zu verraten, ob
    es sie gibt.
    """
    payload = await client._write(
        "POST", f"{client._workspace_prefix}/agent-memory-proposals", data
    )
    return MemoryProposalRead.model_validate(payload)


# --- Faelle (ADR-0053 6.5, D4) ---------------------------------------------------


class CaseElementsBody(BaseModel):
    """Body von `PUT /cases/{id}/elements` aus Sicht des MCP-Clients.

    Spiegelt `CaseElementsReplace` des Routers (Replace-Semantik). Die
    Obergrenze je Aufruf prueft der Server, nicht dieses Modell — eine zweite
    Kopie der Zahl wuerde nur auseinanderlaufen.
    """

    model_config = ConfigDict(extra="forbid")

    elements: list[CaseElementInput]


async def report_case(client: ApiClient, data: CaseCreate) -> CaseRead:
    """`POST .../cases` — Melder setzt der Server aus dem Token."""
    payload = await client._write("POST", f"{client._workspace_prefix}/cases", data)
    return CaseRead.model_validate(payload)


async def submit_case_statement(
    client: ApiClient, case_id: UUID, data: CaseStatementCreate
) -> CaseStatementRead:
    """`POST .../cases/{id}/statement` — nur der betroffene Agent (sonst 403)."""
    payload = await client._write(
        "POST", f"{client._workspace_prefix}/cases/{case_id}/statement", data
    )
    return CaseStatementRead.model_validate(payload)


class CasePage(BaseModel):
    """Eine Seite von `GET /cases`; `next_cursor` ist `None` auf der letzten.

    Die API traegt den Cursor im Header `X-Next-Cursor` (Repo-Konvention der
    Keyset-Listen); das Werkzeug reicht ihn im Body weiter, wie `MemoryPage`.
    """

    items: list[CaseRead]
    next_cursor: str | None = None


async def list_cases(
    client: ApiClient,
    agent_id: UUID | None = None,
    status: CaseStatus | list[CaseStatus] | None = None,
    cursor: str | None = None,
) -> CasePage:
    """`GET .../cases?agent_id=&status=&cursor=` — eine Seite, neueste zuerst.

    `status` geht als wiederholter Query-Parameter raus
    (`?status=open&status=reopened`), wie `GET /cases` ihn seit D6-API1 liest;
    ein Einzelwert bleibt ein einzelner Parameter, eine leere Liste filtert
    nicht. Die Sichtbarkeit entscheidet der Server: ohne `case_triage` nur
    Faelle ueber den eigenen Agenten, ein fremder `agent_id` endet in 403
    `missing_capability`. Ein kaputter `cursor` endet in 422 der API.
    """
    params: dict[str, str | list[str]] = {}
    if agent_id is not None:
        params["agent_id"] = str(agent_id)
    statuses = [status] if isinstance(status, str) else (status or [])
    if statuses:
        # Reihenfolge erhalten, Dubletten raus — die API filtert per IN.
        params["status"] = list(dict.fromkeys(CaseStatus(s).value for s in statuses))
    if cursor is not None:
        params["cursor"] = cursor
    response = await client._request(
        "GET", f"{client._workspace_prefix}/cases", params=params or None
    )
    return CasePage(
        items=[CaseRead.model_validate(item) for item in response.json()],
        next_cursor=response.headers.get("X-Next-Cursor"),
    )


async def get_case(client: ApiClient, case_id: UUID) -> CaseDetail:
    """`GET .../cases/{id}` — Fall mit Verlauf, Zuordnungen und Schilderungen."""
    payload = await client._get(f"{client._workspace_prefix}/cases/{case_id}")
    return CaseDetail.model_validate(payload)


class CaseTriageBody(BaseModel):
    """Body von `POST /cases/{id}/transition` fuer `triage_case`.

    Teilmenge von `CaseTransitionRequest` der API: `to` ist fest `triaged`,
    alles andere (Massnahme, Version) gehoert zu anderen Zielen. Welche Kante
    erlaubt ist, entscheidet der Server (409 `case_transition_forbidden`).
    """

    model_config = ConfigDict(extra="forbid")

    to: Literal["triaged"] = "triaged"
    note: str | None = Field(default=None, min_length=1, max_length=CASE_NOTE_MAX_LENGTH)


async def triage_case(client: ApiClient, case_id: UUID, data: CaseTriageBody) -> CaseRead:
    """`POST .../cases/{id}/transition` mit `to=triaged`."""
    payload = await client._write(
        "POST", f"{client._workspace_prefix}/cases/{case_id}/transition", data
    )
    return CaseRead.model_validate(payload)


async def list_patterns(client: ApiClient, agent_id: UUID | None = None) -> PatternList:
    """`GET .../patterns?agent_id=` — Muster samt `threshold` und `window_days`."""
    params = {"agent_id": str(agent_id)} if agent_id is not None else None
    payload = await client._get(f"{client._workspace_prefix}/patterns", params=params)
    return PatternList.model_validate(payload)


async def create_test_case(client: ApiClient, data: TestCaseCreate) -> TestCaseRead:
    """`POST .../test-cases` — Urheber setzt der Server aus dem Token."""
    payload = await client._write("POST", f"{client._workspace_prefix}/test-cases", data)
    return TestCaseRead.model_validate(payload)


async def get_lesson(client: ApiClient, memory_id: UUID) -> MemoryRead:
    """`GET .../memories/{id}` — fuer Agent-Token nur `kind=lesson` (PM-4).

    Alles andere, auch das eigene Gedaechtnis, beantwortet der Server mit 404
    `memory_not_found` wie eine unbekannte ID.
    """
    payload = await client._get(f"{client._workspace_prefix}/memories/{memory_id}")
    return MemoryRead.model_validate(payload)


async def convert_lesson_to_case(
    client: ApiClient, agent_id: UUID, memory_id: UUID, data: CaseConvertRequest
) -> CaseRead:
    """`POST .../agents/{agent_id}/memories/{id}/convert` — Melder `pattern` (3.7)."""
    payload = await client._write(
        "POST",
        f"{client._workspace_prefix}/agents/{agent_id}/memories/{memory_id}/convert",
        data,
    )
    return CaseRead.model_validate(payload)


async def assign_case_elements(
    client: ApiClient, case_id: UUID, data: CaseElementsBody
) -> list[CaseElementRead]:
    """`PUT .../cases/{id}/elements` — ersetzt die Zuordnung vollstaendig."""
    payload = await client._write(
        "PUT", f"{client._workspace_prefix}/cases/{case_id}/elements", data
    )
    return [CaseElementRead.model_validate(item) for item in payload]
