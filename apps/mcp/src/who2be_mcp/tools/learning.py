"""Lernschleifen-MCP-Tools (ADR-0053 6.2, Paket B3): Prueffaelle lesen, Ergebnisse melden.

Muster wie `tools/kb.py`: modulweite `@with_tool_log`-async-Funktionen (fuer
Tests direkt aufrufbar), `register(mcp)` haengt sie an die FastMCP-Instanz,
`build_client` wird zur Laufzeit ueber `server` aufgeloest.

Rechte setzt allein die API durch (ADR-0039): `list_test_cases` mit fremdem
`agent_id` braucht `case_triage`, `submit_test_results` braucht
`test_report`. `attestation` ist kein Parameter — der Server setzt sie aus
dem Aufrufweg, ueber MCP (Agent-Token) immer `client_self_report`.
"""

from __future__ import annotations

from uuid import UUID

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from who2be_mcp.client import ApiClient
from who2be_mcp.clients import learning as learning_api
from who2be_mcp.clients.learning import TestRunBatch
from who2be_mcp.core_logging import with_tool_log
from who2be_models import EntityType, TestCaseRead, TestRunCreate, TestRunRead

# Zusatz zur Server-Meldung, damit der Agent weiss, wie er korrigiert.
_VERDICT_HINT = (
    " Korrigieren: 'pass' nur, wenn ALLE Laeufe bestanden (runs_passed = "
    "runs_total); sonst 'fail' melden, human_rule-Faelle als 'error'."
)


async def _client() -> ApiClient:
    """API-Client ueber `server.build_client` (Import im Aufruf, zyklusfrei)."""
    from who2be_mcp import server

    return await server.build_client()


def _parse_uuid(value: str, label: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ToolError(f"Ungueltige {label}-UUID: '{value}'.") from exc


@with_tool_log("list_test_cases")
async def list_test_cases(
    agent_id: str | None = None,
    entity_type: EntityType | None = None,
    entity_id: str | None = None,
) -> list[TestCaseRead]:
    """Listet Prueffaelle (Eingabe + erwartetes Verhalten + check_kind).

    Ohne `agent_id` bekommst du die Prueffaelle deines EIGENEN Agenten. Einen
    anderen Agenten per `agent_id` darfst du nur mit der Capability
    `case_triage` abfragen — sonst lehnt der Server ab (missing_capability).
    `entity_type`/`entity_id` filtern auf direkt an ein Element gebundene
    Faelle.
    """
    parsed_agent = None if agent_id is None else _parse_uuid(agent_id, "Agent")
    parsed_entity = None if entity_id is None else _parse_uuid(entity_id, "Element")
    client = await _client()
    return await learning_api.list_test_cases(
        client, agent_id=parsed_agent, entity_type=entity_type, entity_id=parsed_entity
    )


@with_tool_log("submit_test_results")
async def submit_test_results(
    subject_entity_type: EntityType,
    subject_version_id: str,
    results: list[TestRunCreate],
    model_provider: str | None = None,
    model_name: str | None = None,
) -> list[TestRunRead]:
    """Meldet Prueffall-Ergebnisse fuer EINE Elementversion (Selbstauskunft).

    Je Ergebnis: `test_case_id`, `runs_total` (>= 1), `runs_passed`,
    `verdict` (pass|fail|error), `output_excerpt`. `verdict='pass'` NUR bei
    runs_passed = runs_total, sonst 422 test_run_verdict_inconsistent.
    `human_rule`-Faelle bewertest du NICHT: nur Ausgabe in `output_excerpt`
    und `verdict='error'` — die Bewertung macht ein Mensch im Web. Der
    Server speichert alles als `client_self_report`; ein Herkunftsfeld gibt
    es nicht. Die Charge gilt ganz oder gar nicht. Braucht `test_report`.
    Nennt `model_provider`/`model_name`, womit du geprueft hast.
    """
    try:
        data = TestRunBatch(
            subject_entity_type=subject_entity_type,
            subject_version_id=_parse_uuid(subject_version_id, "Version"),
            results=results,
            model_provider=model_provider,
            model_name=model_name,
        )
    except ValidationError as exc:
        errors = exc.errors()
        msg = str(errors[0]["msg"]) if errors else "Ungueltige Eingabe."
        raise ToolError(f"Ungueltige Eingabe: {msg}") from exc
    client = await _client()
    try:
        return await learning_api.submit_test_results(client, data)
    except ToolError as exc:
        if "reason=test_run_verdict_inconsistent" in str(exc):
            raise ToolError(f"{exc}{_VERDICT_HINT}") from exc
        raise


def register(mcp: FastMCP) -> None:
    """Registriert die Lernschleifen-Tools (`output_schema=None`, Payload-Budget)."""
    for fn in (list_test_cases, submit_test_results):
        mcp.tool(output_schema=None)(fn)
