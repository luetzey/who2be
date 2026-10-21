"""Persistenz des Tutorial-Fortschritts (ADR-0060, Migration 0108).

Zwei Teile:

* Konto-Daten (`tutorial_state`, `tutorial_progress`): ohne Mandant, jede
  Query filtert auf die `user_id` des authentifizierten Menschen.
* Ableitungen aus Workspace-Daten (`usage_event`, `agent`): stehen unter RLS
  auf `app.current_tenant`. Der Service betritt dafuer `tenant_scope` des
  geprueften Workspace; die `WHERE workspace_id = $1`-Filter bleiben trotzdem
  als erste Verteidigungslinie stehen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import asyncpg


@dataclass(frozen=True)
class TutorialStateRow:
    welcome_seen_at: datetime | None
    restarted_at: datetime | None


@dataclass(frozen=True)
class StepProgressRow:
    state: str
    changed_at: datetime


@dataclass(frozen=True)
class DerivedSignals:
    """Fruehester Zeitpunkt je abgeleitetem Signal (seit `since`), sonst None."""

    first_mcp_call: datetime | None
    agent_created: datetime | None
    own_agent_mcp_call: datetime | None


@dataclass(frozen=True)
class Membership:
    """Lebende Mitgliedschaft; `org_id` fuer `tenant_scope`."""

    org_id: UUID | None


class TutorialRepository(Protocol):
    async def membership(self, user_id: UUID, workspace_id: UUID) -> Membership | None: ...

    async def states(self, user_id: UUID) -> dict[str, TutorialStateRow]: ...

    async def progress(self, user_id: UUID) -> dict[tuple[str, str], StepProgressRow]: ...

    async def set_step(self, user_id: UUID, tutorial_id: str, step_id: str, state: str) -> None: ...

    async def clear_step(self, user_id: UUID, tutorial_id: str, step_id: str) -> None: ...

    async def mark_welcome_seen(self, user_id: UUID, tutorial_id: str) -> None: ...

    async def restart(self, user_id: UUID, tutorial_id: str) -> None: ...

    async def derived(
        self, user_id: UUID, workspace_id: UUID, since: datetime | None
    ) -> DerivedSignals: ...


#: Mitgliedschaft in einem lebenden Workspace. Liefert die Org fuer
#: `tenant_scope`; `workspace_member`/`workspace` sind ohne gesetzten
#: Mandanten lesbar (permissiv-bei-unset, Migration 0068).
_MEMBERSHIP_QUERY = (
    "SELECT w.org_id FROM workspace_member m "
    "JOIN workspace w ON w.id = m.workspace_id "
    "JOIN organization o ON o.id = w.org_id "
    "WHERE m.user_id = $1 AND m.workspace_id = $2 AND o.deleted_at IS NULL"
)

# Abgeleitete Schritte (ADR-0060 §3). `actor_id` ist der Besitzer des
# Tokens, ueber den der Abruf lief — also die Person, die die Verbindung
# freigegeben hat. Nur serverseitig gezaehlte Auslieferungen
# (`source = 'server'`), keine Selbstmeldungen der Agenten.
_DERIVED_QUERY = (
    "SELECT "
    "  (SELECT min(u.created_at) FROM usage_event u "
    "    WHERE u.workspace_id = $1 AND u.actor_id = $2 AND u.source = 'server' "
    "      AND u.created_at >= $3) AS first_mcp_call, "
    "  (SELECT min(a.created_at) FROM agent a "
    "    WHERE a.workspace_id = $1 AND a.owner_id = $2 AND NOT a.is_managed "
    "      AND a.created_at >= $3) AS agent_created, "
    "  (SELECT min(u.created_at) FROM usage_event u "
    "    JOIN agent a ON a.id = u.agent_id AND a.workspace_id = u.workspace_id "
    "    WHERE u.workspace_id = $1 AND u.actor_id = $2 AND u.source = 'server' "
    "      AND NOT a.is_managed AND u.created_at >= $3) AS own_agent_mcp_call"
)

_EPOCH = datetime.fromisoformat("1970-01-01T00:00:00+00:00")


class PgTutorialRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def membership(self, user_id: UUID, workspace_id: UUID) -> Membership | None:
        """Mitgliedschaft in einem lebenden Workspace, sonst `None`."""
        row = await self._pool.fetchrow(_MEMBERSHIP_QUERY, user_id, workspace_id)
        return None if row is None else Membership(org_id=row["org_id"])

    async def states(self, user_id: UUID) -> dict[str, TutorialStateRow]:
        rows = await self._pool.fetch(
            "SELECT tutorial_id, welcome_seen_at, restarted_at FROM tutorial_state "
            "WHERE user_id = $1",
            user_id,
        )
        return {
            row["tutorial_id"]: TutorialStateRow(row["welcome_seen_at"], row["restarted_at"])
            for row in rows
        }

    async def progress(self, user_id: UUID) -> dict[tuple[str, str], StepProgressRow]:
        rows = await self._pool.fetch(
            "SELECT tutorial_id, step_id, state, changed_at FROM tutorial_progress "
            "WHERE user_id = $1",
            user_id,
        )
        return {
            (row["tutorial_id"], row["step_id"]): StepProgressRow(row["state"], row["changed_at"])
            for row in rows
        }

    async def set_step(self, user_id: UUID, tutorial_id: str, step_id: str, state: str) -> None:
        await self._pool.execute(
            "INSERT INTO tutorial_progress (user_id, tutorial_id, step_id, state) "
            "VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (user_id, tutorial_id, step_id) "
            "DO UPDATE SET state = EXCLUDED.state, changed_at = now() "
            "WHERE tutorial_progress.state IS DISTINCT FROM EXCLUDED.state",
            user_id,
            tutorial_id,
            step_id,
            state,
        )

    async def clear_step(self, user_id: UUID, tutorial_id: str, step_id: str) -> None:
        await self._pool.execute(
            "DELETE FROM tutorial_progress "
            "WHERE user_id = $1 AND tutorial_id = $2 AND step_id = $3",
            user_id,
            tutorial_id,
            step_id,
        )

    async def mark_welcome_seen(self, user_id: UUID, tutorial_id: str) -> None:
        # Erster Zeitpunkt zaehlt: ein zweites „gesehen“ (Begruessung erneut
        # abgespielt) ueberschreibt ihn nicht.
        await self._pool.execute(
            "INSERT INTO tutorial_state (user_id, tutorial_id, welcome_seen_at) "
            "VALUES ($1, $2, now()) "
            "ON CONFLICT (user_id, tutorial_id) DO UPDATE "
            "SET welcome_seen_at = coalesce(tutorial_state.welcome_seen_at, now()), "
            "    updated_at = now()",
            user_id,
            tutorial_id,
        )

    async def restart(self, user_id: UUID, tutorial_id: str) -> None:
        """Setzt genau dieses Tutorial zurueck (eine Transaktion)."""
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "DELETE FROM tutorial_progress WHERE user_id = $1 AND tutorial_id = $2",
                user_id,
                tutorial_id,
            )
            # `clock_timestamp()` statt `now()`: ein Ereignis in derselben
            # Sekunde vor dem Neustart soll nicht mehr zaehlen.
            await conn.execute(
                "INSERT INTO tutorial_state (user_id, tutorial_id, restarted_at) "
                "VALUES ($1, $2, clock_timestamp()) "
                "ON CONFLICT (user_id, tutorial_id) DO UPDATE "
                "SET restarted_at = clock_timestamp(), updated_at = now()",
                user_id,
                tutorial_id,
            )

    async def export(self, user_id: UUID) -> dict[str, list[dict[str, Any]]]:
        """Alle Zeilen des Kontos fuer den DSGVO-Export (Art. 15/20)."""
        states = await self._pool.fetch(
            "SELECT tutorial_id, welcome_seen_at, restarted_at, updated_at "
            "FROM tutorial_state WHERE user_id = $1 ORDER BY tutorial_id",
            user_id,
        )
        progress = await self._pool.fetch(
            "SELECT tutorial_id, step_id, state, changed_at "
            "FROM tutorial_progress WHERE user_id = $1 ORDER BY tutorial_id, step_id",
            user_id,
        )
        return {
            "states": [dict(row) for row in states],
            "progress": [dict(row) for row in progress],
        }

    async def derived(
        self, user_id: UUID, workspace_id: UUID, since: datetime | None
    ) -> DerivedSignals:
        """Liest die Signale; der Aufrufer haelt `tenant_scope` des Workspace."""
        row = await self._pool.fetchrow(_DERIVED_QUERY, workspace_id, user_id, since or _EPOCH)
        if row is None:  # pragma: no cover - SELECT ohne FROM liefert immer eine Zeile
            return DerivedSignals(None, None, None)
        return DerivedSignals(
            first_mcp_call=row["first_mcp_call"],
            agent_created=row["agent_created"],
            own_agent_mcp_call=row["own_agent_mcp_call"],
        )
