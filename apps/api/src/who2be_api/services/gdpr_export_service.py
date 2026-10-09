"""GDPR-Datenexport (Track O, Plan §3.2 / DSGVO Art. 20 — Datenuebertragbarkeit).

Sammelt das vollstaendige Daten-Buendel des Users: alle Organizations +
Workspaces, in denen er Mitglied ist, samt Personas/Playbooks/Resources/Agents
und deren Versionen.

Seit WP20 (ADR-0047/0048/0049) gehoert der Agenten-Arbeitsbereich dazu:
WorkAreas + Artifacts (inkl. doc-Blockliste), der Blob-KATALOG, der
Tabellen-Katalog samt Zeilen-Dump aus dem SQLite-Store, die Knowledge Base
(Nodes/Kanten/Evidence/Konflikte) und das Zugriffslog des Workspace.

Zwei bewusste Grenzen des Buendels:

* **Keine Blob-Bytes.** `wa_blob` liefert nur Metadaten (sha256, Groesse,
  Media-Type, Storage-Key). Ein JSON mit base64-kodierten PDFs waere je nach
  Workspace hunderte MB gross und im Fehlerfall nicht mehr auslieferbar; der
  Storage-Key macht die Objekte fuer den Betreiber trotzdem eindeutig
  adressierbar (`_BLOB_EXPORT_NOTE`).
* **Keine abgeleiteten Index-Daten.** `wa_chunk` und die `search`-tsvectors
  entstehen aus Inhalten, die bereits im Buendel stehen — sie waeren
  Duplikate, keine zusaetzliche Auskunft.

RLS-Konformitaet: die Control-plane-Tabellen (organization/workspace/
workspace_member) tragen kein RLS und werden direkt gelesen. Die
workspace-scoped Inhalts-Tabellen sind unter RLS nur **innerhalb** des jeweiligen
Mandanten sichtbar — deshalb betritt der Export pro Workspace `tenant_scope`
und liest die Inhalte dort. So funktioniert der Export identisch unter der
App-Rolle (`who2be_app`) wie unter dem Owner.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg

from who2be_api.core.entity_sql import safe_entity
from who2be_api.core.security import role_satisfies
from who2be_api.core.tenancy import scope_to_self, tenant_scope
from who2be_api.services.tablestore_provider import get_table_store
from who2be_api.tablestore import AreaStoreMissingError, TableStore, quote_identifier
from who2be_models import WorkspaceRole

logger = logging.getLogger(__name__)

# Tabellen, deren interne Mandanten-Spalte aus dem Export entfernt wird.
_INTERNAL_COLUMNS = frozenset({"workspace_id"})

# Harter Deckel je Tabelle im Zeilen-Dump. Der Export laeuft synchron in einem
# Request und materialisiert das ganze Buendel im Speicher — eine Area-Tabelle
# mit Millionen Zeilen wuerde ihn sprengen. Bei Ueberschreitung traegt der
# Block `truncated: true`; der vollstaendige Datenbestand ist ueber den
# Tabellen-Store-Snapshot des Betreibers zu ziehen (RUNBOOK).
TABLE_ROW_EXPORT_CAP = 10_000

# Hinweistext im Blob-Block: das Buendel enthaelt bewusst keine Bytes.
_BLOB_EXPORT_NOTE = (
    "Dieses Buendel enthaelt die Blob-METADATEN, nicht die Binaerinhalte. "
    "Die Objekte liegen content-addressed im BlobStore unter dem jeweiligen "
    "`storage_key` (Schema `blobs/{workspace_id}/{sha256}`, ADR-0048) und "
    "werden vom Betreiber daraus ausgeleitet (RUNBOOK, Abschnitt "
    '„MinIO-/BlobStore-Backup").'
)

# Hinweis im Export-Manifest, wenn `agent_memories` wegen der Rolle leer bleibt.
_AGENT_MEMORY_WITHHELD_NOTE = (
    "Das Agentengedaechtnis dieses Workspace ist ab der Rolle editor sichtbar "
    "(wie in der Oberflaeche) und deshalb nicht enthalten. Es ist ein Inhalt des "
    "Workspace, kein Datum ueber dich; Fakten ueber dich stehen unter "
    "`user_memories`."
)


# Hinweis im Export-Manifest, wenn `cases` wegen der Rolle nur die eigenen
# Meldungen enthaelt (ADR-0053 3.3, Rechte).
_CASES_OWN_ONLY_NOTE = (
    "Alle Faelle dieses Workspace sind ab der Rolle editor sichtbar (wie in der "
    "Oberflaeche). Enthalten sind deshalb nur die Faelle, die du selbst gemeldet "
    "hast, jeweils mit Verlauf, Zuordnung und Schilderung."
)


# Hinweis im Export-Manifest, wenn `feedback_sessions` wegen der Rolle nur die
# eigenen Protokolle enthaelt (ADR-0053 6.6: `GET /feedback-sessions` ab editor).
_SESSIONS_OWN_ONLY_NOTE = (
    "Alle Gespraechsprotokolle dieses Workspace sind ab der Rolle editor sichtbar "
    "(wie in der Oberflaeche). Enthalten sind deshalb nur die Protokolle, die du "
    "eingereicht hast, an denen du teilgenommen hast oder an deren Massnahmen du "
    "gehandelt hast, jeweils mit Faellen, Massnahmen und deren Verlauf."
)

# Protokolle, an denen ein Mensch beteiligt ist (ADR-0053 3.5/3.6): als
# Einreicher, als Teilnehmer bzw. mit abweichender Meinung, oder als Akteur
# eines Massnahmen-Events. `jsonb @>` sucht den Eintrag in der Liste; die IDs
# liegen als kanonischer UUID-Text vor (`SessionParticipant`, mode="json").
_OWN_SESSIONS_QUERY = (
    "SELECT * FROM feedback_session s WHERE s.workspace_id = $1 AND ("
    "  (s.submitted_by_kind = 'human' AND s.submitted_by = $2) "
    "  OR s.participants @> jsonb_build_array("
    "       jsonb_build_object('kind', 'human', 'id', $2::uuid::text)) "
    "  OR s.dissent @> jsonb_build_array("
    "       jsonb_build_object('participant_kind', 'human', 'participant_id', $2::uuid::text)) "
    "  OR EXISTS ("
    "    SELECT 1 FROM measure m JOIN measure_event e "
    "      ON e.workspace_id = m.workspace_id AND e.measure_id = m.id "
    "    WHERE m.workspace_id = s.workspace_id AND m.session_id = s.id "
    "      AND e.actor_kind = 'human' AND e.actor_id = $2)"
    ") ORDER BY s.created_at ASC, s.id ASC"
)


def _can_read_agent_memory(role: str) -> bool:
    """Gleiche Grenze wie `MemoryService.list_memories` (`require_role` editor).

    Unbekannte Rollenwerte schliessen aus (fail-closed) statt den Export
    scheitern zu lassen.
    """
    try:
        actual = WorkspaceRole(role)
    except ValueError:
        return False
    return role_satisfies(actual, WorkspaceRole.editor)


def _can_read_all_cases(role: str) -> bool:
    """ADR-0053 3.3 (Rechte): alle Faelle lesen ab `editor`, darunter nur die
    selbst gemeldeten. Dieselbe Rollengrenze wie das Agentengedaechtnis, aber
    eine eigene Funktion, damit beide Regeln getrennt nachziehbar bleiben."""
    return _can_read_agent_memory(role)


def _can_read_all_sessions(role: str) -> bool:
    """ADR-0053 6.6: Protokolle lesen ab `editor`, darunter nur die eigenen.
    Eigene Funktion wie `_can_read_all_cases`, damit die Regeln getrennt
    nachziehbar bleiben."""
    return _can_read_agent_memory(role)


def _with_session_children(
    sessions: list[asyncpg.Record],
    session_cases: list[asyncpg.Record],
    measures: list[asyncpg.Record],
    measure_cases: list[asyncpg.Record],
    measure_events: list[asyncpg.Record],
) -> list[dict[str, Any]]:
    """Protokolle mit `case_ids` und `measures`; jede Massnahme mit `case_ids`
    und `events` (aelteste zuerst). Kinder fremder Protokolle fallen heraus,
    auch wenn sie geladen worden waeren. Die Hilfsspalte `agent_id` der
    Verknuepfungen steht schon am Protokoll und entfaellt."""
    cases_by_session: dict[Any, list[Any]] = {}
    for row in session_cases:
        cases_by_session.setdefault(row["session_id"], []).append(row["case_id"])
    cases_by_measure: dict[Any, list[Any]] = {}
    for row in measure_cases:
        cases_by_measure.setdefault(row["measure_id"], []).append(row["case_id"])
    events_by_measure: dict[Any, list[dict[str, Any]]] = {}
    for row in measure_events:
        events_by_measure.setdefault(row["measure_id"], []).append(_clean(row))
    measures_by_session: dict[Any, list[dict[str, Any]]] = {}
    for row in measures:
        item = _clean(row)
        item["case_ids"] = cases_by_measure.get(row["id"], [])
        item["events"] = events_by_measure.get(row["id"], [])
        measures_by_session.setdefault(row["session_id"], []).append(item)
    result: list[dict[str, Any]] = []
    for row in sessions:
        item = _clean(row)
        item["case_ids"] = cases_by_session.get(row["id"], [])
        item["measures"] = measures_by_session.get(row["id"], [])
        result.append(item)
    return result


def _with_case_children(
    cases: list[asyncpg.Record],
    events: list[asyncpg.Record],
    elements: list[asyncpg.Record],
    statements: list[asyncpg.Record],
) -> list[dict[str, Any]]:
    """Faelle mit Verlauf (`events`), Zuordnung (`elements`) und Schilderungen
    (`statements`) je Fall, jeweils aelteste zuerst. Kinder fremder Faelle
    fallen heraus, auch wenn sie geladen worden waeren."""
    grouped: dict[str, dict[Any, list[dict[str, Any]]]] = {
        "events": {},
        "elements": {},
        "statements": {},
    }
    for key, rows in (("events", events), ("elements", elements), ("statements", statements)):
        for row in rows:
            grouped[key].setdefault(row["case_id"], []).append(_clean(row))
    result: list[dict[str, Any]] = []
    for row in cases:
        item = _clean(row)
        for key, by_case in grouped.items():
            item[key] = by_case.get(row["id"], [])
        result.append(item)
    return result


# KB-Zusatztabellen ohne generierte Spalten — `SELECT *` ist hier sicher.
_KB_TABLES: tuple[tuple[str, str], ...] = (
    ("edges", "kb_edge"),
    ("edge_evidence", "kb_edge_evidence"),
    ("node_source_areas", "kb_node_source_area"),
    ("conflicts", "kb_conflict"),
)

# `kb_node` traegt eine generierte `search`-tsvector-Spalte (Migration 0077) —
# Index-Material, kein Nutzdatum. Deshalb explizite Spaltenliste statt `*`
# (Muster: `_MEMORY_COLUMNS` unten).
_KB_NODE_COLUMNS = (
    "id, workspace_id, tier, content, content_ref, source_ref, source_ref_kind, "
    "ttl_expires_at, status, derivation_depth, sensitivity, occurred_at, "
    "occurred_precision, created_by, created_at, updated_at"
)

# `agent_memory` ohne die generierte tsvector-Spalte `search` und ohne den
# Vektor `content_vector` (beides Index-Material, kein Nutzdatum). Mit den
# Gedaechtnis-2.0-Spalten aus Migration 0091.
_MEMORY_COLUMNS = (
    "id, workspace_id, agent_id, status, fact, context, category, importance, source, "
    "triage_note, retrieval_count, last_retrieved_at, created_at, updated_at, "
    "kind, scope, subject_user_id, origin, created_by_agent_id, confirmed_at, "
    "confirmed_by, expires_at, occurrence_count, converted_case_id"
)

# Workspaces + Org-Metadaten des Users (control-plane, ohne RLS). Eingemottete
# Orgs (`deleted_at`) bleiben drin — der Export soll auch vorgemerkte Daten noch
# herausgeben, solange sie nicht hart geloescht sind.
_WORKSPACES_QUERY = (
    "SELECT o.id AS org_id, o.name AS org_name, o.slug AS org_slug, o.kind AS org_kind, "
    "       w.id AS workspace_id, w.name AS workspace_name, w.slug AS workspace_slug, "
    "       m.role AS workspace_role "
    "FROM workspace_member m "
    "JOIN workspace w ON w.id = m.workspace_id "
    "JOIN organization o ON o.id = w.org_id "
    "WHERE m.user_id = $1 "
    "ORDER BY o.created_at ASC, o.id ASC, w.created_at ASC, w.id ASC"
)


def _clean(row: asyncpg.Record) -> dict[str, Any]:
    """Record → dict, ohne interne Mandanten-Spalten."""
    return {key: value for key, value in dict(row).items() if key not in _INTERNAL_COLUMNS}


def _with_events(
    memories: list[asyncpg.Record], events: list[asyncpg.Record]
) -> list[dict[str, Any]]:
    """Gedaechtniseintraege mit ihrer Historie unter `events` (aelteste zuerst).

    Dieselbe Verschachtelung wie Versionen unter ihrer Identitaets-Zeile. Es
    landen nur Events an Eintraegen, die selbst im Block stehen — fremdes
    Nutzergedaechtnis faellt so samt seiner Historie heraus.
    """
    by_memory: dict[Any, list[dict[str, Any]]] = {}
    for row in events:
        by_memory.setdefault(row["memory_id"], []).append(_clean(row))
    result: list[dict[str, Any]] = []
    for row in memories:
        item = _clean(row)
        item["events"] = by_memory.get(row["id"], [])
        result.append(item)
    return result


def _safe_kb_table(table: str) -> str:
    """Whitelist fuer die KB-Tabellennamen im f-String-SQL (Zero-Trust).

    Dasselbe Motiv wie `core/entity_sql.safe_entity`: die Namen stammen heute
    aus einer Modul-Konstante, der Guard erzwingt das aber zur Laufzeit statt
    per Kommentar.
    """
    if table not in {name for _, name in _KB_TABLES}:
        raise ValueError(f"Unbekannte KB-Tabelle: {table!r}")
    return table


class GdprExportService:
    """Baut das exportierbare JSON-Buendel eines Users."""

    def __init__(self, pool: asyncpg.Pool, table_store: TableStore | None = None) -> None:
        self._pool = pool
        # Injizierbar fuer Tests (Muster `set_table_store`); im Betrieb der
        # prozessweite Store, damit die Area-Locks dieselben bleiben.
        self._table_store = table_store or get_table_store()

    async def export(self, user_id: UUID) -> dict[str, Any]:
        rows = await self._pool.fetch(_WORKSPACES_QUERY, user_id)

        # Org → (Metadaten + Workspace-Liste) gruppieren, Reihenfolge erhalten.
        orgs: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            org_id = row["org_id"]
            org = orgs.setdefault(
                org_id,
                {
                    "id": str(org_id),
                    "name": row["org_name"],
                    "slug": row["org_slug"],
                    "kind": row["org_kind"],
                    "workspaces": [],
                },
            )
            org["workspaces"].append(
                await self._export_workspace(
                    workspace_id=row["workspace_id"],
                    org_id=org_id,
                    name=row["workspace_name"],
                    slug=row["workspace_slug"],
                    role=row["workspace_role"],
                    user_id=user_id,
                )
            )

        return {
            "exported_at": datetime.now(UTC),
            "user_id": str(user_id),
            "account": await self._export_account(user_id),
            "organizations": list(orgs.values()),
        }

    async def _export_account(self, user_id: UUID) -> dict[str, Any]:
        """GoTrue-Profildaten des Users (Art.-15-Vollstaendigkeit, WP-E).

        Die Daten liegen im GoTrue-Schema `auth.users`, auf das die
        Laufzeitrolle keinen Zugriff hat. Gelesen wird ueber
        `w2b_self_account()` (Migration 0093), die nur die Zeile von
        `app.current_user_id` liefert — `scope_to_self` setzt die GUC
        transaktionslokal. Ist die Funktion nicht aufrufbar (reine Test-DB ohne
        GoTrue), bleibt der Block leer, statt den ganzen Export scheitern zu
        lassen — Muster `repositories/me_repository._lookup_profile`.
        """
        block: dict[str, Any] = {
            "id": str(user_id),
            "email": None,
            "created_at": None,
            "last_sign_in_at": None,
        }
        try:
            async with self._pool.acquire() as conn, conn.transaction():
                await scope_to_self(conn, user_id)
                row = await conn.fetchrow(
                    "SELECT email, created_at, last_sign_in_at FROM w2b_self_account()"
                )
        except asyncpg.PostgresError:
            return block
        if row is None:
            return block
        # Spalten koennen in alten Test-Stubs fehlen — defensiv per .get().
        record = dict(row)
        block["email"] = record.get("email")
        block["created_at"] = record.get("created_at")
        block["last_sign_in_at"] = record.get("last_sign_in_at")
        return block

    async def _export_workspace(
        self,
        *,
        workspace_id: UUID,
        org_id: UUID,
        name: str,
        slug: str,
        role: str,
        user_id: UUID,
    ) -> dict[str, Any]:
        # Pro Workspace in den Mandanten-Scope wechseln, damit RLS die Inhalte
        # sichtbar macht; jede Query zieht eine mandantengebundene Connection.
        async with tenant_scope(workspace_id, org_id):
            personas = await self._versioned(workspace_id, "persona", "persona_id")
            playbooks = await self._versioned(workspace_id, "playbook", "playbook_id")
            resources = await self._versioned(workspace_id, "resource", "resource_id")
            external_tools = await self._versioned(
                workspace_id, "external_tool", "external_tool_id"
            )
            agents = await self._pool.fetch(
                "SELECT * FROM agent WHERE workspace_id = $1 ORDER BY created_at ASC, id ASC",
                workspace_id,
            )
            # Agent-Memory (ADR-0044): kuratierte Fakten koennen personenbezogene
            # Angaben enthalten — Teil des Art.-20-Buendels ab Tag 1.
            # Seit Gedaechtnis 2.0 (ADR-0053 3.1, Migration 0091) liegen in
            # derselben Tabelle zwei Bestaende mit verschiedenen Besitzern:
            # das Agentengedaechtnis (`scope='agent'`, Inhalt des Workspace)
            # und das Nutzergedaechtnis (`scope='user'`, gehoert genau EINEM
            # Menschen, 3.1.1). Letzteres geht nur an diesen Menschen — ein
            # ungefiltertes SELECT lieferte ihm die Nutzerfakten der uebrigen
            # Mitglieder mit aus. Das Agentengedaechtnis folgt derselben
            # Rollengrenze wie die Oberflaeche (`MemoryService.list_memories`:
            # ab editor) — der Export ist kein Seiteneingang fuer viewer.
            # Beide Bloecke tragen ihre Historie (`agent_memory_event`, 3.1.2)
            # je Eintrag unter `events`.
            agent_memory_visible = _can_read_agent_memory(role)
            memories = (
                await self._pool.fetch(
                    f"SELECT {_MEMORY_COLUMNS} FROM agent_memory "
                    "WHERE workspace_id = $1 AND scope = 'agent' "
                    "ORDER BY created_at ASC, id ASC",
                    workspace_id,
                )
                if agent_memory_visible
                else []
            )
            user_memories = await self._pool.fetch(
                f"SELECT {_MEMORY_COLUMNS} FROM agent_memory "
                "WHERE workspace_id = $1 AND scope = 'user' AND subject_user_id = $2 "
                "ORDER BY created_at ASC, id ASC",
                workspace_id,
                user_id,
            )
            # Historie NUR der exportierten Eintraege laden — nicht workspace-
            # weit. Sonst laegen Ereignisse (mit Fakt-Schnappschuss in
            # `before`/`after`) zu fremden Nutzerfakten im Speicher, und
            # nur `_with_events` stuende zwischen ihnen und dem Buendel.
            exported_ids = [row["id"] for row in (*memories, *user_memories)]
            memory_events = (
                await self._pool.fetch(
                    "SELECT * FROM agent_memory_event "
                    "WHERE workspace_id = $1 AND memory_id = ANY($2::uuid[]) "
                    "ORDER BY memory_id ASC, created_at ASC, id ASC",
                    workspace_id,
                    exported_ids,
                )
                if exported_ids
                else []
            )
            # WorkArea + KB + Zugriffslog (WP20). Der Tabellen-Dump liest die
            # SQLite-Dateien AUSSERHALB von Postgres, braucht aber den Katalog
            # aus dem Mandanten-Scope — deshalb hier drin eingesammelt.
            work_areas = await self._export_work_areas(workspace_id)
            blobs = await self._export_blobs(workspace_id)
            tables = await self._export_tables(workspace_id)
            knowledge_base = await self._export_knowledge_base(workspace_id)
            access_log = await self._pool.fetch(
                "SELECT * FROM agent_access_log WHERE workspace_id = $1 "
                "ORDER BY first_at ASC, id ASC",
                workspace_id,
            )
            # Agent-Favoriten (#427): personenbezogen — welcher Mensch wann
            # welchen Agenten markiert hat. `purge_account_data` loescht die
            # Zeilen, also gehoeren sie auch in die Auskunft; alles andere
            # waere eine Asymmetrie zwischen Art. 17 und Art. 15/20.
            # AUSDRUECKLICH auf `user_id` gefiltert: der Export gehoert genau
            # einem Menschen — ein ungefiltertes SELECT lieferte ihm die Sterne
            # der uebrigen Mitglieder mit aus.
            favorites = await self._pool.fetch(
                "SELECT agent_id, created_at FROM agent_favorite "
                "WHERE workspace_id = $1 AND user_id = $2 "
                "ORDER BY created_at ASC, agent_id ASC",
                workspace_id,
                user_id,
            )
            # Pruefaelle + Prueflaeufe (ADR-0053 3.2, Migration 0089): Freitext
            # (`input`, `expected_behavior`, `output_excerpt`) kann Nutzerinhalte
            # zitieren, `created_by`/`reported_by_user_id` tragen die Person.
            # Workspace-weit wie `agent_memory` — beides sind Inhalte des
            # Workspace, nicht Markierungen eines einzelnen Menschen. Keine
            # generierten Spalten, `*` ist hier sicher.
            test_cases = await self._pool.fetch(
                "SELECT * FROM test_case WHERE workspace_id = $1 ORDER BY created_at ASC, id ASC",
                workspace_id,
            )
            test_runs = await self._pool.fetch(
                "SELECT * FROM test_run WHERE workspace_id = $1 ORDER BY created_at ASC, id ASC",
                workspace_id,
            )
            all_cases_visible = _can_read_all_cases(role)
            cases = await self._export_cases(workspace_id, user_id, all_cases=all_cases_visible)
            all_sessions_visible = _can_read_all_sessions(role)
            feedback_sessions = await self._export_sessions(
                workspace_id, user_id, all_sessions=all_sessions_visible
            )
        return {
            "id": str(workspace_id),
            "name": name,
            "slug": slug,
            "role": role,
            "personas": personas,
            "playbooks": playbooks,
            "resources": resources,
            "external_tools": external_tools,
            "agents": [_clean(row) for row in agents],
            "agent_memories": _with_events(memories, memory_events),
            "user_memories": _with_events(user_memories, memory_events),
            "export_manifest": {
                "agent_memories": (
                    {"included": True}
                    if agent_memory_visible
                    else {"included": False, "reason": _AGENT_MEMORY_WITHHELD_NOTE}
                ),
                "cases": (
                    {"included": True, "scope": "workspace"}
                    if all_cases_visible
                    else {"included": True, "scope": "own_reports", "reason": _CASES_OWN_ONLY_NOTE}
                ),
                "feedback_sessions": (
                    {"included": True, "scope": "workspace"}
                    if all_sessions_visible
                    else {
                        "included": True,
                        "scope": "own_participation",
                        "reason": _SESSIONS_OWN_ONLY_NOTE,
                    }
                ),
            },
            "work_areas": work_areas,
            "wa_blobs": {"note": _BLOB_EXPORT_NOTE, "items": blobs},
            "wa_tables": tables,
            "knowledge_base": knowledge_base,
            "agent_access_log": [_clean(row) for row in access_log],
            "agent_favorites": [_clean(row) for row in favorites],
            "test_cases": [_clean(row) for row in test_cases],
            "test_runs": [_clean(row) for row in test_runs],
            "cases": cases,
            "feedback_sessions": feedback_sessions,
        }

    async def _export_sessions(
        self, workspace_id: UUID, user_id: UUID, *, all_sessions: bool
    ) -> list[dict[str, Any]]:
        """Gespraechsprotokolle mit Faellen und Massnahmen (ADR-0053 3.5/3.6,
        Migration 0103); jede Massnahme mit ihren Faellen und ihrem Verlauf.

        Sichtregel wie in der Oberflaeche (6.6: `GET /feedback-sessions` ab
        `editor`; Muster `_export_cases`): ab `editor` alle Protokolle des
        Workspace, darunter nur die, an denen der exportierende Mensch
        beteiligt ist (`_OWN_SESSIONS_QUERY`). Freitext (`summary`,
        `decisions`, `dissent`, `change_summary`, `note`) kann Personenbezug
        tragen. Die Kind-Tabellen werden nur fuer die exportierten Protokolle
        GELADEN, nicht workspace-weit.
        """
        if all_sessions:
            session_rows = await self._pool.fetch(
                "SELECT * FROM feedback_session WHERE workspace_id = $1 "
                "ORDER BY created_at ASC, id ASC",
                workspace_id,
            )
        else:
            session_rows = await self._pool.fetch(_OWN_SESSIONS_QUERY, workspace_id, user_id)
        session_ids = [row["id"] for row in session_rows]
        if not session_ids:
            return []
        session_cases = await self._pool.fetch(
            "SELECT session_id, case_id FROM feedback_session_case "
            "WHERE workspace_id = $1 AND session_id = ANY($2::uuid[]) "
            "ORDER BY session_id ASC, created_at ASC, case_id ASC",
            workspace_id,
            session_ids,
        )
        measures = await self._pool.fetch(
            "SELECT * FROM measure WHERE workspace_id = $1 AND session_id = ANY($2::uuid[]) "
            "ORDER BY session_id ASC, created_at ASC, id ASC",
            workspace_id,
            session_ids,
        )
        measure_ids = [row["id"] for row in measures]
        measure_cases: list[asyncpg.Record] = []
        measure_events: list[asyncpg.Record] = []
        if measure_ids:
            measure_cases = await self._pool.fetch(
                "SELECT measure_id, case_id FROM measure_case "
                "WHERE workspace_id = $1 AND measure_id = ANY($2::uuid[]) "
                "ORDER BY measure_id ASC, created_at ASC, case_id ASC",
                workspace_id,
                measure_ids,
            )
            measure_events = await self._pool.fetch(
                "SELECT * FROM measure_event "
                "WHERE workspace_id = $1 AND measure_id = ANY($2::uuid[]) "
                "ORDER BY measure_id ASC, created_at ASC, id ASC",
                workspace_id,
                measure_ids,
            )
        return _with_session_children(
            session_rows, session_cases, measures, measure_cases, measure_events
        )

    async def _export_cases(
        self, workspace_id: UUID, user_id: UUID, *, all_cases: bool
    ) -> list[dict[str, Any]]:
        """Faelle (ADR-0053 3.3, Migration 0100) mit Verlauf, Zuordnung und
        Schilderungen.

        Sichtregel wie in der Oberflaeche (3.3, Rechte; Lehre aus #764: der
        Export ist kein Seiteneingang): ab `editor` alle Faelle des Workspace,
        darunter nur die selbst gemeldeten (`reporter_user_id` = der
        exportierende Mensch). Freitext (`situation`, `behavior`, `impact`,
        `expected_behavior`, `note`, Schilderung) kann Personenbezug tragen.
        Die Kind-Tabellen werden nur fuer die exportierten Faelle GELADEN,
        nicht workspace-weit (Muster `agent_memory_event`).
        """
        if all_cases:
            case_rows = await self._pool.fetch(
                "SELECT * FROM agent_case WHERE workspace_id = $1 ORDER BY created_at ASC, id ASC",
                workspace_id,
            )
        else:
            case_rows = await self._pool.fetch(
                "SELECT * FROM agent_case WHERE workspace_id = $1 AND reporter_user_id = $2 "
                "ORDER BY created_at ASC, id ASC",
                workspace_id,
                user_id,
            )
        case_ids = [row["id"] for row in case_rows]
        if not case_ids:
            return []
        events = await self._pool.fetch(
            "SELECT * FROM agent_case_event WHERE workspace_id = $1 AND case_id = ANY($2::uuid[]) "
            "ORDER BY case_id ASC, created_at ASC, id ASC",
            workspace_id,
            case_ids,
        )
        elements = await self._pool.fetch(
            "SELECT * FROM agent_case_element "
            "WHERE workspace_id = $1 AND case_id = ANY($2::uuid[]) "
            "ORDER BY case_id ASC, created_at ASC, id ASC",
            workspace_id,
            case_ids,
        )
        statements = await self._pool.fetch(
            "SELECT * FROM agent_case_statement "
            "WHERE workspace_id = $1 AND case_id = ANY($2::uuid[]) "
            "ORDER BY case_id ASC, created_at ASC, id ASC",
            workspace_id,
            case_ids,
        )
        return _with_case_children(case_rows, events, elements, statements)

    async def _export_work_areas(self, workspace_id: UUID) -> list[dict[str, Any]]:
        """WorkAreas mit ihren Artifacts (ADR-0047).

        Artifacts haengen unter ihrer Area statt flach daneben — dieselbe
        Verschachtelung wie Versionen unter ihrer Identitaets-Zeile. Die
        doc-Blockliste (`content`) ist Nutzdatum und bleibt vollstaendig drin;
        `wa_chunk` fehlt bewusst (abgeleitetes Index-Material, s. Modul-Doc).
        """
        area_rows = await self._pool.fetch(
            "SELECT * FROM work_area WHERE workspace_id = $1 ORDER BY created_at ASC, id ASC",
            workspace_id,
        )
        artifact_rows = await self._pool.fetch(
            "SELECT * FROM wa_artifact WHERE workspace_id = $1 "
            "ORDER BY area_id ASC, created_at ASC, id ASC",
            workspace_id,
        )
        grant_rows = await self._pool.fetch(
            "SELECT * FROM work_area_grant WHERE workspace_id = $1 ORDER BY area_id ASC",
            workspace_id,
        )
        artifacts_by_area: dict[Any, list[dict[str, Any]]] = {}
        for row in artifact_rows:
            artifacts_by_area.setdefault(row["area_id"], []).append(_clean(row))
        grants_by_area: dict[Any, list[dict[str, Any]]] = {}
        for row in grant_rows:
            grants_by_area.setdefault(row["area_id"], []).append(_clean(row))

        areas: list[dict[str, Any]] = []
        for row in area_rows:
            area = _clean(row)
            area["grants"] = grants_by_area.get(row["id"], [])
            area["artifacts"] = artifacts_by_area.get(row["id"], [])
            areas.append(area)
        return areas

    async def _export_blobs(self, workspace_id: UUID) -> list[dict[str, Any]]:
        """Blob-Metadaten OHNE Bytes (ADR-0048, s. `_BLOB_EXPORT_NOTE`)."""
        rows = await self._pool.fetch(
            "SELECT sha256, size_bytes, media_type, storage_key, source_url, "
            "fetched_at, created_at "
            "FROM wa_blob WHERE workspace_id = $1 ORDER BY created_at ASC, sha256 ASC",
            workspace_id,
        )
        return [dict(row) for row in rows]

    async def _export_tables(self, workspace_id: UUID) -> list[dict[str, Any]]:
        """Tabellen-Katalog (`wa_table`) + Zeilen-Dump je Tabelle (ADR-0049).

        Der Katalog lebt in Postgres, die Zeilen in der SQLite-Datei der Area.
        Gelesen wird ueber denselben read-only Pfad wie Agenten-SQL
        (`run_readonly_query`) — der Export bekommt keine Sonderrechte auf den
        Store, und die Engine-Grenzen (Zeit, Zellgroesse, Result-Budget)
        gelten auch hier.
        """
        rows = await self._pool.fetch(
            "SELECT * FROM wa_table WHERE workspace_id = $1 ORDER BY created_at ASC, id ASC",
            workspace_id,
        )
        tables: list[dict[str, Any]] = []
        for row in rows:
            entry = _clean(row)
            entry["rows"] = await self._dump_table_rows(workspace_id, row["area_id"], row["name"])
            tables.append(entry)
        return tables

    async def _dump_table_rows(
        self, workspace_id: UUID, area_id: UUID, table_name: str
    ) -> dict[str, Any]:
        """Zeilen einer Area-Tabelle, gedeckelt auf `TABLE_ROW_EXPORT_CAP`.

        Fehlt die Datei (Area angelegt, nie befuellt) oder scheitert die Query
        an einer Engine-Grenze, bleibt der Block leer und traegt `error` —
        eine einzelne kaputte Tabelle darf das Art.-20-Buendel nicht als
        Ganzes verhindern.
        """
        block: dict[str, Any] = {"columns": [], "rows": [], "truncated": False}
        sql = f"SELECT * FROM {quote_identifier(table_name)}"  # noqa: S608 - Identifier-Allowlist
        try:
            result = await self._table_store.run_readonly_query(
                workspace_id, area_id, sql, TABLE_ROW_EXPORT_CAP
            )
        except AreaStoreMissingError:
            # Kein Store-File: die Area hat nie Zeilen gesehen. Kein Fehlerfall.
            return block
        except Exception as exc:  # noqa: BLE001 - Teil-Ergebnis schlaegt Totalausfall
            logger.warning(
                "GDPR-Export: Tabelle %s (Area %s) nicht lesbar (%s) — Block bleibt leer.",
                table_name,
                area_id,
                exc.__class__.__name__,
            )
            block["error"] = exc.__class__.__name__
            return block
        block["columns"] = result.columns
        block["rows"] = result.rows
        block["truncated"] = result.truncated
        return block

    async def _export_knowledge_base(self, workspace_id: UUID) -> dict[str, Any]:
        """KB-Buendel: Nodes + Kanten + Evidence + Herkunfts-Areas + Konflikte."""
        node_rows = await self._pool.fetch(
            f"SELECT {_KB_NODE_COLUMNS} FROM kb_node WHERE workspace_id = $1 "
            "ORDER BY created_at ASC, id ASC",
            workspace_id,
        )
        block: dict[str, Any] = {"nodes": [_clean(row) for row in node_rows]}
        for key, table in _KB_TABLES:
            rows = await self._pool.fetch(
                f"SELECT * FROM {_safe_kb_table(table)} WHERE workspace_id = $1",  # noqa: S608
                workspace_id,
            )
            block[key] = [_clean(row) for row in rows]
        return block

    async def _versioned(
        self, workspace_id: UUID, entity: str, fk_column: str
    ) -> list[dict[str, Any]]:
        """Identitaets-Zeilen eines Inhalts-Aggregats inkl. aller Versionen.

        `entity` fliesst als f-String-Tabellenname ins SQL. Heute immer ein
        Literal aus dem Aufrufer — die harte `safe_entity`-Whitelist (geteilt mit
        dem Einzel-Export) erzwingt das aber als Runtime-Guard statt nur per
        Kommentar (Defense-in-Depth, Zero-Trust).
        """
        entity = safe_entity(entity)
        identity_rows = await self._pool.fetch(
            f"SELECT * FROM {entity} WHERE workspace_id = $1 ORDER BY created_at ASC, id ASC",
            workspace_id,
        )
        version_rows = await self._pool.fetch(
            f"SELECT * FROM {entity}_version WHERE workspace_id = $1 "
            f"ORDER BY {fk_column} ASC, version ASC",
            workspace_id,
        )
        versions_by_parent: dict[Any, list[dict[str, Any]]] = {}
        for row in version_rows:
            versions_by_parent.setdefault(row[fk_column], []).append(_clean(row))

        result: list[dict[str, Any]] = []
        for row in identity_rows:
            item = _clean(row)
            item["versions"] = versions_by_parent.get(row["id"], [])
            result.append(item)
        return result
