"""Einzel-Element-Export fuer Persona / Playbook / Resource (ADR-0032).

Zwei Formate pro Element:

- `export_json` — die Identitaets-Zeile plus *alle* Versionen eines einzelnen
  Aggregats, ohne interne Mandanten-Spalten (`workspace_id`). Spiegelt den
  `_clean`/`_versioned`-Aufbau aus `GdprExportService`, aber gefiltert auf eine
  einzige ID.
- `export_markdown` — der gerenderte Body der **aktiven** Version (sonst der
  neuesten) mit YAML-Frontmatter (`name`/`status`/`tags` und je nach Entity
  `type`). Die Placeholder-Expansion laeuft ueber den **vorhandenen**
  `render_template_body`-Kern (denselben, den `PersonaService.render` und
  `PlaybookService.render` nutzen) — keine Render-Logik dupliziert.

RLS-Konformitaet: der Aufruf laeuft innerhalb des Request-Scopes, den
`get_current_workspace` bereits via `tenant_scope(workspace_id, org_id)` gesetzt
hat — die App-Connection traegt also `app.current_tenant`/`app.current_org` und
sieht die workspace-scoped Inhalts-Tabellen. Eine erneute, org-lose
`tenant_scope`-Schicht waere falsch (sie wuerde `app.current_org` auf NULL
zuruecksetzen). Die `WHERE workspace_id = $`-Filter bleiben als erste
Verteidigungslinie. Lesen ist fuer Viewer offen (kein `require_role`); der
Router gated nur auf Workspace-Mitgliedschaft.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg

from who2be_api.core.entity_sql import EntityKind, safe_entity
from who2be_api.services.placeholders import RenderContext, render_template_body

# Tabellen-/FK-/Inhalts-Konfiguration je Entity. `body_blocks` extrahiert aus
# dem Versions-`content`-jsonb das BlockNote-Dokument als Block-Liste, die der
# Renderer erwartet (Top-Level-Array). Playbook fuehrt das Dokument als
# stringifizierten `body`; Persona/Resource als `blocks`-Array.
_INTERNAL_COLUMNS = frozenset({"workspace_id"})


def _clean(row: asyncpg.Record) -> dict[str, Any]:
    """Record -> dict, ohne interne Mandanten-Spalten (wie GdprExportService)."""
    return {key: value for key, value in dict(row).items() if key not in _INTERNAL_COLUMNS}


def _persona_blocks(content: dict[str, Any]) -> list[dict[str, Any]]:
    nested = content.get("content")
    if isinstance(nested, dict):
        blocks = nested.get("blocks", [])
        return blocks if isinstance(blocks, list) else []
    return []


def _resource_blocks(content: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = content.get("blocks", [])
    return blocks if isinstance(blocks, list) else []


class EntityExportService:
    """Baut JSON- und Markdown-Export eines einzelnen Aggregats."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def export_json(
        self, workspace_id: UUID, entity: EntityKind, entity_id: UUID
    ) -> dict[str, Any] | None:
        """Identitaets-Zeile + alle Versionen eines Aggregats (oder None ⇒ 404)."""
        entity = safe_entity(entity)
        fk_column = f"{entity}_id"
        identity = await self._pool.fetchrow(
            f"SELECT * FROM {entity} WHERE id = $1 AND workspace_id = $2",
            entity_id,
            workspace_id,
        )
        if identity is None:
            return None
        version_rows = await self._pool.fetch(
            f"SELECT * FROM {entity}_version WHERE {fk_column} = $1 "
            "ORDER BY version ASC, locale ASC",
            entity_id,
        )
        item = _clean(identity)
        item["versions"] = [_clean(row) for row in version_rows]
        return {
            "exported_at": datetime.now(UTC),
            "entity": entity,
            entity: item,
        }

    async def export_markdown(
        self, workspace_id: UUID, entity: EntityKind, entity_id: UUID
    ) -> str | None:
        """Gerenderter Body der aktiven (sonst neuesten) Version als Markdown.

        Liefert None, wenn das Aggregat im Workspace nicht existiert (⇒ 404).
        """
        entity = safe_entity(entity)
        identity = await self._pool.fetchrow(
            f"SELECT name FROM {entity} WHERE id = $1 AND workspace_id = $2",
            entity_id,
            workspace_id,
        )
        if identity is None:
            return None
        # Aktive Version bevorzugt; sonst die hoechste Versionsnummer.
        version = await self._pool.fetchrow(
            f"SELECT content, status, version "
            f"FROM {entity}_version WHERE {entity}_id = $1 "
            "ORDER BY (status = 'active') DESC, version DESC "
            "LIMIT 1",
            entity_id,
        )
        content: dict[str, Any] = {}
        status_value = ""
        if version is not None:
            raw = version["content"]
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            content = parsed if isinstance(parsed, dict) else {}
            status_value = version["status"]

        body_rendered = await self._render_body(workspace_id, entity, content)

        tags = content.get("tags", [])
        frontmatter: dict[str, Any] = {
            "name": identity["name"],
            "status": status_value,
            "tags": tags if isinstance(tags, list) else [],
        }
        if entity == "playbook":
            frontmatter["type"] = content.get("type", "")
        return _render_markdown(frontmatter, body_rendered)

    async def _render_body(
        self, workspace_id: UUID, entity: EntityKind, content: dict[str, Any]
    ) -> str:
        """Expandiert den BlockNote-Body ueber den vorhandenen Renderer-Kern."""
        if entity in ("playbook", "external_tool"):
            # Playbook fuehrt den Body als `body`, ExternalTool als `usage_notes`
            # — beide sind ein stringifiziertes BlockNote-JSON-Dokument.
            field = "body" if entity == "playbook" else "usage_notes"
            body_text = content.get(field, "")
            if not isinstance(body_text, str):
                body_text = ""
        elif entity == "persona":
            body_text = json.dumps(_persona_blocks(content))
        else:
            body_text = json.dumps(_resource_blocks(content))

        render_ctx = RenderContext(
            workspace_id=workspace_id, persona_id=None, now=datetime.now(UTC)
        )
        async with self._pool.acquire() as conn:
            rendered, _unresolved = await render_template_body(body_text, render_ctx, conn)
        return rendered


def _yaml_scalar(value: Any) -> str:
    """Minimaler YAML-Scalar fuer Frontmatter (Strings doppelt gequotet)."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render_markdown(frontmatter: dict[str, Any], body: str) -> str:
    """Baut das Markdown-Dokument: YAML-Frontmatter + Body."""
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                lines.extend(f"  - {_yaml_scalar(item)}" for item in value)
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)
