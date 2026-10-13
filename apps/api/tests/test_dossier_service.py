"""Service-Tests fuer das Dossier eines Agenten (ADR-0053 6.6, Paket E1).

Echte DB unter der Laufzeitrolle `who2be_app` (RLS aktiv), Fixtures aus
`test_measure_service`/`test_session_service`. Belegt:

- **Rechte:** viewer, Agent ohne `case_triage` und agent-gebundener Aufruf
  ohne Policy bekommen 403; editor und Builder mit `case_triage` lesen.
  Mutationsprobe: ohne `require_triage_right` in `DossierService.dossier`
  wird `test_rights_and_not_found` rot.
- **Sichtbarkeit:** unbekannter Agent und Agent aus Workspace B -> 404
  `agent_not_found`.
- **Offene Faelle:** Zaehler je offenem Status (auch 0), `dismissed` zaehlt
  nicht, Texte gekuerzt.
- **Versionen:** Nutzungen nur `source='server'`, Ergebnisse nur
  `source='agent_report'`, Signale aus `agent_feedback`, Faelle im Zeitfenster
  der Version, `insufficient` gegen `min_uses`.
- **Zugriffe:** Summen ohne `ref_id`, ausserhalb des Fensters nicht gezaehlt.
- **Massnahmen und Generationen:** Einstufung an Massnahme und Generation;
  direkte Aktivierung ohne Massnahme; `shared_agent_count`; Cursor.
- **Agent-Trennung:** Massnahmen und Zugriffslog eines anderen Agenten
  erscheinen nicht.
- **Groesse:** jeder Deckel (`DOSSIER_*`) greift, `*_total` bleibt vollstaendig.
- **Abfragezahl:** konstant bei mehr Daten; nur `shared_agent_count` je
  Baustein der Generationen-Seite.

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import asyncpg
import pytest
from test_feedback_session_schema import _measure, _protocol  # type: ignore[import-not-found]
from test_measure_service import _MWorld, _run  # type: ignore[import-not-found]
from test_session_service import _code, _reason  # type: ignore[import-not-found]

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.repositories.dossier_repository import PgDossierRepository
from who2be_api.repositories.test_case_repository import _AFFECTED_SQL
from who2be_api.services import dossier_service
from who2be_api.services.dossier_service import DossierService, shorten
from who2be_api.services.measure_service import FOLLOW_UP_MIN_USES
from who2be_models import CaseCreate, CaseStatus, MeasureVerdict, decode_cursor
from who2be_models.session import DOSSIER_GENERATIONS_LIMIT, DOSSIER_TEXT_MAX_LENGTH, Dossier

pytestmark = pytest.mark.integration


def _service(w: Any) -> DossierService:
    return DossierService(PgDossierRepository(w.pool))


async def _assign_persona(w: Any, agent_id: UUID, persona_id: UUID) -> None:
    await w.owner.execute("UPDATE agent SET persona_id = $1 WHERE id = $2", persona_id, agent_id)


async def _usage(
    w: Any, persona_id: UUID, version: int, n: int, *, source: str, outcome: str | None = None
) -> None:
    for _ in range(n):
        await w.owner.execute(
            "INSERT INTO usage_event (workspace_id, agent_id, entity_type, entity_id, version, "
            " outcome, source) VALUES ($1, $2, 'persona', $3, $4, $5, $6)",
            w.seed.ws_a,
            w.seed.agent_a,
            persona_id,
            version,
            outcome,
            source,
        )


async def _version(dossier: Dossier, persona_id: UUID, number: int) -> Any:
    element = next(e for e in dossier.elements if e.entity_id == persona_id)
    return next(v for v in element.versions if v.version == number)


def test_rights_and_not_found() -> None:
    async def body(w: _MWorld) -> None:
        svc = _service(w)
        for ctx in (w.viewer, w.agent, w.no_policy):
            with pytest.raises((ApiError, ApiGateError)) as exc:
                await svc.dossier(ctx, w.seed.agent_a)
            assert _code(exc) == 403
        for ctx in (w.editor, w.builder):
            dossier = await svc.dossier(ctx, w.seed.agent_a)
            assert dossier.agent_id == w.seed.agent_a
            assert dossier.agent_name == "agent_a"
            assert dossier.min_uses == FOLLOW_UP_MIN_USES
        for unknown in (uuid4(), w.seed.agent_b):
            with pytest.raises(ApiError) as missing:
                await svc.dossier(w.editor, unknown)
            assert _code(missing) == 404
            assert _reason(missing) == "agent_not_found"

    _run(body)


def test_open_cases_counts_and_shortened_items() -> None:
    async def body(w: _MWorld) -> None:
        await w.case_in(CaseStatus.triaged)
        await w.case_in(CaseStatus.reopened)
        await w.case_in(CaseStatus.dismissed)
        long_case = await w.case_svc.report_case(
            w.editor,
            CaseCreate(
                agent_id=w.seed.agent_a,
                situation="x" * 1_000,
                behavior="b",
                expected_behavior="e",
            ),
        )
        # Fall eines anderen Agenten zaehlt nicht.
        await w.case(w.seed.agent_a2)

        dossier = await _service(w).dossier(w.editor, w.seed.agent_a)
        open_cases = dossier.open_cases
        assert open_cases.counts == {
            CaseStatus.open: 1,
            CaseStatus.triaged: 1,
            CaseStatus.in_progress: 0,
            CaseStatus.reopened: 1,
        }
        assert open_cases.total == 3
        assert len(open_cases.items) == 3
        assert all(item.status is not CaseStatus.dismissed for item in open_cases.items)
        long_item = next(i for i in open_cases.items if i.id == long_case.id)
        assert len(long_item.situation) == DOSSIER_TEXT_MAX_LENGTH
        assert long_item.situation.endswith("…")

    _run(body)


def test_versions_access_measures_and_generations(monkeypatch: pytest.MonkeyPatch) -> None:
    async def body(w: _MWorld) -> None:
        persona_id, (_, v2, _) = await w.persona(versions=3)

        # Generation 1 ueber eine Massnahme: v2 verknuepft und aktiviert.
        measure_id, _ = await w.measure(entity_id=persona_id)
        await w.msvc.link_draft(w.editor, measure_id, "persona", v2)
        await w.to_review(persona_id, 2)
        await w.activate_version(persona_id, 2)
        await w.msvc.review(w.editor, measure_id, MeasureVerdict.effective)
        # Generation 2 direkt, ohne Massnahme.
        await w.to_review(persona_id, 3)
        await w.activate_version(persona_id, 3)
        # Zuordnung erst jetzt: sonst verlangte die Aktivierung den Pruefbericht
        # der Pruefaelle von agent_a (6.3). `shared_agent_count` liest den heutigen Stand.
        await _assign_persona(w, w.seed.agent_a, persona_id)
        await _assign_persona(w, w.seed.agent_a2, persona_id)

        # Nutzung: nur `server` zaehlt als Nutzung, `agent_report` als Ergebnis.
        await _usage(w, persona_id, 3, 4, source="server")
        await _usage(w, persona_id, 3, 2, source="agent_report", outcome="applied")
        await _usage(w, persona_id, 2, FOLLOW_UP_MIN_USES, source="server")
        await w.owner.execute(
            "INSERT INTO agent_feedback (workspace_id, agent_id, entity_type, entity_id, "
            " version, signal) VALUES ($1, $2, 'persona', $3, 3, 'unclear')",
            w.seed.ws_a,
            w.seed.agent_a,
            persona_id,
        )
        # Fall mit Zuordnung zur Persona, waehrend v3 aktiv ist.
        case_id = await w.case()
        await w.owner.execute(
            "INSERT INTO agent_case_element (workspace_id, case_id, target, entity_id, "
            " assigned_by_kind, assigned_by) VALUES ($1, $2, 'persona', $3, 'human', $4)",
            w.seed.ws_a,
            case_id,
            persona_id,
            w.seed.user,
        )
        # Zugriffslog: zwei Eintraege im Fenster, einer davor.
        today = datetime.now(UTC).date()
        for ref_id, day in (("r1", today), ("r2", today), ("r3", today - timedelta(days=400))):
            await w.owner.execute(
                "INSERT INTO agent_access_log (workspace_id, agent_id, ref_kind, ref_id, "
                " operation, sensitivity_at_access, access_date) "
                "VALUES ($1, $2, 'artifact', $3, 'read', 'general', $4)",
                w.seed.ws_a,
                w.seed.agent_a,
                ref_id,
                day,
            )

        svc = _service(w)
        dossier = await svc.dossier(w.builder, w.seed.agent_a)

        v3 = await _version(dossier, persona_id, 3)
        assert (v3.active, v3.uses, v3.outcomes, v3.signals) == (
            True,
            4,
            {"applied": 2},
            {"unclear": 1},
        )
        assert v3.cases == 1
        assert v3.insufficient is True
        old = await _version(dossier, persona_id, 2)
        assert (old.active, old.uses, old.insufficient) == (False, FOLLOW_UP_MIN_USES, False)
        assert old.cases == 0

        assert dossier.access.total == 2
        assert [(r.ref_kind, r.operation, r.entries, r.refs) for r in dossier.access.rows] == [
            ("artifact", "read", 2, 2)
        ]
        assert "r1" not in dossier.model_dump_json()

        assert dossier.measures_total == 1
        measure = dossier.measures[0]
        assert measure.id == measure_id
        assert measure.verdict is MeasureVerdict.effective
        assert measure.state.value == "effective"

        newest, first = dossier.generations
        assert (newest.from_version, newest.to_version) == (2, 3)
        assert newest.measure_ids == []
        assert newest.verdict is None
        assert (first.from_version, first.to_version) == (None, 2)
        assert first.measure_ids == [measure_id]
        assert first.verdict is MeasureVerdict.effective
        # agent_a2 erreicht die Persona ebenfalls.
        assert newest.shared_agent_count == 1
        assert dossier.generations_next_cursor is None

        # Cursor: eine Generation je Seite.
        monkeypatch.setattr(dossier_service, "DOSSIER_GENERATIONS_LIMIT", 1)
        page1 = await svc.dossier(w.editor, w.seed.agent_a)
        assert [g.to_version for g in page1.generations] == [3]
        assert page1.generations_next_cursor is not None
        cursor = decode_cursor(page1.generations_next_cursor)
        page2 = await svc.dossier(w.editor, w.seed.agent_a, cursor=cursor)
        assert [g.to_version for g in page2.generations] == [2]
        assert page2.generations_next_cursor is None

    _run(body)


async def _access(w: Any, agent_id: UUID, ref_ids: list[str]) -> None:
    for ref_id in ref_ids:
        await w.owner.execute(
            "INSERT INTO agent_access_log (workspace_id, agent_id, ref_kind, ref_id, "
            " operation, sensitivity_at_access, access_date) "
            "VALUES ($1, $2, 'artifact', $3, 'read', 'general', $4)",
            w.seed.ws_a,
            agent_id,
            ref_id,
            datetime.now(UTC).date(),
        )


async def _measure_with(
    w: Any, entity_id: UUID, *, agent_id: UUID | None = None, change_summary: str | None = None
) -> UUID:
    """Massnahme an einer Persona ueber ein eingereichtes Protokoll (beliebiger Agent)."""
    agent = agent_id or w.seed.agent_a
    case_id = await w.case(agent)
    test_case = await w.test_case(agent)
    overrides: dict[str, object] = {"target": "persona", "entity_id": entity_id}
    if change_summary is not None:
        overrides["change_summary"] = change_summary
    result = await w.svc.submit_protocol(
        w.editor, _protocol(agent, [case_id], [_measure([case_id], test_case, **overrides)])
    )
    measure_id: UUID = result.detail.measures[0].id
    return measure_id


def test_other_agents_measures_and_access_are_excluded() -> None:
    """Massnahmen und Zugriffslog eines anderen Agenten erscheinen nicht (M5/M6)."""

    async def body(w: _MWorld) -> None:
        persona_id, _ = await w.persona(versions=2)
        own = await _measure_with(w, persona_id)
        await _measure_with(w, persona_id, agent_id=w.seed.agent_a2)
        await _measure_with(w, persona_id, agent_id=w.seed.agent_a2)
        await _access(w, w.seed.agent_a, ["own-1"])
        await _access(w, w.seed.agent_a2, ["foreign-1", "foreign-2", "foreign-3"])

        dossier = await _service(w).dossier(w.editor, w.seed.agent_a)
        assert dossier.measures_total == 1
        assert [m.id for m in dossier.measures] == [own]
        assert dossier.access.total == 1
        assert [(r.entries, r.refs) for r in dossier.access.rows] == [(1, 1)]

        # Gegenprobe: das Dossier von agent_a2 sieht genau seine eigenen Zeilen.
        other = await _service(w).dossier(w.editor, w.seed.agent_a2)
        assert other.measures_total == 2
        assert own not in {m.id for m in other.measures}
        assert other.access.total == 3

    _run(body)


def test_size_caps_keep_totals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jeder Deckel greift, `*_total` bleibt vollstaendig (M8 bis M12)."""

    async def body(w: _MWorld) -> None:
        first, _ = await w.persona(versions=3)  # v1 aktiv, v2 inaktiv, v3 Entwurf
        second, _ = await w.persona(versions=1)
        await _measure_with(w, first)
        await _measure_with(w, second, change_summary="y" * 2_000)
        await w.case()  # dritter offener Fall

        svc = _service(w)
        uncapped = await svc.dossier(w.editor, w.seed.agent_a)
        assert uncapped.elements_total == 2
        assert len(uncapped.elements) == 2
        assert uncapped.measures_total == 2
        assert uncapped.open_cases.total == 3
        assert len(uncapped.open_cases.items) == 3
        long_measure = next(m for m in uncapped.measures if m.entity_id == second)
        assert len(long_measure.change_summary) == DOSSIER_TEXT_MAX_LENGTH
        assert long_measure.change_summary.endswith("…")
        uncapped_first = next(e for e in uncapped.elements if e.entity_id == first)
        assert [v.version for v in uncapped_first.versions] == [3, 2, 1]

        # Zwei Versionen je Baustein: die juengste und die aktive (v1) bleibt dabei.
        monkeypatch.setattr(dossier_service, "DOSSIER_VERSIONS_PER_ELEMENT", 2)
        few_versions = await svc.dossier(w.editor, w.seed.agent_a)
        capped_first = next(e for e in few_versions.elements if e.entity_id == first)
        assert [(v.version, v.active) for v in capped_first.versions] == [(3, False), (1, True)]

        monkeypatch.setattr(dossier_service, "DOSSIER_ELEMENTS_LIMIT", 1)
        monkeypatch.setattr(dossier_service, "DOSSIER_OPEN_CASES_LIMIT", 1)
        monkeypatch.setattr(dossier_service, "DOSSIER_MEASURES_LIMIT", 1)
        capped = await svc.dossier(w.editor, w.seed.agent_a)

        assert len(capped.elements) == 1
        assert capped.elements_total == 2
        assert len(capped.open_cases.items) == 1
        assert capped.open_cases.total == 3
        assert len(capped.measures) == 1
        assert capped.measures_total == 2

    _run(body)


