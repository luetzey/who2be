# Plan: Aufräumen Stufe 3 — Render-Helfer + SQL-Bau an ihren Ort

**Datum:** 2026-08-19 · **Branch:** `chore/stufe3-wa-render-tablestore` · **Status:** umgesetzt

## Context

Letzter offene Punkt aus dem Aufräum-Plan der WorkArea-/KB-Session (§„Aufräumen
nach der WorkArea-/KB-Session", 2026-08-19): Stufe 1 (Snippet + Test-Helfer
zusammenführen, PR #380) und Stufe 2 (zwei echte Defekte statt Kosmetik —
Zell-Cap im Schreibpfad, Tool-Gruppen nach Sichtbarkeit trennen, PR #381) waren
gemergt; offen blieb „Rendering/Entschärfung aus `services/wa_tables.py` und
SQL-Bau aus `services/wa_rules.py`" — dieser Plan. Verhaltensneutral: reine
Extraktion, keine neue Logik.

## Schnitt 1 — Render-/Entschärfungs-Helfer aus `wa_tables.py`

Neu: `apps/api/src/who2be_api/services/wa_render.py` (168 Z., reine Funktionen —
kein I/O, kein `ApiGateError`). `wa_tables.py` schrumpft 880 → 755 Z.

Umbenannt beim Verschieben (sprechende Namen statt einer dritten
`_render_markdown`-Definition — `entity_export_service._render_markdown` und
`wa_blocks.render_markdown` existieren bereits, alle drei tun etwas anderes):

| Vorher (`wa_tables.py`, privat) | Nachher (`wa_render.py`, öffentlich) |
|---|---|
| `_render_markdown` | `render_table_markdown` |
| `_render_csv` | `render_table_csv` |
| `_compose_result_doc` | `compose_result_doc` |
| `_csv_cell` | `csv_cell` |
| `_CSV_FORMULA_PREFIXES` | `CSV_FORMULA_PREFIXES` |

Mitgezogen: `single_line`, `sql_fence`, `neutralize_anchor`, `markdown_cell`.

Einzige Teständerung: Import in `apps/api/tests/test_security_fixes_phase2.py`
auf die neuen Namen umgestellt (keine Assertion geändert).

## Schnitt 2 — SQL-Bau aus `wa_rules.py` in den Store

Neu: `TableStore.reapply_category(...)` in `apps/api/src/who2be_api/tablestore/engine.py`
(+53 Z.). Übernimmt den UPDATE-SQL-Bau, der bisher als `_reapply_sql` +
`_like_parameter` in `services/wa_rules.py` lag (360 → 332 Z.); der Service
liefert nur noch Namen aus dem validierten Katalog-Schema und Werte, SQL-Bau
und Identifier-Quoting sitzen im Store. Die redundante Doppel-Validierung
`quote_identifier(validate_identifier(...))` entfiel dabei — `quote_identifier`
validiert bereits intern.

Damit kennt `wa_rules.py` kein SQL mehr — die ARC-3-Leitplanke (kein SQL in
`apps/api/**/services/`) ist für die WorkArea-Services jetzt buchstäblich
erfüllt, nicht nur im Sinn.

## Verifikation

Volle Suite vorher wie nachher **1681 passed** — keine inhaltliche Assertion
im Diff (die einzige Teständerung ist der Import-Umbau oben). Neutralitätsbeweis
für reine Extraktion: gleiche Testzahl, keine geänderte Assertion.

DoD noch ausstehend (lokal vor Push): `ruff check .`, `ruff format --check .`,
`mypy .`, `pytest --cov --cov-fail-under=85`.
