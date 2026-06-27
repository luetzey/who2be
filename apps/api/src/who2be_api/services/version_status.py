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

from collections.abc import Callable
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_unmanaged,
)
from who2be_api.services.promote_validation import (
    validate_promote_persona,
    validate_promote_playbook,
    validate_promote_resource,
)
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_models import (
    ALLOWED_TRANSITIONS,
    DEFAULT_LOCALE,
    AgentCapability,
    EntityType,
    PersonaVersionRead,
    PlaybookVersionRead,
    ResourceVersionRead,
    StatusHistoryEntry,
    SystemPromptTemplateVersionRead,
    VersionStatus,
    WorkspaceRole,
)


def _not_found(entity_type: EntityType) -> HTTPException:
    label = {
        "persona": "Persona",
        "playbook": "Playbook",
        "resource": "Resource",
        "system_prompt_template": "System-Prompt-Template",
    }[entity_type]
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{label}-Version nicht gefunden.",
    )


def _forbidden_transition(from_status: VersionStatus, to_status: VersionStatus) -> ApiGateError:
    # State-Machine verbietet den Uebergang — fuer den Aufrufer endgueltig an
    # diesem Ausgangsstatus (`none`); ein anderer Pfad waere noetig.
    return ApiGateError(
        status=status.HTTP_409_CONFLICT,
        reason="forbidden_transition",
        actionable_by="none",
        detail=(f"Status-Uebergang {from_status.value} → {to_status.value} ist nicht erlaubt."),
    )


def _invariant_violation() -> ApiGateError:
    # Partial-Unique-Index aus 0011 hat zugeschlagen. Race zwischen
    # zwei parallelen Promotions — der zweite Versuch bekommt 409 statt 500.
    # Der Agent kann nach Re-Read des aktuellen Stands erneut versuchen (`agent`).
    return ApiGateError(
        status=status.HTTP_409_CONFLICT,
        reason="concurrent_conflict",
        actionable_by="agent",
        detail="Konfliktierende Status-Aenderung (parallele Transition).",
    )


# Promote-Validator-Map: EntityType -> Validator-Funktion.
# `system_prompt_template` hat keine Pflichtfeld-Tabelle in Welle 4;
# der Slot bleibt None (kein Promote-Gate fuer Templates).
_ValidatorFn = Callable[[str, dict[str, Any], VersionStatus], None]
_PROMOTE_VALIDATORS: dict[str, _ValidatorFn] = {
    "persona": validate_promote_persona,
    "playbook": validate_promote_playbook,
    "resource": validate_promote_resource,
}


def validate_transition(from_status: VersionStatus, to_status: VersionStatus) -> None:
    """Wirft 409, wenn der Uebergang nicht erlaubt ist."""
    if to_status not in ALLOWED_TRANSITIONS[from_status]:
        raise _forbidden_transition(from_status, to_status)


def required_role_for_transition(
    from_status: VersionStatus, to_status: VersionStatus
) -> WorkspaceRole:
    """Mindestrolle fuer einen (erlaubten) Status-Uebergang (ADR-0023).

    Admin-only sind die Uebergaenge, die den publizierten (aktiven) Stand
    veraendern: Promote-to-Active (`review → active`), Retire
    (`active → inactive`) und Reset-auf-Draft (`active → draft`, Track A —
    holt die aktive Version zur Bearbeitung zurueck). Alle uebrigen erlaubten
    Uebergaenge (`draft → review`, `review → draft`, `inactive → draft`) sind
    ab `editor` zulaessig.
    """
    if (
        to_status in (VersionStatus.active, VersionStatus.inactive)
        or from_status == VersionStatus.active
    ):
        return WorkspaceRole.admin
    return WorkspaceRole.editor


# Schreib-Capability je EntityType fuer draft/review-Uebergaenge. Promote/Retire
# (active/inactive) mappt unabhaengig vom Typ auf `promote_retire`.
# System-Prompt-Templates haben einen eigenen Sonderzweig in
# `_require_transition_capability` (ADR-0040): draft/review via
# `system_prompt_write`, active/inactive bleibt fuer Agent-Token hart gesperrt.
_WRITE_CAPABILITY: dict[str, AgentCapability] = {
    "persona": AgentCapability.persona_write,
    "playbook": AgentCapability.playbook_write,
    "resource": AgentCapability.resource_write,
}


