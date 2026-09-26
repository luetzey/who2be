TITEL: W3 Resources: Responsive-Audit von features/resources inkl. BlockNote-Insel (6 Dateien)
LABELS: web, agent-ready, size/S
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `resources`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **6 produktive `.tsx`** unter
`apps/web/src/features/resources/`, davon tragen **0** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/resources -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 6
find apps/web/src/features/resources -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;                             # (leer)
```

`resources` ist eine der **fünf Domänen ohne jeden Breakpoint-Prefix** (neben
`agents`, `auth`, `tools`, `workarea`) — und trägt zugleich die **BlockNote-Insel**,
die #431 in der W3-Checkliste ausdrücklich diesem Paket zuweist: „Resources
inkl. BlockNote-Insel (Toolbar/Slash-Menü auf Touch)". Das ist der inhaltlich
anspruchsvollste Teil des Pakets und der einzige Punkt der dreizehn, bei dem
eine Fremdbibliothek die Touch-Bedienbarkeit bestimmt.

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/resources/pages/ResourceDetailPage.tsx` (416 Z.) | – | `Container` (`:118`–`:414`), `DataList` (`:316`), `:322` `flex items-center justify-between gap-3` **ohne `flex-wrap`** — zu prüfender Fall bei langem Schlüssel/Wert-Paar auf 320 px. **Hier sitzt die BlockNote-Insel** (Editor-Einbettung); ihre Toolbar und das Slash-Menü sind auf Touch zu prüfen. |
| `features/resources/components/SubResourcePicker.tsx` (338 Z.) | – | Der dichteste Kandidat: `:175` `flex items-center gap-3 …`, `:207` `flex items-center gap-2 …`, `:217` `inline-flex overflow-hidden rounded-md border` (Segment-Gruppe), `:305` `flex max-h-72 flex-col gap-1 overflow-auto`. Trägt `min-w-0` an drei Stellen (`:178`, `:213`, `:319`) — **erfüllt** für den Texteinlauf. Zu prüfen: die Segment-Gruppe `:217` und die Zeilen-Aktionen bei 320 px. |
| `features/resources/pages/ResourcesPage.tsx` (273 Z.) | – | `Container` (`:179`), `PageHeader` (`:181`), `EntityCard` (`:119`); `:53` `flex items-center gap-3 rounded-lg border …` als Kind-Eintrag, `:58` trägt `min-w-0 flex-1 truncate` — **erfüllt**. `:261` `flex items-center gap-2 text-sm font-semibold` (Abschnittsüberschrift). Zu prüfen: `EntityCard`-Meta bei 320 px. |
| `features/resources/components/ResourceEditorForm.tsx` (172 Z.) | – | **Kein Klassen-Befund** — kein Grid, keine feste Breite, keine `justify-between`-Zeile. Zu prüfen: Feld-Labels, Hilfetexte und die Submit-Zeile bei 320 px. |
| `features/resources/pages/ResourceNewPage.tsx` (62 Z.) | – | `Container` (`:28`), `PageHeader` (`:36`). **Kein Klassen-Befund.** |
| `features/resources/components/ResourceUsedByList.tsx` (34 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: lange Verwender-Namen in der Liste auf 320 px. |

**Breakpoint-Abdeckung: 0 von 6.**

**Kein `grid-cols-*` in der gesamten Domäne** — einzeln gegengeprüft:

```bash
grep -rnE 'grid-cols-' --include='*.tsx' apps/web/src/features/resources \
  | grep -v '\.test\.tsx'                                                  # (leer)
```

**Was hier bereits stimmt und nicht wiederholt wird:** `SubResourcePicker`
trägt `min-w-0` an allen drei Texteinläufen; `ResourcesPage.tsx:58` ebenso; der
Scroll-Container `:305` ist mit `max-h-72 … overflow-auto` bewusst gesetzt —
ein bewusst scrollender Container nach §4.4 Checklistenpunkt 1, **kein Defekt**.
Die Dialog-/Popover-Caps sitzen seit W2 im Primitive.

### Proposed solution

**Fertig heißt:** Jede der 6 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; **die BlockNote-Insel ist auf einem Touch-Gerät bzw. im
Touch-Emulationsmodus bedient** — Toolbar erreichbar, Slash-Menü auslösbar und
innerhalb des Viewports, Basis-Editing (Text, Überschrift, Liste) möglich.
Jeder gefundene Defekt ist behoben oder mit Begründung als „kein Defekt"
festgehalten. Kein horizontaler Body-Scroll auf den Routen der Domäne.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive · `cn()` läuft über `tailwind-merge`.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **Wie weit geht das BlockNote-Ziel auf dem Phone?** → **Tablet voll
   bedienbar, Phone mindestens lesbar plus Basis-Editing (Text, Überschrift,
   Liste)** → weil #431 genau das als Akzeptanzkriterium formuliert. Ein
   vollwertiger Editor auf 320 px ist ausdrücklich **nicht** das Ziel.
2. **BlockNote-CSS überschreiben oder Container abfedern?** → **erst Container,
   Overrides nur wo gemessen nötig** → weil Overrides in fremde
   Bibliotheks-Interna greifen und bei jedem Upgrade brechen. Ein gemessener
   Überlauf der Toolbar rechtfertigt einen gezielten Override; ein vermuteter
   nicht.
3. **`SubResourcePicker.tsx:217` (Segment-Gruppe, `inline-flex
   overflow-hidden`) — umbrechen oder scrollen lassen?** → **entscheidet die
   Messung**; falls die Gruppe auf 320 px überläuft, ist ein bewusst
   scrollender Container die Wahl, **nicht** ein Umbruch → weil eine
   umbrechende Segment-Gruppe ihre visuelle Einheit verliert und §4.4
   Checklistenpunkt 1 bewusst gescrollte Container ausdrücklich zulässt.
4. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513. Für die BlockNote-Insel gilt: Vitest belegt Klassen und
   Rendering, die Touch-Bedienbarkeit belegt ein manueller Durchgang bzw. W4 —
   **das wird im PR ausdrücklich so benannt, nicht als Test verkauft.**

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Route der Domäne
      horizontalen Body-Scroll (ausgenommen der bewusst scrollende Container
      `SubResourcePicker.tsx:305`, der als solcher benannt ist).
- [ ] **BlockNote-Insel:** auf dem Tablet (768 px) voll bedienbar; auf dem
      Phone (320/375 px) lesbar, Toolbar erreichbar und im Viewport,
      Slash-Menü auslösbar, Basis-Editing (Text, Überschrift, Liste) möglich.
      **Der Nachweis wird am gerenderten Editor geführt, nicht an Klassen.**
- [ ] `ResourceDetailPage.tsx:322` (`justify-between` ohne `flex-wrap`) bricht
      auf 320 px um oder kürzt kontrolliert.
- [ ] Mehrspaltige Grids sind an einen Breakpoint-Prefix gebunden. Gate,
      liefert **keine** Zeile (heute wie nachher):
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/resources | grep -v '\.test\.tsx'
      ```
- [ ] Hit-Targets unterhalb `md` bleiben ≥ 40 px (§11 A11y-Minimum) — geprüft
      an den Zeilen-Aktionen in `SubResourcePicker` und der Segment-Gruppe
      `:217`.
- [ ] Text bleibt auf 320 px lesbar: Flex-Kinder mit Textinhalt tragen
      `min-w-0`. **Heute erfüllt an `SubResourcePicker.tsx:178`/`:213`/`:319`
      und `ResourcesPage.tsx:58`** — das bleibt so.
- [ ] **Alle 6 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 6 Dateien unter `apps/web/src/features/resources/`, ihre
Testnachbarn, bei gemessenem Bedarf gezielte CSS-Overrides für die
BlockNote-Insel im Editor-Container, und `CHANGELOG.md` (§Unreleased, ein
Eintrag, **als letzter Commit** — Sammelpunkt).

### Out of scope

`components/editor/*` außerhalb des Resource-Editors (dort liegt u. a. die
System-Prompt-Insel — eigenes W3-Paket) · `components/ui/*` und
`components/layout/*` (W2 hat dort entschieden) · ein Upgrade oder Austausch
von BlockNote selbst · jede andere Domäne unter `features/` · W4
(Playwright-Mobile-Profile, E2E-Helfer „kein horizontaler Body-Scroll") ·
echter Fullscreen-Dialog unter `sm` (#513 Weiche 3, verworfen) · ESLint-Regel
für nackte `grid-cols-*` (#438 Weiche 5, verworfen) · `apps/api`, `apps/mcp`,
`packages/**`.

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
AK 4 gibt keine Zeile aus. **Dazu der manuelle BlockNote-Durchgang** auf
320/375/768 px, im PR mit dem Ergebnis benannt — er ist Teil der Verifikation
und wird nicht durch einen grünen Vitest-Lauf ersetzt.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen.

### Verweise

Tracking: **#431** (W3, Checklisteneintrag „Resources inkl. BlockNote-Insel
(Toolbar/Slash-Menü auf Touch)"). Norm: `docs/frontend/design-language.md` §4.4
(Mobile-first, Prefix-Pflicht, sechspunktige Review-Checkliste Z. 222–233),
CLAUDE.md §Frontend-Standards. Vorgänger: **#438** (W0), **#500** (W1 —
Schwelle `md`, `useEffect`-freies Muster), **#513** (W2 — Dialog-Inset, Caps im
Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace. Die drei
größten W3-Pakete (`playbooks` 16, `workarea` 14, `personas` 13) laufen nie zu
zweit gleichzeitig.

### Component

Web UI (apps/web)
