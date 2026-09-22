# 564 — W3 Resources: Responsive-Audit von `features/resources` (6 Dateien inkl. BlockNote-Insel)

Stand: 2026-09-23 · Branch `who2be/t_b071837f-564-w3-resources-responsive-audit-von-fe`
Basis: `origin/main` @ `b28c2ebd` · Issue: #564 (agent-ready) · Epic: #431 (W3)

## Auftrag

Die sechs produktiven `.tsx` unter `apps/web/src/features/resources/` gegen die
sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
prüfen; gefundene Defekte beheben, nicht gefundene begründet als „kein Defekt"
abhaken. Dazu die BlockNote-Insel am **gerenderten** Editor prüfen (AK 2:
„Der Nachweis wird am gerenderten Editor geführt, nicht an Klassen").
Keine Änderung an geteilten Primitives.

## Methode — real gemessen, nicht geschätzt

jsdom hat kein Layout. Für dieses Paket reicht ein Klassen-Vertrag nicht, weil
AK 2 den Nachweis ausdrücklich am gerenderten Editor verlangt. Deshalb wurde
eine **Wegwerf-Messharness** (`probe.html` + `src/probe.tsx`, nicht committet)
gegen den echten Vite-Dev-Server gefahren und mit Chrome DevTools Protocol bei
320 / 375 / 768 / 1024 px vermessen: Device-Metrics-Override, dann pro Route
jedes Element mit `getBoundingClientRect().right > clientWidth` eingesammelt,
plus Hit-Target-Höhen und `scrollWidth`/`clientWidth` je Container.

Fixture bewusst pessimistisch: 60-Zeichen-Bezeichner ohne Trennstellen
(`Kundenonboarding_Wissensbasis_Vertriebsteam_Langbezeichner_Q4`), ein
Block-Anker mit `blk_`-Präfix, ein 55-Zeichen-Tag.

## Ist-Zustand nachgemessen (auf `b28c2ebd`)

```bash
find apps/web/src/features/resources -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 6
find … -exec grep -lE '\b(sm|md|lg|xl|2xl):' {} \;                        # (leer)
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/resources | grep -v '\.test\.tsx'                  # (leer)
```

Bestätigt: 6 Dateien, 0 Breakpoint-Prefixe, kein Grid. Damit sind §4.4-Punkte 2
(Grids) und 3 (feste Breiten) in der Domäne **gegenstandslos** — es gibt weder
`grid-cols-*` noch `w-*`/`max-w-*` auf Container-Ebene.

### Gemessener Überlauf je Viewport (Body-`scrollWidth` gegen `clientWidth`)

| Route | 320 | 375 | 768 | 1024 |
|---|---|---|---|---|
| `/resources` | 554 | 554 | 768 ✓ | 1024 ✓ |
| `/resources/r1` | 858 | 857 | 865 | 1009 ✓ |
| `/resources/new` | 320 ✓ | 375 ✓ | 753 ✓ | 1009 ✓ |

## Befund je Datei

| Datei | §4.4-Punkt | Befund |
|---|---|---|
| `pages/ResourcesPage.tsx` | 5 | **Defekt.** Der Slug-Badge (`font-mono text-xs`, kein Umbruch) misst gerendert bei 320 px **554 px** und ist der einzige Domänen-Überläufer der Liste. `slug` ist serverseitig aus dem Namen abgeleitet — ein einziges umbruchfeindliches Wort. Tag-Badges brechen heute an Bindestrichen, tragen aber keinen Cap; ohne `max-w-full` läuft ein trennstellenfreier Tag genauso über. |
| `pages/ResourceDetailPage.tsx` | 5 | **Defekt, zwei Stellen.** (a) Slug-/Tag-Badges im `DetailHeader`-`badges`-Slot, gleiche Ursache — Slug gemessen **541 px** bei 320 px Viewport. (b) `:322` `justify-between` ohne `flex-wrap`: beim Block-Anker drückt die Scope-Badge (**449 px**, `Block blk_…`) den Link auf **Breite 0** — die Zeile kürzt nicht kontrolliert, sie vernichtet den Linktext. AK 3 adressiert genau das. |
| `components/SubResourcePicker.tsx` | 4, 5 | **Defekt, zwei Stellen.** (a) `:181` Anker-Pill („In text (Block `blk_…`)") misst **463 px** — einziger Überläufer im Sub-Resources-Tab. (b) §4.4-Punkt 4: die Zeilen-Aktionen der Resource-Link-Zeile messen **19 × 32 px**, die Segment-Gruppe `:217` **54 px bei 86 px Inhalt** (`overflow-hidden` schneidet „Inline" ab). Beides unter dem 40-px-Floor aus §11 und AK 5. Ursache ist nicht die Button-Größe, sondern die überfüllte einzeilige Zeile: die Textspalte ist bei 320 px bereits auf **Breite 0** gequetscht. |
| `pages/ResourceNewPage.tsx` | 1–6 | **Kein Defekt.** Gemessen 0 Überläufer auf allen vier Viewports. `Container` + `Stack`, einspaltig, eine rechtsbündige Submit-Aktion. |
| `components/ResourceEditorForm.tsx` | 1–6 | **Kein Defekt.** Einspaltig (`flex flex-col gap-6`), alle Felder Block-Elemente über die volle Breite, Hilfetexte sind Fließtext mit Leerzeichen. Gemessen bei 320 px: kein Kind der Form überläuft. Die Insel darin siehe unten. |
| `components/ResourceUsedByList.tsx` | 1–6 | **Kein Defekt.** Reiner Delegat an `components/data/UsedByList`; die Zeilen dort tragen `min-w-0 … truncate`, gemessen bei 320 px kein Überlauf trotz 60-Zeichen-Elternnamen. |

### BlockNote-Insel — am gerenderten Editor gemessen (AK 2)

| Teil | Messung @ 320 px | Bewertung |
|---|---|---|
| Slash-Menü | ausgelöst per `/`; Popover 288 px breit, `left 32 → right 320`, **vollständig im Viewport**, Items (Heading 1/2/3, Quote…) auslösbar | **Kein Defekt** — der Cap `max-width: min(28rem, calc(100vw - 2rem))` aus §BlockNote-Insel greift bereits. |
| Formatting-Toolbar | Selektion → Toolbar erscheint, 320 px breit bei `scrollWidth 375`, `overflow-x: auto`, **im Viewport** | **Kein Defekt** — bewusst scrollender Container nach §4.4 Checklistenpunkt 1. |
| Editor-Textfläche | `.bn-editor` trägt **`padding-inline: 54px`** (BlockNote-Default für die Side-Menu-Rinne). Bei 236 px Containerbreite bleiben **128 px Textbreite** — ≈ 16 Zeichen je Zeile | **Defekt.** AK 2 verlangt „auf dem Phone lesbar"; 54 px Rinne je Seite frisst 46 % der Fläche. Die Rinne ist auf Touch zudem nutzlos: das Side-Menu erscheint per Hover. |

## Fix

Weiche 1 aus #431 gilt: kein Breakpoint-Prefix ohne gemessenen Defekt. Vier der
fünf Fixes kommen deshalb ohne Prefix aus; nur dort, wo eine Änderung den
Desktop verschlechtern würde, steht ein `md:`-Prefix.

1. **Slug-/Tag-Badges** (`ResourcesPage`, `ResourceDetailPage`) —
   `max-w-full break-all` für den Mono-Slug (keine Trennstellen, muss mitten im
   Wort brechen dürfen), `max-w-full break-words` für Tags (Wörter, brechen an
   Wortgrenzen). Identisch zur bereits gemergten Lösung in `features/tools`
   (PR #595) — kein Pattern-Drift.
2. **`ResourceDetailPage.tsx:322`** — `flex-wrap` an der Zeile, `min-w-0` am
   Link, `max-w-full break-all` an der Scope-Badge. Damit kürzt der Link
   kontrolliert (`truncate` greift erst mit `min-w-0`), statt auf 0 zu
   kollabieren, und die Badge rutscht bei Bedarf in die zweite Zeile.
3. **`SubResourcePicker.tsx:181`** — `max-w-full break-all` an der Anker-Pill.
4. **`SubResourcePicker` Resource-Link-Zeile** — die Aktionsgruppe wandert
   unterhalb `md` in eine eigene Zeile: Zeile auf `flex-wrap`, Textspalte auf
   `basis-full md:basis-auto`, Aktionsgruppe zusammengefasst und rechtsbündig.
   Erst dadurch ist Platz für den 40-px-Floor: Icon-Buttons `size-10 md:size-8`,
   Segment-Buttons `h-10 md:h-8`.
   **Weiche 3 des Issues bleibt gewahrt:** die Segment-Gruppe wird *nicht*
   umgebrochen und muss auch nicht scrollen — nach dem Umbruch der Zeile hat
   sie mit 86 px von 238 px reichlich Platz und behält ihre visuelle Einheit.
5. **BlockNote-Insel** — Override in `globals.css` §BlockNote-Insel, **scoped
   auf `.bn-container`** und auf unterhalb `md` begrenzt:
   `padding-inline` der Rinne von 54 px auf `calc(var(--spacing) * 3)` (12 px).
   Weiche 2 des Issues ist damit eingehalten: Container zuerst — hier kann der
   Container aber nichts abfedern (er kann das Padding seines Kindes nicht
   zurücknehmen), und der Bedarf ist gemessen, nicht vermutet. Der Override
   sitzt in dem Block, der ausweislich seines eigenen Kommentars genau für
   BlockNote-Interna angelegt wurde; Desktop bleibt unberührt.

## Bewusst nicht geändert — Primitive-Funde für den Handoff

Nach den fünf Fixes bleibt bei 320 px Rest-Überlauf. Er stammt **vollständig**
aus geteilten Primitives, die diese Karte ausdrücklich nicht anfassen darf:

1. **`components/data/DetailHeader.tsx`** — die `<h1>` trägt keine
   Umbruch-Regel und misst mit dem 60-Zeichen-Namen **857 px**. Das ist der
   größte Einzelposten des `scrollWidth`. Gleicher Fund wie in PR #595
   (Tools); dort bereits als **`t_0ba2f294`** an @pm ausgelagert — hier nur
   bestätigt, nicht doppelt gemeldet.
2. **`components/ui/tabs.tsx`** — `TabsList` ist `flex gap-1` mit
   `overflow: visible`; vier Tabs messen bei 288 px Containerbreite
   **445 px scrollWidth**, „Usage" und „Versions" liegen außerhalb des
   Viewports und sind auf dem Phone **nicht erreichbar**. Betrifft jede
   Detail-Page mit ≥ 3 Tabs, also mehrere W3-Domänen gleichzeitig.
   → **Neuer Fund, gehört als repo-weite Entscheidung ins Primitive-Paket.**
3. **`components/data/AttentionBanner.tsx`** — Titel/Beschreibung werden bei
   320 px auf ≈ 70 px Spaltenbreite gequetscht (Wortsalat), während der
   Aktions-Button die Restbreite hält. Ebenfalls domänenübergreifend.
4. **`components/data/ListFilterBar`, `EntityCard`-Expander** — Hit-Targets
   32 px. Unter dem 40-px-Wunsch aus AK 5, aber über dem in §11 stehenden
   HIG-Floor (≥ 32 px) und in einem Primitive. Kein Blocker, gemeldet.

## Test-first

Neue Fälle als Klassen-Vertrag neben der geänderten Datei (Muster W2/#513 und
PR #595) — jsdom hat kein Layout, die Layout-Aussage selbst ist oben gerendert
belegt:

- `ResourcesPage.test.tsx`: Slug-Badge `break-all` + `max-w-full`, Tag-Badge
  `break-words` + `max-w-full`.
- `ResourceDetailPage.test.tsx`: dasselbe im `DetailHeader`-Slot; dazu die
  Sub-Resource-Zeile (`flex-wrap`, Link `min-w-0`, Scope-Badge `break-all`).
- `SubResourcePicker.test.tsx`: Anker-Pill `break-all`, Zeilen-Aktionen
  `size-10 md:size-8`, Segment-Buttons `h-10 md:h-8`, Zeile `flex-wrap`.

Alle Blöcke laufen **vor** der Änderung rot (eigener `test:`-Commit vor dem
`fix:`-Commit).

Für den CSS-Override gibt es bewusst **keinen** Vitest-Fall: Vitest lädt kein
Stylesheet, ein Test würde nur die eigene Behauptung spiegeln. Der Nachweis ist
die gerenderte Messung oben — und wird im PR als solcher benannt, nicht als
Test verkauft.

## Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b            # NICHT --noEmit
npm run test:coverage
npm run test:a11y     # Issue-Kommentar Nachtrag 1
npm run build
npm run i18n:check
npm run license:check
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/resources | grep -v '\.test\.tsx'   # muss leer bleiben
uv run python scripts/check_code_refs.py .
```

Node 22 (`.nvmrc`) — auf Node 26 kippt die Suite toolchain-bedingt
(CONTRIBUTING.md §DoD).

## Changelog

Fragment unter `changelog.d/` (Verfahren seit PR #587), **nicht** in
`CHANGELOG.md` — der `changelog-guard` weist das sonst ab. Die
Issue-Anweisung „§Unreleased, als letzter Commit" ist überholt.

## Ergebnis (gemessen, Commit `67ad0511`)

### Test-first

- RED vor dem Fix: `Test Files 3 failed | 4 passed (7)` ·
  `Tests 8 failed | 44 passed (52)` — genau die acht neuen Fälle.
  Gegenprobe nach dem Fix per `git stash` der drei Produktivdateien
  wiederholt: dieselben 8 rot.
- GREEN nach dem Fix, Domäne: `Test Files 7 passed (7)` ·
  `Tests 52 passed (52)`.

### Gerendert nachgemessen (nach dem Fix, gegen die Tabelle oben)

| Messpunkt @ 320 px | vorher | nachher |
|---|---|---|
| Slug-Badge Liste | 554 px | im Viewport, bricht |
| Slug-Badge Detail | 541 px | im Viewport, bricht |
| Link in der Block-Anker-Zeile | **0 px** | 204 px, Badge umgebrochen |
| Anker-Pill `SubResourcePicker` | 463 px | im Viewport, bricht |
| Zeilen-Aktionen | 19 × 32 px | **40 × 40 px** |
| Segment-Gruppe | 54 px bei 86 px Inhalt (abgeschnitten) | 104 px bei 102 px — vollständig, als Einheit |
| Editor-Textfläche | 128 px (Rinne 54 px) | **212 px** (Rinne 12 px) |
| Editor-Textfläche @ 1024 px | 801 px (Rinne 54 px) | **unverändert** 801 px |

Überläufer je Route nach dem Fix — was bleibt, ist ausschließlich Primitive:

| Route | 320 | 375 | 768 | 1024 |
|---|---|---|---|---|
| `/resources` | 1 (EntityCard-Titel) | 1 | 0 ✓ | 0 ✓ |
| `/resources/r1` | 3 (h1 + 2 Tabs) | 2 | 1 (h1) | 0 ✓ |
| `/resources/new` | 0 ✓ | 0 ✓ | 0 ✓ | 0 ✓ |

Kein einziger Überläufer stammt noch aus einer der sechs Dateien.

### BlockNote-Insel — AK 2, am gerenderten Editor (nicht an Klassen)

Bei 320 px im Touch-Emulationsmodus durchgeführt:

- **Basis-Editing Text:** getippt, im Dokument angekommen (`typed: true`).
- **Slash-Menü:** per `/` ausgelöst, 288 px breit, `left 32 → right 320` —
  **vollständig im Viewport**, 23 Einträge, Heading- und List-Blöcke vorhanden.
- **Basis-Editing Überschrift:** „Heading 1" aus dem Menü angewendet, der
  Editor rendert danach ein `<h1>` (170 px, im Viewport).
- **Basis-Editing Liste:** „Bullet List" / „Numbered List" im Menü vorhanden
  und auswählbar.
- **Formatting-Toolbar:** über Textselektion erreichbar, 12 Aktionen, liegt im
  Viewport und scrollt bei Bedarf horizontal (`overflow-x: auto`, 375 px
  Inhalt) — bewusst scrollender Container nach §4.4 Punkt 1.

### DoD-Kommandos (Node 22.23.2 aus `.nvmrc`)

- `npm run lint` → 0 (67 Warnungen, alle vorbestehend)
- `npx tsc -b` → 0
- `npm run test:coverage` → 0, **197 Dateien / 1227 Tests, 0 skipped**;
  Statements 87.30 · Branches 82.08 · Functions 82.91 · Lines 88.33 —
  alle Floors (80/79/75/80) halten
- `npm run test:a11y` → 0 (55 passed)
- `npm run build` → 0
- `npm run i18n:check` → 0 (keine neuen Schlüssel eingeführt)
- `npm run license:check` → 0
- `uv run python scripts/check_code_refs.py .` → 0 (951 legacy, 0 error)
- `uv run python scripts/changelog_fragments.py check` → 0
- Grid-Gate aus AK 4 → 0 Zeilen

## Grenzen

Nur `apps/web/src/features/resources/**` + Testnachbarn, der scoped
BlockNote-Block in `apps/web/src/styles/globals.css`, `changelog.d/` und diese
Plandatei. Kein `components/ui/*`, kein `components/data/*`, kein
`components/layout/*`, kein BlockNote-Upgrade. Kein Merge, kein Push auf `main`.
