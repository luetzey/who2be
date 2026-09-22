TITEL: W3 Playbooks: Responsive-Audit von features/playbooks (16 Dateien)
LABELS: web, agent-ready, size/M
---
### Problem

W3 (Feature-Audit je Domäne) von **#431**, Paket `playbooks`. Die Domäne ist
auf `main` @ `87de64c` einzeln nachgemessen: **16 produktive `.tsx`** unter
`apps/web/src/features/playbooks/` — **das größte der dreizehn W3-Pakete**.

```bash
find apps/web/src/features/playbooks -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 16
```

> **Zählweise (Queue-Regeln 48/51):** `find`, nicht die Pathspec
> `'apps/web/src/**/*.tsx'` — die übergeht Wurzel-Dateien (386 gegen 383).
> Ausschluss dreiteilig, nicht nur `*.test.tsx`.

### Die Breakpoint-Zählung dieser Domäne ist 2, nicht 3

`grep -l` meldet drei Dateien mit Breakpoint-Prefix. **Eine davon ist ein
Fehltreffer:** der einzige Treffer in `PlaybookRow.tsx` steht in einem
Kommentar, nicht in einer Klasse.

```bash
# roh — meldet 3:
find apps/web/src/features/playbooks -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' \
  -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;
# PlaybookRow.tsx, ResourceBlockLinkPicker.tsx, PlaybookDetailPage.tsx

# der Treffer in PlaybookRow.tsx:
# :71  {/* Icon-Kachel auf die geteilte `EntityIcon`-Geometrie (md: 44px,
```

`PlaybookRow.tsx` trägt **keine einzige breakpoint-präfixierte Klasse**.
**Effektive Abdeckung: 2 von 16.** Wer die Rohzahl übernimmt, hält die Domäne
für besser abgedeckt, als sie ist — und übersieht dabei ausgerechnet die
Listenzeile, die auf jeder Playbook-Übersicht n-fach gerendert wird.

### Ist-Zustand (nachgemessen 2026-09-22 auf `main` @ `87de64c`)

