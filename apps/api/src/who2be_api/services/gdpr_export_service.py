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
from who2be_api.core.tenancy import tenant_scope
from who2be_api.services.tablestore_provider import get_table_store
from who2be_api.tablestore import AreaStoreMissingError, TableStore, quote_identifier

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

# KB-Zusatztabellen ohne generierte Spalten — `SELECT *` ist hier sicher.
_KB_TABLES: tuple[tuple[str, str], ...] = (
    ("edges", "kb_edge"),
    ("edge_evidence", "kb_edge_evidence"),
    ("node_source_areas", "kb_node_source_area"),
    ("conflicts", "kb_conflict"),
)

# `kb_node` traegt eine generierte `search`-tsvector-Spalte (Migration 0077) —
# Index-Material, kein Nutzdatum. Deshalb explizite Spaltenliste statt `*`
# (Muster: `agent_memory` oben).
_KB_NODE_COLUMNS = (
    "id, workspace_id, tier, content, content_ref, source_ref, source_ref_kind, "
    "ttl_expires_at, status, derivation_depth, sensitivity, occurred_at, "
    "occurred_precision, created_by, created_at, updated_at"
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

        Liest aus `auth.users` (Schema gehoert GoTrue). Robust gegen fehlende
        `auth.users` in Test-DBs oder eingeschraenkten Berechtigungen — Muster
        analog `repositories/me_repository._lookup_email`: bei PostgresError
        wird ein leerer Account-Block zurueckgegeben, statt den ganzen Export
        scheitern zu lassen.
        """
        block: dict[str, Any] = {
            "id": str(user_id),
            "email": None,
            "created_at": None,
            "last_sign_in_at": None,
        }
        try:
            row = await self._pool.fetchrow(
                "SELECT email, created_at, last_sign_in_at FROM auth.users WHERE id = $1",
                user_id,
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
            # Explizite Spalten statt `*`: die generierte tsvector-Spalte
            # `search` ist internes Index-Material, kein Nutzdatum.
            memories = await self._pool.fetch(
                "SELECT id, workspace_id, agent_id, status, fact, context, category, "
                "importance, source, triage_note, retrieval_count, last_retrieved_at, "
                "created_at, updated_at "
                "FROM agent_memory WHERE workspace_id = $1 ORDER BY created_at ASC, id ASC",
                workspace_id,
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
            "agent_memories": [_clean(row) for row in memories],
            "work_areas": work_areas,
            "wa_blobs": {"note": _BLOB_EXPORT_NOTE, "items": blobs},
            "wa_tables": tables,
            "knowledge_base": knowledge_base,
            "agent_access_log": [_clean(row) for row in access_log],
        }

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
