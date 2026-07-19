"""Geschaeftslogik fuer das Agent-Memory (ADR-0044).

Zwei getrennte Pfade:

- **Agent-Pfad** (`save`/`search`/`list_active`): nur fuer agent-gebundene
  Tokens, gated ueber `require_memory_mode` (off < read_only < suggest < auto)
  + `require_write_rate`. `save` durchlaeuft IMMER die serverseitigen Waechter
  (Injection-Filter, Importance-Schwelle, Dedup, Cap) — „Vertrauen ist gut,
  Validierung ist Pflicht" (Kap. 13.4) — und persistiert je nach Modus als
  `pending` (suggest → Kurations-Schleuse) oder `active` (auto).
- **Management-Pfad** (`list_memories`/`triage`/`update_memory`/`delete_*`):
  human-only (editor+). Agent-gebundene Tokens sind hier HART gesperrt — sonst
  koennte sich ein suggest-Agent seine eigenen Vorschlaege freigeben (Umgehung
  der Schleuse) oder fremde Memories lesen.

`context` (Triage-Hilfe) erscheint nur in `MemoryRead` (Management-Sicht),
nie in `MemoryHit` (Retrieval) — kein Injection-Vektor Richtung Prompt.
"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_memory_mode,
    require_role,
    require_write_rate,
)
from who2be_api.repositories.memory_repository import MemoryRepository
from who2be_models import (
    MEMORY_MAX_PER_AGENT,
    MEMORY_MIN_IMPORTANCE,
    MemoryCreate,
    MemoryGuardConfig,
    MemoryGuardMode,
    MemoryHit,
    MemoryMode,
    MemoryRead,
    MemoryStatus,
    MemoryTriage,
    MemoryTriageAction,
    MemoryUpdate,
    WorkspaceRole,
)

# Deckel fuer Retrieval-Antworten (Token-Budget des Client-Prompts).
_SEARCH_K_MAX = 20
_LIST_LIMIT_MAX = 50

# Injection-Waechter: blockt KI-gerichtete Manipulationsmuster — bewusst NICHT
# jede legitime Instruktions-Praeferenz („antworte immer auf Deutsch" ist ein
# gewolltes Memory der Kategorie `instruction`). Der Filter ist Vorfilter,
# nicht Richter: den Graubereich entscheidet die menschliche Triage.
#
# WICHTIG (False-Positive-Fix 2026-07-19): „System-Prompt" allein ist in
# Who2Be Alltagsvokabular (Templates, Placeholder, Builder-Arbeit) und darf
# NICHT blocken — nur die Kombination mit einem Manipulations-Verb
# („verrate/zeige/gib ... System-Prompt", „ignoriere ... System-Prompt")
# ist ein Angriffsmuster.
_INJECTION_PATTERN = re.compile(
    r"(?i)("
    r"(ignor\w*|missachte)\s+(alle[nr]?\s+|deine[nr]?\s+|den\s+|all\s+|your\s+|previous\s+|the\s+)?"
    r"(regeln|anweisungen|instruktionen|rules|instructions|guidelines|system.?prompts?)"
    r"|(reveal|leak|dump|print|zeige|verrate|nenne|gib)\s+"
    r"(mir\s+)?(deinen\s+|den\s+|the\s+|your\s+)?system.?prompts?"
    r"|jailbreak"
    r"|disregard\s+(all|previous|your)"
    r"|vergiss\s+(alle|deine)\s+(regeln|anweisungen)"
    r"|override\s+(safety|rules|instructions)"
    r")"
)


def _covered_by_allow_phrase(text: str, span: tuple[int, int], allow_phrases: list[str]) -> bool:
    """True, wenn der Regex-Treffer `span` vollstaendig in einem Vorkommen
    einer Allow-Phrase liegt (case-insensitiv).

    Bewusst NICHT „Phrase kommt irgendwo im Text vor" — sonst koennte ein
    Angreifer eine Allow-Phrase einfach anhaengen, um den Filter zu umgehen.

    Die Phrasen-Suche laeuft als case-insensitive Regex auf dem ORIGINALTEXT
    (`re.escape` + IGNORECASE), nicht auf `text.casefold()`: casefold kann
    Stringlaengen aendern (ß→ss) und wuerde die Treffer-Spans verschieben
    (False-Allow-/False-Block-Risiko bei deutschem Text).
    """
    start, end = span
    for phrase in allow_phrases:
        for occurrence in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            if occurrence.start() <= start and end <= occurrence.end():
                return True
    return False


def _guard_rejection(config: MemoryGuardConfig, text: str) -> str | None:
    """Injection-Verdikt fuer `text` gemaess Workspace-Konfiguration.

    Liefert eine menschenlesbare Ablehnungs-Begruendung oder None (ok).
    `off` prueft nichts (bewusste Owner-Entscheidung — gilt auch fuer
    auto-Agenten); `custom` = Built-in mit Allow-Suppression + Block-Phrasen;
    `standard` = nur Built-in.
    """
    if config.mode == MemoryGuardMode.off:
        return None
    if config.mode == MemoryGuardMode.custom:
        # Gleiche Matching-Semantik wie die Allow-Suche (re.escape + IGNORECASE
        # auf dem Originaltext, Security-Review INFO-3). Die getroffene Phrase
        # wird bewusst NICHT ins Fehlerdetail reflektiert (Security-Review
        # LOW-2: kein admin-kontrollierter Text in den Agent-Kontext).
        for phrase in config.block_phrases:
            if re.search(re.escape(phrase), text, re.IGNORECASE):
                return (
                    "Nicht gespeichert — der Inhalt enthaelt eine im Workspace "
                    "blockierte Phrase. Der Workspace-Besitzer pflegt die Liste "
                    "in den Einstellungen."
                )
    for match in _INJECTION_PATTERN.finditer(text):
        if config.mode == MemoryGuardMode.custom and _covered_by_allow_phrase(
            text, match.span(), config.allow_phrases
        ):
            continue
        return (
            "Nicht gespeichert — der Inhalt enthaelt instruktionsartige "
            "Manipulationsmuster. Memories sind Fakten ueber den Nutzer, "
            "keine Anweisungen an ein KI-System."
        )
    return None


def _memory_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory nicht gefunden.")


def _agent_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent nicht gefunden.")


class MemoryService:
    """Waechter + Modus-Logik ueber dem Memory-Repository."""

    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------ Agent

    async def save(self, ctx: WorkspaceContext, data: MemoryCreate) -> MemoryRead:
        require_memory_mode(ctx, MemoryMode.suggest)
        require_write_rate(ctx)
        assert ctx.agent_id is not None and ctx.tool_policy is not None  # via Gate garantiert

        if data.importance < MEMORY_MIN_IMPORTANCE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Nicht gespeichert — importance {data.importance} liegt unter der "
                    f"Schwelle {MEMORY_MIN_IMPORTANCE}. Nur dauerhaft relevante Fakten "
                    "vorschlagen (waere er in 3 Monaten noch nuetzlich?)."
                ),
            )
        # Injection-Verdikt gemaess Workspace-Konfiguration (ADR-0044-Addendum):
        # standard = Built-in, custom = Built-in mit Allow-Suppression +
        # Block-Phrasen, off = kein Injection-Filter (Owner-Entscheidung,
        # gilt auch fuer auto-Agenten). Alle anderen Waechter (Importance,
        # Dedup, Cap, Rate-Limit) laufen unabhaengig davon IMMER.
        guard = await self._repo.get_guard_config(ctx.workspace_id)
        for text in (data.fact, data.context or ""):
            if not text:
                continue
            rejection = _guard_rejection(guard, text)
            if rejection is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=rejection,
                )
        duplicate = await self._repo.find_similar(ctx.workspace_id, ctx.agent_id, data.fact)
        if duplicate is not None:
            dup_id, dup_fact = duplicate
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Nicht gespeichert — zu aehnlich zu vorhandenem Memory "
                    f"[{str(dup_id)[:8]}]: „{dup_fact}“. Duplikate (auch bereits "
                    "abgelehnte Vorschlaege) werden nicht erneut aufgenommen."
                ),
            )
        # Cap zaehlt bewusst ALLE Status inkl. rejected (Security-Review N-3):
        # harte Obergrenze pro Agent statt unbegrenzt wachsender rejected-Menge.
        # Ein Agent kann so sein eigenes Gedaechtnis fuellen (Selbst-DoS) — das
        # ist in der Triage-UI sichtbar und vom Menschen aufraeumbar.
        count = await self._repo.count_for_agent(ctx.workspace_id, ctx.agent_id)
        if count >= MEMORY_MAX_PER_AGENT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Nicht gespeichert — das Gedaechtnis dieses Agenten ist voll "
                    f"({MEMORY_MAX_PER_AGENT} Eintraege). Der Workspace-Besitzer muss "
                    "zuerst aufraeumen (Agent-Detailseite → Gedaechtnis)."
                ),
            )
        new_status = (
            MemoryStatus.active
            if ctx.tool_policy.memory_mode == MemoryMode.auto
            else MemoryStatus.pending
        )
        return await self._repo.insert(
            ctx.workspace_id,
            ctx.agent_id,
            new_status,
            data.fact,
            data.context,
            data.category.value,
            data.importance,
        )

    async def search(self, ctx: WorkspaceContext, query: str, k: int) -> list[MemoryHit]:
        require_memory_mode(ctx, MemoryMode.read_only)
        assert ctx.agent_id is not None
        if not query.strip():
            return []
        k = max(1, min(k, _SEARCH_K_MAX))
        return await self._repo.search_active(ctx.workspace_id, ctx.agent_id, query, k)

    async def list_active(self, ctx: WorkspaceContext, limit: int) -> list[MemoryHit]:
        require_memory_mode(ctx, MemoryMode.read_only)
        assert ctx.agent_id is not None
        limit = max(1, min(limit, _LIST_LIMIT_MAX))
        return await self._repo.list_active(ctx.workspace_id, ctx.agent_id, limit)

    # ------------------------------------------------------------- Management

    def _require_human(self, ctx: WorkspaceContext) -> None:
        # Kurations-Endpunkte sind human-only: ein agent-gebundener Token darf
        # weder eigene Vorschlaege freigeben (Schleusen-Umgehung) noch fremde
        # Memories lesen/aendern — unabhaengig von Rolle oder Capabilities.
        # Beide Indikatoren pruefen (Security-Review N-2, Defense-in-Depth):
        # heute impliziert agent_id eine Policy (NOT-NULL-Default), aber die
        # Schleuse soll nicht an dieser DB-Invariante haengen.
        if ctx.tool_policy is not None or ctx.agent_id is not None:
            raise ApiGateError(
                status=status.HTTP_403_FORBIDDEN,
                reason="missing_capability",
                actionable_by="human",
                detail=(
                    "Die Memory-Verwaltung (Triage/Bearbeiten/Loeschen) ist Menschen "
                    "vorbehalten — agent-gebundene Tokens koennen Vorschlaege nur "
                    "ueber save_memory einreichen."
                ),
            )

    async def _require_agent(self, ctx: WorkspaceContext, agent_id: UUID) -> None:
        if not await self._repo.agent_belongs_to(ctx.workspace_id, agent_id):
            raise _agent_not_found()

    def _require_guard_admin(self, ctx: WorkspaceContext) -> None:
        # Waechter-Konfiguration ist eine Sicherheits-Einstellung: admin-Rolle
        # UND echter Mensch (JWT-Login). JEDER API-Token ist gesperrt — auch
        # ungebundene Admin-Tokens (Security-Review LOW-1: require_aal2
        # exemptet Maschinen-Tokens, damit wuerde der MFA-Anker entfallen).
        # Ein Agent darf den Filter, der IHN prueft, ohnehin nie anfassen.
        require_role(ctx, WorkspaceRole.admin)
        if ctx.is_api_token:
            raise ApiGateError(
                status=status.HTTP_403_FORBIDDEN,
                reason="missing_capability",
                actionable_by="human",
                detail=(
                    "Die Waechter-Konfiguration ist dem eingeloggten Menschen "
                    "vorbehalten (Web-UI) — API-Tokens sind hier gesperrt."
                ),
            )

    async def get_guard(self, ctx: WorkspaceContext) -> MemoryGuardConfig:
        self._require_guard_admin(ctx)
        return await self._repo.get_guard_config(ctx.workspace_id)

    async def set_guard(
        self, ctx: WorkspaceContext, config: MemoryGuardConfig
    ) -> MemoryGuardConfig:
        self._require_guard_admin(ctx)
        return await self._repo.set_guard_config(ctx.workspace_id, config)

    async def list_memories(
        self, ctx: WorkspaceContext, agent_id: UUID, status_filter: MemoryStatus | None
    ) -> list[MemoryRead]:
        require_role(ctx, WorkspaceRole.editor)
        self._require_human(ctx)
        await self._require_agent(ctx, agent_id)
        return await self._repo.list_for_agent(ctx.workspace_id, agent_id, status_filter)

    async def triage(
        self, ctx: WorkspaceContext, agent_id: UUID, memory_id: UUID, data: MemoryTriage
    ) -> MemoryRead:
        require_role(ctx, WorkspaceRole.editor)
        self._require_human(ctx)
        await self._require_agent(ctx, agent_id)
        existing = await self._repo.get(ctx.workspace_id, agent_id, memory_id)
        if existing is None:
            raise _memory_not_found()
        if existing.status != MemoryStatus.pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nur offene Vorschlaege (pending) koennen triagiert werden.",
            )
        new_status = (
            MemoryStatus.active
            if data.action == MemoryTriageAction.approve
            else MemoryStatus.rejected
        )
        # Fakt-Edition nur bei Freigabe sinnvoll (abgelehnter Text bleibt als
        # Dedup-Basis unveraendert erhalten).
        fact = data.fact if data.action == MemoryTriageAction.approve else None
        updated = await self._repo.triage(
            ctx.workspace_id, agent_id, memory_id, new_status, fact, data.note
        )
        if updated is None:  # Race: parallel triagiert
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nur offene Vorschlaege (pending) koennen triagiert werden.",
            )
        return updated

    async def update_memory(
        self, ctx: WorkspaceContext, agent_id: UUID, memory_id: UUID, data: MemoryUpdate
    ) -> MemoryRead:
        require_role(ctx, WorkspaceRole.editor)
        self._require_human(ctx)
        await self._require_agent(ctx, agent_id)
        updated = await self._repo.update(
            ctx.workspace_id,
            agent_id,
            memory_id,
            data.fact,
            data.category.value if data.category is not None else None,
            data.importance,
        )
        if updated is None:
            raise _memory_not_found()
        return updated

    async def delete_memory(self, ctx: WorkspaceContext, agent_id: UUID, memory_id: UUID) -> None:
        require_role(ctx, WorkspaceRole.editor)
        self._require_human(ctx)
        await self._require_agent(ctx, agent_id)
        if not await self._repo.delete(ctx.workspace_id, agent_id, memory_id):
            raise _memory_not_found()

    async def delete_all(self, ctx: WorkspaceContext, agent_id: UUID) -> None:
        require_role(ctx, WorkspaceRole.editor)
        self._require_human(ctx)
        await self._require_agent(ctx, agent_id)
        await self._repo.delete_all(ctx.workspace_id, agent_id)
