# 572 — W3 WorkArea: Responsive-Audit von `features/workarea` (14 Dateien)

Stand: 2026-09-23 · Branch `who2be/t_8ce80cb9-572-w3-workarea-responsive-audit-von-fea`
Basis: `origin/main` @ `9a05a4e8` · Issue: #572 · Epic: #431 (W3)

## Auftrag

Die vierzehn produktiven `.tsx` unter `apps/web/src/features/workarea/` gegen die
sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4 bei
320 / 375 / 768 / 1024 px prüfen; gefundene Defekte beheben, nicht gefundene
begründet als „kein Defekt" abhaken. Keine Änderung an geteilten Primitives,
`features/settings` (inkl. `SettingsNav`) unter keinen Umständen.

## Hinweis zur Zahl 40 px (PM-Kommentar an der Karte, 2026-09-23)

Die 40 px in diesem Paket kommen aus **AK 3 dieses Issues**, nicht aus der Norm.
`design-language.md` §11 ist die einzige Quelle des Floors und setzt ihn auf
**≥ 32 px**; 40 px ist dort die Präferenz `size="default"`, `size="sm"` (36 px)
bleibt ausdrücklich zulässig. Die gemessenen 36 px der Nav-Einträge und
Zeilen-Aktionen sind nach der Norm also **zulässig** — dieses Paket hebt sie
unterhalb `md` an, weil **sein Akzeptanzkriterium** es verlangt. Keine Stelle in
Code, Test, Kommentar oder Changelog-Fragment schreibt die 40 px der Norm zu.

## Methode — real gemessen, nicht geschätzt

jsdom hat kein Layout, und AK 1–5 sind Layout-Aussagen. Deshalb eine
**Wegwerf-Messharness** (statisches HTML mit der echten Elternkette
`Container > Card > CardContent > …` bzw. `Container > Table-Wrapper > …` und den
wörtlichen Klassenlisten der vierzehn Dateien) gegen das **gebaute** Stylesheet
`dist/assets/index-BF0blzzS.css` aus dem eigenen `npm run build`, gefahren in
Chromium (Playwright) bei allen vier Viewports.

Erfassungskriterium ist **`child.right > parent.contentRight`** je Element
(Überlauf gegen die Eltern-Innenkante), nicht nur gegen den Viewport — die in
PR #599 Runde 2 gelernte Lehre. Inhalt der drei bewusst gescrollten
`Table`-Wrapper ist nach §4.4 Punkt 1 ausgenommen; der Wrapper selbst wird
weiter gemessen. Zusätzlich je Element `scrollWidth > clientWidth` — das fängt
**abgeschnittenen** Text (§4.4 Punkt 5), der keinen Body-Scroll erzeugt.

Fixtures bewusst pessimistisch und domänentypisch: ein snake_case-Tabellenname
(`quartalsumsatz_nach_produktkategorie_2026`, 41 Zeichen ohne Trennstelle), eine
`sha256:`-Prüfsumme (71 Zeichen), eine 84-Zeichen-Quell-URL, ein
Artefakt-Anker `<uuid>#<block>`.

Harness und Skript liegen außerhalb des Repos (Scratch) und werden nicht
committet.

## Ist-Zustand bestätigt (auf `9a05a4e8`)

```bash
find apps/web/src/features/workarea -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 14
find apps/web/src/features/workarea -name '*.tsx' ! -name '*.test.tsx' | wc -l  # 15 (Zählfalle)
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/workarea | grep -v '\.test\.tsx'                   # (leer)
```

Vierzehn Dateien, **null** mit Breakpoint-Prefix, kein Mehrspalten-Grid. §4.4
Punkt 2 ist in der Domäne gegenstandslos (AK 6 ohne Eingriff erfüllt). Die
Zählfalle aus dem Issue trifft zu: `test-utils.tsx` wird vom naiven Filter
durchgelassen.

## Gemessener Body-Überlauf (AK 1)

| Viewport | `documentElement.scrollWidth` / `clientWidth` | Überläufer gegen Eltern-Innenkante |
|---|---|---|
| 320 | 599 / 320 ✗ | 5 |
| 375 | 599 / 375 ✗ | 2 |
| 768 | 768 / 768 ✓ | 0 |
| 1024 | 1024 / 1024 ✓ | 0 |

