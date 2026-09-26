TITEL: W3 Agents: Responsive-Audit von features/agents (10 Dateien)
LABELS: web, agent-ready, size/M
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `agents`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **10 produktive `.tsx`** unter
`apps/web/src/features/agents/`, davon tragen **0** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/agents -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 10
find apps/web/src/features/agents -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;                             # (leer)
```

`agents` ist das **viertgrößte** der dreizehn W3-Pakete und eine der **fünf
Domänen ohne jeden Breakpoint-Prefix** (neben `auth`, `resources`, `tools`,
`workarea`). Anders als bei `auth` gibt es hier **kein dokumentiertes
Mobile-first-Muster**, das die Null erklärt — die Domäne besteht aus zwei sehr
langen Editor-/Abschnitts-Komponenten (612 und 594 Zeilen) und einer
Baumdarstellung, alle ohne jede breakpoint-abhängige Abfederung.

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/agents/components/AgentEditorForm.tsx` (612 Z.) | – | **Die längste Datei der Domäne.** `:77` `flex items-center gap-2` (Feld-/Label-Zeile) ohne `flex-wrap`. Kein Grid, keine feste Breite, **kein `min-w-0`** (gegengeprüft). Zu prüfen: Feldgruppen, Hilfetexte, Validierungsfehler und der Submit-Bereich auf 320 px. |
| `features/agents/components/AgentMemorySection.tsx` (594 Z.) | – | **`:336` `<Select … className="w-24">`** — feste 96 px an einem Auswahlfeld für die Wichtigkeitsstufe, in einer Label-/Feld-Zeile. Auf 320 px zu prüfen (§4.4 Checklistenpunkt 3). `:115` und `:167` zwei `<DialogContent>` **ohne eigene Breitenklasse** → beide erben den W2-Default `w-[calc(100vw-2rem)] max-w-lg` + `max-h`/Scroll, **erfüllt, kein Defekt**. `:492` `flex items-center gap-2` ohne `flex-wrap`. |
| `features/agents/pages/AgentsPage.tsx` (460 Z.) | – | **Kein Klassen-Befund** — kein Grid, keine feste Breite, keine `justify-between`-Zeile, kein `min-w-0`. Zu prüfen: Listeneinträge, Filter/Suche und `PageHeader`-Actions auf 320 px. |
| `features/agents/components/AgentTokensSection.tsx` (316 Z.) | – | `:211` `flex items-center justify-between` **ohne `flex-wrap`** — Label links (`:212`), Zähler rechts (`:213`, `tabular-nums`). Kurzer Inhalt, aber mehrsprachig zu prüfen. Weiter zu prüfen: die Token-Liste selbst — Token-Präfixe und Zeitstempel sind lange, umbruchfeindliche Zeichenketten. |
| `features/agents/components/AgentHierarchyView.tsx` (179 Z.) | – | Die Baumdarstellung. `:55` `flex items-center gap-3 rounded-lg px-2 py-2 …`, `:59` `min-w-0 flex-1`, `:61` `mt-0.5 flex flex-wrap items-center gap-2`, `:64` `min-w-0 truncate` am Namens-Link, `:95` `flex items-center gap-2 rounded-md px-2 py-1.5 text-sm …`, `:98` `min-w-0 flex-1 truncate` — **die einzige Datei der Domäne, die `min-w-0` konsequent führt (3×) und umbricht (`flex-wrap` auf `:61`). Weitgehend erfüllt.** Zu prüfen: **`:95` `px-2 py-1.5 text-sm` ergibt rechnerisch ~32 px Zeilenhöhe — unter dem 40-px-Minimum aus §11** (§4.4 Checklistenpunkt 4), und die Einrückungstiefe bei verschachtelten Agenten auf 320 px. |
| `features/agents/pages/AgentDetailPage.tsx` (132 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Kopfbereich mit Agent-Metadaten und Aktionen auf 320 px. |
| `features/agents/components/CopyPromptButton.tsx` (102 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Hit-Target unterhalb `md`. |
| `features/agents/components/DeleteAgentButton.tsx` (92 Z.) | – | `:66` `<DialogContent>` ohne eigene Breitenklasse → erbt den W2-Default, **erfüllt**. Zu prüfen: Hit-Target und die Bestätigungstexte im Dialog auf 320 px. |
| `features/agents/components/AgentConnectorSection.tsx` (89 Z.) | – | `:54` und `:70` je `flex items-center gap-2` ohne `flex-wrap` — zwei zu prüfende Zeilen mit Connector-Bezeichnern (technische Namen, umbruchfeindlich). |
| `features/agents/components/DuplicateAgentButton.tsx` (65 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Hit-Target unterhalb `md`. |

**Breakpoint-Abdeckung: 0 von 10.**

**Kein `grid-cols-*` in der gesamten Domäne** — einzeln gegengeprüft:

```bash
grep -rnE 'grid-cols-' --include='*.tsx' apps/web/src/features/agents \
  | grep -v '\.test\.tsx'                                                  # (leer)
```

`min-w-0` kommt in der Domäne **genau dreimal** vor, alle drei in
`AgentHierarchyView.tsx` (`:59`, `:64`, `:98`). Die übrigen neun Dateien führen
es **null** Mal — bei Formularen voller technischer Bezeichner (Agent-Namen,
Connector-Aliase, Token-Präfixe) ist das der Hauptkandidat für Textüberlauf.

**Was hier bereits stimmt und nicht wiederholt wird:** die drei
`<DialogContent>`-Aufrufstellen (`:115`, `:167`, `:66`) erben den W2-Inset aus
dem Primitive und brauchen **keine** eigenen Caps; `AgentHierarchyView` führt
`min-w-0` und `flex-wrap` bereits richtig. Die Dialog-/Popover-Caps sitzen seit
W2 im Primitive.

### Proposed solution

**Fertig heißt:** Jede der 10 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; jeder gefundene Defekt ist behoben oder mit Begründung als „kein
Defekt" festgehalten. Kein horizontaler Body-Scroll auf den Routen der Domäne.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive, Aufrufstellen ergänzen keine
eigenen · `cn()` läuft über `tailwind-merge`: zwei Klassen derselben Familie
löschen einander, `w-*` und `max-w-*` nicht.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **`AgentHierarchyView` ist das Vorbild, nicht die Baustelle** → die
   übrigen neun Dateien werden **nach seinem Muster** nachgezogen (`min-w-0`
   am Text tragenden Flex-Kind, `truncate` am Namen, `flex-wrap` an der
   Meta-Zeile) → weil das Muster im Repo bereits existiert und funktioniert;
   ein zweites, abweichendes Muster wäre Pattern Drift.
2. **`AgentMemorySection.tsx:336` (`w-24` am `Select`)** → **responsiv
   abfedern** (`w-20 sm:w-24` oder `w-full sm:w-24`), nicht entfernen → weil
   das Feld nur eine einstellige Stufe zeigt und die feste Breite dem
   Desktop-Layout dient; auf 320 px ist sie zu prüfen. §4.4 Checklistenpunkt 3.
3. **`AgentHierarchyView.tsx:95` (Zeilenhöhe ~32 px)** → **auf ≥ 40 px bringen
   unterhalb `md`**, z. B. über `min-h-10` auf Mobile → weil §11 das
   A11y-Minimum setzt und Baumknoten die primären Navigationsziele der Ansicht
   sind. §4.4 Checklistenpunkt 4.
4. **Die beiden langen Editor-Dateien (612 und 594 Zeilen) aufteilen?** →
   **Nein** → weil das ein Refactoring ist, kein Responsive-Audit. Wer beim
   Prüfen einen Aufteilungsbedarf sieht, notiert ihn als eigenes Paket und
   fasst ihn hier nicht an (Scope-Disziplin; Refactoring läuft über den
   Refactoring-Lauf, nicht über W3).
5. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513 — Klassenwirkung und Rendering werden per Vitest belegt,
   die visuelle Gegenprobe ist W4.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Route der Domäne
      horizontalen Body-Scroll.
- [ ] **Technische Bezeichner brechen um oder kürzen kontrolliert** — Agent-
      Namen, Connector-Aliase (`AgentConnectorSection.tsx:54`/`:70`) und
      Token-Präfixe laufen auf 320 px nicht aus ihrem Container. Flex-Kinder
      mit Textinhalt tragen `min-w-0` nach dem Muster von
      `AgentHierarchyView.tsx:59`/`:98`.
- [ ] `AgentMemorySection.tsx:336` (`w-24`) ist auf 320 px darstellbar —
      responsiv abgefedert oder als unkritisch belegt.
- [ ] **Hit-Targets unterhalb `md` ≥ 40 px** (§11 A11y-Minimum) — geprüft an
      den Baumknoten (`AgentHierarchyView.tsx:95`) und den drei Icon-/Aktions-
      Buttons (`CopyPromptButton`, `DeleteAgentButton`, `DuplicateAgentButton`).
- [ ] Die drei Dialoge (`AgentMemorySection.tsx:115`/`:167`,
      `DeleteAgentButton.tsx:66`) bleiben auf 320 px innerhalb der
      Fensterbreite und scrollen in sich — **über den W2-Primitive-Default,
      ohne eigene Caps an der Aufrufstelle.**
- [ ] `AgentTokensSection.tsx:211` bricht auf 320 px um oder passt vollständig.
- [ ] Mehrspaltige Grids sind an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile (heute wie nachher — die Domäne hat kein `grid-cols-*`):
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/agents | grep -v '\.test\.tsx'
      ```
- [ ] **Alle 10 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 10 Dateien unter `apps/web/src/features/agents/`, ihre Testnachbarn,
und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter Commit** —
Sammelpunkt).

### Out of scope

`components/ui/*` und `components/layout/*` (W2 hat dort entschieden; eine
Änderung wirkt auf alle dreizehn Domänen und ist ein eigenes Paket) · **das
Aufteilen der langen Editor-Dateien** (Refactoring, eigenes Paket) · jede
Änderung an Agent-Datenmodell, Connector-Bindungen oder Token-Semantik · jede
andere Domäne unter `features/` · W4 (Playwright-Mobile-Profile, E2E-Helfer
„kein horizontaler Body-Scroll") · echter Fullscreen-Dialog unter `sm` (#513
Weiche 3, verworfen) · ESLint-Regel für nackte `grid-cols-*` (#438 Weiche 5,
verworfen) · `apps/api`, `apps/mcp`, `packages/**`.

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
AK 7 gibt keine Zeile aus.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen.

### Verweise

Tracking: **#431** (W3, Checklisteneintrag „Agents"). Norm:
`docs/frontend/design-language.md` §4.4 (Mobile-first, Prefix-Pflicht,
sechspunktige Review-Checkliste Z. 222–233) und §11 (A11y-Minimum 40 px),
CLAUDE.md §Frontend-Standards. Vorgänger: **#438** (W0), **#500** (W1 —
Schwelle `md`, `useEffect`-freies Muster), **#513** (W2 — Dialog-Inset, Caps im
Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace. Die drei
größten W3-Pakete (`playbooks` 16, `workarea` 14, `personas` 13) laufen nie zu
zweit gleichzeitig; dieses ist das vierte in der Größenordnung und sollte
ebenfalls nicht neben einem der drei laufen.

### Component

Web UI (apps/web)
