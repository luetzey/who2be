# K4 (#431) — BlockNote auf Tablet bedienbar, auf Phone lesbar

Stand: 2026-09-24 · Branch `who2be/t_1a4f5f3f-welle-7-k4-blocknote-auf-tablet-bedienba`
Basis: `origin/main` @ `116bfcd2` · Epic: #431 (W3/W7) · Kanban: `t_1a4f5f3f`

## Auftrag

Das letzte offene Akzeptanzkriterium von #431: BlockNote auf Tablet **bedienbar**,
auf Phone **lesbar + Basis-Editing**. Zuerst messen, dann trennen in
behebbar / Bibliotheksbefund / Design-Frage. Nicht gegen eine strengere Latte
messen als die genannte.

**Gemessen wurde gegen den Floor aus `docs/frontend/design-language.md` §11:
„Verbindlich ist ein Floor von ≥ 32px (HIG)."** Nicht gegen die 44px aus dem
Epic-Body von #431 — §11 sagt im eigenen Wortlaut, es sei „die einzige Quelle
des Floors", und 44px sind dort ausdrücklich „Praeferenz", kein Mindestwert.

## Methode — real gemessen, nicht geschätzt

jsdom hat kein Layout. Gemessen wurde wie in #564: Wegwerf-Harness
(`probe.html` + `src/probe.tsx`, **nicht committet**) gegen den echten
Vite-Dev-Server, per Chrome DevTools Protocol mit
`Emulation.setDeviceMetricsOverride` + `Emulation.setTouchEmulationEnabled`.

Profile: **320×568**, **iPhone 13 (390×664, dpr 3, touch)**,
**iPad gen 7 (810×1080, dpr 2, touch)**, dazu die Schwellenpaare
**767 / 768 px** zur Prüfung der `md`-Grenze.

Fixture: Heading + langer Fließtext-Absatz + Listeneintrag im `BlockNoteEditor`
mit `editable`, gemountet unter `ThemeProvider`, also mit derselben Insel-CSS
wie in der App.

Ausgelöst wurde jedes Overlay so, wie es die Bibliothek erwartet: Slash-Menü
per `/` nach `Enter`, Formatting-Toolbar per Maus-Drag-Selektion,
Side-Menu/Drag-Handle per `mousemove` über den Block **und** per reinem
`Input.dispatchTouchEvent`-Tap.

## Messprotokoll (Ist-Zustand auf `116bfcd2`)

### 1. Editor-Textfläche — trägt der #564-Fix?

| Viewport | `.bn-container` | `.bn-editor` | `padding-inline` | Textfläche |
|---|---|---|---|---|
| 320 | 288 px | 286 px | **12 px** | **262 px** |
| 390 (iPhone 13) | 358 px | 356 px | **12 px** | **332 px** |
| 810 (iPad gen 7) | 778 px | 776 px | 54 px | 668 px |

**Der Fix trägt.** Statt der in #564 gemessenen 128 px Textfläche bei 320 px
stehen jetzt 262 px — gut das Doppelte, ≈ 33 statt ≈ 16 Zeichen je Zeile. Ab
`md` ist das BlockNote-Default (54 px) unverändert, der Desktop ist unberührt.
Kein Body-Überlauf auf irgendeinem Profil (`scrollWidth == clientWidth`).

### 2. Side-Menu (Drag-Handle + „Add block") — **neuer Defekt, Folge des #564-Fixes**

BlockNote positioniert den Side-Menu-Wrapper per Inline-Transform relativ zum
Rand der Block-Content-Spalte, mit festem Offset nach links. Gemessen am
Wrapper: `transform: translate(-21px, 134px)`.

| Viewport | `padding-inline` | Side-Menu `x` … `right` | im Viewport? | „Add block" `x` |
|---|---|---|---|---|
| 320 | 12 px | **−21 … 29** | **nein** | **−20** (24×24) |
| 390 | 12 px | **−21 … 29** | **nein** | **−20** (24×24) |
| 767 | 12 px | **−21 … 29** | **nein** | **−20** (24×24) |
| 768 | 54 px | 21 … 71 | ja | 22 (24×24) |
| 810 | 54 px | 21 … 71 | ja | 22 (24×24) |

**Gegenprobe, die die Ursache belegt:** dieselbe Messung bei 390 px, aber mit
per Inline-`<style>` erzwungener 54-px-Rinne → Side-Menu bei `x = 21`,
`within = true`. Die 42 px, die der #564-Fix aus der Rinne nimmt, sind exakt
die 42 px, um die das Menü nach links aus dem Viewport rutscht.

**Die im #564-Kommentar genannte Begründung „die Rinne ist unterhalb `md`
funktionslos, weil das Side-Menu per Hover erscheint, den es auf Touch nicht
gibt" ist so nicht haltbar.** Gemessen: nach einem reinen
`touchStart`/`touchEnd`-Tap auf einen Block ist `.bn-side-menu` im DOM,
`visibility: visible`, `opacity: 1` — Chromium feuert nach einem Tap die
Compatibility-Mouse-Events, und BlockNotes `mousemove`-Handler
(`extensions-D6JcJCwd.js`, `SideMenuPlugin`) greift darauf an. Das Menü ist auf
Touch also **nicht** abwesend, sondern **halb außerhalb des Viewports**.

