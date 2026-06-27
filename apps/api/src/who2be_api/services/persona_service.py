"""Geschaeftslogik fuer das Persona-Aggregat.

Workspace-Pruefung liegt im SQL der Repository-Schicht; der Service
uebersetzt ein fehlendes Ergebnis (`None`) in ein `HTTPException 404`.

Phase 2.1b: Der `active_only`-Schalter reicht in den Lese-Pfad durch (Plan
§2.1.D). Statt pauschal fuer jeden API-Token folgt die Draft-Sichtbarkeit der
Write-Capability: ein Agent mit `persona_write` (Editor-/Meta-Agent wie der
Builder) liest die Current-Version inkl. Draft/Review (`ctx.sees_drafts`), reine
Konsum-Agenten bleiben auf `active`. Die Draft-on-Edit-Konfliktlage aus dem Repo
wird auf 409 gemappt.
"""

import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status
from pydantic import BaseModel

from who2be_api.core.agent_scope import require_read_flag
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_write_rate,
    require_write_tags,
)
from who2be_api.repositories.persona_repository import PersonaRepository
from who2be_api.repositories.usage_repository import UsageRepository
from who2be_api.services.placeholders import RenderContext, render_template_body
from who2be_api.services.placeholders.registry import render_skills_table
from who2be_api.services.version_diff import compute_version_diff
from who2be_models import (
    DEFAULT_LOCALE,
    AgentCapability,
    DeleteBlocked,
    PersonaCreate,
    PersonaRead,
    PersonaUpdate,
    PersonaUsage,
    PersonaVersionContent,
    PersonaVersionRead,
    VersionDiff,
    VersionStatus,
    WorkspaceRole,
    encode_cursor,
)


class PersonaRenderResponse(BaseModel):
    """Antwort des Persona-Render-Endpoints: expandierter Profil-Body + Misses.

    Spiegelt den Playbook-Render-Vertrag (`PlaybookRenderResponse`): `body_rendered`
    ist der durch den Placeholder-Renderer expandierte Profil-Body (Katalog-Pills
    fetch-time gegen die aktiven Playbooks/Resources des Workspace). `unresolved`
    listet deduplizierte Miss-Keys.

    Hinweis: Die Skills-Tabelle ist derzeit deaktiviert (Coming Soon, ADR-0026) —
    `render_skills_table` liefert `""`, es wird nichts angehaengt.
    """

    body_rendered: str
    unresolved: list[str]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona nicht gefunden.")


def _delete_blocked(usages: list[PersonaUsage]) -> HTTPException:
    """409: eingehende Agenten-Referenzen blockieren das Persona-Delete.

    `detail` ist der strukturierte `DeleteBlocked`-Body (Klartext + maschinen-
    lesbare Verwender-Liste), den das Frontend fuer die Blockier-Anzeige nutzt.
    """
    names = ", ".join(u.agent_name for u in usages)
    detail = DeleteBlocked(
        message=(
            f"Persona kann nicht geloescht werden — sie wird von {len(usages)} "
            f"Agent(en) genutzt: {names}. Loese die Verknuepfungen zuerst."
        ),
        blocked_by={"agents": list(usages)},
    )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail.model_dump(mode="json"),
    )


def _invalid_against() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Ungueltiger 'against'-Parameter; erwartet 'active' oder eine Versions-Nummer.",
    )


def _draft_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Es existiert bereits ein Draft. Promote oder verwirf den "
            "bestehenden Draft, bevor du erneut editierst."
        ),
    )


def _review_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Diese Version steht in der Review — Auto-Save ist deaktiviert. "
            "Lehne die Review erst ab, bevor du weiter editierst."
        ),
    )


