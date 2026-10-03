# Gedaechtnis-API: Mehrfachwerte und Ausschluss in Filtern (t_5f8bdb35)

Folge aus Review C5b-1 (PR #803, Hinweis 4). Spec gedaechtnisverwaltung §6.2:
Facetten sind Mehrfachauswahl (ODER in der Gruppe, UND zwischen Gruppen),
Standardansicht „alle Status ausser Abgelehnt“.

## Completion-Condition

- `GET /memories`, `GET /memories/counts` und `POST /memories/batch` (Filtermodus)
  nehmen fuer `status`, `kind`, `origin` mehrere Werte (Wiederholung des
  Query-Parameters bzw. Liste im JSON) und `exclude_status` (wiederholbar).
- Liste, Zaehler (`total`) und Batch-Auswahl ergeben fuer dieselben Filter
  dieselbe Menge (Test, inkl. `expected_count`-Abgleich).
- Rot-Probe belegt den Test.
- Mandantentrennung unveraendert (bestehende Tests gruen).
- openapi.json neu exportiert, ADR-0053-Vertragstabelle nachgezogen.
- Python-DoD lokal gruen, CI 17/17.

## Entscheidungen (aus dem Repo belegt)

1. **Ein Wert oder Liste, intern Liste.** `MemoryFilter.status|kind|origin`
   nehmen einen Einzelwert ODER eine Liste; ein Validator normalisiert auf eine
   duplikatfreie Liste. Grund: der Web-Client schickt im Batch-Body heute
   Einzelwerte (`filter: {status: 'pending'}`, types.ts) und die Web-Umstellung
   ist Out-of-Scope. Ausserdem bleibt `MemoryFilter(status=...)` in Service
   und Tests gueltig, sodass der Diff in 8 Dateien passt.
2. **Ausschluss heisst `exclude_status`** (Liste). Weitere Ausschluesse sind
   laut Karte nicht gefordert.
3. **Facette `status` ignoriert auch `exclude_status`.** Die Zaehler-Gruppe
   zaehlt ohne ihren eigenen Filter (6.4.1). Nur so kann die Web-Liste die
   Zahl fuer „Abgelehnt“ an deren eigenem Haken zeigen.
4. **Warteschlangen-Regel verallgemeinert.** Ist `pending` unter den Status
   und `lesson` nicht unter den Arten, faellt `pending AND lesson` weg. Fuer
   einen einzelnen Wert ist das identisch zu heute. Ein reiner Ausschluss ohne
   positive Status loest die Regel nicht aus (Standardansicht zeigt
   Lernvorschlaege wie bisher).
5. Leere Liste im JSON = kein Filter (wie `None`).

## Dateien (8, ohne diese Plan-Datei)

1. packages/models/src/who2be_models/memory.py
2. apps/api/src/who2be_api/routers/memory.py
3. apps/api/src/who2be_api/repositories/memory_repository.py
4. apps/api/tests/test_memory_list_counts.py
5. apps/api/tests/test_memory_list_counts_api.py
6. docs/reference/openapi.json
7. docs/adr/0053-*.md (REST-Tabelle)
8. changelog.d/t-5f8bdb35-memory-filter-mehrfachwerte.added.md

## Schritte

- [x] Modell + Validator
- [x] Router: Listen-Query-Parameter
- [x] `_memory_where`: ANY/NOT ANY, Regel 4, skip-Logik
- [x] Service-Tests: Mehrfachwerte, Ausschluss, Liste==Zaehler==Batch
- [x] API-Test: Parameter-Wiederholung, Einzelwert-Kompatibilitaet Batch
- [x] Rot-Probe (6/6 rot: Ausschluss ignoriert, status-Facette behaelt
      Ausschluss, nur erster Status, Queue-Regel nur bei Einzelwert,
      Batch-Auswahl ohne Ausschluss, Zaehler nur erster Origin)
- [x] openapi.json, ADR, Fragment
- [ ] DoD lokal, Push, danach PR
