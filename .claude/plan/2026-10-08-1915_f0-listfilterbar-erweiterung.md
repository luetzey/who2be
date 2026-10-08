# F0 — ListFilterBar-Erweiterung E1–E9 (Filter-Standard)

Status: umgesetzt, PR offen · Karte t_e6c82f40 · Vorgabe `filter-standard-2026-10.md` (@designer, t_c5144418) §2, §2.5, §4 Zeile F0

## Ziel
ListFilterBar wird das Standard-Filtermuster aller Listen; vor D6b (Fall-Liste), D6g (Muster) und M1–M3 (/memory).

## Schnitt (7 Dateien laut §4, ohne diese Plan-Datei)
1. `apps/web/src/components/data/ListFilterBar.tsx` — E1 `statusOptions`, E2 Suche optional + `searchPlaceholder`, E3 `facets` (Reihenfolge Agent → Typ → generisch → Tag → Sprache, Zahl „(n)“, Hinweis per `aria-describedby`), E4 eine `ul` „Aktive Filter“ + Zuruecksetzen am Ende + Fokusfuehrung, E5 `sortOptions`, E7 `countsUnavailable`/`resultCount`, E8 `bare`, E9 40-px-Chips unter `md`
2. `apps/web/src/components/data/ListFilterSheet.tsx` (neu) — E6 Sheet von unten, `max-h-[85svh]`, Fuss fest, Fokus zurueck auf „Filter“
3. `apps/web/src/components/data/ListFilterBar.test.tsx` — Inline-Test → Sheet-Test, generische Chips/Facetten, Chips je Facette, Fokus, eine Facette ohne Sheet, axe (Leiste + offenes Sheet)
4. `apps/web/src/lib/listFilter.ts` — `StatusChipOption`, `FacetOption`, `FacetSpec`, `visibleStatusChips`
5./6. `de.json`/`en.json` — `data:filter.*` nach §2.4
7. `changelog.d/list-filter-bar-standard.changed.md`

## Entscheidungen innerhalb der Vorgabe
- Sheet-Pflicht: ab zwei sichtbaren Facetten ODER sobald eine Anzeige-Option da ist (§2.2 „höchstens eine Facette und keine Anzeige-Option“ → inline).
- Ist das Sheet aktiv (`useIsMobile()`), entfaellt die versteckte Inline-Kopie ganz (sonst doppelte Labels im DOM); ohne `matchMedia` (jsdom) bleibt das Raster `hidden md:contents`.
- Versionsstatus-Weg (`counts`/`status`) laeuft intern ueber dieselben Chip-Optionen: „Alle“ bleibt immer, uebrige 0er entfallen wie bisher.
- Die vier Seiten bleiben unveraendert; neu sichtbar sind dort die Tag-Chips und die einzeilige Chip-Liste. Kein Seiten-Test bricht (1963/1963 gruen).

## Verifikation
`npm run lint` (0 Fehler), `npx tsc -b`, `npm run test:coverage` 1963/1963, Skip-Budget 0, `npm run build`, `npm run license:check`, `npm run i18n:check`, `changelog_fragments.py check`. Fotos + measure.json unter `.shots/t_e6c82f40/` (nicht committet). e2e-mobile: CI (lokal kein Compose-Stack).