Von den fünf Überläufern bei 320 px liegen **drei in Dateien dieser Domäne** und
werden behoben; **zwei stammen aus dem geteilten `DetailHeader`** und sind als
Primitive-Fund gemeldet, nicht repariert (siehe unten).

## Befund je Datei — alle vierzehn abgehakt (AK 7)

| Datei | §4.4-Punkt | Befund |
|---|---|---|
| `components/WorkAreaNav.tsx` | 4 | **Defekt.** Die drei Einträge messen gerendert **36 px** hoch (`px-3 py-2` bei `text-sm`: 20 px Zeilenhöhe + 2×8 px Padding) — die Rechnung des Issues stimmt auf den Pixel. AK 3 verlangt unterhalb `md` 40 px. Der Umbruch selbst ist in Ordnung: bei 320 px legt `flex-wrap` die Einträge auf drei Zeilen, kein Überlauf. |
| `components/WorkAreaLayout.tsx` | 1–6 | **Kein Defekt.** 20 Zeilen, `Container className="pb-0"` + `<Outlet />`. Kein Grid, keine feste Breite, kein interaktives Element. Das vermutete zweispaltige Layout existiert nicht — bestätigt. |
| `pages/WorkAreaSearchPage.tsx` | 3, 5 | **Defekt, zwei Stellen.** (a) `:52` `min-w-64` misst bei 320 px **256 px in einem 238 px breiten `CardContent`** — gemessene **+18 px** Überlauf, exakt der im Issue vermutete harte Breiten-Befund. (b) Der Treffer-Snippet `:119` schneidet einen trennstellenfreien Beleg-Token ab (`scrollWidth` 297 px in 238 px sichtbar). Der Anker-`MetaPill` `:121` ist **erfüllt** (bricht an den Bindestrichen der UUID, kein Überlauf). |
| `pages/AreasPage.tsx` | 5 | **Defekt.** Die Besitzer-`MetaPill` `:69` läuft bei 320 px **+49 px** über die Innenkante der Meta-Zeile: ein langer Agentenname hat in einer `inline-flex`-Pille keine Trennstelle. Der Karten-Titel und der `PageHeader`-CTA (40 px) sind erfüllt. |
| `components/ArtifactList.tsx` | 5 | **Defekt.** Die Quell-`MetaPill` `:67` läuft bei 320 px **+344 px** und bei 375 px **+289 px** über — der schwerste Überläufer der Domäne. Eine Quell-URL ist der Regelfall, nicht der Ausreißer (`source_url` aus dem Ingest). Titel und Datums-Pille sind erfüllt. |
| `pages/ArtifactDetailPage.tsx` | 4, 5 | **Defekt, drei Stellen.** (a) Die Quell-`MetaPill` `:214` schneidet die URL ab (`scrollWidth` 510 px in 288 px). (b) Der Rohtext-`<pre>` `:237` bricht an Leerzeichen korrekt um — **wie das Issue sagt** —, ein trennstellenfreies Token läuft aber über (`scrollWidth` 207 px in 170 px). Das ist eine Ergänzung zum Befund des Issues, kein Widerruf: `min-w-0` + `whitespace-pre-wrap` bleiben. (c) Der Anker-Kopieren-Button `:241` misst **40 × 36 px** — unter der AK-3-Schwelle. Die Kopf-Aktionen (Export/Löschen) messen 40 px und sind erfüllt. |
| `pages/KbNodeDetailPage.tsx` | 5 | **Defekt, drei Stellen gleicher Ursache.** Node-Inhalt `:91`, Inhalts-Referenz `:125` und Nachbar-Link `:169` schneiden trennstellenfreie Bezeichner ab (je `scrollWidth` > `clientWidth` bei 320 **und** 375 px). Genau die Bezeichner, die AK 5 nennt. `:122` `source_ref` trägt bereits `break-all` und ist **erfüllt** — das Muster existiert in der Datei, es fehlt nur an drei Geschwistern. `co_n`-Pille und Tier-Badges: erfüllt. |
| `pages/KbSearchPage.tsx` | 5 | **Defekt, eine Stelle.** Der Treffer-Link `:83` schneidet ab (`scrollWidth` 297 px in 238 px). Suchfeld (40 px, volle Breite) und Badge-Reihe: erfüllt. |
| `components/AreaGrants.tsx` | 3, 4 | **Defekt, zwei Stellen.** (a) Das Rollen-`Select` `:116` misst bei 320 px **33 px Breite** — die Tabellenspalte schrumpft es unter jede Bedienbarkeit. **Identischer Befund wie #568/`MembersPage` (dort 32 px).** (b) Der Entfernen-Button `:133` misst **36 px** hoch (`size="sm"`), unter der AK-3-Schwelle. Der Tabellen-Wrapper scrollt in sich (Weiche 1) — zulässig. Zur Weiche 4 siehe „Bewusst nicht geändert". |
| `components/TableList.tsx` | 1 | **Kein Defekt.** Die Tabelle scrollt in ihrem Primitive-Wrapper (gemessen 498 px Inhalt in 288 px Wrapper bei 320 px) — §4.4 Punkt 1 und Weiche 1. Der Tabellenname bleibt in der Zelle, die Zelle im Wrapper. Kein Body-Scroll. |
| `pages/TableDetailPage.tsx` | 1 | **Kein Defekt in der Datei.** Die zwei Tabellen scrollen in ihren Wrappern (Nicht-Befund 1 bestätigt, gemessen 571 px in 238 px), `whitespace-nowrap` `:241` bleibt (Nicht-Befund 2). Kopfbereich: Export-Button 40 px, die beiden Schema-`MetaPill`s ohne Überlauf. Der **Titel** läuft über — der sitzt aber im geteilten `DetailHeader`, siehe Primitive-Funde. |
| `pages/AreaDetailPage.tsx` | 1–6 | **Kein Defekt in der Datei.** `TabsList` misst 288 px bei 320 px Viewport, die drei Trigger je 44 px hoch (erfüllt). Keine feste Breite, kein Grid. Der Titel-Überlauf (+4 px) stammt aus dem `DetailHeader`, siehe unten. |
| `components/NewWorkAreaDialog.tsx` | 1, 3, 4 | **Kein Defekt.** `DialogContent` erbt den W2-Default und misst gemessen **288 px bei 320 px Viewport** (kein Überlauf), die beiden Eingabefelder 238 × 40 px über die volle Breite, Trigger und Absenden je 40 px. Bestätigt den Befund des Issues. |
| `components/KbBadges.tsx` | 5 | **Kein Defekt.** Tier- und Status-Badge messen 92 bzw. 94 px und liegen in einer `flex-wrap`-Reihe von 288 px — zwei Badges passen nebeneinander, drei brächen um. Kein Überlauf auf keinem Viewport. |

