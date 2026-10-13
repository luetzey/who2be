"""Dossier eines Agenten fuer die Vorbereitung eines Gespraechs (ADR-0053 6.6, Paket E1).

`GET /agents/{agent_id}/dossier` — Rolle `editor` / Capability `case_triage`
(6.6; dieselbe Regel wie die Triage, `require_triage_right`). Ein fremder
oder unbekannter Agent endet mit `agent_not_found` (404), sichtbar und
unsichtbar gleich.

Bloecke (6.6: „offene Faelle, Signale und Fallrate je Version,
Zugriffslog-Zusammenfassung, fruehere Massnahmen mit Einstufung“; N2 a:
Generationen):

- **open_cases**: Zaehler je offenem Status (open, triaged, in_progress,
  reopened) plus die schwersten/juengsten Faelle, Texte gekuerzt.
- **elements**: Bausteine mit ihren juengsten Versionen (die aktive immer
  dabei). Je Version Rohzahlen (QE8 a): Nutzungen nur `source='server'`,
  Ergebnisse nur `source='agent_report'` (3.4, D3), Signale aus
  `agent_feedback`, Faelle im Zeitfenster der Version — dieselbe Naeherung
  wie die Nachschau (`session_repository.follow_up_figures`), weil
  `agent_case` keine Version kennt. `insufficient` mit derselben Schwelle wie
  die Nachschau (`FOLLOW_UP_MIN_USES`, eine Quelle).
- **access**: Summen des Zugriffslogs der letzten
  `DOSSIER_ACCESS_WINDOW_DAYS` Tage, ohne Einzelzeilen und ohne `ref_id`.
- **measures**: die juengsten Massnahmen des Agenten mit Zustand und
  juengster Einstufung.
- **generations**: Aktivierungen der Bausteine, neueste zuerst, mit Cursor.

Groesse: Die Antwort geht auch ueber MCP an Modelle (W-E1). Jede Liste hat
einen festen Deckel aus `who2be_models.session` (`DOSSIER_*`), Freitexte
werden auf `DOSSIER_TEXT_MAX_LENGTH` gekuerzt.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import ClassVar, cast
from uuid import UUID

from fastapi import status

from who2be_api.core.errors import ApiError
from who2be_api.core.security import WorkspaceContext
from who2be_api.repositories.dossier_repository import (
    ActivationRow,
    CaseWindow,
    DossierRepository,
    ElementRef,
    MeasureRow,
    VersionRow,
)
from who2be_api.services.case_service import require_triage_right
from who2be_api.services.measure_service import FOLLOW_UP_MIN_USES
from who2be_models import (
    CaseSeverity,
    CaseStatus,
    EntityType,
    MeasureEventKind,
    MeasureTarget,
    MeasureVerdict,
    encode_cursor,
    measure_state_for,
)
from who2be_models.session import (
    DOSSIER_ACCESS_WINDOW_DAYS,
    DOSSIER_ELEMENTS_LIMIT,
    DOSSIER_GENERATIONS_LIMIT,
    DOSSIER_MEASURES_LIMIT,
    DOSSIER_OPEN_CASES_LIMIT,
    DOSSIER_TEXT_MAX_LENGTH,
    DOSSIER_VERSIONS_PER_ELEMENT,
    Dossier,
    DossierAccess,
    DossierAccessRow,
    DossierCase,
    DossierElement,
    DossierGeneration,
    DossierMeasure,
    DossierOpenCases,
    DossierVersion,
)

# Offene Status in fester Reihenfolge; jeder erscheint im Zaehler, auch mit 0.
OPEN_CASE_STATUSES: tuple[CaseStatus, ...] = (
    CaseStatus.open,
    CaseStatus.triaged,
    CaseStatus.in_progress,
    CaseStatus.reopened,
)

# Platzhalter fuer ein geloeschtes Element (Name nicht mehr lesbar).
_DELETED_NAME = "—"


def _agent_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Agent nicht gefunden.",
        reason="agent_not_found",
    )


def shorten(text: str, limit: int = DOSSIER_TEXT_MAX_LENGTH) -> str:
    """Kuerzt auf `limit` Zeichen inklusive „…“."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _now_utc() -> datetime:
    return datetime.now(UTC)


def pick_versions(rows: list[VersionRow], per_element: int) -> list[VersionRow]:
    """Die aktive Version plus die juengsten bis `per_element`, neueste zuerst."""
    newest = sorted(rows, key=lambda r: r.version, reverse=True)
    active = [r for r in newest if r.active][:1]
    rest = [r for r in newest if r not in active]
    picked = active + rest[: max(per_element - len(active), 0)]
    return sorted(picked, key=lambda r: r.version, reverse=True)


