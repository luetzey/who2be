# Template für die dreizehn W3-Domänenpakete

Verbindlich für jedes der dreizehn Issues. Platzhalter in `<…>`.
**Jeder `datei:zeile`-Zeiger wird beim Schreiben im Repo aufgelöst, nie
aus #431 übernommen** — Vorgabe 5 des Auftrags.

---

**Titel:** `W3 <Domäne>: Responsive-Audit von features/<verzeichnis> (<n> Dateien)`

**Labels:** `web`, `agent-ready`, `size/S` (n ≤ 8) bzw. `size/M` (n > 8)

---

## Body-Gerüst

### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `<domäne>`. Die Domäne ist
auf `main` @ `87de64c` einzeln nachgemessen: **`<n>` produktive `.tsx`**
unter `apps/web/src/features/<verzeichnis>/`, davon tragen **`<b>`** einen
Breakpoint-Prefix.

```bash
find apps/web/src/features/<verzeichnis> -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # <n>
```

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien. Ausschluss
> `-name '*.test.tsx' -o -name '*test-utils*' -o -path '*/test/*'`, nicht nur
> `*.test.tsx`.

### Ist-Zustand (nachgemessen <datum> auf `main` @ `87de64c`)

Tabelle **aller** `<n>` Dateien, je Zeile: Pfad · Breakpoint-Prefix ja/nein ·
gemessener Befund mit `datei:zeile` oder „kein Befund". Kein Eintrag ohne
Messung, keine Vermutung.

| Datei | Breakpoints | Befund |
|---|---|---|
| `<pfad>` | `sm:`/– | `<pfad>:<zeile>` `<klasse/konstrukt>` — `<warum defekt auf 320 px>` |

**Gemessene Defektklassen** (nach §4.4-Checkliste `docs/frontend/design-language.md`
Z. 222–233): feste Breiten ohne Abfederung · Mehrspalten-Grid ohne Prefix ·
Flex-Kind ohne `min-w-0` · Hit-Target < 40 px unterhalb `md` · Tabelle ohne
scrollenden Wrapper · Header-/Toolbar-Zeile, die auf 320 px nicht umbricht.

**Was hier bereits stimmt** — ausdrücklich benennen, damit das Paket nicht
Erfülltes wiederholt (Queue-Regel 22: neu messen, nicht abhaken).

### Proposed solution

**Fertig heißt:** Jede der `<n>` Dateien ist bei **320 / 375 / 768 / 1024 px**
gegen die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md`
§4.4 geprüft; jeder gefundene Defekt ist behoben oder mit Begründung als
„kein Defekt" im Issue festgehalten. Kein horizontaler Body-Scroll auf den
Routen der Domäne.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513):
Mobile-Schwelle ist `md` · breakpoint-abhängiger State als Render-Zeit-Vergleich,
**kein `useEffect`** (`react-hooks/set-state-in-effect`) · Dialog-Inset
`w-[calc(100vw-2rem)] max-w-lg` + `max-h`/Scroll und die Popover-/Dropdown-Caps
sitzen im Primitive — Aufrufstellen ergänzen keine eigenen ·
`cn()` läuft über `tailwind-merge`: zwei Klassen derselben Familie löschen
einander, `w-*` und `max-w-*` nicht.

#### Vorentschieden (Frage → Entscheidung → weil)

Mindestens die domänenspezifischen Weichen, je mit Beleg. Keine Weiche ohne
`weil` und ohne Repo-Fundstelle.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Route der Domäne
      horizontalen Body-Scroll (ausgenommen bewusst scrollende Container —
      Tabellen, Code-Blöcke — die als solche benannt sind).
- [ ] Mehrspaltige Grids der Domäne sind an einen Breakpoint-Prefix gebunden.
      Gate, liefert **keine** Zeile:
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/<verzeichnis> | grep -v '\.test\.tsx'
      ```
- [ ] Feste Breiten auf Container-Ebene sind responsiv abgefedert
      (`w-full md:w-64` statt `w-64`). Belegte Fundstellen: `<liste>`.
- [ ] Hit-Targets unterhalb `md` bleiben ≥ 40 px (§11 A11y-Minimum).
- [ ] Text bleibt auf 320 px lesbar — Flex-Kinder mit Textinhalt tragen
      `min-w-0`, keine abgeschnittenen Labels.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first,
      CLAUDE.md §Workflow); die Coverage-Thresholds aus
      `apps/web/vite.config.ts:49-53` halten.
