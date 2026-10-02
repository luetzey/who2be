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

import logging
import re
from dataclasses import dataclass
from uuid import UUID

from fastapi import status
from pydantic import JsonValue

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_memory_mode,
    require_role,
    require_write_rate,
    role_satisfies,
)
from who2be_api.embeddings import build_embedding_port
from who2be_api.repositories.memory_repository import (
    MemoryOwner,
    MemoryRepository,
    MemoryRevokeSelection,
)
from who2be_models import (
    MEMORY_MAX_PER_AGENT,
    MEMORY_MAX_PER_USER,
    MEMORY_MIN_IMPORTANCE,
    MemoryCategory,
    MemoryCreate,
    MemoryGuardConfig,
    MemoryGuardMode,
    MemoryHit,
    MemoryKind,
    MemoryMode,
    MemoryOrigin,
    MemoryRead,
    MemoryScope,
    MemorySource,
    MemoryStatus,
    MemoryTriage,
    MemoryTriageAction,
    MemoryUpdate,
    WorkspaceRole,
)
from who2be_models.memory import (
    MEMORY_AUTO_SWITCHABLE_CELLS,
    MEMORY_MAX_NOTES_PER_AGENT,
    MEMORY_REVOKE_SAMPLE_SIZE,
    MemoryAutoCell,
    MemoryAutoPolicy,
    MemoryAutoPolicyRead,
    MemoryAutoRow,
    MemoryBatchItemResult,
    MemoryEventKind,
    MemoryEventRead,
    MemoryProposalCreate,
    MemoryProposalDecision,
    MemoryProposalRead,
    MemoryProposalStatus,
    MemoryRevokeAuto,
    MemoryRevokeAutoPreview,
    MemoryRevokeAutoResult,
    MemoryRollback,
    MemorySaveResult,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------ Freigabematrix


@dataclass(frozen=True)
class MemoryDecision:
    """Ergebnis der Freigabematrix fuer einen neuen Eintrag (ADR-0053 4)."""

    status: MemoryStatus
    # Aktiv per Matrix: unbestaetigt, mit Verfallszeitpunkt (3.1.3).
    auto_activated: bool = False
    # Aktiv und bestaetigt: der Mensch ist die Quelle (Kanal human/import).
    confirmed: bool = False


def matrix_row(kind: MemoryKind, category: MemoryCategory) -> MemoryAutoRow:
    """Zeile der Matrix 4.2 fuer einen neuen Eintrag.

    `instruction` traegt per Definition Verhaltenswirkung und bildet deshalb
    eine eigene Zeile; nur die uebrigen Kategorien sind `user_fact`.
    """
    if kind == MemoryKind.lesson:
        return MemoryAutoRow.lesson
    if kind == MemoryKind.agent_note:
        return MemoryAutoRow.agent_note
    if category == MemoryCategory.instruction:
        return MemoryAutoRow.user_fact_instruction
    return MemoryAutoRow.user_fact


def decide_memory_status(
    *,
    mode: MemoryMode | None,
    source: MemorySource,
    row: MemoryAutoRow,
    origin: MemoryOrigin,
    policy: MemoryAutoPolicy,
) -> MemoryDecision:
    """Die Freigabematrix Art x Herkunft (ADR-0053 4.1/4.2) als reine Funktion.

    - Kanal `human`/`import`: aktiv und bestaetigt — ausser `lesson` (auch ein
      Mensch macht daraus einen Fall, keinen aktiven Eintrag) und Vorschlaegen.
    - Kanal `agent`: nur unter `memory_mode=auto` UND nur fuer eine Zelle, die
      der Admin eingeschaltet hat UND die schaltbar ist. Eine eingeschaltete
      Nie-Zelle ignoriert der Server (`MemoryAutoPolicy.effective`).
    - Alles andere: `pending` (Kurations-Schleuse).
    """
    if source in (MemorySource.human, MemorySource.import_):
        if row in (MemoryAutoRow.lesson, MemoryAutoRow.proposal):
            return MemoryDecision(MemoryStatus.pending)
        return MemoryDecision(MemoryStatus.active, confirmed=True)
    if mode != MemoryMode.auto:
        return MemoryDecision(MemoryStatus.pending)
    if MemoryAutoCell(row=row, origin=origin) in policy.effective():
        return MemoryDecision(MemoryStatus.active, auto_activated=True)
    return MemoryDecision(MemoryStatus.pending)


def _sorted_cells(cells: frozenset[MemoryAutoCell]) -> list[MemoryAutoCell]:
    return sorted(cells, key=lambda cell: (cell.row.value, cell.origin.value))


def _auto_policy_read(policy: MemoryAutoPolicy) -> MemoryAutoPolicyRead:
    return MemoryAutoPolicyRead(
        enabled_cells=_sorted_cells(policy.effective()),
        switchable_cells=_sorted_cells(MEMORY_AUTO_SWITCHABLE_CELLS),
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


# Secret-Scan (ADR-0053 7.1 #2, Paket C2b): Zugangsdaten und Geheimnisse
# gehoeren nie ins Gedaechtnis — weder als Nutzerfakt noch als Arbeitsnotiz
# (3.1.5). Der Scan ist ein Vorfilter mit bekannten Formen, kein Beweis fuer
# Geheimnisfreiheit (nicht tragend, 7.1 #2): er faengt das Versehen, nicht den
# gezielten Umweg. Er laeuft UNABHAENGIG von der Waechter-Konfiguration —
# `off` und Allow-Phrasen schalten nur den Injection-Filter ab, nicht diesen.
#
# Bewusst eng: jedes Muster verlangt eine Form, die in einem Fakt ueber einen
# Menschen nicht vorkommt (Schluesselblock, Zuweisung eines Wertes an ein
# Geheimnis-Feld, Zugangsdaten in einer URL, bekannte Token-Praefixe). Das
# Wort „Passwort“ allein blockt nicht — „Nutzer nutzt einen Passwortmanager“
# ist ein legitimer Fakt.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Schluesselblock (PEM/OpenSSH).
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY( BLOCK)?-----"),
    # Geheimnis-Feld mit zugewiesenem Wert: `passwort: …`, `api_key=…`.
    re.compile(
        r"(?i)\b(pass(wor[dt])?|pwd|kennwort|secret|geheimnis|api[ _-]?key|"
        r"access[ _-]?key|secret[ _-]?key|private[ _-]?key|client[ _-]?secret|"
        r"auth[ _-]?token|access[ _-]?token|bearer[ _-]?token|token)\s*[:=]\s*"
        r"[\"']?[^\s\"']{6,}"
    ),
    # Dasselbe in Prosa: „das Passwort des Nutzers lautet X“. Der Wert muss
    # wie ein Zugangswert aussehen (mindestens 8 Zeichen, Ziffer UND
    # Buchstabe), damit „das Passwort ist sicher“ ein Fakt bleibt.
    re.compile(
        r"(?i)\b(passwor[dt]|kennwort|passphrase|pin|api[ _-]?key|secret|token|"
        r"zugangsdaten|credentials?)\b[^\n]{0,40}?"
        r"(?:\s(?:lautet|lauten|ist|sind|is|are)\b\s*:?|[:=])\s*[\"']?"
        r"(?=[^\s\"']*\d)(?=[^\s\"']*[A-Za-z])[^\s\"']{8,}"
    ),
    # Authorization-Header mit Wert.
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{20,}"),
    # Zugangsdaten in einer URL: `schema://nutzer:wert@host`.
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s/@]+@[^\s/]+"),
    # JSON Web Token (drei base64url-Teile; `eyJ` ist ein base64-kodiertes `{"`).
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    # Bekannte Token-Praefixe: eigener API-Token und verbreitete Anbieter.
    re.compile(
        r"\b(w2b_[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"glpat-[A-Za-z0-9_-]{20,}|xox[abposr]-[A-Za-z0-9-]{10,}|"
        r"sk-[A-Za-z0-9_-]{20,}|(AKIA|ASIA)[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,})"
    ),
)

