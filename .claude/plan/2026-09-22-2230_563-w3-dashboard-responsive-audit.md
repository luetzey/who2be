# #563 W3 Dashboard — Responsive-Audit `features/dashboard` (5 Dateien)

Branch: `who2be/t_96b20b9c-563-w3-dashboard-responsive-audit-von-fe`
Basis: `origin/main` @ `b28c2ebd` (rebased, 34 Commits nachgezogen)
Spezifikation: Issue #563 (agent-ready, keine offene Entscheidung)
Norm: `docs/frontend/design-language.md` §4.4 (sechspunktige Review-Checkliste), §11 (Hit-Targets ≥ 40 px)

## Befund je Datei (gegen die §4.4-Checkliste, 320/375/768/1024 px)

| Datei | Befund | Aktion |
|---|---|---|
| `pages/DashboardPage.tsx` | KPI-Grid `sm:grid-cols-2 lg:grid-cols-3` erfüllt (Punkt 2); `CardHeader` bricht um; Quickstart-Leiste `flex-wrap`. **Defekt:** Legenden-`<li>` ohne `min-w-0` (Punkt 5). | `min-w-0` am `<li>` ergänzen |
| `components/StatusBar.tsx` | **Defekt:** `w-24 flex-none` Label ohne responsive Abfederung (Punkt 3). Auf 320 px bleiben dem Balken nach Label (96 px) + 2×gap-4 (32 px) + Zahlen-Ablesung nur ~100 px. | `w-20 truncate md:w-24` (Weiche 1: abfedern, nicht entfernen) |
| `components/PaginationControls.tsx` | **Defekt:** `<nav>` ohne `flex-wrap` (Punkt 1). Der Hit-Target-Punkt entfällt: §11 nennt **≥ 32 px** als Floor, `size="sm"` = `h-9` (36 px) liegt darüber (PM-Klarstellung 2026-09-23, Karte t_d782f2bc zieht die „≥ 40 px" in §4.4 nach). | `flex-wrap` am `<nav>` |
| `components/ActivityRow.tsx` | **kein Defekt.** `:103` trägt `min-w-0 flex-1 truncate`; Icons `size-8`/`size-4` ohne Textinhalt; die Zeile ist ein `<div>` **ohne Interaktion** — kein Hit-Target, §11 greift nicht. | — |
| `components/KpiCard.tsx` | **kein Defekt.** `:24` trägt `min-w-0`; keine festen Breiten; Label/Beschreibung umbrechen normal, Zahl ist `tabular-nums` ohne Mindestbreite. | — |

## Weichen — geerbt aus dem Issue, nicht neu entschieden

1. StatusBar-Label: **Breite abfedern**, nicht entfernen (Label ist die Achsenbeschriftung).
2. PaginationControls: **`flex-wrap`**, keine `useIsMobile()`-Verzweigung (W2-Muster `PageHeader.tsx`).
3. KPI-Grid: **nicht anfassen** (erfüllt §4.4 bereits).
4. Tests: `*.test.tsx` neben die geänderte Komponente (W2/#513-Muster).

Schwelle `md` folgt #500 (`hooks/useMediaQuery.ts`) — die Prefixe sind `md:`, nicht `sm:`.

## Schritte

1. **Rot:** Testfälle für die Klassenwirkung schreiben und fallen sehen
   - `StatusBar.test.tsx`: Label trägt `w-20`, `truncate`, `md:w-24`; kein nacktes `w-24`.
   - `PaginationControls.test.tsx` (neu): `<nav>` trägt `flex-wrap`; beide Buttons `h-10 md:h-9`; Rendern erst ab `totalPages > 1`.
   - `DashboardPage.test.tsx`: Legenden-`<li>` trägt `min-w-0`.
2. **Grün:** die drei Änderungen anwenden.
3. **Gates:** Grid-Gate aus AK 4; `npm run lint`, `npx tsc -b`, `npm run test:coverage` (Branches-Floor 79), `npm run build`, `npm run i18n:check`, `npm run license:check`.
4. **Changelog:** Fragment `changelog.d/dashboard-responsive-audit.changed.md` (Fragment-Verfahren, **nicht** CHANGELOG.md — PM-Korrektur zur Issue-Anweisung).
5. Commit, Push, PR gegen `main`, `all-green` am exakten Head-SHA abwarten.

## Grenzen

Nur `apps/web/src/features/dashboard/**` + Testnachbarn + `changelog.d/`.
Keine Änderung unter `components/ui/**` oder `components/layout/**`.
Kein i18n-Schlüssel neu (die Änderungen sind rein layoutseitig).
