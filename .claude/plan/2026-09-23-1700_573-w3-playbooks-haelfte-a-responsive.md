# 573 — W3 Playbooks Hälfte A: Responsive-Audit der fünf großen Dateien

Stand: 2026-09-23 · Branch `who2be/t_e1c18492-573-w3-playbooks-haelfte-a-responsive-au`
Basis: `origin/main` @ `c558860d` · Issue: #573 (Hälfte A) · Epic: #431 (W3)

## Auftrag

Fünf Dateien unter `apps/web/src/features/playbooks/` gegen die sechspunktige
Review-Checkliste aus `docs/frontend/design-language.md` §4.4 bei 320 / 375 /
768 / 1024 px prüfen, Defekte beheben, Nicht-Funde begründet abhaken. Die
übrigen elf Dateien der Domäne gehören zur Schwesterkarte (Hälfte B) und werden
**nicht angefasst**.

| Datei | Zeilen |
|---|---|
| `pages/PlaybookDetailPage.tsx` | 397 |
| `components/PlaybookListToolbar.tsx` | 341 |
| `components/ResourceBlockLinkPicker.tsx` | 334 |
| `components/PlaybookEditorForm.tsx` | 257 |
| `components/PlaybookComposesPicker.tsx` | 238 |

## Hinweis zur Zahl 40 px

`docs/frontend/design-language.md` §11 ist die **einzige** Quelle des
Hit-Target-Floors und setzt ihn auf **≥ 32 px**; 40 px ist dort die Präferenz
`size="default"`, `size="sm"` (36 px) bleibt ausdrücklich zulässig. Die 40 px in
diesem Paket kommen aus **AK 5 dieses Issues**, nicht aus der Norm. Keine Stelle
in Code, Test, Kommentar oder Changelog-Fragment schreibt die 40 px der Norm zu.

Davon zu unterscheiden sind die hier gemessenen **24-px- und 28-px-Stellen**:
die unterschreiten den Norm-Floor aus §11 und sind unabhängig vom AK Defekte.

## Methode — real gemessen, nicht geschätzt

jsdom hat kein Layout, AK 1–5 sind Layout-Aussagen. Deshalb eine
**Wegwerf-Messharness** (statisches HTML mit den wörtlichen Klassenlisten der
fünf Dateien und ihrer echten Elternkette `Container > Card > CardContent > …`
bzw. dem Dialog-/Popover-Primitive) gegen das **gebaute** Stylesheet
`dist/assets/index-kTcR54w2.css` aus dem eigenen `npm run build`, gefahren in
Chromium (Playwright) bei 320 / 375 / 768 / 1024 px.

Erfassungskriterien je Element:

- `child.right > parent.contentRight` — Überlauf gegen die **Eltern-Innenkante**,
  nicht nur gegen den Viewport.
- `scrollWidth > clientWidth` — **abgeschnittener** Inhalt (§4.4 Punkt 5), der
  keinen Body-Scroll erzeugt.
- gerenderte Höhe je interaktivem Element (§4.4 Punkt 4 / §11).

Weil `cn()` über `tailwind-merge` läuft, im statischen HTML aber nicht, sind die
Varianten-Klassen dort vorab aufgelöst notiert (z. B. `size="sm"` + `h-8` →
nur `h-8`) — sonst misst die Harness Höhen, die im Produkt nie entstehen.

Fixtures bewusst pessimistisch und domänentypisch: ein trennstellenfreier
Playbook-Name (`Onboarding-Checkliste_Vertrieb_Enterprise_2026`), ein langer
Persona-Name in der „Verwendet in"-Liste, ein langer Resource-Name im Picker,
ein 50-Zeichen-Trigger.

Harness und Skript liegen außerhalb des Repos (Scratch) und werden nicht
committet.

## Gemessener Body-Überlauf (AK 1) — vorher

| Viewport | `documentElement.scrollWidth` / `clientWidth` | Überläufer gegen Eltern-Innenkante |
|---|---|---|
| 320 | 437 / 320 ✗ | 6 |
| 375 | 437 / 375 ✗ | 6 |
| 768 | 768 / 768 ✓ | 0 |
| 1024 | 1024 / 1024 ✓ | 0 |

