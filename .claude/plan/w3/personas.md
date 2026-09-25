TITEL: W3 Personas: Responsive-Audit von features/personas (13 Dateien)
LABELS: web, agent-ready, size/M
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `personas`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **13 produktive `.tsx`** unter
`apps/web/src/features/personas/`, davon trägt **1** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/personas -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 13
find apps/web/src/features/personas -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;    # nur components/PersonaModesEditor.tsx
```

`personas` ist das **drittgrößte** der dreizehn W3-Pakete (nach `playbooks` 16
und `workarea` 14) und trägt mit `PersonaModesEditor` den Editor, den #431 in
der W3-Checkliste ausdrücklich diesem Paket zuweist („Personas (inkl.
`PersonaModesEditor`)"). Zwölf von dreizehn Dateien tragen keinen einzigen
Breakpoint-Prefix — **die eine Ausnahme ist genau der genannte Editor.**

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/personas/components/PersonaModesEditor.tsx` (378 Z.) | **ja** (1) | **Der Schwerpunkt des Pakets.** `:328` `grid gap-4 sm:grid-cols-2` — **erfüllt**, mobile-first gebunden (Trigger/Identität nebeneinander erst ab 640 px). `:274` `flex items-center justify-between gap-2` als Modus-Kopfzeile, `:275` `flex min-w-0 items-center gap-2` — Texteinlauf **erfüllt**; `:277` `size-7 flex-none` Nummernchip; `:287` `flex items-center gap-2` mit `size="sm"`-Aktionen (`:292`, `:303`) **ohne `flex-wrap`** — zu prüfender Fall auf 320 px, wenn Nummer, Modusname, Default-Badge und zwei Aktionen auf einer Zeile stehen. **Hit-Target der `size="sm"`-Buttons unterhalb `md` zu prüfen** (§11, §4.4 Checklistenpunkt 4). |
| `features/personas/pages/PersonaDetailPage.tsx` (335 Z.) | – | **Kein Klassen-Befund** — kein Grid, keine feste Breite, keine `justify-between`-Zeile, kein `min-w-0`. Zu prüfen: Persona-Metadaten, Modus-Übersicht und Aktionen auf 320 px. |
| `features/personas/components/PersonaPlaybooksCard.tsx` (391 Z.) | – | Die längste Datei der Domäne. `:96` `flex items-center gap-3 rounded-lg border …` (Playbook-Eintrag), `:98` `size-6 shrink-0` Chip, `:101` `min-w-0 flex-1 truncate` — **erfüllt** für den Texteinlauf. `:265` `CardHeader` `flex-row items-center justify-between gap-2 space-y-0` **ohne `flex-wrap`**, `:266` `CardTitle` `flex items-center gap-2` — zu prüfender Fall. |
| `features/personas/components/PersonaProfileFields.tsx` (250 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Feldgruppen des Persona-Profils (Identität, Ton, Allowed/Forbidden) und deren mehrzeilige Textfelder auf 320 px. |
| `features/personas/components/PersonaProfileEditor.tsx` (203 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Editor-Rahmen und Speichern-Leiste auf 320 px. |
| `features/personas/pages/PersonasPage.tsx` (180 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Listeneinträge und `PageHeader`-Actions auf 320 px. |
| `features/personas/components/PersonaEditorForm.tsx` (149 Z.) | – | `:44` `flex items-center gap-2` ohne `flex-wrap`. Sonst kein Klassen-Befund. |
| `features/personas/components/PersonaSkillsEditor.tsx` (135 Z.) | – | `:69` `flex items-center justify-between gap-2` **ohne `flex-wrap`** — Skill-Zeile mit Aktion rechts; zu prüfender Fall bei langen Skill-Namen. |
| `features/personas/components/PlaybookLinkItem.tsx` (105 Z.) | – | `:84` `<li className="flex items-center gap-3 px-3 py-2">`, `:86` `flex min-w-0 flex-1 flex-wrap items-center gap-2` — **erfüllt**: bricht um und trägt `min-w-0`. Zu prüfen: `px-3 py-2` ergibt rechnerisch ~36 px Zeilenhöhe — **unter dem 40-px-Minimum aus §11**, wenn die Zeile klickbar ist. |
| `features/personas/components/PersonaSkillsTable.tsx` (58 Z.) | – | Zweispaltige Tabelle über das `Table`-Primitive (`:37`ff). Der horizontale Wrapper sitzt im Primitive (`components/ui/table.tsx:14`, `relative w-full overflow-auto`) — **erfüllt, kein Defekt**. **`:40` `<TableHead className="w-1/3">`** — Prozentbreite, keine feste px-Breite; auf 320 px sind das ~107 px für die Skill-Spalte. Zu prüfen, ob Skill-Name und Hinweistext dort noch lesbar sind. |
| `features/personas/components/PersonaModesPanel.tsx` (47 Z.) | – | `:32` `flex items-center gap-3`, `:34` `min-w-0` — **erfüllt** für den Texteinlauf. Zu prüfen: Modus-Zusammenfassung auf 320 px. |
| `features/personas/components/SkillsComingSoon.tsx` (45 Z.) | – | `:26` und `:36` je `flex items-center gap-2` ohne `flex-wrap`. Dünne Platzhalter-Komponente; geringes Risiko. |
| `features/personas/pages/PersonaNewPage.tsx` (62 Z.) | – | **Kein Klassen-Befund** — dünne Seite. |

**Breakpoint-Abdeckung: 1 von 13.**

**Genau ein `grid-cols-*` in der gesamten Domäne, und es ist gebunden** —
einzeln gegengeprüft:

```bash
grep -rnE 'grid-cols-' --include='*.tsx' apps/web/src/features/personas \
  | grep -v '\.test\.tsx'
# PersonaModesEditor.tsx:328:  grid gap-4 sm:grid-cols-2
```

**Was hier bereits stimmt und nicht wiederholt wird:** das Modus-Grid ist
mobile-first gebunden; `min-w-0` sitzt an fünf Stellen richtig
(`PersonaModesEditor.tsx:275`, `PersonaPlaybooksCard.tsx:101`,
`PersonaModesPanel.tsx:34`, `PlaybookLinkItem.tsx:86`, plus die
Truncate-Varianten); `PlaybookLinkItem.tsx:86` bricht bereits um; der
Tabellen-Wrapper sitzt im `Table`-Primitive. Die Dialog-/Popover-Caps sitzen
seit W2 im Primitive.

### Proposed solution

**Fertig heißt:** Jede der 13 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; **`PersonaModesEditor` ist auf 320 px vollständig bedienbar** — Modus
anlegen, umbenennen, als Default setzen, löschen. Jeder gefundene Defekt ist
behoben oder mit Begründung als „kein Defekt" festgehalten. Kein horizontaler
Body-Scroll auf den Routen der Domäne.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive · `cn()` läuft über `tailwind-merge`.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **`PersonaModesEditor.tsx:274`/`:287` — Kopfzeile umbrechen oder Aktionen
   in ein Menü?** → **umbrechen (`flex-wrap`)**, kein Overflow-Menü → weil ein
   Menü eine zweite Interaktionsebene einführt und §4.4 Checklistenpunkt 5
   Umbruch als Mittel der Wahl nennt. Ein Overflow-Menü wäre eine
   Designentscheidung ohne gemessenen Bedarf.
2. **`size="sm"`-Aktionen im Modus-Kopf (`:292`, `:303`) und die Zeilenhöhe in
   `PlaybookLinkItem.tsx:84`** → **auf ≥ 40 px bringen unterhalb `md`** → weil
   §11 das A11y-Minimum setzt; beide liegen rechnerisch bei ~32–36 px. §4.4
   Checklistenpunkt 4 nennt die `size="sm"`-Verdichtung ausdrücklich.
3. **`PersonaSkillsTable.tsx:40` (`w-1/3`) — anfassen?** → **nur bei gemessener
   Unlesbarkeit**; dann als Prozentwert oberhalb der Mobile-Schwelle
   (`sm:w-1/3`), nicht als feste px-Breite → weil eine Prozentbreite anders als
   `w-64` bereits mitskaliert und §4.4 Checklistenpunkt 3 auf feste Breiten
   zielt. Gemessen wird mit dem längsten realen Skill-Namen.
4. **`PersonaModesEditor.tsx:328` (`sm:grid-cols-2`) anfassen?** → **Nein** →
   weil es die §4.4-Regel bereits erfüllt; ein zusätzlicher `md:`-Schritt wäre
   eine Designentscheidung ohne Defekt.
5. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513 — der `PersonaModesEditor` ist die am dichtesten
   getestete Komponente der Domäne und der natürliche Ort für die
   Klassen-Assertions.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Route der Domäne
      horizontalen **Body**-Scroll. Die Skills-Tabelle scrollt in ihrem eigenen
      Wrapper — das ist zulässig und als solches benannt.
- [ ] **`PersonaModesEditor` ist auf 320 px vollständig bedienbar:** Modus
      anlegen, umbenennen, als Default markieren, löschen; die Kopfzeile
      (`:274`) bricht um statt überzulaufen.
- [ ] **Hit-Targets unterhalb `md` ≥ 40 px** (§11 A11y-Minimum) — geprüft an
      den `size="sm"`-Aktionen im Modus-Kopf und an `PlaybookLinkItem.tsx:84`.
- [ ] `PersonaPlaybooksCard.tsx:265` (`CardHeader`, `justify-between` ohne
      `flex-wrap`) und `PersonaSkillsEditor.tsx:69` brechen auf 320 px um oder
      passen vollständig.
- [ ] Lange Persona-, Modus-, Playbook- und Skill-Namen brechen um oder kürzen
      kontrolliert — Flex-Kinder mit Textinhalt tragen `min-w-0` nach dem
      bestehenden Muster.
- [ ] Mehrspaltige Grids bleiben an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile:
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/personas | grep -v '\.test\.tsx'
      ```
- [ ] **Alle 13 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 13 Dateien unter `apps/web/src/features/personas/`, ihre
Testnachbarn, und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter
Commit** — Sammelpunkt).

### Out of scope

`components/ui/*` und `components/layout/*` (inkl. `table.tsx` — W2 hat dort
entschieden; eine Änderung wirkt auf alle dreizehn Domänen und ist ein eigenes
Paket) · jede Änderung am Persona-Datenmodell, an der Modus-Semantik oder am
Skills-Konzept · jede andere Domäne unter `features/` · W4
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
AK 6 gibt keine Zeile aus.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen.

### Verweise

Tracking: **#431** (W3, Checklisteneintrag „Personas (inkl.
`PersonaModesEditor`)"). Norm: `docs/frontend/design-language.md` §4.4
(Mobile-first, Prefix-Pflicht, sechspunktige Review-Checkliste Z. 222–233) und
§11 (A11y-Minimum 40 px), CLAUDE.md §Frontend-Standards. Vorgänger: **#438**
(W0), **#500** (W1 — Schwelle `md`, `useEffect`-freies Muster), **#513** (W2 —
Dialog-Inset, Caps im Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace. **`personas`
ist mit 13 Dateien das drittgrößte der dreizehn W3-Pakete — die drei größten
(`playbooks` 16, `workarea` 14, `personas` 13) laufen nie zu zweit
gleichzeitig.**

### Component

Web UI (apps/web)
