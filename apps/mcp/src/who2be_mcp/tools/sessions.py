"""Gespraechs-MCP-Tools (ADR-0053 6.6/6.7, Paket E-MCP-1).

Vier Werkzeuge fuer das Feedback-Gespraech: Dossier lesen, Protokoll
einreichen, Entwurf mit einer Massnahme verknuepfen, Nachschau lesen. Muster
wie `tools/learning.py`: modulweite `@with_tool_log`-Funktionen (fuer Tests
direkt aufrufbar), `register(mcp)` haengt sie an die FastMCP-Instanz.

Sichtbar nur mit `case_triage` (`tool_requirements`, ADR-0042-Filter). Die
Rechte prueft allein die API (`require_triage_right`); die Einstufung
(`review`) und das Zurueckziehen haben bewusst KEIN Werkzeug — das entscheidet
ein Mensch (6.6, F-W7). Die Werkzeuge haengen an einzelne Problem-Gruende nur
einen Korrektur-Hinweis, alle uebrigen gehen unveraendert durch.

`get_dossier` liefert nach ADR-0056 standardmaessig Markdown: ein voll
ausgereiztes Dossier ist als JSON ueber der 50.000-Zeichen-Grenze der
Konsumenten-Laufzeit (Beleg im Budget-Test `test_session_tools.py`).
"""

from __future__ import annotations

from datetime import date

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import ValidationError

from who2be_mcp.client import ApiClient
from who2be_mcp.clients import sessions as sessions_api
from who2be_mcp.clients.sessions import FollowUpReport, MeasureLinkDraftBody, SessionSubmitResult
from who2be_mcp.core_logging import with_tool_log
from who2be_mcp.tools.learning import _first_error, _parse_uuid
from who2be_models import (
    EntityType,
    MeasureCreate,
    MeasureEventRead,
    SessionCreate,
    SessionDecision,
    SessionDissent,
    SessionParticipant,
    SessionTrigger,
)
from who2be_models.session import Dossier

# Zusatz je Problem-Grund: die Server-Meldung bleibt vorn, der Hinweis sagt,
# was der Agent jetzt tun kann. Nur Gruende, bei denen er etwas tun kann.
_SESSION_HINTS: dict[str, str] = {
    "session_cases_invalid": (
        " Korrigieren: `case_ids` des Protokolls muessen Faelle dieses Agenten sein "
        "(`list_cases`), die `case_ids` jeder Massnahme muessen im Protokoll stehen."
    ),
    "measure_test_case_required": (
        " Korrigieren: zuerst den Pruefall dieses Agenten anlegen, dann seine id als "
        "`test_case_id` angeben (`list_test_cases`)."
    ),
    "test_subject_version_not_found": (
        " Korrigieren: die Version muss zum Element der Massnahme gehoeren "
        "(gleiche Art, gleiche `entity_id`, `list_versions`)."
    ),
}


def _with_hint(exc: ToolError) -> ToolError:
    """Haengt den Korrektur-Hinweis zum `reason` der Problem-Antwort an."""
    message = str(exc)
    for reason, hint in _SESSION_HINTS.items():
        if f"reason={reason}" in message:
            return ToolError(f"{message}{hint}")
    return exc


async def _client() -> ApiClient:
    """API-Client ueber `server.build_client` (Import im Aufruf, zyklusfrei)."""
    from who2be_mcp import server

    return await server.build_client()


# --- Dossier ---------------------------------------------------------------------


def _counts(values: dict[str, int]) -> str:
    return ", ".join(f"{key} {value}" for key, value in values.items() if value) or "-"