## Befund je Datei — alle fünf abgehakt

### `pages/PlaybookDetailPage.tsx` — Defekt, drei Stellen

- **`:132` Titel-`h1`.** Ein trennstellenfreier Playbook-Name misst bei 320 px
  **404,8 px in 288 px Innenraum (+116,8 px)**. `min-w-0` am Elternteil `:129`
  erlaubt das Schrumpfen, ein unbrechbares Wort läuft trotzdem über (§4.4 P5).
- **`:284` Relations-Grid.** Die vier `Card`s messen **421,3 px (+133,3 px)**.
  Ursache ist nicht die Spaltenzahl — das Grid ist mobile-first korrekt an `sm`
  gebunden —, sondern die Default-`min-width:auto` von Grid-Items: der
  `truncate`-Persona-Name `:316` trägt `whitespace-nowrap` und setzt damit die
  min-content-Breite der Spur auf die volle Textbreite. `truncate` greift erst,
  wenn das Item schrumpfen darf.
- **`:118` Zurück-Button.** Gemessen **36 px** (`size="sm"`). Nach §11 zulässig,
  nach AK 5 dieses Issues unterhalb `md` anzuheben.

**Erfüllt und nicht angefasst:** `:284` `sm:grid-cols-2` und `:285`/`:325`
`sm:col-span-2` (mobile-first gebunden, unterhalb `sm` einspaltig) · `:128`
`flex-wrap` und `:156` Aktions-Reihe (40 px, brechen um) · `:240`
Danger-Zonen-Toggle (gemessen 44 px) · `:263` Löschen-Button (40 px).

### `components/PlaybookListToolbar.tsx` — Defekt, fünf Stellen

- **`:133` Segment-Gruppe.** `inline-flex … gap-1 rounded-lg bg-muted p-1`
  **ohne `flex-wrap`**: gemessen **388,5 px in 288 px (+100,5 px)** — der
  schwerste Fund des Pakets, und ein anderer als der im Issue vermutete. Die
  Gruppe wächst mit jedem sichtbaren Status; vier Segmente reichen schon.
- **`:75` Segment-Button** (`h-8`) — gemessen **32 px**.
- **`:183` Suchfeld-Clear** (`size-8`) — gemessen **32 px**.
- **`:314`/`:330` Filter-Chips** (`h-7`) — gemessen **28 px**. Das
  **unterschreitet den Norm-Floor aus §11 (≥ 32 px)** und ist unabhängig vom AK
  ein Defekt.
- **`:296` Reset-Button im Popover** (`h-8`) — gemessen **32 px**.

**Erfüllt und nicht angefasst:** `:162` `min-w-48` am Suchfeld — gemessen
**kein Defekt**: sobald die Zeile umbricht, steht das Feld mit 288 px allein,
und 192 px Mindestbreite passen auch in die geteilte Zeile nicht hinein, weil
sie dann umbricht. Weiche 1 aus #431 (kein Prefix ohne gemessenen Defekt) gilt,
Vorentscheidung 2 des Issues beschreibt nur *wie* zu binden wäre, falls ein
Defekt vorläge · `:200` Popover `w-72` — gemessen 288 px bei 320 px Viewport,
durch `max-w-[calc(100vw-1rem)]` des Primitives gedeckelt · `:131`/`:309`/`:325`
`flex-wrap` · die fünf Popover-`Select`s (40 px) · `:192` Filter-Trigger (40 px).

### `components/ResourceBlockLinkPicker.tsx` — Defekt, zwei Stellen

- **`:199` Resource-Zeilen-Button.** `w-full justify-start` erbt das
  `whitespace-nowrap` der Button-Basis: ein langer Resource-Name wird
  abgeschnitten (`scrollWidth` **344 px** in **238 px** sichtbar) — und zwar bei
  320, 375 **und 768 px**, also auch oberhalb der Mobile-Schwelle.
- **`:251`/`:263` Embed-Modus-Buttons** (`h-6`) — gemessen **24 px**.
  **Unterschreitet den Norm-Floor aus §11.**

