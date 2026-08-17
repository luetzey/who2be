"""Datenzugriff fuer Kategorisierungs-Regeln + Quell-Konventionen (WP17, Spec L/M2).

Postgres-Seite der deterministischen Kategorisierung (ADR-0049): Regeln
(`wa_category_rule`, 0078) sind die EINZIGE Quelle einer Kategorie — kein
Import setzt eine Kategorie ohne Regeltabellen-Eintrag („Regel VOR Modell").
Der Upsert-Schluessel ist `UNIQUE (area_id, pattern)`; `ON CONFLICT DO
UPDATE` macht ihn deterministisch, und `(xmax = 0)` unterscheidet Anlage von
Ersetzung (Router → 201/200). `created_by` ist die Akteur-Kennung als Text
(``agent:<id>`` | ``user:<id>`` | ``model:<id>``) — vergeben vom SERVICE aus
dem Token, nie vom Client.

Quell-Konventionen (`wa_source_convention`, 0078 — Spec M2) haben denselben
deterministischen Upsert ueber `UNIQUE (area_id, source_name)`; `created_by`
ist hier die Akteur-UUID. Dieses Modul ist die EINZIGE Stelle, die
Konventions-Zeilen liest oder schreibt — auch fuer den describe-Pfad
(`services/wa_tables.describe`). Die frueher parallel gepflegte Kopie in
`wa_table_repository` ist entfallen, nachdem ihr strengerer Mapper describe
mit 500 beantwortet hat (Befund 2026-08-16).

Regel-Konflikte („zwei aktive Regeln, verschiedene Kategorien") landen als
`kb_conflict(kind='rule')` (0077): der Insert dedupliziert offene Konflikte
desselben Regel-Paars per `WHERE NOT EXISTS` — ein Konflikt wird gemeldet,
nicht gestapelt. Alle Mutationen sind conn-faehig (Muster
`wa_blob_repository`): die Regel-Phase des Imports laeuft in EINER
Postgres-Transaktion des Services (422 `rule_required` rollt neue Regeln mit
zurueck). Jede Query filtert auf `workspace_id` (Defense-in-Depth zur RLS).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Protocol, TypeAlias
from uuid import UUID

import asyncpg

from who2be_models import CategoryRuleRead, SourceConventionRead

_Fetcher: TypeAlias = asyncpg.Pool | asyncpg.Connection

_RULE_COLUMNS = (
    "id, area_id, pattern, category, created_by, confidence, active, created_at, updated_at"
)

# UNIQUE (area_id, pattern) aus 0078 als Conflict-Target; `(xmax = 0)` ist
# nur bei einer frisch eingefuegten Zeile wahr (Anlage vs. Ersetzung).
# Ein Upsert reaktiviert eine deaktivierte Regel bewusst (active = true):
# „anlegen/ersetzen" heisst, der neue Stand gilt.
_UPSERT_RULE_SQL = (
    "INSERT INTO wa_category_rule "
    "(workspace_id, area_id, pattern, category, created_by, confidence) "
    "VALUES ($1, $2, $3, $4, $5, $6) "
    "ON CONFLICT (area_id, pattern) DO UPDATE SET "
    "category = EXCLUDED.category, created_by = EXCLUDED.created_by, "
    "confidence = EXCLUDED.confidence, active = true, updated_at = now() "
    f"RETURNING {_RULE_COLUMNS}, (xmax = 0) AS inserted"
)

_LIST_RULES_SQL = (
    f"SELECT {_RULE_COLUMNS} FROM wa_category_rule "
    "WHERE workspace_id = $1 AND area_id = $2 ORDER BY pattern"
)

_LIST_ACTIVE_RULES_SQL = (
    f"SELECT {_RULE_COLUMNS} FROM wa_category_rule "
    "WHERE workspace_id = $1 AND area_id = $2 AND active ORDER BY pattern"
)

_UPSERT_CONVENTION_SQL = (
    "INSERT INTO wa_source_convention "
    "(workspace_id, area_id, source_name, convention, created_by) "
    "VALUES ($1, $2, $3, $4::jsonb, $5) "
    "ON CONFLICT (area_id, source_name) DO UPDATE SET "
    "convention = EXCLUDED.convention, created_by = EXCLUDED.created_by, "
    "updated_at = now() "
    "RETURNING id, area_id, source_name, convention, created_by, created_at, updated_at"
)

_GET_CONVENTION_SQL = (
    "SELECT id, area_id, source_name, convention, created_by, created_at, updated_at "
    "FROM wa_source_convention "
    "WHERE workspace_id = $1 AND area_id = $2 AND source_name = $3"
)

_LIST_CONVENTIONS_SQL = (
    "SELECT id, area_id, source_name, convention, created_by, created_at, updated_at "
    "FROM wa_source_convention WHERE workspace_id = $1 AND area_id = $2 ORDER BY source_name"
)

# Offene Konflikte desselben Regel-Paars (in beliebiger Reihenfolge) werden
# nicht gedoppelt — der Insert ist damit idempotent pro offenem Paar.
_INSERT_RULE_CONFLICT_SQL = (
    "INSERT INTO kb_conflict (workspace_id, kind, a_id, b_id, reason) "
    "SELECT $1, 'rule', $2, $3, $4 "
    "WHERE NOT EXISTS ("
    "SELECT 1 FROM kb_conflict "
    "WHERE workspace_id = $1 AND kind = 'rule' AND resolved_at IS NULL "
    "AND ((a_id = $2 AND b_id = $3) OR (a_id = $3 AND b_id = $2))"
    ") RETURNING id"
)


def _to_rule(row: asyncpg.Record) -> CategoryRuleRead:
    """Regel-Zeile → `CategoryRuleRead`; numeric-`confidence` kommt als Decimal."""
    confidence = row["confidence"]
    return CategoryRuleRead(
        id=row["id"],
        area_id=row["area_id"],
        pattern=row["pattern"],
        category=row["category"],
        created_by=row["created_by"],
        confidence=float(confidence) if confidence is not None else None,
        active=row["active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_convention(row: asyncpg.Record) -> SourceConventionRead:
    """Konventions-Zeile → `SourceConventionRead`; jsonb ggf. als String.

    Der String-Zweig deckt Connections ohne jsonb-Codec ab (Owner-/Test-,
    Muster `audit_log_repository`). Er bleibt zusaetzlich die letzte Abwehr
    gegen doppelt encodierte Altbestaende: bis 2026-08-16 schrieb
    `upsert_convention` vor-serialisiert, und der einzige Leser OHNE diesen
    Zweig hat den describe-Pfad mit 500 beendet. Ein Leser, der an einer
    unerwarteten Zeilenform stirbt, nimmt den ganzen Endpunkt mit.
    """
    raw = row["convention"]
    convention: dict[str, Any] = raw if isinstance(raw, dict) else json.loads(raw)
    return SourceConventionRead(
        id=row["id"],
        area_id=row["area_id"],
        source_name=row["source_name"],
        convention=convention,
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class WaRuleRepository(Protocol):
    """Vertrag des Regel-/Konventions-Datenzugriffs (Service-Sicht)."""

    async def upsert_rule(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        area_id: UUID,
        *,
        pattern: str,
        category: str,
        created_by: str,
        confidence: float | None,
    ) -> tuple[CategoryRuleRead, bool]: ...

    async def list_rules(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID, *, active_only: bool = False
    ) -> list[CategoryRuleRead]: ...

    async def upsert_convention(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        area_id: UUID,
        *,
        source_name: str,
        convention: dict[str, object],
        created_by: UUID,
    ) -> SourceConventionRead: ...

    async def get_convention(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID, source_name: str
    ) -> SourceConventionRead | None: ...

    async def list_conventions(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID
    ) -> list[SourceConventionRead]: ...

    async def insert_rule_conflict(
        self, fetcher: _Fetcher, workspace_id: UUID, *, a_id: UUID, b_id: UUID, reason: str
    ) -> bool: ...


class PgWaRuleRepository:
    """asyncpg-Implementierung von `WaRuleRepository`.

    Stateless und conn-faehig: die Regel-Phase des Zeilen-Imports (Spec L)
    laeuft auf der Transaktions-Connection des Services, die Routen-Pfade
    auf dem Pool.
    """

    async def upsert_rule(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        area_id: UUID,
        *,
        pattern: str,
        category: str,
        created_by: str,
        confidence: float | None,
    ) -> tuple[CategoryRuleRead, bool]:
        """Regel anlegen/ersetzen; `True` = neu angelegt (Router → 201)."""
        row = await fetcher.fetchrow(
            _UPSERT_RULE_SQL,
            workspace_id,
            area_id,
            pattern,
            category,
            created_by,
            # numeric verlangt Decimal; ueber str, damit 0.9 nicht als
            # 0.9000000000000000222… ankommt (Float-Repraesentation).
            Decimal(str(confidence)) if confidence is not None else None,
        )
        assert row is not None  # Upsert liefert immer genau eine Zeile
        return _to_rule(row), bool(row["inserted"])

    async def list_rules(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID, *, active_only: bool = False
    ) -> list[CategoryRuleRead]:
        """Regeln der Area; `active_only` fuer den Matching-Pfad (Spec L)."""
        sql = _LIST_ACTIVE_RULES_SQL if active_only else _LIST_RULES_SQL
        rows = await fetcher.fetch(sql, workspace_id, area_id)
        return [_to_rule(row) for row in rows]

    async def upsert_convention(
        self,
        fetcher: _Fetcher,
        workspace_id: UUID,
        area_id: UUID,
        *,
        source_name: str,
        convention: dict[str, object],
        created_by: UUID,
    ) -> SourceConventionRead:
        """Konvention anlegen/ersetzen (M2) — genau eine je (Area, Quelle).

        `convention` geht als **dict** an den Bind-Parameter, NICHT
        vor-serialisiert: der `::jsonb`-Cast aktiviert den jsonb-Codec des
        App-Pools (`core/db.init_connection`, `encoder=json.dumps`), ein
        bereits serialisierter String wuerde dadurch ein zweites Mal in
        Quotes verpackt (dieselbe Regel wie in `workspace_repository`). Genau
        das war der Fall bis 2026-08-16 — in der Spalte stand ein
        JSON-*String* statt eines Objekts, und der describe-Pfad antwortete
        mit 500. Migration 0081 packt die Bestandszeilen aus.
        """
        row = await fetcher.fetchrow(
            _UPSERT_CONVENTION_SQL,
            workspace_id,
            area_id,
            source_name,
            convention,
            created_by,
        )
        assert row is not None  # Upsert liefert immer genau eine Zeile
        return _to_convention(row)

    async def get_convention(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID, source_name: str
    ) -> SourceConventionRead | None:
        """Konvention einer Quelle; `None` → Service wirft 422 `convention_missing`."""
        row = await fetcher.fetchrow(_GET_CONVENTION_SQL, workspace_id, area_id, source_name)
        return _to_convention(row) if row is not None else None

    async def list_conventions(
        self, fetcher: _Fetcher, workspace_id: UUID, area_id: UUID
    ) -> list[SourceConventionRead]:
        """Konventionen der Area (Routen-Liste, Spec M2)."""
        rows = await fetcher.fetch(_LIST_CONVENTIONS_SQL, workspace_id, area_id)
        return [_to_convention(row) for row in rows]

    async def insert_rule_conflict(
        self, fetcher: _Fetcher, workspace_id: UUID, *, a_id: UUID, b_id: UUID, reason: str
    ) -> bool:
        """`kb_conflict(kind='rule')` anlegen; `False` = offenes Paar existiert schon."""
        row = await fetcher.fetchrow(_INSERT_RULE_CONFLICT_SQL, workspace_id, a_id, b_id, reason)
        return row is not None
