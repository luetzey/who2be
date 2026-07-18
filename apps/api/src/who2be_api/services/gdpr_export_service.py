"""GDPR-Datenexport (Track O, Plan §3.2 / DSGVO Art. 20 — Datenuebertragbarkeit).

Sammelt das vollstaendige Daten-Buendel des Users: alle Organizations +
Workspaces, in denen er Mitglied ist, samt Personas/Playbooks/Resources/Agents
und deren Versionen.

RLS-Konformitaet: die Control-plane-Tabellen (organization/workspace/
workspace_member) tragen kein RLS und werden direkt gelesen. Die
workspace-scoped Inhalts-Tabellen sind unter RLS nur **innerhalb** des jeweiligen
Mandanten sichtbar — deshalb betritt der Export pro Workspace `tenant_scope`
und liest die Inhalte dort. So funktioniert der Export identisch unter der
App-Rolle (`who2be_app`) wie unter dem Owner.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg

from who2be_api.core.tenancy import tenant_scope
from who2be_api.services.entity_sql import safe_entity

# Tabellen, deren interne Mandanten-Spalte aus dem Export entfernt wird.
_INTERNAL_COLUMNS = frozenset({"workspace_id"})

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


class GdprExportService:
    """Baut das exportierbare JSON-Buendel eines Users."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

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
        }

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