def _require_transition_capability(
    ctx: WorkspaceContext, entity_type: EntityType, to_status: VersionStatus
) -> None:
    """Pro-Agent-Gate fuer Status-Uebergaenge (No-Op fuer ungebundene Tokens).

    Promote/Retire (→active/→inactive) verlangen `promote_retire`; draft/review
    die Schreib-Capability der Domain. System-Prompt-Templates: draft/review via
    `system_prompt_write`, aber active/inactive bleibt hart gesperrt (ADR-0040).
    """
    if ctx.tool_policy is None:
        return
    if entity_type == "system_prompt_template":
        # ADR-0040: Agenten duerfen Templates verfassen + zur Review einreichen
        # (draft/review mit `system_prompt_write`), aber NIE selbst scharfschalten
        # oder zurueckziehen — das Aktivieren des eigenen System-Prompts bleibt
        # eine menschliche Handlung (Injection-Schutz, ADR-0012).
        if to_status in (VersionStatus.active, VersionStatus.inactive):
            raise ApiGateError(
                status=status.HTTP_403_FORBIDDEN,
                reason="missing_capability",
                actionable_by="none",
                detail=(
                    "Agent-gebundene Tokens duerfen System-Prompt-Templates nicht "
                    "aktivieren oder zurueckziehen — das uebernimmt ein Mensch/Admin."
                ),
            )
        require_capability(ctx, AgentCapability.system_prompt_write)
        return
    if entity_type not in _WRITE_CAPABILITY:
        # Sonstige Nicht-MCP-Entities (z. B. Version-Sub-Typen) bleiben fuer einen
        # agent-gebundenen Token endgueltig gesperrt (`none`).
        raise ApiGateError(
            status=status.HTTP_403_FORBIDDEN,
            reason="missing_capability",
            actionable_by="none",
            detail="Agent-gebundene Tokens duerfen diese Entitaet nicht aendern.",
        )
    if to_status in (VersionStatus.active, VersionStatus.inactive):
        require_capability(ctx, AgentCapability.promote_retire)
        # Optionale Pro-Domain-Verfeinerung (ADR-0039): `transition_grants` kann
        # `promote_retire` pro Domain/Richtung weiter einschraenken.
        promote = to_status == VersionStatus.active
        if not ctx.tool_policy.can_transition(entity_type, promote=promote):
            action = "aktivieren" if promote else "zurueckziehen"
            raise ApiGateError(
                status=status.HTTP_403_FORBIDDEN,
                reason="missing_capability",
                actionable_by="human",
                detail=f"Dieser Agent darf {entity_type} nicht {action} (transition_grants).",
            )
    else:
        require_capability(ctx, _WRITE_CAPABILITY[entity_type])


