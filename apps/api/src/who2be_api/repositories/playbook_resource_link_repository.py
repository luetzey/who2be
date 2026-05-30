"""Persistenz fuer Playbook->Resource-Block-Refs (`playbook_resource_link`).

Block-Refs zeigen auf einzelne Heading-Bloecke einer Resource (ADR-0021,
Phase 3-A: Heading-Only-Anker). `list_links` reichert jeden Link an:

- `available_in='active'` wenn der Anker in der aktiven Resource-Version
  liegt; `'draft'` als Fallback auf die aktuelle (nicht-aktive) Version
  (Phase-3-A F-10); `None` wenn der Anker nirgends mehr existiert.
- `preview` (~200 Zeichen Klartext des Anker-Blocks) bleibt fuer
  Backward-Compat erhalten.
- `section_block_ids` + `section_preview` (~400 Zeichen) tragen die Section
  vom Anker-Heading bis zum naechsten Heading desselben Levels.

`set_links` fuehrt Workspace-Pruefung und Set-Replace in einer Transaktion
aus (`FOR UPDATE` auf der Playbook-Zeile); die Composite-FKs aus 0016
erzwingen DB-seitig die Workspace-Bindung.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID

import asyncpg

from who2be_models import ResourceLinkItem, ResourceLinkRead

_PREVIEW_LEN = 200
_SECTION_PREVIEW_LEN = 400
_HEADING_TYPE = "heading"
# BlockNote-Default fuer ein Heading ohne `props.level` — entspricht <h1>.
_DEFAULT_HEADING_LEVEL = 1


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


def _heading_level(block: dict[str, Any]) -> int:
    """Liest `props.level` eines Heading-Blocks; Default 1 (BlockNote-h1)."""
    props = block.get("props")
    if isinstance(props, dict):
        level = props.get("level")
        if isinstance(level, int):
            return level
    return _DEFAULT_HEADING_LEVEL


def is_heading_block(block: dict[str, Any]) -> bool:
    """True, wenn der Block ein BlockNote-Heading ist."""
    return isinstance(block, dict) and block.get("type") == _HEADING_TYPE


def block_section_text(blocks: list[dict[str, Any]], anchor_block_id: str) -> tuple[list[str], str]:
    """Sammelt eine Section ab dem Anker-Heading.

    Liefert `(block_ids, preview_text)`:
    - Anker-Block nicht gefunden → `([], "")`.
    - Anker kein Heading → fallback auf nur den Anker-Block (defensive
      Lese-Schicht; die Heading-Pflicht greift im Service vor dem PUT).
    - Anker ist Heading → alle Bloecke vom Anker (inkl.) bis exklusive zum
      naechsten Heading mit dem gleichen `props.level`. Tiefere Headings
      (groesseres Level) bleiben in der Section.

    `preview_text` ist der mit `"\\n\\n"` verbundene Klartext der Section,
    abgeschnitten auf `_SECTION_PREVIEW_LEN` Zeichen.
    """
    anchor_index = next(
        (i for i, b in enumerate(blocks) if isinstance(b, dict) and b.get("id") == anchor_block_id),
        None,
    )
    if anchor_index is None:
        return [], ""

    anchor = blocks[anchor_index]
    if not is_heading_block(anchor):
        text = block_plain_text(anchor)
        return [anchor_block_id], text[:_SECTION_PREVIEW_LEN]

    anchor_level = _heading_level(anchor)
    section: list[dict[str, Any]] = [anchor]
    for block in blocks[anchor_index + 1 :]:
        if not isinstance(block, dict):
            continue
        if is_heading_block(block) and _heading_level(block) == anchor_level:
            break
        section.append(block)

    block_ids = [block_id for block in section if isinstance(block_id := block.get("id"), str)]
    chunks = [block_plain_text(block) for block in section]
    text = "\n\n".join(chunk for chunk in chunks if chunk)
    return block_ids, text[:_SECTION_PREVIEW_LEN]


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

    async def load_resource_blocks(
        self, workspace_id: UUID, resource_ids: Sequence[UUID]
    ) -> dict[UUID, list[dict[str, Any]]]: ...

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
        # Zwei LEFT JOINs: bevorzugt die Active-Version, fallback auf die
        # Current-Version (egal welcher Status). Der Block-Match entscheidet
        # pro Link, ob `available_in` 'active' oder 'draft' wird. Fuer
        # 'resource'-Scope-Links existiert kein Block-Anker; die Verfuegbarkeit
        # ergibt sich aus dem schieren Vorhandensein der Active/Current-Version.
        rows = await self._pool.fetch(
            "SELECT prl.resource_id, prl.block_id, prl.position, prl.link_scope, "
            "       r.name AS resource_name, "
            "       rva.content AS active_content, "
            "       rvc.content AS current_content "
            "FROM playbook_resource_link prl "
            "JOIN resource r ON r.id = prl.resource_id "
            "LEFT JOIN resource_version rva "
            "  ON rva.resource_id = r.id AND rva.status = 'active' "
            "LEFT JOIN resource_version rvc "
            "  ON rvc.resource_id = r.id AND rvc.version = r.current_version "
            "WHERE prl.playbook_id = $1 AND prl.workspace_id = $2 "
            "ORDER BY prl.position, prl.resource_id, "
            "         COALESCE(prl.block_id, '')",
            playbook_id,
            workspace_id,
        )
        return [self._to_link_read(row) for row in rows]

    async def load_resource_blocks(
        self, workspace_id: UUID, resource_ids: Sequence[UUID]
    ) -> dict[UUID, list[dict[str, Any]]]:
        """Lookup-Helper fuer den Service: Block-Liste pro Resource — Active
        wenn vorhanden, sonst Current. Resources, die keinem Workspace gehoeren
        oder ohne Version existieren, sind im Ergebnis schlicht abwesend.
        """
        ids = list(set(resource_ids))
        if not ids:
            return {}
        rows = await self._pool.fetch(
            "SELECT r.id AS resource_id, "
            "       COALESCE(rva.content, rvc.content) AS content "
            "FROM resource r "
            "LEFT JOIN resource_version rva "
            "  ON rva.resource_id = r.id AND rva.status = 'active' "
            "LEFT JOIN resource_version rvc "
            "  ON rvc.resource_id = r.id AND rvc.version = r.current_version "
            "WHERE r.workspace_id = $1 AND r.id = ANY($2::uuid[])",
            workspace_id,
            ids,
        )
        result: dict[UUID, list[dict[str, Any]]] = {}
        for row in rows:
            content = row["content"]
            if isinstance(content, dict):
                blocks = content.get("blocks", [])
                result[row["resource_id"]] = [b for b in blocks if isinstance(b, dict)]
            else:
                result[row["resource_id"]] = []
        return result

    @staticmethod
    def _to_link_read(row: asyncpg.Record) -> ResourceLinkRead:
        link_scope: Literal["resource", "block"] = row["link_scope"]
        anchor_id = row["block_id"]
        active_content = row["active_content"]
        current_content = row["current_content"]
        active_blocks = _blocks_of(active_content)
        current_blocks = _blocks_of(current_content)

        if link_scope == "resource":
            # Ganzes Dokument referenziert: Verfuegbarkeit haengt nur an der
            # Existenz einer Active- bzw. Current-Version, kein Section-Match.
            available_in: Literal["active", "draft"] | None
            if active_content is not None:
                available_in = "active"
            elif current_content is not None:
                available_in = "draft"
            else:
                available_in = None
            return ResourceLinkRead(
                resource_id=row["resource_id"],
                resource_name=row["resource_name"],
                block_id=None,
                position=row["position"],
                available=available_in is not None,
                available_in=available_in,
                preview=None,
                section_block_ids=[],
                section_preview=None,
                link_scope="resource",
            )

        # Bevorzugt Active; nur fallback auf Current, wenn der Anker dort
        # nicht (mehr) gefunden wird. So sieht das UI fuer eine Resource mit
        # Active+Draft den Active-Stand und kippt nur dann auf "Nur in Draft",
        # wenn der Block in Active nicht mehr existiert.
        match_blocks: list[dict[str, Any]] | None = None
        available_in = None
        if any(b.get("id") == anchor_id for b in active_blocks):
            match_blocks = active_blocks
            available_in = "active"
        elif any(b.get("id") == anchor_id for b in current_blocks):
            match_blocks = current_blocks
            available_in = "draft"

        preview: str | None = None
        section_block_ids: list[str] = []
        section_preview: str | None = None
        if match_blocks is not None and anchor_id is not None:
            anchor = next(b for b in match_blocks if b.get("id") == anchor_id)
            text = block_plain_text(anchor)
            preview = text[:_PREVIEW_LEN] if text else None
            ids, section_text = block_section_text(match_blocks, anchor_id)
            section_block_ids = ids
            section_preview = section_text or None
        return ResourceLinkRead(
            resource_id=row["resource_id"],
            resource_name=row["resource_name"],
            block_id=anchor_id,
            position=row["position"],
            available=available_in is not None,
            available_in=available_in,
            preview=preview,
            section_block_ids=section_block_ids,
            section_preview=section_preview,
            link_scope="block",
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
                    "SELECT id FROM resource WHERE workspace_id = $1 AND id = ANY($2::uuid[])",
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
                    "(playbook_id, resource_id, block_id, workspace_id, "
                    " owner_id, position, link_scope) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    [
                        (
                            playbook_id,
                            item.resource_id,
                            item.block_id,
                            workspace_id,
                            owner_id,
                            item.position,
                            item.link_scope,
                        )
                        for item in items
                    ],
                )
        return SetLinksResult(playbook_found=True)


def _blocks_of(content: Any) -> list[dict[str, Any]]:
    """Extrahiert die Block-Liste eines `resource_version.content`-Felds."""
    if not isinstance(content, dict):
        return []
    blocks = content.get("blocks", [])
    if not isinstance(blocks, list):
        return []
    return [b for b in blocks if isinstance(b, dict)]
