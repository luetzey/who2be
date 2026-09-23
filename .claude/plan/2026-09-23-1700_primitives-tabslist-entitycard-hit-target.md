# Drei Primitive-Funde aus dem Responsive-Audit #570 Haelfte A

Karte: t_9a9d5c66 · Branch: `who2be/t_9a9d5c66-primitives-tabslist-unscrollbar-320-px-e`
Basis: `origin/main` @ c558860d · Node 22.23.2 (Pflicht nach CONTRIBUTING.md)

## Ziel

Drei Defekte in geteilten Primitives beheben, die der Auditor von #570 gemessen
gemeldet, aber laut Karte nicht selbst anfassen durfte. Der Reviewer hat alle
drei am Quelltext bestaetigt. Reihenfolge nach Schwere:

1. `components/ui/tabs.tsx` — `TabsList` scrollt nicht und bricht nicht. Bei
   320 px ist der dritte Tab **unerreichbar** (+173 px ausserhalb der
   Innenkante). Ein nicht bedienbares Element — der einzige der drei Funde,
   der eine Funktion vollstaendig entzieht.
2. `components/data/EntityCard.tsx` — der Titel-`Link` traegt keine
   Umbruch-Erlaubnis, waehrend der description-Absatz direkt darunter
   `break-words` hat (PR #606 hat den Titel derselben Komponente ausgelassen).
3. `components/ui/checkbox.tsx` / `radio-group.tsx` — Hit-Target 16 px.
   **Echte Unterschreitung des Floors** aus `docs/frontend/design-language.md`
   §11 (>= 32 px verbindlich), nicht nur ein Akzeptanzkriterium-Thema.

## Normbezug — woher welche Zahl kommt

§11 ist die **einzige** Quelle des Hit-Target-Floors und setzt ihn auf
**>= 32 px**; 40 px ist der Regelfall (`size="default"`), 44 px die
Mobile-Praeferenz, `size="sm"` (36 px) ausdruecklich zulaessig. Dieses Paket
zielt auf **32 px** fuer Checkbox und RadioGroupItem — der Floor, nicht mehr.
Eine hoehere Zahl haette hier kein Akzeptanzkriterium, aus dem sie herzuleiten
waere (anders als in #570, wo AK 4 die 40 px setzte). Das Paket schreibt der
Norm also keine Zahl zu, die dort nicht steht — der Fehler, der #568, #569
und #572 blockiert hat.

## Messverfahren

Chromium (Playwright, `~/.cache/ms-playwright`) gegen das **gebaute**
Stylesheet aus `dist/assets/*.css`, Viewports 320 / 375 / 768 / 1024 px.
Klassenlisten werden als **Ergebnis von `cn()`** (tailwind-merge) gemessen,
nicht als Quell-Konkatenation. Harness liegt im Scratch, ausserhalb des Repos,
und wird nicht committet.

Fuer die Variantenwahl (Fund 2) werden die Kandidaten als CSS-Property
gemessen, weil die Klassen vor der Aenderung nicht im JIT-Build stehen; die
Klasse-zu-Property-Abbildung wird aus dem gebauten CSS belegt und die
gewaehlte Variante nach der Aenderung noch einmal als Klasse gegengemessen.

## Weichen — entschieden, mit Begruendung

**Fund 1 — `overflow-x-auto` statt `flex-wrap`.** Eine Tab-Leiste, die in
zwei Zeilen umbricht, verliert ihre `border-b`-Kante als durchgehende Linie
und der 2px-Unterstrich des aktiven Tabs sitzt dann in der oberen Zeile ueber
der Leiste — das ist die Optik, die der Design-Handoff „Detail-Redesign"
gerade herstellt. Horizontales Scrollen ist das etablierte Muster fuer
Tab-Leisten und §4.4 Punkt 1 nimmt „bewusst gescrollte Container" ausdruecklich
vom 320px-Kriterium aus. Risiko, das gemessen wird: `overflow-x: auto` setzt
`overflow-y` rechnerisch auf `auto`, und der Unterstrich liegt mit
`-bottom-px` 1 px **ausserhalb** der Box — das kann vertikal clippen oder eine
zweite Scrollbar erzeugen.

**Fund 3 — Padding-Huelle statt groesserer Box.** Die visuelle 16px-Box bleibt,
die klickbare Flaeche waechst ueber ein absolut positioniertes Pseudoelement am
Control. Pseudoelemente gehoeren fuer Hit-Testing zu ihrem Element, das Layout
der Zeile bleibt unveraendert (`size`/`h-*`/`w-*` werden nicht angefasst, wie
die Karte fordert).

**`Label` wird nicht auf 32 px gehoben.** Ein `<label>` ist kein interaktives
Element im Sinne von §11: es hat keine ARIA-Rolle, ist nicht fokussierbar und
erscheint in keinem Accessibility-Tree als Control — es leitet Klicks an sein
Control weiter. Der Floor gilt dem Control, und das erreicht ihn nach dieser
Aenderung. Das `Label`-Primitive repo-weit auf `min-h-8` zu heben, wuerde jede
Formular-Beschriftung ueber jedem Input um 18 px auseinanderziehen — ein
Layout-Eingriff in dreizehn Domaenen ohne gemessenen Defekt (Weiche 1 aus
#431: kein Eingriff ohne Messung).

## Schritte

1. Plan ablegen (diese Datei).
2. Vorher-Messung aller drei Funde gegen das gebaute CSS.
3. Je Fund: **RED**-Test (Klassen-Vertrag bzw. Verhalten, kein Snapshot) →
   **GREEN** minimale Aenderung am Primitive → Nachher-Messung.
   Drei getrennte Commits, je mit eigener Messung.
4. Changelog-Fragment unter `changelog.d/` (`*.fixed.md`) — **nicht**
   `CHANGELOG.md`.
5. DoD vollstaendig: `npm run lint`, `npx tsc -b`, `npm run test:coverage`,
   Skip-Budget-Gate, `npm run build`, `npm run license:check`,
   `npm run i18n:check`, `uv run python scripts/check_code_refs.py .`,
   `changelog_fragments.py check` + `guard --base origin/main`.
6. Push, PR oeffnen, `all-green` gegen den exakten Head-SHA. **Kein Merge.**

## Grenzen

- Nur die drei genannten Primitives plus deren Tests plus das Fragment.
- Keine Aenderung unter `features/*`. Bricht ein Test in einer fremden
  Domaene: nicht anpassen, melden.
- Keine Struktur-, Prop- oder Slot-Aenderung an den Primitives.
- Kein Merge, kein Push auf main.

## Verifikations-Log

_(wird waehrend der Umsetzung gefuellt)_
