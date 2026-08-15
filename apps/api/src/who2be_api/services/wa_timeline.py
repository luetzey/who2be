"""Geschaeftslogik der Timeline (Spec N, ADR-0047/0049 — WP15).

Die Timeline ist eine reine LESE-Sicht ueber drei Quellenarten — Artifacts
(`wa_artifact`), KB-Nodes (`kb_node`) und Tabellen-Zeilen (`table:<id>`,
SQLite via TableStore). Der MERGE passiert HIER uebers Datum: die Buckets
sind die VEREINIGUNG aller Quellen — ein Tag mit Notizen, aber ohne
Transaktionen, ist eine volle Scheibe (Spec-Akzeptanz N). Ausgabe
chronologisch, Bucket-Label ISO (``2026-08-01`` bzw. Wochen-/Monatsanfang).
Es wird NICHTS persistiert — insbesondere entsteht aus Gleichzeitigkeit NIE
eine Kante (Spec §10.7); wer eine Korrelation behaupten will, muss den
`co_occurs_with`-Weg mit Fallzahl gehen (Spec O).

`unknown`-Bucket: Elemente mit ``occurred_precision='unknown'`` haben KEIN
verlaessliches Datum — sie landen NIE in einer Datums-Scheibe und werden
FENSTERLOS gesammelt (alle unknown-Elemente der gescope-ten Areas/Nodes,
gedeckelt): ein Fenster-Filter auf einem unzuverlaessigen Datum wuerde
Eintraege willkuerlich verstecken (Spec-Akzeptanz N).

Tabellen-Quellen liefern pro Bucket EIN `TimelineItem(anchor='table:<id>',
kind='table_rows')` + die Zeilenzahl in den counts — KEINE Row-Anker:
SQLite-Zeilen haben keine adressierbaren Anker in der Anker-Sprache
(ADR-0021 kennt ``<artifact_id>[#block]``, ``node:<id>``, ``table:<id>``).

Zugriff (Plan-API-Tabelle WP15): Artifacts/Nodes werden STILL auf den
Lese-Scope gefiltert (`readable_area_ids` bzw. KB-Sichtbarkeit in der
Repo-SQL). Explizit angeforderte `table:<id>`-Quellen verlangen dagegen
read-Grants auf ALLE sources — fehlt einer → 403 `area_forbidden` (bewusste
Plan-Entscheidung: die explizite Quelle still zu verschweigen waere ein
falsches "leeres" Ergebnis); eine im Workspace unbekannte Tabelle bleibt 404
(`TimelineTableNotFound`, uebersetzt der Router).

ARC-3: kein SQL, keine HTTPException — Repos, `core/workarea_scope`,
TableStore (SQLite NUR ueber ihn) und `ApiGateError`/Domain-Exception.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Final
from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import WorkspaceContext
from who2be_api.core.workarea_scope import readable_area_ids
from who2be_api.repositories.timeline_repository import (
    TableTimelineSource,
    TimelineRepository,
)
from who2be_api.tablestore import TableStore
from who2be_models import TimelineGranularity, TimelineItem, TimelineResult, TimelineSlice

# Item-Kappung pro Bucket und Quelle (DoS-/Payload-Schutz, Plan WP15): die
# counts zaehlen IMMER vollstaendig, nur die Item-Liste wird gedeckelt.
BUCKET_ITEM_CAP: Final = 200
# Deckel des fensterlosen unknown-Buckets, je Quelle (s. Modul-Kopf).
UNKNOWN_ITEM_CAP: Final = 200


class TimelineTableNotFound(LookupError):
    """Eine `table:<id>`-Quelle existiert im Workspace nicht — Router → 404."""

    def __init__(self, table_id: UUID) -> None:
        super().__init__(f"Tabelle {table_id} nicht gefunden.")
        self.table_id = table_id


def _table_source_forbidden(table_id: UUID) -> ApiGateError:
    """403 fuer eine explizit angeforderte Quelle ohne read-Grant (Plan WP15)."""
    return ApiGateError(
        status=status.HTTP_403_FORBIDDEN,
        reason="area_forbidden",
        actionable_by="human",
        detail=(
            f"Kein Lesezugriff auf die Timeline-Quelle 'table:{table_id}'. Der "
            "Workspace-Besitzer kann dem Agenten einen read-Grant fuer die Area "
            "der Tabelle vergeben — oder die Quelle aus dem Aufruf entfernen."
        ),
    )


def _bucket_for(day: date, granularity: TimelineGranularity) -> date:
    """Tag → Bucket-Schluessel: Tag selbst, ISO-Wochen-Montag oder Monatserster.

    App-seitiges Pendant zu ``date_trunc`` (Postgres bucketet Woche ebenfalls
    ab Montag) — noetig fuer die tag-granularen SQLite-Aggregate.
    """
    if granularity is TimelineGranularity.week:
        return day - timedelta(days=day.weekday())
    if granularity is TimelineGranularity.month:
        return day.replace(day=1)
    return day


class WaTimelineService:
    """Merge der Timeline-Quellen hinter den Workspace-Gates (read-only)."""

    def __init__(self, pool: asyncpg.Pool, repo: TimelineRepository, store: TableStore) -> None:
        self._pool = pool
        self._repo = repo
        self._store = store

    async def timeline(
        self,
        ctx: WorkspaceContext,
        *,
        window_start: datetime,
        window_end: datetime,
        granularity: TimelineGranularity,
        include_artifacts: bool,
        include_nodes: bool,
        table_ids: list[UUID],
    ) -> TimelineResult:
        """Zeitscheiben ``[start, end)`` + fensterloser unknown-Bucket (Spec N).

        Fenster-Validierung (to > from, max. 366 Tage) macht der Router;
        hier passiert Scope-Aufloesung, Quellen-Gate und der Merge.
        """
        restrict = await readable_area_ids(self._pool, ctx)
        # Quellen-Gate ZUERST (Plan: read-Grants auf alle sources, sonst 403)
        # — ein verbotener Aufruf soll scheitern, bevor Teilergebnisse fliessen.
        sources: list[TableTimelineSource] = []
        for table_id in table_ids:
            source = await self._repo.table_source(self._pool, ctx.workspace_id, table_id)
            if source is None:
                raise TimelineTableNotFound(table_id)
            if restrict is not None and source.area_id not in restrict:
                raise _table_source_forbidden(table_id)
            sources.append(source)

        slices: dict[date, TimelineSlice] = {}

        def slice_for(bucket: date) -> TimelineSlice:
            existing = slices.get(bucket)
            if existing is None:
                existing = TimelineSlice(bucket=bucket.isoformat())
                slices[bucket] = existing
            return existing

        if include_artifacts:
            for row in await self._repo.artifact_buckets(
                self._pool,
                ctx.workspace_id,
                window_start=window_start,
                window_end=window_end,
                granularity=granularity.value,
                restrict_area_ids=restrict,
                item_cap=BUCKET_ITEM_CAP,
            ):
                bucket = slice_for(row.bucket)
                bucket.items.append(TimelineItem(anchor=row.anchor, kind="artifact"))
                # `total` zaehlt den GANZEN Bucket — unabhaengig vom Item-Cap.
                bucket.counts["artifact"] = row.total

        if include_nodes:
            for row in await self._repo.node_buckets(
                self._pool,
                ctx.workspace_id,
                window_start=window_start,
                window_end=window_end,
                granularity=granularity.value,
                restrict_area_ids=restrict,
                item_cap=BUCKET_ITEM_CAP,
            ):
                bucket = slice_for(row.bucket)
                bucket.items.append(TimelineItem(anchor=row.anchor, kind="node"))
                bucket.counts["node"] = row.total

        for source in sources:
            day_counts = await self._repo.table_day_counts(
                self._store,
                ctx.workspace_id,
                source.area_id,
                source.name,
                source.occurred_column,
                window_start=window_start,
                window_end=window_end,
            )
            anchor = f"table:{source.table_id}"
            anchored: set[date] = set()
            for day, count in day_counts:
                bucket_key = _bucket_for(day, granularity)
                bucket = slice_for(bucket_key)
                if bucket_key not in anchored:
                    # EIN Item pro Tabelle und Bucket — Zeilen haben keine
                    # adressierbaren Anker (s. Modul-Kopf).
                    bucket.items.append(TimelineItem(anchor=anchor, kind="table_rows"))
                    anchored.add(bucket_key)
                bucket.counts["table_rows"] = bucket.counts.get("table_rows", 0) + count

        unknown: list[TimelineItem] = []
        if include_artifacts:
            unknown.extend(
                TimelineItem(anchor=anchor, kind="artifact")
                for anchor in await self._repo.unknown_artifact_anchors(
                    self._pool,
                    ctx.workspace_id,
                    restrict_area_ids=restrict,
                    cap=UNKNOWN_ITEM_CAP,
                )
            )
        if include_nodes:
            unknown.extend(
                TimelineItem(anchor=anchor, kind="node")
                for anchor in await self._repo.unknown_node_anchors(
                    self._pool,
                    ctx.workspace_id,
                    restrict_area_ids=restrict,
                    cap=UNKNOWN_ITEM_CAP,
                )
            )

        ordered = [slices[bucket] for bucket in sorted(slices)]
        return TimelineResult(slices=ordered, unknown=unknown)
