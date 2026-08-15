"""Persistenz fuer das Agent-Aggregat.

Agents sind die Top-Level-Konfiguration der Phase-3-Runde-3-Domain (Track 3):
genau eine Persona, genau ein Template, optionaler Status. Keine
Versionshistorie — direkte UPDATEs auf `agent`.

Die Composite-FKs (workspace_id, persona_id) / (workspace_id, template_id)
aus Migration 0023 erzwingen, dass Persona + Template aus demselben
Workspace stammen. INSERT/UPDATE bekommen daher nur die `workspace_id` des
Aufrufers; Cross-Workspace-Verweise werden DB-seitig abgewiesen.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import AgentRead, AgentStatus, AgentToolPolicy


@dataclass(frozen=True)
class AgentListMeta:
    """Denormalisierte List-Card-Pills eines Agenten (Batch-Aggregat).

    Von `list_meta` pro Agent-ID geliefert und im Service in das `AgentRead`
    gejoint. `persona_name`/`template_name` sind None, solange kein Persona/
    Template verknuepft ist; `template_version` traegt die aktive Template-
    Version (None ohne aktive Version). `playbook_count` zaehlt die Playbooks
    der verknuepften Persona (`persona_playbook`); `pending_memory_count` die
    Gedaechtnis-Vorschlaege in der Freigabe-Schleuse (`agent_memory.status=
    'pending'`, ADR-0044).
    """

    persona_name: str | None
    template_name: str | None
    template_version: int | None
    playbook_count: int
    pending_memory_count: int


# `persona_active` wird per EXISTS-Subquery auf `persona_version.status='active'`
# mitgelesen — so kennt jedes AgentRead die Aktivierbarkeit ohne Extra-Roundtrip.
# Ein Agent ohne Persona (`persona_id IS NULL`) ergibt korrekt False.
_PERSONA_ACTIVE_EXPR = """
    EXISTS (
        SELECT 1 FROM persona_version pv
        WHERE pv.persona_id = {col} AND pv.status = 'active'
    )
"""

_SELECT = f"""
    SELECT a.id, a.workspace_id, a.owner_id, a.name, a.description,
           a.persona_id, a.system_prompt_template_id, a.status, a.tool_policy,
           a.is_managed, a.model_provider, a.model_name,
           a.created_at, a.updated_at,
           {_PERSONA_ACTIVE_EXPR.format(col="a.persona_id")} AS persona_active
    FROM agent a
"""

# RETURNING fuer INSERT/UPDATE — identische Spalten wie `_SELECT` (ohne `a.`-Alias,
# da `RETURNING` auf der Ziel-Tabelle operiert), inkl. `persona_active`. Die
# Korrelation muss `agent.persona_id` qualifizieren: unqualifiziert wuerde
# `persona_id` in der Subquery auf `persona_version.persona_id` aufloesen.
_RETURNING = f"""
    RETURNING id, workspace_id, owner_id, name, description,
              persona_id, system_prompt_template_id, status, tool_policy,
              is_managed, model_provider, model_name, created_at, updated_at,
              {_PERSONA_ACTIVE_EXPR.format(col="agent.persona_id")} AS persona_active
