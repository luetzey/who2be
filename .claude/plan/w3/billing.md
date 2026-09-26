TITEL: W3 Billing: Responsive-Audit von features/billing (1 Datei, Cloud-Build)
LABELS: web, agent-ready, size/S
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `billing`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **genau 1 produktive `.tsx`** unter
`apps/web/src/features/billing/`.

```bash
find apps/web/src/features/billing -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 1
```

**Dieses Paket existiert, weil sein Audit ohne eine Sonderbedingung nichts
prüft.** `BillingPanel` hängt an einem Build-Zeit-Literal: im Default-Build
(On-Prem, ohne `VITE_WHO2BE_EDITION`) ist `__CLOUD_BUILD__` das Literal
`false`, der dynamische Import liegt im toten Ternary-Zweig und
`features/billing` landet **nicht im ausgelieferten JS**. Verifiziert:

```
apps/web/src/features/settings/pages/OrgSettingsPage.tsx:56-58
  const BillingPanel = __CLOUD_BUILD__
    ? lazy(() => import('@/features/billing').then((m) => ({ default: m.BillingPanel })))
    : null
apps/web/vite.config.ts:11   const isCloudBuild = (process.env.VITE_WHO2BE_EDITION ?? 'onprem') === 'cloud'
apps/web/vite.config.ts:16   __CLOUD_BUILD__: JSON.stringify(isCloudBuild)
```

CI erzwingt beide Richtungen: `.github/workflows/ci.yml:197` („Assert on-prem
bundle excludes Billing-UI (ADR-0029)") und die Cloud-Gegenprobe ab
`ci.yml:207` mit `VITE_WHO2BE_EDITION: cloud` (`:214`).

**Ein Audit, das die Flagge nicht setzt, läuft grün durch, ohne die Fläche
gesehen zu haben** — die Klasse stillen Fehlschlags, gegen die #442 §Kollisionen
geschrieben ist. Deshalb ist `billing` ein eigenes, dreizehntes Paket
(Entscheidung vom 2026-09-14, Variante 1): nur dieses eine trägt die
Editions-Sonderbedingung, die übrigen zwölf bleiben beim Default-Build.

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/billing/components/BillingPanel.tsx` (191 Z.) | **ja** (1) | `BillingPanel.tsx:144` `grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2` — **erfüllt**, in W2/#513 korrigiert. `:78` und `:134` tragen `flex items-center justify-between` **ohne** `flex-wrap` und **ohne** `min-w-0` — auf 320 px der zu prüfende Fall (Label links, Wert/Aktion rechts). |

**Breakpoint-Abdeckung: 1 von 1.** Die einzige Datei der Domäne trägt einen
Prefix — `billing` ist damit die einzige der dreizehn Domänen mit voller
formaler Abdeckung. Das ersetzt die visuelle Prüfung nicht.

**Was hier bereits stimmt und nicht wiederholt wird:** das Grid ist
mobile-first gebunden (W2); die Dialog-/Popover-Caps sitzen im Primitive.

### Proposed solution

**Fertig heißt:** `BillingPanel` ist **im Cloud-Build** bei 320 / 375 / 768 /
1024 px gegen die sechspunktige Review-Checkliste aus
`docs/frontend/design-language.md` §4.4 geprüft; kein horizontaler Body-Scroll
auf der Route, die das Panel rendert (Org-Einstellungen). Jeder gefundene
Defekt ist behoben oder mit Begründung als „kein Defekt" festgehalten.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`, `(max-width: 767px)`) · breakpoint-abhängiger
State als Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive, Aufrufstellen ergänzen keine
eigenen · `cn()` läuft über `tailwind-merge`: zwei Klassen derselben Familie
löschen einander, `w-*` und `max-w-*` nicht.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **Eigenes Paket oder Teil von Settings?** → **eigenes Paket** → weil sonst
   **ein** Paket die Editions-Flagge tragen müsste und dessen übrige acht
   Dateien sie nicht brauchen; und weil ein Settings-Audit im Default-Build
   `BillingPanel` gar nicht rendert (`OrgSettingsPage.tsx:274`,
   `{BillingPanel ? … : null}`) und grün liefe, ohne etwas geprüft zu haben.
2. **Wie wird die Fläche sichtbar gemacht?** → **`VITE_WHO2BE_EDITION=cloud`
   vor Build und Testlauf** → weil `vite.config.ts:11` genau diese Variable
   liest und CI es ab `ci.yml:207` genauso macht. Kein anderer Weg ist im Repo
   vorgesehen.