_PERSONA_TABLES = ("persona", "persona_version", "persona_id")
_PLAYBOOK_TABLES = ("playbook", "playbook_version", "playbook_id")
_RESOURCE_TABLES = ("resource", "resource_version", "resource_id")
_TEMPLATE_TABLES = (
    "system_prompt_template",
    "system_prompt_template_version",
    "template_id",
)


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
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaVersionRead:
        row = await self._transition(
            ctx, "persona", _PERSONA_TABLES, persona_id, version, to_status, note, locale
        )
        return PersonaVersionRead.model_validate(dict(row))

    async def transition_playbook_version(
        self,
        ctx: WorkspaceContext,
        playbook_id: UUID,
        version: int,
        to_status: VersionStatus,
        note: str | None,
        locale: str = DEFAULT_LOCALE,
    ) -> PlaybookVersionRead:
        row = await self._transition(
            ctx, "playbook", _PLAYBOOK_TABLES, playbook_id, version, to_status, note, locale
        )
        return PlaybookVersionRead.model_validate(dict(row))

    async def transition_resource_version(
        self,
        ctx: WorkspaceContext,
        resource_id: UUID,
        version: int,
        to_status: VersionStatus,
        note: str | None,
        locale: str = DEFAULT_LOCALE,
    ) -> ResourceVersionRead:
        row = await self._transition(
            ctx, "resource", _RESOURCE_TABLES, resource_id, version, to_status, note, locale
        )
        return ResourceVersionRead.model_validate(dict(row))

    async def transition_system_prompt_template_version(
        self,
        ctx: WorkspaceContext,
        template_id: UUID,
        version: int,
        to_status: VersionStatus,
        note: str | None,
        locale: str = DEFAULT_LOCALE,
    ) -> SystemPromptTemplateVersionRead:
        row = await self._transition(
            ctx,
            "system_prompt_template",
            _TEMPLATE_TABLES,
            template_id,
            version,
            to_status,
            note,
            locale,
        )
        return SystemPromptTemplateVersionRead.model_validate(dict(row))

    async def provenance_persona(
        self, ctx: WorkspaceContext, persona_id: UUID, version: int
    ) -> list[StatusHistoryEntry]:
        return await self._provenance(ctx, "persona", _PERSONA_TABLES, persona_id, version)

    async def provenance_playbook(
        self, ctx: WorkspaceContext, playbook_id: UUID, version: int
    ) -> list[StatusHistoryEntry]:
        return await self._provenance(ctx, "playbook", _PLAYBOOK_TABLES, playbook_id, version)

    async def provenance_resource(
        self, ctx: WorkspaceContext, resource_id: UUID, version: int
    ) -> list[StatusHistoryEntry]:
        return await self._provenance(ctx, "resource", _RESOURCE_TABLES, resource_id, version)

    async def provenance_system_prompt_template(
        self, ctx: WorkspaceContext, template_id: UUID, version: int
    ) -> list[StatusHistoryEntry]:
        return await self._provenance(
            ctx, "system_prompt_template", _TEMPLATE_TABLES, template_id, version
        )

    async def _provenance(
        self,
        ctx: WorkspaceContext,
        entity_type: EntityType,
        tables: tuple[str, str, str],
        entity_id: UUID,
        version: int,
    ) -> list[StatusHistoryEntry]:
        """Liefert die `status_history`-Kette einer Version (chronologisch).

        Beantwortet „warum aktiv" — die Episoden, die diese Version durch die
        State-Machine bewegt haben. Workspace-Isolation ueber das Entity; eine
        Version ohne Historie (Alt-Daten vor Migration 0029) liefert `[]`.
        """
        entity_tbl, _version_tbl, _fk_col = tables
        async with self._pool.acquire() as conn:
            owned = await conn.fetchval(
                f"SELECT 1 FROM {entity_tbl} WHERE id = $1 AND workspace_id = $2",
                entity_id,
                ctx.workspace_id,
            )
            if owned is None:
                raise _not_found(entity_type)
            rows = await conn.fetch(
                "SELECT id, entity_type, entity_id, version, from_status, to_status, "
                "changed_by, changed_at, note "
                "FROM status_history "
                "WHERE entity_type = $1 AND entity_id = $2 AND version = $3 "
                "ORDER BY changed_at ASC",
                entity_type,
                entity_id,
                version,
            )
        return [StatusHistoryEntry.model_validate(dict(row)) for row in rows]

    async def _transition(
        self,
        ctx: WorkspaceContext,
        entity_type: EntityType,
        tables: tuple[str, str, str],
        entity_id: UUID,
        version: int,
        to_status: VersionStatus,
        note: str | None,
        locale: str = DEFAULT_LOCALE,
    ) -> asyncpg.Record:
        entity_tbl, version_tbl, fk_col = tables
        async with self._pool.acquire() as conn, conn.transaction():
            # Ziel-Version laden + sperren. JOIN ueber das Entity sichert,
            # dass die Version im richtigen Workspace lebt. `version` ist seit
            # Content-i18n nur noch je (entity, locale) eindeutig — daher der
            # zusaetzliche `locale`-Filter (ADR-0027).
            # `e.name` und `pv.content` werden fuer die Promote-Validation
            # mitgeladen (Welle 4).
            target = await conn.fetchrow(
                f"SELECT pv.status, pv.content, e.name, e.is_managed FROM {version_tbl} pv "
                f"JOIN {entity_tbl} e ON e.id = pv.{fk_col} "
                f"WHERE pv.{fk_col} = $1 AND pv.version = $2 "
                "AND e.workspace_id = $3 AND pv.locale = $4 "
                "FOR UPDATE OF pv",
                entity_id,
                version,
                ctx.workspace_id,
                locale,
            )
            if target is None:
                raise _not_found(entity_type)
            # Managed-Lock: vom System verwaltete Aggregate duerfen ueber die API
            # nicht transitioniert werden (der Start-Sync nutzt rohes SQL).
            require_unmanaged(target["is_managed"])
            from_status = VersionStatus(target["status"])
            validate_transition(from_status, to_status)
            # RBAC-Gate nach der State-Machine: erst pruefen, ob der Uebergang
            # ueberhaupt erlaubt ist (409), dann ob die Rolle ihn ausfuehren
            # darf (403). Promote/Retire verlangen admin (ADR-0023).
            require_role(ctx, required_role_for_transition(from_status, to_status))
            # Pro-Agent-Gate zusaetzlich zum Rollen-Gate (No-Op fuer ungebundene Tokens).
            _require_transition_capability(ctx, entity_type, to_status)

            # Promote-Validation (Welle 4): Pflichtfelder vor draft->review/active.
            # Nur fuer Entities mit Pflichtfeld-Tabelle (persona, playbook, resource).
            # system_prompt_template hat kein Gate. PromoteValidationError propagiert
            # zum Exception-Handler in main.py (application/problem+json, 409).
            # asyncpg gibt jsonb-Felder dank registered codec als dict zurueck.
            validator = _PROMOTE_VALIDATORS.get(entity_type)
            if validator is not None and from_status == VersionStatus.draft:
                content_dict: dict[str, Any] = target["content"]
                validator(target["name"], content_dict, to_status)

            # Composite-Aktiv-Invariante (WP-4 / #256): ein Composite-Playbook
            # darf erst `active` werden, wenn ALLE referenzierten Sub-Playbooks
            # eine aktive Version haben. Die Pruefung sitzt bewusst hier (Promote-
            # Zeit) statt an Link-Zeit (`set_composition`) — so darf man Drafts
            # frei verketten und die Invariante haelt erst beim Publish des
            # Eltern-Composite. Nur fuer playbook->active relevant.
            if entity_type == "playbook" and to_status == VersionStatus.active:
                await self._assert_composite_children_active(conn, entity_id)

            # Active-Promotion: die bisherige Active-Version derselben
            # Entity zuerst auf `inactive` setzen — sonst kollidiert der
            # Partial-Unique-Index. Audit-Eintrag fuer das implizite
            # Inactive-Setzen schreiben.
            if to_status == VersionStatus.active:
                # Nur die Active-Version DERSELBEN Sprache inaktivieren — andere
                # Sprachvarianten haben ihren eigenen Active-Slot (per-locale
                # Partial-Unique-Index).
                prev_active_version = await conn.fetchval(
                    f"UPDATE {version_tbl} SET status = 'inactive' "
                    f"WHERE {fk_col} = $1 AND locale = $2 AND status = 'active' "
                    "RETURNING version",
                    entity_id,
                    locale,
                )
                if prev_active_version is not None:
                    await self._history.record(
                        conn,
                        entity_type,
                        entity_id,
                        VersionStatus.active,
                        VersionStatus.inactive,
                        ctx.user_id,
                        note=(f"Auto-inactiviert durch Promotion von v{version} auf 'active'."),
                        version=prev_active_version,
                    )

            try:
                updated = await conn.fetchrow(
                    f"UPDATE {version_tbl} SET status = $1 "
                    f"WHERE {fk_col} = $2 AND version = $3 AND locale = $4 "
                    "RETURNING version, status, locale, content, created_by, created_at",
                    to_status.value,
                    entity_id,
                    version,
                    locale,
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
                version=version,
            )

            # Reset-auf-Draft (Track A): wird die aktive Version zur Bearbeitung
            # zurueckgeholt, reaktivieren wir die zuletzt aktive Version, damit
            # die Invariante „genau eine aktiv" haelt. `version → draft` hat oben
            # die Active-Slot freigeraeumt, also kollidiert der Partial-Unique-
            # Index nicht. Gibt es keine fruehere aktive Version, bleibt die
            # Entity ohne aktive Version (erlaubt, §3.1).
            if from_status == VersionStatus.active and to_status == VersionStatus.draft:
                await self._reactivate_previous(
                    conn, entity_type, version_tbl, fk_col, entity_id, version, ctx.user_id, locale
                )
            return updated

    async def _assert_composite_children_active(
        self, conn: asyncpg.Connection, parent_id: UUID
    ) -> None:
        """Wirft 409, wenn ein referenziertes Sub-Playbook nicht aktiv ist.

        Composite-Aktiv-Invariante (WP-4 / #256, ADR-0024): ein Composite darf
        nur `active` werden, wenn jedes seiner Kinder eine aktive Version hat.
        Geprueft in derselben Transaktion wie der Transition-UPDATE (konsistent
        gegen parallele Kind-Retires). Ein Kind ohne `status='active'`-Version
        blockiert — der Owner muss das Kind erst aktivieren (`human`).
        """
        blocked = await conn.fetch(
            "SELECT child.id, child.name "
            "FROM playbook_composition pc "
            "JOIN playbook child ON child.id = pc.child_id "
            "WHERE pc.parent_id = $1 "
            "AND NOT EXISTS ("
            "    SELECT 1 FROM playbook_version cv "
            "    WHERE cv.playbook_id = child.id AND cv.status = 'active'"
            ") "
            "ORDER BY pc.position ASC",
            parent_id,
        )
        if not blocked:
            return
        names = ", ".join(f"{row['name']} ({row['id']})" for row in blocked)
        raise ApiGateError(
            status=status.HTTP_409_CONFLICT,
            reason="composite_child_inactive",
            actionable_by="human",
            detail=(
                "Composite kann nicht aktiviert werden — folgende Sub-Playbooks "
                f"haben keine aktive Version: {names}. Aktiviere sie zuerst."
            ),
        )

    async def _reactivate_previous(
        self,
        conn: asyncpg.Connection,
        entity_type: EntityType,
        version_tbl: str,
        fk_col: str,
        entity_id: UUID,
        reset_version: int,
        user_id: UUID,
        locale: str = DEFAULT_LOCALE,
    ) -> None:
        """Reaktiviert die zuletzt aktive Version nach einem Reset-auf-Draft.

        „Zuletzt aktiv" = juengste `status_history`-Episode mit
        `to_status='active'` fuer eine ANDERE Version als die gerade
        zurueckgesetzte. Nur reaktiviert, wenn diese Version noch existiert und
        aktuell `inactive` ist (Defense gegen Races / zwischenzeitlich
        weiterbearbeitete Versionen).
        """
        prev_version = await conn.fetchval(
            "SELECT version FROM status_history "
            "WHERE entity_type = $1 AND entity_id = $2 AND to_status = 'active' "
            "AND version IS NOT NULL AND version <> $3 "
            "ORDER BY changed_at DESC LIMIT 1",
            entity_type,
            entity_id,
            reset_version,
        )
        if prev_version is None:
            return
        reactivated = await conn.fetchval(
            f"UPDATE {version_tbl} SET status = 'active' "
            f"WHERE {fk_col} = $1 AND version = $2 AND locale = $3 AND status = 'inactive' "
            "RETURNING version",
            entity_id,
            prev_version,
            locale,
        )
        if reactivated is not None:
            await self._history.record(
                conn,
                entity_type,
                entity_id,
                VersionStatus.inactive,
                VersionStatus.active,
                user_id,
                note=f"Reaktiviert nach Reset von v{reset_version} auf Draft.",
                version=prev_version,
            )


__all__ = [
    "VersionStatusService",
    "required_role_for_transition",
    "validate_transition",
]
