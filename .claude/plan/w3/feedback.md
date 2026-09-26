TITEL: W3 Feedback: Responsive-Audit von features/feedback (6 Dateien)
LABELS: web, agent-ready, size/S
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `feedback`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **6 produktive `.tsx`** unter
`apps/web/src/features/feedback/`, davon tragen **3** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/feedback -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 6
find apps/web/src/features/feedback -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;
# FeedbackInbox.tsx, FeedbackDetailPage.tsx, FeedbackItemDetailPage.tsx
```

Die Domäne ist der **Feedback-Posteingang** aus der W3-Checkliste von #431. Sie
ist die einzige der dreizehn, in der eine Seite **fünf** feste Breiten auf
einmal trägt (`FeedbackOverviewPage.tsx`) — und ausgerechnet diese Seite ist
die einzige der drei Feedback-Seiten **ohne** jeden Breakpoint-Prefix.

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/feedback/pages/FeedbackOverviewPage.tsx` (254 Z.) | **–** | **Der Schwerpunkt des Pakets.** `:172` `flex w-52 min-w-0 flex-none items-center gap-2.5` — feste 208 px, `flex-none`, in einer Zeile mit zwei weiteren Spalten. `:191` `flex min-w-[7.5rem] flex-1 flex-col gap-1.5` (120 px Mindestbreite, mit erklärendem Kommentar ab `:188`). `:217` `w-24 flex-none text-right` (96 px). **Summe der festen Anteile: 208 + 120 + 96 = 424 px plus Gaps — auf 320 px rechnerisch nicht darstellbar.** Der klarste gemessene Defekt der Domäne, §4.4 Checklistenpunkt 3. |
| `features/feedback/pages/FeedbackDetailPage.tsx` (389 Z.) | **ja** (2) | `:156` `mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6` — **erfüllt**, mobile-first. `:190` `grid gap-6 md:grid-cols-2` — **erfüllt**, gebunden. `:215` `flex items-center justify-between gap-3 border-t pt-3` und `:227`/`:302` `CardHeader` mit `flex-row items-center justify-between gap-2` **ohne `flex-wrap`** — drei zu prüfende Fälle. `:211` `labelWidth="w-24"` und `:242` `labelWidth="w-20"`: feste Label-Breiten als Prop an `DataList`. |
| `features/feedback/pages/FeedbackItemDetailPage.tsx` (292 Z.) | **ja** (2) | `:114` `mx-auto flex w-full max-w-5xl … sm:px-6` — **erfüllt**. `:159` `grid gap-6 md:grid-cols-2` — **erfüllt**. `:53` `flex items-start justify-between gap-3` mit `:55` `min-w-0 text-right font-medium` — Texteinlauf **erfüllt**, Umbruch der Zeile zu prüfen. `:205`/`:245` `flex items-center gap-2` ohne `flex-wrap`. |
| `features/feedback/components/FeedbackInbox.tsx` (274 Z.) | **ja** (1) | `:191` `grid gap-4 sm:grid-cols-2 lg:grid-cols-3` — **erfüllt**, mobile-first gebunden. Zu prüfen: Karteninhalt (Betreff, Melder, Zeitstempel) im einspaltigen Fall auf 320 px. |
| `features/feedback/components/ReportProblemDialog.tsx` (123 Z.) | – | `:73` `<DialogContent>` **ohne eigene Breitenklasse** — nimmt damit den W2-Default `w-[calc(100vw-2rem)] max-w-lg` + `max-h`/Scroll. **Erfüllt, kein Defekt.** Zu prüfen: Formularfelder und Fehlermeldungen im Dialog bei 320 px. |
| `features/feedback/components/ResolutionSegments.tsx` (71 Z.) | – | **Kein Klassen-Befund** — kein Grid, keine feste Breite. Zu prüfen: eine Segment-Gruppe mit mehreren Zuständen auf 320 px; wenn sie überläuft, ist ein bewusst scrollender Container die Wahl. |

**Breakpoint-Abdeckung: 3 von 6.**

**Was hier bereits stimmt und nicht wiederholt wird:** beide `md:grid-cols-2`
sind gebunden; beide Detailseiten federn ihr horizontales Padding mit `sm:px-6`
ab; `FeedbackInbox` ist mobile-first; der `ReportProblemDialog` erbt den
W2-Inset aus dem Primitive; `min-w-0` sitzt an `:55` und `:174`/`:191`
(Overview) richtig.

### Proposed solution

