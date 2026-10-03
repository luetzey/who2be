"""Datenzugriff fuer das Agent-Memory (ADR-0044).

Jede Query filtert auf `workspace_id` — per Signatur erzwungen
(Defense-in-Depth zusaetzlich zur RLS) — und zusaetzlich auf den Besitzer:
`agent_id` fuer das Agentengedaechtnis, `subject_user_id` fuer das
Nutzergedaechtnis (`count_for_user`), `memory_id` fuer die Historie. Es gibt
keinen Weg, ueber dieses Repository fremde Memories zu lesen oder zu
schreiben (Leak-Test-Kritikalitaet, Kap. 11.7 des Memory-Konzepts).

Gedaechtnis 2.0 (ADR-0053 3.1, Migration 0091): die heutigen Abrufpfade
(`search_active`, `list_active`) filtern auf `status='active'` UND
`scope='agent'`. Lernvorschlaege (`kind='lesson'`) koennen per DB-CHECK nie
`active` sein; das Nutzergedaechtnis (`scope='user'`) erreicht diese Pfade
erst, wenn C2a/C4 es ausdruecklich anbinden. Loeschen schreibt je Zeile eine
inhaltsfreie `audit_log`-Zeile `memory.deleted` (Weiche M5).

Retrieval (nur `status='active'`): drei Zweige — FTS ('simple'-tsvector,
ADR-0037-Muster), ILIKE und pg_trgm-Similarity — plus optional ein
Vektor-Zweig (ADR-0046 Welle 3). Die drei lexikalischen Zweige faengt auch
Namen/IDs/Abkuerzungen, die reine FTS verfehlt; der Vektor-Zweig faengt
Umschreibungen und sprachuebergreifende Treffer, die keiner von ihnen findet.

Die Raenge werden per Reciprocal Rank Fusion verschmolzen, NICHT mehr als
lexikografische `ORDER BY`-Kaskade sortiert. Der Grund ist nicht Eleganz: eine
Kaskade laesst den ersten Term dominieren, sodass ein perfekter Vektor-Treffer
hinter jedem beliebigen FTS-Treffer landet. RRF fusioniert Raenge und ist damit
skalenunabhaengig — `ts_rank`, Trigram-Similarity und Cosinus-Distanz sind
nicht vergleichbar normierbar.

Ausgelieferte Treffer erhoehen das Nutzungs-Log
(`retrieval_count`/`last_retrieved_at`) — in einem SEPARATEN Statement, nicht
in derselben Transaktion (der frueher hier stehende Satz war falsch).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import asyncpg

from who2be_models import (
    MemoryEventCreate,
    MemoryEventRead,
    MemoryGuardConfig,
    MemoryHit,
    MemoryRead,
    MemoryStatus,
)
from who2be_models.memory import (
    MEMORY_HEALTH_EXPIRING_DAYS,
    MEMORY_HEALTH_NEVER_DELIVERED_DAYS,
    MEMORY_HEALTH_STALE_DELIVERY_DAYS,
    MEMORY_UNCONFIRMED_TTL_DAYS,
    MemoryActorKind,
    MemoryAutoCell,
    MemoryAutoPolicy,
    MemoryCountGroup,
    MemoryEventKind,
    MemoryFilter,
    MemoryHealth,
    MemoryKind,
    MemoryListSort,
    MemoryOrigin,
    MemoryProposalAction,
    MemoryProposalCreate,
    MemoryProposalRead,
    MemoryProposalStatus,
    MemoryScope,
    MemorySource,
)

# Trigram-Schwelle fuer den Dedup-Waechter (similarity(fact, kandidat)).
MEMORY_DEDUP_SIMILARITY = 0.6
# Trigram-Schwelle, ab der ein Fakt als Fuzzy-Suchtreffer gilt.
_SEARCH_SIMILARITY = 0.3

# Reciprocal Rank Fusion, identisch zur Passage-Suche (content_chunk_repository).
_RRF_K = 60

# Ab welcher Cosinus-AEHNLICHKEIT ein Vektor-Treffer zaehlt. Ohne Schranke
# liefert die Vektor-Suche IMMER die k naechsten Memories — auch zu einer voellig
# fremden Frage. Bei Memory waere das besonders schaedlich: der Agent haelt
# gespeicherte Nutzerdaten fuer eine Antwort auf seine Frage.
# Bewusst konservativ, gegen das reale Modell noch nicht kalibriert (ADR-0046).
_MIN_VECTOR_SIMILARITY = 0.45

# Ab welcher Cosinus-AEHNLICHKEIT der Dedup-Waechter zuschlaegt. DEUTLICH
# strenger als die Suchschwelle: ein falsch positiver Dedup verwirft einen
# gueltigen Fakt dauerhaft (409), ein falsch negativer kostet nur einen
# Listenplatz von 500. Die Asymmetrie der Kosten bestimmt die Schwelle.
_DEDUP_VECTOR_SIMILARITY = 0.92

# Existiert die Vektor-Spalte? Migration 0072 legt sie NICHT an, wenn pgvector
# auf dem Server fehlt (fail-soft) — der Normalfall einer On-Prem-Instanz auf
# Standard-Postgres, der keinen Fehler ausloesen darf.
#
# `pg_attribute` + `to_regclass` statt `information_schema.columns`: nur so wird
# die Tabelle geprueft, die die Queries per `search_path` auch treffen (Muster
# Migration 0021, Begruendung in `content_chunk_repository._HAS_VECTOR_SQL`).
_HAS_VECTOR_SQL = """
SELECT EXISTS (
    SELECT 1 FROM pg_attribute
    WHERE attrelid = to_regclass('agent_memory')
      AND attname = 'content_vector'
      AND NOT attisdropped
)
"""

_vector_supported: bool | None = None

_READ_COLUMNS = (
    "id, agent_id, status, fact, context, category, importance, source, "
    "triage_note, retrieval_count, last_retrieved_at, created_at, updated_at, "
    "kind, scope, subject_user_id, origin, created_by_agent_id, confirmed_at, "
    "confirmed_by, expires_at, occurrence_count, converted_case_id"
)

_EVENT_COLUMNS = (
    "id, memory_id, event, actor_kind, actor_id, agent_id, before, after, reason, created_at"
)

_PROPOSAL_COLUMNS = (
    "id, memory_id, agent_id, action, new_fact, reason, status, decided_by, decided_at, created_at"
)
_PROPOSAL_COLUMNS_P = ", ".join(f"p.{c.strip()}" for c in _PROPOSAL_COLUMNS.split(","))

# Inhaltsfreie Spur einer Loeschung (ADR-0053 3.1.2, Weiche M5): nur WER WANN
# WELCHE ID geloescht hat — nie Fakt, Kontext oder Historie. Die Historie geht
# per Cascade mit dem Eintrag.
MEMORY_DELETED_AUDIT_ACTION = "memory.deleted"
# Ein- und Ausschalten einer Zelle der Freigabematrix (ADR-0053 4.3: wer,
# wann, welche Zelle). Je geaenderter Zelle eine Zeile, `detail={row, origin}`.
MEMORY_AUTO_POLICY_ENABLED_AUDIT_ACTION = "memory.auto_policy.enabled"
MEMORY_AUTO_POLICY_DISABLED_AUDIT_ACTION = "memory.auto_policy.disabled"


def _jsonb_out(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    raw = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, dict):
        raise TypeError(f"jsonb-Schnappschuss ist kein Objekt: {type(raw).__name__}")
    return raw


def _snapshot(memory: MemoryRead) -> dict[str, Any]:
    """Historien-Schnappschuss (3.1.2): nie `context` oder `triage_note`."""
    return {
        "fact": memory.fact,
        "category": memory.category.value,
        "importance": memory.importance,
        "status": memory.status.value,
        "kind": memory.kind.value,
        "origin": memory.origin.value,
    }


def _cell_key(cell: MemoryAutoCell) -> str:
    """Stabiler `audit_log.target` einer Matrix-Zelle, z. B. `user_fact:user_stated`."""
    return f"{cell.row.value}:{cell.origin.value}"


def _event(row: asyncpg.Record) -> MemoryEventRead:
    data = dict(row)
    data["before"] = _jsonb_out(data["before"])
    data["after"] = _jsonb_out(data["after"])
    return MemoryEventRead.model_validate(data)


def reset_vector_support() -> None:
    """Verwirft den Prozess-Cache der Spalten-Erkennung (Tests)."""
    global _vector_supported
    _vector_supported = None


class MemoryRepository(Protocol):
    """Vertrag des Memory-Datenzugriffs (Service-Sicht)."""

    async def agent_belongs_to(self, workspace_id: UUID, agent_id: UUID) -> bool: ...

    async def get_guard_config(self, workspace_id: UUID) -> MemoryGuardConfig: ...

    async def set_guard_config(
        self, workspace_id: UUID, config: MemoryGuardConfig
    ) -> MemoryGuardConfig: ...

    async def count_for_agent(self, workspace_id: UUID, agent_id: UUID) -> int: ...

    async def count_notes_for_agent(self, workspace_id: UUID, agent_id: UUID) -> int: ...

    async def get_auto_policy(self, workspace_id: UUID) -> MemoryAutoPolicy: ...

    async def set_auto_policy(
        self, workspace_id: UUID, policy: MemoryAutoPolicy, actor_id: UUID
    ) -> MemoryAutoPolicy: ...

    async def find_similar(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        fact: str,
        fact_vector: Sequence[float] | None = None,
        *,
        lessons: bool = False,
    ) -> tuple[UUID, str] | None: ...

    async def find_similar_user(
        self,
        workspace_id: UUID,
        subject_user_id: UUID,
        fact: str,
        fact_vector: Sequence[float] | None = None,
    ) -> tuple[UUID, str] | None: ...

    async def insert(
        self,
        workspace_id: UUID,
        agent_id: UUID | None,
        status: MemoryStatus,
        fact: str,
        context: str | None,
        category: str,
        importance: int,
        *,
        kind: MemoryKind = MemoryKind.user_fact,
        scope: MemoryScope = MemoryScope.agent,
        origin: MemoryOrigin = MemoryOrigin.legacy_unknown,
        source: MemorySource = MemorySource.agent,
        subject_user_id: UUID | None = None,
        created_by_agent_id: UUID | None = None,
        auto_activated: bool = False,
    ) -> MemoryRead: ...

    async def merge_lesson(
        self, workspace_id: UUID, agent_id: UUID, memory_id: UUID
    ) -> MemoryRead | None: ...

    async def search_active(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        query: str,
        k: int,
        query_vector: Sequence[float] | None = None,
    ) -> list[MemoryHit]: ...

    async def set_vector(self, memory_id: UUID, vector: Sequence[float]) -> None: ...

    async def list_active(
        self, workspace_id: UUID, agent_id: UUID, limit: int
    ) -> list[MemoryHit]: ...

    async def list_for_agent(
        self, workspace_id: UUID, agent_id: UUID, status: MemoryStatus | None
    ) -> list[MemoryRead]: ...

    async def get(
        self, workspace_id: UUID, agent_id: UUID, memory_id: UUID
    ) -> MemoryRead | None: ...

    async def triage(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        new_status: MemoryStatus,
        fact: str | None,
        note: str | None,
        actor_id: UUID | None = None,
    ) -> MemoryRead | None: ...

    async def update(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        fact: str | None,
        category: str | None,
        importance: int | None,
        actor_id: UUID | None = None,
    ) -> MemoryRead | None: ...

    async def delete(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        actor_id: UUID | None = None,
    ) -> bool: ...

    async def delete_all(
        self, workspace_id: UUID, agent_id: UUID, actor_id: UUID | None = None
    ) -> int: ...

    async def count_for_user(self, workspace_id: UUID, subject_user_id: UUID) -> int: ...

    async def insert_event(
        self, workspace_id: UUID, data: MemoryEventCreate
    ) -> MemoryEventRead: ...

    async def list_events(self, workspace_id: UUID, memory_id: UUID) -> list[MemoryEventRead]: ...

    # --- Paket C3a: Besitzer-gebundene Pfade (Agenten- UND Nutzergedaechtnis)

    async def get_owned(
        self, workspace_id: UUID, owner: MemoryOwner, memory_id: UUID
    ) -> MemoryRead | None: ...

    async def list_for_user(
        self, workspace_id: UUID, subject_user_id: UUID, status: MemoryStatus | None
    ) -> list[MemoryRead]: ...

    async def triage_owned(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        memory_id: UUID,
        new_status: MemoryStatus,
        fact: str | None,
        note: str | None,
        actor_id: UUID | None = None,
    ) -> MemoryRead | None: ...

    async def update_owned(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        memory_id: UUID,
        fact: str | None,
        category: str | None,
        importance: int | None,
        actor_id: UUID | None = None,
    ) -> MemoryRead | None: ...

    async def delete_owned(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        memory_id: UUID,
        actor_id: UUID | None = None,
    ) -> bool: ...

    async def confirm(
        self, workspace_id: UUID, owner: MemoryOwner, memory_id: UUID, actor_id: UUID
    ) -> MemoryRead | None: ...

    async def reactivate(
        self, workspace_id: UUID, owner: MemoryOwner, memory_id: UUID, actor_id: UUID
    ) -> MemoryRead | None: ...

    async def restore(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        memory_id: UUID,
        snapshot: MemorySnapshot,
        actor_id: UUID,
        reason: str,
    ) -> MemoryRead | None: ...

    async def insert_proposal(
        self, workspace_id: UUID, agent_id: UUID, memory: MemoryRead, data: MemoryProposalCreate
    ) -> MemoryProposalRead: ...

    async def get_proposal(
        self, workspace_id: UUID, proposal_id: UUID
    ) -> tuple[MemoryProposalRead, MemoryOwner] | None: ...

    async def list_proposals(
        self,
        workspace_id: UUID,
        *,
        viewer_user_id: UUID,
        include_agent_scope: bool,
        agent_id: UUID | None = None,
        status: MemoryProposalStatus | None = None,
    ) -> list[MemoryProposalRead]: ...

    async def decide_proposal(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        proposal_id: UUID,
        *,
        accept: bool,
        actor_id: UUID,
        note: str | None,
    ) -> MemoryProposalRead | None: ...

    # --- Paket C3b-2: Not-Aus (6.4.1)

    async def preview_auto_revocable(
        self, workspace_id: UUID, selection: MemoryRevokeSelection, sample_size: int
    ) -> MemoryRevokeOutcome: ...

    async def revoke_auto(
        self,
        workspace_id: UUID,
        selection: MemoryRevokeSelection,
        *,
        expected_count: int,
        actor_id: UUID,
    ) -> MemoryRevokeOutcome: ...

    # --- Paket C3c-1a: workspace-weite Liste und Zaehler (6.4.1)

    async def list_visible(
        self,
        workspace_id: UUID,
        visibility: MemoryVisibility,
        filters: MemoryFilter,
        *,
        sort: MemoryListSort,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> list[MemoryRead]: ...

    async def count_visible(
        self, workspace_id: UUID, visibility: MemoryVisibility, filters: MemoryFilter
    ) -> int: ...

    async def count_grouped(
        self,
        workspace_id: UUID,
        visibility: MemoryVisibility,
        filters: MemoryFilter,
        group: MemoryCountGroup,
    ) -> dict[str, int]: ...


@dataclass(frozen=True)
class MemoryVisibility:
    """Was ein Mensch in der workspace-weiten Sicht sehen darf (ADR-0053 6.4.1).

    Immer das eigene Nutzergedaechtnis (`viewer_user_id`); das
    Agentengedaechtnis aller Agenten nur mit `include_agent_scope` (ab
    `editor`). Das Nutzergedaechtnis anderer Personen gehoert nie zur Sicht
    (3.1.1, Owner-Entscheidung 3a). Einzige Ausnahme ist die Zaehler-Gruppe
    `subject_user_id`: sie zaehlt jedes Nutzergedaechtnis, liefert aber nur
    Zahlen, und der Service gibt sie nur `admin` frei.
    """

    viewer_user_id: UUID
    include_agent_scope: bool


@dataclass(frozen=True)
class MemoryRevokeSelection:
    """Auswahl des Not-Aus (ADR-0053 6.4.1), vom Service aus Body und Rechten gebaut.

    Betroffen: `status='active'`, `confirmed_at IS NULL` und ein Ereignis
    `auto_activated` mit `since <= created_at < until`. Sichtbar fuer den
    Aufrufer sind das Agentengedaechtnis und sein eigenes Nutzergedaechtnis
    (`viewer_user_id`). Das Nutzergedaechtnis anderer Personen gehoert nur mit
    `include_other_users` zur Auswahl — und bleibt auch dann verborgen: es
    zaehlt in `hidden_count`, erscheint aber nie mit Inhalt oder ID (3.1.1).
    """

    viewer_user_id: UUID
    since: datetime
    until: datetime | None = None
    agent_id: UUID | None = None
    origins: tuple[MemoryOrigin, ...] | None = None
    include_other_users: bool = False


@dataclass(frozen=True)
class MemoryRevokeOutcome:
    """Ergebnis von Vorschau bzw. Ruecknahme.

    `count` zaehlt alle Treffer, `hidden_count` deren Anteil aus fremdem
    Nutzergedaechtnis. `visible` sind nur Eintraege, die der Aufrufer sehen
    darf (Vorschau: hoechstens `sample_size`, vor der Aenderung; Ruecknahme:
    alle sichtbaren, nach der Aenderung). `applied=False` heisst: nichts
    geaendert (Vorschau oder abweichende Zahl).
    """

    count: int
    hidden_count: int
    visible: list[MemoryRead]
    applied: bool


@dataclass(frozen=True)
class MemoryOwner:
    """Besitzer eines Eintrags — genau eines der beiden Felder ist gesetzt.

    Jede besitzer-gebundene Abfrage filtert ueber `clause` auf Geltungsbereich
    UND Besitzer: Agentengedaechtnis ueber `agent_id`, Nutzergedaechtnis ueber
    `subject_user_id` (ADR-0053 3.1.1). So bleibt die Repository-Regel „kein
    Weg zu fremden Memories“ auch fuer das Nutzergedaechtnis erhalten.
    """

    agent_id: UUID | None = None
    subject_user_id: UUID | None = None

    def __post_init__(self) -> None:
        if (self.agent_id is None) == (self.subject_user_id is None):
            raise ValueError("MemoryOwner braucht genau einen Besitzer.")

    @property
    def owner_id(self) -> UUID:
        owner = self.agent_id if self.agent_id is not None else self.subject_user_id
        assert owner is not None  # __post_init__
        return owner

    def clause(self, param: int, alias: str = "") -> str:
        """SQL-Bedingung mit dem Besitzer als `$param` (feste Zeichenkette)."""
        p = f"{alias}." if alias else ""
        if self.agent_id is not None:
            return f"{p}scope = 'agent' AND {p}agent_id = ${param}"
        return f"{p}scope = 'user' AND {p}subject_user_id = ${param}"


# Schnappschuss-Form der Historie (3.1.2), Schluessel siehe `_snapshot`.
MemorySnapshot = dict[str, Any]


class PgMemoryRepository:
    """asyncpg-Implementierung von `MemoryRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def agent_belongs_to(self, workspace_id: UUID, agent_id: UUID) -> bool:
        owned = await self._pool.fetchval(
            "SELECT 1 FROM agent WHERE id = $1 AND workspace_id = $2",
            agent_id,
            workspace_id,
        )
        return owned is not None

    async def get_guard_config(self, workspace_id: UUID) -> MemoryGuardConfig:
        # `{}` (Spalten-Default) deserialisiert zur Standard-Konfiguration.
        raw = await self._pool.fetchval(
            "SELECT memory_guard FROM workspace WHERE id = $1", workspace_id
        )
        if raw is None:
            return MemoryGuardConfig()
        return MemoryGuardConfig.model_validate(json.loads(raw) if isinstance(raw, str) else raw)

    async def set_guard_config(
        self, workspace_id: UUID, config: MemoryGuardConfig
    ) -> MemoryGuardConfig:
        # dict, NICHT vor-serialisiert: der `::jsonb`-Cast aktiviert den
        # jsonb-Codec des App-Pools (`core/db.init_connection`), ein String
        # wuerde ein zweites Mal encodiert und landete als JSON-*String* in
        # der Spalte. `get_guard_config` faengt das zwar tolerant ab — die
        # gleiche Doppel-Encodierung hat den describe-Pfad aber ueber einen
        # strengeren Leser mit 500 beendet (Befund 2026-08-16).
        await self._pool.execute(
            "UPDATE workspace SET memory_guard = $2::jsonb WHERE id = $1",
            workspace_id,
            config.model_dump(mode="json"),
        )
        return config

    async def count_for_agent(self, workspace_id: UUID, agent_id: UUID) -> int:
        # Arbeitsnotizen zaehlen NICHT gegen MEMORY_MAX_PER_AGENT: sie haben
        # eine eigene, getrennte Obergrenze (ADR-0053 3.1.5), damit Notizen
        # die Nutzerfakten nicht verdraengen. `scope='user'` traegt
        # `agent_id IS NULL` und faellt ohnehin heraus (3.1.1).
        count = await self._pool.fetchval(
            "SELECT COUNT(*)::int FROM agent_memory "
            "WHERE workspace_id = $1 AND agent_id = $2 AND kind <> 'agent_note'",
            workspace_id,
            agent_id,
        )
        return int(count or 0)

    async def count_notes_for_agent(self, workspace_id: UUID, agent_id: UUID) -> int:
        """Arbeitsnotizen eines Agenten ueber ALLE Status (3.1.5)."""
        count = await self._pool.fetchval(
            "SELECT COUNT(*)::int FROM agent_memory "
            "WHERE workspace_id = $1 AND agent_id = $2 AND kind = 'agent_note'",
            workspace_id,
            agent_id,
        )
        return int(count or 0)

    async def get_auto_policy(self, workspace_id: UUID) -> MemoryAutoPolicy:
        # `{}` (Spalten-Default, 0095) = keine Zelle eingeschaltet (M3).
        raw = await self._pool.fetchval(
            "SELECT memory_auto_policy FROM workspace WHERE id = $1", workspace_id
        )
        if raw is None:
            return MemoryAutoPolicy()
        return MemoryAutoPolicy.model_validate(json.loads(raw) if isinstance(raw, str) else raw)

    async def set_auto_policy(
        self, workspace_id: UUID, policy: MemoryAutoPolicy, actor_id: UUID
    ) -> MemoryAutoPolicy:
        """Schreibt die WIRKSAME Matrix und protokolliert jede geaenderte Zelle.

        Nie-Zellen sind beim Aufrufer bereits herausgefiltert. Je ein- oder
        ausgeschalteter Zelle eine `audit_log`-Zeile (wer, wann, welche Zelle,
        ADR-0053 4.3) — in derselben Transaktion wie die Aenderung, damit es
        keine Einstellung ohne Spur gibt. Eine unveraenderte Einstellung
        schreibt keine Audit-Zeile.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            raw = await conn.fetchval(
                "SELECT memory_auto_policy FROM workspace WHERE id = $1 FOR UPDATE",
                workspace_id,
            )
            previous = (
                MemoryAutoPolicy.model_validate(json.loads(raw) if isinstance(raw, str) else raw)
                if raw is not None
                else MemoryAutoPolicy()
            ).effective()
            current = frozenset(policy.enabled_cells)
            # dict an `::jsonb` (jsonb-Codec des App-Pools) — Muster set_guard_config.
            await conn.execute(
                "UPDATE workspace SET memory_auto_policy = $2::jsonb WHERE id = $1",
                workspace_id,
                policy.model_dump(mode="json"),
            )
            changes = [
                (MEMORY_AUTO_POLICY_ENABLED_AUDIT_ACTION, cell) for cell in current - previous
            ] + [(MEMORY_AUTO_POLICY_DISABLED_AUDIT_ACTION, cell) for cell in previous - current]
            for action, cell in sorted(changes, key=lambda c: (c[0], c[1].row, c[1].origin)):
                await conn.execute(
                    "INSERT INTO audit_log (workspace_id, actor_id, action, target, detail) "
                    "VALUES ($1, $2, $3, $4, $5::jsonb)",
                    workspace_id,
                    actor_id,
                    action,
                    _cell_key(cell),
                    {"row": cell.row.value, "origin": cell.origin.value},
                )
        return policy

    async def find_similar(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        fact: str,
        fact_vector: Sequence[float] | None = None,
        *,
        lessons: bool = False,
    ) -> tuple[UUID, str] | None:
        """Findet ein hinreichend aehnliches Memory (Dedup-Waechter).

        Prueft gegen ALLE Status, auch `rejected` — sonst schlaegt der Agent
        Abgelehntes in der naechsten Session erneut vor.

        `lessons=True` sucht nur unter den Lernvorschlaegen des Agenten (Basis
        des lesson-Merge, ADR-0053 3.1.6, inkl. `rejected`/`converted`);
        sonst nur unter den uebrigen Arten. Die Kanaele sind getrennt: ein
        Lernvorschlag (nie abrufbar) darf keinen Fakt blockieren und
        umgekehrt.

        Der Trigram-Zweig (≥ `MEMORY_DEDUP_SIMILARITY`) bleibt massgeblich und
        unveraendert. Der Vektor-Zweig kommt additiv dazu und faengt
        Paraphrasen, die zeichenbasiert nicht aehnlich sind („Kunde bevorzugt
        E-Mail" vs. „Kontaktpraeferenz des Kunden ist E-Mail"). Seine Schwelle
        ist deutlich strenger als die der Suche: ein falsch positiver Dedup
        verwirft einen gueltigen Fakt dauerhaft, ein falsch negativer kostet
        nur einen von 500 Listenplaetzen.
        """
        kind_filter = "kind = 'lesson'" if lessons else "kind <> 'lesson'"
        return await self._find_similar_where(
            f"workspace_id = $1 AND agent_id = $2 AND {kind_filter}",
            workspace_id,
            agent_id,
            fact,
            fact_vector,
        )

    async def find_similar_user(
        self,
        workspace_id: UUID,
        subject_user_id: UUID,
        fact: str,
        fact_vector: Sequence[float] | None = None,
    ) -> tuple[UUID, str] | None:
        """Dedup-Waechter des Nutzergedaechtnisses je (workspace_id, subject_user_id)."""
        return await self._find_similar_where(
            "workspace_id = $1 AND scope = 'user' AND subject_user_id = $2",
            workspace_id,
            subject_user_id,
            fact,
            fact_vector,
        )

    async def _find_similar_where(
        self,
        where: str,
        workspace_id: UUID,
        owner_id: UUID,
        fact: str,
        fact_vector: Sequence[float] | None,
    ) -> tuple[UUID, str] | None:
        # `where` ist eine feste Zeichenkette dieser Klasse, nie Eingabe.
        use_vector = fact_vector is not None and await self.vector_supported()
        if not use_vector:
            row = await self._pool.fetchrow(
                "SELECT id, fact FROM agent_memory "
                f"WHERE {where} AND similarity(fact, $3) >= $4 "
                "ORDER BY similarity(fact, $3) DESC LIMIT 1",
                workspace_id,
                owner_id,
                fact,
                MEMORY_DEDUP_SIMILARITY,
            )
        else:
            row = await self._pool.fetchrow(
                "SELECT id, fact FROM agent_memory "
                f"WHERE {where} "
                "  AND (similarity(fact, $3) >= $4 "
                "       OR (content_vector IS NOT NULL "
                f"           AND 1 - (content_vector <=> $5::vector) >= "
                f"{_DEDUP_VECTOR_SIMILARITY})) "
                "ORDER BY similarity(fact, $3) DESC LIMIT 1",
                workspace_id,
                owner_id,
                fact,
                MEMORY_DEDUP_SIMILARITY,
                list(fact_vector or []),
            )
        if row is None:
            return None
        return (row["id"], row["fact"])

    async def insert(
        self,
        workspace_id: UUID,
        agent_id: UUID | None,
        status: MemoryStatus,
        fact: str,
        context: str | None,
        category: str,
        importance: int,
        *,
        kind: MemoryKind = MemoryKind.user_fact,
        scope: MemoryScope = MemoryScope.agent,
        origin: MemoryOrigin = MemoryOrigin.legacy_unknown,
        source: MemorySource = MemorySource.agent,
        subject_user_id: UUID | None = None,
        created_by_agent_id: UUID | None = None,
        auto_activated: bool = False,
    ) -> MemoryRead:
        """Legt einen Eintrag an und schreibt seine ersten Historien-Ereignisse.

        `created_by_agent_id` faellt auf `agent_id` zurueck (Agentengedaechtnis);
        beim Nutzergedaechtnis ist `agent_id` NULL und der Einreicher steht
        nur dort (3.1). `auto_activated`: die Freigabematrix hat den Eintrag
        aktiv gesetzt. Verfall (3.1.3): jeder unbestaetigte Eintrag — `pending`
        oder automatisch aktiviert — bekommt `expires_at = created_at + 30
        Tage` (`now()` ist in der Transaktion stabil, also gleich
        `created_at`). Ausgenommen ist `lesson`: der DB-CHECK 0091 laesst fuer
        Lernvorschlaege kein `expired` zu, sie bleiben Signal fuer die
        Mustererkennung (3.1.6). Ereignisse: `created` (Agent) und ggf.
        `auto_activated` (System, „Matrix") — in derselben Transaktion.
        """
        submitter = created_by_agent_id if created_by_agent_id is not None else agent_id
        unconfirmed = auto_activated or status == MemoryStatus.pending
        expires = kind != MemoryKind.lesson and unconfirmed
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO agent_memory "
                "(workspace_id, agent_id, created_by_agent_id, status, fact, context, "
                " category, importance, kind, scope, origin, source, subject_user_id, "
                " expires_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, "
                "        CASE WHEN $14::bool THEN now() + make_interval(days => $15) END) "
                f"RETURNING {_READ_COLUMNS}",
                workspace_id,
                agent_id,
                submitter,
                status.value,
                fact,
                context,
                category,
                importance,
                kind.value,
                scope.value,
                origin.value,
                source.value,
                subject_user_id,
                expires,
                MEMORY_UNCONFIRMED_TTL_DAYS,
            )
            assert row is not None
            created = MemoryRead.model_validate(dict(row))
            events = [(MemoryEventKind.created, MemoryActorKind.agent)]
            if auto_activated:
                events.append((MemoryEventKind.auto_activated, MemoryActorKind.system))
            for event, actor_kind in events:
                await conn.execute(
                    "INSERT INTO agent_memory_event "
                    "(workspace_id, memory_id, event, actor_kind, agent_id, after) "
                    "VALUES ($1, $2, $3, $4, $5, $6::jsonb)",
                    workspace_id,
                    created.id,
                    event.value,
                    actor_kind.value,
                    submitter,
                    _snapshot(created),
                )
        return created

    async def merge_lesson(
        self, workspace_id: UUID, agent_id: UUID, memory_id: UUID
    ) -> MemoryRead | None:
        """Wiederholung eines Lernvorschlags (ADR-0053 3.1.6, 3.1.2 `merged`).

        Erhoeht `occurrence_count` am Treffer, laesst Status und Inhalt
        unveraendert und schreibt das Ereignis `merged` (Agent; `before` und
        `after` gleich, weil sich der Treffer inhaltlich nicht aendert) — in
        einer Transaktion. Keine neue Zeile, also auch keine Obergrenze.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "UPDATE agent_memory SET occurrence_count = occurrence_count + 1 "
                "WHERE workspace_id = $1 AND agent_id = $2 AND id = $3 AND kind = 'lesson' "
                f"RETURNING {_READ_COLUMNS}",
                workspace_id,
                agent_id,
                memory_id,
            )
            if row is None:
                return None
            merged = MemoryRead.model_validate(dict(row))
            snapshot = _snapshot(merged)
            await conn.execute(
                "INSERT INTO agent_memory_event "
                "(workspace_id, memory_id, event, actor_kind, agent_id, before, after) "
                "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $6::jsonb)",
                workspace_id,
                memory_id,
                MemoryEventKind.merged.value,
                MemoryActorKind.agent.value,
                agent_id,
                snapshot,
            )
        return merged

    async def vector_supported(self) -> bool:
        """True, wenn `agent_memory.content_vector` existiert (gecacht)."""
        global _vector_supported
        if _vector_supported is None:
            _vector_supported = bool(await self._pool.fetchval(_HAS_VECTOR_SQL))
        return _vector_supported

    async def search_active(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        query: str,
        k: int,
        query_vector: Sequence[float] | None = None,
    ) -> list[MemoryHit]:
        """Rangsortierte aktive Memories (ADR-0044, Fusion nach ADR-0046).

        Vier Zweige, jeder liefert einen eigenen Rang, verschmolzen per RRF:

        - **FTS** — Wortstamm-Treffer.
        - **ILIKE** — Teilstrings, die die Tokenisierung zerlegt (Projekt-IDs).
        - **Trigram** — Tippfehler und Abkuerzungen.
        - **Vektor** (optional) — Umschreibungen und sprachuebergreifend.

        Frueher entschied eine lexikografische Kaskade
        (`ts_rank` → `similarity` → `importance`). Die liess den ersten Term
        dominieren: ein perfekter Vektor-Treffer waere hinter jedem beliebigen
        FTS-Treffer gelandet. `importance` bleibt als Tiebreak — ein
        Transparenz-Signal des Kurators, kein Relevanzmass.

        `query_vector=None` (kein Embedding-Port oder keine Spalte) heisst
        einfach: drei Zweige statt vier.
        """
        use_vector = query_vector is not None and await self.vector_supported()

        # Feste Positionen: $1 workspace, $2 agent, $3 query, $4 limit,
        # $5 Trigram-Schwelle. Der Vektor kommt nur dazu, wenn er gebraucht
        # wird — ein gebundener, aber unreferenzierter Parameter waere fuer
        # Postgres typlos.
        args: list[object] = [workspace_id, agent_id, query, k, _SEARCH_SIMILARITY]
        # „ilike" waere als CTE-Name ein reserviertes Keyword.
        branches = ["fts", "substr", "trgm"]
        vector_cte = ""
        if use_vector:
            args.append(list(query_vector or []))
            branches.append("vec")
            vector_cte = (
                ", vec AS ("
                "  SELECT id, row_number() OVER ("
                "    ORDER BY content_vector <=> $6::vector, importance DESC"
                "  ) AS rnk"
                "  FROM scoped"
                "  WHERE content_vector IS NOT NULL"
                f"    AND 1 - (content_vector <=> $6::vector) >= {_MIN_VECTOR_SIMILARITY}"
                ")"
            )

        score = " + ".join(f"coalesce(1.0 / ({_RRF_K} + {b}.rnk), 0)" for b in branches)
        joins = " ".join(f"LEFT JOIN {b} ON {b}.id = s.id" for b in branches)
        matched = " OR ".join(f"{b}.id IS NOT NULL" for b in branches)

        sql = (
            "WITH scoped AS ("
            "  SELECT id, fact, category, importance, search"
            f"{', content_vector' if use_vector else ''}"
            "  FROM agent_memory"
            "  WHERE workspace_id = $1 AND agent_id = $2 AND status = 'active'"
            "    AND scope = 'agent'"
            "), "
            "fts AS ("
            "  SELECT id, row_number() OVER ("
            "    ORDER BY ts_rank(search, plainto_tsquery('simple', $3)) DESC, importance DESC"
            "  ) AS rnk"
            "  FROM scoped WHERE search @@ plainto_tsquery('simple', $3)"
            "), "
            "substr AS ("
            "  SELECT id, row_number() OVER (ORDER BY importance DESC) AS rnk"
            "  FROM scoped WHERE fact ILIKE '%' || $3 || '%'"
            "), "
            "trgm AS ("
            "  SELECT id, row_number() OVER ("
            "    ORDER BY similarity(fact, $3) DESC, importance DESC"
            "  ) AS rnk"
            "  FROM scoped WHERE similarity(fact, $3) >= $5"
            ")"
            f"{vector_cte} "
            "SELECT s.id, s.fact, s.category "
            f"FROM scoped s {joins} "
            f"WHERE {matched} "
            f"ORDER BY ({score}) DESC, s.importance DESC "
            "LIMIT $4"
        )

        rows = await self._pool.fetch(sql, *args)
        hits = [MemoryHit.model_validate(dict(row)) for row in rows]
        await self._bump_retrieval(workspace_id, agent_id, [hit.id for hit in hits])
        return hits

    async def set_vector(self, memory_id: UUID, vector: Sequence[float]) -> None:
        """Setzt den Vektor eines Memories (Schreibpfad + Backfill)."""
        if not await self.vector_supported():
            return
        await self._pool.execute(
            "UPDATE agent_memory SET content_vector = $2 WHERE id = $1",
            memory_id,
            list(vector),
        )

    async def fetch_missing_vectors(self, limit: int) -> list[tuple[UUID, str]]:
        """Memories ohne Vektor — Arbeitsvorrat des Backfills."""
        if not await self.vector_supported():
            return []
        rows = await self._pool.fetch(
            "SELECT id, fact FROM agent_memory "
            "WHERE content_vector IS NULL ORDER BY created_at LIMIT $1",
            limit,
        )
        return [(row["id"], row["fact"]) for row in rows]

    async def list_active(self, workspace_id: UUID, agent_id: UUID, limit: int) -> list[MemoryHit]:
        rows = await self._pool.fetch(
            "SELECT id, fact, category FROM agent_memory "
            "WHERE workspace_id = $1 AND agent_id = $2 AND status = 'active' "
            "AND scope = 'agent' "
            "ORDER BY importance DESC, created_at DESC LIMIT $3",
            workspace_id,
            agent_id,
            limit,
        )
        hits = [MemoryHit.model_validate(dict(row)) for row in rows]
        await self._bump_retrieval(workspace_id, agent_id, [hit.id for hit in hits])
        return hits

    async def _bump_retrieval(
        self, workspace_id: UUID, agent_id: UUID, memory_ids: list[UUID]
    ) -> None:
        # Nutzungs-Log (Transparenz, ADR-0044). Selbstlimitierend: pro Memory
        # hoechstens ein Write/Minute (Security-Review N-1 — Reads sind sonst
        # ein ungedrosselter Write-Verstaerker am write_rate_limit vorbei).
        # Der Zaehler ist ein Transparenz-Signal, kein exakter Abruf-Counter.
        if not memory_ids:
            return
        await self._pool.execute(
            "UPDATE agent_memory "
            "SET retrieval_count = retrieval_count + 1, last_retrieved_at = now() "
            "WHERE workspace_id = $1 AND agent_id = $2 AND id = ANY($3::uuid[]) "
            "AND (last_retrieved_at IS NULL OR last_retrieved_at < now() - interval '60 seconds')",
            workspace_id,
            agent_id,
            memory_ids,
        )

    async def list_for_agent(
        self, workspace_id: UUID, agent_id: UUID, status: MemoryStatus | None
    ) -> list[MemoryRead]:
        if status is None:
            rows = await self._pool.fetch(
                f"SELECT {_READ_COLUMNS} FROM agent_memory "
                "WHERE workspace_id = $1 AND agent_id = $2 "
                "ORDER BY created_at DESC",
                workspace_id,
                agent_id,
            )
        else:
            rows = await self._pool.fetch(
                f"SELECT {_READ_COLUMNS} FROM agent_memory "
                "WHERE workspace_id = $1 AND agent_id = $2 AND status = $3 "
                "ORDER BY created_at DESC",
                workspace_id,
                agent_id,
                status.value,
            )
        return [MemoryRead.model_validate(dict(row)) for row in rows]

    async def get(self, workspace_id: UUID, agent_id: UUID, memory_id: UUID) -> MemoryRead | None:
        return await self.get_owned(workspace_id, MemoryOwner(agent_id=agent_id), memory_id)

    async def get_owned(
        self, workspace_id: UUID, owner: MemoryOwner, memory_id: UUID
    ) -> MemoryRead | None:
        """Ein Eintrag, nur wenn er `owner` gehoert (Geltungsbereich UND Besitzer)."""
        row = await self._pool.fetchrow(
            f"SELECT {_READ_COLUMNS} FROM agent_memory "
            f"WHERE workspace_id = $1 AND {owner.clause(2)} AND id = $3",
            workspace_id,
            owner.owner_id,
            memory_id,
        )
        return MemoryRead.model_validate(dict(row)) if row is not None else None

    async def list_for_user(
        self, workspace_id: UUID, subject_user_id: UUID, status: MemoryStatus | None
    ) -> list[MemoryRead]:
        """Nutzergedaechtnis EINER Person (3.1.1), neueste zuerst."""
        rows = await self._pool.fetch(
            f"SELECT {_READ_COLUMNS} FROM agent_memory "
            "WHERE workspace_id = $1 AND scope = 'user' AND subject_user_id = $2 "
            "  AND ($3::text IS NULL OR status = $3::text) "
            "ORDER BY created_at DESC",
            workspace_id,
            subject_user_id,
            status.value if status is not None else None,
        )
        return [MemoryRead.model_validate(dict(row)) for row in rows]

    async def _mutate(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        owner: MemoryOwner,
        memory_id: UUID,
        *,
        set_sql: str,
        set_args: Sequence[object],
        condition: str,
        event: MemoryEventKind,
        actor_id: UUID | None,
        reason: str | None,
    ) -> MemoryRead | None:
        """Aendert einen Eintrag und schreibt sein Historien-Ereignis — in `conn`s Transaktion.

        Liest den Vorzustand `FOR UPDATE` (besitzer-gebunden, plus `condition`
        als feste Zusatzbedingung), aendert per `set_sql` (Parameter ab `$3`;
        `$1` Workspace, `$2` ID) und haengt `event` mit `before`/`after` an
        (Akteur: Mensch, 3.1.2). `None`, wenn kein passender Eintrag existiert.
        `set_sql` und `condition` sind feste Zeichenketten dieses Moduls.
        """
        before_row = await conn.fetchrow(
            f"SELECT {_READ_COLUMNS} FROM agent_memory "
            f"WHERE workspace_id = $1 AND {owner.clause(2)} AND id = $3 {condition} "
            "FOR UPDATE",
            workspace_id,
            owner.owner_id,
            memory_id,
        )
        if before_row is None:
            return None
        before = MemoryRead.model_validate(dict(before_row))
        row = await conn.fetchrow(
            f"UPDATE agent_memory SET {set_sql}, updated_at = now() "
            f"WHERE workspace_id = $1 AND id = $2 RETURNING {_READ_COLUMNS}",
            workspace_id,
            memory_id,
            *set_args,
        )
        assert row is not None  # Zeile ist gesperrt
        after = MemoryRead.model_validate(dict(row))
        await _insert_human_event(conn, workspace_id, before, event, actor_id, reason, after)
        return after

    async def triage(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        new_status: MemoryStatus,
        fact: str | None,
        note: str | None,
        actor_id: UUID | None = None,
    ) -> MemoryRead | None:
        return await self.triage_owned(
            workspace_id,
            MemoryOwner(agent_id=agent_id),
            memory_id,
            new_status,
            fact,
            note,
            actor_id,
        )

    async def triage_owned(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        memory_id: UUID,
        new_status: MemoryStatus,
        fact: str | None,
        note: str | None,
        actor_id: UUID | None = None,
    ) -> MemoryRead | None:
        # Triage wirkt NUR auf pending (Schleusen-Invariante): active/rejected
        # Zeilen bleiben unberuehrt — dann kommt None zurueck (Service → 409).
        # Freigabe ist menschliche Bestaetigung (3.1.3): `confirmed_at/_by`
        # gesetzt und `expires_at = NULL` — nur so endet der Verfall. Eine
        # Ablehnung laesst beides stehen; der Verfallsjob greift nur auf
        # `pending`/`active`. Ereignis `approved` bzw. `rejected` mit der
        # Notiz als Grund (3.1.2: `triage_note` wird gespiegelt) — ohne diese
        # Spur haette ein Rollback keinen Vorzustand der Freigabe.
        event = (
            MemoryEventKind.approved
            if new_status == MemoryStatus.active
            else MemoryEventKind.rejected
        )
        async with self._pool.acquire() as conn, conn.transaction():
            return await self._mutate(
                conn,
                workspace_id,
                owner,
                memory_id,
                set_sql=(
                    "status = $3::text, fact = COALESCE($4, fact), triage_note = $5, "
                    "confirmed_at = CASE WHEN $3::text = 'active' THEN now() "
                    "  ELSE confirmed_at END, "
                    "confirmed_by = CASE WHEN $3::text = 'active' THEN $6::uuid "
                    "  ELSE confirmed_by END, "
                    "expires_at = CASE WHEN $3::text = 'active' THEN NULL ELSE expires_at END"
                ),
                set_args=(new_status.value, fact, note, actor_id),
                condition="AND status = 'pending'",
                event=event,
                actor_id=actor_id,
                reason=note,
            )

    async def update(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        fact: str | None,
        category: str | None,
        importance: int | None,
        actor_id: UUID | None = None,
    ) -> MemoryRead | None:
        return await self.update_owned(
            workspace_id,
            MemoryOwner(agent_id=agent_id),
            memory_id,
            fact,
            category,
            importance,
            actor_id,
        )

    async def update_owned(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        memory_id: UUID,
        fact: str | None,
        category: str | None,
        importance: int | None,
        actor_id: UUID | None = None,
    ) -> MemoryRead | None:
        """Bearbeiten durch einen Menschen; schreibt `edited` (3.1.2)."""
        async with self._pool.acquire() as conn, conn.transaction():
            return await self._mutate(
                conn,
                workspace_id,
                owner,
                memory_id,
                set_sql=(
                    "fact = COALESCE($3, fact), category = COALESCE($4, category), "
                    "importance = COALESCE($5, importance)"
                ),
                set_args=(fact, category, importance),
                condition="",
                event=MemoryEventKind.edited,
                actor_id=actor_id,
                reason=None,
            )

    async def confirm(
        self, workspace_id: UUID, owner: MemoryOwner, memory_id: UUID, actor_id: UUID
    ) -> MemoryRead | None:
        """Bestaetigt einen aktiven, unbestaetigten Eintrag und hebt den Verfall auf (3.1.3)."""
        async with self._pool.acquire() as conn, conn.transaction():
            return await self._mutate(
                conn,
                workspace_id,
                owner,
                memory_id,
                set_sql="confirmed_at = now(), confirmed_by = $3, expires_at = NULL",
                set_args=(actor_id,),
                condition="AND status = 'active' AND confirmed_at IS NULL",
                event=MemoryEventKind.confirmed,
                actor_id=actor_id,
                reason=None,
            )

    async def reactivate(
        self, workspace_id: UUID, owner: MemoryOwner, memory_id: UUID, actor_id: UUID
    ) -> MemoryRead | None:
        """`expired` → `active`, bestaetigt durch diesen Menschen (6.4)."""
        async with self._pool.acquire() as conn, conn.transaction():
            return await self._mutate(
                conn,
                workspace_id,
                owner,
                memory_id,
                set_sql=(
                    "status = 'active', confirmed_at = now(), confirmed_by = $3, expires_at = NULL"
                ),
                set_args=(actor_id,),
                condition="AND status = 'expired'",
                event=MemoryEventKind.reactivated,
                actor_id=actor_id,
                reason=None,
            )

    async def restore(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        memory_id: UUID,
        snapshot: MemorySnapshot,
        actor_id: UUID,
        reason: str,
    ) -> MemoryRead | None:
        """Rollback (3.1.2): stellt `fact, category, importance, status` aus `snapshot` her.

        `kind` und `origin` bleiben: kein Ereignis aendert sie, und ein anderer
        Wert koennte die Art-x-Scope-Invarianten (0091) verletzen. Die
        Bestaetigung bleibt nur bei einem aktiven Ziel stehen; wer auf einen
        Stand vor der Freigabe zurueckgeht, nimmt auch die Bestaetigung
        zurueck. Ein dadurch unbestaetigter `pending`/`active`-Eintrag
        verfaellt wieder (ausser `lesson`, 3.1.3) — sonst entstuende ueber den
        Rollback ein unbestaetigter Eintrag ohne Verfall. Ereignis
        `rolled_back` mit `reason` (Verweis auf das Ziel-Ereignis).
        """
        async with self._pool.acquire() as conn, conn.transaction():
            return await self._mutate(
                conn,
                workspace_id,
                owner,
                memory_id,
                set_sql=(
                    "fact = $3, category = $4, importance = $5, status = $6::text, "
                    "confirmed_at = CASE WHEN $6::text = 'active' THEN confirmed_at END, "
                    "confirmed_by = CASE WHEN $6::text = 'active' THEN confirmed_by END, "
                    "expires_at = CASE "
                    "  WHEN kind = 'lesson' THEN expires_at "
                    "  WHEN $6::text = 'pending' "
                    "    OR ($6::text = 'active' AND confirmed_at IS NULL) "
                    "  THEN COALESCE(expires_at, now() + make_interval(days => $7)) "
                    "  WHEN $6::text = 'active' THEN NULL "
                    "  ELSE expires_at END"
                ),
                set_args=(
                    snapshot["fact"],
                    snapshot["category"],
                    snapshot["importance"],
                    snapshot["status"],
                    MEMORY_UNCONFIRMED_TTL_DAYS,
                ),
                condition="",
                event=MemoryEventKind.rolled_back,
                actor_id=actor_id,
                reason=reason,
            )

    async def delete(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        memory_id: UUID,
        actor_id: UUID | None = None,
    ) -> bool:
        return await self.delete_owned(
            workspace_id, MemoryOwner(agent_id=agent_id), memory_id, actor_id
        )

    async def delete_owned(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        memory_id: UUID,
        actor_id: UUID | None = None,
    ) -> bool:
        # Loeschen + inhaltsfreie Audit-Zeile in EINER Anweisung (atomar, M5).
        result = await self._pool.execute(
            _delete_with_audit_sql(owner, "AND id = $4"),
            workspace_id,
            owner.owner_id,
            actor_id,
            memory_id,
        )
        return _affected(result) == 1

    async def delete_all(
        self, workspace_id: UUID, agent_id: UUID, actor_id: UUID | None = None
    ) -> int:
        result = await self._pool.execute(
            _delete_with_audit_sql(MemoryOwner(agent_id=agent_id), ""),
            workspace_id,
            agent_id,
            actor_id,
        )
        return _affected(result)

    # ---------------------------------------------- Vorschlaege (3.1.4, C3a)

    async def insert_proposal(
        self, workspace_id: UUID, agent_id: UUID, memory: MemoryRead, data: MemoryProposalCreate
    ) -> MemoryProposalRead:
        """Legt einen Vorschlag an (immer `pending`), Ereignis `change_proposed`/`delete_proposed`.

        Es gibt keinen Parameter fuer den Status: ein Vorschlag entsteht
        ausnahmslos offen (Matrix 4.2, Zeile „Aenderung/Loeschung“: nie
        automatisch). Das Ereignis traegt den unveraenderten Stand als
        `before` und `after` und die Begruendung des Agenten als `reason`.
        """
        event = (
            MemoryEventKind.change_proposed
            if data.action == MemoryProposalAction.change
            else MemoryEventKind.delete_proposed
        )
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO agent_memory_proposal "
                "(workspace_id, memory_id, agent_id, action, new_fact, reason) "
                "VALUES ($1, $2, $3, $4, $5, $6) "
                f"RETURNING {_PROPOSAL_COLUMNS}",
                workspace_id,
                memory.id,
                agent_id,
                data.action.value,
                data.new_fact,
                data.reason,
            )
            assert row is not None
            snapshot = _snapshot(memory)
            await conn.execute(
                "INSERT INTO agent_memory_event "
                "(workspace_id, memory_id, event, actor_kind, agent_id, before, after, reason) "
                "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $6::jsonb, $7)",
                workspace_id,
                memory.id,
                event.value,
                MemoryActorKind.agent.value,
                agent_id,
                snapshot,
                data.reason,
            )
        return MemoryProposalRead.model_validate(dict(row))

    async def get_proposal(
        self, workspace_id: UUID, proposal_id: UUID
    ) -> tuple[MemoryProposalRead, MemoryOwner] | None:
        """Ein Vorschlag mit dem Besitzer des Eintrags, auf den er zielt.

        Die Rechtepruefung macht der Service anhand des Besitzers (3.1.1:
        Nutzergedaechtnis nur die Person selbst).
        """
        row = await self._pool.fetchrow(
            f"SELECT {_PROPOSAL_COLUMNS_P}, m.agent_id AS m_agent_id, "
            "       m.subject_user_id AS m_subject_user_id "
            "FROM agent_memory_proposal p "
            "JOIN agent_memory m ON m.workspace_id = p.workspace_id AND m.id = p.memory_id "
            "WHERE p.workspace_id = $1 AND p.id = $2",
            workspace_id,
            proposal_id,
        )
        if row is None:
            return None
        data = dict(row)
        owner = MemoryOwner(
            agent_id=data.pop("m_agent_id"), subject_user_id=data.pop("m_subject_user_id")
        )
        return MemoryProposalRead.model_validate(data), owner

    async def list_proposals(
        self,
        workspace_id: UUID,
        *,
        viewer_user_id: UUID,
        include_agent_scope: bool,
        agent_id: UUID | None = None,
        status: MemoryProposalStatus | None = None,
    ) -> list[MemoryProposalRead]:
        """Vorschlaege, die `viewer_user_id` sehen darf (3.1.1, 6.4.1).

        Sichtbar sind Vorschlaege zum Agentengedaechtnis (nur mit
        `include_agent_scope`, also ab `editor`) und Vorschlaege zum EIGENEN
        Nutzergedaechtnis. Vorschlaege zum Nutzergedaechtnis anderer Personen
        erscheinen nie — auch nicht fuer `admin`, auch nicht ueber den Filter
        `agent_id` (ein vorschlagender Agent kann beide Gedaechtnisse treffen).
        """
        rows = await self._pool.fetch(
            f"SELECT {_PROPOSAL_COLUMNS_P} "
            "FROM agent_memory_proposal p "
            "JOIN agent_memory m ON m.workspace_id = p.workspace_id AND m.id = p.memory_id "
            "WHERE p.workspace_id = $1 "
            "  AND ((m.scope = 'agent' AND $3::bool) "
            "       OR (m.scope = 'user' AND m.subject_user_id = $2)) "
            "  AND ($4::uuid IS NULL OR p.agent_id = $4::uuid) "
            "  AND ($5::text IS NULL OR p.status = $5::text) "
            "ORDER BY p.created_at DESC, p.id",
            workspace_id,
            viewer_user_id,
            include_agent_scope,
            agent_id,
            status.value if status is not None else None,
        )
        return [MemoryProposalRead.model_validate(dict(row)) for row in rows]

    async def decide_proposal(
        self,
        workspace_id: UUID,
        owner: MemoryOwner,
        proposal_id: UUID,
        *,
        accept: bool,
        actor_id: UUID,
        note: str | None,
    ) -> MemoryProposalRead | None:
        """Entscheidung eines Menschen (3.1.4), alles in einer Transaktion.

        - Ablehnung: Vorschlag `rejected`, Ereignis `proposal_rejected`.
        - Annahme `change`: Vorschlag `accepted`, Ereignisse
          `proposal_accepted` und `edited` (neuer Fakt).
        - Annahme `delete`: Vorschlag `accepted`, Eintrag hart geloescht mit
          inhaltsfreier `memory.deleted`-Spur; Historie und Vorschlag fallen
          per Cascade (M5). Die Antwort traegt den Stand vor dem Cascade.

        `None`, wenn der Vorschlag nicht (mehr) offen ist oder sein Eintrag
        nicht `owner` gehoert — die Status-Bedingung im UPDATE macht parallele
        Entscheidungen sicher.
        """
        new_status = MemoryProposalStatus.accepted if accept else MemoryProposalStatus.rejected
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "UPDATE agent_memory_proposal "
                "SET status = $3, decided_by = $4, decided_at = now() "
                "WHERE workspace_id = $1 AND id = $2 AND status = 'pending' "
                "  AND memory_id IN (SELECT id FROM agent_memory "
                f"                   WHERE workspace_id = $1 AND {owner.clause(5)}) "
                f"RETURNING {_PROPOSAL_COLUMNS}",
                workspace_id,
                proposal_id,
                new_status.value,
                actor_id,
                owner.owner_id,
            )
            if row is None:
                return None
            proposal = MemoryProposalRead.model_validate(dict(row))
            memory_row = await conn.fetchrow(
                f"SELECT {_READ_COLUMNS} FROM agent_memory "
                "WHERE workspace_id = $1 AND id = $2 FOR UPDATE",
                workspace_id,
                proposal.memory_id,
            )
            assert memory_row is not None  # Vorschlag haengt per FK am Eintrag
            memory = MemoryRead.model_validate(dict(memory_row))
            if not accept:
                await _insert_human_event(
                    conn, workspace_id, memory, MemoryEventKind.proposal_rejected, actor_id, note
                )
                return proposal
            if proposal.action == MemoryProposalAction.delete:
                await conn.execute(
                    _delete_with_audit_sql(owner, "AND id = $4"),
                    workspace_id,
                    owner.owner_id,
                    actor_id,
                    memory.id,
                )
                return proposal
            await _insert_human_event(
                conn, workspace_id, memory, MemoryEventKind.proposal_accepted, actor_id, note
            )
            await self._mutate(
                conn,
                workspace_id,
                owner,
                memory.id,
                set_sql="fact = $3",
                set_args=(proposal.new_fact,),
                condition="",
                event=MemoryEventKind.edited,
                actor_id=actor_id,
                reason=proposal.reason,
            )
            return proposal

    async def count_for_user(self, workspace_id: UUID, subject_user_id: UUID) -> int:
        """Eintraege des Nutzergedaechtnisses ueber ALLE Status (3.1.1).

        Grundlage der Obergrenze `MEMORY_MAX_PER_USER`; die Pruefung baut C2a.
        """
        count = await self._pool.fetchval(
            "SELECT COUNT(*)::int FROM agent_memory "
            "WHERE workspace_id = $1 AND scope = 'user' AND subject_user_id = $2",
            workspace_id,
            subject_user_id,
        )
        return int(count or 0)

    async def insert_event(self, workspace_id: UUID, data: MemoryEventCreate) -> MemoryEventRead:
        """Haengt ein Historien-Ereignis an (append-only, 3.1.2).

        `before`/`after` als dict an `$n::jsonb` (App-Pool mit jsonb-Codec,
        `core/db.init_connection`) — Muster `set_guard_config`.
        """
        row = await self._pool.fetchrow(
            "INSERT INTO agent_memory_event "
            "(workspace_id, memory_id, event, actor_kind, actor_id, agent_id, "
            " before, after, reason) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9) "
            f"RETURNING {_EVENT_COLUMNS}",
            workspace_id,
            data.memory_id,
            data.event.value,
            data.actor_kind.value,
            data.actor_id,
            data.agent_id,
            data.before,
            data.after,
            data.reason,
        )
        assert row is not None
        return _event(row)

    async def list_events(self, workspace_id: UUID, memory_id: UUID) -> list[MemoryEventRead]:
        """Historie eines Eintrags, aelteste zuerst."""
        rows = await self._pool.fetch(
            f"SELECT {_EVENT_COLUMNS} FROM agent_memory_event "
            "WHERE workspace_id = $1 AND memory_id = $2 ORDER BY created_at, id",
            workspace_id,
            memory_id,
        )
        return [_event(row) for row in rows]

    # ---------------------------------------------------- Not-Aus (6.4.1, C3b-2)

    async def preview_auto_revocable(
        self, workspace_id: UUID, selection: MemoryRevokeSelection, sample_size: int
    ) -> MemoryRevokeOutcome:
        """Vorschau: zaehlt die Treffer und liefert hoechstens `sample_size` sichtbare.

        Aendert nichts. Fremdes Nutzergedaechtnis zaehlt nur in `hidden_count`;
        die Stichprobe filtert es in SQL heraus, sein Inhalt verlaesst die
        Datenbank also gar nicht erst.
        """
        args = _revoke_args(workspace_id, selection)
        totals = await self._pool.fetchrow(
            "SELECT COUNT(*)::int AS count, "
            f"       COUNT(*) FILTER (WHERE {_REVOKE_HIDDEN})::int AS hidden "
            f"FROM agent_memory m WHERE {_REVOKE_WHERE}",
            *args,
        )
        assert totals is not None
        rows = await self._pool.fetch(
            f"SELECT {_READ_COLUMNS_M} FROM agent_memory m "
            f"WHERE {_REVOKE_WHERE} AND NOT ({_REVOKE_HIDDEN}) "
            f"ORDER BY m.created_at DESC, m.id LIMIT {int(sample_size)}",
            *args,
        )
        return MemoryRevokeOutcome(
            count=int(totals["count"]),
            hidden_count=int(totals["hidden"]),
            visible=[MemoryRead.model_validate(dict(row)) for row in rows],
            applied=False,
        )

    async def revoke_auto(
        self,
        workspace_id: UUID,
        selection: MemoryRevokeSelection,
        *,
        expected_count: int,
        actor_id: UUID,
    ) -> MemoryRevokeOutcome:
        """Not-Aus: alle Treffer `active` → `pending`, je Eintrag Ereignis `auto_revoked`.

        Alles in EINER Transaktion: Auswahl `FOR UPDATE` (nach ID sortiert,
        damit zwei parallele Laeufe nicht gegenseitig verklemmen), Vergleich
        mit `expected_count`, Aenderung und Historie. Weicht die Zahl ab, wird
        nichts geaendert (`applied=False`). Faellt ein Schritt danach aus, rollt
        die Transaktion alles zurueck — alle oder keiner.

        Die Bestaetigung bleibt leer (der Eintrag war nie bestaetigt); der
        Verfall laeuft weiter bzw. wird gesetzt, falls er fehlt (3.1.3: kein
        unbestaetigter Eintrag ohne Verfall). Geloescht wird nichts.
        """
        args = _revoke_args(workspace_id, selection)
        async with self._pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch(
                f"SELECT {_READ_COLUMNS_M}, ({_REVOKE_HIDDEN}) AS hidden "
                f"FROM agent_memory m WHERE {_REVOKE_WHERE} "
                "ORDER BY m.id FOR UPDATE OF m",
                *args,
            )
            hidden_ids = {row["id"] for row in rows if row["hidden"]}
            count, hidden_count = len(rows), len(hidden_ids)
            if count != expected_count:
                return MemoryRevokeOutcome(
                    count=count, hidden_count=hidden_count, visible=[], applied=False
                )
            before = {
                row["id"]: MemoryRead.model_validate(
                    {k: v for k, v in row.items() if k != "hidden"}
                )
                for row in rows
            }
            updated = await conn.fetch(
                "UPDATE agent_memory SET status = 'pending', updated_at = now(), "
                "  expires_at = COALESCE(expires_at, now() + make_interval(days => $3)) "
                "WHERE workspace_id = $1 AND id = ANY($2::uuid[]) "
                f"RETURNING {_READ_COLUMNS}",
                workspace_id,
                list(before),
                MEMORY_UNCONFIRMED_TTL_DAYS,
            )
            if len(updated) != count:  # gesperrte Zeilen — darf nicht passieren
                raise RuntimeError("Not-Aus: Zeilenzahl nach dem Update weicht ab.")
            after = sorted(
                (MemoryRead.model_validate(dict(row)) for row in updated), key=lambda m: m.id
            )
            for memory in after:
                await _insert_human_event(
                    conn,
                    workspace_id,
                    before[memory.id],
                    MemoryEventKind.auto_revoked,
                    actor_id,
                    None,
                    memory,
                )
        return MemoryRevokeOutcome(
            count=count,
            hidden_count=hidden_count,
            visible=[m for m in after if m.id not in hidden_ids],
            applied=True,
        )

    # ------------------------- Workspace-weite Liste und Zaehler (6.4.1, C3c-1a)

    async def list_visible(
        self,
        workspace_id: UUID,
        visibility: MemoryVisibility,
        filters: MemoryFilter,
        *,
        sort: MemoryListSort,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> list[MemoryRead]:
        """Eine Seite der sichtbaren Eintraege, Keyset auf `(created_at, id)`.

        Beide Sortierschluessel laufen in dieselbe Richtung; `id` bricht
        Gleichstaende, damit die Reihenfolge deterministisch ist und keine
        Zeile an einer Seitengrenze doppelt erscheint oder fehlt.
        """
        where = _memory_where(workspace_id, visibility, filters)
        direction, compare = ("ASC", ">") if sort == MemoryListSort.oldest else ("DESC", "<")
        if cursor is not None:
            at, after_id = cursor
            where.add(
                f"(m.created_at, m.id) {compare} "
                f"({where.bind(at)}::timestamptz, {where.bind(after_id)}::uuid)"
            )
        rows = await self._pool.fetch(
            f"SELECT {_READ_COLUMNS_M} FROM agent_memory m WHERE {where.sql} "
            f"ORDER BY m.created_at {direction}, m.id {direction} "
            f"LIMIT {where.bind(limit)}",
            *where.args,
        )
        return [MemoryRead.model_validate(dict(row)) for row in rows]

    async def count_visible(
        self, workspace_id: UUID, visibility: MemoryVisibility, filters: MemoryFilter
    ) -> int:
        """Anzahl der Eintraege, die `list_visible` mit denselben Filtern zeigt."""
        where = _memory_where(workspace_id, visibility, filters)
        count = await self._pool.fetchval(
            f"SELECT COUNT(*)::int FROM agent_memory m WHERE {where.sql}", *where.args
        )
        return int(count or 0)

    async def count_grouped(
        self,
        workspace_id: UUID,
        visibility: MemoryVisibility,
        filters: MemoryFilter,
        group: MemoryCountGroup,
    ) -> dict[str, int]:
        """Facetten-Zaehler einer Gruppe, ohne den eigenen Filter dieser Gruppe.

        Jeder Wert ist so gezaehlt, dass er der Laenge von `list_visible` mit
        diesem Wert als Filter entspricht. `health` meldet alle Zustaende
        (auch 0), weil sie sich nicht ausschliessen und nicht per `GROUP BY`
        entstehen. Werte ohne Schluessel (Eintrag ohne Agent) fallen weg.

        `subject_user_id` zaehlt das Nutzergedaechtnis ALLER Personen im
        Workspace — nur Zahlen, ohne Freitextsuche (sonst waere fremder
        Inhalt ueber Zahlen abtastbar). Die Freigabe (nur `admin`) liegt im
        Service.
        """
        if group == MemoryCountGroup.health:
            where = _memory_where(workspace_id, visibility, filters, skip=group)
            columns = ", ".join(
                f"COUNT(*) FILTER (WHERE {_HEALTH_SQL[h]})::int AS {h.value}" for h in MemoryHealth
            )
            row = await self._pool.fetchrow(
                f"SELECT {columns} FROM agent_memory m WHERE {where.sql}", *where.args
            )
            assert row is not None
            return {h.value: int(row[h.value]) for h in MemoryHealth}
        where = _memory_where(
            workspace_id,
            visibility,
            filters,
            skip=group,
            all_user_memory=group == MemoryCountGroup.subject_user_id,
        )
        key = _GROUP_KEY_SQL[group]
        rows = await self._pool.fetch(
            f"SELECT {key} AS key, COUNT(*)::int AS n FROM agent_memory m "
            f"WHERE {where.sql} AND {key} IS NOT NULL GROUP BY 1 ORDER BY 1",
            *where.args,
        )
        return {row["key"]: int(row["n"]) for row in rows}


# Filterbau der workspace-weiten Sicht (6.4.1). Liste, Zaehler und spaeter die
# Stapel-Auswahl per Filter (C3c-2a) nutzen ihn gemeinsam, damit alle drei
# dieselbe Menge meinen. Jeder Wert aus `MemoryFilter` wird gebunden; der
# SQL-Text besteht nur aus festen Zeichenketten dieses Moduls.
_HEALTH_SQL: dict[MemoryHealth, str] = {
    MemoryHealth.unconfirmed: "m.status = 'active' AND m.confirmed_at IS NULL",
    # Ohne Untergrenze: ein ueberfaelliger Eintrag, den der Verfallsjob noch
    # nicht erreicht hat, verfaellt ebenfalls gleich.
    MemoryHealth.expiring_soon: (
        "m.status IN ('pending', 'active') "
        f"AND m.expires_at < now() + make_interval(days => {int(MEMORY_HEALTH_EXPIRING_DAYS)})"
    ),
    MemoryHealth.never_delivered: (
        "m.status = 'active' AND m.retrieval_count = 0 AND m.created_at < "
        f"now() - make_interval(days => {int(MEMORY_HEALTH_NEVER_DELIVERED_DAYS)})"
    ),
    MemoryHealth.stale_delivery: (
        "m.status = 'active' AND m.last_retrieved_at < "
        f"now() - make_interval(days => {int(MEMORY_HEALTH_STALE_DELIVERY_DAYS)})"
    ),
    MemoryHealth.external_or_inferred: "m.origin IN ('external_content', 'inferred')",
}

# Zurueckgehalten (6.4.1, PM-Entscheidung F1 = a): abgeleitet, kein Feld.
_HELD_SQL = (
    "m.status = 'pending' "
    "AND (m.origin IN ('external_content', 'inferred') OR m.category = 'instruction')"
)

# Der Agent eines Eintrags: beim Agentengedaechtnis der Besitzer, beim
# Nutzergedaechtnis (`agent_id IS NULL`, 3.1.1) der einreichende Agent.
_AGENT_SQL = "COALESCE(m.agent_id, m.created_by_agent_id)"

_GROUP_KEY_SQL: dict[MemoryCountGroup, str] = {
    MemoryCountGroup.agent: f"{_AGENT_SQL}::text",
    MemoryCountGroup.kind: "m.kind",
    MemoryCountGroup.status: "m.status",
    MemoryCountGroup.origin: "m.origin",
    MemoryCountGroup.source: "m.source",
    MemoryCountGroup.subject_user_id: "m.subject_user_id::text",
}


class _Where:
    """Sammelt Bedingungen und gebundene Parameter (`$1` ist der Workspace)."""

    def __init__(self, workspace_id: UUID) -> None:
        self.args: list[object] = [workspace_id]
        self._parts: list[str] = ["m.workspace_id = $1"]

    def bind(self, value: object) -> str:
        self.args.append(value)
        return f"${len(self.args)}"

    def add(self, condition: str) -> None:
        self._parts.append(condition)

    @property
    def sql(self) -> str:
        return " AND ".join(f"({part})" for part in self._parts)


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _memory_where(
    workspace_id: UUID,
    visibility: MemoryVisibility,
    filters: MemoryFilter,
    *,
    skip: MemoryCountGroup | None = None,
    all_user_memory: bool = False,
) -> _Where:
    """Bedingung der workspace-weiten Sicht samt Filtern.

    `skip` laesst den Filter einer Zaehler-Gruppe weg (Facette).
    `all_user_memory` ersetzt die Sichtbarkeit durch „jedes
    Nutzergedaechtnis“ und laesst `scope` und `q` weg — nur fuer die
    Zaehler-Gruppe `subject_user_id`.

    Warteschlangen-Regel (6.4.1 „Zaehler“): `status=pending` schliesst
    Lernvorschlaege aus, ausser bei `kind=lesson`. In der Facette `status`
    gilt dasselbe fuer den Wert `pending`, in der Facette `kind` traegt der
    Wert `lesson` die Ausnahme selbst.
    """
    where = _Where(workspace_id)
    if all_user_memory:
        where.add("m.scope = 'user'")
    else:
        own = f"m.scope = 'user' AND m.subject_user_id = {where.bind(visibility.viewer_user_id)}"
        where.add(f"({own}) OR m.scope = 'agent'" if visibility.include_agent_scope else own)
        if filters.scope is not None:
            where.add(f"m.scope = {where.bind(filters.scope.value)}")
        if filters.q is not None:
            where.add(f"m.fact ILIKE '%' || {where.bind(_escape_like(filters.q))} || '%'")
    explicit_lesson = filters.kind == MemoryKind.lesson
    if skip == MemoryCountGroup.status:
        if not explicit_lesson:
            where.add("NOT (m.status = 'pending' AND m.kind = 'lesson')")
    elif filters.status is not None:
        where.add(f"m.status = {where.bind(filters.status.value)}")
        if (
            filters.status == MemoryStatus.pending
            and not explicit_lesson
            and skip != MemoryCountGroup.kind
        ):
            where.add("m.kind <> 'lesson'")
    if filters.kind is not None and skip != MemoryCountGroup.kind:
        where.add(f"m.kind = {where.bind(filters.kind.value)}")
    if filters.agent_id is not None and skip != MemoryCountGroup.agent:
        where.add(f"{_AGENT_SQL} = {where.bind(filters.agent_id)}::uuid")
    if filters.origin is not None and skip != MemoryCountGroup.origin:
        where.add(f"m.origin = {where.bind(filters.origin.value)}")
    if filters.source is not None and skip != MemoryCountGroup.source:
        where.add(f"m.source = {where.bind(filters.source.value)}")
    if filters.health is not None and skip != MemoryCountGroup.health:
        where.add(_HEALTH_SQL[filters.health])
    if filters.held is not None:
        where.add(_HELD_SQL if filters.held else f"NOT ({_HELD_SQL})")
    if filters.created_after is not None:
        where.add(f"m.created_at >= {where.bind(filters.created_after)}::timestamptz")
    return where


# Not-Aus-Auswahl (6.4.1). Parameter: $1 Workspace, $2 Aufrufer (fuer die
# Sichtbarkeit), $3 since, $4 until, $5 Agent, $6 Herkuenfte, $7
# include_other_users. Fremdes Nutzergedaechtnis gehoert nur mit $7 zur
# Auswahl. Der Agentenfilter greift auf Besitzer ODER Einreicher, weil das
# Nutzergedaechtnis `agent_id IS NULL` traegt und der Einreicher dort nur in
# `created_by_agent_id` steht (3.1.1). Feste Zeichenketten, nie Eingabe.
_READ_COLUMNS_M = ", ".join(f"m.{c.strip()}" for c in _READ_COLUMNS.split(","))
_REVOKE_HIDDEN = "m.scope = 'user' AND m.subject_user_id <> $2"
_REVOKE_WHERE = (
    "m.workspace_id = $1 AND m.status = 'active' AND m.confirmed_at IS NULL "
    "AND EXISTS (SELECT 1 FROM agent_memory_event e "
    "            WHERE e.workspace_id = $1 AND e.memory_id = m.id "
    "              AND e.event = 'auto_activated' AND e.created_at >= $3 "
    "              AND ($4::timestamptz IS NULL OR e.created_at < $4::timestamptz)) "
    "AND ($5::uuid IS NULL OR m.agent_id = $5::uuid OR m.created_by_agent_id = $5::uuid) "
    "AND ($6::text[] IS NULL OR m.origin = ANY($6::text[])) "
    "AND (m.scope = 'agent' OR m.subject_user_id = $2 OR $7::bool)"
)


def _revoke_args(workspace_id: UUID, selection: MemoryRevokeSelection) -> tuple[object, ...]:
    return (
        workspace_id,
        selection.viewer_user_id,
        selection.since,
        selection.until,
        selection.agent_id,
        [o.value for o in selection.origins] if selection.origins is not None else None,
        selection.include_other_users,
    )


# Loescht Eintraege eines Besitzers und schreibt je geloeschter Zeile
# `audit_log (action='memory.deleted', target=<memory_id>)` — ohne Inhalt.
# Data-modifying CTE: beides in einer Anweisung, also atomar ohne explizite
# Transaktion. `$2` ist der Besitzer, `$3` der Akteur; `extra` engt optional
# auf eine ID ($4) ein. `extra` und die Besitzer-Bedingung sind feste
# Zeichenketten dieses Moduls, nie Eingabe.
def _delete_with_audit_sql(owner: MemoryOwner, extra: str) -> str:
    return (
        "WITH deleted AS ("
        f"  DELETE FROM agent_memory WHERE workspace_id = $1 AND {owner.clause(2)} {extra} "
        "  RETURNING id, workspace_id"
        ") "
        "INSERT INTO audit_log (workspace_id, actor_id, action, target) "
        f"SELECT workspace_id, $3::uuid, '{MEMORY_DELETED_AUDIT_ACTION}', id::text FROM deleted"
    )


async def _insert_human_event(
    conn: asyncpg.Connection,
    workspace_id: UUID,
    before: MemoryRead,
    event: MemoryEventKind,
    actor_id: UUID | None,
    reason: str | None,
    after: MemoryRead | None = None,
) -> None:
    """Historien-Ereignis eines Menschen (3.1.2); ohne `after` gilt der unveraenderte Stand."""
    snapshot_before = _snapshot(before)
    await conn.execute(
        "INSERT INTO agent_memory_event "
        "(workspace_id, memory_id, event, actor_kind, actor_id, before, after, reason) "
        "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)",
        workspace_id,
        before.id,
        event.value,
        MemoryActorKind.human.value,
        actor_id,
        snapshot_before,
        _snapshot(after) if after is not None else snapshot_before,
        reason,
    )


def _affected(status: object) -> int:
    """Zeilenzahl aus einem asyncpg-Status wie ``INSERT 0 3``."""
    try:
        return int(str(status).rsplit(" ", 1)[-1])
    except ValueError:
        return 0