def dossier_text(dossier: Dossier) -> str:
    """Lesefassung von `get_dossier` (ADR-0056, Option B): Markdown je Block.

    Alle Zahlen bleiben Rohzahlen (QE8 a); die Texte sind schon serverseitig
    gekuerzt. Kein JSON, kein Escaping.
    """
    open_cases = dossier.open_cases
    parts = [
        f"# Dossier {dossier.agent_name} ({dossier.agent_id})",
        f"- stand: {dossier.generated_at.isoformat()} · min_uses: {dossier.min_uses}\n"
        '> Markdown-Fassung. Felder als JSON: `format="full"`.',
    ]

    lines = [
        f"## Offene Faelle ({open_cases.total})",
        f"- je Status: {_counts({k.value: v for k, v in open_cases.counts.items()})}",
    ]
    for case in open_cases.items:
        lines.append(
            f"- {case.status.value} · {case.severity.value} · {case.id} · "
            f"{case.created_at.date().isoformat()}: {case.situation} → erwartet: "
            f"{case.expected_behavior}"
        )
    parts.append("\n".join(lines))

    lines = [f"## Bausteine ({len(dossier.elements)} von {dossier.elements_total})"]
    for element in dossier.elements:
        lines.append(f"### {element.entity_type} {element.name} ({element.entity_id})")
        for v in element.versions:
            head = f"v{v.version}" + (" aktiv" if v.active else "")
            if v.activated_at is not None:
                head += f", aktiviert {v.activated_at.date().isoformat()}"
            cases = "-" if v.cases is None else str(v.cases)
            lines.append(
                f"- {head}: uses {v.uses} · outcomes {_counts(v.outcomes)} · "
                f"signals {_counts(v.signals)} · Faelle {cases}"
                + (" · zu wenig Nutzung" if v.insufficient else "")
            )
    parts.append("\n".join(lines))

    access = dossier.access
    lines = [
        f"## Zugriffe seit {access.since.isoformat()} ({access.window_days} Tage, "
        f"{access.total} Eintraege)"
    ]
    for row in access.rows:
        lines.append(
            f"- {row.ref_kind}/{row.operation}/{row.sensitivity}: {row.entries} Eintraege, "
            f"{row.refs} Objekte, zuletzt {row.last_on.isoformat()}"
        )
    parts.append("\n".join(lines))

    lines = [f"## Massnahmen ({len(dossier.measures)} von {dossier.measures_total})"]
    for m in dossier.measures:
        target = m.target.value if m.entity_id is None else f"{m.target.value} {m.entity_id}"
        lines.append(
            f"- {m.state.value} · {target} · {m.id}: {m.change_summary} "
            f"(Nachschau {m.follow_up_at.isoformat()}, Faelle {m.case_count})"
        )
    parts.append("\n".join(lines))

    lines = [f"## Generationen ({len(dossier.generations)})"]
    for g in dossier.generations:
        source = "neu" if g.from_version is None else f"v{g.from_version}"
        measures = ", ".join(str(i) for i in g.measure_ids) or "direkt, ohne Massnahme"
        extra = "" if g.verdict is None else f" · {g.verdict.value}"
        shared = (
            "" if g.shared_agent_count is None else f" · weitere Agenten {g.shared_agent_count}"
        )
        lines.append(
            f"- {g.activated_at.date().isoformat()} {g.entity_type} {g.name}: "
            f"{source} → v{g.to_version} · Massnahmen: {measures}{extra}{shared}"
        )
    if dossier.generations_next_cursor is not None:
        lines.append(f'- weitere Generationen: `cursor="{dossier.generations_next_cursor}"`')
    parts.append("\n".join(lines))
    return "\n\n".join(parts)


@with_tool_log("get_dossier")
async def get_dossier(
    agent_id: str, cursor: str | None = None, format: str = "text"
) -> Dossier | str:
    """Dossier zur Vorbereitung eines Feedback-Gespraechs ueber einen Agenten.

    Offene Faelle, Bausteine mit Rohzahlen je Version (Nutzung, Ergebnisse, Signale, Faelle),
    Zugriffe, fruehere Massnahmen, Generationen. `cursor` blaettert nur die Generationen.
    Braucht `case_triage`. Default Markdown; JSON: `format="full"`.
    """
    from who2be_mcp.server import _validate_response_format

    _validate_response_format(format)
    parsed = _parse_uuid(agent_id, "Agent")
    client = await _client()
    dossier = await sessions_api.get_dossier(client, parsed, cursor)
    return dossier_text(dossier) if format == "text" else dossier