## Fix — vierzehn Stellen, acht Dateien

Weiche 1 aus #431 gilt: kein Breakpoint-Prefix ohne gemessenen Defekt. Elf der
vierzehn Stellen kommen ohne Prefix aus; die drei mit `md:`/`sm:` stehen dort,
wo die Mobile-Lösung den Desktop sonst verschlechtern würde.

1. **`WorkAreaNav.tsx`** — `min-h-10 … md:min-h-0` an der Eintragszeile.
   **Wörtlich die Klassenfolge aus PR #604 (`SettingsNav`)**, wie die Karte es
   verlangt: das Schwesterpaket hat zuerst gemessen und entschieden, hier wird
   dieselbe Lösung übernommen statt einer zweiten Variante. `SettingsNav` selbst
   bleibt unangetastet. Gemessen 36 px → 40 px unterhalb `md`.
2. **`WorkAreaSearchPage.tsx:52`** — `min-w-0 sm:min-w-64`. **Wörtlich
   Vorentscheidung 2.** Die Mindestbreite dient dem Desktop-Raster; unterhalb
   `sm` fällt sie weg.
3. **`WorkAreaSearchPage.tsx:119`** — `break-words` am Snippet.
4. **`AreasPage.tsx:69`** — `max-w-full break-all` an der Besitzer-`MetaPill`
   (Muster `ResourcesPage.tsx:134` aus #564).
5. **`ArtifactList.tsx:67`** — `max-w-full break-all` an der Quell-`MetaPill`.
6. **`ArtifactDetailPage.tsx:214`** — `max-w-full break-all` an der
   Quell-`MetaPill`.
7. **`ArtifactDetailPage.tsx:237`** — `break-words` am Rohtext-`<pre>`
   (additiv zu `min-w-0 whitespace-pre-wrap`).
8. **`ArtifactDetailPage.tsx:241`** — `min-h-10 md:min-h-0` am Anker-Button.
9. **`KbSearchPage.tsx:83`** — `break-words` am Treffer-Link.
10. **`KbNodeDetailPage.tsx:91`** — `break-words` am Node-Inhalt.
11. **`KbNodeDetailPage.tsx:125`** — `break-all` an der Inhalts-Referenz
    (`sha256:` hat keine Trennstelle — dieselbe Wahl wie `:122` daneben).
12. **`KbNodeDetailPage.tsx:169`** — `break-words` am Nachbar-Link.
13. **`AreaGrants.tsx:116`** — `min-w-32` am Rollen-`Select`. **Wörtlich die
    Lösung aus PR #604/`MembersPage`**: die Rolle bleibt in ihrer Zelle, die
    Zelle bekommt nur eine Untergrenze. Das `Select`-Primitive bleibt unberührt.
14. **`AreaGrants.tsx:133`** — `min-h-10 md:min-h-0` am Entfernen-Button.

`break-words` statt `break-all`, wo normaler Fließtext steht: es bricht **nur**,
wenn ein einzelnes Wort allein nicht passt, und zerhackt gewöhnliche Sätze
nicht. `break-all` nur dort, wo der Inhalt strukturell trennstellenfrei ist
(URL, `sha256:`, Agentenname in einer Pille).

## Nachher gemessen (gegen `dist/assets/index-D8YMVQuv.css` aus dem Fix-Build)

| Viewport | vorher `scrollWidth`/`clientWidth` | nachher | Überläufer vorher → nachher |
|---|---|---|---|
| 320 | 599 / 320 | **574 / 320** | 5 → **2** (beide `DetailHeader`) |
| 375 | 599 / 375 | **574 / 375** | 2 → **1** (`DetailHeader`) |
| 768 | 768 / 768 | 768 / 768 | 0 → 0 |
| 1024 | 1024 / 1024 | 1024 / 1024 | 0 → 0 |

Alle Überläufer **in Dateien dieses Pakets sind weg**. Abgeschnittener Text
(`scrollWidth > clientWidth`) trat vorher an neun markierten Stellen auf und
tritt **nachher an keiner** mehr auf — außer an den drei Tabellen-Wrappern, wo
er nach §4.4 Punkt 1 hingehört.

Einzelwerte vorher → nachher (320 px, sofern nicht anders vermerkt):

| Stelle | vorher | nachher |
|---|---|---|
| `WorkAreaNav` Eintrag (Höhe) | 36 px | **40 px**, ab `md` unverändert 36 px |
| `AreaGrants` Entfernen-Button (Höhe) | 36 px | **40 px**, ab `md` unverändert 36 px |
| `ArtifactDetailPage` Anker-Button (Höhe) | 36 px | **40 px**, ab `md` unverändert 36 px |
| `AreaGrants` Rollen-`Select` (Breite) | 33 px | **128 px**, ab `md` 139 px statt 101 px |
| `WorkAreaSearchPage` Suchfeld-Label | 256 px, +18 px Überlauf | **97 px**, kein Überlauf; ab `sm` unverändert 529/785 px |
| `AreasPage` Besitzer-Pille | 215 px, +49 px Überlauf | **166 px**, kein Überlauf; ab 768 px unverändert 347 px |
| `ArtifactList` Quell-Pille | 510 px, +344 px Überlauf | **166 px**, kein Überlauf; ab 768 px unverändert 552 px |
| `ArtifactDetailPage` Quell-Pille | 288 px, Inhalt 510 px abgeschnitten | **288 px, nichts abgeschnitten** |
| `ArtifactDetailPage` Rohtext-`<pre>` | 170 px, Inhalt 207 px abgeschnitten | **170 px, nichts abgeschnitten** |
| `KbSearchPage` Treffer-Link | abgeschnitten | **umbricht** (80 px statt 60 px hoch) |
| `KbNodeDetailPage` Inhalt / Referenz / Nachbar | alle drei abgeschnitten | **alle drei umbrechen** |
| `WorkAreaSearchPage` Snippet | abgeschnitten | **umbricht** |

**Keine Desktop-Regression:** bei 768 und 1024 px sind sämtliche Maße
unverändert, bis auf die zwei gewollten Verbesserungen (`Select` breiter, weil
die Zelle mehr Platz hat) — Vorher-Nachher gegengemessen.

## Verbleibender Body-Überlauf — außerhalb dieses Pakets

AK 1 ist **in allen vierzehn Dateien der Domäne erfüllt**. Der Rest-Überlauf bei
320/375 px stammt nachweislich aus `components/data/DetailHeader.tsx` (Fund 1
unten) und träfe jede Detailseite des Produkts gleichermaßen. Er wird nach der
Karten-Grenze gemeldet statt repariert — genau wie das Schwesterpaket #568 mit
seinen zwei Primitive-Funden verfahren ist.

## Bewusst nicht geändert

- **Tabellen als Karten stapeln** — Weiche 1, verworfen. Die drei Tabellen
  scrollen in ihren Primitive-Wrappern, gemessen kein Body-Scroll daraus.
- **`TableDetailPage.tsx:241` `whitespace-nowrap`** — Nicht-Befund 2 des Issues.
- **Der Tabellen-Wrapper** — Nicht-Befund 1, sitzt im Primitive.
- **Das Berechtigungs-Dropdown aus der Zelle holen** — Weiche 4 verlangt die
  Prüfung, nicht die Bewegung. Gemessen: das Control ist ein **natives
  `<select>`**, kein DOM-Overlay im scrollenden Container — es öffnet ein
  Betriebssystem-Popup außerhalb des Dokumentflusses und kann die Scroll-Geste
  des Wrappers strukturell nicht abfangen. Das im Issue befürchtete Problem
  existiert hier nicht; gehandelt wird nur an der gemessenen Breite (Fix 13).
  **Dieses Ergebnis gehört nach Weiche 4 ins Schwester-Issue #568** und wird im
  Handoff gemeldet.
- **`features/settings` / `SettingsNav`** — eigenes Paket, unter keinen
  Umständen.

## Primitive-Funde für den Handoff — nicht repariert

Beide liegen in `components/data/DetailHeader.tsx`, das **zwölf
Geschwisterpakete** anfassen. Nach der Karten-Grenze wird gemeldet statt
repariert.

1. **Das `<h1>` trägt kein `break-words`.** Gemessen bei 320 px: der
   Tabellenname `quartalsumsatz_nach_produktkategorie_2026` misst in `text-2xl`
   **502 px** und läuft **+270 px** über die Innenkante; ein Bereichsname mit
   Bindestrichen +4 px. Der umgebende `div` trägt bereits `min-w-0` — es fehlt
   allein die Umbruch-Erlaubnis am `h1`. **Das ist der verbleibende
   Body-Überlauf bei 320/375 px** (AK 1): er entsteht nicht in einer der
   vierzehn Dateien, sondern im geteilten Header, und träfe jede Detailseite des
   Produkts mit einem trennstellenfreien Titel.
2. **Der Zurück-Link misst 36 px** (`size="sm"`, `h-9`). Nach §11 zulässig
   (≥ 32 px), nach AK 3 dieses Pakets unterhalb `md` zu niedrig. Betrifft jede
   Detailseite.

Beide sind gemessen, nicht vermutet. Keiner ist ein Blocker für die vierzehn
Dateien dieses Pakets.

## Test-first

Neue Fälle als **Klassen-Vertrag** neben der geänderten Datei (Muster W2/#513
und PR #604), mit `features/workarea/test-utils.tsx` als Helfer (Weiche 5).
jsdom hat kein Layout — die Tests prüfen, dass die gemessene Lösung im Markup
steht; die Layout-Aussage selbst ist oben gerendert belegt. Das steht in jedem
Testkommentar ausdrücklich so und wird nicht als Layout-Test verkauft.

Jeder Fall war vor der Änderung rot (Protokoll im Handoff).

## Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b
npm run test:coverage -- --reporter=default --reporter=junit --outputFile.junit=junit-web.xml
python3 ../../scripts/ci/assert_skips_within_budget.py junit-web.xml
npm run test:a11y
npm run build
npm run license:check
```

Dazu `uv run python scripts/changelog_fragments.py check` und
`python3 scripts/check_code_refs.py` im Repo-Root.
