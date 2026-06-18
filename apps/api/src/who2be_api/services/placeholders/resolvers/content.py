"""Inhalts-Resolver: Playbook- und Resource-Expansion (Active-Version).

Beide filtern auf `status='active'` — analog zu den MCP-Reads im Repo.
"""

from __future__ import annotations

import logging
from uuid import UUID

import asyncpg

from who2be_api.repositories.playbook_resource_link_repository import block_section_text
from who2be_api.services.placeholders._core import (
    RenderContext,
    ResolveResult,
    block_plain_text,
)
from who2be_api.services.placeholders._scope import (
    render_visible_playbook_ids,
    render_visible_resource_ids,
)

logger = logging.getLogger(__name__)


class PlaybookResolver:
    """Expandiert `target_id` (UUID) zum Body der Active-Version des Playbooks.

    Filtert auf `status='active'` — analog zu MCP-Reads im Repo. Bei nicht
    gefunden: lokalisierter Fehler-String + Miss-Key.

    **Composite-aware (B1):** Hat das Playbook Kinder in `playbook_composition`,
    wird die Orchestrierungs-Sequenz angehaengt:
    - Composite-Body zuerst (wie bisher).
    - Dann eine `## Ablauf (Sub-Playbooks)`-Sektion mit nummerierten Kindern
      (nur aktive Versionen, geordnet nach `position`); inaktive/fehlende Kinder
      werden uebersprungen (kein Hard-Fail). Atomic-Pills bleiben unveraendert.
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"playbook:{target_id}"
        try:
            playbook_id = UUID(target_id)
        except ValueError:
            logger.warning("PlaybookResolver: ungueltige UUID '%s'", target_id)
            return ResolveResult(text="<Playbook nicht verfuegbar>", unresolved_key=miss_key)

        # Read-Scoping: ein `assigned`-Agent darf ueber ein eingebettetes Pill
        # kein nicht-zugewiesenes Playbook expandieren — sauberer Miss statt Leak.
        scope = await render_visible_playbook_ids(db, ctx)
        if scope is not None and playbook_id not in scope:
            return ResolveResult(text="<Playbook nicht verfuegbar>", unresolved_key=miss_key)

        row = await db.fetchrow(
            """
            SELECT p.name, pv.content
              FROM playbook p
              JOIN playbook_version pv
                ON pv.playbook_id = p.id AND pv.status = 'active'
             WHERE p.id = $1
               AND p.workspace_id = $2
            """,
            playbook_id,
            ctx.workspace_id,
        )
        if row is None:
            logger.info(
                "PlaybookResolver: Playbook %s nicht gefunden (Workspace %s)",
                playbook_id,
                ctx.workspace_id,
            )
            return ResolveResult(text="<Playbook nicht verfuegbar>", unresolved_key=miss_key)

        content: dict[str, object] = dict(row["content"])
        name: str = row["name"]
        description = str(content.get("description", "")).strip()
        body = str(content.get("body", "")).strip()
        lines: list[str] = [f"### {name}"]
        if description:
            lines.append(description)
        if body:
            lines.append(body)

        # --- Composite-Erweiterung (B1) ---
        # Kinder aus playbook_composition laden (nur aktive Versionen, geordnet).
        child_rows = await db.fetch(
            """
            SELECT p.name AS child_name, pv.content AS child_content
              FROM playbook_composition pc
              JOIN playbook p ON p.id = pc.child_id
              JOIN playbook_version pv
                ON pv.playbook_id = p.id AND pv.status = 'active'
             WHERE pc.parent_id = $1
               AND pc.workspace_id = $2
             ORDER BY pc.position ASC
            """,
            playbook_id,
            ctx.workspace_id,
        )
        if child_rows:
            lines.append("\n## Ablauf (Sub-Playbooks)")
            for idx, child_row in enumerate(child_rows, start=1):
                child_content: dict[str, object] = dict(child_row["child_content"])
                child_name: str = child_row["child_name"]
                child_description = str(child_content.get("description", "")).strip()
                child_body = str(child_content.get("body", "")).strip()
                child_parts: list[str] = [f"**{child_name}**"]
                if child_description:
                    child_parts.append(child_description)
                if child_body:
                    child_parts.append(child_body)
                lines.append(f"{idx}. " + " — ".join(child_parts))

        return ResolveResult(text="\n".join(lines))


class ResourceResolver:
    """Expandiert `target_id` zur Active-Version einer Resource.

    Filtert auf `status='active'` — analog zu MCP-Reads im Repo. Bei nicht
    gefunden: lokalisierter Fehler-String + Miss-Key.

    **Block-Anker (B2):** `target_id` kann eine reine Resource-UUID sein oder
    ein Section-Anker der Form `"<resource_uuid>#<block_id>"`:
    - ohne `#` (oder leerer Block-Teil) → ganze Resource (Bestandsverhalten).
    - mit `#<block_id>` → nur die Section ab dem Anker-Heading (via
      `block_section_text`). Existiert der Anker-Block in der Active-Version
      nicht → sauberer Miss (leerer Body + Miss-Key).

    Der Miss-Key bleibt in allen Faellen `f"resource:{target_id}"` (inkl.
    Anker-Suffix), damit der unresolved-Tracker das Pill eindeutig wiederfindet.
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,
    ) -> ResolveResult:
        miss_key = f"resource:{target_id}"
        resource_part, _, block_id = target_id.partition("#")
        try:
            resource_id = UUID(resource_part)
        except ValueError:
            logger.warning("ResourceResolver: ungueltige UUID '%s'", resource_part)
            return ResolveResult(text="<Resource nicht verfuegbar>", unresolved_key=miss_key)

        # Read-Scoping: nicht-zugewiesene Resource ueber ein Pill → Miss, kein Leak.
        scope = await render_visible_resource_ids(db, ctx)
        if scope is not None and resource_id not in scope:
            return ResolveResult(text="<Resource nicht verfuegbar>", unresolved_key=miss_key)

        row = await db.fetchrow(
            """
            SELECT r.name, rv.content
              FROM resource r
              JOIN resource_version rv
                ON rv.resource_id = r.id AND rv.status = 'active'
             WHERE r.id = $1
               AND r.workspace_id = $2
            """,
            resource_id,
            ctx.workspace_id,
        )
        if row is None:
            logger.info(
                "ResourceResolver: Resource %s nicht gefunden (Workspace %s)",
                resource_id,
                ctx.workspace_id,
            )
            return ResolveResult(text="<Resource nicht verfuegbar>", unresolved_key=miss_key)

        content: dict[str, object] = dict(row["content"])
        name: str = row["name"]
        # BlockNote-JSON: content.blocks Liste von Block-Dicts -> Plaintext
        raw_blocks = content.get("blocks", [])
        blocks: list[dict[str, object]] = list(raw_blocks) if isinstance(raw_blocks, list) else []

        if block_id:
            # Section-Anker: nur die Section ab dem Anker-Heading rendern.
            section_block_ids, body_text = block_section_text(blocks, block_id)
            if not section_block_ids:
                logger.info(
                    "ResourceResolver: Anker-Block '%s' in Resource %s nicht gefunden",
                    block_id,
                    resource_id,
                )
                return ResolveResult(text="", unresolved_key=miss_key)
            lines: list[str] = [f"#### {name}"]
            if body_text:
                lines.append(body_text)
            return ResolveResult(text="\n".join(lines))

        parts: list[str] = []
        for block in blocks:
            text = block_plain_text(block)
            if text:
                parts.append(text)
        body_text = "\n\n".join(parts).strip()
        lines = [f"#### {name}"]
        if body_text:
            lines.append(body_text)
        return ResolveResult(text="\n".join(lines))