class PersonaService:
    """Legt Personae an, liest, listet, aktualisiert und versioniert sie.

    Track F: haelt zusaetzlich den Pool fuer den Render-Pfad (`render`), der den
    Persona-Profil-Body durch den Placeholder-Renderer jagt (Katalog-Pills
    fetch-time). Der Pool ist optional, damit Unit-Tests, die nur die
    Versions-/CRUD-Methoden treffen, den Service weiterhin nur mit dem Repo
    konstruieren koennen.
    """

    def __init__(
        self,
        persona_repo: PersonaRepository,
        pool: asyncpg.Pool | None = None,
        usage_repo: UsageRepository | None = None,
    ) -> None:
        self._repo = persona_repo
        self._pool = pool
        self._usage_repo = usage_repo

    async def create(self, ctx: WorkspaceContext, data: PersonaCreate) -> PersonaRead:
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.persona_write)
        require_write_rate(ctx)
        require_write_tags(ctx, "persona", data.content.tags)
        return await self._repo.insert(
            ctx.workspace_id, ctx.user_id, data.name, data.content, data.locales
        )

    async def list_all(
        self,
        ctx: WorkspaceContext,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
        locale: str = DEFAULT_LOCALE,
    ) -> tuple[list[PersonaRead], str | None]:
        require_read_flag(ctx, "persona_read", "Personas")
        # `limit + 1`-Peek: gibt es eine Folge-Zeile, codieren wir den
        # Cursor aus der letzten Zeile der Seite — sonst `None` (Ende).
        rows = await self._repo.list_by_workspace(
            ctx.workspace_id,
            limit + 1,
            cursor,
            active_only=not ctx.sees_drafts(AgentCapability.persona_write),
            locale=locale,
        )
        if len(rows) > limit:
            items = rows[:limit]
            tail = items[-1]
            return items, encode_cursor(tail.created_at, tail.id)
        return rows, None

    async def get(
        self, ctx: WorkspaceContext, persona_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> PersonaRead:
        require_read_flag(ctx, "persona_read", "Personas")
        persona = await self._repo.fetch(
            ctx.workspace_id,
            persona_id,
            active_only=not ctx.sees_drafts(AgentCapability.persona_write),
            locale=locale,
        )
        if persona is None:
            raise _not_found()
        return persona

    async def render(
        self, ctx: WorkspaceContext, persona_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> PersonaRenderResponse:
        """Expandiert den Persona-Profil-Body durch den Placeholder-Renderer (Track F).

        Der BlockNote-Profil-Body (`content.content.blocks`) wird mit
        `persona_id=persona.id` gerendert — so loesen die Katalog-Pills
        (`playbooks-catalog`/`resources-catalog`) sowie die Slash-Refs
        fetch-time gegen die aktiven Playbooks/Resources des Workspace auf.
        Die Skills-Tabelle ist derzeit deaktiviert (Coming Soon, ADR-0026) und
        wird nicht angehaengt — `render_skills_table` liefert `""`.

        Wird vom MCP-Tool `get_persona` genutzt (der MCP-Prozess hat keinen
        DB-Zugriff). Leerer Body + keine Skills → leerer `body_rendered`.
        """
        persona = await self.get(ctx, persona_id, locale=locale)
        body_blocks = persona.content.content.blocks if persona.content.content is not None else []
        body_json = json.dumps([block.model_dump(mode="json") for block in body_blocks])

        render_ctx = RenderContext(
            workspace_id=ctx.workspace_id,
            persona_id=persona.id,
            now=datetime.now(UTC),
            # Read-Scope des AUFRUFERS durchreichen (Security-Review MEDIUM-1):
            # ohne tool_policy/agent_id expandieren Katalog-Pills
            # (`playbooks-catalog`/`resources-catalog`) und `{{playbook:id}}`/
            # `{{resource:id}}`-Refs workspace-weit — ein `assigned`-Agent saehe
            # so nicht zugewiesene Inhalte. None (Mensch/JWT) = unrestricted.
            tool_policy=ctx.tool_policy,
            agent_id=ctx.agent_id,
        )
        if self._pool is None:  # pragma: no cover - im Prod immer gesetzt
            raise RuntimeError("PersonaService.render benoetigt einen DB-Pool.")
        async with self._pool.acquire() as conn:
            body_rendered, unresolved = await render_template_body(body_json, render_ctx, conn)

        skills_table = render_skills_table(
            [skill.model_dump(mode="json") for skill in persona.content.skills]
        )
        if skills_table:
            body_rendered = f"{body_rendered}\n\n{skills_table}" if body_rendered else skills_table

        return PersonaRenderResponse(body_rendered=body_rendered, unresolved=unresolved)

    async def _check_update_tags(
        self, ctx: WorkspaceContext, persona_id: UUID, incoming_tags: list[str], locale: str
    ) -> None:
        """Tag-Scope beim Update: eingehende Tags + (nur bei Restriktion) Bestand."""
        require_write_tags(ctx, "persona", incoming_tags)
        if ctx.tool_policy is not None and ctx.tool_policy.write_tags_for("persona") is not None:
            existing = await self.get(ctx, persona_id, locale)
            require_write_tags(ctx, "persona", existing.content.tags)

    async def update(
        self,
        ctx: WorkspaceContext,
        persona_id: UUID,
        data: PersonaUpdate,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaRead:
        """Erzeugt eine neue Version der Persona (im `locale`-Track).

        Auf einer Active-Persona entsteht eine neue Draft-Version (Plan §2.1.C);
        existiert bereits ein Draft, antwortet der Service mit 409.
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.persona_write)
        require_write_rate(ctx)
        await self._check_update_tags(ctx, persona_id, data.content.tags, locale)
        outcome = await self._repo.update(
            ctx.workspace_id, ctx.user_id, persona_id, data.name, data.content, locale
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.persona is None:
            raise _not_found()
        return outcome.persona

    async def update_draft(
        self,
        ctx: WorkspaceContext,
        persona_id: UUID,
        data: PersonaUpdate,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaRead:
        """Auto-Save-Pfad (PATCH `.../draft`) — upsertet die Draft-Version.

        Im Gegensatz zu `update` schreibt dieser Pfad in einen bestehenden
        Draft in-place, ohne neue Version anzulegen. Active bleibt
        unangetastet. 409 nur fuer den Edge-Case "Review-Pending"
        (siehe Repository-Doku).
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.persona_write)
        require_write_rate(ctx)
        await self._check_update_tags(ctx, persona_id, data.content.tags, locale)
        outcome = await self._repo.upsert_draft(
            ctx.workspace_id, ctx.user_id, persona_id, data.name, data.content, locale
        )
        if outcome.conflict == "review_pending":
            raise _review_conflict()
        if outcome.persona is None:
            raise _not_found()
        return outcome.persona

    async def list_versions(
        self, ctx: WorkspaceContext, persona_id: UUID, locale: str = DEFAULT_LOCALE
    ) -> list[PersonaVersionRead]:
        versions = await self._repo.list_versions(ctx.workspace_id, persona_id, locale)
        if versions is None:
            raise _not_found()
        return versions

    async def get_version(
        self, ctx: WorkspaceContext, persona_id: UUID, version: int, locale: str = DEFAULT_LOCALE
    ) -> PersonaVersionRead:
        found = await self._repo.fetch_version(ctx.workspace_id, persona_id, version, locale)
        if found is None:
            raise _not_found()
        return found

    async def restore(
        self,
        ctx: WorkspaceContext,
        persona_id: UUID,
        source_version: int,
        locale: str = DEFAULT_LOCALE,
    ) -> PersonaRead:
        """Stellt den Snapshot `source_version` als neue Draft wieder her (§3.1).

        Non-destruktiv: aus dem Snapshot entsteht eine frische Draft-Version.
        `fetch_version` hat den Snapshot bereits strict gegen das aktuelle
        Content-Schema validiert (ADR-0009). 409 bei bereits offenem Draft.
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.persona_write)
        require_write_rate(ctx)
        snapshot = await self._repo.fetch_version(
            ctx.workspace_id, persona_id, source_version, locale
        )
        if snapshot is None:
            raise _not_found()
        require_write_tags(ctx, "persona", snapshot.content.tags)
        outcome = await self._repo.restore_version(
            ctx.workspace_id, ctx.user_id, persona_id, snapshot.content, locale
        )
        if outcome.conflict == "draft_exists":
            raise _draft_conflict()
        if outcome.persona is None:
            raise _not_found()
        return outcome.persona

    async def diff(
        self,
        ctx: WorkspaceContext,
        persona_id: UUID,
        version: int,
        against: str,
        locale: str = DEFAULT_LOCALE,
    ) -> VersionDiff:
        """Strukturierter Feld-/Block-Diff der Version `version` gegen `against`."""
        target = await self._repo.fetch_version(ctx.workspace_id, persona_id, version, locale)
        if target is None:
            raise _not_found()
        versions = await self._repo.list_versions(ctx.workspace_id, persona_id, locale)
        if versions is None:
            raise _not_found()
        base_version, base_content = self._resolve_against(against, versions)
        before = base_content.model_dump(mode="json") if base_content is not None else {}
        return compute_version_diff(
            version=version,
            against=against,
            against_version=base_version,
            before=before,
            after=target.content.model_dump(mode="json"),
        )

    def _resolve_against(
        self, against: str, versions: list[PersonaVersionRead]
    ) -> tuple[int | None, PersonaVersionContent | None]:
        if against == "active":
            for candidate in versions:
                if candidate.status == VersionStatus.active:
                    return candidate.version, candidate.content
            return None, None
        try:
            wanted = int(against)
        except ValueError:
            raise _invalid_against() from None
        for candidate in versions:
            if candidate.version == wanted:
                return candidate.version, candidate.content
        raise _not_found()

    async def list_tags(self, ctx: WorkspaceContext, locale: str = DEFAULT_LOCALE) -> list[str]:
        """DISTINCT-Tags des Workspaces — Datenquelle fuer den Tag-Picker."""
        return await self._repo.list_distinct_tags(ctx.workspace_id, locale)

    async def delete(self, ctx: WorkspaceContext, persona_id: UUID) -> None:
        """Hard-Delete der Persona (ADR-0032).

        Editor-Gate (analog `agent_service.delete`). Blockiert mit 409, solange
        ein Agent die Persona nutzt (`agent.persona_id` ON DELETE RESTRICT) —
        der 409-Body listet die blockierenden Agenten. Existiert die Persona
        nicht (mehr), antwortet 404. Die FK-Kaskaden raeumen Versionen und
        ausgehende Playbook-Links beim DELETE selbst ab.
        """
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.persona_write)
        require_write_rate(ctx)
        persona = await self._repo.fetch(ctx.workspace_id, persona_id)
        if persona is None:
            raise _not_found()
        if self._usage_repo is None:  # pragma: no cover - im Prod immer gesetzt
            raise RuntimeError("PersonaService.delete benoetigt ein UsageRepository.")
        usages = await self._usage_repo.list_persona_usages(ctx.workspace_id, persona_id)
        if usages:
            raise _delete_blocked(usages)
        deleted = await self._repo.delete(ctx.workspace_id, persona_id)
        if not deleted:
            raise _not_found()
