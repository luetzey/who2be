TITEL: W3 System Prompts: Responsive-Audit von features/system-prompts (7 Dateien)
LABELS: web, agent-ready, size/S
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `system-prompts`. Die Domäne
ist auf `main` @ `87de64c` einzeln nachgemessen: **7 produktive `.tsx`** unter
`apps/web/src/features/system-prompts/`, davon trägt **1** einen
Breakpoint-Prefix.

```bash
find apps/web/src/features/system-prompts -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 7
find apps/web/src/features/system-prompts -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;    # nur components/PlaceholderHelp.tsx
```

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

**Die Domäne trägt die einzige verbliebene ungecappte Popover-Aufrufstelle
aus der W2-Messung** — `PlaceholderHelp.tsx:121` mit `w-96` (384 px). In #513
war das der **belegte Defektfall** auf 320 px. Seit W2 greift der
Primitive-Default `max-w-[calc(100vw-1rem)]` darüber, weil `w-*` und `max-w-*`
verschiedene `tailwind-merge`-Familien sind und einander nicht auslöschen.
**Das ist damit erfüllt und wird hier nicht wiederholt** — wohl aber am
gerenderten Popover nachgewiesen, statt abgehakt (Queue-Regel 22).

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/system-prompts/components/PlaceholderHelp.tsx` (136 Z.) | **ja** (1) | `:87` `grid grid-cols-1 gap-1 sm:grid-cols-[10rem_1fr]` — **erfüllt**, mobile-first gebunden (einspaltig unter `sm`, Zwei-Spalten-Definitionsliste darüber). `:121` `max-h-[70vh] w-96 overflow-auto` am `PopoverContent`: 384 px fest, **gecappt durch den W2-Primitive-Default** `max-w-[calc(100vw-1rem)]` (`components/ui/popover.tsx`). **Erfüllt — nachzuweisen, nicht zu ändern.** `:89` `flex items-center gap-1.5 font-mono text-xs` — Platzhalternamen in Monospace, Kandidat für Überlauf bei langen Namen. |
| `features/system-prompts/components/SystemPromptEditorForm.tsx` (155 Z.) | – | `:123` `flex items-center justify-between` **ohne `flex-wrap`** — zu prüfender Fall auf 320 px (Label links, Aktion/Schalter rechts). |
| `features/system-prompts/pages/SystemPromptNewPage.tsx` (169 Z.) | – | `:142` `flex items-center justify-between` **ohne `flex-wrap`** — derselbe Fall wie oben, zweite Fundstelle. |
| `features/system-prompts/pages/SystemPromptDetailPage.tsx` (152 Z.) | – | **Kein Klassen-Befund** — kein Grid, keine feste Breite, keine `justify-between`-Zeile. Zu prüfen: Versionsmetadaten und die Prompt-Vorschau bei 320 px. |
| `features/system-prompts/pages/SystemPromptsPage.tsx` (148 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Listeneinträge und `PageHeader`-Actions bei 320 px. |
| `features/system-prompts/components/SystemPromptStatusActionBar.tsx` (102 Z.) | – | **Kein Klassen-Befund.** Die Domänen-Variante der Status-Aktionsleiste. Zu prüfen: ob die Aktionen auf 320 px umbrechen. **Hinweis:** die generische `components/version/StatusActionBar.tsx` ist **nicht** Teil dieses Pakets (siehe Out of scope). |
| `features/system-prompts/pages/HelpPlaceholdersPage.tsx` (42 Z.) | – | **Kein Klassen-Befund** — dünne Seite über `Container` (`:22`). |

**Breakpoint-Abdeckung: 1 von 7.**

**Was hier bereits stimmt und nicht wiederholt wird:** das Definitionslisten-
Grid auf `:87` ist mobile-first gebunden; der `w-96`-Popover ist seit W2 durch
das Primitive gecappt; `Container` federt die Seitenbreite bereits ab
(`components/layout/Container.tsx:6`).

### Proposed solution

**Fertig heißt:** Jede der 7 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; jeder gefundene Defekt ist behoben oder mit Begründung als „kein
Defekt" festgehalten. Kein horizontaler Body-Scroll auf den Routen der Domäne.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive, Aufrufstellen ergänzen keine
eigenen · `cn()` läuft über `tailwind-merge`: zwei Klassen derselben Familie
löschen einander, `w-*` und `max-w-*` nicht — **genau daran hängt, dass
`PlaceholderHelp.tsx:121` heute gecappt ist.**

#### Vorentschieden (Frage → Entscheidung → weil)

1. **`PlaceholderHelp.tsx:121` (`w-96`) auf einen kleineren Wert setzen?** →
   **Nein** → weil der Primitive-Default aus W2 die Breite bereits auf
   `calc(100vw-1rem)` deckelt und ein zweiter Cap an der Aufrufstelle genau
   die Doppelpflege wäre, die #513 Weiche 1 verworfen hat. **Nachweisen, nicht
   ändern.**
2. **Die zwei `justify-between`-Zeilen (`SystemPromptEditorForm.tsx:123`,
   `SystemPromptNewPage.tsx:142`) — `flex-wrap` oder Umbau?** → **`flex-wrap`**
   → weil das dem Repo-Muster folgt (`PageHeader.tsx:37`) und keine zweite,
   breakpoint-abhängige Render-Variante einführt.
3. **Lange Platzhalternamen in Monospace (`:89`) — umbrechen oder kürzen?** →
   **kontrolliert kürzen** (`min-w-0` + `truncate`), nicht umbrechen → weil ein
   umgebrochener Platzhaltername (`{{…}}`) nicht mehr als ein Token lesbar ist
   und die Hilfe damit ihren Zweck verliert. Der vollständige Name bleibt über
   `title`/Tooltip erreichbar.
4. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513 — dort ist auch `popover.test.tsx` entstanden, an dem
   sich der Cap-Nachweis für `:121` orientieren kann.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Route der Domäne
      horizontalen Body-Scroll.
- [ ] **Das Platzhalter-Hilfe-Popover (`PlaceholderHelp.tsx:121`) bleibt auf
      320 px innerhalb der Fensterbreite** — nachgewiesen am gerenderten
      Popover, nicht per Klassen-Behauptung. Die `w-96`-Klasse an der
      Aufrufstelle bleibt unverändert.
- [ ] Die beiden `justify-between`-Zeilen (`SystemPromptEditorForm.tsx:123`,
      `SystemPromptNewPage.tsx:142`) brechen auf 320 px um oder passen
      vollständig.
- [ ] Mehrspaltige Grids bleiben an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile:
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/system-prompts | grep -v '\.test\.tsx'
      ```