_SECRET_REJECTION = (
    "Nicht gespeichert — der Inhalt sieht nach Zugangsdaten oder einem Geheimnis "
    "aus. Passwoerter, Schluessel und Tokens gehoeren nicht ins Gedaechtnis."
)


def _secret_rejection(text: str) -> str | None:
    """Secret-Verdikt fuer `text` (ADR-0053 7.1 #2) oder None.

    Reflektiert den Treffer bewusst NICHT ins Fehlerdetail: das Geheimnis
    soll nicht ueber die Fehlerantwort zurueck in den Agent-Kontext oder in
    ein Log laufen.
    """
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return _SECRET_REJECTION
    return None


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


def _memory_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Memory nicht gefunden.",
        reason="memory_not_found",
    )


def _agent_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Agent nicht gefunden.",
        reason="agent_not_found",
    )


def _proposal_not_found() -> ApiError:
    # Kein eigener Grund (ADR-0053 6.1 kennt nur `memory_not_found`): auch ein
    # Vorschlag, den der Aufrufer nicht sehen darf, ist „nicht gefunden“.
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Vorschlag nicht gefunden.",
        reason="memory_not_found",
    )


def _proposal_not_pending() -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail="Der Vorschlag ist bereits entschieden.",
        reason="memory_proposal_not_pending",
    )


