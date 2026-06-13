"""Katalog-Resolver: Briefing-Tabellen der zugeordneten Playbooks / Resources."""

from __future__ import annotations

import logging
import re

import asyncpg

from who2be_api.services.placeholders._core import (
    RenderContext,
    ResolveResult,
    table_cell,
)

logger = logging.getLogger(__name__)

# Obergrenze fuer Katalog-Tabellen (DoS-Schutz gegen riesige Agenten-Prompts).
_CATALOG_LIMIT = 100


def _normalize_triggers(raw: str | None) -> str:
    """Zerlegt die freitext-Trigger-Spalte (Komma/Newline) zu ``"t1, t2"``."""
    if not raw:
        return ""
    tokens = [t.strip() for t in re.split(r"[,\n]", raw) if t.strip()]
    return ", ".join(tokens)


class PlaybooksCatalogResolver:
    """Expandiert zu einer Briefing-**Tabelle** der dem Agenten zugeordneten Playbooks.

    Quelle: die der Persona des Agenten verknuepften Playbooks (`persona_playbook`),
    jeweils Active-Version (`status='active'`) — konsistent mit den MCP-Reads und
    der Applied-Pill.

    `target_id` steuert den Filter (Pill-Setting):
    - ``"triggered"`` → nur Playbooks mit nicht-leerem Trigger-Feld.
    - ``""`` / ``"all"`` / sonstiges → alle verknuepften aktiven Playbooks.

    Spalten: **Playbook | Trigger | Aufruf | Beschreibung**. Die `Aufruf`-Spalte
    enthaelt den konkreten MCP-Call (`fetch_playbook("<id>")`), damit der Agent
    unmittelbar handlungsfaehig ist.

    Verhalten:
    - `ctx.persona_id` ist None → Miss (im Editor-Preview ohne Persona-Kontext
      zeigt das den Laufzeit-Hinweis; nie eine irrefuehrend leere Tabelle).
    - Persona vorhanden, aber keine (passenden) Playbooks → kurzer Hinweistext
      (kein Miss).
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"playbooks-catalog:{target_id}"
        if ctx.persona_id is None:
            logger.info("PlaybooksCatalogResolver: ctx.persona_id ist None — Miss")
            return ResolveResult(text="", unresolved_key=miss_key)

        only_triggered = target_id == "triggered"

        rows = await db.fetch(
            """
            SELECT p.id, p.name, p.triggers, pv.content
              FROM persona_playbook pp
              JOIN playbook p ON p.id = pp.playbook_id
              JOIN playbook_version pv
                ON pv.playbook_id = p.id AND pv.status = 'active'
             WHERE pp.persona_id = $1
               AND p.workspace_id = $2
             ORDER BY p.created_at DESC
            """,
            ctx.persona_id,
            ctx.workspace_id,
        )

        entries: list[tuple[str, str, str, str]] = []
        for row in rows:
            triggers = _normalize_triggers(row["triggers"])
            if only_triggered and not triggers:
                continue
            content: dict[str, object] = dict(row["content"]) if row["content"] else {}
            description = str(content.get("description", "")).strip()
            entries.append(
                (
                    str(row["name"]),
                    triggers,
                    f'fetch_playbook("{row["id"]}")',
                    description,
                )
            )

        if not entries:
            if only_triggered:
                return ResolveResult(
                    text="_Dir sind aktuell keine Playbooks mit Triggern zugeordnet._"
                )
            return ResolveResult(text="_Dir sind aktuell keine Playbooks zugeordnet._")

        lines = [
            "## Deine Playbooks",
            (
                "Diese Playbooks stehen dir zur Verfuegung. Wenn der Nutzer eines der "
                "Trigger-Stichworte anspricht, lade das Playbook ueber die Aufruf-Spalte "
                "(`fetch_playbook(...)`) und folge seinen Schritten."
            ),
            "",
            "| Playbook | Trigger | Aufruf | Beschreibung |",
            "|---|---|---|---|",
        ]
        for name, triggers, call, description in entries:
            lines.append(
                f"| {table_cell(name)} | {table_cell(triggers)} "
                f"| `{call}` | {table_cell(description)} |"
            )
        return ResolveResult(text="\n".join(lines))


class ResourcesCatalogResolver:
    """Expandiert zu einer Briefing-**Tabelle** der aktiven Resources des Workspace.

    Quelle: alle Resources des Workspace in ihrer Active-Version
    (`status='active'`) — konsistent mit `list_resources` und den MCP-Reads.
    Im Gegensatz zur `playbooks-catalog`-Pill ist **kein** Persona-Kontext noetig
    (Resources haengen nicht an der Persona), daher gibt es hier nie einen
    Persona-Miss.

    `target_id` steuert den Filter (Pill-Setting):
    - ``""`` / ``"all"`` → alle aktiven Resources.
    - sonst → nur Resources, deren `content.tags` den Wert (exakt) enthalten.

    Spalten: **Resource | Tags | Aufruf | Beschreibung**. Die `Aufruf`-Spalte
    enthaelt den konkreten MCP-Call (`fetch_resource("<id>")`), damit der Agent
    unmittelbar handlungsfaehig ist.

    Verhalten:
    - Keine (passenden) Resources → kurzer Hinweistext (kein Miss).
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        tag = target_id.strip()
        tag_filter = None if tag in ("", "all") else tag

        # Deckel gegen aufgeblaehte Agenten-Prompts (Self-DoS): bei mehr aktiven
        # Resources als `_CATALOG_LIMIT` werden nur die juengsten gelistet und ein
        # „… und N weitere"-Hinweis angehaengt. `+ 1`-Peek erkennt den Overflow.
        rows = await db.fetch(
            """
            SELECT r.id, r.name, rv.content
              FROM resource r
              JOIN resource_version rv
                ON rv.resource_id = r.id AND rv.status = 'active'
             WHERE r.workspace_id = $1
               AND ($2::text IS NULL OR $2 = ANY(
                   SELECT jsonb_array_elements_text(rv.content->'tags')))
             ORDER BY r.created_at DESC
             LIMIT $3
            """,
            ctx.workspace_id,
            tag_filter,
            _CATALOG_LIMIT + 1,
        )
        overflow = len(rows) > _CATALOG_LIMIT
        rows = rows[:_CATALOG_LIMIT]

        entries: list[tuple[str, str, str, str]] = []
        for row in rows:
            content: dict[str, object] = dict(row["content"]) if row["content"] else {}
            description = str(content.get("description", "")).strip()
            raw_tags = content.get("tags", [])
            tags_list = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
            entries.append(
                (
                    str(row["name"]),
                    ", ".join(tags_list),
                    f'fetch_resource("{row["id"]}")',
                    description,
                )
            )

        if not entries:
            if tag_filter is not None:
                return ResolveResult(text=f"_Keine aktiven Resources mit dem Tag „{tag_filter}“._")
            return ResolveResult(text="_Im Workspace gibt es aktuell keine aktiven Resources._")

        scope_note = (
            f"Wissens-Resources mit dem Tag „{tag_filter}“."
            if tag_filter is not None
            else "Diese Wissens-Resources stehen dir im Workspace zur Verfuegung."
        )
        lines = [
            "## Verfuegbare Resources",
            (
                f"{scope_note} Lade eine Resource ueber die Aufruf-Spalte "
                "(`fetch_resource(...)`), wenn du ihren Inhalt brauchst."
            ),
            "",
            "| Resource | Tags | Aufruf | Beschreibung |",
            "|---|---|---|---|",
        ]
        for name, tags_str, call, description in entries:
            lines.append(
                f"| {table_cell(name)} | {table_cell(tags_str)} "
                f"| `{call}` | {table_cell(description)} |"
            )
        if overflow:
            lines.append("")
            lines.append(
                f"_… und weitere — gefiltert auf die {_CATALOG_LIMIT} juengsten Resources. "
                "Nutze `list_resources(tag?)` fuer den vollstaendigen Katalog._"
            )
        return ResolveResult(text="\n".join(lines))
