TITEL: W3 Settings: Responsive-Audit von features/settings (8 Dateien)
LABELS: web, agent-ready, size/S
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `settings`. Die Domäne ist auf
`main` @ `87de64c` einzeln nachgemessen: **8 produktive `.tsx`** unter
`apps/web/src/features/settings/`, davon tragen **3** einen Breakpoint-Prefix.

```bash
find apps/web/src/features/settings -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 8
find apps/web/src/features/settings -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;
# AccountPage.tsx, OrgSettingsPage.tsx, WorkspaceSettingsPage.tsx
```

**Acht Dateien, nicht neun.** `features/billing` ist ein eigenes, dreizehntes
Paket (Entscheidung vom 2026-09-14, Variante 1) — siehe den Pflichtabschnitt
„Schnittkante zu Billing" unten. Wer hier neun zählt, hat das Billing-Paket
mitgezählt und misst gegen den falschen Bestand.

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Schnittkante zu Billing — Pflichtlektüre vor dem Audit

`OrgSettingsPage.tsx:56-58` lädt `BillingPanel` lazy hinter einem
**Build-Zeit-Literal**:

```ts
const BillingPanel = __CLOUD_BUILD__
  ? lazy(() => import('@/features/billing').then((m) => ({ default: m.BillingPanel })))
  : null
```

`apps/web/vite.config.ts:11` setzt `isCloudBuild` aus `VITE_WHO2BE_EDITION`
(Default `'onprem'`), `:16` ersetzt `__CLOUD_BUILD__` als Literal. Im
Default-Build ist es `false`, der Import liegt im toten Ternary-Zweig und
`features/billing` landet **nicht im Bundle**; `OrgSettingsPage.tsx:274`
rendert dann `null`. CI erzwingt beide Richtungen (`ci.yml:197` On-Prem-Assert,
`ci.yml:207-222` Cloud-Gegenprobe mit `VITE_WHO2BE_EDITION: cloud` auf `:214`).