**Fertig heißt:** Jede der 6 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; **insbesondere ist die dreispaltige Posteingangs-Zeile in
`FeedbackOverviewPage` auf 320 px darstellbar.** Jeder gefundene Defekt ist
behoben oder mit Begründung als „kein Defekt" festgehalten. Kein horizontaler
Body-Scroll auf den Routen der Domäne.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive, Aufrufstellen ergänzen keine
eigenen · `cn()` läuft über `tailwind-merge`.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **`FeedbackOverviewPage` — Spalten stapeln oder Breiten abfedern?** →
   **stapeln unterhalb `md`** (die Zeile wird `flex-col md:flex-row`, die
   festen Breiten werden `md:`-präfixiert) → weil drei feste Anteile von
   zusammen 424 px auf 320 px **rechnerisch** nicht passen; eine reine
   Verkleinerung der Breiten würde alle drei Spalten unlesbar machen. §4.4
   Mobile-first: die präfixlose Klasse ist der Phone-Fall.
2. **Der Kommentar auf `:188-190` begründet `min-w-[7.5rem]` als funktionale
   Mindestbreite — wird die angetastet?** → **Nein, sie wird `md:`-präfixiert,
   nicht entfernt** → weil die dort dokumentierte Begründung für den
   Desktop-Fall weiter gilt; im gestapelten Phone-Fall ist sie gegenstandslos.
   **Der Kommentar wird mitgezogen, nicht gelöscht** — er erklärt sonst eine
   Klasse, die nicht mehr dort steht.
3. **Die drei `justify-between`-Zeilen (`FeedbackDetailPage.tsx:215`, `:227`,
   `:302`) — `flex-wrap` oder Umbau?** → **`flex-wrap`** → weil das dem
   Repo-Muster folgt (`PageHeader.tsx:37`, `EntityCard`) und keine zweite,
   breakpoint-abhängige Render-Variante einführt.
4. **`labelWidth="w-24"` / `"w-20"` (`:211`, `:242`) — Prop anfassen?** →
   **nur wenn die Messung einen Überlauf zeigt**; dann responsiv als Prop-Wert,
   **nicht** durch Änderung an `DataList` selbst → weil `DataList` ein geteiltes
   Primitive ist und eine Änderung dort alle dreizehn Domänen trifft (eigenes
   Paket).
5. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513; der Overview-Fall wird als Klassen-Assertion belegt
   (welche Klassen an der Zeile hängen), die visuelle Gegenprobe ist W4.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Route der Domäne
      horizontalen Body-Scroll.
- [ ] **Die Posteingangs-Zeile in `FeedbackOverviewPage` ist auf 320 px
      vollständig sichtbar** — die drei festen Breiten (`:172` `w-52`, `:191`
      `min-w-[7.5rem]`, `:217` `w-24`) gelten nur noch oberhalb der
      Mobile-Schwelle oder sind responsiv ersetzt.
- [ ] Die `justify-between`-Zeilen in `FeedbackDetailPage` (`:215`, `:227`,
      `:302`) und `FeedbackItemDetailPage` (`:53`, `:205`, `:245`) brechen auf
      320 px um oder passen vollständig.
- [ ] Mehrspaltige Grids bleiben an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile:
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/feedback | grep -v '\.test\.tsx'
      ```
- [ ] Hit-Targets unterhalb `md` bleiben ≥ 40 px (§11 A11y-Minimum) — geprüft
      an `ResolutionSegments` und den Zeilen-Aktionen im Posteingang.
- [ ] Text bleibt auf 320 px lesbar: Flex-Kinder mit Textinhalt tragen
      `min-w-0`; lange Betreffzeilen und Melder-Adressen brechen um oder kürzen
      kontrolliert.
- [ ] **Alle 6 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 6 Dateien unter `apps/web/src/features/feedback/`, ihre
Testnachbarn, und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter
Commit** — Sammelpunkt).

### Out of scope

`components/ui/*`, `components/layout/*` und `components/data/*` (inkl.
`DataList` und `EntityCard`; W2 hat dort entschieden, eine Änderung wirkt auf
alle dreizehn Domänen und ist ein eigenes Paket) · jede andere Domäne unter
`features/` · W4 (Playwright-Mobile-Profile, E2E-Helfer „kein horizontaler
Body-Scroll") · echter Fullscreen-Dialog unter `sm` (#513 Weiche 3, verworfen) ·
ESLint-Regel für nackte `grid-cols-*` (#438 Weiche 5, verworfen) · jede
inhaltliche Änderung am Feedback-Workflow oder den Resolution-Zuständen ·
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

Tracking: **#431** (W3, Checklisteneintrag „Feedback-Posteingang"). Norm:
`docs/frontend/design-language.md` §4.4 (Mobile-first, Prefix-Pflicht,
sechspunktige Review-Checkliste Z. 222–233), CLAUDE.md §Frontend-Standards.
Vorgänger: **#438** (W0), **#500** (W1 — Schwelle `md`, `useEffect`-freies
Muster), **#513** (W2 — Dialog-Inset, Caps im Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace. Die drei
größten W3-Pakete (`playbooks` 16, `workarea` 14, `personas` 13) laufen nie zu
zweit gleichzeitig.

### Component

Web UI (apps/web)