def _transition_invalid(memory: MemoryRead, *, event: MemoryEventKind | None = None) -> ApiError:
    params: dict[str, JsonValue] = {"status": memory.status.value}
    if event is not None:
        params["event"] = event.value
        detail = (
            f"Das Ereignis `{event.value}` hat keinen Vorzustand, "
            "auf den zurueckgesetzt werden kann."
        )
    else:
        detail = (
            "Dieser Statuswechsel ist fuer ein Memory im Status "
            f"`{memory.status.value}` nicht moeglich."
        )
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
        reason="memory_transition_invalid",
        params=params,
    )


class MemoryService:
    """Waechter + Modus-Logik ueber dem Memory-Repository."""

    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    async def _embed(self, text: str) -> list[float] | None:
        """Vektor eines Textes — BEST EFFORT (ADR-0046 Welle 3).

        `save_memory` ist ein rate-limitierter LAUFZEIT-Call des Agenten, kein
        Builder-Vorgang: ein langsames oder kaputtes Modell darf ihn nie
        scheitern lassen. Ohne Vektor greift weiterhin der Trigram-Dedup, und
        der Backfill holt den Vektor nach.

        Gilt genauso fuer die Anfrage-Seite: schlaegt das Einbetten der Query
        fehl, sucht `search_active` eben nur lexikalisch. Eine schlechtere
        Antwort ist besser als keine.
        """
        embedder = build_embedding_port()
        if embedder is None or not text.strip():
            return None
        try:
            vectors = await embedder.embed([text])
        except Exception:  # noqa: BLE001 - Degradation ist Absicht
            logger.warning("Memory-Embedding fehlgeschlagen — es wird lexikalisch gearbeitet.")
            return None
        return list(vectors[0]) if vectors else None

    # ------------------------------------------------------------------ Agent

    async def save(self, ctx: WorkspaceContext, data: MemoryCreate) -> MemorySaveResult:
        """Speicherpfad des Agenten (ADR-0044, ADR-0053 3.1.1/3.1.5/3.1.6/4).

        Reihenfolge: Gates → Pflicht-Herkunft und Art x Scope → Importance →
        Injection-Waechter → Dublette (bei `lesson`: Merge statt 409) →
        Obergrenze → Freigabematrix → Insert. Den Kanal (`source`) setzt der
        Server: dieser Pfad ist nur fuer agent-gebundene Tokens offen, also
        immer `agent` (Weiche M8).
        """
        require_memory_mode(ctx, MemoryMode.suggest)
        require_write_rate(ctx)
        assert ctx.agent_id is not None and ctx.tool_policy is not None  # via Gate garantiert

        # `legacy_unknown` markiert nur den Bestand vor C2a; als Deklaration
        # waere er ein Weg, die Pflicht-Herkunft zu umgehen.
        if data.origin is None or data.origin == MemoryOrigin.legacy_unknown:
            raise ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Nicht gespeichert — die Herkunft fehlt. `origin` ist Pflicht: "
                    "user_stated (vom Nutzer gesagt), inferred (selbst geschlossen) "
                    "oder external_content (aus Werkzeug, Web oder Dokument)."
                ),
                reason="memory_origin_required",
            )
        origin = data.origin
        # DB-CHECK 0091: `scope='user'` nur mit `kind='user_fact'` (3.1). Hier
        # vorab als stabiler Grund statt als 500 aus der CheckViolation.
        if data.scope == MemoryScope.user and data.kind != MemoryKind.user_fact:
            raise ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Nicht gespeichert — `kind={data.kind.value}` ist im "
                    "Nutzergedaechtnis (`scope=user`) nicht erlaubt; dort gibt es nur "
                    "Fakten ueber den Nutzer (`user_fact`)."
                ),
                reason="memory_kind_scope_invalid",
                params={"kind": data.kind.value, "scope": data.scope.value},
            )

        if data.importance < MEMORY_MIN_IMPORTANCE:
            raise ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Nicht gespeichert — importance {data.importance} liegt unter der "
                    f"Schwelle {MEMORY_MIN_IMPORTANCE}. Nur dauerhaft relevante Fakten "
                    "vorschlagen (waere er in 3 Monaten noch nuetzlich?)."
                ),
                reason="memory_importance_too_low",
                params={"importance": data.importance, "minimum": MEMORY_MIN_IMPORTANCE},
            )
        # Secret-Scan (7.1 #2) vor dem Injection-Waechter und unabhaengig von
        # dessen Konfiguration: auch `off` laesst kein Geheimnis durch. Gleicher
        # Grund `memory_guard_rejected` — fuer den Agenten ist beides „dieser
        # Inhalt gehoert nicht ins Gedaechtnis“.
        for text in (data.fact, data.context or ""):
            secret = _secret_rejection(text) if text else None
            if secret is not None:
                raise ApiError(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=secret,
                    reason="memory_guard_rejected",
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
                raise ApiError(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=rejection,
                    reason="memory_guard_rejected",
                )
        fact_vector = await self._embed(data.fact)
        is_user_scope = data.scope == MemoryScope.user
        if data.kind == MemoryKind.lesson:
            # Wiederholung eines Lernvorschlags ist Signal, kein Fehler (3.1.6):
            # gegen ALLE lesson-Eintraege desselben Agenten inkl. rejected und
            # converted. Der Treffer behaelt seinen Status; keine neue Zeile.
            lesson_hit = await self._repo.find_similar(
                ctx.workspace_id, ctx.agent_id, data.fact, fact_vector, lessons=True
            )
            if lesson_hit is not None:
                merged = await self._repo.merge_lesson(
                    ctx.workspace_id, ctx.agent_id, lesson_hit[0]
                )
                if merged is not None:
                    return MemorySaveResult(**merged.model_dump(), merged_into=merged.id)
        if is_user_scope:
            duplicate = await self._repo.find_similar_user(
                ctx.workspace_id, ctx.user_id, data.fact, fact_vector
            )
        elif data.kind == MemoryKind.lesson:
            duplicate = None  # oben geprueft
        else:
            duplicate = await self._repo.find_similar(
                ctx.workspace_id, ctx.agent_id, data.fact, fact_vector
            )
        if duplicate is not None:
            dup_id, dup_fact = duplicate
            duplicate_id = str(dup_id)[:8]
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Nicht gespeichert — zu aehnlich zu vorhandenem Memory "
                    f"[{duplicate_id}]: „{dup_fact}“. Duplikate (auch bereits "
                    "abgelehnte Vorschlaege) werden nicht erneut aufgenommen."
                ),
                reason="memory_duplicate",
                params={"duplicate_id": duplicate_id, "duplicate_fact": dup_fact},
            )
        await self._enforce_caps(ctx, ctx.agent_id, data.kind, is_user_scope)

        decision = decide_memory_status(
            mode=ctx.tool_policy.memory_mode,
            source=MemorySource.agent,
            row=matrix_row(data.kind, data.category),
            origin=origin,
            policy=await self._repo.get_auto_policy(ctx.workspace_id),
        )
        created = await self._repo.insert(
            ctx.workspace_id,
            None if is_user_scope else ctx.agent_id,
            decision.status,
            data.fact,
            data.context,
            data.category.value,
            data.importance,
            kind=data.kind,
            scope=data.scope,
            origin=origin,
            source=MemorySource.agent,
            subject_user_id=ctx.user_id if is_user_scope else None,
            created_by_agent_id=ctx.agent_id,
            auto_activated=decision.auto_activated,
        )
        # Vektor nachziehen. Bewusst NACH dem Insert und ohne Fehlerpfad: das
        # Memory ist bereits gespeichert, der Vektor nur eine Beschleunigung
        # des spaeteren Suchens.
        if fact_vector is not None:
            await self._repo.set_vector(created.id, fact_vector)
        return MemorySaveResult(**created.model_dump(), auto_activated=decision.auto_activated)

    async def _enforce_caps(
        self, ctx: WorkspaceContext, agent_id: UUID, kind: MemoryKind, is_user_scope: bool
    ) -> None:
        """Obergrenzen je Geltungsbereich und Art, gezaehlt ueber ALLE Status.

        Alle Status inkl. rejected (Security-Review N-3): harte Obergrenze statt
        unbegrenzt wachsender rejected-Menge. Ein Agent kann so sein eigenes
        Gedaechtnis fuellen (Selbst-DoS) — das ist in der Triage-UI sichtbar
        und vom Menschen aufraeumbar.

        - Nutzergedaechtnis: `MEMORY_MAX_PER_USER` je (workspace_id,
          subject_user_id), `memory_cap_reached` mit `scope='user'` (3.1.1).
        - Arbeitsnotizen: `MEMORY_MAX_NOTES_PER_AGENT` je Agent, getrennt von
          der Agentengrenze, `memory_note_cap_reached` (3.1.5).
        - Sonst: `MEMORY_MAX_PER_AGENT` (ohne Arbeitsnotizen).
        """
        if is_user_scope:
            if await self._repo.count_for_user(ctx.workspace_id, ctx.user_id) >= (
                MEMORY_MAX_PER_USER
            ):
                raise ApiError(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Nicht gespeichert — dein Nutzergedaechtnis in diesem Workspace "
                        f"ist voll ({MEMORY_MAX_PER_USER} Eintraege). Zuerst aufraeumen."
                    ),
                    reason="memory_cap_reached",
                    params={"maximum": MEMORY_MAX_PER_USER, "scope": MemoryScope.user.value},
                )
            return
        if kind == MemoryKind.agent_note:
            if await self._repo.count_notes_for_agent(ctx.workspace_id, agent_id) >= (
                MEMORY_MAX_NOTES_PER_AGENT
            ):
                raise ApiError(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Nicht gespeichert — die Arbeitsnotizen dieses Agenten sind voll "
                        f"({MEMORY_MAX_NOTES_PER_AGENT} Eintraege). Der Workspace-Besitzer "
                        "muss zuerst aufraeumen (Agent-Detailseite → Gedaechtnis)."
                    ),
                    reason="memory_note_cap_reached",
                    params={"maximum": MEMORY_MAX_NOTES_PER_AGENT},
                )
            return
        if await self._repo.count_for_agent(ctx.workspace_id, agent_id) >= MEMORY_MAX_PER_AGENT:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Nicht gespeichert — das Gedaechtnis dieses Agenten ist voll "
                    f"({MEMORY_MAX_PER_AGENT} Eintraege). Der Workspace-Besitzer muss "
                    "zuerst aufraeumen (Agent-Detailseite → Gedaechtnis)."
                ),
                reason="memory_cap_reached",
                params={"maximum": MEMORY_MAX_PER_AGENT},
            )

    async def search(self, ctx: WorkspaceContext, query: str, k: int) -> list[MemoryHit]:
        require_memory_mode(ctx, MemoryMode.read_only)
        assert ctx.agent_id is not None
        if not query.strip():
            return []
        k = max(1, min(k, _SEARCH_K_MAX))
        query_vector = await self._embed(query)
        return await self._repo.search_active(
            ctx.workspace_id, ctx.agent_id, query, k, query_vector
        )

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

    # ---------------------------------------------------------- Freigabematrix

    async def get_auto_policy(self, ctx: WorkspaceContext) -> MemoryAutoPolicyRead:
        # Gleiches Gate wie der Injection-Waechter (ADR-0053 4.1): admin UND
        # eingeloggter Mensch. Die Matrix steuert, was ein Agent ohne
        # menschliche Freigabe aktiv setzen darf — ein Token darf sie weder
        # lesen noch schreiben.
        self._require_guard_admin(ctx)
        return _auto_policy_read(await self._repo.get_auto_policy(ctx.workspace_id))

    async def set_auto_policy(
        self, ctx: WorkspaceContext, policy: MemoryAutoPolicy
    ) -> MemoryAutoPolicyRead:
        self._require_guard_admin(ctx)
        # Nie-Zellen werden ignoriert, nicht abgelehnt (ADR-0053 4.2): gespeichert
        # wird nur, was wirkt. So kann auch ein Altbestand mit Nie-Zellen nie
        # still mitwirken, falls die Schaltbarkeit spaeter enger wird.
        effective = MemoryAutoPolicy(enabled_cells=_sorted_cells(policy.effective()))
        stored = await self._repo.set_auto_policy(ctx.workspace_id, effective, ctx.user_id)
        return _auto_policy_read(stored)

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
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nur offene Vorschlaege (pending) koennen triagiert werden.",
                reason="memory_not_pending",
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
            ctx.workspace_id, agent_id, memory_id, new_status, fact, data.note, ctx.user_id
        )
        if updated is None:  # Race: parallel triagiert
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nur offene Vorschlaege (pending) koennen triagiert werden.",
                reason="memory_not_pending",
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
            ctx.user_id,
        )
        if updated is None:
            raise _memory_not_found()
        return updated

    async def delete_memory(self, ctx: WorkspaceContext, agent_id: UUID, memory_id: UUID) -> None:
        require_role(ctx, WorkspaceRole.editor)
        self._require_human(ctx)
        await self._require_agent(ctx, agent_id)
        if not await self._repo.delete(ctx.workspace_id, agent_id, memory_id, ctx.user_id):
            raise _memory_not_found()

    async def delete_all(self, ctx: WorkspaceContext, agent_id: UUID) -> None:
        require_role(ctx, WorkspaceRole.editor)
        self._require_human(ctx)
        await self._require_agent(ctx, agent_id)
        await self._repo.delete_all(ctx.workspace_id, agent_id, ctx.user_id)

    # ------------------------------------------- Vorschlaege von Agenten (3.1.4)

    async def propose(
        self, ctx: WorkspaceContext, data: MemoryProposalCreate
    ) -> MemoryProposalRead:
        """Aenderungs- oder Loeschvorschlag eines Agenten (MCP `propose_memory_change`, C4).

        Gates wie `save_memory` (Modus `suggest`, Schreib-Rate). Ein Agent darf
        nur vorschlagen, was er abrufen darf (3.1.4): sein eigenes
        Agentengedaechtnis oder das Nutzergedaechtnis des Token-Besitzers,
        jeweils nur `active` und nie `lesson` (der Abruf liefert nichts
        anderes, 6.2). Alles andere ist fuer ihn `memory_not_found` — auch ein
        existierender fremder Eintrag, damit die Antwort nichts verraet.

        `new_fact` und `reason` durchlaufen Secret-Scan und Injection-Waechter
        wie `save_memory`. Der Vorschlag entsteht IMMER `pending`; einen Pfad
        zur automatischen Annahme gibt es nicht — auch nicht unter
        `memory_mode=auto` mit eingeschalteter Matrix-Zelle (4.2).
        """
        require_memory_mode(ctx, MemoryMode.suggest)
        require_write_rate(ctx)
        assert ctx.agent_id is not None  # via Gate garantiert
        memory = await self._repo.get_owned(
            ctx.workspace_id, MemoryOwner(agent_id=ctx.agent_id), data.memory_id
        )
        if memory is None:
            memory = await self._repo.get_owned(
                ctx.workspace_id, MemoryOwner(subject_user_id=ctx.user_id), data.memory_id
            )
        if (
            memory is None
            or memory.status != MemoryStatus.active
            or memory.kind == MemoryKind.lesson
        ):
            raise _memory_not_found()
        guard = await self._repo.get_guard_config(ctx.workspace_id)
        for text in (data.new_fact or "", data.reason):
            if not text:
                continue
            rejection = _secret_rejection(text) or _guard_rejection(guard, text)
            if rejection is not None:
                raise ApiError(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=rejection,
                    reason="memory_guard_rejected",
                )
        return await self._repo.insert_proposal(ctx.workspace_id, ctx.agent_id, memory, data)

    async def list_proposals(
        self,
        ctx: WorkspaceContext,
        *,
        agent_id: UUID | None = None,
        status_filter: MemoryProposalStatus | None = None,
    ) -> list[MemoryProposalRead]:
        """Vorschlaege fuer einen Menschen (6.4.1 `GET /memory-proposals`).

        Ab `viewer` sichtbar: Vorschlaege zum eigenen Nutzergedaechtnis. Ab
        `editor` dazu alle zum Agentengedaechtnis. Vorschlaege zum
        Nutzergedaechtnis anderer Personen sieht niemand (3.1.1, auch admin
        nicht). `agent_id` ist ein optionaler Filter auf den Absender.
        """
        require_role(ctx, WorkspaceRole.viewer)
        self._require_human(ctx)
        if agent_id is not None:
            await self._require_agent(ctx, agent_id)
        return await self._repo.list_proposals(
            ctx.workspace_id,
            viewer_user_id=ctx.user_id,
            include_agent_scope=role_satisfies(ctx.role, WorkspaceRole.editor),
            agent_id=agent_id,
            status=status_filter,
        )

    async def decide_proposal(
        self, ctx: WorkspaceContext, proposal_id: UUID, data: MemoryProposalDecision
    ) -> MemoryProposalRead:
        """Annahme oder Ablehnung durch einen Menschen (3.1.4).

        Rechte folgen dem Ziel-Eintrag: Agentengedaechtnis ab `editor`,
        Nutzergedaechtnis nur die Person selbst (jede Rolle ab `viewer`).
        Wer den Vorschlag nicht entscheiden darf, bekommt `memory_not_found` —
        nicht 403, damit ein fremdes Nutzergedaechtnis nicht ueber
        Vorschlags-IDs abtastbar ist.
        """
        require_role(ctx, WorkspaceRole.viewer)
        self._require_human(ctx)
        found = await self._repo.get_proposal(ctx.workspace_id, proposal_id)
        if found is None:
            raise _proposal_not_found()
        proposal, owner = found
        if owner.subject_user_id is not None:
            if owner.subject_user_id != ctx.user_id:
                raise _proposal_not_found()
        elif not role_satisfies(ctx.role, WorkspaceRole.editor):
            raise _proposal_not_found()
        if proposal.status != MemoryProposalStatus.pending:
            raise _proposal_not_pending()
        decided = await self._repo.decide_proposal(
            ctx.workspace_id,
            owner,
            proposal_id,
            accept=data.accept,
            actor_id=ctx.user_id,
            note=data.note,
        )
        if decided is None:  # Race: parallel entschieden
            raise _proposal_not_pending()
        return decided

    # ------------------- Historie, Rollback, Bestaetigen, Reaktivieren (3.1.2, 6.4)
    #
    # `agent_id=None` heisst: das EIGENE Nutzergedaechtnis (`/me/memories`, C3b);
    # sonst das Agentengedaechtnis dieses Agenten (`/agents/{id}/memories`).

    async def _owner(self, ctx: WorkspaceContext, agent_id: UUID | None) -> MemoryOwner:
        """Besitzer samt Rechtepruefung (3.1.1).

        Agentengedaechtnis: `editor`, Mensch, Agent im Workspace.
        Nutzergedaechtnis: jede Rolle ab `viewer`, Mensch, und nur das eigene —
        der Besitzer ist IMMER `ctx.user_id`, es gibt keinen Parameter, ueber
        den jemand (auch admin) ein fremdes Nutzergedaechtnis adressiert.
        """
        if agent_id is None:
            require_role(ctx, WorkspaceRole.viewer)
            self._require_human(ctx)
            return MemoryOwner(subject_user_id=ctx.user_id)
        require_role(ctx, WorkspaceRole.editor)
        self._require_human(ctx)
        await self._require_agent(ctx, agent_id)
        return MemoryOwner(agent_id=agent_id)

    async def _owned(
        self, ctx: WorkspaceContext, agent_id: UUID | None, memory_id: UUID
    ) -> tuple[MemoryOwner, MemoryRead]:
        owner = await self._owner(ctx, agent_id)
        memory = await self._repo.get_owned(ctx.workspace_id, owner, memory_id)
        if memory is None:
            raise _memory_not_found()
        return owner, memory

    async def list_my_memories(
        self, ctx: WorkspaceContext, status_filter: MemoryStatus | None
    ) -> list[MemoryRead]:
        """Eigenes Nutzergedaechtnis (`GET /me/memories`)."""
        await self._owner(ctx, None)
        return await self._repo.list_for_user(ctx.workspace_id, ctx.user_id, status_filter)

    async def history(
        self, ctx: WorkspaceContext, agent_id: UUID | None, memory_id: UUID
    ) -> list[MemoryEventRead]:
        """Historie eines Eintrags, aelteste zuerst (3.1.2)."""
        _, memory = await self._owned(ctx, agent_id, memory_id)
        return await self._repo.list_events(ctx.workspace_id, memory.id)

    async def confirm(
        self, ctx: WorkspaceContext, agent_id: UUID | None, memory_id: UUID
    ) -> MemoryRead:
        """Bestaetigt einen aktiven, unbestaetigten Eintrag; der Verfall endet (3.1.3)."""
        owner, memory = await self._owned(ctx, agent_id, memory_id)
        if memory.status != MemoryStatus.active or memory.confirmed_at is not None:
            raise _transition_invalid(memory)
        updated = await self._repo.confirm(ctx.workspace_id, owner, memory_id, ctx.user_id)
        if updated is None:  # Race
            raise _transition_invalid(memory)
        return updated

    async def reactivate(
        self, ctx: WorkspaceContext, agent_id: UUID | None, memory_id: UUID
    ) -> MemoryRead:
        """`expired` → `active`, zugleich bestaetigt (6.4)."""
        owner, memory = await self._owned(ctx, agent_id, memory_id)
        if memory.status != MemoryStatus.expired:
            raise _transition_invalid(memory)
        updated = await self._repo.reactivate(ctx.workspace_id, owner, memory_id, ctx.user_id)
        if updated is None:  # Race
            raise _transition_invalid(memory)
        return updated

    async def rollback(
        self, ctx: WorkspaceContext, agent_id: UUID | None, memory_id: UUID, data: MemoryRollback
    ) -> MemoryRead:
        """Stellt den Zustand aus `before` des gewaehlten Ereignisses her (3.1.2).

        Nur ein Mensch (Gate in `_owner`). Das Ereignis muss zu GENAU diesem
        Eintrag gehoeren — sonst `memory_not_found`. Ohne `before`
        (z. B. `created`) gibt es keinen Vorzustand: `memory_transition_invalid`.
        Geschrieben wird ein neues Ereignis `rolled_back`; die Historie bleibt
        append-only.
        """
        owner, memory = await self._owned(ctx, agent_id, memory_id)
        events = await self._repo.list_events(ctx.workspace_id, memory.id)
        target = next((e for e in events if e.id == data.event_id), None)
        if target is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ereignis gehoert nicht zu diesem Memory.",
                reason="memory_not_found",
            )
        if target.before is None:
            raise _transition_invalid(memory, event=target.event)
        restored = await self._repo.restore(
            ctx.workspace_id,
            owner,
            memory_id,
            target.before,
            ctx.user_id,
            reason=f"rollback_to:{target.id}",
        )
        if restored is None:  # Race: parallel geloescht
            raise _memory_not_found()
        return restored

    # ------------------------------ Eigenes Nutzergedaechtnis kuratieren (3.1.1)

    async def triage_my(
        self, ctx: WorkspaceContext, memory_id: UUID, data: MemoryTriage
    ) -> MemoryRead:
        """Triage im eigenen Nutzergedaechtnis — nur die Person selbst."""
        owner, memory = await self._owned(ctx, None, memory_id)
        if memory.status != MemoryStatus.pending:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nur offene Vorschlaege (pending) koennen triagiert werden.",
                reason="memory_not_pending",
            )
        approve = data.action == MemoryTriageAction.approve
        updated = await self._repo.triage_owned(
            ctx.workspace_id,
            owner,
            memory_id,
            MemoryStatus.active if approve else MemoryStatus.rejected,
            data.fact if approve else None,
            data.note,
            ctx.user_id,
        )
        if updated is None:  # Race
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nur offene Vorschlaege (pending) koennen triagiert werden.",
                reason="memory_not_pending",
            )
        return updated

    async def update_my(
        self, ctx: WorkspaceContext, memory_id: UUID, data: MemoryUpdate
    ) -> MemoryRead:
        """Bearbeiten im eigenen Nutzergedaechtnis."""
        owner = await self._owner(ctx, None)
        updated = await self._repo.update_owned(
            ctx.workspace_id,
            owner,
            memory_id,
            data.fact,
            data.category.value if data.category is not None else None,
            data.importance,
            ctx.user_id,
        )
        if updated is None:
            raise _memory_not_found()
        return updated

    async def delete_my(self, ctx: WorkspaceContext, memory_id: UUID) -> None:
        """Hard-Delete im eigenen Nutzergedaechtnis, inhaltsfreie Audit-Spur (M5)."""
        owner = await self._owner(ctx, None)
        if not await self._repo.delete_owned(ctx.workspace_id, owner, memory_id, ctx.user_id):
            raise _memory_not_found()

    # --------------------------------------------------- Not-Aus (6.4.1, C3b-2)

    async def revoke_auto(
        self, ctx: WorkspaceContext, data: MemoryRevokeAuto
    ) -> MemoryRevokeAutoPreview | MemoryRevokeAutoResult:
        """Notfall-Ruecknahme automatisch aktivierter Eintraege (ADR-0053 6.4.1).

        Rechte: `editor` und Mensch — Agentengedaechtnis und das eigene
        Nutzergedaechtnis. `include_other_users=true` ist `admin` vorbehalten
        (403 `insufficient_role`); auch dann sieht der Admin vom fremden
        Nutzergedaechtnis nur die Anzahl (`hidden_count`), nie Inhalt oder ID
        (Owner-Entscheidung 3a, 3.1.1).

        `dry_run` aendert nichts. Sonst wird alles oder nichts zurueckgenommen:
        weicht die Trefferzahl von `expected_count` ab, kommt 409
        `memory_batch_count_mismatch` mit `params={count}` und es bleibt alles,
        wie es war.
        """
        require_role(ctx, WorkspaceRole.editor)
        self._require_human(ctx)
        if data.include_other_users:
            require_role(ctx, WorkspaceRole.admin)
        if data.agent_id is not None:
            await self._require_agent(ctx, data.agent_id)
        selection = MemoryRevokeSelection(
            viewer_user_id=ctx.user_id,
            since=data.since,
            until=data.until,
            agent_id=data.agent_id,
            origins=tuple(data.origin) if data.origin is not None else None,
            include_other_users=data.include_other_users,
        )
        if data.dry_run:
            preview = await self._repo.preview_auto_revocable(
                ctx.workspace_id, selection, MEMORY_REVOKE_SAMPLE_SIZE
            )
            return MemoryRevokeAutoPreview(
                count=preview.count, hidden_count=preview.hidden_count, sample=preview.visible
            )
        assert data.expected_count is not None  # Modell-Validator
        outcome = await self._repo.revoke_auto(
            ctx.workspace_id,
            selection,
            expected_count=data.expected_count,
            actor_id=ctx.user_id,
        )
        if not outcome.applied:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Es gibt {outcome.count} betroffene Eintraege, bestaetigt waren "
                    f"{data.expected_count}. Nichts geaendert — bitte die Vorschau neu laden."
                ),
                reason="memory_batch_count_mismatch",
                params={"count": outcome.count},
            )
        return MemoryRevokeAutoResult(
            count=outcome.count,
            hidden_count=outcome.hidden_count,
            results=[MemoryBatchItemResult(id=m.id, ok=True) for m in outcome.visible],
        )
