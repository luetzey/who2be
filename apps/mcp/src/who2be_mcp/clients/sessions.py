"""REST-Aufrufe der Gespraechs-Werkzeuge (ADR-0053 6.6, Paket E-MCP-1).

Freie Funktionen nach dem Muster von `clients/learning.py`: paket-internes
Friend-Modul des `ApiClient`, nutzt `_get`/`_write` und damit dieselbe
Fehler-Uebersetzung in `ToolError` (`detail` + `reason`).

Pfade: Router `apps/api/src/who2be_api/routers/sessions.py` unter
`/v1/workspaces/{ws_id}`.

Die Antwortmodelle von `POST /feedback-sessions` und
`GET /measures/{id}/follow-up` leben nur in der API (`session_service`,
`measure_service`). Der MCP-Prozess importiert `who2be_api` nicht (ADR-0005),
darum stehen hier Spiegel. Dass sie gleich bleiben, prueft
`apps/api/tests/test_rest_mcp_parity.py` (Schema-Vergleich).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from who2be_mcp.client import ApiClient
from who2be_models import CaseStatus, EntityType, MeasureEventRead, MeasureState, SessionCreate
from who2be_models.session import Dossier, SessionDetail


class CaseUnchanged(BaseModel):
    """Ein Fall einer Massnahme, der nicht auf `in_progress` ging, mit seinem Status."""

    case_id: UUID
    status: CaseStatus


class SessionSubmitResult(BaseModel):
    """Ergebnis des Einreichens: das Protokoll und was mit den Faellen geschah."""

    detail: SessionDetail
    cases_started: list[UUID]
    cases_unchanged: list[CaseUnchanged]


class RunRate(BaseModel):
    """Juengster Pruefall-Lauf einer Version."""

    runs_total: int
    runs_passed: int
    verdict: str
    attestation: str
    created_at: datetime


class VersionReport(BaseModel):
    """Rohzahlen einer Version: Pruefall-Lauf, Nutzungen, Faelle."""

    version_id: UUID | None
    version: int
    test_run: RunRate | None
    uses: int
    cases: int | None


class FollowUpReport(BaseModel):
    """Kennzahlen der Nachschau als Rohzahlen; die Einstufung macht ein Mensch."""

    model_config = ConfigDict(extra="forbid")

    measure_id: UUID
    state: MeasureState
    follow_up_at: date
    due: bool
    reviewable: bool
    before: VersionReport | None
    after: VersionReport | None
    recurrence: int | None
    min_uses: int
    insufficient: bool


class MeasureLinkDraftBody(BaseModel):
    """Body von `POST /measures/{id}/link-draft` (Spiegel von `MeasureLinkDraftRequest`)."""

    model_config = ConfigDict(extra="forbid")

    version_entity_type: EntityType
    version_id: UUID


async def get_dossier(client: ApiClient, agent_id: UUID, cursor: str | None = None) -> Dossier:
    """`GET .../agents/{id}/dossier?cursor=` — `cursor` blaettert nur `generations`."""
    params = {"cursor": cursor} if cursor is not None else None
    payload = await client._get(f"{client._workspace_prefix}/agents/{agent_id}/dossier", params)
    return Dossier.model_validate(payload)


async def submit_session_protocol(client: ApiClient, data: SessionCreate) -> SessionSubmitResult:
    """`POST .../feedback-sessions` — Protokoll, Faelle und Massnahmen in einer Transaktion.

    Den Einreicher setzt der Server aus dem Token. Faelle mit Massnahme gehen
    in derselben Transaktion auf `in_progress` (W-E2 = a).
    """
    payload = await client._write("POST", f"{client._workspace_prefix}/feedback-sessions", data)
    return SessionSubmitResult.model_validate(payload)


async def link_measure_draft(
    client: ApiClient, measure_id: UUID, data: MeasureLinkDraftBody
) -> MeasureEventRead:
    """`POST .../measures/{id}/link-draft` — Event `draft_linked` (Weiche E2 = a)."""
    payload = await client._write(
        "POST", f"{client._workspace_prefix}/measures/{measure_id}/link-draft", data
    )
    return MeasureEventRead.model_validate(payload)


async def get_follow_up(client: ApiClient, measure_id: UUID) -> FollowUpReport:
    """`GET .../measures/{id}/follow-up` — fuer einen Agenten entsteht ggf. `follow_up_prepared`."""
    payload = await client._get(f"{client._workspace_prefix}/measures/{measure_id}/follow-up")
    return FollowUpReport.model_validate(payload)
