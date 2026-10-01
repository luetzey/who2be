"""Mandantentrennung je MCP-Tool: jedes Tool als Agent von A mit IDs von B.

Gegenstueck zu `test_tenant_isolation_api.py` fuer die MCP-Oberflaeche
(ADR-0055 §7, Owner-Entscheidung 2026-09-30, Mandantentrennung = b). Die
Tools laufen ueber den In-Memory-FastMCP-Client gegen die echte App:
`server.build_client` liefert einen `ApiClient`, dessen Transport die App per
ASGI aufruft und jeden HTTP-Status mitschreibt. So prueft der Test nicht nur,
dass ein Tool mit fremden IDs scheitert, sondern auch, woran: an einer 403/404
der API.

**1. Inventar (ohne DB).** Jedes registrierte Tool steht in `MCP_PROBES` oder
in `MCP_EXEMPT` (mit Begruendung). Ein neues Tool ohne Eintrag ist rot, ein
Eintrag ohne Tool ebenfalls.

**2. Lauf (mit DB).** Zwei Mandanten A und B mit identischem Bestand
(`who2be_api.testing.tenant_pair`), jeder mit einem agent-gebundenen Token.

* **V2 fremde Objekt-ID** — Tool mit ID-Argument, als A-Agent, alle IDs von
  B. Erwartet: Tool-Fehler, und die letzte API-Antwort dahinter ist 403/404.
  Fuer Such- und Filter-Tools (`filters=True`) ist Erfolg erlaubt; dort zaehlen
  Leck-Check und Orakel-Vergleich.
* **V3 Scan** — Tool ohne ID-Argument, als A-Agent. Erwartet: kein Tool-Fehler.
* **Kein Leck** — in keinem Ergebnis an A steht ein Marker oder eine ID von B
  (ausser A hat sie selbst gesendet).
* **Kein Existenz-Orakel** — dieselbe V2-Probe mit Zufalls-IDs liefert
  dieselbe Folge von HTTP-Status wie mit B-IDs.
* **Schreibschutz** — Fingerabdruck von B vorher/nachher gleich.
* **Gegenprobe** — jede V2-Probe als B-Agent mit B-IDs kommt am Objekt-Lookup
  vorbei. Erst damit ist die 404 von A ein Befund an der Mandantengrenze.
* **Null geprueft ist rot** — Mindestzahlen je Variante.

V1 (fremder Workspace im Pfad) gibt es hier nicht: der Agent-Token ist an
seinen Workspace gebunden, und `build_client` setzt genau diesen. Den Fall
"Token von A, Pfad nach B" deckt V1 im REST-Test ab.
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from who2be_api.main import app
from who2be_api.testing.tenant_pair import (
    ANCHOR_DENIED,
    DENIED,
    TABLE_SCHEMA,
    Tenant,
    control_passes,
    fingerprint_async,
    ghost_of,
    isolation_stores,
    leaks,
    seed_tenant,
)
from who2be_api.testing.workspace_setup import cleanup_workspaces
from who2be_mcp import server
from who2be_mcp.client import ApiClient
from who2be_mcp.server import mcp

_REF = re.compile(r"<<([a-z0-9_]+)>>")
_BASE = "http://testserver"


@dataclass(frozen=True)
class ToolProbe:
    """Argument-Vorlage eines Tools; `<<key>>` wird je Mandant ersetzt.

    `filters`, `known`, `denied`: wie `Probe` im REST-Test.
    """

    args: dict[str, Any] = field(default_factory=dict)
    filters: bool = False
    known: str = ""
    denied: frozenset[int] = DENIED


_TEXT_FILE = base64.b64encode(b"Isolation probe text.").decode()
_PERSONA = {"description": "x", "system_prompt": "x", "content": {"blocks": []}}
_PLAYBOOK = {"description": "x", "body": "1. x", "type": "workflow"}
_RESOURCE = {"description": "x", "blocks": []}
_TOOL = {"display_name": "x", "mcp_server_name": "x", "tool_names": ["t"]}
_TEMPLATE = {"description": "", "body": "x"}
_WHEN = "2026-08-01T00:00:00Z"
_SOURCE_REF = "<<artifact_id>>#<<block_id>>"
_PB_REF = {"entity_type": "playbook", "entity_id": "<<playbook_id>>"}


def _version_tools(kind: str, id_key: str) -> dict[str, ToolProbe]:
    """restore_/transition_ fuer die versionierten Arten (gleiches Schema)."""
    return {
        f"restore_{kind}": ToolProbe({id_key: f"<<{id_key}>>", "version": 1}),
        f"transition_{kind}": ToolProbe({id_key: f"<<{id_key}>>", "version": 1, "to": "review"}),
    }


MCP_PROBES: dict[str, ToolProbe] = {
    # --- Lesen ------------------------------------------------------------
    "get_persona": ToolProbe({"identifier": "<<persona_id>>"}),
    "fetch_playbook": ToolProbe({"playbook_id": "<<playbook_id>>"}),
    "fetch_resource": ToolProbe({"resource_id": "<<resource_id>>"}),
    "list_resource_blocks": ToolProbe({"resource_id": "<<resource_id>>"}),
    "get_external_tool": ToolProbe({"identifier": "<<tool_id>>"}),
    "get_system_prompt": ToolProbe({"template_id": "<<template_id>>"}),
    "get_agent": ToolProbe({"agent_id": "<<agent_id>>"}),
    "fetch_agent": ToolProbe({"agent_id": "<<agent_id>>"}),
    "find_usages": ToolProbe(_PB_REF),
    "get_feedback": ToolProbe(_PB_REF),
    "list_versions": ToolProbe(_PB_REF),
    "get_version": ToolProbe({**_PB_REF, "version": 1}),
    "diff_versions": ToolProbe({**_PB_REF, "version": 1}),
    "list_test_cases": ToolProbe({"agent_id": "<<agent_id>>"}, filters=True),
    "list_agents": ToolProbe(),
    "list_playbooks": ToolProbe(),
    "list_resources": ToolProbe(),
    "list_external_tools": ToolProbe(),
    "list_system_prompts": ToolProbe(),
    "list_placeholders": ToolProbe(),
    "list_triggers": ToolProbe(),
    "list_memories": ToolProbe(),
    "whoami": ToolProbe(),
    "ping": ToolProbe(),
    "search": ToolProbe({"query": "<<marker>>"}, filters=True),
    "search_content": ToolProbe({"query": "<<marker>>"}, filters=True),
    "search_kb": ToolProbe({"query": "<<marker>>"}, filters=True),
    "search_memory": ToolProbe({"query": "<<marker>>"}, filters=True),
    "search_workarea": ToolProbe({"query": "<<marker>>"}, filters=True),
    # --- Schreiben: Bibliothek ---------------------------------------------
    "create_persona": ToolProbe({"data": {"name": "iso", "content": _PERSONA}}),
    "create_playbook": ToolProbe({"data": {"name": "iso", "content": _PLAYBOOK}}),
    "create_resource": ToolProbe({"data": {"name": "iso", "content": _RESOURCE}}),
    "create_external_tool": ToolProbe({"data": {"name": "iso", "content": _TOOL}}),
    "create_system_prompt": ToolProbe({"data": {"name": "iso", "content": _TEMPLATE}}),
    "update_persona": ToolProbe({"persona_id": "<<persona_id>>", "data": {"content": _PERSONA}}),
    "update_playbook": ToolProbe(
        {"playbook_id": "<<playbook_id>>", "data": {"content": _PLAYBOOK}}
    ),
    "update_resource": ToolProbe(
        {"resource_id": "<<resource_id>>", "data": {"content": _RESOURCE}}
    ),
    "update_external_tool": ToolProbe({"tool_id": "<<tool_id>>", "data": {"content": _TOOL}}),
    "update_system_prompt": ToolProbe(
        {"template_id": "<<template_id>>", "data": {"content": _TEMPLATE}}
    ),
    **_version_tools("persona", "persona_id"),
    **_version_tools("playbook", "playbook_id"),
    **_version_tools("resource", "resource_id"),
    **_version_tools("external_tool", "tool_id"),
    "restore_system_prompt": ToolProbe({"template_id": "<<template_id>>", "version": 1}),
    "transition_system_prompt": ToolProbe(
        {"template_id": "<<template_id>>", "version": 1, "data": {"to": "review"}}
    ),
    "set_persona_playbooks": ToolProbe(
        {"persona_id": "<<persona_id>>", "playbook_ids": ["<<playbook_id>>"]}
    ),
    "set_playbook_composes": ToolProbe(
        {"playbook_id": "<<playbook_id>>", "child_ids": ["<<child_playbook_id>>"]}
    ),
    "set_playbook_resource_links": ToolProbe(
        {
            "playbook_id": "<<playbook_id>>",
            "links": {
                "links": [
                    {"resource_id": "<<resource_id>>", "position": 0, "link_scope": "resource"}
                ]
            },
        }
    ),
    "set_resource_sub_resources": ToolProbe(
        {
            "resource_id": "<<resource_id>>",
            "links": {"links": [{"child_id": "<<child_resource_id>>"}]},
        }
    ),
    # --- Agenten -------------------------------------------------------------
    "create_agent": ToolProbe(
        {
            "data": {
                "name": "iso",
                "persona_id": "<<persona_id>>",
                "system_prompt_template_id": "<<template_id>>",
            }
        }
    ),
    "update_agent": ToolProbe(
        {"agent_id": "<<agent_id>>", "data": {"persona_id": "<<persona_id>>"}}
    ),
    "copy_agent": ToolProbe({"agent_id": "<<agent_id>>"}),
    # --- Lernen ----------------------------------------------------------------
    "record_usage": ToolProbe({"data": _PB_REF}),
    "submit_feedback": ToolProbe({"data": {**_PB_REF, "signal": "helpful"}}),
    "report_problem": ToolProbe({"data": {"category": "other", "note": "iso"}}),
    "resolve_feedback": ToolProbe({"feedback_id": "<<feedback_id>>", "resolution": "dismissed"}),
    "save_memory": ToolProbe({"fact": "Nutzer mag Gruen"}),
    "submit_test_results": ToolProbe(
        {
            "subject_entity_type": "persona",
            "subject_version_id": "<<version_id>>",
            "results": [
                {
                    "test_case_id": "<<case_id>>",
                    "runs_total": 1,
                    "runs_passed": 1,
                    "verdict": "pass",
                }
            ],
        }
    ),
    # --- Arbeitsbereich ----------------------------------------------------------
    "create_artifact": ToolProbe(
        {"title": "iso", "content_md": "x", "occurred_at": _WHEN, "area_id": "<<area_id>>"}
    ),
    "ingest": ToolProbe({"file_b64": _TEXT_FILE, "filename": "iso.txt", "area_id": "<<area_id>>"}),
    "list_artifacts": ToolProbe({"area_id": "<<area_id>>"}),
    "read_artifact": ToolProbe({"artifact_id": "<<artifact_id>>"}),
    "append_artifact": ToolProbe({"artifact_id": "<<artifact_id>>", "content_md": "x"}),
    "patch_artifact": ToolProbe(
        {
            "artifact_id": "<<artifact_id>>",
            "anchor": "<<block_id>>",
            "op": "replace",
            "expected_rev": 1,
            "content_md": "x",
        }
    ),
    "promote_artifact": ToolProbe(
        {"artifact_id": "<<artifact_id>>", "target_resource_id": "<<resource_id>>"}
    ),
    "list_tables": ToolProbe({"area_id": "<<area_id>>"}),
    "create_table": ToolProbe(
        {"area_id": "<<area_id>>", "name": "iso_mcp", "schema": TABLE_SCHEMA}
    ),
    "describe_table": ToolProbe({"table_id": "<<table_id>>"}),
    "query_table": ToolProbe({"table_id": "<<table_id>>", "sql": "SELECT 1"}),
    "insert_rows": ToolProbe(
        {
            "table_id": "<<table_id>>",
            "rows": [{"occurred_at": "2026-08-03T00:00:00+00:00", "amount": 3, "purpose": "x"}],
        }
    ),
    "save_query_result": ToolProbe(
        {"table_id": "<<table_id>>", "sql": "SELECT 1", "title": "iso", "occurred_at": _WHEN}
    ),
    "timeline": ToolProbe(
        {
            "from_": "2026-01-01T00:00:00Z",
            "to": "2026-12-31T00:00:00Z",
            "sources": ["table:<<table_id>>"],
        }
    ),
    "list_category_rules": ToolProbe({"area_id": "<<area_id>>"}),
    "upsert_category_rule": ToolProbe(
        {"area_id": "<<area_id>>", "pattern": "iso", "category": "x"}
    ),
    "set_convention": ToolProbe(
        {"area_id": "<<area_id>>", "source_name": "bank", "convention": {"decimal_separator": ","}}
    ),
    # --- Knowledge Base ----------------------------------------------------------
    "create_node": ToolProbe(
        {"content": "iso", "tier": "hypothesis", "source_ref": _SOURCE_REF, "occurred_at": _WHEN},
        denied=ANCHOR_DENIED,
    ),
    "update_node": ToolProbe({"node_id": "<<node_id>>", "content": "iso"}),
    "create_edge": ToolProbe(
        {
            "from_anchor": "node:<<node_id>>",
            "to_anchor": "node:<<node2_id>>",
            "type": "supports",
            "evidence_from": [_SOURCE_REF],
            "evidence_to": [_SOURCE_REF],
        },
        denied=ANCHOR_DENIED,
    ),
    "neighbors": ToolProbe({"anchor": "node:<<node_id>>"}, denied=ANCHOR_DENIED),
    # Loeschende Tools zuletzt: die Gegenprobe laeuft in dieser Reihenfolge.
    "delete_table": ToolProbe({"table_id": "<<table_id>>"}),
    "delete_artifact": ToolProbe({"artifact_id": "<<artifact_id>>"}),
}

MCP_EXEMPT: dict[str, str] = {}


def _tool_names() -> set[str]:
    return {t.name for t in asyncio.run(mcp.list_tools())}


def test_every_tool_is_probed_or_exempt() -> None:
    """Neues Tool ohne Eintrag oder Eintrag ohne Tool: rot."""
    live = _tool_names()
    assert len(live) > 60, f"Tool-Liste unplausibel klein ({len(live)})"
    assert not set(MCP_PROBES) & set(MCP_EXEMPT)
    missing = sorted(live - set(MCP_PROBES) - set(MCP_EXEMPT))
    assert not missing, (
        "MCP-Tool(s) ohne Mandantentrennungs-Probe. In MCP_PROBES eintragen oder mit "
        "Begruendung in MCP_EXEMPT:\n  " + "\n  ".join(missing)
    )
    stale = sorted((set(MCP_PROBES) | set(MCP_EXEMPT)) - live)
    assert not stale, f"Eintrag ohne Tool (entfernen): {stale}"


# --------------------------------------------------------------------------
# Lauf
# --------------------------------------------------------------------------


class RecordingTransport(httpx.AsyncBaseTransport):
    """ASGI-Transport zur App, der jeden Antwortstatus mitschreibt."""

    def __init__(self) -> None:
        self._inner = httpx.ASGITransport(app=app)
        self.statuses: list[int] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._inner.handle_async_request(request)
        self.statuses.append(response.status_code)
        return response


@dataclass(frozen=True)
class Outcome:
    is_error: bool
    statuses: tuple[int, ...]
    text: str


def _fill(template: Any, ids: dict[str, str]) -> Any:
    if isinstance(template, str):
        return _REF.sub(lambda m: ids[m.group(1)], template)
    if isinstance(template, list):
        return [_fill(v, ids) for v in template]
    if isinstance(template, dict):
        return {k: _fill(v, ids) for k, v in template.items()}
    return template


def _has_refs(probe: ToolProbe) -> bool:
    return bool(_REF.search(json.dumps(probe.args)))


async def _call(
    transport: RecordingTransport, who: Tenant, tool: str, args: dict[str, Any]
) -> Outcome:
    async def _build() -> ApiClient:
        return ApiClient(_BASE, who.agent_token, who.workspace_id, transport=transport)

    server.build_client = _build
    transport.statuses = []
    async with Client(mcp) as client:
        result = await client.call_tool(tool, args, raise_on_error=False)
    parts = [getattr(block, "text", "") for block in result.content]
    text = "\n".join(parts) + json.dumps(result.structured_content, default=str)
    return Outcome(result.is_error, tuple(transport.statuses), text)


@dataclass
class Report:
    findings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    known_seen: set[str] = field(default_factory=set)

    def count(self, what: str) -> None:
        self.counts[what] = self.counts.get(what, 0) + 1


async def _probe_as_a(
    transport: RecordingTransport, report: Report, tool: str, a: Tenant, b: Tenant, ghost: Tenant
) -> None:
    probe = MCP_PROBES[tool]
    marker_b = {**b.ids, "marker": b.marker}
    args = _fill(probe.args, marker_b)
    variant = "V2" if _has_refs(probe) else "V3"
    if variant == "V3":
        args = _fill(probe.args, {**a.ids, "marker": a.marker})
    out = await _call(transport, a, tool, args)
    report.count(variant)
    leaked = leaks(out.text, json.dumps(args), b)
    if leaked:
        report.findings.append(f"{variant} {tool}: B-Daten im Ergebnis an A: {leaked}")
    if any(s >= 500 for s in out.statuses):
        report.findings.append(f"{variant} {tool}: API-Serverfehler {out.statuses}")
        return
    if variant == "V3":
        if out.is_error:
            report.findings.append(f"V3 {tool}: Tool-Fehler fuer A {out.text[:200]}")
        return
    if not out.is_error and not probe.filters:
        report.findings.append(f"V2 {tool}: A mit B-IDs erfolgreich {out.text[:200]}")
        return
    if out.is_error and (not out.statuses or out.statuses[-1] not in probe.denied):
        if not probe.filters:
            report.findings.append(
                f"V2 {tool}: Fehler nicht an der Mandantengrenze (Status {out.statuses}) "
                f"{out.text[:200]}"
            )
            return
    ghost_args = _fill(probe.args, {**ghost.ids, "marker": ghost.marker})
    phantom = await _call(transport, a, tool, ghost_args)
    if (phantom.is_error, phantom.statuses) != (out.is_error, out.statuses):
        if probe.known:
            report.known_seen.add(tool)
            return
        report.findings.append(
            f"V2 {tool}: Existenz-Orakel — B-IDs {out.statuses}/{out.is_error}, "
            f"unbekannte IDs {phantom.statuses}/{phantom.is_error}"
        )


async def run_isolation(a: Tenant, b: Tenant, ghost: Tenant) -> Report:
    report = Report()
    original = server.build_client
    transport = RecordingTransport()
    try:
        async with app.router.lifespan_context(app):
            before = await fingerprint_async(b)
            for tool in MCP_PROBES:
                await _probe_as_a(transport, report, tool, a, b, ghost)
            after = await fingerprint_async(b)
            changed = sorted(k for k in before if before[k] != after.get(k))
            if changed:
                report.findings.append(f"Schreibzugriff bei B durch A-Tools: {changed}")

            marker_b = {**b.ids, "marker": b.marker}
            for tool, probe in MCP_PROBES.items():
                if not _has_refs(probe) or probe.filters:
                    continue
                out = await _call(transport, b, tool, _fill(probe.args, marker_b))
                report.count("control")
                last = out.statuses[-1] if out.statuses else 0
                if out.statuses and control_passes(last):
                    continue
                if probe.known:
                    report.known_seen.add(tool)
                    continue
                report.findings.append(
                    f"Gegenprobe {tool}: B mit eigenen IDs -> {out.statuses} {out.text[:200]}"
                )
    finally:
        server.build_client = original

    for tool, probe in MCP_PROBES.items():
        if probe.known and tool not in report.known_seen:
            report.findings.append(
                f"{tool}: als bekannt markierte Abweichung tritt nicht mehr auf — "
                f"`known` entfernen ({probe.known})"
            )
    return report


@pytest.fixture
def isolation_env(tmp_path: Path) -> Iterator[None]:
    with isolation_stores(tmp_path):
        yield


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db", "isolation_env")
def test_no_mcp_tool_crosses_the_tenant_boundary(patched_jwt_secret: str) -> None:
    tenants: list[Tenant] = []
    try:
        with TestClient(app) as client:
            a = seed_tenant(client, "A", patched_jwt_secret)
            tenants.append(a)
            b = seed_tenant(client, "B", patched_jwt_secret)
            tenants.append(b)
        report = asyncio.run(run_isolation(a, b, ghost_of(b)))

        assert not report.findings, f"{len(report.findings)} Befund(e):\n" + "\n".join(
            report.findings
        )
        # Null geprueft ist rot (Mindestzahlen knapp unter dem heutigen Stand).
        counts = report.counts
        assert counts.get("V2", 0) >= 55, counts
        assert counts.get("V3", 0) >= 15, counts
        assert counts.get("control", 0) >= 50, counts
    finally:
        cleanup_workspaces([t.user_id for t in tenants])
