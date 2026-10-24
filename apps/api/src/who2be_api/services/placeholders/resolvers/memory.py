"""Memory-Resolver: modus-bewusster Gedaechtnis-Hinweis (ADR-0044).

Einziger Ort der Gedaechtnis-Prompt-Logik: `memory_prompt_block` wird vom
`memory`-Placeholder (dieses Modul), vom `tools-overview`-Auto-Append
(Fallback fuer Templates ohne expliziten Placeholder) und von der
Laufzeit-Sektion in `PersonaService` genutzt — ein Wortlaut ueberall. Die
Saetze selbst (DE/EN) liegen in `placeholders/_texts.py`.

Copy-Herkunft: Builder-Briefing 2026-07-19, angepasst an die reale
Schleusen-Mechanik (suggest = serverseitiges `pending` + Freigabe durch den
Workspace-Besitzer in der UI — KEINE Chat-Bestaetigung vor dem Schreiben).
"""

from __future__ import annotations

import logging

import asyncpg

from who2be_api.services.placeholders._core import RenderContext, ResolveResult
from who2be_api.services.placeholders._texts import texts_for
from who2be_models import AgentToolPolicy

logger = logging.getLogger(__name__)


def memory_prompt_block(policy: AgentToolPolicy, locale: str | None = None) -> str:
    """Der modus-/direktive-abhaengige Gedaechtnis-Block; `off` → leer.

    Direktive-Overlay wird an den Modus-Text angehaengt; die Direktive ist
    reine Textstaerke, kein Recht (ADR-0044) — sie aendert nie das Tool-Gating.
    `locale` (Sprachkuerzel oder BCP-47) waehlt die Sprache; fehlt sie, Deutsch.
    """
    t = texts_for(locale)
    mode_text = t.memory_modes.get(policy.memory_mode)
    if mode_text is None:  # off
        return ""
    return mode_text + t.memory_directives[policy.memory_directive]


class MemoryPromptResolver:
    """Expandiert den `memory`-Placeholder zum modus-bewussten Hinweis.

    Liest `memory_mode` + `memory_directive` des gerenderten Agenten aus
    `ctx.tool_policy`. `off` oder fehlende Policy (z. B. Persona-Body-Render
    ohne Agent-Kontext) rendert den leeren String — bewusst KEIN Miss und nie
    ein Fehler: der Placeholder darf in jedem Template stehen, ohne bei
    deaktiviertem Gedaechtnis Rauschen oder Warnungen zu erzeugen.

    `target_id` bleibt ungenutzt (analog `tools-overview`).
    """

    async def resolve(
        self,
        target_id: str,  # noqa: ARG002
        ctx: RenderContext,
        db: asyncpg.Connection,  # noqa: ARG002
    ) -> ResolveResult:
        policy = ctx.tool_policy
        if policy is None:
            return ResolveResult(text="")
        return ResolveResult(text=memory_prompt_block(policy, ctx.locale))