"""


class AgentRepository(Protocol):
    """Service-seitige Abstraktion."""

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        description: str,
        persona_id: UUID | None,
        template_id: UUID | None,
        status: AgentStatus,
        tool_policy: AgentToolPolicy,
    ) -> AgentRead | None: ...

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[AgentRead]: ...

    async def fetch(self, workspace_id: UUID, agent_id: UUID) -> AgentRead | None: ...

    async def list_meta(
        self, workspace_id: UUID, agent_ids: list[UUID]
    ) -> dict[UUID, AgentListMeta]: ...

    async def deep_copy(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        source_persona_id: UUID,
        source_template_id: UUID,
        new_slug: str,
        agent_name: str,
        description: str,
        status: AgentStatus,
        tool_policy: AgentToolPolicy,
    ) -> AgentRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        name: str | None,
        description: str | None,
        persona_id: UUID | None,
        template_id: UUID | None,
        status: AgentStatus | None,
        tool_policy: AgentToolPolicy | None,
        model_provider: str | None = None,
        model_name: str | None = None,
    ) -> AgentRead | None: ...

    async def delete(self, workspace_id: UUID, agent_id: UUID) -> bool: ...

    async def persona_has_active_version(self, workspace_id: UUID, persona_id: UUID) -> bool: ...


class PgAgentRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        name: str,
        description: str,
        persona_id: UUID | None,
        template_id: UUID | None,
        status: AgentStatus,
        tool_policy: AgentToolPolicy,
    ) -> AgentRead | None:
        try:
            row = await self._pool.fetchrow(
                "INSERT INTO agent (workspace_id, owner_id, name, description, "
                "  persona_id, system_prompt_template_id, status, tool_policy) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
                f"{_RETURNING}",
                workspace_id,
                owner_id,
                name,
                description,
                persona_id,
                template_id,
                status.value,
                tool_policy.model_dump(mode="json"),
            )
        except asyncpg.ForeignKeyViolationError:
            # Composite-FK auf persona/template ausgeloest — Referenz lebt
            # nicht im gleichen Workspace (oder wurde geloescht).
            return None
        return AgentRead.model_validate(dict(row))

    async def deep_copy(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        source_persona_id: UUID,
        source_template_id: UUID,
        new_slug: str,
        agent_name: str,
        description: str,
        status: AgentStatus,
        tool_policy: AgentToolPolicy,
    ) -> AgentRead | None:
        """Tiefe Kopie eines verwalteten Agenten (Builder-Voll-Klon).

        Persona, die daran geknuepften Playbooks und das Template werden als
        unverwaltete, editierbare v1-active-Aggregate dupliziert (Inhalt der
        jeweils aktiven Quell-Version), dann ein unverwalteter Agent darauf
        gezeigt. Alles in einer Transaktion. `workspace_id` der Versions-Zeilen
        fuellt der 0035-Trigger. Gibt None zurueck, wenn Persona/Template der
        Quelle nicht (mehr) im Workspace liegen.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            # ADR-0045: die Kopie uebernimmt die Entity-Sprache der Quelle.
            new_persona_id = await conn.fetchval(
                "INSERT INTO persona (workspace_id, owner_id, name, is_managed, locale) "
                "SELECT $1, $2, name, false, locale FROM persona "
                "WHERE id = $3 AND workspace_id = $1 RETURNING id",
                workspace_id,
                owner_id,
                source_persona_id,
            )
            if new_persona_id is None:
                return None
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, status, created_by, locale) "
                "SELECT $1, 1, content, 'active', $2, locale FROM persona_version "
                "WHERE persona_id = $3 AND status = 'active'",
                new_persona_id,
                owner_id,
                source_persona_id,
            )
            links = await conn.fetch(
                "SELECT pb.id, pb.name, pb.type, pb.tags, pb.triggers, pb.locale "
                "FROM persona_playbook pp JOIN playbook pb ON pb.id = pp.playbook_id "
                "WHERE pp.persona_id = $1",
                source_persona_id,
            )
            for pb in links:
                new_pb_id = await conn.fetchval(
                    "INSERT INTO playbook "
                    "(workspace_id, owner_id, name, type, tags, triggers, is_managed, locale) "
                    "VALUES ($1, $2, $3, $4, $5, $6, false, $7) RETURNING id",
                    workspace_id,
                    owner_id,
                    pb["name"],
                    pb["type"],
                    pb["tags"],
                    pb["triggers"],
                    pb["locale"],
                )
                await conn.execute(
                    "INSERT INTO playbook_version "
                    "(playbook_id, version, content, status, created_by, locale) "
                    "SELECT $1, 1, content, 'active', $2, locale FROM playbook_version "
                    "WHERE playbook_id = $3 AND status = 'active'",
                    new_pb_id,
                    owner_id,
                    pb["id"],
                )
                await conn.execute(
                    "INSERT INTO persona_playbook "
                    "(persona_id, playbook_id, workspace_id, owner_id) "
                    "VALUES ($1, $2, $3, $4)",
                    new_persona_id,
                    new_pb_id,
                    workspace_id,
                    owner_id,
                )
            new_template_id = await conn.fetchval(
                "INSERT INTO system_prompt_template "
                "(workspace_id, owner_id, name, slug, is_managed, locale) "
                "SELECT $1, $2, name, $3, false, locale FROM system_prompt_template "
                "WHERE id = $4 AND workspace_id = $1 RETURNING id",
                workspace_id,
                owner_id,
                new_slug,
                source_template_id,
            )
            if new_template_id is None:
                return None
            await conn.execute(
                "INSERT INTO system_prompt_template_version "
                "(template_id, version, content, status, created_by, locale) "
                "SELECT $1, 1, content, 'active', $2, locale FROM system_prompt_template_version "
                "WHERE template_id = $3 AND status = 'active'",
                new_template_id,
                owner_id,
                source_template_id,
            )
            row = await conn.fetchrow(
                "INSERT INTO agent (workspace_id, owner_id, name, description, "
                "  persona_id, system_prompt_template_id, status, tool_policy) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
                f"{_RETURNING}",
                workspace_id,
                owner_id,
                agent_name,
                description,
                new_persona_id,
                new_template_id,
                status.value,
                tool_policy.model_dump(mode="json"),
            )
            return AgentRead.model_validate(dict(row))

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        limit: int,
        after: tuple[datetime, UUID] | None,
    ) -> list[AgentRead]:
        if after is None:
            rows = await self._pool.fetch(
                f"{_SELECT} WHERE a.workspace_id = $1 "
                "ORDER BY a.created_at DESC, a.id DESC LIMIT $2",
                workspace_id,
                limit,
            )
        else:
            rows = await self._pool.fetch(
                f"{_SELECT} WHERE a.workspace_id = $1 "
                "AND (a.created_at, a.id) < ($2, $3) "
                "ORDER BY a.created_at DESC, a.id DESC LIMIT $4",
                workspace_id,
                after[0],
                after[1],
                limit,
            )
        return [AgentRead.model_validate(dict(row)) for row in rows]

    async def fetch(self, workspace_id: UUID, agent_id: UUID) -> AgentRead | None:
        row = await self._pool.fetchrow(
            f"{_SELECT} WHERE a.id = $1 AND a.workspace_id = $2",
            agent_id,
            workspace_id,
        )
        return AgentRead.model_validate(dict(row)) if row is not None else None

    async def list_meta(
        self, workspace_id: UUID, agent_ids: list[UUID]
    ) -> dict[UUID, AgentListMeta]:
        """Batch-Aggregat fuer die List-Card-Pills (ein Roundtrip, kein N+1).

        Ein Set-basierter Join ueber `= ANY($2)` liefert Persona-/Template-Name,
        die aktive Template-Version und die Playbook-Anzahl der verknuepften
        Persona fuer alle uebergebenen Agenten auf einmal. Leere ID-Liste => {}.
        """
        if not agent_ids:
            return {}
        rows = await self._pool.fetch(
            "SELECT a.id AS agent_id, p.name AS persona_name, "
            "       t.name AS template_name, tv.version AS template_version, "
            "       COALESCE(pc.cnt, 0)::int AS playbook_count, "
            "       COALESCE(pm.cnt, 0)::int AS pending_memory_count "
            "FROM agent a "
            "LEFT JOIN persona p ON p.id = a.persona_id "
            "LEFT JOIN system_prompt_template t ON t.id = a.system_prompt_template_id "
            "LEFT JOIN system_prompt_template_version tv "
            "  ON tv.template_id = t.id AND tv.status = 'active' "
            "LEFT JOIN ( "
            "    SELECT persona_id, COUNT(*) AS cnt "
            "    FROM persona_playbook GROUP BY persona_id "
            ") pc ON pc.persona_id = a.persona_id "
            "LEFT JOIN ( "
            "    SELECT agent_id, COUNT(*) AS cnt "
            "    FROM agent_memory WHERE status = 'pending' GROUP BY agent_id "
            ") pm ON pm.agent_id = a.id "
            "WHERE a.workspace_id = $1 AND a.id = ANY($2)",
            workspace_id,
            agent_ids,
        )
        return {
            row["agent_id"]: AgentListMeta(
                persona_name=row["persona_name"],
                template_name=row["template_name"],
                template_version=row["template_version"],
                playbook_count=row["playbook_count"],
                pending_memory_count=row["pending_memory_count"],
            )
            for row in rows
        }

    async def update(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        name: str | None,
        description: str | None,
        persona_id: UUID | None,
        template_id: UUID | None,
        status: AgentStatus | None,
        tool_policy: AgentToolPolicy | None,
        model_provider: str | None = None,
        model_name: str | None = None,
    ) -> AgentRead | None:
        # `model_provider`/`model_name` (User-Entscheidung 6, ADR-0047):
        # COALESCE-Semantik wie alle anderen Felder — `None` laesst den
        # Bestand unangetastet. Explizites Leeren (zurueck auf NULL) ist
        # damit bewusst (noch) nicht moeglich — dokumentierter offener Punkt.
        try:
            row = await self._pool.fetchrow(
                "UPDATE agent SET "
                "  name = COALESCE($3, name), "
                "  description = COALESCE($4, description), "
                "  persona_id = COALESCE($5, persona_id), "
                "  system_prompt_template_id = COALESCE($6, system_prompt_template_id), "
                "  status = COALESCE($7, status), "
                "  tool_policy = COALESCE($8::jsonb, tool_policy), "
                "  model_provider = COALESCE($9, model_provider), "
                "  model_name = COALESCE($10, model_name), "
                "  updated_at = now() "
                "WHERE id = $1 AND workspace_id = $2 "
                f"{_RETURNING}",
                agent_id,
                workspace_id,
                name,
                description,
                persona_id,
                template_id,
                status.value if status is not None else None,
                tool_policy.model_dump(mode="json") if tool_policy is not None else None,
                model_provider,
                model_name,
            )
        except asyncpg.ForeignKeyViolationError:
            return None
        return AgentRead.model_validate(dict(row)) if row is not None else None

    async def delete(self, workspace_id: UUID, agent_id: UUID) -> bool:
        result = await self._pool.execute(
            "DELETE FROM agent WHERE id = $1 AND workspace_id = $2",
            agent_id,
            workspace_id,
        )
        # asyncpg gibt "DELETE <n>" zurueck; n=0 wenn nichts geloescht wurde.
        return bool(result.split()[-1] != "0")

    async def persona_has_active_version(self, workspace_id: UUID, persona_id: UUID) -> bool:
        """True, wenn die Persona im Workspace eine aktive Version hat.

        Workspace-gepinnt: ein Cross-Workspace-`persona_id` (theoretisch durch
        den Composite-FK ausgeschlossen) liefert False statt eines Lecks.
        """
        active: bool = await self._pool.fetchval(
            "SELECT EXISTS ("
            "  SELECT 1 FROM persona_version pv "
            "  JOIN persona p ON p.id = pv.persona_id "
            "  WHERE pv.persona_id = $1 AND p.workspace_id = $2 "
            "    AND pv.status = 'active'"
            ")",
            persona_id,
            workspace_id,
        )
        return active