**Für dieses Paket heißt das:** der Audit läuft im **Default-Build** und sieht
die Billing-Fläche nicht. **Das ist richtig so** — die Fläche gehört dem
Billing-Paket, das die Flagge als einziges der dreizehn setzt. **Niemand sucht
sie hier, und niemand hält sie durch dieses Paket für erledigt.** Die
Ternary-Zeilen `:56-58` bleiben unangetastet.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/settings/components/SettingsNav.tsx` (54 Z.) | **–** | `:35` `className="flex flex-wrap gap-1 border-b pb-px"` (am `<nav>` ab `:33`) — **erfüllt**: die Tab-Leiste bricht bereits um. Bis zu vier Einträge (`:20-25`, der vierte nur für Admins), je `flex items-center gap-2 rounded-md px-3 py-2 text-sm` mit `h-4 w-4`-Icon. **Zu prüfen: `px-3 py-2` bei `text-sm` ergibt rechnerisch ~36 px Höhe — unter dem 40-px-Minimum aus §11**, §4.4 Checklistenpunkt 4. Das ist der wahrscheinlichste echte Defekt der Domäne. |
| `features/settings/components/SettingsLayout.tsx` (21 Z.) | – | `Container className="pb-0"` um die Nav, darunter `<Outlet />`. **Kein Klassen-Befund** — und ausdrücklich **kein** zweispaltiges Settings-Layout: der erklärende Kommentar im File hält fest, dass die Pages ihren eigenen `Container`/`PageHeader` mitbringen. Der klassische „Nav neben Inhalt"-Mobile-Defekt existiert hier **nicht**. |
| `features/settings/pages/AccountPage.tsx` (586 Z.) | **ja** (1) | `:71` `grid gap-3 text-sm sm:grid-cols-[8rem_1fr]` — **erfüllt**, einspaltig unter `sm`. `:308` `<DialogContent>` ohne eigene Breitenklasse → erbt den W2-Default, **erfüllt**. Die längste Datei der Domäne; zu prüfen: Passwort-/E-Mail-Formulare und ihre Fehlerzustände auf 320 px. |
| `features/settings/pages/OrgSettingsPage.tsx` (366 Z.) | **ja** (1) | `:132` `grid gap-3 text-sm sm:grid-cols-[8rem_1fr]` — **erfüllt**. `:219` `<Select {...field} className="max-w-xs">` — feste Obergrenze 320 px auf einem Formularfeld; auf einem 320-px-Viewport abzüglich Container-Padding zu prüfen. `:332` `<DialogContent>` erbt den W2-Default, **erfüllt**. `:56-58`/`:274` Billing-Ternary → out of scope, siehe oben. |
| `features/settings/pages/WorkspaceSettingsPage.tsx` (274 Z.) | **ja** (2) | `:183` `mt-6 grid gap-1 border-t pt-6 text-sm sm:grid-cols-[10rem_1fr]` — **erfüllt**. `:186` `text-xs text-muted-foreground sm:col-start-2` — **erfüllt**, die Hilfszeile rutscht oberhalb `sm` korrekt in die zweite Spalte. `:237` `<DialogContent>` erbt den W2-Default. |
| `features/settings/pages/MembersPage.tsx` (360 Z.) | **–** | **Der zweite Schwerpunkt.** Vierspaltige Mitgliedertabelle über das `Table`-Primitive (`:182`–`:219`): E-Mail (`:194`), Rollen-`Select` **in der Zelle** (`:198`-`:214`), Beitrittsdatum (`:216`), Aktionen rechtsbündig (`:219`). Der horizontale Wrapper ist im Primitive vorhanden (`components/ui/table.tsx:14`, `relative w-full overflow-auto`) — **erfüllt, kein Defekt**. Zu prüfen: ob ein `Select` innerhalb eines horizontal scrollenden Containers auf Touch bedienbar bleibt, und die Einladungszeile `:309` (`flex flex-wrap items-center justify-between gap-3` — **erfüllt**, bricht um). |
| `features/settings/components/MfaSection.tsx` (297 Z.) | – | `:82` `flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm` **ohne `flex-wrap`**, mit `:84` `flex min-w-0 items-center gap-2` — Texteinlauf **erfüllt**, Umbruch der Faktor-Zeile zu prüfen. `:180` und `:273` zwei `<DialogContent>` ohne eigene Breitenklasse → beide erben den W2-Default (`w-[calc(100vw-2rem)] max-w-lg` + `max-h`/Scroll), **erfüllt**. Zu prüfen: QR-Code und Backup-Code-Liste im Dialog auf 320 px. |
| `features/settings/components/MemoryGuardSection.tsx` (220 Z.) | – | **Kein Klassen-Befund** — kein Grid, keine feste Breite, keine `justify-between`-Zeile. Zu prüfen: Schwellenwert-Eingaben und Beschreibungstexte auf 320 px. |

**Breakpoint-Abdeckung: 3 von 8.**

**Was hier bereits stimmt und nicht wiederholt wird:** alle drei
Definitionslisten-Grids sind mobile-first gebunden; die Settings-Navigation
bricht um; die vier Dialoge erben den W2-Inset; der Tabellen-Wrapper sitzt im
Primitive; `min-w-0` sitzt an `MfaSection.tsx:84` richtig; die Einladungszeile
`MembersPage.tsx:309` trägt `flex-wrap`. **Das zweispaltige Settings-Layout,
das man hier vermuten würde, existiert nicht** — das ist ein Nicht-Befund, der
ins Issue gehört, damit er nicht dreimal nachgesucht wird.

### Proposed solution

**Fertig heißt:** Jede der 8 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
die sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
geprüft; jeder gefundene Defekt ist behoben oder mit Begründung als „kein
Defekt" festgehalten. Kein horizontaler Body-Scroll auf den Settings-Routen —
ausgenommen die Mitgliedertabelle, die als bewusst scrollender Container
benannt ist.

**Geerbt, nicht neu entschieden** (#431, W1/#500, W2/#513): Mobile-Schwelle ist
`md` (`hooks/useMediaQuery.ts:7`) · breakpoint-abhängiger State als
Render-Zeit-Vergleich, **kein `useEffect`** · Dialog-Inset und
Popover-/Dropdown-Caps sitzen im Primitive, Aufrufstellen ergänzen keine
eigenen · `cn()` läuft über `tailwind-merge`.

#### Vorentschieden (Frage → Entscheidung → weil)

1. **`SettingsNav` — Hit-Target aufpolstern oder Tabs auf Mobile umbauen?** →
   **aufpolstern** (`py-2.5`/`min-h-10` unterhalb `md`), kein Umbau → weil die
   Leiste bereits umbricht (`:35` `flex-wrap`) und der gemessene Defekt die
   Höhe ist, nicht die Anordnung. Ein Select-Dropdown statt Tabs wäre eine
   Designentscheidung ohne gemessenen Bedarf.
2. **Mitgliedertabelle — stapeln als Karten auf Mobile oder scrollen lassen?**
   → **scrollen lassen** → weil der Wrapper im `Table`-Primitive bereits
   existiert (`table.tsx:14`) und §4.4 Checklistenpunkt 1 Tabellen ausdrücklich
   als bewusst gescrollte Container ausnimmt. Ein Karten-Layout wäre eine
   zweite Darstellung derselben Daten, also Doppelpflege — und es gibt keinen
   gemessenen Defekt, der sie rechtfertigt.
3. **Das Rollen-`Select` in der scrollenden Tabellenzelle (`:198`)** → **wird
   auf Touch geprüft und nur bei gemessenem Problem bewegt** → weil ein
   Dropdown in einem horizontal scrollenden Container auf Touch klemmen kann
   (Scroll-Geste gegen Öffnen-Geste). Zeigt die Messung das, ist die
   Rollen-Änderung in den Zeilen-Aktionsbereich zu verlagern; zeigt sie es
   nicht, bleibt alles.
4. **`OrgSettingsPage.tsx:219` (`max-w-xs` am `Select`)** → **nur bei
   gemessenem Überlauf abfedern** (`w-full sm:max-w-xs`) → weil `max-w-*` eine
   Obergrenze ist und auf 320 px bereits das Container-Padding greift. §4.4
   Checklistenpunkt 3 verlangt die Prüfung, nicht automatisch die Änderung.
5. **Billing anfassen?** → **Nein, unter keinen Umständen** → weil es ein
   eigenes Paket ist und die Ternary-Zeilen die ADR-0029-Isolation tragen, die
   CI in beide Richtungen erzwingt.
6. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Settings-Route horizontalen
      **Body**-Scroll. Die Mitgliedertabelle scrollt in ihrem eigenen Wrapper —
      das ist zulässig und im Issue als solches benannt.
- [ ] **Die Einträge der Settings-Navigation erreichen unterhalb `md` ≥ 40 px
      Hit-Target** (§11 A11y-Minimum) — gemessen, nicht angenommen.
- [ ] **Das Rollen-`Select` in der Mitgliedertabelle ist auf einem
      Touch-Viewport bedienbar** — öffnen, Wert wählen, schließen, ohne dass
      der Tabellen-Scroll die Geste abfängt.
- [ ] `MfaSection.tsx:82` bricht auf 320 px um oder passt vollständig; QR-Code
      und Backup-Codes bleiben im Dialog vollständig sichtbar und scrollbar.
- [ ] Mehrspaltige Grids bleiben an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile:
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/settings | grep -v '\.test\.tsx'
      ```
