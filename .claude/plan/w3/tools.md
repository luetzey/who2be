TITEL: W3 Tools: Responsive-Audit von features/tools (4 Dateien)
LABELS: web, agent-ready, size/S
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `tools`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **4 produktive `.tsx`** unter
`apps/web/src/features/tools/`, davon tragen **0** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/tools -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 4
find apps/web/src/features/tools -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;                             # (leer)
```

`tools` ist mit 4 Dateien das **kleinste** der dreizehn W3-Pakete nach
`billing` — und eines der fünf ohne jeden Breakpoint-Prefix (neben `agents`,
`auth`, `resources`, `workarea`).

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

**Null Prefixe ist hier kein Automatismus für „defekt".** Die Domäne ist
durchgehend einspaltig gebaut — jede gemessene Flex-Achse ist `flex-col`, es
gibt kein einziges `grid-cols-*`, keine feste Breite und keine
`justify-between`-Zeile. Eine einspaltige Seite **braucht** keinen Prefix. Was
dieses Paket prüft, ist deshalb nicht die Klassenliste, sondern der gerenderte
Inhalt bei 320 px: die Layout-Primitives, die Formularfelder und die Aktionen.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/tools/pages/ToolsPage.tsx` (174 Z.) | – | Liste über `Container` (`:64`), `PageHeader` (`:66`) und `EntityCard` (`:130`); Kinder-`<ul>` auf `:124` ist `flex flex-col gap-3`. **Kein Klassen-Befund.** Zu prüfen: `EntityCard`-Meta-Zeilen und die `PageHeader`-Actions bei 320 px — beide Primitives tragen bereits `flex-wrap` (`components/layout/PageHeader.tsx:37`), der Nachweis am gerenderten Fall fehlt. |
| `features/tools/pages/ToolDetailPage.tsx` (297 Z.) | – | `Container` (`:99`–`:295`); `:251` `flex flex-col gap-3 px-4 pb-4`. **Kein Klassen-Befund.** Zu prüfen: Detail-Metadaten (Tool-Alias, MCP-Server-Name, Tool-Bezeichner) sind lange, umbruchfeindliche Bezeichner — der Kandidat für Überlauf auf 320 px. |
| `features/tools/components/ToolEditorForm.tsx` (234 Z.) | – | `:64` `flex flex-col gap-6`. **Kein Klassen-Befund.** Zu prüfen: Feld-Labels, Hilfetexte und die Submit-Zeile bei 320 px. |
| `features/tools/pages/ToolNewPage.tsx` (61 Z.) | – | `Container` (`:28`), `PageHeader` (`:36`), `:44` `flex flex-col gap-3`, `:46` `flex justify-end`. **Kein Klassen-Befund** — eine einzelne rechtsbündige Aktion läuft auf 320 px nicht über. |

**Kein Grid, keine feste Breite, keine `justify-between`-Zeile in der gesamten
Domäne** — einzeln gegengeprüft:

```bash
grep -rnE 'grid-cols-|w-\[|min-w-[0-9[]|max-w-[a-z0-9[]|justify-between' \
  --include='*.tsx' apps/web/src/features/tools | grep -v '\.test\.tsx'   # (leer)
```

**Was hier bereits stimmt und nicht wiederholt wird:** `Container`
(`components/layout/Container.tsx:6`, `mx-auto w-full max-w-5xl px-4 py-6
sm:px-6`) federt die Seitenbreite bereits ab; `PageHeader.tsx:24` ist
`flex-col … sm:flex-row` und seine Actions-Zeile `:37` trägt `flex-wrap`. Die
Dialog-/Popover-Caps sitzen seit W2 im Primitive.

### Proposed solution

**Fertig heißt:** Jede der 4 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; jeder gefundene Defekt ist behoben oder mit Begründung als „kein
Defekt" im Issue festgehalten. Kein horizontaler Body-Scroll auf den Routen der
Domäne (`/tools`, `/tools/new`, `/tools/:id`).

**Erwartung ehrlich benannt:** Dies ist das Paket mit der geringsten
Defekt-Wahrscheinlichkeit der dreizehn. Ein Ergebnis „vier Dateien geprüft,
null Defekte, hier die Belege" ist ein **gültiges** Ergebnis und kein
Fehlschlag — es darf nur nicht behauptet, sondern muss gezeigt werden
(Queue-Regel 22: neu messen, nicht abhaken).

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive · `cn()` läuft über `tailwind-merge`.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **Prefixe nachrüsten, weil null Prefixe auffällig sind?** → **Nein, nur wo
   ein Defekt gemessen ist** → weil §4.4 Mobile-first vorschreibt: die
   präfixlose Klasse **ist** der Phone-Fall. Ein `sm:`-Prefix ohne Defekt wäre
   Ballast, kein Fortschritt.
2. **Was ist bei 320 px der wahrscheinliche Fund?** → **lange, umbruchfeindliche
   Bezeichner in der Detailansicht** (Tool-Alias, MCP-Server-Name) → weil die
   Domäne genau daraus besteht und `min-w-0` in der gesamten Domäne **null**
   Mal vorkommt (gegengeprüft). Gegenmittel ist `min-w-0` + `truncate` bzw.
   `break-words`, nicht ein Breakpoint.
3. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513 → weil jede Änderung an dieser Domäne test-first belegt
   werden muss und die Coverage-Thresholds (`vite.config.ts:49-53`,
   Branches-Floor 79) sonst kippen können.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine der drei Routen der Domäne
      horizontalen Body-Scroll.
- [ ] Mehrspaltige Grids sind an einen Breakpoint-Prefix gebunden. Gate,
      liefert **keine** Zeile (heute wie nachher):
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/tools | grep -v '\.test\.tsx'
      ```
- [ ] Feste Breiten auf Container-Ebene sind responsiv abgefedert. **Heute gibt
      es keine** — wird eine eingeführt, trägt sie einen Prefix.
- [ ] Hit-Targets unterhalb `md` bleiben ≥ 40 px (§11 A11y-Minimum) — geprüft
      an den Aktionen in `ToolsPage.tsx` und `ToolDetailPage.tsx`.
- [ ] Text bleibt auf 320 px lesbar: Flex-Kinder mit Textinhalt tragen
      `min-w-0`, lange Bezeichner brechen um oder kürzen kontrolliert.
- [ ] **Alle 4 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 4 Dateien unter `apps/web/src/features/tools/`, ihre Testnachbarn,
und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter Commit** —
Sammelpunkt).

### Out of scope

`components/ui/*` und `components/layout/*` (W2 hat dort entschieden; eine
Änderung an `Container`, `PageHeader` oder `EntityCard` wirkt auf alle dreizehn
Domänen und ist ein eigenes Paket) · jede andere Domäne unter `features/` · W4
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
AK 2 gibt keine Zeile aus.

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
zweit gleichzeitig; dieses hier ist klein genug, um daneben zu passen.

### Component

Web UI (apps/web)