def version_windows(
    activations: list[ActivationRow],
) -> dict[tuple[str, UUID, int], tuple[datetime, datetime | None]]:
    """Je (Art, ID, Version): juengste Aktivierung bis zur naechsten einer anderen Version.

    `activations` aelteste zuerst. Ohne Folge-Aktivierung ist das Fenster offen.
    """
    by_element: dict[tuple[str, UUID], list[ActivationRow]] = defaultdict(list)
    for row in activations:
        by_element[(row.entity_type, row.entity_id)].append(row)
    windows: dict[tuple[str, UUID, int], tuple[datetime, datetime | None]] = {}
    for (kind, entity_id), rows in by_element.items():
        for index, row in enumerate(rows):
            until = next(
                (later.changed_at for later in rows[index + 1 :] if later.version != row.version),
                None,
            )
            # Spaetere Aktivierungen derselben Version ueberschreiben: es gilt die juengste.
            windows[(kind, entity_id, row.version)] = (row.changed_at, until)
    return windows


def _measure(row: MeasureRow) -> DossierMeasure:
    last_event = MeasureEventKind(row.last_event) if row.last_event is not None else None
    last_verdict = MeasureVerdict(row.last_verdict) if row.last_verdict is not None else None
    return DossierMeasure(
        id=row.id,
        session_id=row.session_id,
        target=MeasureTarget(row.target),
        entity_id=row.entity_id,
        change_summary=shorten(row.change_summary),
        state=measure_state_for(last_event, last_verdict),
        verdict=MeasureVerdict(row.reviewed_verdict) if row.reviewed_verdict else None,
        reviewed_at=row.reviewed_at,
        follow_up_at=row.follow_up_at,
        case_count=row.case_count,
        created_at=row.created_at,
    )


