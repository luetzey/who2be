TITEL: W3 Dashboard: Responsive-Audit von features/dashboard (5 Dateien)
LABELS: web, agent-ready, size/S
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `dashboard`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **5 produktive `.tsx`** unter
`apps/web/src/features/dashboard/`, davon trägt **1** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/dashboard -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 5
find apps/web/src/features/dashboard -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;    # nur pages/DashboardPage.tsx
```

Das Dashboard ist die **Landeseite nach dem Login** — die erste Fläche, die ein
Nutzer auf dem Handy sieht. Es ist zugleich die einzige Domäne, deren
Hauptseite bereits mobile-first gebunden ist (`sm:grid-cols-2 lg:grid-cols-3`),
während **vier von fünf** ihrer Komponenten feste Zahlenspalten und
Icon-Stapel ohne jede Abfederung tragen.

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/dashboard/pages/DashboardPage.tsx` (271 Z.) | **ja** (1) | `:168` `grid gap-4 sm:grid-cols-2 lg:grid-cols-3` — **erfüllt**, mobile-first gebunden. `:193` `CardHeader` trägt `flex-row flex-wrap items-center justify-between gap-3` — **erfüllt**, bricht um. `:137` `flex flex-wrap items-center gap-2` — **erfüllt**. `:197` `<li className="flex items-center gap-1.5">` ohne `min-w-0`: zu prüfender Fall bei langen Statuslabels. |
| `features/dashboard/components/StatusBar.tsx` (89 Z.) | – | **`:34` `<span className="w-24 flex-none text-sm font-medium">{label}</span>` — feste Breite 96 px, `flex-none`, in einer `flex items-center gap-4`-Zeile (`:33`).** Auf 320 px bleiben dem Balken (`:38`, `flex h-3 flex-1 overflow-hidden`) nach Label und Gap rechnerisch ~200 px minus Container-Padding. Der klassische §4.4-Checklistenpunkt 3 (feste Breite auf Container-Ebene ohne responsive Abfederung). |
| `features/dashboard/components/ActivityRow.tsx` (114 Z.) | – | `:86` `flex items-center gap-3`; `:103` trägt bereits `min-w-0 flex-1 truncate` — **erfüllt** für den Texteinlauf. `:90` `size-8` und `:97` `size-4` Badge sind fixe Icon-Größen ohne Textinhalt, kein Überlauf-Risiko. Zu prüfen: Hit-Target der Zeile unterhalb `md`. |
| `features/dashboard/components/KpiCard.tsx` (34 Z.) | – | `:22` `CardContent` mit `flex items-center gap-4 p-4`; `:24` trägt `min-w-0` — **erfüllt**. Zu prüfen: lange KPI-Zahlen und -Labels bei 320 px innerhalb des einspaltigen Grid-Falls. |
| `features/dashboard/components/PaginationControls.tsx` (50 Z.) | – | `:26` `<nav className="flex items-center justify-between gap-3">` **ohne `flex-wrap`**. Zwei Buttons plus Positionsanzeige auf einer Zeile — zu prüfender Fall bei 320 px, wenn die Anzeige mehrsprachig lang wird. |

**Breakpoint-Abdeckung: 1 von 5.**

**Was hier bereits stimmt und nicht wiederholt wird:** das KPI-Grid ist seit
jeher mobile-first gebunden; `ActivityRow` und `KpiCard` tragen `min-w-0` an
der richtigen Stelle; der `CardHeader` auf `DashboardPage.tsx:193` bricht um.
Das sind drei Punkte, die dieses Paket **nicht** anfasst.

### Proposed solution

**Fertig heißt:** Jede der 5 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; jeder gefundene Defekt ist behoben oder mit Begründung als „kein
Defekt" im Issue festgehalten. Kein horizontaler Body-Scroll auf der
Dashboard-Route.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive · `cn()` läuft über `tailwind-merge`:
zwei Klassen derselben Familie löschen einander, `w-*` und `max-w-*` nicht.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **`StatusBar.tsx:34` — Label abschaffen, kürzen oder Breite abfedern?** →
   **Breite abfedern** (`w-20 sm:w-24` oder `min-w-0` mit `truncate`), nicht
   das Label entfernen → weil das Label die Achsenbeschriftung des Balkens ist
   und ohne es die Zahl bedeutungslos wird. §4.4 Checklistenpunkt 3 verlangt
   die Abfederung, nicht den Verzicht.