3. **Wo liegen die i18n-Strings?** → **`features/billing/i18n.ts`, nicht am
   Sammelpunkt** → weil ADR-0029 sie dort bewusst isoliert und
   `src/i18n/localeParity.test.ts:26` das ausdrücklich dokumentiert. **Folge:
   dieses Paket ist als einziges der dreizehn nicht am i18n-Sammelpunkt
   beteiligt und kann parallel zu jedem anderen W3-Paket laufen.**

### Acceptance criteria

- [ ] Im **Cloud-Build** erzeugt die Org-Einstellungsroute mit gerendertem
      `BillingPanel` auf 320, 375, 768 und 1024 px keinen horizontalen
      Body-Scroll.
- [ ] Die beiden `justify-between`-Zeilen (`BillingPanel.tsx:78`, `:134`)
      brechen auf 320 px um oder kürzen kontrolliert (`flex-wrap` bzw.
      `min-w-0` + `truncate`) — kein überlaufender Wert, kein abgeschnittenes
      Label.
- [ ] Mehrspaltige Grids bleiben an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile:
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/billing | grep -v '\.test\.tsx'
      ```
- [ ] Hit-Targets unterhalb `md` bleiben ≥ 40 px (§11 A11y-Minimum).
- [ ] **Der Nachweis wird im Cloud-Build geführt.** Ein Beleg aus dem
      Default-Build zählt nicht — dort ist die Komponente nicht im Bundle.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).
- [ ] Der On-Prem-Bundle-Assert (`ci.yml:197`) bleibt grün — die Änderung darf
      `features/billing` nicht ins Default-Bundle ziehen.

### Scope

`apps/web/src/features/billing/components/BillingPanel.tsx`, sein Testnachbar,
bei Bedarf `apps/web/src/features/billing/i18n.ts`, und `CHANGELOG.md`
(§Unreleased, ein Eintrag, **als letzter Commit** — Sammelpunkt).

### Out of scope

`features/settings` und insbesondere `OrgSettingsPage.tsx` (eigenes W3-Paket;
die Ternary-Zeilen `:56-58` bleiben unangetastet) · `components/ui/*` (W2 hat
dort entschieden) · jede andere Domäne unter `features/` · W4
(Playwright-Mobile-Profile, E2E-Helfer „kein horizontaler Body-Scroll") ·
echter Fullscreen-Dialog unter `sm` (#513 Weiche 3, verworfen) · jede Änderung
an der Editions-Isolation selbst (ADR-0029) · `apps/api`, `apps/mcp`,
`packages/**`.

### Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b            # NICHT --noEmit: das prueft null Dateien (Solution-File)
VITE_WHO2BE_EDITION=cloud npm run test:coverage
VITE_WHO2BE_EDITION=cloud npm run build
```

**Die Flagge ist hier Pflicht, nicht Kosmetik** — ohne sie ist die Fläche nicht
im Bundle und der Audit prüft nichts (ADR-0029, `vite.config.ts:11`).

Dazu die Gegenprobe, dass der On-Prem-Ausschluss hält:

```bash
cd apps/web && npm run build   # Default = on-prem
grep -rl 'BillingPanel' dist/assets/ && echo "FEHLER: Billing im On-Prem-Bundle" || echo "OK"
```

**Grün heißt:** Exit 0 bei allen vieren; `test:coverage` nennt Dateizahl und
Testzahl (Queue-Regel 21), die Branches-Thresholds halten; das Grid-Gate aus
AK 3 gibt keine Zeile aus; die On-Prem-Gegenprobe meldet `OK`.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen, inklusive beider Bundle-Asserts.

### Verweise

Tracking: **#431** (W3). Norm: `docs/frontend/design-language.md` §4.4
(Mobile-first, Prefix-Pflicht, sechspunktige Review-Checkliste Z. 222–233),
CLAUDE.md §Frontend-Standards. Editions-Isolation: **ADR-0029**,
`vite.config.ts:11`/`:16`, `ci.yml:197` + `:207-222`,
`src/i18n/localeParity.test.ts:26`. Vorgänger: **#438** (W0), **#500** (W1 —
Schwelle `md`, `useEffect`-freies Muster), **#513** (W2 — Dialog-Inset, Caps im
Primitive, `tailwind-merge`; hat auch `BillingPanel.tsx:144` korrigiert).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). **Ausnahme: am i18n-Sammelpunkt ist dieses Paket
nicht beteiligt** (ADR-0029) — es ist damit das einzige der dreizehn, das
i18n-seitig kollisionsfrei neben jedem anderen laufen kann.

### Component

Web UI (apps/web)