class DossierService:
    """Stellt das Dossier zusammen; liest nur."""

    __test__: ClassVar[bool] = False

    def __init__(self, repo: DossierRepository, *, now: Callable[[], datetime] = _now_utc) -> None:
        self._repo = repo
        self._now = now

    async def dossier(
        self,
        ctx: WorkspaceContext,
        agent_id: UUID,
        *,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> Dossier:
        """`GET /agents/{agent_id}/dossier` (6.6)."""
        require_triage_right(ctx)
        ws = ctx.workspace_id
        name = await self._repo.agent_name(ws, agent_id)
        if name is None:
            raise _agent_not_found()
        now = self._now()

        elements = await self._repo.elements(ws, agent_id)
        names = {(e.entity_type, e.entity_id): e.name for e in elements}
        all_pairs = [(e.entity_type, e.entity_id) for e in elements]
        shown = elements[:DOSSIER_ELEMENTS_LIMIT]

        generations, next_cursor = await self._generations(ws, agent_id, all_pairs, names, cursor)
        measures, measures_total = await self._repo.measures(ws, agent_id, DOSSIER_MEASURES_LIMIT)
        since = (now - timedelta(days=DOSSIER_ACCESS_WINDOW_DAYS)).date()
        access_rows = await self._repo.access_summary(ws, agent_id, since)

        return Dossier(
            agent_id=agent_id,
            agent_name=name,
            generated_at=now,
            min_uses=FOLLOW_UP_MIN_USES,
            open_cases=await self._open_cases(ws, agent_id),
            elements=await self._elements(ws, shown),
            elements_total=len(elements),
            access=DossierAccess(
                since=since,
                window_days=DOSSIER_ACCESS_WINDOW_DAYS,
                total=sum(r.entries for r in access_rows),
                rows=[
                    DossierAccessRow(
                        ref_kind=r.ref_kind,
                        operation=r.operation,
                        sensitivity=r.sensitivity,
                        entries=r.entries,
                        refs=r.refs,
                        last_on=r.last_on,
                    )
                    for r in access_rows
                ],
            ),
            measures=[_measure(m) for m in measures],
            measures_total=measures_total,
            generations=generations,
            generations_next_cursor=next_cursor,
        )

    async def _open_cases(self, ws: UUID, agent_id: UUID) -> DossierOpenCases:
        raw = await self._repo.open_case_counts(ws, agent_id)
        counts = {s: raw.get(s.value, 0) for s in OPEN_CASE_STATUSES}
        rows = await self._repo.open_cases(ws, agent_id, DOSSIER_OPEN_CASES_LIMIT)
        return DossierOpenCases(
            counts=counts,
            total=sum(counts.values()),
            items=[
                DossierCase(
                    id=r.id,
                    status=CaseStatus(r.status),
                    severity=CaseSeverity(r.severity),
                    situation=shorten(r.situation),
                    expected_behavior=shorten(r.expected_behavior),
                    created_at=r.created_at,
                )
                for r in rows
            ],
        )

    async def _elements(self, ws: UUID, shown: list[ElementRef]) -> list[DossierElement]:
        pairs = [(e.entity_type, e.entity_id) for e in shown]
        if not pairs:
            return []
        by_element: dict[tuple[str, UUID], list[VersionRow]] = defaultdict(list)
        for row in await self._repo.versions(ws, pairs):
            by_element[(row.entity_type, row.entity_id)].append(row)
        picked = {
            key: pick_versions(rows, DOSSIER_VERSIONS_PER_ELEMENT)
            for key, rows in by_element.items()
        }
        windows = version_windows(await self._repo.activations(ws, pairs))

        uses: dict[tuple[str, UUID, int], int] = defaultdict(int)
        outcomes: dict[tuple[str, UUID, int], dict[str, int]] = defaultdict(dict)
        for u in await self._repo.usage(ws, pairs):
            key = (u.entity_type, u.entity_id, u.version)
            if u.source == "server":
                uses[key] += u.count
            elif u.outcome is not None:
                outcomes[key][u.outcome] = outcomes[key].get(u.outcome, 0) + u.count
        signals: dict[tuple[str, UUID, int], dict[str, int]] = defaultdict(dict)
        for s in await self._repo.signals(ws, pairs):
            signals[(s.entity_type, s.entity_id, s.version)][s.signal] = s.count

        # Fallzaehler nur fuer die gezeigten Versionen mit Aktivierungsdatum.
        keys = [
            (kind, entity_id, v.version)
            for (kind, entity_id), versions in picked.items()
            for v in versions
            if (kind, entity_id, v.version) in windows
        ]
        counts = await self._repo.case_counts(
            ws,
            [CaseWindow(k[0], k[1], windows[k][0], windows[k][1]) for k in keys],
        )
        cases = dict(zip(keys, counts, strict=True))

        result: list[DossierElement] = []
        for element in shown:
            key2 = (element.entity_type, element.entity_id)
            versions = []
            for v in picked.get(key2, []):
                key3 = (element.entity_type, element.entity_id, v.version)
                window = windows.get(key3)
                versions.append(
                    DossierVersion(
                        version=v.version,
                        active=v.active,
                        activated_at=window[0] if window is not None else None,
                        uses=uses.get(key3, 0),
                        outcomes=outcomes.get(key3, {}),
                        signals=signals.get(key3, {}),
                        cases=cases.get(key3),
                        insufficient=uses.get(key3, 0) < FOLLOW_UP_MIN_USES,
                    )
                )
            result.append(
                DossierElement(
                    entity_type=cast(EntityType, element.entity_type),
                    entity_id=element.entity_id,
                    name=element.name or _DELETED_NAME,
                    versions=versions,
                )
            )
        return result

    async def _generations(
        self,
        ws: UUID,
        agent_id: UUID,
        pairs: list[tuple[str, UUID]],
        names: dict[tuple[str, UUID], str | None],
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[DossierGeneration], str | None]:
        rows = await self._repo.generations(
            ws, pairs, limit=DOSSIER_GENERATIONS_LIMIT + 1, cursor=cursor
        )
        next_cursor = None
        if len(rows) > DOSSIER_GENERATIONS_LIMIT:
            rows = rows[:DOSSIER_GENERATIONS_LIMIT]
            next_cursor = encode_cursor(rows[-1].activated_at, rows[-1].id)
        if not rows:
            return [], None

        on_page = list(dict.fromkeys((r.entity_type, r.entity_id) for r in rows))
        linked: dict[UUID, list[tuple[UUID, str | None, datetime | None]]] = defaultdict(list)
        for gm in await self._repo.generation_measures(ws, on_page):
            linked[gm.activation_id].append((gm.measure_id, gm.verdict, gm.reviewed_at))
        shared = {
            pair: await self._repo.shared_agent_count(ws, pair[0], pair[1], agent_id)
            for pair in on_page
        }

        result: list[DossierGeneration] = []
        for row in rows:
            measures = linked.get(row.id, [])
            reviewed = [(at, verdict) for _, verdict, at in measures if verdict and at]
            verdict = max(reviewed)[1] if reviewed else None
            key = (row.entity_type, row.entity_id)
            result.append(
                DossierGeneration(
                    entity_type=cast(EntityType, row.entity_type),
                    entity_id=row.entity_id,
                    name=names.get(key) or _DELETED_NAME,
                    from_version=row.from_version,
                    to_version=row.to_version,
                    activated_at=row.activated_at,
                    measure_ids=[m for m, _, _ in measures],
                    verdict=MeasureVerdict(verdict) if verdict else None,
                    shared_agent_count=shared[key],
                )
            )
        return result, next_cursor