- [ ] Hit-Targets unterhalb `md` bleiben ≥ 40 px (§11 A11y-Minimum) — geprüft
      an `SystemPromptStatusActionBar` und den Listen-Aktionen.
- [ ] Text bleibt auf 320 px lesbar: Platzhalternamen und Prompt-Vorschauen
      brechen um oder kürzen kontrolliert; Flex-Kinder mit Textinhalt tragen
      `min-w-0` (heute **null** Vorkommen in der Domäne — gegengeprüft).
- [ ] **Alle 7 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 7 Dateien unter `apps/web/src/features/system-prompts/`, ihre
Testnachbarn, und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter
Commit** — Sammelpunkt).

### Out of scope

`components/ui/*` (insbesondere `popover.tsx` — W2 hat dort entschieden, der
Cap bleibt im Primitive) · `components/editor/system-prompt/*` (die
Platzhalter-Blöcke des Editors liegen außerhalb von `features/` und sind
eigenes Paket; dort liegt auch `PlaceholderBlock.test-utils.tsx`, einer der
drei Test-Helfer aus der Ausschluss-Regel) · **`components/version/StatusActionBar.tsx`**
(die Bottom-Bar-Aufwertung ist aus W2 verschoben, braucht einen eigenen
Design-Beschluss und liegt nicht unter `features/` — sie bleibt offener Punkt
an #431) · jede andere Domäne unter `features/` · W4 (Playwright-Mobile-Profile,
E2E-Helfer „kein horizontaler Body-Scroll") · echter Fullscreen-Dialog unter
`sm` (#513 Weiche 3, verworfen) · ESLint-Regel für nackte `grid-cols-*` (#438
Weiche 5, verworfen) · `apps/api`, `apps/mcp`, `packages/**`.

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

Tracking: **#431** (W3, Checklisteneintrag „System Prompts"). Norm:
`docs/frontend/design-language.md` §4.4 (Mobile-first, Prefix-Pflicht,
sechspunktige Review-Checkliste Z. 222–233), CLAUDE.md §Frontend-Standards.
Vorgänger: **#438** (W0), **#500** (W1 — Schwelle `md`, `useEffect`-freies
Muster), **#513** (W2 — Dialog-Inset, Caps im Primitive, `tailwind-merge`;
`PlaceholderHelp.tsx:121` war dort der belegte Defektfall).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace. Die drei
größten W3-Pakete (`playbooks` 16, `workarea` 14, `personas` 13) laufen nie zu
zweit gleichzeitig.

### Component

Web UI (apps/web)
