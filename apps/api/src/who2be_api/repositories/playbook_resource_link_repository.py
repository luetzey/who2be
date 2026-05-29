"""Persistenz fuer Playbook->Resource-Block-Refs (`playbook_resource_link`).

Block-Refs zeigen auf einzelne Bloecke einer Resource (ADR-0021); sie loesen
immer gegen die **aktive** Resource-Version auf. `list_links` reichert jeden
Link um `available` (existiert der Block in der aktiven Version?) und eine
Plain-Text-`preview` (erste 200 Zeichen) an.

`set_links` fuehrt Workspace-Pruefung und Set-Replace in einer Transaktion aus
(`FOR UPDATE` auf der Playbook-Zeile), analog `persona_playbook_repository`.
Die Composite-FKs aus 0016 erzwingen DB-seitig die Workspace-Bindung.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

import asyncpg

from who2be_models import ResourceLinkItem, ResourceLinkRead

_PREVIEW_LEN = 200


def block_plain_text(block: dict[str, Any]) -> str:
    """Sammelt rekursiv alle `text`-Felder eines BlockNote-Blocks ein.

    BlockNote-Inline-Content liegt unter `content`/`children` als verschachtelte
    Liste von `{type, text|content, …}`-Knoten. Wir ziehen nur die Klartext-
    Anteile heraus — kein HTML, keine Styles (kein Leak ueber die Vorschau).
    """

    parts: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if isinstance(node, dict):
            text = node.get("text")
            if isinstance(text, str):
                parts.append(text)
            _walk(node.get("content"))
            _walk(node.get("children"))

    _walk(block.get("content"))
    _walk(block.get("children"))
    return "".join(parts)


@dataclass(frozen=True)
class SetLinksResult:
    """Ergebnis einer atomaren `set_links`-Operation.

    Erfolg, wenn `playbook_found` True und `missing_resource_ids` leer ist.
    """

    playbook_found: bool
    missing_resource_ids: list[UUID] = field(default_factory=list)


class PlaybookResourceLinkRepository(Protocol):
    """Service-seitige Abstraktion fuer Playbook-Resource-Block-Refs."""

    async def list_links(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[ResourceLinkRead] | None: ...

    async def set_links(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        links: Sequence[ResourceLinkItem],
    ) -> SetLinksResult: ...


class PgPlaybookResourceLinkRepository:
    """asyncpg-Implementierung von `PlaybookResourceLinkRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_links(
        self, workspace_id: UUID, playbook_id: UUID
    ) -> list[ResourceLinkRead] | None:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM playbook WHERE id = $1 AND workspace_id = $2",
            playbook_id,
            workspace_id,
        )
        if owned is None:
            return None
        # LEFT JOIN auf die aktive Version: fehlt sie (Resource ohne Active),
        # ist `active_content` NULL und alle Bloecke gelten als unavailable.
        rows = await self._pool.fetch(
            "SELECT prl.resource_id, prl.block_id, prl.position, "
            "       r.name AS resource_name, rv.content AS active_content "
            "FROM playbook_resource_link prl "
            "JOIN resource r ON r.id = prl.resource_id "
            "LEFT JOIN resource_version rv "
            "  ON rv.resource_id = r.id AND rv.status = 'active' "
            "WHERE prl.playbook_id = $1 AND prl.workspace_id = $2 "
            "ORDER BY prl.position, prl.resource_id, prl.block_id",
            playbook_id,
            workspace_id,
        )
        return [self._to_link_read(row) for row in rows]

    @staticmethod
    def _to_link_read(row: asyncpg.Record) -> ResourceLinkRead:
        content = row["active_content"]
        blocks = content.get("blocks", []) if isinstance(content, dict) else []
        match = next(
            (b for b in blocks if isinstance(b, dict) and b.get("id") == row["block_id"]),
            None,
        )
        preview: str | None = None
        if match is not None:
            text = block_plain_text(match)
            preview = text[:_PREVIEW_LEN] if text else None
        return ResourceLinkRead(
            resource_id=row["resource_id"],
            resource_name=row["resource_name"],
            block_id=row["block_id"],
            position=row["position"],
            available=match is not None,
            preview=preview,
        )

    async def set_links(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        playbook_id: UUID,
        links: Sequence[ResourceLinkItem],
    ) -> SetLinksResult:
        items = list(links)
        resource_ids = list({item.resource_id for item in items})
        async with self._pool.acquire() as conn, conn.transaction():
            playbook = await conn.fetchval(
                "SELECT 1 FROM playbook WHERE id = $1 AND workspace_id = $2 FOR UPDATE",
                playbook_id,
                workspace_id,
            )
            if playbook is None:
                return SetLinksResult(playbook_found=False)
            if resource_ids:
                owned_rows = await conn.fetch(
                    "SELECT id FROM resource "
                    "WHERE workspace_id = $1 AND id = ANY($2::uuid[])",
                    workspace_id,
                    resource_ids,
                )
                owned = {row["id"] for row in owned_rows}
                missing = [rid for rid in resource_ids if rid not in owned]
                if missing:
                    return SetLinksResult(playbook_found=True, missing_resource_ids=missing)
            await conn.execute(
                "DELETE FROM playbook_resource_link WHERE playbook_id = $1", playbook_id
            )
            if items:
                await conn.executemany(
                    "INSERT INTO playbook_resource_link "
                    "(playbook_id, resource_id, block_id, workspace_id, owner_id, position) "
                    "VALUES ($1, $2, $3, $4, $5, $6)",
                    [
                        (
                            playbook_id,
                            item.resource_id,
                            item.block_id,
                            workspace_id,
                            owner_id,
                            item.position,
                        )
                        for item in items
                    ],
                )
        return SetLinksResult(playbook_found=True)
