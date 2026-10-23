"""Persistenz der Werkzeug-Profile pro Agent (ADR-0059 §4, Migration 0111).

Zwei Teile:

* `tool_profile`: die Profile eines Workspace (vier mitgelieferte mit
  `builtin_key`, beliebig viele eigene). RLS auf `app.current_tenant`; die
  `WHERE workspace_id = $1`-Filter bleiben trotzdem als erste Linie stehen.
* Die drei Spalten am Agenten (`tool_profile_id`, `tools_added`,
  `tools_removed`). Gelesen werden sie ueber `agent_repository` (`AgentRead`),
  geschrieben nur hier (`assign_agent`), weil die Zuordnung ein eigener Weg ist
  (ADR-0059 §7.3: eigener Endpunkt, auch fuer verwaltete Agenten).

Gruppen, mitgelieferte Profile und Formel kommen ausschliesslich aus
`who2be_models.tool_profiles` (Single Source of Truth). Die Migration 0111
spiegelt den Seed in SQL; der Paritaetstest prueft beide Wege gegeneinander.

Das Repository prueft keine Namen gegen den Katalog und keine Rollen — das ist
Aufgabe des Service (Q2b, 422 `unknown_tool` usw.). Es uebersetzt nur
Datenbank-Zustaende in eigene Ausnahmen, damit es frei von FastAPI bleibt
(ADR-0002).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

import asyncpg

from who2be_models import DEFAULT_LOCALE
from who2be_models.tool_profiles import (
    BUILTIN_PROFILES,
    BuiltinProfileKey,
    ToolProfileGrant,
    ToolProfileRead,
)

# Name des Unique-Index aus 0111 (Name je Workspace, ohne Gross/Klein).
_NAME_UNIQUE_INDEX = "tool_profile_name_uq"


class ToolProfileNameTakenError(Exception):
    """Ein anderes Profil im Workspace traegt schon diesen Namen."""


class ToolProfileBuiltinError(Exception):
    """Ein mitgeliefertes Profil soll geloescht werden (API: 409 `tool_profile_builtin`)."""


class ToolProfileInUseError(Exception):
    """Das Profil haengt noch an Agenten (API: 409 `tool_profile_in_use`)."""

    def __init__(self, agent_count: int) -> None:
        super().__init__(f"Profil ist {agent_count} Agent(en) zugeordnet.")
        self.agent_count = agent_count


def builtin_profile_name(key: BuiltinProfileKey, content_locale: str) -> str:
    """Name eines mitgelieferten Profils in der Content-Sprache des Workspace.

    Unbekannte Sprachen fallen auf `DEFAULT_LOCALE` zurueck, wie in der
    Migration 0111 (alles ausser 'en' heisst deutsch).
    """
    names = BUILTIN_PROFILES[key].names
    return names.get(content_locale, names[DEFAULT_LOCALE])


async def seed_builtin_profiles(
    conn: asyncpg.Connection, workspace_id: UUID, content_locale: str
) -> None:
    """Legt die vier mitgelieferten Profile eines Workspace an (idempotent).

    Code-Gegenstueck zu Schritt 3 der Migration 0111. Laeuft beim Anlegen
    eines Workspace VOR dem Agenten-Seed, damit der verwaltete Builder sein
    Profil gleich beim Insert bekommt (W59-3 = A). Ein Re-Lauf prallt an
    `UNIQUE (workspace_id, builtin_key)` ab und laesst angepasste Profile
    unveraendert.
    """
    for key, profile in BUILTIN_PROFILES.items():
        await conn.execute(
            "INSERT INTO tool_profile (workspace_id, builtin_key, name, groups, tools) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (workspace_id, builtin_key) DO NOTHING",
            workspace_id,
            key.value,
            builtin_profile_name(key, content_locale),
            [group.value for group in profile.groups],
            list(profile.tools),
        )


async def builtin_profile_id(
    conn: asyncpg.Connection, workspace_id: UUID, key: BuiltinProfileKey
) -> UUID | None:
    """ID eines mitgelieferten Profils im Workspace, None wenn (noch) nicht da."""
    value = await conn.fetchval(
        "SELECT id FROM tool_profile WHERE workspace_id = $1 AND builtin_key = $2",
        workspace_id,
        key.value,
    )
    return value if isinstance(value, UUID) else None


# `agent_count` per korrelierter Unterabfrage: ein Roundtrip fuer die Liste,
# kein N+1. Der Index `agent_tool_profile_idx` (0111) traegt sie.
_SELECT = """
    SELECT p.id, p.workspace_id, p.builtin_key, p.name, p.description,
           p.groups, p.tools, p.created_at, p.updated_at,
           (SELECT count(*) FROM agent a
             WHERE a.workspace_id = p.workspace_id
               AND a.tool_profile_id = p.id)::int AS agent_count
    FROM tool_profile p
