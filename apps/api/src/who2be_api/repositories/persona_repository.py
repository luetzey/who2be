"""Persistenz fuer das Persona-Aggregat (`persona` + `persona_version`).

Versionierung ueber eine History-Tabelle (ADR-0004): `insert` und `update`
schreiben Identitaets-Zeile und Versions-Snapshot in einer Transaktion.
Verantwortung: SQL + Row↔Model-Mapping, keine Geschaeftsregeln.
"""

from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_models import PersonaContent, PersonaRead, PersonaVersionRead

# Persona-Zeile verbunden mit dem Inhalt ihrer aktuellen Version.
_SELECT_CURRENT = """
    SELECT p.id, p.owner_id, p.name, p.current_version,
           p.created_at, p.updated_at, pv.content
    FROM persona p
    JOIN persona_version pv
      ON pv.persona_id = p.id AND pv.version = p.current_version
"""


class PersonaRepository(Protocol):
    """Service-seitige Abstraktion fuer den Persona-Zugriff."""

    async def insert(
        self, owner_id: UUID, name: str, content: PersonaContent
    ) -> PersonaRead: ...

    async def list_by_owner(self, owner_id: UUID) -> list[PersonaRead]: ...

    async def fetch(self, owner_id: UUID, persona_id: UUID) -> PersonaRead | None: ...

    async def update(
        self,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaContent,
    ) -> PersonaRead | None: ...

    async def list_versions(
        self, owner_id: UUID, persona_id: UUID
    ) -> list[PersonaVersionRead] | None: ...

    async def fetch_version(
        self, owner_id: UUID, persona_id: UUID, version: int
    ) -> PersonaVersionRead | None: ...


class PgPersonaRepository:
    """asyncpg-Implementierung von `PersonaRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def insert(
        self, owner_id: UUID, name: str, content: PersonaContent
    ) -> PersonaRead:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            persona = await conn.fetchrow(
                "INSERT INTO persona (owner_id, name) VALUES ($1, $2) "
                "RETURNING id, owner_id, name, current_version, "
                "created_at, updated_at",
                owner_id,
                name,
            )
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, created_by) "
                "VALUES ($1, $2, $3, $4)",
                persona["id"],
                persona["current_version"],
                content_json,
                owner_id,
            )
        return PersonaRead.model_validate({**dict(persona), "content": content_json})

    async def list_by_owner(self, owner_id: UUID) -> list[PersonaRead]:
        rows = await self._pool.fetch(
            f"{_SELECT_CURRENT} WHERE p.owner_id = $1 ORDER BY p.created_at DESC",
            owner_id,
        )
        return [PersonaRead.model_validate(dict(row)) for row in rows]

    async def fetch(self, owner_id: UUID, persona_id: UUID) -> PersonaRead | None:
        row = await self._pool.fetchrow(
            f"{_SELECT_CURRENT} WHERE p.id = $1 AND p.owner_id = $2",
            persona_id,
            owner_id,
        )
        return PersonaRead.model_validate(dict(row)) if row is not None else None

    async def update(
        self,
        owner_id: UUID,
        persona_id: UUID,
        name: str | None,
        content: PersonaContent,
    ) -> PersonaRead | None:
        content_json = content.model_dump(mode="json")
        async with self._pool.acquire() as conn, conn.transaction():
            current = await conn.fetchrow(
                "SELECT current_version FROM persona "
                "WHERE id = $1 AND owner_id = $2 FOR UPDATE",
                persona_id,
                owner_id,
            )
            if current is None:
                return None
            next_version = current["current_version"] + 1
            persona = await conn.fetchrow(
                "UPDATE persona "
                "SET current_version = $1, name = COALESCE($2, name), "
                "updated_at = now() "
                "WHERE id = $3 "
                "RETURNING id, owner_id, name, current_version, "
                "created_at, updated_at",
                next_version,
                name,
                persona_id,
            )
            await conn.execute(
                "INSERT INTO persona_version "
                "(persona_id, version, content, created_by) "
                "VALUES ($1, $2, $3, $4)",
                persona_id,
                next_version,
                content_json,
                owner_id,
            )
        return PersonaRead.model_validate({**dict(persona), "content": content_json})

    async def list_versions(
        self, owner_id: UUID, persona_id: UUID
    ) -> list[PersonaVersionRead] | None:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM persona WHERE id = $1 AND owner_id = $2",
            persona_id,
            owner_id,
        )
        if owned is None:
            return None
        rows = await self._pool.fetch(
            "SELECT version, content, created_by, created_at "
            "FROM persona_version WHERE persona_id = $1 ORDER BY version DESC",
            persona_id,
        )
        return [PersonaVersionRead.model_validate(dict(row)) for row in rows]

    async def fetch_version(
        self, owner_id: UUID, persona_id: UUID, version: int
    ) -> PersonaVersionRead | None:
        row = await self._pool.fetchrow(
            "SELECT pv.version, pv.content, pv.created_by, pv.created_at "
            "FROM persona_version pv "
            "JOIN persona p ON p.id = pv.persona_id "
            "WHERE p.id = $1 AND p.owner_id = $2 AND pv.version = $3",
            persona_id,
            owner_id,
            version,
        )
        return (
            PersonaVersionRead.model_validate(dict(row)) if row is not None else None
        )
