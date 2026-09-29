"""Lernschleifen-REST-Aufrufe des MCP-Servers (ADR-0053 6.2, Paket B3).

Freie Funktionen nach dem Muster von `clients/kb.py` (Architektur-
Entscheidung 3.2): paket-internes Friend-Modul des `ApiClient`, nutzt dessen
`_get`/`_write` und damit dieselbe Fehler-Uebersetzung in `ToolError`
(`problem_message`: `detail` + `reason`).

Pfade: Router `test_cases.py` unter `/v1/workspaces/{ws_id}`.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from who2be_mcp.client import ApiClient
from who2be_models import EntityType, TestCaseRead, TestRunCreate, TestRunRead


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
