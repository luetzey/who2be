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

Alle Zahlen aus Chromium gegen das jeweils gebaute Stylesheet, Hitflaechen per
`elementFromPoint`-Raster (0,5px-Schritte). Der Harness lag im Scratch und ist
bewusst nicht Teil des Repos.

### Fund 1 — TabsList

Vorher, 320px, Klassenlisten als `cn()`-Ergebnis:

| Aufrufstelle | Trigger-Summe | letzter Tab | Body-Ueberlauf |
|---|---|---|---|
| AgentEditorForm DE | 461px | unerreichbar, +173px | 477/320 |
| AgentEditorForm EN | 455px | unerreichbar | 471/320 |
| ResourceDetailPage | 540px | unerreichbar (auch bei 375px) | 556/320 |
| PersonaDetailPage | 498px | unerreichbar (auch bei 375px) | 514/320 |

Damit ist der Fund breiter als gemeldet: zwei Detailseiten sind auch auf
375px-Geraeten betroffen, nicht nur auf 320px.

Nachher: alle vier erreichbar (Scrollweg 167–252px), Body-Ueberlauf durchgehend
0, vertikaler Scroll 0. 768/1024px unveraendert ohne Scroll.

Das im Plan vermutete Risiko trat ein und wurde behoben: `overflow-x-auto`
allein ergab `scrollHeight` 45 gegen `clientHeight` 44 — der Container liess
sich um 1px vertikal scrollen, weil der Unterstrich mit `-bottom-px` aus der
Box ragt. `pb-px` legt den Pixel als Polsterung nach innen; Optik unveraendert,
vertikaler Scroll 0. Die Alternative `bottom-0` haette den Unterstrich auf die
graue Trennlinie gesetzt und deren Kante verschoben.

### Fund 2 — EntityCard

Die im Plan angenommene Korrektur (`break-words`, analog zu PR #606) ist an
dieser Stelle **wirkungslos**: der Ueberlauf blieb bei exakt +116,5px. Ursache
ist nicht die Umbruch-Regel, sondern `min-width: auto` am Flex-Item —
`overflow-wrap: break-word` senkt die min-content-Breite eines Elements nicht,
`overflow-wrap: anywhere` (Tailwind `wrap-anywhere`) schon.

Gegen `break-all` entschieden, gemessen an einem gewoehnlichen Titel:
`break-all` zerlegte „Kundenservice Eskalation Stufe Zwei" in 165,8/82,5px
(mitten im Wort), `wrap-anywhere` bricht dieselbe Zeile an den Leerzeichen bei
100,4/143,9px. Bei trennstellenfreien Bezeichnern sind beide identisch — der
Unterschied trifft also nur die gewoehnlichen Titel, und die sind der Regelfall.

Zweiter, im Plan nicht vorhergesehener Befund: traegt die Karte Zeilen-Aktionen
(AgentsPage), kollabiert die `min-w-0 flex-1`-Textspalte bei 320px auf 0px.
Die Umbruch-Erlaubnis allein haette die Karte dort von 762 auf 1522px
aufgeblaeht. `min-w-32` plus `flex-wrap` am Karten-Body loesen das; beide sind
noetig (`flex-wrap` allein liess 375px bei 44,7px Spaltenbreite stehen,
`min-w-32` allein schob die Aktionen 105px ueber den Rand).

| Lage, 320px | vorher | nachher |
|---|---|---|
| mit Aktionen, snake_case | Spalte 0px, +282,5px, Karte 762px | Spalte 198px, 0, Karte 208px |
| mit Aktionen, normaler Titel | Spalte 0px, +100,4px, Karte 832px | Spalte 198px, 0, Karte 208px |
| ohne Aktionen, snake_case | +116,5px, Body 371/320 | 0, Body 320/320 |

768/1024px: Karte durchgehend 84px, Titel einzeilig — unveraendert.

### Fund 3 — Hit-Targets

Die Plan-Annahme „Pseudoelement am Control" gilt nur fuer das Radio. Bei der
Checkbox scheiterte sie gemessen: ein `<input>` ist ein replaced element und
rendert keine Pseudoelemente (Hitbox blieb 16,5px). Auch `p-2` am Huell-Span
half nicht — es vergroessert die Box auf 32px und damit die Zeilenhoehe, ohne
die Hitflaeche anzufassen. Loesung dort: Optik an den Span, Hitbox an den
Input. Die Zustaende mussten dabei von `peer-*` auf `has-[…]` wechseln, weil
`peer-*` ein Geschwister adressiert, der Span aber Elternknoten ist.

| Element | visuelle Box | Hit vorher | Hit nachher |
|---|---|---|---|
| Checkbox @ AgentEditorForm | 16x16 unveraendert | 16,5x16,5 | 32,5x32,5 |
| Radio @ CatalogScopePicker | 16x16 unveraendert | 16,0x16,5 | 32,5x32,5 |
| Radio @ AgentEditorForm | 16x16 unveraendert | 16,0x16,5 | 32,5x32,5 |

Zustands-Gegenprobe Checkbox gegen die Ausgangswerte: Fuellung oklch(0.205 0 0),
Rahmen oklch(0.205 0 0), Disabled-Opazitaet 0.5, Fokus-Ring als identischer
`box-shadow` — alle vier Zustaende treffen exakt. Zeilenhoehe 16px und
Zeilenabstand 8px unveraendert. Ein Klick 12px neben der sichtbaren Box
schaltet jetzt um (vorher kein Treffer).

Grenzfall ohne Handlungsbedarf: in einer RadioGroup mit `gap-2` und ohne
Karten-Padding beschneiden sich benachbarte Hitflaechen gegenseitig auf
32,5x28px; ab `gap-3` sind es 32px. Alle fuenf realen Aufrufstellen (vier
Picker + AgentEditorForm) verwenden `p-3`-Karten und messen 32,5x32,5px. Ein
Eingriff ins Gruppen-Layout waere hier ein Eingriff ohne gemessenen Defekt.

### Tests

RED vor jeder Aenderung nachgewiesen (Fund 1: 3 von 4, Fund 2: 2 von 3,
Fund 3: 5 von 8 — die jeweils gruenen Faelle sind Regressionssicherungen).
Volle Suite nach allen drei Commits: **207 Dateien, 1314 Tests, alle gruen.**

Umgebungsnotiz: Node 22.23.2 braucht `NODE_OPTIONS=--localstorage-file=…`,
sonst scheitern 157 Tests in ThemeProvider/SessionProvider an
`window.localStorage`. Das ist kein Repo-Defekt — gegen den unveraenderten
Basis-Commit reproduziert (per `git stash` gegengeprueft) und in CI nicht
vorhanden.