### 3. Formatting-Toolbar — Hit-Targets unter dem Floor

Auf **allen** gemessenen Profilen sind die Toolbar-Buttons **30 × 30 px**.
§11 verlangt ≥ 32 px „auf keinem Breakpoint" darunter.

| Viewport | Toolbar-Rect | im Viewport? | `scrollWidth` / `clientWidth` | kleinster Button |
|---|---|---|---|---|
| 320 | 0, 94, 320 × 36 | ja | 375 / 318 (scrollt) | **18,7 × 30** (Block-Typ) |
| 390 | 0, 94, 390 × 36 | ja | 388 / 388 | 30 × 30 |
| 810 | 71, 62, 484 × 36 | ja | 482 / 482 | 30 × 30 |

12 Buttons, keiner außerhalb des Viewports. Der horizontale Scroll bei 320 px
ist ein bewusster Scroll-Container (`overflow-x: auto` von BlockNote) und nach
§4.4 Checklistenpunkt 1 zulässig — **kein** Defekt. Defekt sind allein die
Höhen (30 px) und die auf **18,7 px** zusammengedrückte Breite des
Block-Typ-Buttons bei 320 px (`flex-shrink: 1`, `min-width: auto`).

### 4. Slash-Menü — kein Defekt

| Viewport | Rect | im Viewport? | Items | kleinste Item-Höhe |
|---|---|---|---|---|
| 320 | 32, 10, **288 × 341** | ja | 23 | **54 px** |
| 390 | 38, 323, **352 × 398** | ja | 23 | **54 px** |
| 767 | 53, 219, 352 × 480 | ja | 23 | 54 px |

`max-width: min(28rem, calc(100vw - 2rem))` und `max-height: min(60vh, 480px)`
aus der bestehenden Insel greifen; `overflow-y: auto`, `scrollHeight` 1488 bei
`clientHeight` 396 → alle 23 Einträge erreichbar. Item-Höhe 54 px liegt
deutlich über dem Floor. **Auf Touch auslösbar** (Tap → Fokus im
`contenteditable`, `/` öffnet das Menü).

### 5. Drag-Handle-Menü („Open block menu") — Hit-Targets unter dem Floor

Gemessen auf iPad (810 px, dort ist das Side-Menu erreichbar): Dropdown
`78, 84, 100 × 66`, im Viewport. Einträge **„Delete" 94 × 30** und
**„Colors" 94 × 30** — 30 px, unter dem Floor.

### 6. Side-Menu-Buttons selbst

„Add block" und „Open block menu" messen je **24 × 24 px**, auf jedem Profil.
Deutlich unter dem Floor.

## Dreiteilige Einordnung jedes Funds

| # | Fund | Einordnung |
|---|---|---|
| F1 | Textfläche 262 px @ 320 px | **kein Defekt** — #564-Fix trägt, nachgemessen |
| F2 | Side-Menu ragt unterhalb `md` um 21 px links aus dem Viewport | **behebbar (Klassen-/CSS-Änderung)** → in dieser Karte behoben |
| F3 | Toolbar-Buttons 30 px, Block-Typ-Button 18,7 px @ 320 px | **behebbar (CSS)** → in dieser Karte behoben |
| F4 | Side-Menu-Buttons 24 px | **behebbar (CSS)** → in dieser Karte behoben |
| F5 | Drag-Handle-Menü-Einträge 30 px | **behebbar (CSS)** → in dieser Karte behoben |
| F6 | Slash-Menü | **kein Defekt** |
| F7 | Toolbar scrollt horizontal @ 320 px | **kein Defekt** — bewusster Scroll-Container, §4.4 Punkt 1 |
| F8 | Side-Menu erscheint auf Touch über Compatibility-Mouse-Events, nicht über einen Touch-Pfad; es gibt in 0.54.2 keinen Touch-eigenen Trigger | **Bibliotheksbefund** — nicht gepatcht, nur gemeldet |
| F9 | Der 30-px-Default der Mantine-`ActionIcon` in `@blocknote/mantine` liegt repo-weit unter §11 | **Bibliotheksbefund**, von uns per Override kompensiert statt gepatcht |
| F10 | Soll das Side-Menu auf dem Phone ganz entfallen oder in die Fläche zurückgeholt werden? | **Design-Frage an den PM** — siehe unten |

## Fix

Alles in `apps/web/src/styles/globals.css`, §BlockNote-Insel. Keine
Bibliotheksänderung, kein neuer Breakpoint — die Schwelle bleibt `md` (767 px).

1. **F2 — Side-Menu unterhalb `md` ausblenden.** Der Zustand vorher ist in
   keiner Lesart gut: ein Bedienelement, das zu 42 % außerhalb des Viewports
   liegt, ist weder bedienbar noch lesbar. Zwei Wege wären möglich:
   Rinne zurück auf 54 px (macht den gemessenen #564-Fix rückgängig und halbiert
   die Textfläche wieder) oder das Menü unterhalb `md` entfernen. Nur der zweite
   erfüllt beide Latten gleichzeitig. Das Basis-Editing bleibt vollständig:
   neuer Block per `Enter`, Blocktyp per Slash-Menü, Löschen per `Backspace`,
   Formatieren über die Toolbar. Verloren geht auf dem Phone allein das
   Drag-Handle-Menü (Delete/Colors) und der „+"-Knopf — Komfort, nicht Basis.
