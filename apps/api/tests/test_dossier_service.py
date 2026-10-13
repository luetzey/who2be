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

Ohne DB greift der zentrale Skip; mit `WHO2BE_REQUIRE_DB=1` schlaegt er hart fehl.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from test_measure_service import _MWorld, _run  # type: ignore[import-not-found]
from test_session_service import _code, _reason  # type: ignore[import-not-found]

from who2be_api.core.errors import ApiError, ApiGateError
from who2be_api.repositories.dossier_repository import PgDossierRepository
from who2be_api.services import dossier_service
from who2be_api.services.dossier_service import DossierService, shorten
from who2be_api.services.measure_service import FOLLOW_UP_MIN_USES
from who2be_models import CaseCreate, CaseStatus, MeasureVerdict, decode_cursor
from who2be_models.session import DOSSIER_TEXT_MAX_LENGTH, Dossier

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


def test_shorten_keeps_short_text() -> None:
    assert shorten("kurz") == "kurz"
    assert shorten("abcdef", 4) == "abc…"
