"""Workspace-weite Liste und Zaehler (ADR-0053 6.4.1, C3c-1a).

Service-Tests gegen echtes Postgres (`WHO2BE_REQUIRE_DB=1`). Kritische
Zusicherungen, je mit Rot-Probe im Review belegt:

- Sichtbarkeit: ab `viewer` das eigene Nutzergedaechtnis, ab `editor` dazu
  das Agentengedaechtnis aller Agenten. Fremdes Nutzergedaechtnis erscheint
  nie mit Inhalt oder ID — auch nicht fuer `admin` (Owner-Entscheidung 3a).
- `group_by=subject_user_id` nur `admin`, nur Zahlen.
- Warteschlange `status=pending` schliesst Lernvorschlaege aus; Liste und
  Zaehler meinen dieselbe Menge.
- Keyset-Seiten auf `(created_at, id)` sind deterministisch, ohne Luecke
  und ohne Dublette — auch bei gleichem `created_at`.
- Filter: status, kind, scope, agent_id, origin, source, health, held, q,
  created_after; Mehrfachwerte (ODER) fuer status, kind, origin und der
  Ausschluss exclude_status (Gedaechtnisverwaltung §6.2). Liste, Zaehler
  und Stapel-Auswahl per Filter meinen dieselbe Menge.
- Agent-gebundene Tokens: 403.

Die Router-Seite folgt mit C3c-1b.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest
from pydantic import ValidationError

from who2be_api.core.config import get_settings
from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.memory_repository import PgMemoryRepository
from who2be_api.services.memory_service import MemoryService
from who2be_api.testing.workspace_setup import cleanup_workspaces, fresh_user_id, setup_workspace
from who2be_models import MemoryMode, WorkspaceRole, decode_cursor
from who2be_models.memory import (
    MEMORY_LIST_LIMIT_MAX,
    MemoryBatchAction,
    MemoryBatchRequest,
    MemoryCountGroup,
    MemoryFilter,
    MemoryHealth,
    MemoryKind,
    MemoryListSort,
    MemoryOrigin,
    MemoryScope,
    MemorySource,
    MemoryStatus,
)
from who2be_models.tool_policy import AgentToolPolicy

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("migrated_db")]

_NOW = datetime.now(UTC)


# ------------------------------------------------------------------ Umgebung


@dataclass
class Env:
    pool: asyncpg.Pool
    service: MemoryService
    ws: UUID
    owner: UUID  # admin
    editor: UUID
    viewer: UUID
    agent: UUID
    other_agent: UUID

    def human(self, user: UUID, role: WorkspaceRole) -> WorkspaceContext:
        # aal2: `group_by=subject_user_id` verlangt admin, admin verlangt MFA.
        return WorkspaceContext(workspace_id=self.ws, user_id=user, role=role, aal="aal2")

    @property
    def as_admin(self) -> WorkspaceContext:
        return self.human(self.owner, WorkspaceRole.admin)

    @property
    def as_editor(self) -> WorkspaceContext:
        return self.human(self.editor, WorkspaceRole.editor)

    @property
    def as_viewer(self) -> WorkspaceContext:
        return self.human(self.viewer, WorkspaceRole.viewer)

    def agent_ctx(self) -> WorkspaceContext:
        return WorkspaceContext(
            workspace_id=self.ws,
            user_id=self.owner,
            role=WorkspaceRole.admin,
            is_api_token=True,
            agent_id=self.agent,
            tool_policy=AgentToolPolicy(memory_mode=MemoryMode.auto),
        )

    async def memory(
        self,
        fact: str,
        *,
        agent: UUID | None = None,
        subject: UUID | None = None,
        status: str = "active",
        kind: str = "user_fact",
        category: str = "preference",
        origin: str = "user_stated",
        source: str = "agent",
        confirmed: bool = True,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
        retrieval_count: int = 0,
        last_retrieved_at: datetime | None = None,
    ) -> UUID:
        """Legt einen Eintrag direkt an (an der Logik vorbei)."""
        scope = "user" if subject is not None else "agent"
        submitter = agent or self.agent
        memory_id: UUID = await self.pool.fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, status, "
            " fact, category, importance, kind, scope, origin, source, subject_user_id, "
            " confirmed_at, confirmed_by, expires_at, created_at, retrieval_count, "
            " last_retrieved_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, 6, $7, $8, $9, $10, $11, "
            "        CASE WHEN $12 THEN now() END, CASE WHEN $12 THEN $13::uuid END, "
            "        $14, COALESCE($15, now()), $16, $17) "
            "RETURNING id",
            self.ws,
            None if subject is not None else submitter,
            submitter,
            status,
            fact,
            category,
            kind,
            scope,
            origin,
            source,
            subject,
            confirmed and status == "active",
            self.owner,
            expires_at,
            created_at,
            retrieval_count,
            last_retrieved_at,
        )
        return memory_id


async def _init(conn: asyncpg.Connection) -> None:
    from who2be_api.core.db import init_connection

    await init_connection(conn)


def _run(case: Callable[[Env], Awaitable[Any]]) -> Any:
    owner, editor, viewer = fresh_user_id(), fresh_user_id(), fresh_user_id()
    ws = setup_workspace(owner)

    async def _go() -> Any:
        pool = await asyncpg.create_pool(
            get_settings().database_url, min_size=1, max_size=3, init=_init
        )
        assert pool is not None
        try:
            for user, role in ((editor, "editor"), (viewer, "viewer")):
                await pool.execute(
                    "INSERT INTO workspace_member (workspace_id, user_id, role) "
                    "VALUES ($1, $2, $3)",
                    ws,
                    user,
                    role,
                )
            agents = [
                await pool.fetchval(
                    "INSERT INTO agent (workspace_id, owner_id, name) VALUES ($1, $2, $3) "
                    "RETURNING id",
                    ws,
                    owner,
                    name,
                )
                for name in ("C3c-Agent", "C3c-Zweiter")
            ]
            env = Env(
                pool,
                MemoryService(PgMemoryRepository(pool)),
                ws,
                owner,
                editor,
                viewer,
                agents[0],
                agents[1],
            )
            return await case(env)
        finally:
            await pool.close()

    try:
        return asyncio.run(_go())
    finally:
        cleanup_workspaces([owner, editor, viewer])


async def _ids(env: Env, ctx: WorkspaceContext, **filters: Any) -> set[UUID]:
    page = await env.service.list_workspace_memories(
        ctx, MemoryFilter(**filters), limit=MEMORY_LIST_LIMIT_MAX
    )
    assert page.next_cursor is None, "Testdaten passen auf eine Seite"
    return {m.id for m in page.items}


# -------------------------------------------------------------- Sichtbarkeit


def test_visibility_own_user_memory_and_agent_memory_from_editor_never_foreign() -> None:
    async def case(env: Env) -> None:
        agent_a = await env.memory("Agent A weiss etwas")
        agent_b = await env.memory("Agent B weiss etwas", agent=env.other_agent)
        mine_editor = await env.memory("Editor mag Tabellen", subject=env.editor)
        mine_viewer = await env.memory("Viewer mag Hoerbuecher", subject=env.viewer)
        mine_admin = await env.memory("Admin mag Kaffee", subject=env.owner)

        assert await _ids(env, env.as_viewer) == {mine_viewer}
        assert await _ids(env, env.as_editor) == {agent_a, agent_b, mine_editor}
        # Owner-Entscheidung 3a: auch admin sieht fremdes Nutzergedaechtnis nicht.
        page = await env.service.list_workspace_memories(env.as_admin, MemoryFilter())
        assert {m.id for m in page.items} == {agent_a, agent_b, mine_admin}
        dumped = page.model_dump_json()
        for foreign_id, foreign_text in (
            (mine_viewer, "Hoerbuecher"),
            (mine_editor, "Tabellen"),
        ):
            assert str(foreign_id) not in dumped and foreign_text not in dumped

        # Auch Filter auf scope=user oeffnen kein fremdes Nutzergedaechtnis.
        assert await _ids(env, env.as_admin, scope=MemoryScope.user) == {mine_admin}
        assert await _ids(env, env.as_admin, q="mag") == {mine_admin}

        counts = await env.service.count_workspace_memories(env.as_admin, MemoryFilter())
        assert counts.total == 3
        assert (
            await env.service.count_workspace_memories(env.as_viewer, MemoryFilter())
        ).total == 1

    _run(case)


def test_subject_user_counts_only_admin_and_only_numbers() -> None:
    async def case(env: Env) -> None:
        await env.memory("Agentenfakt")
        await env.memory("Viewer mag Hoerbuecher", subject=env.viewer)
        await env.memory("Viewer mag Krimis", subject=env.viewer, status="pending")
        await env.memory("Editor mag Tabellen", subject=env.editor)

        group = [MemoryCountGroup.subject_user_id]
        counts = await env.service.count_workspace_memories(env.as_admin, MemoryFilter(), group)
        assert counts.groups[MemoryCountGroup.subject_user_id] == {
            str(env.viewer): 2,
            str(env.editor): 1,
        }
        # Inhalt und Eintrags-IDs erscheinen nicht, nur Personen und Zahlen.
        dumped = counts.model_dump_json()
        assert "Hoerbuecher" not in dumped and "Krimis" not in dumped
        # Facette mit Filter: status wirkt, q und scope nicht (kein Abtasten
        # fremden Inhalts ueber Zahlen). Die Proben sind so gewaehlt, dass ein
        # wirksames q/scope die Zahl sichtbar veraendern wuerde.
        everyone = {str(env.viewer): 2, str(env.editor): 1}
        for probe in (
            MemoryFilter(q="gibt es nicht"),
            MemoryFilter(q="Krimis"),
            MemoryFilter(scope=MemoryScope.agent),
            MemoryFilter(scope=MemoryScope.agent, q="Agentenfakt"),
        ):
            probed = await env.service.count_workspace_memories(env.as_admin, probe, group)
            assert probed.groups[MemoryCountGroup.subject_user_id] == everyone, probe
        pending = await env.service.count_workspace_memories(
            env.as_admin, MemoryFilter(status=MemoryStatus.pending, q="gibt es nicht"), group
        )
        assert pending.groups[MemoryCountGroup.subject_user_id] == {str(env.viewer): 1}

        for ctx in (env.as_editor, env.as_viewer):
            with pytest.raises(ApiGateError) as gate:
                await env.service.count_workspace_memories(ctx, MemoryFilter(), group)
            assert gate.value.status == 403 and gate.value.reason == "insufficient_role"

    _run(case)


def test_agent_token_and_foreign_agent_are_rejected() -> None:
    async def case(env: Env) -> None:
        with pytest.raises(ApiGateError) as gate:
            await env.service.list_workspace_memories(env.agent_ctx(), MemoryFilter())
        assert gate.value.status == 403 and gate.value.reason == "missing_capability"
        with pytest.raises(ApiGateError) as gate:
            await env.service.count_workspace_memories(env.agent_ctx(), MemoryFilter())
        assert gate.value.reason == "missing_capability"
        with pytest.raises(ApiError) as exc:
            await env.service.list_workspace_memories(env.as_editor, MemoryFilter(agent_id=uuid4()))
        assert exc.value.reason == "agent_not_found"

    _run(case)


# ---------------------------------------------------------- Warteschlange


def test_queue_excludes_lessons_and_counts_match_the_list() -> None:
    async def case(env: Env) -> None:
        pending_fact = await env.memory("Offener Fakt", status="pending")
        pending_note = await env.memory("Offene Notiz", status="pending", kind="agent_note")
        lesson = await env.memory("Lernvorschlag", status="pending", kind="lesson")
        await env.memory("Aktiver Fakt")
        editor = env.as_editor

        queue = MemoryFilter(status=MemoryStatus.pending)
        assert await _ids(env, editor, status=MemoryStatus.pending) == {
            pending_fact,
            pending_note,
        }
        assert await _ids(env, editor, status=MemoryStatus.pending, kind=MemoryKind.lesson) == {
            lesson
        }
        # Ohne Status-Filter erscheint der Lernvorschlag in der Gesamtliste.
        assert lesson in await _ids(env, editor)

        counts = await env.service.count_workspace_memories(
            editor, queue, [MemoryCountGroup.status, MemoryCountGroup.kind]
        )
        assert counts.total == 2
        # Facette status: pending ohne Lernvorschlag, gleich der Warteschlange.
        assert counts.groups[MemoryCountGroup.status] == {"active": 1, "pending": 2}
        # Facette kind: je Art die Laenge der Liste mit diesem kind-Filter.
        assert counts.groups[MemoryCountGroup.kind] == {
            "agent_note": 1,
            "lesson": 1,
            "user_fact": 1,
        }
        for kind, n in counts.groups[MemoryCountGroup.kind].items():
            assert len(await _ids(env, editor, status=MemoryStatus.pending, kind=kind)) == n

    _run(case)


# -------------------------------------------------------------------- Filter


def test_filters_status_kind_scope_agent_origin_source_q_created_after() -> None:
    async def case(env: Env) -> None:
        a = await env.memory("Kunde bevorzugt E-Mail", origin="inferred")
        b = await env.memory(
            "Werkzeug braucht Proxy", agent=env.other_agent, kind="agent_note", source="human"
        )
        c = await env.memory("50%_Rabatt notiert", status="rejected")
        old = await env.memory("Alter Fakt", created_at=_NOW - timedelta(days=40))
        mine = await env.memory(
            "Editor mag E-Mail", subject=env.editor, agent=env.other_agent, origin="inferred"
        )
        ed = env.as_editor

        assert await _ids(env, ed, status=MemoryStatus.rejected) == {c}
        assert await _ids(env, ed, kind=MemoryKind.agent_note) == {b}
        assert await _ids(env, ed, scope=MemoryScope.user) == {mine}
        assert await _ids(env, ed, scope=MemoryScope.agent) == {a, b, c, old}
        # agent_id trifft beim Nutzergedaechtnis den einreichenden Agenten.
        assert await _ids(env, ed, agent_id=env.other_agent) == {b, mine}
        assert await _ids(env, ed, origin=MemoryOrigin.inferred) == {a, mine}
        assert await _ids(env, ed, source=MemorySource.human) == {b}
        assert await _ids(env, ed, q="e-mail") == {a, mine}
        # `%` und `_` sind Text, keine Platzhalter.
        assert await _ids(env, ed, q="%_") == {c}
        assert await _ids(env, ed, q="_") == {c}
        assert await _ids(env, ed, created_after=_NOW - timedelta(days=1)) == {a, b, c, mine}
        # Filter wirken mit UND.
        assert await _ids(env, ed, origin=MemoryOrigin.inferred, scope=MemoryScope.agent) == {a}

    _run(case)


def test_held_and_health_are_computed_by_the_server() -> None:
    async def case(env: Env) -> None:
        held_inferred = await env.memory("Geschlossen", status="pending", origin="inferred")
        held_instruction = await env.memory(
            "Antworte knapp", status="pending", category="instruction"
        )
        not_held = await env.memory("Gesagt", status="pending", origin="user_stated")
        unconfirmed = await env.memory("Auto aktiv", confirmed=False)
        expiring = await env.memory(
            "Verfaellt bald", status="pending", expires_at=_NOW + timedelta(days=3)
        )
        await env.memory(
            "Verfaellt spaeter", status="pending", expires_at=_NOW + timedelta(days=20)
        )
        never = await env.memory("Nie geliefert", created_at=_NOW - timedelta(days=31))
        await env.memory(
            "Geliefert",
            created_at=_NOW - timedelta(days=31),
            retrieval_count=2,
            last_retrieved_at=_NOW - timedelta(days=1),
        )
        stale = await env.memory(
            "Lange her", retrieval_count=1, last_retrieved_at=_NOW - timedelta(days=91)
        )
        external = await env.memory("Aus dem Web", origin="external_content")
        ed = env.as_editor

        assert await _ids(env, ed, held=True) == {held_inferred, held_instruction}
        assert not_held in await _ids(env, ed, held=False)
        assert held_inferred not in await _ids(env, ed, held=False)
        assert await _ids(env, ed, health=MemoryHealth.unconfirmed) == {unconfirmed}
        assert await _ids(env, ed, health=MemoryHealth.expiring_soon) == {expiring}
        assert await _ids(env, ed, health=MemoryHealth.never_delivered) == {never}
        assert await _ids(env, ed, health=MemoryHealth.stale_delivery) == {stale}
        assert await _ids(env, ed, health=MemoryHealth.external_or_inferred) == {
            held_inferred,
            external,
        }

        counts = await env.service.count_workspace_memories(
            ed, MemoryFilter(health=MemoryHealth.unconfirmed), [MemoryCountGroup.health]
        )
        assert counts.total == 1
        # Facette health: ohne den eigenen Filter, alle Werte, auch 0 nicht weggelassen.
        assert counts.groups[MemoryCountGroup.health] == {
            "unconfirmed": 1,
            "expiring_soon": 1,
            "never_delivered": 1,
            "stale_delivery": 1,
            "external_or_inferred": 2,
        }
        empty = await env.service.count_workspace_memories(
            ed, MemoryFilter(q="gibt es nicht"), [MemoryCountGroup.health]
        )
        assert empty.groups[MemoryCountGroup.health] == {h.value: 0 for h in MemoryHealth}

    _run(case)


def test_facets_ignore_their_own_filter_but_keep_the_others() -> None:
    async def case(env: Env) -> None:
        await env.memory("A1")
        await env.memory("A2", origin="inferred")
        await env.memory("B1", agent=env.other_agent)
        await env.memory("B2", agent=env.other_agent, status="pending")
        counts = await env.service.count_workspace_memories(
            env.as_editor,
            MemoryFilter(agent_id=env.agent, status=MemoryStatus.active),
            [MemoryCountGroup.agent, MemoryCountGroup.status, MemoryCountGroup.origin],
        )
        assert counts.total == 2
        # agent: ohne agent-Filter, aber mit status=active.
        assert counts.groups[MemoryCountGroup.agent] == {str(env.agent): 2, str(env.other_agent): 1}
        # status: ohne status-Filter, aber mit agent.
        assert counts.groups[MemoryCountGroup.status] == {"active": 2}
        assert counts.groups[MemoryCountGroup.origin] == {"inferred": 1, "user_stated": 1}

    _run(case)


# ------------------------------------------------------------------- Seiten


def test_keyset_pages_are_deterministic_without_gaps_or_duplicates() -> None:
    async def case(env: Env) -> None:
        # Gleiches created_at fuer mehrere Zeilen: nur der id-Tiebreak trennt sie.
        same = _NOW - timedelta(hours=1)
        ids = [await env.memory(f"Fakt {i}", created_at=same) for i in range(5)]
        ids += [
            await env.memory(f"Spaeter {i}", created_at=_NOW - timedelta(minutes=i))
            for i in range(4)
        ]
        ed = env.as_editor

        for sort in MemoryListSort:
            seen: list[UUID] = []
            cursor = None
            pages = 0
            while True:
                page = await env.service.list_workspace_memories(
                    ed, MemoryFilter(), sort=sort, limit=2, cursor=cursor
                )
                pages += 1
                seen += [m.id for m in page.items]
                if page.next_cursor is None:
                    break
                cursor = decode_cursor(page.next_cursor)
                assert cursor is not None
            assert pages == 5
            assert len(seen) == len(set(seen)) == len(ids)
            full = await env.service.list_workspace_memories(
                ed, MemoryFilter(), sort=sort, limit=MEMORY_LIST_LIMIT_MAX
            )
            assert [m.id for m in full.items] == seen
            keys = [(m.created_at, m.id) for m in full.items]
            assert keys == sorted(keys, reverse=sort == MemoryListSort.newest)

    _run(case)


def test_limit_is_capped_at_fifty() -> None:
    async def case(env: Env) -> None:
        for i in range(MEMORY_LIST_LIMIT_MAX + 1):
            await env.memory(f"Fakt {i}")
        page = await env.service.list_workspace_memories(env.as_editor, MemoryFilter(), limit=500)
        assert len(page.items) == MEMORY_LIST_LIMIT_MAX
        assert page.next_cursor is not None
        last = await env.service.list_workspace_memories(
            env.as_editor, MemoryFilter(), cursor=decode_cursor(page.next_cursor)
        )
        assert len(last.items) == 1 and last.next_cursor is None

    _run(case)


# ------------------------------------------- Mehrfachwerte und Ausschluss (§6.2)


def test_multi_values_or_within_and_between_and_exclude_status() -> None:
    async def case(env: Env) -> None:
        active = await env.memory("Aktiv", origin="inferred")
        pending = await env.memory("Offen", status="pending", kind="agent_note")
        rejected = await env.memory("Abgelehnt", status="rejected")
        expired = await env.memory("Abgelaufen", status="expired", origin="external_content")
        lesson = await env.memory("Lernvorschlag", status="pending", kind="lesson")
        ed = env.as_editor

        # ODER innerhalb eines Feldes (Werte als Text, wie sie die API annimmt).
        assert await _ids(env, ed, status=["active", "expired"]) == {active, expired}
        assert await _ids(env, ed, kind=["agent_note", "lesson"]) == {pending, lesson}
        assert await _ids(env, ed, origin=["inferred", "external_content"]) == {active, expired}
        # UND zwischen den Feldern.
        assert await _ids(env, ed, status=["active", "expired"], origin=["external_content"]) == {
            expired
        }
        # Ein Einzelwert wirkt wie bisher (Bestand: Batch-Body des Web-Clients).
        assert await _ids(env, ed, status=MemoryStatus.rejected) == {rejected}
        # Standardansicht §6.2: alle Status ausser „Abgelehnt“ — samt Lernvorschlag.
        assert await _ids(env, ed, exclude_status=["rejected"]) == {
            active,
            pending,
            expired,
            lesson,
        }
        assert await _ids(env, ed, exclude_status=["rejected", "pending"]) == {active, expired}
        # Auswahl und Ausschluss zugleich: der Ausschluss gewinnt.
        assert await _ids(env, ed, status=["active", "rejected"], exclude_status="rejected") == {
            active
        }
        # Warteschlangen-Regel auch in der Mehrfachauswahl: `pending` ohne
        # `lesson` unter den Arten laesst Lernvorschlaege weg ...
        assert await _ids(env, ed, status=["pending", "active"]) == {pending, active}
        # ... mit `lesson` unter den Arten gehoeren sie dazu.
        assert await _ids(env, ed, status=["pending"], kind=["lesson", "agent_note"]) == {
            pending,
            lesson,
        }

    _run(case)


def test_status_facet_ignores_selection_and_exclusion() -> None:
    async def case(env: Env) -> None:
        await env.memory("Aktiv")
        await env.memory("Offen", status="pending")
        await env.memory("Abgelehnt", status="rejected")
        await env.memory("Abgelehnt 2", status="rejected", origin="inferred")
        counts = await env.service.count_workspace_memories(
            env.as_editor,
            MemoryFilter(exclude_status=[MemoryStatus.rejected], origin=[MemoryOrigin.user_stated]),
            [MemoryCountGroup.status, MemoryCountGroup.origin],
        )
        assert counts.total == 2
        # Der Haken „Abgelehnt“ bekommt seine Zahl, obwohl er ausgeschlossen ist.
        assert counts.groups[MemoryCountGroup.status] == {
            "active": 1,
            "pending": 1,
            "rejected": 1,
        }
        # Andere Facetten behalten den Ausschluss.
        assert counts.groups[MemoryCountGroup.origin] == {"user_stated": 2}

    _run(case)


# Filter, fuer die Liste, Zaehler und Stapel-Auswahl dieselbe Menge meinen muessen.
_SAME_SET_FILTERS: tuple[dict[str, Any], ...] = (
    {"exclude_status": [MemoryStatus.rejected]},
    {"status": [MemoryStatus.pending, MemoryStatus.active]},
    {"status": [MemoryStatus.pending], "kind": [MemoryKind.lesson, MemoryKind.user_fact]},
    {"kind": [MemoryKind.agent_note, MemoryKind.lesson], "exclude_status": [MemoryStatus.expired]},
    {"origin": [MemoryOrigin.inferred, MemoryOrigin.external_content]},
    {
        "status": [MemoryStatus.active, MemoryStatus.rejected],
        "exclude_status": [MemoryStatus.rejected],
        "origin": [MemoryOrigin.user_stated, MemoryOrigin.inferred],
    },
)


def test_list_counts_and_batch_filter_select_the_same_set() -> None:
    async def case(env: Env) -> None:
        seeds = (
            ("A", "active", "user_fact", "user_stated"),
            ("B", "active", "agent_note", "inferred"),
            ("C", "pending", "user_fact", "user_stated"),
            ("D", "pending", "lesson", "inferred"),
            ("E", "rejected", "user_fact", "external_content"),
            ("F", "expired", "agent_note", "user_stated"),
            ("G", "pending", "agent_note", "external_content"),
        )
        for fact, status, kind, origin in seeds:
            await env.memory(fact, status=status, kind=kind, origin=origin)
        await env.memory("Eigenes", subject=env.editor, status="rejected")
        await env.memory("Fremdes", subject=env.viewer, status="pending")
        ed = env.as_editor

        for raw in _SAME_SET_FILTERS:
            filters = MemoryFilter(**raw)
            listed = await _ids(env, ed, **raw)
            assert listed, f"Probe ohne Treffer sagt nichts: {raw}"
            counts = await env.service.count_workspace_memories(ed, filters)
            assert counts.total == len(listed), raw
            # Stapel per Filter: die Zahl der Auswahl steht in der 409 ...
            with pytest.raises(ApiError) as exc:
                await env.service.batch(
                    ed,
                    MemoryBatchRequest(
                        action=MemoryBatchAction.confirm,
                        filter=filters,
                        expected_count=len(listed) + 1,
                    ),
                )
            assert exc.value.reason == "memory_batch_count_mismatch", raw
            assert exc.value.params == {"count": len(listed)}, raw
            # ... und mit passender Zahl laeuft der Stapel ueber genau diese IDs.
            # `confirm` aendert nur `active`-Eintraege; die uebrigen melden einen
            # Fehler je Eintrag, die Menge der IDs bleibt dieselbe.
            result = await env.service.batch(
                ed,
                MemoryBatchRequest(
                    action=MemoryBatchAction.confirm,
                    filter=filters,
                    expected_count=len(listed),
                ),
            )
            assert {r.id for r in result.results} == listed, raw

    _run(case)


def test_filter_validation() -> None:
    assert MemoryFilter(status=MemoryStatus.active).status == [MemoryStatus.active]
    assert MemoryFilter(
        kind=[MemoryKind.lesson, MemoryKind.lesson, MemoryKind.agent_note]
    ).kinds == [MemoryKind.lesson, MemoryKind.agent_note]
    # Leere Liste heisst „kein Filter“.
    assert MemoryFilter(origin=[], exclude_status=[]).model_dump(exclude_none=True) == {}
    assert MemoryFilter.model_validate({"exclude_status": "rejected"}).excluded_statuses == [
        MemoryStatus.rejected
    ]
    with pytest.raises(ValidationError):
        MemoryFilter.model_validate({"status": ["active", "gibt-es-nicht"]})
    with pytest.raises(ValidationError, match="Zeitzone"):
        MemoryFilter(created_after=datetime(2026, 10, 1))  # noqa: DTZ001
    with pytest.raises(ValidationError):
        MemoryFilter(q="")
    with pytest.raises(ValidationError):
        MemoryFilter(unknown="x")  # type: ignore[call-arg]