2. **F3 — Toolbar-Buttons auf 32 px.** `min-height`/`min-width: 32px` an
   `.bn-toolbar .bn-button`, dazu `flex-shrink: 0` und eine `min-width` am
   Block-Typ-Button, damit er bei 320 px nicht mehr auf 18,7 px kollabiert. Die
   Toolbar scrollt dadurch bei 320 px etwas weiter — das ist der bereits
   vorhandene, zulässige Scroll-Container.
3. **F4 — Side-Menu-Buttons auf 32 px** (wirksam ab `md`, wo das Menü nach
   Fix 1 überhaupt noch erscheint).
4. **F5 — Drag-Handle-Menü-Einträge auf 32 px** `min-height`.

## Regressionstest

`apps/web/src/components/editor/BlockNoteEditor.test.tsx` — dasselbe Muster wie
die dort bestehenden Insel-Tests: CSS-Vertrag gegen `globals.css`, weil jsdom
kein Layout hat und `@blocknote/mantine` in der Suite global gemockt ist. Die
Layout-Aussagen selbst sind oben gerendert belegt.

## Offene Frage an den PM (F10)

Der Fix blendet das Side-Menu unterhalb `md` aus. Damit sind „Block löschen"
und „Block-Farbe" auf dem Phone nur noch über Tastatur bzw. gar nicht
erreichbar. Gegen die Latte dieser Karte („Phone: lesbar + Basis-Editing") ist
das erfüllt; wenn das Produkt auf dem Phone mehr als Basis-Editing will, ist
das eine eigene Karte (Side-Menu als Touch-Affordance, z. B. per Long-Press
oder als Bottom-Sheet) und kein CSS-Fix.

## Ergebnis gegen das Kriterium

### Nachmessung nach dem Fix (gebautes CSS, gleiche Harness)

| Messgroesse | 320 | 390 (iPhone 13) | 810 (iPad gen 7) |
|---|---|---|---|
| Textflaeche | 262 px | 332 px | 668 px |
| Body-Ueberlauf | keiner | keiner | keiner |
| Toolbar im Viewport | ja | ja | ja |
| kleinster Toolbar-Button | **32 × 32** | **32 × 32** | **32 × 32** |
| Side-Menu | `display: none` | `display: none` | `x = 5`, im Viewport, Buttons **32 × 32** |
| Drag-Handle-Menue-Eintraege | — | — | **94 × 32**, im Viewport |
| Slash-Menue | 288 px, im Viewport, 23 Items, Item-Hoehe 54 px | 352 px, im Viewport | 352 px, im Viewport |

Vorher/nachher der behobenen Funde: Toolbar-Buttons 30 → 32, Block-Typ-Button
18,7 → 32, Side-Menu-Buttons 24 → 32, Drag-Handle-Eintraege 30 → 32,
Side-Menu bei `x = -21` → unterhalb `md` entfernt.

### Basis-Editing auf dem Phone — per reinem Touch belegt

Bei 390 px, ausschliesslich mit `Input.dispatchTouchEvent` (kein
Maus-Event): Tap in den Editor → Fokus im `contenteditable`; `Enter` → neuer
Block; `/` + „Head" → Slash-Menue mit Treffer; Touch-Tap auf „Heading 1" →
Dokument geht von `['heading','paragraph','bulletListItem']` auf
`['heading','paragraph','bulletListItem','heading']`. Blocktyp-Wechsel auf dem
Phone funktioniert also ohne Side-Menu.

### Regressionstest

`BlockNoteEditor.test.tsx`, 5 neue Faelle. Rot-Probe gefahren: mit
`globals.css` von `origin/main` und den neuen Tests → **5 failed / 21 passed**;
mit dem Fix → **26 passed**.

### Antwort

**Ja, das Kriterium ist erfuellt.**

- **Tablet bedienbar:** alle Overlays im Viewport, alle Hit-Targets auf dem
  Floor aus §11 (32 px), Side-Menu und Drag-Handle-Menue erreichbar.
- **Phone lesbar + Basis-Editing:** 262 px Textflaeche bei 320 px, kein
  Ueberlauf, Toolbar und Slash-Menue im Viewport und auf dem Floor;
  Basis-Editing per Touch nachgewiesen.

**Einschraenkung, die zur Antwort gehoert:** auf dem Phone sind „Block
loeschen" und „Block-Farbe" seit diesem Fix nur noch ueber die Tastatur bzw.
gar nicht erreichbar, weil das Side-Menu dort entfaellt. Gegen die Latte
dieser Karte („lesbar + Basis-Editing", ausdruecklich nicht „voller
Funktionsumfang auf 320 px") ist das erfuellt. Will das Produkt auf dem Phone
mehr, ist das die Design-Frage F10 und eine eigene Karte.