"""

_RETURNING = """
    RETURNING id, workspace_id, builtin_key, name, description, groups, tools,
              created_at, updated_at,
              (SELECT count(*) FROM agent a
                WHERE a.workspace_id = tool_profile.workspace_id
                  AND a.tool_profile_id = tool_profile.id)::int AS agent_count
"""


def _read(row: asyncpg.Record) -> ToolProfileRead:
    return ToolProfileRead.model_validate(dict(row))


def _is_name_conflict(exc: asyncpg.UniqueViolationError) -> bool:
    return getattr(exc, "constraint_name", None) == _NAME_UNIQUE_INDEX


class ToolProfileRepository(Protocol):
    """Service-seitige Abstraktion."""

    async def list_by_workspace(self, workspace_id: UUID) -> list[ToolProfileRead]: ...

    async def fetch(self, workspace_id: UUID, profile_id: UUID) -> ToolProfileRead | None: ...

    async def insert(
        self,
        workspace_id: UUID,
        name: str,
        description: str,
        groups: Sequence[str],
        tools: Sequence[str],
    ) -> ToolProfileRead: ...

    async def update(
        self,
        workspace_id: UUID,
        profile_id: UUID,
        name: str,
        description: str,
        groups: Sequence[str],
        tools: Sequence[str],
    ) -> ToolProfileRead | None: ...

    async def reset_builtin(
        self, workspace_id: UUID, profile_id: UUID, content_locale: str
    ) -> ToolProfileRead | None: ...

    async def delete(self, workspace_id: UUID, profile_id: UUID) -> bool: ...

    async def assign_agent(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        tool_profile_id: UUID | None,
        tools_added: Sequence[str],
        tools_removed: Sequence[str],
    ) -> bool: ...

    async def fetch_grant(self, workspace_id: UUID, agent_id: UUID) -> ToolProfileGrant | None: ...


class PgToolProfileRepository:
    """asyncpg-Implementierung."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_by_workspace(self, workspace_id: UUID) -> list[ToolProfileRead]:
        """Alle Profile: mitgelieferte zuerst (Lieferreihenfolge), dann eigene nach Name."""
        rows = await self._pool.fetch(
            f"{_SELECT} WHERE p.workspace_id = $1 "
            "ORDER BY p.builtin_key IS NULL, "
            "  array_position($2::text[], p.builtin_key), lower(p.name), p.id",
            workspace_id,
            [key.value for key in BUILTIN_PROFILES],
        )
        return [_read(row) for row in rows]

    async def fetch(self, workspace_id: UUID, profile_id: UUID) -> ToolProfileRead | None:
        row = await self._pool.fetchrow(
            f"{_SELECT} WHERE p.workspace_id = $1 AND p.id = $2",
            workspace_id,
            profile_id,
        )
        return _read(row) if row is not None else None

    async def insert(
        self,
        workspace_id: UUID,
        name: str,
        description: str,
        groups: Sequence[str],
        tools: Sequence[str],
    ) -> ToolProfileRead:
        """Legt ein eigenes Profil an (`builtin_key IS NULL`)."""
        try:
            row = await self._pool.fetchrow(
                "INSERT INTO tool_profile (workspace_id, name, description, groups, tools) "
                "VALUES ($1, $2, $3, $4, $5) "
                f"{_RETURNING}",
                workspace_id,
                name,
                description,
                list(groups),
                list(tools),
            )
        except asyncpg.UniqueViolationError as exc:
            if _is_name_conflict(exc):
                raise ToolProfileNameTakenError(name) from exc
            raise
        return _read(row)

    async def update(
        self,
        workspace_id: UUID,
        profile_id: UUID,
        name: str,
        description: str,
        groups: Sequence[str],
        tools: Sequence[str],
    ) -> ToolProfileRead | None:
        """Ersetzt Name, Beschreibung, Gruppen und Werkzeuge (auch mitgelieferte, Owner a)."""
        try:
            row = await self._pool.fetchrow(
                "UPDATE tool_profile SET name = $3, description = $4, "
                "  groups = $5, tools = $6, updated_at = now() "
                "WHERE workspace_id = $1 AND id = $2 "
                f"{_RETURNING}",
                workspace_id,
                profile_id,
                name,
                description,
                list(groups),
                list(tools),
            )
        except asyncpg.UniqueViolationError as exc:
            if _is_name_conflict(exc):
                raise ToolProfileNameTakenError(name) from exc
            raise
        return _read(row) if row is not None else None

    async def reset_builtin(
        self, workspace_id: UUID, profile_id: UUID, content_locale: str
    ) -> ToolProfileRead | None:
        """Setzt ein mitgeliefertes Profil auf den Lieferstand (ADR-0059 §7.1).

        Name in der Content-Sprache, leere Beschreibung, Gruppen und Werkzeuge
        aus `BUILTIN_PROFILES`. None, wenn das Profil fehlt oder ein eigenes
        ist (`builtin_key IS NULL`).
        """
        key_value = await self._pool.fetchval(
            "SELECT builtin_key FROM tool_profile WHERE workspace_id = $1 AND id = $2",
            workspace_id,
            profile_id,
        )
        if key_value is None:
            return None
        key = BuiltinProfileKey(key_value)
        profile = BUILTIN_PROFILES[key]
        try:
            row = await self._pool.fetchrow(
                "UPDATE tool_profile SET name = $3, description = '', "
                "  groups = $4, tools = $5, updated_at = now() "
                "WHERE workspace_id = $1 AND id = $2 AND builtin_key IS NOT NULL "
                f"{_RETURNING}",
                workspace_id,
                profile_id,
                builtin_profile_name(key, content_locale),
                [group.value for group in profile.groups],
                list(profile.tools),
            )
        except asyncpg.UniqueViolationError as exc:
            # Ein eigenes Profil traegt inzwischen den Liefernamen.
            if _is_name_conflict(exc):
                raise ToolProfileNameTakenError(builtin_profile_name(key, content_locale)) from exc
            raise
        return _read(row) if row is not None else None

    async def delete(self, workspace_id: UUID, profile_id: UUID) -> bool:
        """Loescht ein eigenes Profil. False, wenn es im Workspace nicht existiert.

        Mitgelieferte Profile: `ToolProfileBuiltinError`. Noch zugeordnet:
        `ToolProfileInUseError` mit der Zahl der Agenten. Kein stilles
        Zurueckfallen auf „Alle“ — der FK aus 0111 ist `ON DELETE RESTRICT`.
        Die Zaehlung laeuft unter `FOR UPDATE` auf der Profilzeile, der FK
        haelt den Fall ab, dass zwischen Zaehlung und Delete eine Zuordnung
        dazukommt.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT builtin_key FROM tool_profile "
                "WHERE workspace_id = $1 AND id = $2 FOR UPDATE",
                workspace_id,
                profile_id,
            )
            if row is None:
                return False
            if row["builtin_key"] is not None:
                raise ToolProfileBuiltinError
            in_use: int = await conn.fetchval(
                "SELECT count(*) FROM agent WHERE workspace_id = $1 AND tool_profile_id = $2",
                workspace_id,
                profile_id,
            )
            if in_use:
                raise ToolProfileInUseError(in_use)
            try:
                await conn.execute(
                    "DELETE FROM tool_profile WHERE workspace_id = $1 AND id = $2",
                    workspace_id,
                    profile_id,
                )
            except asyncpg.ForeignKeyViolationError as exc:
                count: int = await conn.fetchval(
                    "SELECT count(*) FROM agent WHERE workspace_id = $1 AND tool_profile_id = $2",
                    workspace_id,
                    profile_id,
                )
                raise ToolProfileInUseError(count) from exc
        return True

    async def assign_agent(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        tool_profile_id: UUID | None,
        tools_added: Sequence[str],
        tools_removed: Sequence[str],
    ) -> bool:
        """Setzt Profil und Ausnahmen am Agenten; `tool_profile_id=None` heisst „Alle“.

        Gilt auch fuer verwaltete Agenten (ADR-0059 §7.3). False, wenn der
        Agent im Workspace fehlt oder das Profil nicht im Workspace des Agenten
        liegt (der zusammengesetzte FK aus 0111 lehnt es ab).
        """
        try:
            result: str = await self._pool.execute(
                "UPDATE agent SET tool_profile_id = $3, tools_added = $4, "
                "  tools_removed = $5, updated_at = now() "
                "WHERE workspace_id = $1 AND id = $2",
                workspace_id,
                agent_id,
                tool_profile_id,
                list(tools_added),
                list(tools_removed),
            )
        except asyncpg.ForeignKeyViolationError:
            return False
        return result.split()[-1] != "0"

    async def fetch_grant(self, workspace_id: UUID, agent_id: UUID) -> ToolProfileGrant | None:
        """Das Profil eines Agenten in `whoami`-Form (ADR-0059 §6.1).

        None bei „Alle ohne Ausnahmen“ oder wenn der Agent fehlt. „Alle“ mit
        Ausnahmen liefert `id=None`, `name=""` und nur die Ausnahmen.
        """
        row = await self._pool.fetchrow(
            "SELECT a.tool_profile_id, a.tools_added, a.tools_removed, "
            "       p.name, p.groups, p.tools "
            "FROM agent a "
            "LEFT JOIN tool_profile p "
            "  ON p.workspace_id = a.workspace_id AND p.id = a.tool_profile_id "
            "WHERE a.workspace_id = $1 AND a.id = $2",
            workspace_id,
            agent_id,
        )
        if row is None:
            return None
        return grant_from_row(row)


def grant_from_row(row: asyncpg.Record | dict[str, Any]) -> ToolProfileGrant | None:
    """`ToolProfileGrant` aus Agent-Spalten plus (optional gejointem) Profil.

    Erwartet `tool_profile_id`, `tools_added`, `tools_removed` und bei
    gesetztem Profil `name`, `groups`, `tools`. Gemeinsam fuer `fetch_grant`
    und kuenftige Join-Ladewege (whoami, Q2b), damit die Abbildung nur
    einmal existiert.
    """
    added = list(row["tools_added"] or [])
    removed = list(row["tools_removed"] or [])
    profile_id = row["tool_profile_id"]
    if profile_id is None:
        if not added and not removed:
            return None
        return ToolProfileGrant(id=None, name="", tools_added=added, tools_removed=removed)
    return ToolProfileGrant(
        id=profile_id,
        name=row["name"],
        groups=list(row["groups"] or []),
        tools=list(row["tools"] or []),
        tools_added=added,
        tools_removed=removed,
    )


__all__ = [
    "PgToolProfileRepository",
    "ToolProfileBuiltinError",
    "ToolProfileInUseError",
    "ToolProfileNameTakenError",
    "ToolProfileRepository",
    "builtin_profile_id",
    "builtin_profile_name",
    "grant_from_row",
    "seed_builtin_profiles",
]