class _CountingPool:
    """Zaehlt die Abfragen des Repositories; `_AFFECTED_SQL` (shared_agent_count) getrennt."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self.fixed = 0
        self.shared = 0

    def _count(self, sql: str) -> None:
        if sql in _AFFECTED_SQL.values():
            self.shared += 1
        else:
            self.fixed += 1

    async def fetch(self, sql: str, *args: Any) -> Any:
        self._count(sql)
        return await self._pool.fetch(sql, *args)

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self._count(sql)
        return await self._pool.fetchval(sql, *args)

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self._count(sql)
        return await self._pool.fetchrow(sql, *args)


def test_query_count_does_not_grow_with_data() -> None:
    """Feste Abfragezahl; nur shared_agent_count je Baustein der Seite (N+1-Beleg)."""

    async def body(w: _MWorld) -> None:
        persona_id, _ = await w.persona(versions=3)
        await w.to_review(persona_id, 2)
        await w.activate_version(persona_id, 2)
        await _assign_persona(w, w.seed.agent_a, persona_id)

        async def count() -> tuple[int, int, Dossier]:
            pool = _CountingPool(w.pool)
            svc = DossierService(PgDossierRepository(cast(asyncpg.Pool, pool)))
            dossier = await svc.dossier(w.editor, w.seed.agent_a)
            return pool.fixed, pool.shared, dossier

        fixed_before, shared_before, before = await count()

        # Mehr von allem: Version + Aktivierung, Faelle, Massnahmen, Zugriffe.
        await w.to_review(persona_id, 3)
        await w.activate_version(persona_id, 3)
        for _ in range(3):
            await _measure_with(w, persona_id)
            await w.case()
        await _access(w, w.seed.agent_a, [f"r{i}" for i in range(5)])

        fixed_after, shared_after, after = await count()

        assert len(after.generations) > len(before.generations)
        assert after.measures_total == 3 > before.measures_total
        assert after.open_cases.total > before.open_cases.total
        assert after.access.total == 5
        assert fixed_after == fixed_before
        # shared_agent_count: eine Abfrage je Baustein der Generationen-Seite.
        on_page = {(g.entity_type, g.entity_id) for g in after.generations}
        assert shared_after == shared_before == len(on_page) == 1
        assert shared_after <= DOSSIER_GENERATIONS_LIMIT

    _run(body)


def test_shorten_keeps_short_text() -> None:
    assert shorten("kurz") == "kurz"
    assert shorten("abcdef", 4) == "abc…"
