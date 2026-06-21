"""Single-Placeholder-Preview fuer den Editor-Overlay.

Loest einen *einzelnen* Platzhalter (`kind` + `target_id`) zu seinem Output auf —
fuer das Pill-Klick-Overlay im BlockNote-Editor. Im Gegensatz zu
`render_template_body` (das einen ganzen Body traversiert) ruft dieser Service
gezielt den passenden Resolver aus dem `REGISTRY`-Dict auf.

Read-only: keine Mutation, keine Rollen-Pruefung ueber die Workspace-
Mitgliedschaft hinaus (die steckt bereits in `get_current_workspace`).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status
from pydantic import BaseModel

from who2be_api.core.security import WorkspaceContext
from who2be_api.services.placeholders import RenderContext
from who2be_api.services.placeholders.registry import REGISTRY


class PlaceholderPreviewResponse(BaseModel):
    """Antwort des Preview-Endpoints fuer eine einzelne Pill.

    `text` ist der aufgeloeste Output (bei Miss der lokalisierte Fallback-String
    des Resolvers). `unresolved` ist `True`, wenn der Resolver keinen gueltigen
    Wert finden konnte (z. B. Playbook nicht gefunden, persona-field ohne
    Persona-Kontext) — das Frontend zeigt dann einen erklaerenden Hinweis.
    """

    kind: str
    target_id: str
    text: str
    unresolved: bool


class PlaceholderPreviewService:
    """Loest einen einzelnen Platzhalter ueber den REGISTRY-Resolver auf."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def preview(
        self,
        ctx: WorkspaceContext,
        kind: str,
        target_id: str,
        persona_id: UUID | None,
    ) -> PlaceholderPreviewResponse:
        """Resolved `kind`/`target_id` im Workspace-Kontext zu seinem Output.

        Unbekanntes `kind` -> 422 (der Editor schickt nur bekannte Kinds; ein
        422 macht einen Frontend-Bug sichtbar, statt still leeren Text zu zeigen).
        """
        resolver = REGISTRY.get(kind)
        if resolver is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unbekannter Placeholder-Typ: {kind}",
            )

        render_ctx = RenderContext(
            workspace_id=ctx.workspace_id,
            persona_id=persona_id,
            now=datetime.now(UTC),
            # Read-Scope des AUFRUFERS durchreichen (Security-Review HIGH-1):
            # Preview loest eine einzelne, FREI WAEHLBARE Pill auf — ohne
            # tool_policy/agent_id konnte ein `assigned`/`none`-Agent ueber
            # `?kind=playbook&target_id=<beliebige_uuid>` (bzw. resources-catalog)
            # jeden Inhalt/Katalog des Workspace lesen. None (Mensch/JWT) =
            # unrestricted.
            tool_policy=ctx.tool_policy,
            agent_id=ctx.agent_id,
        )
        async with self._pool.acquire() as conn:
            result = await resolver.resolve(target_id, render_ctx, conn)

        return PlaceholderPreviewResponse(
            kind=kind,
            target_id=target_id,
            text=result.text,
            unresolved=result.unresolved_key is not None,
        )
