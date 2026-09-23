# #573 W3 playbooks — Hälfte B: Responsive-Audit der elf kleinen Dateien

Karte: `t_00e42785` · Issue: [#573](https://github.com/luetzey/who2be/issues/573)
Branch: `who2be/t_00e42785-573-w3-playbooks-haelfte-b-responsive-au`
Basis: `origin/main` @ `c558860d`

Schwesterkarte (Hälfte A, die fünf großen Dateien) läuft als PR #612 —
die dort behandelten Dateien werden hier **nicht** angefasst.

## Norm-Lage (wichtig, dreimal blockiert)

`docs/frontend/design-language.md` §11 ist die **einzige** Quelle des
Hit-Target-Floors und setzt: **≥ 32 px verbindlich**, 40 px (`size="default"`)
Regelfall, 44 px mobile Präferenz, **`size="sm"` (36 px) ausdrücklich zulässig,
wo Dichte gewollt ist (Zeilen-Aktionen, Zurück-Links)**.

Die 40-px-Zahl in diesem PR stammt daher **nicht** aus §11, sondern aus
**Akzeptanzkriterium 5 des Issues #573** („Hit-Targets unterhalb `md` ≥ 40 px").
Wo ich unterhalb `md` auf 40 px hebe, ist das die Erfüllung dieses AK — der
Vorher-Wert lag in allen Fällen bereits über dem Norm-Floor. Formulierungen
der Art „§11 verlangt 40 px" kommen in Code, Tests, Kommentaren und
Changelog-Fragment nicht vor.

## Messmethode

Gemessen wurde **am gebauten Stylesheet in Chromium**, nicht am Klassennamen:

- `npm run build` → `apps/web/dist/assets/index-kTcR54w2.css` (280 734 Bytes)
- Harness (Scratch, nicht committet): Playwright-Chromium lädt statische
  HTML-Nachbauten der Komponenten mit **genau diesem** Stylesheet inline und
  liest `getBoundingClientRect()` sowie `scrollWidth - clientWidth` aus, bei
  **320 / 375 / 768 / 1024 px**.
- Die Nachbauten tragen die Klassen der Aufrufstelle **bereits aufgelöst**
  (`cn()`/`tailwind-merge` läuft im statischen HTML nicht), inklusive der
  Wrapper-Kette `Container` (`px-4`, Innenraum 288 px bei 320 px Viewport).
- Realistischer Inhalt: lange deutsche Playbook-Namen, Block-Anker der Form
  `<uuid>#<block_id>`, zwei Tags, drei Branch-Knoten.

`bodyScroll` = `documentElement.scrollWidth - clientWidth`; `OVF+n` = das
Element selbst läuft um n px über seine eigene Box.

## Befunde je Datei (alle elf)

### 1. `PlaybookDetailTabs.tsx` — **DEFEKT, behoben**

320 px: **`bodyScroll = 84`**, `tablist` `OVF+100`, die drei Tabs enden bei
x = 403,8 statt spätestens 304. 375 px: `bodyScroll = 29`. Ab 768 px sauber.
Ursache: `flex gap-1 border-b` (`:50`) ohne `flex-wrap` — drei Tabs mit
DE-Labels messen zusammen 379,8 px + 8 px Gaps gegen 288 px Innenraum.

Fix: `flex-wrap` an der `tablist`-Zeile. AK 6 nennt Umbruch als eine der
beiden zulässigen Auflösungen; §4.4 Checklistenpunkt 5 nennt Umbruch als
Mittel der Wahl. Hit-Target der Tabs: 44 px hoch (gemessen) — unverändert.

### 2. `ComposedByList.tsx` — **DEFEKT, behoben**

320 px mit einem Playbook-Namen **ohne Trennstelle**
(`Kundenonboardinggesamtprozessvertriebsuebergabecomposite`):
**`bodyScroll = 94`**, `li` `OVF+110`, der Link misst 397,7 px gegen 288 px
Spalte. Mit Bindestrichen im Namen (225,7 px) unauffällig — der Defekt hängt
am Inhalt, nicht am Breakpoint, und Composite-Namen sind im Deutschen
regelmäßig zusammengeschrieben.

Fix: `break-words` am Listeneintrag. Kein `truncate`, weil der Backlink den
vollen Namen tragen soll (einzige Fundstelle des Elternnamens auf der Seite).

### 3. `PlaybookRow.tsx` — **DEFEKT, behoben**

320 px: die Textspalte `:76` (`min-w-0 flex-1`) wird auf **0 px** gerechnet
(`mitte=0x386`, `OVF+102`), während die Meta-Spalte `:200` als `shrink-0` mit
zwei Tags **193,3 px** belegt und bis x = 302,3 reicht. Name, Beschreibung,
Composite-Button und Kind-Links überlappen sie (`name` endet bei 195,4,
`child-name` `OVF+282`). Kein Body-Scroll — aber die Zeile ist unlesbar,
und genau diesen Fall macht **Weiche 3 des Issues** zur Bedingung:
„nur bei gemessener Unlesbarkeit lösen, dann durch **Umbruch der Zeile
unterhalb `md`**, nicht durch Streichen von `shrink-0`".

Fix entsprechend: `flex-wrap md:flex-nowrap` an der Karte `:68`, die
Textspalte bekommt unterhalb `md` eine eigene Zeile (`basis-full md:basis-0`),
die Meta-Spalte wird unterhalb `md` zur vollbreiten liegenden Leiste
(`w-full flex-row items-center justify-between md:w-auto md:flex-col`).
`shrink-0` bleibt stehen — die Badges bleiben geschützt.

Hit-Targets in dieser Datei (AK 5): Composite-Aufklapp-Button `:141`/`:144`
maß **32 px** (`h-auto px-3 py-2 text-xs`), Kind-Link `:172` **38 px**. Beide
über dem Norm-Floor, beide unter der vom AK geforderten Zahl — unterhalb `md`
auf 40 px gehoben (`min-h-10 md:min-h-0`), die Verdichtung ab `md` bleibt.

### 4. `LinkedBlocksList.tsx` — **DEFEKT, behoben**

320 px: `li` `:78` ohne `flex-wrap`, die Aktionsspalte `:84` ist `shrink-0`
und belegt 144,1 px. Der Resource-Name bekommt nur **105,9 px**
(`OVF+78`) und läuft aus seiner Box. Block-Anker sind umbruchfeindlich, die
Subline kürzt per `truncate` kontrolliert (gewollt, kein Defekt).

Fix: `flex-wrap` am Listeneintrag; die Textspalte trägt zusätzlich
`basis-full md:basis-0`, damit sie unterhalb `md` die volle Breite bekommt
statt mit der Aktionsleiste zu konkurrieren.

Hit-Target (AK 5): Entfernen-Button `:90` `size="sm"` maß **36 px** — über
dem Norm-Floor und dort als Zeilen-Aktion ausdrücklich zulässig, aber unter
der vom AK geforderten Zahl. Unterhalb `md` auf 40 px gehoben
(`h-10 md:h-9`).

### 5. `PlaybookBodyEditor.tsx` — geprüft, **Insel-Befund notiert, nicht repariert**

`bn-container` `:123` misst bei 320 px 288 px, `bodyScroll = 0`; der Rahmen
selbst ist korrekt. Das Innenleben (Toolbar, Slash-Menü, Drag-Handles,
Formatierungs-Popover) erzeugt BlockNote **eigenes DOM außerhalb der
Tailwind-Klassenhoheit dieser Datei** und ist mit der Klassen-Harness nicht
erreichbar.

Nach dem Pflichtabschnitt des Issues bleibt die Insel hier **ungerührt**: kein
globaler `bn-*`-Override (domänenübergreifend, eigenes Paket), keine
Aufrufer-Klasse gegen Bibliotheks-DOM. Derselbe Editor läuft in
`features/resources` — der Übertrag gehört ins dortige W3-Issue. **Offen und
hier bewusst nicht entschieden**, weil er außerhalb dieser Kartengrenze liegt.

### 6.–11. Geprüft, **kein Defekt** (mit Messwerten)

| Datei | Messung bei 320 px | Warum kein Defekt |
|---|---|---|
| `PlaybooksPage.tsx` | `bodyScroll = 0`; `PageHeader` 288 px, `h1` 115,7 px, Aktionsleiste bricht per `flex-wrap` auf eigene Zeile, Button 158 × **40** px | Die Seite selbst trägt keine feste Breite; der einzige Defekt ihrer Route saß in `PlaybookRow` und ist dort behoben |
| `ReviewBanner.tsx` | `bodyScroll = 0`; Banner 288 px, Branch-Graph mit **drei** Knoten bricht auf drei Zeilen um (68,9 / 174 / 144,9 px), Aktionsleiste 167,8 px eigene Zeile | Beide `flex-wrap` (`:81`, `:85`) greifen; der im Issue offene Punkt „Branch-Graph bei mehreren Knoten" ist damit gemessen erledigt |
| `PlaybooksEmptyStates.tsx` | `bodyScroll = 0`; Hero 288 px, Inhalt 190 px (`p-12`), CTA 190 × **44** px, Typ-Chips brechen auf drei Zeilen; NoResults-Reset 181,3 × **40** px | `max-w-*` ist eine Obergrenze; beide Leerzustände bleiben innerhalb der Spalte, beide Aktionen über dem AK-Wert |
| `PlaybookNewPage.tsx` | `bodyScroll = 0`; Zurück-Button 98,6 × **36** px | 36 px = `size="sm"`, das §11 **für Zurück-Links ausdrücklich zulässt** und das über dem Floor liegt. Der Button steht allein in einer `self-start`-Zeile, nichts kollidiert — kein Anheben ohne Befund |
| `SubPlaybookFlow.tsx` | `bodyScroll = 0`; zwei Glieder brechen auf je eine volle Zeile um (260 / 288 px), Hit-Target **46** px | `min-w-40` (160 px) liegt unter dem 288-px-Innenraum, `flex-wrap` (`:24`) greift — die im Issue vermutete Weiche 2 trifft hier **nicht** zu, es gibt nichts zu binden |
| `PlaybookTypeIcon.tsx` | Kachel 44 × 44 px (`size-11` von der Aufrufstelle), `shrink-0` | Reine dekorative Kachel fester Größe, gibt keinen Platz ab und braucht keinen — unverändert |

### Gemeldet statt repariert

Keine Primitive unter `components/ui/` oder `components/data/` zeigte in diesem
Paket einen Befund: `button.tsx` liefert `size="sm"` = `h-9` (36 px) und
`size="default"` = `h-10` (40 px), `badge.tsx` ist inhaltsgroß. Alle Anhebungen
sitzen an der Aufrufstelle.

## Tests

Je geänderter Datei ein `*.responsive.test.tsx` neben der Datei (Muster W2/#513).
Es sind **jsdom-Klassenverträge**, keine Layout-Assertions — jsdom hat kein
Layout. Das steht im Kopf jeder Testdatei; die Layout-Aussagen sind oben gegen
das gebaute Stylesheet belegt. Jeder Test war vor der Änderung rot
(Gegenprobe im Handoff).

## Changelog

Fragment `changelog.d/i573-playbooks-responsive-b.fixed.md` — **nicht**
`CHANGELOG.md` (Verfahren: CONTRIBUTING.md, `scripts/changelog_fragments.py`).

## Verifikation

Web-DoD aus CONTRIBUTING.md auf Node 22.23.2: `lint`, `tsc -b`,
`test:coverage` + Skip-Budget, `build`, `license:check`; dazu
`check_code_refs.py` und `changelog_fragments.py check`. Ergebnisse im Handoff.
