"""Deterministische Kategorisierung + Quell-Konventionen (WP17 — Spec L/M2, ADR-0049).

„Regel VOR Modell" (Spec L): KEIN Lauf aendert eine Kategorie ohne
Regeltabellen-Eintrag. Die Regel-Phase des Zeilen-Imports
(`categorize_rows`, aufgerufen von `WaTableService.insert_rows`) arbeitet in
fester Reihenfolge:

1. Mitgelieferte `new_rules` werden ZUERST persistiert (Upsert auf
   (area_id, pattern)). `created_by` attribuiert der SERVER aus dem Token
   (``agent:<id>`` | ``user:<id>``) — das ``model:``-Praefix vergibt der
   Aufrufer NIE selbst: die Runtime meldet Modell-Regeln als `new_rules`,
   der Server attribuiert den Token.
2. Matching gegen die AKTIVEN Regeln der Area: case-insensitive Substring
   des `pattern` im Wert der `match_column`; der laengste Pattern gewinnt.
3. GENAU EINE Kategorie unter den Treffern → der Server setzt die
   `category_column` der Row (ueberschreibt jeden Client-Wert).
4. Treffer mit VERSCHIEDENEN Kategorien → Row bleibt unkategorisiert (NULL)
   + `kb_conflict(kind='rule')` — kein stilles Gewinnen; offene Konflikte
   desselben Regel-Paars werden nicht gedoppelt.
5. KEIN Treffer, aber Client-Kategorie → 422 `rule_required` fuer den
   GANZEN Request — die Regel-Phase laeuft in EINER Postgres-Transaktion,
   Schritt 1 rollt mit zurueck; SQLite sieht erst nach erfolgreicher
   Regel-Phase Writes (kein Teilzustand).
6. KEIN Treffer, keine Client-Kategorie → Row bleibt unkategorisiert
   (Kategorisierung ist optional pro Row).

Quell-Konventionen (Spec M2): `insert_rows` mit `source_name` verlangt eine
hinterlegte `wa_source_convention` der Area (sonst 422 `convention_missing`,
VOR jedem Write) — die INHALTLICHE Anwendung der Konvention (Einheiten,
Notation, Formate) ist Sache der Agent-Runtime, der Server erzwingt nur ihre
Existenz.

Rueckwirkende Re-Kategorisierung: der Regel-Upsert (`WaRuleService.
upsert_rule`) kategorisiert die SQLite-Rows aller Area-Tabellen mit
category/match-Spalten NEU — ueber `TableStore.reapply_category`
(server-only Schreibpfad, ADR-0049: der Server unterliegt dem Authorizer
nicht). Der Service liefert nur Namen aus dem validierten Katalog-Schema
und Werte; SQL-Bau und Identifier-Quoting liegen im Store (ARC-3).
Konflikt-Rows (eine ANDERE aktive Regel mit anderer
Kategorie matcht dieselbe Row) werden dabei NICHT angefasst — nur
nicht-konfligierende Rows updaten. Jeder Upsert wird im `audit_log`
protokolliert (``workarea.rules_reapplied``: rule_id, Tabellen, Zeilenzahlen).

Gates (H1-Muster `wa_tables`): Regel-/Konventions-Writes = `require_role
(editor)` + `require_capability(workarea_write)` + `require_write_rate` +
`ensure_area_access(write)`; Reads = Area-READ (fehlender Read-Grant → 404,
kein Existenz-Leak).

ARC-3: kein SQL, keine HTTPException — nur `ApiGateError`, Repos,
`core/workarea_scope`; SQLite AUSSCHLIESSLICH ueber den TableStore.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_write_rate,
)
from who2be_api.core.workarea_scope import ensure_area_access
from who2be_api.repositories.wa_rule_repository import WaRuleRepository
from who2be_api.repositories.wa_table_repository import WaTableRepository
from who2be_api.services.audit_service import AuditService
from who2be_api.tablestore import TableStore
from who2be_models import (
    AgentCapability,
    CategoryRuleRead,
    CategoryRuleUpsert,
    NewRule,
    SourceConventionRead,
    SourceConventionSet,
    TableSchema,
    WorkAreaGrantLevel,
    WorkspaceRole,
)

# Zeichen-Cap fuer den Match-Wert im Konflikt-`reason` — das Feld ist eine
# Triage-Notiz, kein Daten-Dump.
_REASON_VALUE_CAP = 120


def rule_actor(ctx: WorkspaceContext) -> str:
    """Akteur-Kennung fuer `wa_category_rule.created_by` — vom SERVER vergeben.

    ``agent:<id>`` bei agent-gebundenem Token, sonst ``user:<id>``. Das
    ``model:``-Praefix vergibt der Aufrufer NICHT selbst — die Runtime meldet
    Modell-Regeln als `new_rules`, der Server attribuiert den Token (Spec L).
    """
    if ctx.agent_id is not None:
        return f"agent:{ctx.agent_id}"
    return f"user:{ctx.user_id}"


def rule_required(index: int, category: object, value: object) -> ApiGateError:
    """422 `rule_required`: Kategorie-Wert ohne matchende aktive Regel (Spec L).

    Der GANZE Request wird abgelehnt (kein Teilzustand) — der Agent liefert
    die Regel als `new_rules`-Element nach oder legt sie ueber
    `POST .../category-rules` an.
    """
    return ApiGateError(
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        reason="rule_required",
        actionable_by="agent",
        detail=(
            f"Zeile {index}: Kategorie '{category}' ohne matchende aktive Regel "
            f"fuer den Wert '{value}' — Regel VOR Modell (Spec L). Die Regel als "
            "`new_rules`-Element mitliefern oder ueber POST "
            "/work-areas/{area_id}/category-rules anlegen; nichts wurde importiert."
        ),
    )


def convention_missing(source_name: str) -> ApiGateError:
    """422 `convention_missing`: `source_name` ohne Quell-Konvention (Spec M2).

    Abgelehnt, nicht geraten — die Konvention wird ueber
    `PUT /work-areas/{area_id}/conventions/{source_name}` hinterlegt.
    """
    return ApiGateError(
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        reason="convention_missing",
        actionable_by="agent",
        detail=(
            f"Fuer die Quelle '{source_name}' ist keine Konvention hinterlegt — "
            "erst PUT /work-areas/{area_id}/conventions/{source_name} "
            "(Einheiten, Notation, Dezimal-/Datumsformat), dann importieren. "
            "Nichts wurde importiert."
        ),
    )


def _matches(pattern: str, value: object) -> bool:
    """Case-insensitive Substring-Match des Patterns im Match-Spalten-Wert."""
    return isinstance(value, str) and pattern.lower() in value.lower()


async def categorize_rows(
    conn: asyncpg.Connection,
    ctx: WorkspaceContext,
    *,
    area_id: UUID,
    schema: TableSchema,
    rows: list[dict[str, object]],
    new_rules: list[NewRule],
    repo: WaRuleRepository,
) -> None:
    """Regel-Phase des Zeilen-Imports (Spec L) — mutiert `rows` in place.

    MUSS auf einer offenen Transaktions-Connection laufen: wirft
    `rule_required`, rollen die in Schritt 1 persistierten `new_rules` (und
    etwaige Konflikt-Zeilen) mit zurueck — der Aufrufer schreibt SQLite erst
    NACH erfolgreicher Rueckkehr (kein Teilzustand). Ablauf und Faelle (a)–(f)
    siehe Modul-Docstring.
    """
    if schema.category_column is None or schema.match_column is None:
        return
    actor = rule_actor(ctx)
    for new_rule in new_rules:
        await repo.upsert_rule(
            conn,
            ctx.workspace_id,
            area_id,
            pattern=new_rule.pattern,
            category=new_rule.category,
            created_by=actor,
            confidence=new_rule.confidence,
        )
    active_rules = await repo.list_rules(conn, ctx.workspace_id, area_id, active_only=True)
    for index, row in enumerate(rows):
        value = row.get(schema.match_column)
        matches = [rule for rule in active_rules if _matches(rule.pattern, value)]
        if not matches:
            if row.get(schema.category_column) is not None:
                raise rule_required(index, row.get(schema.category_column), value)
            continue
        # Laengster Pattern gewinnt (deterministisch; Tie-Break: Pattern-Text).
        matches.sort(key=lambda rule: (-len(rule.pattern), rule.pattern))
        winner = matches[0]
        dissent = next((rule for rule in matches[1:] if rule.category != winner.category), None)
        if dissent is None:
            row[schema.category_column] = winner.category
            continue
        # Verschiedene Kategorien → NIE still gewinnen (Spec L): Row bleibt
        # unkategorisiert, der Konflikt wird gemeldet (dedupliziert pro Paar).
        value_text = str(value)[:_REASON_VALUE_CAP]
        await repo.insert_rule_conflict(
            conn,
            ctx.workspace_id,
            a_id=winner.id,
            b_id=dissent.id,
            reason=(
                f"Pattern '{winner.pattern}' ({winner.category}) vs. "
                f"'{dissent.pattern}' ({dissent.category}) auf Wert '{value_text}'"
            ),
        )
        row[schema.category_column] = None


class WaRuleService:
    """Regel-/Konventions-Routen + rueckwirkende Re-Kategorisierung (WP17)."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        rule_repo: WaRuleRepository,
        table_repo: WaTableRepository,
        store: TableStore,
        *,
        audit_service: AuditService,
    ) -> None:
        self._pool = pool
        self._rules = rule_repo
        self._tables = table_repo
        self._store = store
        self._audit = audit_service

    def _require_write(self, ctx: WorkspaceContext) -> None:
        """Schreib-Gate (H1, Muster `wa_tables`): IMMER zuerst
        `require_role(editor)`, dann Capability + Rate (fuer Menschen No-Ops)."""
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, AgentCapability.workarea_write)
        require_write_rate(ctx)

    async def set_convention(
        self, ctx: WorkspaceContext, area_id: UUID, source_name: str, data: SourceConventionSet
    ) -> SourceConventionRead:
        """Quell-Konvention anlegen/ersetzen (Spec M2); `created_by` = Akteur-UUID."""
        self._require_write(ctx)
        await ensure_area_access(self._pool, ctx, area_id, WorkAreaGrantLevel.write)
        return await self._rules.upsert_convention(
            self._pool,
            ctx.workspace_id,
            area_id,
            source_name=source_name,
            convention=data.convention,
            created_by=ctx.user_id,
        )

    async def list_conventions(
        self, ctx: WorkspaceContext, area_id: UUID
    ) -> list[SourceConventionRead]:
        """Konventionen der Area; fehlender Read-Grant → 404 (kein Leak)."""
        await ensure_area_access(self._pool, ctx, area_id, WorkAreaGrantLevel.read)
        return await self._rules.list_conventions(self._pool, ctx.workspace_id, area_id)

    async def upsert_rule(
        self, ctx: WorkspaceContext, area_id: UUID, data: CategoryRuleUpsert
    ) -> tuple[CategoryRuleRead, bool]:
        """Regel anlegen/ersetzen (Spec L) + rueckwirkende Re-Kategorisierung.

        Nach dem Upsert werden die SQLite-Rows aller Area-Tabellen mit
        category/match-Spalten neu kategorisiert (nur nicht-konfligierende
        Rows, s. Modul-Docstring) und der Lauf im `audit_log` protokolliert
        (``workarea.rules_reapplied``). Rueckgabe: (Regel, neu-angelegt?) —
        der Router antwortet 201 bei Anlage, 200 bei Ersetzung.
        """
        self._require_write(ctx)
        await ensure_area_access(self._pool, ctx, area_id, WorkAreaGrantLevel.write)
        rule, created = await self._rules.upsert_rule(
            self._pool,
            ctx.workspace_id,
            area_id,
            pattern=data.pattern,
            category=data.category,
            created_by=rule_actor(ctx),
            confidence=data.confidence,
        )
        reapplied = await self._reapply(ctx, area_id, rule)
        await self._audit.record(
            self._pool,
            action="workarea.rules_reapplied",
            actor_id=ctx.user_id,
            workspace_id=ctx.workspace_id,
            target=rule.id,
            detail={
                "rule_id": str(rule.id),
                "pattern": rule.pattern,
                "category": rule.category,
                "tables": reapplied,
            },
        )
        return rule, created

    async def list_rules(self, ctx: WorkspaceContext, area_id: UUID) -> list[CategoryRuleRead]:
        """Regeln der Area (inkl. inaktiver — Betreiber-Sicht); Read-Gate wie oben."""
        await ensure_area_access(self._pool, ctx, area_id, WorkAreaGrantLevel.read)
        return await self._rules.list_rules(self._pool, ctx.workspace_id, area_id)

    async def _reapply(
        self, ctx: WorkspaceContext, area_id: UUID, rule: CategoryRuleRead
    ) -> dict[str, int]:
        """Wendet `rule` rueckwirkend auf alle Area-Tabellen an (server-only).

        `TableStore.reapply_category` ist der serverseitige Schreibpfad an der
        SQLite-Datei (ADR-0049) — Konflikt-Rows bleiben unangetastet (die
        `excluded_patterns` werden dort zu NOT-Klauseln). Der Service prueft
        nur das Katalog-Schema: Tabellen ohne category-/match-Spalte werden
        uebersprungen. Rueckgabe: Tabellenname → Anzahl geaenderter Zeilen
        (fuer das Audit-Detail).
        """
        active_rules = await self._rules.list_rules(
            self._pool, ctx.workspace_id, area_id, active_only=True
        )
        other_rules = [
            other
            for other in active_rules
            if other.id != rule.id and other.category != rule.category
        ]
        counts: dict[str, int] = {}
        for table in await self._tables.list_for_area(self._pool, ctx.workspace_id, area_id):
            schema = table.schema_
            if schema.category_column is None or schema.match_column is None:
                continue
            counts[table.name] = await self._store.reapply_category(
                ctx.workspace_id,
                area_id,
                table=table.name,
                category_column=schema.category_column,
                match_column=schema.match_column,
                category=rule.category,
                pattern=rule.pattern,
                excluded_patterns=[other.pattern for other in other_rules],
            )
        return counts