- [ ] Jede der `<n>` Dateien ist in der Ist-Tabelle mit Befund **oder**
      begründetem „kein Defekt" abgehakt — keine ungeprüfte Datei.

### Scope

Genau die `<n>` Dateien unter `apps/web/src/features/<verzeichnis>/`, ihre
Testnachbarn, und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter
Commit** — Sammelpunkt).

### Out of scope

`components/ui/*` (W2 hat dort entschieden; eine Änderung am Primitive ist ein
eigenes Paket) · jede andere Domäne unter `features/` · W4
(Playwright-Mobile-Profile, E2E-Helfer „kein horizontaler Body-Scroll") ·
echter Fullscreen-Dialog unter `sm` (#513 Weiche 3, verworfen) · ESLint-Regel
für nackte `grid-cols-*` (#438 Weiche 5, verworfen) · `apps/api`, `apps/mcp`,
`packages/**`.

### Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b            # NICHT --noEmit: das prüft null Dateien (Solution-File)
npm run test:coverage
npm run build
```

**Grün heißt:** Exit 0 bei allen vieren; `test:coverage` nennt Dateizahl und
Testzahl (Queue-Regel 21), die Branches-Thresholds halten; das Grid-Gate aus
AK 2 gibt keine Zeile aus.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:72`) — die schweren CI-Jobs laufen.

### Verweise

Tracking: **#431** (W3). Norm: `docs/frontend/design-language.md` §4.4
(Mobile-first, Prefix-Pflicht, sechspunktige Review-Checkliste Z. 222–233),
CLAUDE.md §Frontend-Standards. Vorgänger: **#438** (W0 — `Sheet`,
`useMediaQuery`, §4.4), **#500** (W1 — Schwelle `md`, `useEffect`-freies
Muster), **#513** (W2 — Dialog-Inset, Caps im Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in
getrennten Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace.
Die drei größten W3-Pakete (`playbooks` 16, `workarea` 14, `personas` 13)
laufen nie zu zweit gleichzeitig.

### Component

Web UI (apps/web)

---

## Abweichungen, die nur einzelne Pakete betreffen

**`billing` (1 Datei)** — Verifikation **zusätzlich**, sonst prüft der Audit
nichts (ADR-0029, `vite.config.ts:11`, `ci.yml` On-Prem-Assert + Cloud-Gegenprobe):

```bash
cd apps/web
VITE_WHO2BE_EDITION=cloud npm run build
VITE_WHO2BE_EDITION=cloud npm run test:coverage
```

Erreicht wird `BillingPanel` von genau einer Stelle —
`features/settings/pages/OrgSettingsPage.tsx:<zeile>`, lazy hinter
`__CLOUD_BUILD__`. Ohne die Flagge liegt der Import im toten Ternary-Zweig und
`features/billing` landet nicht im Bundle. **Billing-i18n liegt in
`features/billing/i18n.ts`, nicht am Sammelpunkt** (`localeParity.test.ts:<zeile>`)
— das Paket kann parallel zu jedem anderen W3-Paket laufen.

**`settings` (8 Dateien)** — `OrgSettingsPage.tsx` lädt `BillingPanel`, aber
dessen Fläche gehört zum Billing-Paket. Der Body sagt das ausdrücklich, damit
die Schnittkante nicht zweimal auditiert wird.

**`workarea` (14 Dateien)** — `TableDetailPage` hat **keinen** Defekt beim
Tabellen-Wrapper: der sitzt im `Table`-Primitive
(`components/ui/table.tsx:<zeile>`, `relative w-full overflow-auto`).
Queue-Regel 18 — es wurde `overflow-x-auto` gesucht, geschrieben steht
`overflow-auto`. Im Body als „erfüllt, nichts zu tun" führen.

**`resources` (6 Dateien)** — trägt die BlockNote-Insel (Toolbar/Slash-Menü auf
Touch) aus der #431-Checkliste.

**`personas` (13 Dateien)** — trägt `PersonaModesEditor` aus der
#431-Checkliste.

**`auth` (9) / `legal` (8)** — seit 2026-09-15 **zwei** Pakete, nicht
„öffentliche Seiten" (17 Dateien wären das größte aller W3-Pakete). `legal` ist
statischer Text, `auth` sind Formulare mit Fehlerzuständen und Step-up — zwei
verschiedene Audit-Vorgänge. Beide am i18n-Sammelpunkt: nie gleichzeitig im
selben Arbeitsbaum.