# --- Protokoll -------------------------------------------------------------------


@with_tool_log("submit_session_protocol")
async def submit_session_protocol(
    agent_id: str,
    trigger: SessionTrigger,
    participants: list[SessionParticipant],
    case_ids: list[str],
    summary: str,
    decisions: list[SessionDecision],
    dissent: list[SessionDissent],
    follow_up_at: str,
    measures: list[MeasureCreate],
    supersedes_id: str | None = None,
) -> SessionSubmitResult:
    """Reicht das Protokoll eines Feedback-Gespraechs ein, mit Faellen und Massnahmen.

    Eine Transaktion; danach unveraenderlich, Korrektur nur als neues Protokoll mit
    `supersedes_id`. `follow_up_at` als `YYYY-MM-DD`. Jede Massnahme braucht `case_ids` aus dem
    Protokoll und einen `test_case_id` dieses Agenten. Faelle mit Massnahme gehen auf
    `in_progress`. Einstufen tut ein Mensch. Braucht `case_triage`.
    """
    try:
        due = date.fromisoformat(follow_up_at)
    except ValueError as exc:
        raise ToolError(f"Ungueltiges follow_up_at: '{follow_up_at}' (YYYY-MM-DD).") from exc
    try:
        data = SessionCreate(
            agent_id=_parse_uuid(agent_id, "Agent"),
            trigger=trigger,
            participants=participants,
            case_ids=[_parse_uuid(c, "Fall") for c in case_ids],
            summary=summary,
            decisions=decisions,
            dissent=dissent,
            follow_up_at=due,
            measures=measures,
            supersedes_id=None
            if supersedes_id is None
            else _parse_uuid(supersedes_id, "Protokoll"),
        )
    except ValidationError as exc:
        raise ToolError(f"Ungueltige Eingabe: {_first_error(exc)}") from exc
    client = await _client()
    try:
        return await sessions_api.submit_session_protocol(client, data)
    except ToolError as exc:
        raise _with_hint(exc) from exc


# --- Massnahmen ------------------------------------------------------------------


@with_tool_log("link_measure_draft")
async def link_measure_draft(
    measure_id: str, version_entity_type: EntityType, version_id: str
) -> MeasureEventRead:
    """Verknuepft einen Entwurf (Version des Ziel-Elements) mit einer Massnahme.

    Geht, bis die Version aktiv ist; die juengste Verknuepfung gilt. Aktivieren tut ein
    Mensch. Braucht `case_triage`.
    """
    parsed = _parse_uuid(measure_id, "Massnahme")
    data = MeasureLinkDraftBody(
        version_entity_type=version_entity_type,
        version_id=_parse_uuid(version_id, "Version"),
    )
    client = await _client()
    try:
        return await sessions_api.link_measure_draft(client, parsed, data)
    except ToolError as exc:
        raise _with_hint(exc) from exc


@with_tool_log("get_follow_up")
async def get_follow_up(measure_id: str) -> FollowUpReport:
    """Nachschau einer Massnahme: Kennzahlen vorher/nachher als Rohzahlen.

    Pruefall-Lauf, Nutzungen und Faelle je Version, Wiederauftreten, `due`, `reviewable`,
    `insufficient`. Die Einstufung macht ein Mensch, dafuer gibt es kein Werkzeug.
    Braucht `case_triage`.
    """
    parsed = _parse_uuid(measure_id, "Massnahme")
    client = await _client()
    return await sessions_api.get_follow_up(client, parsed)


def register(mcp: FastMCP) -> None:
    """Registriert die Gespraechs-Tools (`output_schema=None`, Payload-Budget)."""
    for fn in (get_dossier, submit_session_protocol, link_measure_draft, get_follow_up):
        mcp.tool(output_schema=None)(fn)