**Erfüllt und nicht angefasst:** `:180` `DialogContent max-w-3xl` — gemessen
288 px bei 320 px Viewport, `w-[calc(100vw-2rem)]` des Primitives bleibt
bestehen (Vorentscheidung 4) · `:192` `grid-cols-1 sm:grid-cols-2` · die
Block-Labels `:300`–`:312` (brechen um, kein Überlauf, auch bei langen
Heading-Texten) · die Checkboxen (16 px, nicht-interaktive Trefferfläche liegt
auf dem zugehörigen `Label`).

### `components/PlaybookComposesPicker.tsx` — Defekt, vier Stellen

- **`:125` Kind-Zeile.** `flex items-center justify-between gap-2` **ohne
  `flex-wrap`**: min-content **319,1 px** in **238 px** Dialog-Innenraum. Weil
  `DialogContent` ein `grid` ist, zieht die Zeile den gesamten Dialog-Inhalt auf
  (`scrollWidth` 367 px in 286 px) — der vom Issue vorhergesagte Hauptbefund,
  hier gemessen bestätigt.
- **`:138`/`:149` Move-Buttons** (`h-6 w-6`) — gemessen **24 × 24 px**.
- **`:160` Entfernen-Button** (`h-6`) — gemessen **24 px**.
  Beide **unterschreiten den Norm-Floor aus §11**.

**Erfüllt und nicht angefasst:** `:103` `DialogContent max-w-lg` — redundant zum
Primitive-Default, aber ohne Defekt; Vorentscheidung 4 verbietet die
Aufräumarbeit ausdrücklich · `:178` `max-h-60 overflow-auto` (bewusst
gescrollter Container, §4.4 P1) · `:187` Auswahlzeilen (brechen um,
gemessen kein Überlauf).

### `components/PlaybookEditorForm.tsx` — kein Defekt

Alle gemessenen Elemente liegen bei 320 px exakt auf den 238 px Innenraum von
`Card > CardContent`, kein Überlauf und kein abgeschnittener Inhalt auf keinem
der vier Viewports: `Input` Name/Beschreibung und `Select` Typ je 238 × 40 px,
die Validierungsmeldung bricht um (60 px hoch statt abgeschnitten), der
`FormSection`-Kopf 238 px, der `TagInput` bricht seine Pillen bei 320 px auf
drei Zeilen um (`flex-wrap` im Primitive), das Eingabefeld darin misst 40 px.
Kein Grid, keine feste Breite, kein `min-w-0` nötig — der Klassen-Nicht-Befund
des Issues ist **gemessen bestätigt**.

