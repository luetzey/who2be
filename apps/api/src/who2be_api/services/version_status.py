"""State-Machine + Transition-Service fuer Persona-/Playbook-Versionen.

Die State-Machine lebt hier als kanonische API-Sicht (Plan §2.1.C):
    draft → review
    review → active | draft
    active → inactive
    inactive → draft

Verbotene Uebergaenge → 409. Promotion auf `active` setzt eine bereits
aktive Version derselben Entity atomar auf `inactive` (Plan: "Active-
Promotion setzt vorher aktive Version auf inactive"). `status_history` wird
in derselben Transaktion geschrieben — sowohl fuer den eigentlichen
Wechsel als auch fuer das implizite Inactivieren der bisherigen
Active-Version.

Der Service nimmt eine `asyncpg.Pool` direkt — der Transition-Algorithmus
fuehrt mehrere abhaengige UPDATEs aus, die ein PgRepository-Interface
unnoetig aufblaehen wuerden. Wir bleiben hier bei rohem SQL und halten die
Transition-Logik an einer Stelle.
"""

from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.security import WorkspaceContext
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_models import (
    ALLOWED_TRANSITIONS,
    EntityType,
    PersonaVersionRead,
    PlaybookVersionRead,
    ResourceVersionRead,
    VersionStatus,
)


def _not_found(entity_type: EntityType) -> HTTPException:
    label = {"persona": "Persona", "playbook": "Playbook", "resource": "Resource"}[entity_type]
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{label}-Version nicht gefunden.",
    )


def _forbidden_transition(
    from_status: VersionStatus, to_status: VersionStatus
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Status-Uebergang {from_status.value} → {to_status.value} "
            "ist nicht erlaubt."
        ),
    )


def _invariant_violation() -> HTTPException:
    # Partial-Unique-Index aus 0011 hat zugeschlagen. Race zwischen
    # zwei parallelen Promotions — der zweite Versuch bekommt 409 statt 500.
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Konfliktierende Status-Aenderung (parallele Transition).",
    )


def validate_transition(from_status: VersionStatus, to_status: VersionStatus) -> None:
    """Wirft 409, wenn der Uebergang nicht erlaubt ist."""
    if to_status not in ALLOWED_TRANSITIONS[from_status]:
        raise _forbidden_transition(from_status, to_status)


_PERSONA_TABLES = ("persona", "persona_version", "persona_id")
_PLAYBOOK_TABLES = ("playbook", "playbook_version", "playbook_id")
_RESOURCE_TABLES = ("resource", "resource_version", "resource_id")


class VersionStatusService:
    """Fuehrt Status-Wechsel fuer Persona- und Playbook-Versionen aus."""

    def __init__(self, pool: asyncpg.Pool, history: StatusHistoryService) -> None:
        self._pool = pool
        self._history = history

    async def transition_persona_version(
        self,
        ctx: WorkspaceContext,
        persona_id: UUID,
        version: int,
        to_status: VersionStatus,
        note: str | None,
    ) -> PersonaVersionRead:
        row = await self._transition(
            ctx, "persona", _PERSONA_TABLES, persona_id, version, to_status, note
        )
        return PersonaVersionRead.model_validate(dict(row))

    async def transition_playbook_version(
        self,
        ctx: WorkspaceContext,
        playbook_id: UUID,
        version: int,
        to_status: VersionStatus,
        note: str | None,
    ) -> PlaybookVersionRead:
        row = await self._transition(
            ctx, "playbook", _PLAYBOOK_TABLES, playbook_id, version, to_status, note
        )
        return PlaybookVersionRead.model_validate(dict(row))

    async def transition_resource_version(
        self,
        ctx: WorkspaceContext,
        resource_id: UUID,
        version: int,
        to_status: VersionStatus,
        note: str | None,
    ) -> ResourceVersionRead:
        row = await self._transition(
            ctx, "resource", _RESOURCE_TABLES, resource_id, version, to_status, note
        )
        return ResourceVersionRead.model_validate(dict(row))

    async def _transition(
        self,
        ctx: WorkspaceContext,
        entity_type: EntityType,
        tables: tuple[str, str, str],
        entity_id: UUID,
        version: int,
        to_status: VersionStatus,
        note: str | None,
    ) -> asyncpg.Record:
        entity_tbl, version_tbl, fk_col = tables
        async with self._pool.acquire() as conn, conn.transaction():
            # Ziel-Version laden + sperren. JOIN ueber das Entity sichert,
            # dass die Version im richtigen Workspace lebt.
            target = await conn.fetchrow(
                f"SELECT pv.status FROM {version_tbl} pv "
                f"JOIN {entity_tbl} e ON e.id = pv.{fk_col} "
                f"WHERE pv.{fk_col} = $1 AND pv.version = $2 "
                "AND e.workspace_id = $3 "
                "FOR UPDATE OF pv",
                entity_id,
                version,
                ctx.workspace_id,
            )
            if target is None:
                raise _not_found(entity_type)
            from_status = VersionStatus(target["status"])
            validate_transition(from_status, to_status)

            # Active-Promotion: die bisherige Active-Version derselben
            # Entity zuerst auf `inactive` setzen — sonst kollidiert der
            # Partial-Unique-Index. Audit-Eintrag fuer das implizite
            # Inactive-Setzen schreiben.
            if to_status == VersionStatus.active:
                prev_active_version = await conn.fetchval(
                    f"UPDATE {version_tbl} SET status = 'inactive' "
                    f"WHERE {fk_col} = $1 AND status = 'active' "
                    "RETURNING version",
                    entity_id,
                )
                if prev_active_version is not None:
                    await self._history.record(
                        conn,
                        entity_type,
                        entity_id,
                        VersionStatus.active,
                        VersionStatus.inactive,
                        ctx.user_id,
                        note=(
                            "Auto-inactiviert durch Promotion von v"
                            f"{version} auf 'active'."
                        ),
                    )

            try:
                updated = await conn.fetchrow(
                    f"UPDATE {version_tbl} SET status = $1 "
                    f"WHERE {fk_col} = $2 AND version = $3 "
                    "RETURNING version, status, content, created_by, created_at",
                    to_status.value,
                    entity_id,
                    version,
                )
            except asyncpg.UniqueViolationError as exc:
                raise _invariant_violation() from exc
            # FOR UPDATE oben hat die Row gesperrt — gibt es plausibel nur
            # via Race nicht mehr; trotzdem defensiv abfangen.
            if updated is None:
                raise _not_found(entity_type)

            await self._history.record(
                conn,
                entity_type,
                entity_id,
                from_status,
                to_status,
                ctx.user_id,
                note,
            )
            return updated


__all__ = [
    "VersionStatusService",
    "validate_transition",
]
