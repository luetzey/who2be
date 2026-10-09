# M1 — /memory „Einträge“ auf ListFilterBar (Filter-Standard)

Status: umgesetzt, PR offen · Karte t_96945d84 · Vorgabe `filter-standard-2026-10.md` (@designer, t_c5144418) §2, §3.1, §4 Zeile M1

## Ziel
Der Tab „Einträge“ nutzt die Standard-Filterleiste (F0, #863). Die Facettenspalte entfällt, die Liste hat die volle Breite.

## Schnitt (8 Dateien laut §4, ohne diese Plan-Datei)
1. `apps/web/src/components/memory/MemoryFacets.tsx`: neuer Adapter `useMemoryFilterBar(filters, counts, countsError, agents, onChange)` → `statusOptions`/`status`/`onStatusChange`/`facets`. `MemoryFacetColumn` und „Alle n zeigen“ entfallen. `FilterSheetButton`/`ActiveFilterChips` bleiben bis M2 für die Agent-Karte.
2. `apps/web/src/features/memory/pages/MemoryPage.tsx` (EntriesTab): `ListFilterBar` mit Suche, Status-Chips, fünf Facetten, `sortOptions`, `countsUnavailable`, `resultCount`.
3. `apps/web/src/features/memory/pages/MemoryPage.test.tsx`: Radios → Selects/Chips, Status-Chips mit 0er-Regel, Zahl „(n)“ + alphabetische Agenten + Hinweis, „Keine Treffer“, Mobil-Sheet (Fuß „n Treffer zeigen“, Fokus zurück), axe mit offenem Sheet.
4. `apps/web/src/components/memory/MemoryList.tsx`: Leer gefiltert → `data:filter.emptyFilteredTitle` + `data:filter.reset`.
5. `apps/web/e2e/scroll-guard.spec.ts` (C5b-1): Knopf-Regex `/^(Filter|Filters)( \(|$)/`, Knopf Pflicht unter `md`, versteckt ab `md`, Panel ohne Seitwärts-Scroll.
6./7. `de.json`/`en.json`: Orphans `entries.facet.showAll`, `entries.hintFor`, dazu `entries.facetsRegion` und `entries.noMatch` (durch M1 verwaist) entfernt. Die Orphan-Baseline wird nicht angefasst.
8. `changelog.d/t-96945d84-memory-entries-filterbar.changed.md`

## Entscheidungen innerhalb der Vorgabe
- Status-Chips: Alle · Aktiv · Zur Freigabe · Abgelaufen · Abgelehnt. Die Tokens entsprechen `StatusLine` (active/review/draft/draft). Die URL behält `status=` (fehlt = Alle). Ohne Status-Filter ist „Alle“ gleich `counts.total`, mit Status-Filter die Summe von `groups.status`, denn die Gruppe zählt ohne den eigenen Filter.
- Agenten-Select: Werte aus `groups.agent` (mit Zahl), ohne Zahlen alle geladenen Agenten. Ein gesetzter Agent bleibt wählbar. Sortiert wird alphabetisch nach Name.
- Sortierung: Standard `''` = „Neueste zuerst“ (nicht in der URL), `oldest` als URL-Wert, wie bisher.
- „Filter zurücksetzen“ in der Leiste erscheint, sobald Suche oder eine Facette inkl. Status gesetzt ist. Die Sortierung bleibt dabei stehen (§2.1.6).

## Verifikation
`npm run lint` (0 Fehler), `npx tsc -b`, `npm run test:coverage` (Node 22), Skip-Budget, `npm run build`, `npm run license:check`, `npm run i18n:check`. e2e-mobile lokal gegen einen eigenen Podman-Compose-Stack: 3 Profile, 99 bestanden, 6 übersprungen (Billing, nur Cloud). C5b-1 zusätzlich auf chromium (Desktop) grün. Fotos + measure.json unter `.shots/t_96945d84/` (nicht committet).