**Primitive-Fund, gemeldet statt repariert:** der `InfoTooltip`-Trigger neben
dem Section-Titel misst **24 × 24 px** und unterschreitet damit den Norm-Floor
aus §11. Er sitzt in `components/ui/info-tooltip.tsx` und ist damit
domänenübergreifend — außerhalb des Scopes dieses Pakets (Karten-Rahmen: „Keine
Primitives unter `components/ui/` ändern — melden statt reparieren").

### BlockNote-Insel

`PlaybookBodyEditor.tsx` gehört zur Schwesterkarte (Hälfte B) und ist hier nicht
im Scope. `PlaybookEditorForm.tsx:193` rendert die Komponente nur; die Insel
selbst wird von Hälfte B geprüft. Kein `bn-*`-Override in diesem PR.

## Fix — elf Stellen, vier Dateien

Weiche 1 aus #431 gilt: kein Breakpoint-Prefix ohne gemessenen Defekt. Die
`md:`-Prefixe stehen dort, wo die Mobile-Lösung die Desktop-Dichte sonst
verschlechtern würde.

1. **`PlaybookDetailPage.tsx:132`** — `min-w-0 break-words` am Titel-`h1`. Das
   `min-w-0` ist notwendig: als Flex-Item greift `break-words` sonst nicht, weil
   das Item nicht unter seine min-content-Breite schrumpfen darf. Nachgemessen
   ohne `min-w-0` blieb der Überlauf bei exakt +116,8 px stehen.
2. **`PlaybookDetailPage.tsx:285`/`:325`/`:346`/`:355`** — `min-w-0` an den vier
   `Card`s des Relations-Grids. Die Klasse an der **Aufrufstelle**, nicht im
   Primitive: das Grid-Item muss schrumpfen dürfen, damit `truncate` greift.
3. **`PlaybookDetailPage.tsx:118`** — `min-h-10 md:min-h-0` am Zurück-Button.
4. **`PlaybookListToolbar.tsx:133`** — `flex-wrap` an der Segment-Gruppe.
5. **`PlaybookListToolbar.tsx:75`** — `min-h-10 md:min-h-0` am Segment-Button
   (`min-height` gewinnt gegen das `h-8` derselben Klassenliste).
6. **`PlaybookListToolbar.tsx:183`** — `h-10 md:h-8` am Clear-Button. Nur die
   Höhe: die Breite bleibt bei 32 px, weil das `pr-9` des Feldes genau 36 px
   Platz lässt.
7. **`PlaybookListToolbar.tsx:314`/`:330`** — `h-10 md:h-7` an den Filter-Chips.
8. **`PlaybookListToolbar.tsx:296`** — `min-h-10 md:min-h-0` am Reset-Button.
9. **`ResourceBlockLinkPicker.tsx:199`** — `h-auto min-h-10 py-2 text-left
   whitespace-normal break-words` am Resource-Button. Ohne `md:`-Rückfall: der
   Abschnitt tritt auch bei 768 px auf.
10. **`ResourceBlockLinkPicker.tsx:251`/`:263`** — `h-10 md:h-6` an den
    Embed-Modus-Buttons.
11. **`PlaybookComposesPicker.tsx:125`** — `flex-wrap` an der Kind-Zeile plus
    `min-w-0` am Namens-`span` (Vorentscheidung 1: umbrechen, kein
    Overflow-Menü), und `h-10 md:h-6` an den drei Zeilen-Aktionen `:138`/`:149`/
    `:160` (`w-10 md:w-6` an den beiden Move-Buttons).

## Tests

Test-first nach CLAUDE.md §Workflow: jeder neue Fall war vor der Änderung rot.
jsdom hat kein Layout, deshalb sind es **Klassen-Verträge**; die Layout-Aussage
selbst ist in diesem Plan gerendert belegt. Muster wörtlich wie in #568/#572
(`min-h-10` + `md:`-Rückfall), damit kein Pattern Drift entsteht.

## Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b
npm run test:coverage
npm run build
```

Plus die Neumessung derselben Harness gegen das neu gebaute Stylesheet.

## Gemessener Body-Überlauf (AK 1) — nachher

| Viewport | `documentElement.scrollWidth` / `clientWidth` | Überläufer gegen Eltern-Innenkante |
|---|---|---|
| 320 | 320 / 320 ✓ | 0 |
| 375 | 375 / 375 ✓ | 0 |
| 768 | 768 / 768 ✓ | 0 |
| 1024 | 1024 / 1024 ✓ | 0 |

Verbleibend gemeldet wird allein der Persona-Name in der „Verwendet in"-Liste
(`scrollWidth` 339 px in 206 px) — das ist das beabsichtigte `truncate`, also
das vom AK ausdrücklich erlaubte **kontrollierte Kürzen**, kein Überlauf.

Hit-Targets nach dem Fix, bei 320 px gemessen:

| Stelle | vorher | nachher |
|---|---|---|
| `PlaybookComposesPicker` Move-Buttons | 24 × 24 px | 40 × 40 px |
| `PlaybookComposesPicker` Entfernen | 24 px | 40 px |
| `ResourceBlockLinkPicker` Embed-Modus | je 24 px | je 40 px |
| `PlaybookListToolbar` Filter-Chips | 28 px | 40 px |
| `PlaybookListToolbar` Segment-Buttons | 32 px | 40 px |
| `PlaybookListToolbar` Suchfeld-Reset | 32 px | 40 px |
| `PlaybookListToolbar` Popover-Reset | 32 px | 40 px |
| `PlaybookDetailPage` Zurück-Link | 36 px | 40 px |

Ab `md` fallen alle Maße auf die vorherige Desktop-Dichte zurück; die
Resource-Zeile im Picker bleibt bewusst ohne `md:`-Rückfall, weil ihr Abschnitt
auch bei 768 px auftrat.