2. **`PaginationControls.tsx:26` — `flex-wrap` oder Kurzform auf Mobile?** →
   **`flex-wrap`** → weil das dem Muster folgt, das W2 im Repo etabliert hat
   (`PageHeader.tsx:37`, `EntityCard`) und keine zweite, breakpoint-abhängige
   Render-Variante einführt. Eine `useIsMobile()`-Verzweigung wäre teurer und
   nach W1 nur für echte Layout-Wechsel gedacht.
3. **KPI-Grid anfassen?** → **Nein** → weil `DashboardPage.tsx:168` bereits
   `sm:grid-cols-2 lg:grid-cols-3` trägt und damit die §4.4-Regel erfüllt. Ein
   zusätzlicher `md:`-Schritt wäre eine Designentscheidung ohne gemessenen
   Defekt.
4. **Tests wohin?** → **`*.test.tsx` neben die geänderte Komponente**, nach dem
   Muster von W2/#513 → weil `StatusBar` und `PaginationControls` kleine,
   gut isoliert testbare Komponenten sind und die Klassenwirkung dort direkt
   belegbar ist.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt die Dashboard-Route keinen
      horizontalen Body-Scroll.
- [ ] **`StatusBar` zeigt auf 320 px Label und Balken nebeneinander ohne
      Überlauf** — die feste Breite auf `StatusBar.tsx:34` ist responsiv
      abgefedert oder durch `min-w-0`/`truncate` ersetzt.
- [ ] **`PaginationControls` bricht auf 320 px um oder passt vollständig** —
      keine Aktion liegt außerhalb des Viewports.
- [ ] Mehrspaltige Grids bleiben an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile:
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/dashboard | grep -v '\.test\.tsx'
      ```
- [ ] Hit-Targets unterhalb `md` bleiben ≥ 40 px (§11 A11y-Minimum) — geprüft
      an `PaginationControls` und der `ActivityRow`-Zeile.
- [ ] Text bleibt auf 320 px lesbar: Flex-Kinder mit Textinhalt tragen
      `min-w-0` — insbesondere `DashboardPage.tsx:197` (Statusliste).
- [ ] **Alle 5 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 5 Dateien unter `apps/web/src/features/dashboard/`, ihre
Testnachbarn, und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter
Commit** — Sammelpunkt).

### Out of scope

`components/ui/*` und `components/layout/*` (W2 hat dort entschieden; eine
Änderung wirkt auf alle dreizehn Domänen und ist ein eigenes Paket) · jede
andere Domäne unter `features/` · W4 (Playwright-Mobile-Profile, E2E-Helfer
„kein horizontaler Body-Scroll") · echter Fullscreen-Dialog unter `sm` (#513
Weiche 3, verworfen) · ESLint-Regel für nackte `grid-cols-*` (#438 Weiche 5,
verworfen) · jede inhaltliche Änderung an den KPIs oder der Aktivitätsliste ·
`apps/api`, `apps/mcp`, `packages/**`.

### Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b            # NICHT --noEmit: das prueft null Dateien (Solution-File)
npm run test:coverage
npm run build
```

**Grün heißt:** Exit 0 bei allen vieren; `test:coverage` nennt Dateizahl und
Testzahl (Queue-Regel 21), die Branches-Thresholds halten; das Grid-Gate aus
AK 4 gibt keine Zeile aus.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen.

### Verweise

Tracking: **#431** (W3). Norm: `docs/frontend/design-language.md` §4.4
(Mobile-first, Prefix-Pflicht, sechspunktige Review-Checkliste Z. 222–233),
CLAUDE.md §Frontend-Standards. Vorgänger: **#438** (W0 — `Sheet`,
`useMediaQuery`, §4.4), **#500** (W1 — Schwelle `md`, `useEffect`-freies
Muster), **#513** (W2 — Dialog-Inset, Caps im Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace. Die drei
größten W3-Pakete (`playbooks` 16, `workarea` 14, `personas` 13) laufen nie zu
zweit gleichzeitig.

### Component

Web UI (apps/web)