- [ ] Text bleibt auf 320 px lesbar: lange E-Mail-Adressen in der
      Mitgliederliste brechen um oder kürzen kontrolliert.
- [ ] **Alle 8 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei.
- [ ] **`features/billing` ist nicht angefasst** und der On-Prem-Bundle-Assert
      (`ci.yml:197`) bleibt grün.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 8 Dateien unter `apps/web/src/features/settings/`, ihre
Testnachbarn, und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter
Commit** — Sammelpunkt).

### Out of scope

**`features/billing` und die Ternary-Zeilen `OrgSettingsPage.tsx:56-58`/`:274`**
(eigenes W3-Paket, ADR-0029-Isolation) · `components/ui/*` und
`components/layout/*` (inkl. `table.tsx` und `Container` — W2 hat dort
entschieden; eine Änderung wirkt auf alle dreizehn Domänen und ist ein eigenes
Paket) · jede andere Domäne unter `features/` · W4 (Playwright-Mobile-Profile,
E2E-Helfer „kein horizontaler Body-Scroll") · echter Fullscreen-Dialog unter
`sm` (#513 Weiche 3, verworfen) · ESLint-Regel für nackte `grid-cols-*` (#438
Weiche 5, verworfen) · jede Änderung an Rollenmodell, MFA-Verfahren oder
Memory-Guard-Semantik · `apps/api`, `apps/mcp`, `packages/**`.

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
AK 5 gibt keine Zeile aus.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen, inklusive beider Bundle-Asserts
(`ci.yml:197` und `:207-222`).

### Verweise

Tracking: **#431** (W3, Checklisteneintrag „Settings (Members, MFA)"; die
Abtrennung von Billing ist im Block vom 2026-09-14 hergeleitet). Norm:
`docs/frontend/design-language.md` §4.4 (Mobile-first, Prefix-Pflicht,
sechspunktige Review-Checkliste Z. 222–233) und §11 (A11y-Minimum 40 px),
CLAUDE.md §Frontend-Standards und §Editionen. Editions-Isolation: **ADR-0029**,
`vite.config.ts:11`/`:16`, `ci.yml:197` + `:207-222`. Vorgänger: **#438** (W0),
**#500** (W1 — Schwelle `md`, `useEffect`-freies Muster), **#513** (W2 —
Dialog-Inset, Caps im Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace. **Nicht
gleichzeitig mit dem Billing-Paket fahren** — beide berühren die Org-Route,
auch wenn ihre Dateien disjunkt sind. Die drei größten W3-Pakete (`playbooks`
16, `workarea` 14, `personas` 13) laufen nie zu zweit gleichzeitig.

### Component

Web UI (apps/web)
