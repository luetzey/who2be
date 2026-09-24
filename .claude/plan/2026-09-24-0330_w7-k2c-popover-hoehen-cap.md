# Welle 7 / K2c — Popover-Primitive: Hoehen-Cap (Befund B8)

Karte: t_beb889a0 · Basis: K2b-Branch @ 129b7d6e (Stapel-PR)

## Ziel

`PopoverContent` begrenzt seine Hoehe am verfuegbaren Platz und scrollt zu
hohen Inhalt in sich — so wie `DialogContent` es bereits tut. Damit wird der
Bestaetigen-Button des ResourcePickers auf 320px und 390px wieder klickbar.

## Befund, selbst nachgemessen

Die Karte nennt `--radix-popper-available-height` als naheliegenden Weg und
fordert, das selbst zu pruefen statt zu glauben. Geprueft an der installierten
Quelle (`@radix-ui/react-popper@1.3.7`, `@radix-ui/react-popover@1.1.23`):

- In react-popper 1.3.7 (dist/index.mjs, Zeile 148-157, `size`-Middleware): die
  `size`-Middleware von Floating UI
  schreibt `--radix-popper-available-width/-height` **an den Content-Knoten**
  (`elements.floating.style`), nicht an den Wrapper. Der Wert stammt aus
  `detectOverflow` und beruecksichtigt damit `collisionPadding` und die
  Ankerposition.
- In react-popover 1.1.23 (dist/index.mjs, Zeile 253-259, `PopoverContentImpl`):
  Popover re-exportiert die Variablen
  unter eigenem Namen: `--radix-popover-content-available-height:
  var(--radix-popper-available-height)`, gesetzt als Inline-`style` am selben
  Knoten, den `PopoverContent` mit `className` bestueckt.

Daraus die **Wahl**: `max-h-[var(--radix-popover-content-available-height)]`,
nicht `--radix-popper-*`. Beide zeigen auf denselben Wert; die
`--radix-popover-*`-Form ist die von Popover **oeffentlich zugesagte**
Schnittstelle (das `re-namespace exposed content custom properties` im Quelltext
sagt das woertlich), die Popper-Form ist ein Implementierungsdetail eine Ebene
tiefer. Eine `70vh`-Pauschale scheidet aus: sie kennt weder Ankerposition noch
`collisionPadding` — im gemessenen Trace waren bei einem Viewport von 568px und
Panel-Start y = 326px genau 234px verfuegbar, 70vh waeren 398px gewesen.

## Aenderung (4 Dateien)

1. `apps/web/src/components/ui/popover.tsx` — `max-h-[var(...)]` +
   `overflow-y-auto` in die Basisklassen, mit Begruendung im Kommentar analog
   `apps/web/src/components/ui/dialog.tsx@94c5cc74#DialogContent:44-51`. Bewusst
   genau ein `max-h-*` im String (tailwind-merge).
2. `apps/web/src/components/ui/popover.test.tsx` — zwei neue Tests im Muster
   `apps/web/src/components/ui/dialog.test.tsx@94c5cc74` (Test „begrenzt die
   Hoehe und scrollt zu hohen Inhalt in sich", Zeile 65-69); der bisherige
   Breiten-Test wird vom mitgeschleppten
   `max-h-[70vh] overflow-auto` befreit, damit er nur noch die Breite prueft.
3. `apps/web/src/features/system-prompts/components/PlaceholderHelp.tsx` —
   `max-h-[70vh] overflow-auto` entfernt (siehe unten).
4. `changelog.d/w7k2c-popover-hoehen-cap.fixed.md` — Fragment.

## PlaceholderHelp: entfernt, nicht belassen — Begruendung

Die Karte verlangt eine begruendete Wahl. Belassen haette bedeutet: der
Aufrufer-`max-h-[70vh]` gewinnt ueber tailwind-merge und **verdraengt** den
neuen Cap. Auf einem 320px-Viewport waeren 70vh = 398px gewesen, waehrend real
oft deutlich weniger verfuegbar ist — der Aufrufer haette den Fix an genau
dieser Stelle wieder ausgeschaltet. `overflow-auto` ist zudem seit dem Fix
redundant (`overflow-y-auto` steht in der Basis). Entfernen ist damit nicht
Kosmetik, sondern Voraussetzung dafuer, dass der Fix dort ueberhaupt greift.
Der zweite Test haelt genau diese Verdraengungs-Mechanik fest, damit sie
dokumentiert bleibt statt ueberraschend zuzuschlagen.

## Rot-Probe (Akzeptanzkriterium 2)

`npx vitest run src/components/ui/popover.test.tsx` **vor** dem Fix:

```
 ❯ src/components/ui/popover.test.tsx (6 tests | 2 failed) 442ms
     × begrenzt die Hoehe auf den verfuegbaren Platz und scrollt in sich
     × laesst einen engeren Aufrufer-Cap die Hoehe verdraengen
AssertionError: expected [ 'w2b-anim-pop', 'z-50', …(8) ] to include
  'max-h-[var(--radix-popover-content-av…'
 Tests  2 failed | 4 passed (6)
```

Nach dem Fix: 6 passed.

## Aufrufer-Pruefung (Akzeptanzkriterium 4)

17 Importstellen von `@/components/ui/popover`. Davon rendern nur 4 ein
`PopoverContent` — die uebrigen 13 importieren `Popover`, `PopoverTrigger`,
`PopoverAnchor` oder die Typen `Measurable`/`AnchorRef` und sind von einer
Klassenaenderung am Content-Knoten strukturell nicht beruehrbar (per `grep -rn
"PopoverContent" src` nachgezaehlt).

| Aufrufer | eigenes `max-h`? | Folge |
|---|---|---|
| `PickerPopover.tsx` (ResourcePicker, PlaybookPicker, ToolPicker, PersonaFieldPicker, DateFormatPicker, CatalogScopePicker, ResourcesCatalogScopePicker) | nein | erbt den Cap — das ist der Fix |
| `PlaceholderPreviewPopover.tsx` | nein am Content (`max-h-[60vh]` liegt an einem **inneren** `div`, andere Gruppe) | erbt den Cap, inneres Limit bleibt |
| `PlaybookListToolbar.tsx` | nein | erbt den Cap |
| `PlaceholderHelp.tsx` | vorher ja | entfernt, erbt jetzt den Cap |

## Norm

Der Kommentar in `apps/web/src/components/ui/dialog.tsx@94c5cc74#DialogContent:50`
beruft sich auf „Designsprache §4.4". §4.4
(`docs/frontend/design-language.md@52be7ed1#4.4 Responsive & Breakpoints:193-233`) ist „Responsive & Breakpoints" und
traegt eine Review-Checkliste, die in Punkt 1 den **horizontalen** Scroll bei
320px adressiert und in Punkt 5 die Lesbarkeit — eine Aussage zur
**Hoehen**-Begrenzung schwebender Panels steht dort nicht. Die Zuschreibung im
Nachbarcode wird deshalb **nicht uebernommen**. Der Fix ist eigenstaendig
begruendet: Punkt 1 der Checkliste verlangt, dass eine Aenderung bei 320px
rendert, ohne dass Inhalt unerreichbar wird; der gemessene Trace belegt, dass
genau das verletzt war.

## Verifikation

- `npx vitest run` (Web-Suite vollstaendig)
- `npx tsc -b`
- `npx eslint .`
- `npx prettier --check`
- E2E `journeys.spec.ts` auf mobile-320 / mobile-iphone-13 / tablet-ipad-gen-7
  ueber CI (`all-green` gegen den exakten Head-SHA)
