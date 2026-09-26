TITEL: W3 WorkArea: Responsive-Audit von features/workarea (14 Dateien)
LABELS: web, agent-ready, size/M
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `workarea`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **14 produktive `.tsx`** unter
`apps/web/src/features/workarea/`, davon tragen **0** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/workarea -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 14
find apps/web/src/features/workarea -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;                             # (leer)
```

> **Achtung, hier hängt der Zähler:** `features/workarea/test-utils.tsx` ist
> Test-Infrastruktur, heißt aber nicht `*.test.tsx`. Ein naives
> `! -name '*.test.tsx'` liefert in dieser Domäne **15** statt 14 und in der
> Gesamtsumme 108 statt 107. **Diese Domäne ist der Grund, warum der Ausschluss
> dreiteilig ist** (`-name '*.test.tsx' -o -name '*test-utils*' -o -path
> '*/test/*'`, Queue-Regel 51). Ebenso gilt: `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` (386 gegen 383, Queue-Regel 48).

`workarea` ist das **zweitgrößte** der dreizehn W3-Pakete, eine der **fünf
Domänen ohne jeden Breakpoint-Prefix** — und die Domäne mit der höchsten
Datendichte: Tabellen mit beliebig vielen Spalten, eine Knowledge-Base-Suche,
Artefakt-Ansichten mit Rohtext.

### Zwei Nicht-Befunde, die vorab feststehen

**Beides wurde in früheren Läufen falsch als Defekt geführt und wird hier
ausdrücklich nicht erneut gesucht:**

1. **`TableDetailPage` hat keinen Defekt beim Tabellen-Wrapper.** Der
   horizontale Scroll sitzt im `Table`-Primitive — `components/ui/table.tsx:14`,
   `relative w-full overflow-auto` — und an der Aufrufstelle steht seit W2 ein
   erklärender Kommentar (`TableDetailPage.tsx:223-225`: „Der horizontale
   Scroll steckt im `Table`-Primitive … breite Tabellen scrollen in sich, die
   Seite selbst nie."). **Queue-Regel 18:** #431 suchte `overflow-x-auto`,
   geschrieben steht `overflow-auto` — die Messung traf die Schreibweise statt
   die Sache. **Erfüllt, nichts zu tun.**
2. **`whitespace-nowrap` in den Tabellenzellen (`TableDetailPage.tsx:241`) ist
   bewusst und richtig.** §4.4 Checklistenpunkt 1 nimmt bewusst gescrollte
   Container (Tabellen, Code-Blöcke) ausdrücklich aus. Ein Umbruch in
   Datenzellen würde Spaltenausrichtung und Lesbarkeit zerstören. **Kein
   Defekt.**

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/workarea/pages/TableDetailPage.tsx` (270 Z.) | – | Tabellenvorschau über das `Table`-Primitive (`:226`ff). Wrapper **erfüllt** (siehe Nicht-Befund 1), `:241` `whitespace-nowrap` **bewusst** (Nicht-Befund 2). Zu prüfen: der Kopfbereich (Tabellenname, Zeilenzahl, Aktionen) und die SQL-/Query-Fläche auf 320 px. |
| `features/workarea/pages/ArtifactDetailPage.tsx` (264 Z.) | – | `:237` `<pre className="min-w-0 flex-1 font-sans text-sm whitespace-pre-wrap">` — **erfüllt**: Rohtext bricht um und trägt `min-w-0`. Zu prüfen: Artefakt-Metadaten (Anker `<artifact_id>#<block_id>`, umbruchfeindlich) und die Block-Navigation auf 320 px. |
| `features/workarea/components/AreaGrants.tsx` (187 Z.) | – | Tabelle über das `Table`-Primitive — Wrapper **erfüllt**. Zu prüfen: Rollen-/Berechtigungs-Auswahl in der Zelle auf Touch (ein Dropdown in einem horizontal scrollenden Container kann die Scroll-Geste abfangen) und lange Principal-Bezeichner. |
| `features/workarea/pages/KbNodeDetailPage.tsx` (182 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Node-Anker (`node:<id>`), Kanten-Listen mit `co_n`-Fallzahlen und Tier-Badges auf 320 px. |
| `features/workarea/pages/WorkAreaSearchPage.tsx` (135 Z.) | – | **`:52` `flex min-w-64 flex-1 flex-col items-start gap-1 text-sm font-normal`** — Mindestbreite 256 px an einem Treffer-Eintrag. Auf 320 px abzüglich Container-Padding (`px-4` je Seite) bleiben 288 px; die Mindestbreite passt knapp, kippt aber bei jedem zusätzlichen Geschwister-Element oder `gap`. **Der einzige harte Breiten-Befund der Domäne** (§4.4 Checklistenpunkt 3). |
| `features/workarea/components/NewWorkAreaDialog.tsx` (125 Z.) | – | `:89` `<DialogContent>` **ohne eigene Breitenklasse** → erbt den W2-Default `w-[calc(100vw-2rem)] max-w-lg` + `max-h`/Scroll, **erfüllt, kein Defekt**. Zu prüfen: Formularfelder im Dialog auf 320 px. |
| `features/workarea/pages/KbSearchPage.tsx` (97 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Suchfeld, Filter und Trefferliste auf 320 px. |
| `features/workarea/pages/AreaDetailPage.tsx` (95 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Bereichs-Metadaten und Aktionen. |
| `features/workarea/pages/AreasPage.tsx` (91 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Listeneinträge und `PageHeader`-Actions. |
| `features/workarea/components/ArtifactList.tsx` (85 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Dateinamen und Zeitstempel je Eintrag auf 320 px. |
| `features/workarea/components/TableList.tsx` (84 Z.) | – | Tabelle über das `Table`-Primitive — Wrapper **erfüllt**. Zu prüfen: Tabellennamen und Zeilenzahlen. |
| `features/workarea/components/WorkAreaNav.tsx` (49 Z.) | – | `:30` `<nav className="flex flex-wrap gap-1 border-b pb-px">` — **erfüllt**, die drei Einträge (`:20-23`) brechen um. Je Eintrag `flex items-center gap-2 rounded-md px-3 py-2 text-sm` mit `h-4 w-4`-Icon. **Zu prüfen: `px-3 py-2` bei `text-sm` ergibt rechnerisch ~36 px Höhe — unter dem 40-px-Minimum aus §11** (§4.4 Checklistenpunkt 4). Identisch zu `SettingsNav` — **wer hier ändert, prüft die Wirkung dort mit.** |
| `features/workarea/components/KbBadges.tsx` (46 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Badge-Reihen (Tier, `co_n`) bei mehreren Badges auf 320 px. |
| `features/workarea/components/WorkAreaLayout.tsx` (20 Z.) | – | `Container className="pb-0"` um die Nav, darunter `<Outlet />` — **kein zweispaltiges Layout**, die Pages bringen ihren eigenen `Container`/`PageHeader` mit (erklärender Kommentar im File). **Kein Klassen-Befund.** |

**Breakpoint-Abdeckung: 0 von 14.**

**Kein `grid-cols-*` in der gesamten Domäne** — einzeln gegengeprüft:

```bash
grep -rnE 'grid-cols-' --include='*.tsx' apps/web/src/features/workarea \
  | grep -v '\.test\.tsx'                                                  # (leer)
```

**Was hier bereits stimmt und nicht wiederholt wird:** der Tabellen-Wrapper
sitzt im Primitive (dreimal genutzt: `AreaGrants`, `TableList`,
`TableDetailPage`); `ArtifactDetailPage.tsx:237` bricht Rohtext korrekt um; die
Sub-Navigation bricht um; der Dialog erbt den W2-Inset; es gibt kein
zweispaltiges Layout, das auf Mobile zerlegt werden müsste.

### Proposed solution

**Fertig heißt:** Jede der 14 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; jeder gefundene Defekt ist behoben oder mit Begründung als „kein
Defekt" festgehalten. **Kein horizontaler Body-Scroll** auf den Routen der
Domäne — die drei Tabellen scrollen in ihren eigenen Wrappern, das ist
zulässig und im Ergebnis als solches benannt.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive · `cn()` läuft über `tailwind-merge`.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **Tabellen auf Mobile als Karten stapeln?** → **Nein, scrollen lassen** →
   weil der Wrapper im Primitive bereits existiert (`table.tsx:14`), §4.4
   Checklistenpunkt 1 Tabellen ausdrücklich ausnimmt und ein Karten-Layout eine
   zweite Darstellung derselben Daten wäre (Doppelpflege ohne gemessenen
   Defekt). **Die Tabellenvorschau zeigt beliebige Nutzerspalten — ein
   Karten-Layout hätte hier nicht einmal ein stabiles Schema.**
2. **`WorkAreaSearchPage.tsx:52` (`min-w-64`)** → **auf `min-w-0` unterhalb der
   Mobile-Schwelle bzw. `sm:min-w-64`** → weil 256 px Mindestbreite auf einem
   288-px-Innenraum keinen Sicherheitsabstand lässt und jede zusätzliche
   Geschwister-Spalte sie kippt. Die Mindestbreite dient dem Desktop-Raster,
   nicht dem Phone.
3. **`WorkAreaNav`-Hit-Target** → **auf ≥ 40 px bringen unterhalb `md`** →
   weil §11 das Minimum setzt. **Und ausdrücklich:** die Komponente ist
   klassengleich zu `features/settings/components/SettingsNav.tsx` — die
   Änderung wird dort **nicht** mitgemacht (eigenes Paket), aber im Issue
   benannt, damit beide Pakete dieselbe Lösung wählen und kein Pattern Drift
   entsteht.
4. **Das Dropdown in der `AreaGrants`-Tabellenzelle** → **auf Touch prüfen,
   nur bei gemessenem Problem bewegen** → weil ein Dropdown in einem
   horizontal scrollenden Container die Scroll-Geste abfangen kann. Zeigt die
   Messung das, wandert die Aktion aus der Zelle; zeigt sie es nicht, bleibt
   alles. **Dieselbe Frage stellt sich im Settings-Paket bei der
   Mitgliedertabelle — wer zuerst misst, schreibt das Ergebnis ins andere
   Issue.**
5. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513. **`features/workarea/test-utils.tsx` ist der
   Domänen-Test-Helfer** und beim Testschreiben zu nutzen, statt einen zweiten
   anzulegen.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Route der Domäne
      horizontalen **Body**-Scroll. Die drei Tabellen (`TableDetailPage`,
      `TableList`, `AreaGrants`) scrollen in ihren eigenen Wrappern — zulässig,
      im Ergebnis benannt.
- [ ] **`WorkAreaSearchPage.tsx:52` ist auf 320 px darstellbar** — die
      Mindestbreite gilt nur noch oberhalb der Mobile-Schwelle oder ist
      responsiv ersetzt.
- [ ] **Hit-Targets unterhalb `md` ≥ 40 px** (§11 A11y-Minimum) — geprüft an
      den drei `WorkAreaNav`-Einträgen und den Listen-Aktionen.
- [ ] **Das Berechtigungs-Dropdown in `AreaGrants` ist auf einem
      Touch-Viewport bedienbar** — öffnen, Wert wählen, schließen, ohne dass
      der Tabellen-Scroll die Geste abfängt.
- [ ] Umbruchfeindliche Bezeichner (Artefakt-Anker `<artifact_id>#<block_id>`,
      `node:<id>`, Tabellennamen) brechen um oder kürzen kontrolliert —
      Flex-Kinder mit Textinhalt tragen `min-w-0` nach dem Muster von
      `ArtifactDetailPage.tsx:237`.
- [ ] Mehrspaltige Grids sind an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile (heute wie nachher — die Domäne hat kein `grid-cols-*`):
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/workarea | grep -v '\.test\.tsx'
      ```
- [ ] **Alle 14 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei. Für die zwei
      Nicht-Befunde oben gilt die dortige Begründung; sie werden **nicht**
      erneut als Defekt geführt.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 14 Dateien unter `apps/web/src/features/workarea/`, ihre
Testnachbarn (inkl. `features/workarea/test-utils.tsx`, falls der Helfer
erweitert werden muss), und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als
letzter Commit** — Sammelpunkt).

### Out of scope

`components/ui/*` und `components/layout/*` (insbesondere **`table.tsx` — der
Wrapper bleibt, wo er ist**; W2 hat dort entschieden, eine Änderung wirkt auf
alle dreizehn Domänen und ist ein eigenes Paket) · **`features/settings`**
(inkl. `SettingsNav`, obwohl klassengleich — eigenes W3-Paket) · jede Änderung
an Tabellen-Schema, Query-Semantik oder KB-Kantenmodell · jede andere Domäne
unter `features/` · W4 (Playwright-Mobile-Profile, E2E-Helfer „kein
horizontaler Body-Scroll") · echter Fullscreen-Dialog unter `sm` (#513 Weiche
3, verworfen) · ESLint-Regel für nackte `grid-cols-*` (#438 Weiche 5,
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
AK 6 gibt keine Zeile aus.

**Bestandskontrolle vor dem Abschluss** — der Ausschluss muss dreiteilig sein:

```bash
find apps/web/src/features/workarea -name '*.tsx' ! -name '*.test.tsx' | wc -l          # 15 (falsch)
find apps/web/src/features/workarea -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l                # 14 (richtig)
```

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen.

### Verweise

Tracking: **#431** (W3, Checklisteneintrag „WorkArea/Tabellen/Timeline"). Norm:
`docs/frontend/design-language.md` §4.4 (Mobile-first, Prefix-Pflicht,
sechspunktige Review-Checkliste Z. 222–233) und §11 (A11y-Minimum 40 px),
CLAUDE.md §Frontend-Standards. Vorgänger: **#438** (W0), **#500** (W1 —
Schwelle `md`, `useEffect`-freies Muster), **#513** (W2 — Dialog-Inset, Caps im
Primitive, `tailwind-merge`). Zählweise: #442 §Kollisionen (Ausschluss-Falle,
Pathspec-Falle) und der Nenner-Kommentar an #431 vom 2026-09-13.

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace. **`workarea`
ist mit 14 Dateien das zweitgrößte der dreizehn W3-Pakete — die drei größten
(`playbooks` 16, `workarea` 14, `personas` 13) laufen nie zu zweit
gleichzeitig.**

### Component

Web UI (apps/web)