| Datei | Breakpoints | Befund |
|---|---|---|
| `features/playbooks/pages/PlaybookDetailPage.tsx` (397 Z.) | **ja** (3) | `:284` `grid gap-4 sm:grid-cols-2` — **erfüllt**, mobile-first gebunden. `:285`/`:325` `Card className="sm:col-span-2"` — **erfüllt**, unterhalb `sm` einspaltig. `:129` `min-w-0` — Texteinlauf **erfüllt**. Zu prüfen: Kopfbereich mit Metadaten, Tab-Leiste (`PlaybookDetailTabs`) und Aktionen auf 320 px. |
| `features/playbooks/components/PlaybookListToolbar.tsx` (341 Z.) | – | **Der Schwerpunkt des Pakets.** `:162` **`relative min-w-48 flex-1`** am Suchfeld — 192 px Mindestbreite; steht in einer Zeile mit weiteren Elementen, auf 320 px (Innenraum ~288 px) der erste Kipp-Kandidat (§4.4 Checklistenpunkt 3). `:200` `PopoverContent className="flex w-72 flex-col gap-4"` — 288 px feste Breite; das Primitive trägt `max-w-[calc(100vw-1rem)]` (`components/ui/popover.tsx:48`), `w-*` und `max-w-*` löschen einander **nicht** → **gedeckelt, erfüllt**. `:131`/`:309`/`:325` `flex flex-wrap` — **erfüllt**. `:71`/`:295`/`:313`/`:329` `size="sm"` und `:180` `size="icon"` — **Hit-Targets unterhalb `md` zu prüfen** (§11). |
| `features/playbooks/components/ResourceBlockLinkPicker.tsx` (334 Z.) | **ja** (1) | `:192` `grid grid-cols-1 gap-4 sm:grid-cols-2` — **erfüllt**, explizit einspaltig als Basis. `:180` **`<DialogContent className="max-w-3xl">`** — überschreibt per `tailwind-merge` nur das `max-w-lg` des Primitives; `w-[calc(100vw-2rem)]` (`components/ui/dialog.tsx:51`) bleibt bestehen → auf 320 px **erfüllt, kein Defekt**. Zu prüfen: die zweispaltige Auswahlfläche oberhalb `sm` bei langen Block-Ankern, `:210` Listeneinträge und die `size="sm"`-Aktionen `:250`/`:262`. |
| `features/playbooks/components/PlaybookEditorForm.tsx` (257 Z.) | – | **Kein Klassen-Befund** — kein Grid, keine feste Breite, kein `min-w-0`. Zu prüfen: Feldgruppen, Trigger-Eingabe und Validierungsfehler auf 320 px. |
| `features/playbooks/components/PlaybookComposesPicker.tsx` (238 Z.) | – | `:103` `<DialogContent className="max-w-lg">` — **redundant**: identisch zum Primitive-Default (`dialog.tsx:51`), wirkungslos, aber harmlos. `:125` `flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm` **ohne `flex-wrap`** — Kind-Playbook-Name links, drei `size="sm"`-Aktionen rechts (`:137`, `:148`, `:159`); **der wahrscheinlichste echte Überlauf der Domäne** auf 320 px. `px-3 py-2` bei `text-sm` ergibt ~36 px — **unter dem 40-px-Minimum aus §11**. |
| `features/playbooks/components/PlaybookRow.tsx` (214 Z.) | **– (Kommentar-Fehltreffer, siehe oben)** | Die n-fach gerenderte Listenzeile. `:68` `relative flex gap-4 rounded-xl border bg-card p-4 …`, `:74` `PlaybookTypeIcon className="size-11 rounded-xl"`, `:76` `flex min-w-0 flex-1 flex-col gap-1` — Texteinlauf **erfüllt**. `:77`/`:111`/`:202` `flex flex-wrap` — **erfüllt**. `:150`/`:177` `min-w-0 truncate` — **erfüllt**. `:200` `flex shrink-0 flex-col items-end justify-between gap-2` — **die rechte Meta-Spalte ist `shrink-0`**: sie gibt auf 320 px keinen Platz ab, während links `min-w-0` alles trägt. Zu prüfen, ob die Zeile dadurch unlesbar schmal wird. `:141` `size="sm"` mit `:144` `h-auto w-full justify-start gap-2 px-3 py-2` und `:172` `px-3 py-2` — **Hit-Target ~36 px, unter §11**. |
| `features/playbooks/pages/PlaybooksPage.tsx` (195 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Listenrahmen, `PageHeader`-Actions und das Zusammenspiel mit der Toolbar auf 320 px. |
| `features/playbooks/components/PlaybookBodyEditor.tsx` (181 Z.) | – | `:123` `bn-container rounded-md border bg-background py-2` — **die BlockNote-Insel.** Der Editor rendert eigenes DOM außerhalb der Tailwind-Klassenhoheit. **Siehe Pflichtabschnitt unten.** |
| `features/playbooks/components/ReviewBanner.tsx` (115 Z.) | – | `:81` `flex flex-wrap items-center justify-between gap-4 …` und `:85` `flex flex-wrap items-center gap-3` — **beide erfüllt**, brechen um. Zu prüfen: der Branch-Graph (`data-testid="branch-graph"`) bei mehreren Knoten auf 320 px. |
| `features/playbooks/components/LinkedBlocksList.tsx` (103 Z.) | – | `:78` `flex items-center justify-between gap-3 rounded-md border p-3` **ohne `flex-wrap`**, `:80` `flex min-w-0 flex-col gap-1` — Texteinlauf **erfüllt**, Umbruch zu prüfen. `:90` `size="sm"` — Hit-Target zu prüfen. Block-Anker (`<resource_id>#<block_id>`) sind umbruchfeindlich. |
| `features/playbooks/components/PlaybooksEmptyStates.tsx` (97 Z.) | – | `:29` `max-w-md`, `:88` `max-w-sm`, `:38` `mt-8 flex max-w-xl flex-wrap justify-center gap-2` — **alle drei erfüllt**: `max-w-*` ist eine Obergrenze und bricht um. Kein Defekt erwartet. |
| `features/playbooks/components/PlaybookDetailTabs.tsx` (86 Z.) | – | Die Tab-Leiste der Detailseite. **Kein `flex-wrap` im Klassen-Befund** — zu prüfen, ob die Tabs auf 320 px umbrechen oder überlaufen, und ob ihr Hit-Target §11 erfüllt. |
| `features/playbooks/pages/PlaybookNewPage.tsx` (62 Z.) | – | **Kein Klassen-Befund** — dünne Seite. |
| `features/playbooks/components/SubPlaybookFlow.tsx` (54 Z.) | – | Die Composite-Kette. `:24` `flex flex-wrap items-stretch gap-3` — **erfüllt**, bricht um. `:34` **`li className="flex min-w-40 flex-1"`** — 160 px Mindestbreite je Kettenglied; bei zwei Gliedern nebeneinander plus `gap-3` und Pfeil-Trenner (`:30`) auf 320 px zu prüfen. `:45` `min-w-0 truncate` — **erfüllt**. `:37` `px-3 py-3` ≈ 40 px — **erfüllt**. |
| `features/playbooks/components/ComposedByList.tsx` (40 Z.) | – | **Kein Klassen-Befund.** Zu prüfen: Rückverweis-Liste bei langen Playbook-Namen. |
| `features/playbooks/components/PlaybookTypeIcon.tsx` (29 Z.) | – | Reine Icon-Kachel (`size-11` von der Aufrufstelle). **Kein Klassen-Befund.** |

**Effektive Breakpoint-Abdeckung: 2 von 16.**

**Beide `grid-cols-*` sind gebunden** — einzeln gegengeprüft:

```bash
grep -rnE 'grid-cols-' --include='*.tsx' apps/web/src/features/playbooks \
  | grep -v '\.test\.tsx'
# ResourceBlockLinkPicker.tsx:192:  grid grid-cols-1 gap-4 sm:grid-cols-2
# PlaybookDetailPage.tsx:284:      grid gap-4 sm:grid-cols-2
```

**Kein `Table`-Primitive in der Domäne** (gegengeprüft) — die Frage
„Tabelle stapeln oder scrollen?" stellt sich hier nicht.

**Was hier bereits stimmt und nicht wiederholt wird:** beide Grids sind
mobile-first gebunden; `flex-wrap` sitzt an neun Stellen richtig; `min-w-0`
an sieben; die Empty-States sind durchweg korrekt; `SubPlaybookFlow` bricht um
und erfüllt §11; die Popover-/Dialog-Caps sitzen seit W2 im Primitive und die
beiden Aufrufer-`max-w-*` sind durch `w-[calc(100vw-2rem)]` bzw.
`max-w-[calc(100vw-1rem)]` gedeckelt.

### BlockNote-Insel — Pflichtlektüre vor dem Audit

`PlaybookBodyEditor.tsx:123` rendert den BlockNote-Editor in einem
`bn-container`. **Der Editor erzeugt eigenes DOM, das nicht über
Tailwind-Klassen dieser Datei erreichbar ist** — Toolbar, Slash-Menü,
Drag-Handles und Formatierungs-Popover kommen aus der Bibliothek.

**Für dieses Paket heißt das:**

- Die Insel wird **geprüft, aber nicht per Tailwind-Klasse repariert**. Was
  innerhalb des Editors auf 320 px überläuft, gehört in einen eigenen
  Befund-Eintrag mit Screenshot-Beschreibung — **nicht in einen Hotfix, der
  Bibliotheks-DOM per globalem CSS überschreibt.**
- Derselbe Editor läuft in `features/resources` (eigenes W3-Paket). **Wer hier
  einen Insel-Befund notiert, schreibt ihn ins andere Issue mit** — sonst wird
  er zweimal gefunden und womöglich zweimal unterschiedlich gelöst.
- Ein globaler `bn-*`-CSS-Override wäre eine domänenübergreifende Änderung und
  damit **ein eigenes Paket**, nicht Teil dieses Audits.

### Proposed solution

**Fertig heißt:** Jede der 16 Dateien ist bei 320 / 375 / 768 / 1024 px gegen
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

1. **`PlaybookComposesPicker.tsx:125` — umbrechen oder Aktionen in ein Menü?**
   → **umbrechen (`flex-wrap`)**, kein Overflow-Menü → weil §4.4
   Checklistenpunkt 5 Umbruch als Mittel der Wahl nennt und ein Menü eine
   zweite Interaktionsebene ohne gemessenen Bedarf einführt. Drei `size="sm"`-
   Aktionen neben einem Namen sind der klassische Umbruchfall.
2. **`PlaybookListToolbar.tsx:162` (`min-w-48`) und `SubPlaybookFlow.tsx:34`
   (`min-w-40`)** → **Mindestbreite oberhalb der Mobile-Schwelle binden**
   (`min-w-0 sm:min-w-48` bzw. `sm:min-w-40`), nicht ersatzlos streichen →
   weil beide dem Desktop-Raster dienen und auf 288 px Innenraum keinen
   Sicherheitsabstand lassen. §4.4 Checklistenpunkt 3.
3. **`PlaybookRow.tsx:200` (`shrink-0` an der Meta-Spalte)** → **nur bei
   gemessener Unlesbarkeit lösen**, dann durch Umbruch der Zeile unterhalb
   `md`, nicht durch Streichen von `shrink-0` → weil `shrink-0` die Badges vor
   dem Zerquetschen schützt; das Problem ist die einzeilige Anordnung, nicht
   die Klasse.
4. **Die beiden Aufrufer-`max-w-*` an `DialogContent` (`:180` `max-w-3xl`,
   `:103` `max-w-lg`) anfassen?** → **Nein** → weil `w-[calc(100vw-2rem)]` aus
   dem Primitive bestehen bleibt und beide damit auf 320 px korrekt sind. Das
   redundante `max-w-lg` zu entfernen wäre Kosmetik ohne Defekt. **W2 hat
   entschieden, dass Caps im Primitive sitzen — das gilt auch rückwärts: keine
   Aufräumarbeit an Aufrufstellen ohne Befund.**
5. **`size="sm"`-Hit-Targets** → **auf ≥ 40 px bringen unterhalb `md`** →
   weil §11 das A11y-Minimum setzt; betroffen sind mindestens
   `PlaybookRow.tsx:141`/`:172`, `PlaybookComposesPicker.tsx:137`/`:148`/`:159`,
   `LinkedBlocksList.tsx:90` und die Toolbar-Aktionen. §4.4 Checklistenpunkt 4
   nennt die `size="sm"`-Verdichtung ausdrücklich.
6. **BlockNote-Insel** → **prüfen, notieren, nicht per globalem CSS
   reparieren** → siehe Pflichtabschnitt oben.
7. **Tests wohin?** → **`*.test.tsx` neben die geänderte Datei**, nach dem
   Muster von W2/#513.

### Acceptance criteria

- [ ] Auf 320, 375, 768 und 1024 px erzeugt keine Route der Domäne
      horizontalen Body-Scroll.
- [ ] **`PlaybookComposesPicker.tsx:125` bricht auf 320 px um** — Kind-Name
      und die drei Aktionen überlaufen nicht.
- [ ] **`PlaybookListToolbar` ist auf 320 px bedienbar** — Suchfeld (`:162`),
      Filter-Popover (`:200`) und die Aktions-Reihen erreichbar, ohne dass die
      Zeile überläuft.
- [ ] **`PlaybookRow` bleibt auf 320 px lesbar** — Name, Typ-Badge und
      Meta-Spalte (`:200`, `shrink-0`) zusammen; lange Playbook- und
      Kind-Namen brechen um oder kürzen kontrolliert.
- [ ] **Hit-Targets unterhalb `md` ≥ 40 px** (§11 A11y-Minimum) — geprüft an
      allen `size="sm"`/`size="icon"`-Stellen der Domäne und an
      `PlaybookDetailTabs`.
- [ ] **`PlaybookDetailTabs` läuft auf 320 px nicht über** — umgebrochen oder
      als bewusst scrollender Container benannt.
- [ ] Die beiden Dialoge (`ResourceBlockLinkPicker.tsx:180`,
      `PlaybookComposesPicker.tsx:103`) bleiben auf 320 px innerhalb der
      Fensterbreite und scrollen in sich — **über den W2-Primitive-Default**.
- [ ] Mehrspaltige Grids bleiben an einen Breakpoint gebunden. Gate, liefert
      **keine** Zeile:
      ```bash
      grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
        apps/web/src/features/playbooks | grep -v '\.test\.tsx'
      ```
- [ ] **Die BlockNote-Insel ist auf 320 px geprüft und das Ergebnis
      festgehalten** — inklusive Übertrag eines etwaigen Befunds ins
      `resources`-Issue. **Kein globaler `bn-*`-CSS-Override in diesem PR.**
- [ ] **Alle 16 Dateien sind in der Ist-Tabelle mit Befund oder begründetem
      „kein Defekt" abgehakt** — keine ungeprüfte Datei.
- [ ] Jeder neue Testfall war **vor** der Änderung rot (Test-first, CLAUDE.md
      §Workflow); die Coverage-Thresholds aus `apps/web/vite.config.ts:49-53`
      halten (Branches-Floor **79**).

### Scope

Genau die 16 Dateien unter `apps/web/src/features/playbooks/`, ihre
Testnachbarn, und `CHANGELOG.md` (§Unreleased, ein Eintrag, **als letzter
Commit** — Sammelpunkt).

### Out of scope

`components/ui/*` und `components/layout/*` (W2 hat dort entschieden; eine
Änderung wirkt auf alle dreizehn Domänen und ist ein eigenes Paket) · **jeder
globale `bn-*`/BlockNote-CSS-Override** (domänenübergreifend, eigenes Paket) ·
**`features/resources`** (teilt den BlockNote-Editor, ist aber ein eigenes
W3-Paket) · jede Änderung an Playbook-Datenmodell, Composite-Semantik,
Trigger-Auflösung oder Review-/Branch-Logik · jede andere Domäne unter
`features/` · W4 (Playwright-Mobile-Profile, E2E-Helfer „kein horizontaler
Body-Scroll") · echter Fullscreen-Dialog unter `sm` (#513 Weiche 3, verworfen) ·
ESLint-Regel für nackte `grid-cols-*` (#438 Weiche 5, verworfen) · `apps/api`,
`apps/mcp`, `packages/**`.

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
AK 8 gibt keine Zeile aus.

**Umgebung:** kein Docker-Daemon nötig (reines Web-Paket, Vitest ist DB-frei).
Das Paket fasst `apps/web/**` an und steht **nicht** auf der Doku-Allowlist
(`ci.yml:74`) — die schweren CI-Jobs laufen.

### Verweise

Tracking: **#431** (W3, Checklisteneintrag „Playbooks"). Norm:
`docs/frontend/design-language.md` §4.4 (Mobile-first, Prefix-Pflicht,
sechspunktige Review-Checkliste Z. 222–233) und §11 (A11y-Minimum 40 px),
CLAUDE.md §Frontend-Standards. Primitive-Belege: `components/ui/dialog.tsx:51`
(`w-[calc(100vw-2rem)] max-w-lg`), `components/ui/popover.tsx:48`
(`max-w-[calc(100vw-1rem)]`). Vorgänger: **#438** (W0), **#500** (W1 — Schwelle
`md`, `useEffect`-freies Muster), **#513** (W2 — Dialog-Inset, Caps im
Primitive, `tailwind-merge`).

**Kollision:** fasst `apps/web` an — nicht parallel zu einem anderen
`apps/web`-Paket im selben Arbeitsbaum, sondern nacheinander oder in getrennten
Worktrees (#442 §Wellen). i18n je Paket auf **einen** Namespace.
**`playbooks` ist mit 16 Dateien das größte der dreizehn W3-Pakete — die drei
größten (`playbooks` 16, `workarea` 14, `personas` 13) laufen nie zu zweit
gleichzeitig.** Zusätzlich: **nicht gleichzeitig mit `resources`**, weil beide
die BlockNote-Insel berühren.

### Component

Web UI (apps/web)
