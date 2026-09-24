# 570 — W3 Agents Hälfte A: Responsive-Audit (4 große Dateien)

Stand: 2026-09-23 · Branch `who2be/t_bf48ee1a-570-w3-agents-haelfte-a-responsive-audit`
Basis: `origin/main` @ `c558860d` · Issue: #570 · Epic: #431 (W3) · Karte: `t_bf48ee1a`

## Auftrag

Vier der zehn produktiven `.tsx` unter `apps/web/src/features/agents/` gegen die
sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4 bei
320 / 375 / 768 / 1024 px prüfen, Defekte beheben, Nicht-Funde begründet
abhaken. Die restlichen sechs Dateien gehören der Schwesterkarte (Hälfte B) und
werden **nicht angefasst** — sonst kollidieren die PRs.

| Datei | Zeilen |
|---|---|
| `components/AgentEditorForm.tsx` | 612 |
| `components/AgentMemorySection.tsx` | 594 |
| `pages/AgentsPage.tsx` | 460 |
| `components/AgentTokensSection.tsx` | 316 |

## Woher die Zahl 40 px kommt — nicht aus der Norm

**AK 4 dieses Issues** verlangt unterhalb `md` 40 px. Die Norm verlangt das
nicht: `design-language.md` §11 ist die einzige Quelle des Floors und setzt ihn
auf **≥ 32 px**; 40 px ist dort die Präferenz `size="default"`, und `size="sm"`
(36 px) ist **ausdrücklich zulässig**. Die gemessenen 32- und 36-px-Stellen
dieses Pakets sind nach der Norm also **konform** — sie werden unterhalb `md`
angehoben, weil **das Akzeptanzkriterium dieses Issues** es verlangt, nicht weil
§11 es fordert. Keine Stelle in Code, Test, Kommentar oder Changelog-Fragment
schreibt die 40 px der Norm zu (Lehre aus #568, #569, #572).

## Methode — real gemessen, nicht am Klassennamen abgelesen

jsdom hat kein Layout, AK 1–5 sind aber Layout-Aussagen. Deshalb eine
**Wegwerf-Messharness**: statisches HTML mit der echten Elternkette
(`Container > Card > CardContent > Stack > ul > li > …`) und den wörtlichen
Klassenlisten der vier Dateien, gefahren in Chromium (Playwright) gegen das
**gebaute** Stylesheet `dist/assets/index-kTcR54w2.css` aus dem eigenen
`npm run build`, bei allen vier Viewports.

Erfassungskriterien je Element:

- `child.right > parent.contentRight` — Überlauf gegen die **Eltern-Innenkante**,
  nicht nur gegen den Viewport (Lehre aus PR #599 Runde 2).
- `scrollWidth > clientWidth` — **abgeschnittener** Text (§4.4 Punkt 5), der
  keinen Body-Scroll erzeugt und deshalb sonst durchrutscht.
- gerenderte Höhe interaktiver Elemente (AK 4).

**Vier Messrunden, weil die ersten zwei Harness-Artefakte produzierten** — beide
wurden isoliert, statt sie als Fund zu verkaufen:

1. Runde 1: ein langer Karten-Titel kollabierte die Meta-Spalte auf 0 px
   Innenbreite und ließ *jede* Pille als „Überläufer" erscheinen.
2. Runde 2/3 (`isolate.html`): Karten mit kurzem Titel, ohne Actions, mit
   einzelnen Action-Kombinationen und Pills allein in einer 238-px-Spalte —
   trennt Primitive-Effekt von eigenständigem Pill-Überlauf.
3. Runde 4 (`merge.html`): alle Klassenlisten als **Ergebnis von
   `cn()`/tailwind-merge** statt als Quell-Konkatenation. Das korrigiert zwei
   Fehlmessungen: `size="sm"` + `className="h-8"` ergibt 32 px (nicht 36), und
   `w-24` am `Select` löscht das `w-full` des Primitives (96 px, nicht 204 px).

Fixtures pessimistisch und domänentypisch: ein snake_case-Agentenname
(`kundenservice_eskalation_stufe_zwei_bot`), ein Template-Bezeichner mit
Version (`systemprompt_kundenservice_eskalation · v14`, 42 Zeichen), ein
Token-Name (`w2b_ci_deploy_kundenservice_eskalation_stufe_zwei`), ISO-Zeitstempel
mit Mikrosekunden, eine 84-Zeichen-Artefakt-URL mit `#block`-Anker — und jedes
mehrsprachige Label in **DE und EN** (AK: „mehrsprachig zu prüfen").

Harness und Skripte liegen im Scratch, außerhalb des Repos, und werden nicht
committet.

## Ist-Zustand bestätigt (auf `c558860d`)

```bash
find apps/web/src/features/agents -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l   # 10
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/agents | grep -v '\.test\.tsx'                    # (leer)
```

Zehn Dateien, **null** mit Breakpoint-Prefix, kein Mehrspalten-Grid. §4.4
Punkt 2 ist in der Domäne gegenstandslos — AK 7 ist ohne Eingriff erfüllt und
bleibt es (das Gate liefert nachher dieselbe leere Ausgabe).

## Gemessener Body-Überlauf (AK 1)

| Viewport | `documentElement.scrollWidth` / `clientWidth` |
|---|---|
| 320 | 477 / 320 ✗ |
| 375 | 477 / 375 ✗ |
| 768 | 768 / 768 ✓ |
| 1024 | 1024 / 1024 ✓ |

Nach Abzug der Harness-Artefakte bleiben **fünf eigenständige Überläufer** in
den vier Dateien plus **ein Primitive-Fund** (`EntityCard`-Titel).

## Befund je Datei — alle vier abgehakt (AK 8)

### `pages/AgentsPage.tsx` (460 Z.) — Defekt, fünf Stellen

Das Issue notiert „**kein Klassen-Befund**". Das stimmt für die Klassen und ist
gerade deshalb der Grund, genauer zu messen: die Defekte sitzen im Inhalt, nicht
in den Klassen.

- **`:363` Template-`MetaPill`** — gemessen **256 px in einer 238 px breiten
  Spalte, +18 px Überlauf**. `systemprompt_kundenservice_eskalation · v14` hat
  keine Trennstelle, die `inline-flex`-Pille bricht nicht. Der einzige
  gemessene Pill-Überlauf der Datei.
- **`:354` Persona-`MetaPill`** — gemessen **genau 238 px**, also bündig an der
  Innenkante ohne Reserve. Ein Zeichen mehr im Personennamen läuft über;
  derselbe Inhaltstyp (technischer Bezeichner) und dieselbe Behandlung wie
  `:363`.
- **`:99` `FilterChip`** — gerendert **32 px** hoch. `size="sm"` (h-9) plus
  `className="h-8"`, und `h-8` gewinnt in `tailwind-merge`. Nach §11 zulässig,
  nach AK 4 zu niedrig. Betrifft alle vier Chips, DE und EN.
- **`:293` Filter-Reset** — gerendert **32 px** (`h-8 px-2`), gleiche Lage.
- **`:437` „Einrichten"** — gerendert **36 px** (`size="sm"`), gleiche Lage.

Erfüllt und **nicht angefasst**: `PageHeader`-CTA 40 px · Suchfeld 40 × 238 px
über die volle Breite · `favorite-toggle` 40 × 40 px (`size="icon"`) ·
Chip-Reihe bricht bei 320 px auf drei Zeilen (`flex-wrap` vorhanden) ·
`pendingMemories`-Pille 220,8 px in 238 px · `playbookCount`-Pille 101,4 px ·
`AgentStatusPill` 86 px.

### `components/AgentMemorySection.tsx` (594 Z.) — Defekt, neun Stellen

- **`:359` / `:395` `<Stack>` in einer `flex-wrap`-Zeile ohne `min-w-0`** —
  gemessen **298,9 px** bzw. **340,9 px** in 254 px: **+45 px** und **+87 px**
  Überlauf, der Text zusätzlich abgeschnitten (341 in 254). Genau der
  Hauptkandidat, den das Issue benennt („`min-w-0` fehlt in neun von zehn
  Dateien"). Isoliert gegengemessen (V6), also nicht Folge eines anderen Fundes.
- **`:251` Kontext-Absatz** — **218 px Inhalt in 204 px sichtbar**, die
  Artefakt-URL wird abgeschnitten. `context` ist ein Freitextfeld aus dem
  Ingest; eine URL darin ist der Regelfall.
- **`:109` / `:502` `ConfirmDeleteButton`-Trigger** — **32 px** in der
  `ghost`-Variante (`h-8`), **36 px** als `outline`. Eine Änderung am Trigger
  deckt alle drei Aufrufstellen (`:369`, `:405`, `:501`).
- **`:163` Ablehnen, `:260` Freigeben, `:346`/`:349` Abbrechen/Speichern,
  `:366` Bearbeiten, `:561` Rejected-Toggle** — je **36 px** (`size="sm"`).

**Der prominenteste Nicht-Fund der Domäne: `:336` `<Select className="w-24">`.**
Das Issue vermutet hier den harten Breiten-Defekt und AK 3 verlangt die
Prüfung. Gemessen ist es **kein Defekt**: `tailwind-merge` löscht das `w-full`
des Primitives, das Feld misst **96 px in einer 204 px breiten Spalte** und
bleibt mit 108 px Reserve innerhalb der Innenkante — bei 40 px Höhe und
einstelligem Inhalt (Stufen 1–10). Die feste Breite dient dem Desktop-Layout
und schadet auf 320 px nicht. Vorentscheidung 2 des Issues bot an, sie zu
`w-20 sm:w-24` abzufedern; die Messung zeigt, dass das eine Verschlechterung
ohne Anlass wäre — Weiche 1 aus #431 (kein Prefix ohne gemessenen Defekt).
**Belegt als unkritisch, unverändert.**

Weitere Nicht-Funde: **`:243` Fakt-`Input`** zeigt `scrollWidth` 503 in 202 —
das ist das native Scrollen eines `<input>` über seinen eigenen Wert, kein
Layout-Überlauf; das Feld selbst misst 204 px und bleibt in der Spalte.
**`:115` / `:167` die beiden `<DialogContent>`** erben den W2-Default und
brauchen keine eigenen Caps (Issue-Befund bestätigt, unverändert). **`:491`**
trägt `flex-wrap` bereits. **`:49` `MemoryPills`** bricht um. **`:492`** ist
201,8 px in 238 px — passt.

### `components/AgentTokensSection.tsx` (316 Z.) — Defekt, sieben Stellen

- **`:229` Inaktiv-Toggle** — **282 px breit in 238 px, +44 px Überlauf.** Das
  Label „1 abgelaufene · 2 widerrufene Tokens" trifft auf das
  `whitespace-nowrap` des Button-Primitives. **Dies ist der Verursacher des
  Body-Scrolls** bei 320 px; zusätzlich 36 px hoch.
- **`:128` `<Stack>` ohne `min-w-0`** — **335,5 px in 254 px, +81 px**, Inhalt
  abgeschnitten (335 in 254). Dieselbe Ursache wie in der Memory-Sektion.
- **`:154` Token-Name** — `w2b_ci_deploy_kundenservice_eskalation_stufe_zwei`
  ohne Trennstelle, läuft mit dem Stack über. Token-Präfixe sind strukturell
  trennstellenfrei — genau der Fall, den AK 2 nennt.
- **`:165` / `:177` / `:186`** Umbenennen/Rotieren/Widerrufen — je **36 px**.
- **`:136` / `:144`** Speichern/Abbrechen im Rename-Zustand — je **36 px**.

**Nicht-Fund, den das Issue als Fund vermutet: `:211` Zählerzeile.** Das Issue
notiert „`flex items-center justify-between` **ohne `flex-wrap`**" als zu
prüfenden Defekt. Gemessen passt die Zeile mit großer Reserve: Label 86,1 px +
Zähler 7,8 px in 238 px (DE), 83,3 px + 31,2 px bei vierstelligem Zähler (EN).
Beide Seiten sind kurze, feste Texte — `flex-wrap` hätte nichts zu tun.
**Belegt als unkritisch, unverändert.** Erfüllt außerdem: `:280` Rollen-`Select`
und `:296` Datumsfeld je 40 × 238 px, Absenden 40 px, `:127` und `:164` tragen
`flex-wrap` bereits.

### `components/AgentEditorForm.tsx` (612 Z.) — kein Defekt in der Datei

Die längste Datei der Domäne, und die einzige der vier ohne eine einzige
Änderung. Alle vom Issue genannten Prüfpunkte sind gemessen erfüllt:

- **`:77` Feld-/Label-Zeile ohne `flex-wrap`** (der Klassen-Befund des Issues):
  die Zeile misst 241,9 px in 241,9 px, das Label 217,9 px. Sie **muss** nicht
  umbrechen, weil das Label als Block-Text in sich umbricht — beim längsten
  DE-Label (67 Zeichen, `feedback_resolve`) auf 42 px Höhe, beim längsten
  EN-Label auf 28 px. Kein Überlauf auf keinem Viewport. `flex-wrap` wäre hier
  wirkungslos: das Flex-Kind ist bereits das umbrechende Element.
- **Validierungsfehler / Hilfetexte** (`:311` Missing-Notice): 241,9 px breit,
  80 px hoch bei drei fehlenden Feldern, `shrink-0` am Icon, Text bricht um.
- **Feldgruppen** (`:455` Preset-Zeilen): 241,9 px, die Beschreibung bricht auf
  80 px um. `:538` Rate-Limit-Label 124,5 px, Feld 241,9 px.
- **Submit-Bereich** (`:166`): `flex justify-end`, Button 40 px — erfüllt.
- **`:190` `TabsList`**: die drei Trigger summieren sich auf 461 px und der
  Container scrollt sie ab (`scrollWidth` 461 in 288 px) — aber der
  **`TabsList`-Container selbst bleibt bei 288 px** und erzeugt keinen
  Body-Scroll. Die Trigger sind 44 px hoch (über AK 4). Das Verhalten sitzt im
  geteilten `Tabs`-Primitive und trifft **sechs weitere Aufrufstellen** in fünf
  Domänen — siehe Primitive-Funde, gemeldet statt repariert.

## Fix — 24 Stellen, drei Dateien

Weiche 1 aus #431 gilt: **kein Breakpoint-Prefix ohne gemessenen Defekt.** Die
Umbruch-Fixes kommen ohne Prefix aus; `md:` steht nur an den Hit-Targets, wo die
Mobile-Lösung die Desktop-Dichte sonst verschlechtern würde.

**Umbruch / Kürzung (9):**

1. `AgentsPage.tsx:363` — `min-w-0 truncate` an der Template-`MetaPill`.
2. `AgentsPage.tsx:354` — `min-w-0 truncate` an der Persona-`MetaPill`.
3. `AgentMemorySection.tsx:359` — `min-w-0` am aktiven `<Stack>`.
4. `AgentMemorySection.tsx:360` — `break-words` am aktiven Fakt.
5. `AgentMemorySection.tsx:395` — `min-w-0` am Rejected-`<Stack>`.
6. `AgentMemorySection.tsx:396`/`:398` — `break-words` an Fakt und Notiz.
7. `AgentMemorySection.tsx:251` — `break-words` am Kontext-Absatz.
8. `AgentTokensSection.tsx:128` — `min-w-0` am Token-`<Stack>`, `break-all` am
   Token-Namen `:154`.
9. `AgentTokensSection.tsx:161` — `break-words` an der Zeitstempel-Zeile.

### Die Klassenwahl ist gemessen, nicht geraten

Die erste Fassage setzte überall `max-w-full break-all`, wie es die
Schwesterpakete #564/#572 an ihren Pillen taten. **Die Nachmessung hat das
widerlegt** — deshalb wurden drei Varianten (`break-all`, `break-words`,
`truncate`) in zwei Elternlagen gegeneinander gemessen:

| Variante | Pille in normaler 238-px-Spalte | Pille in kollabierter Spalte (Karte mit Zeilen-Aktionen) |
|---|---|---|
| ohne | 319,5 px, **+81 px Überlauf** | 256 px, **+256 px Überlauf** |
| `break-words` | 238 px, aber **Inhalt 297 px abgeschnitten** | 16 px breit, Inhalt abgeschnitten |
| `break-all` | 238 px ✓ | 16 px breit und **612 px HOCH** — ein Zeichen je Zeile |
| `min-w-0 truncate` | 238 px ✓ | 16 px, kein Überlauf ✓ |

Zwei Lehren, beide gemessen:

- **`break-words` reicht bei reinem snake_case nicht.** `overflow-wrap:
  break-word` bricht innerhalb eines Wortes nur, wenn das Wort allein nicht
  passt — und ein Underscore ist keine Trennstelle. Für die Pillen also
  unbrauchbar.
- **`break-all` ist an den Pillen aktiv schädlich.** Trägt die Karte
  Zeilen-Aktionen (`favorite-toggle` + „Einrichten"), kollabiert die
  `min-w-0 flex-1`-Textspalte des `EntityCard`-Primitives auf 16 px, und
  `break-all` zieht die Pille dann auf 612 px Höhe. Das wäre eine schlimmere
  Regression als der Ausgangsdefekt gewesen — und es hätte nur in dieser
  Eltern-Lage gezeigt, nicht in der isolierten Messung.

Darum an den Pillen **`min-w-0 truncate`** — AK 2 lässt „kürzt kontrolliert"
ausdrücklich zu, und es ist wörtlich das Muster aus
`AgentHierarchyView.tsx:64`/`:98`, das Vorentscheidung 1 des Issues als Vorbild
benennt. In den Fließtext-Absätzen (Fakt, Notiz, Kontext, Zeitstempel) bleibt
`break-words`: dort ist gemessen genug Spaltenbreite, damit es greift, und es
zerhackt gewöhnliche Sätze nicht. `break-all` nur am Token-Namen, der aus einem
einzigen trennstellenfreien Präfix-String besteht.

Die zweite Korrektur aus der Nachmessung: **`min-w-0` am Stack allein genügt
nicht.** Es beseitigte den Überlauf, ließ den Text aber abgeschnitten (299 px in
204 px) — §4.4 Punkt 5 greift dort, wo Punkt 1 schon erfüllt ist. Erst der
Umbruch am Absatz selbst behebt beides.

**Hit-Targets nach AK 4, je `min-h-10 md:min-h-0` (14):**

`AgentsPage` `:99`, `:293`, `:437` · `AgentMemorySection` `:109` (deckt drei
Aufrufstellen), `:163`, `:260`, `:346`, `:349`, `:366`, `:561` ·
`AgentTokensSection` `:136`, `:144`, `:165`, `:177`, `:186`.

Wörtlich die Klassenfolge aus PR #604 (`SettingsNav`) und #605 (`WorkAreaNav`,
`AreaGrants`): `min-h-10` hebt unterhalb `md` auf 40 px, `md:min-h-0` gibt ab
`md` die Verdichtung frei. `min-h-*` kollidiert in `tailwind-merge` nicht mit
dem `h-8`/`h-9` der Variante — die Variante bleibt die Desktop-Höhe. Eine
zweite Variante desselben Musters wäre Pattern Drift.

**Überlauf + Hit-Target zugleich (1):**

10. `AgentTokensSection.tsx:229` — `h-auto min-h-10 items-start py-2 text-left
    whitespace-normal md:h-9 md:min-h-0 md:items-center md:py-0`. Hier reicht
    `min-h-10` nicht: das `whitespace-nowrap` des Primitives erzwingt die
    282 px, also braucht die Aufrufstelle die Umbruch-Erlaubnis, und mit
    umbrechendem Text muss `h-9` zu `h-auto` werden, sonst schneidet die feste
    Höhe die zweite Zeile ab.

## Nachher gemessen (gegen `dist/assets/index-BLkDlzzj.css` aus dem Fix-Build)

| Viewport | vorher `scrollWidth`/`clientWidth` | nachher | Überläufer in Paket-Dateien |
|---|---|---|---|
| 320 | 477 / 320 ✗ | **320 / 320 ✓** | 5 → **0** |
| 375 | 477 / 375 ✗ | **375 / 375 ✓** | 4 → **0** |
| 768 | 768 / 768 ✓ | 768 / 768 ✓ | 0 → 0 |
| 1024 | 1024 / 1024 ✓ | 1024 / 1024 ✓ | 0 → 0 |

**Der horizontale Body-Scroll ist weg** — AK 1 ist für die vier Dateien erfüllt.
Interaktive Elemente unter 40 px: **7 → 0**.

Einzelwerte vorher → nachher (320 px):

| Stelle | vorher | nachher |
|---|---|---|
| Template-Pille | 256 px, +18 px Überlauf (319,5 px ohne Version) | **238 px, kein Überlauf** |
| Persona-Pille | 238 px, ohne Reserve | **238 px, kürzt kontrolliert** |
| Token-Disclosure | 282 px, +44 px Überlauf, 36 px hoch | **238 px, umbricht auf 56 px, 40 px Mindesthöhe** |
| Token-Stack | 335,5 px, +81 px, Inhalt abgeschnitten | **204 px, nichts abgeschnitten** |
| Memory-Stack aktiv | 298,9 px, +45 px, abgeschnitten | **204 px, Fakt umbricht auf 80 px** |
| Memory-Stack abgelehnt | 340,9 px, +87 px, abgeschnitten | **204 px, nichts abgeschnitten** |
| Kontext-Absatz | Inhalt 218 px in 204 px abgeschnitten | **204 px, umbricht auf 140 px** |
| Filter-Chips | 32 px | **40 px**, ab `md` unverändert 32 px |
| Filter-Reset | 32 px | **40 px**, ab `md` 32 px |
| „Einrichten" | 36 px | **40 px**, ab `md` 36 px |
| Löschen-Trigger (3 Stellen) | 32 px | **40 px**, ab `md` 32 px |
| Triage-/Zeilen-/Rename-Aktionen (11) | je 36 px | je **40 px**, ab `md` 36 px |
| Wichtigkeits-`Select` | 96 px | **96 px — unverändert** |
| Token-Zählerzeile | 86,1 + 7,8 px in 238 px | **unverändert** |

**Keine Desktop-Regression:** bei 768 und 1024 px sind sämtliche Maße
unverändert und kein einziges Element läuft über oder wird abgeschnitten —
Vorher-Nachher gegengemessen.

Was bei 320 px noch als „abgeschnitten" gemessen wird, sind ausschließlich die
`truncate`-Pillen — das ist die gewollte Wirkung der Klasse (Ellipse statt
Überlauf), nicht ein Restdefekt. Der einzige verbleibende Überlauf (+16 px)
entsteht in der kollabierten Textspalte des `EntityCard`-Primitives und ist
Primitive-Fund 2.

## Bewusst nicht geändert

- **`AgentMemorySection.tsx:336` `w-24`** — gemessen kein Defekt (96 px in
  204 px). Vorentscheidung 2 des Issues bot die Abfederung an; Weiche 1 verbietet
  sie ohne gemessenen Defekt.
- **`AgentTokensSection.tsx:211` Zählerzeile** — gemessen kein Defekt.
- **`AgentEditorForm.tsx`** — keine Änderung, alle Prüfpunkte erfüllt.
- **Die drei `<DialogContent>`-Aufrufstellen** — erben den W2-Inset, keine
  eigenen Caps (Issue-Vorgabe).
- **Die beiden langen Editor-Dateien aufteilen** — Vorentscheidung 4: ein
  Refactoring, kein Responsive-Audit.
- **`components/ui/*` und `components/data/*`** — Primitives, laut Karte melden
  statt reparieren.
- **Die sechs Dateien der Schwesterkarte** (`AgentHierarchyView`,
  `AgentDetailPage`, `CopyPromptButton`, `DeleteAgentButton`,
  `AgentConnectorSection`, `DuplicateAgentButton`) — Hälfte B.

## Primitive-Funde für den Handoff — nicht repariert

Alle drei sind gemessen, nicht vermutet, und keiner blockiert die vier Dateien.

1. **`components/ui/tabs.tsx` — `TabsList` scrollt nicht und bricht nicht.**
   Drei Trigger summieren 461 px; der Container klemmt sie bei 288 px ab, ohne
   `overflow-x-auto` und ohne `flex-wrap`. Der dritte Tab („Verbindung") ist bei
   320 px **unerreichbar**: er liegt +173 px außerhalb der Innenkante, ohne
   Scroll-Möglichkeit. Auch die Zwei-Tab-Variante überläuft (331 in 288).
   Betrifft **sieben Aufrufstellen in sechs Domänen** (`AgentEditorForm`,
   `AreaDetailPage`, `ResourceDetailPage`, `ToolDetailPage`,
   `SystemPromptDetailPage`, `PersonaDetailPage`, `FeedbackOverviewPage`) — eine
   Änderung dort wirkt überall und ist ein eigenes Paket. **Der gravierendste
   der drei Funde: ein Bedienelement ist nicht erreichbar, nicht nur knapp.**
2. **`components/data/EntityCard.tsx` — der Titel-`Link` trägt kein
   `break-words`.** `kundenservice_eskalation_stufe_zwei_bot` misst 282,5 px und
   läuft +116,5 px über; die Textspalte trägt `min-w-0`, dem `<a>` fehlt die
   Umbruch-Erlaubnis. PR #606 hat genau das für den *description*-Absatz und die
   `DetailHeader`-H1 getan — der Titel-Link derselben Komponente ist dabei offen
   geblieben. Trifft jede Listenseite des Produkts. Folgefehler: kollabiert die
   Meta-Spalte auf 0 px, wodurch dann *jede* Pille überläuft.
3. **`components/ui/checkbox.tsx` / `label.tsx` — Checkbox-Hit-Target 16 px.**
   Die Checkbox misst 16 × 16 px, das zugehörige `Label` ist 14 px hoch; keine
   der beiden klickbaren Flächen erreicht den **§11-Floor von 32 px** — anders
   als die übrigen Funde dieses Pakets ist das eine echte Norm-Unterschreitung,
   nicht nur ein AK-4-Thema. Betrifft das repo-weite Form-Checkbox-Muster (u. a.
   `SignupPage`), in `AgentEditorForm` 15 Aufrufstellen. Dasselbe gilt für
   `RadioGroupItem` (16 px).

## Test-first

Neue Fälle als **Klassen-Vertrag** neben der geänderten Datei (Muster W2/#513,
PR #604/#605). jsdom hat kein Layout — die Tests belegen, dass die gemessene
Lösung im Markup steht; die Layout-Aussage selbst ist hier gerendert belegt. Das
steht in jedem Testkommentar ausdrücklich so und wird nicht als Layout-Test
verkauft. Jeder Fall war vor der Änderung rot (Protokoll im Handoff).

## Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b            # NICHT --noEmit: das prueft null Dateien (Solution-File)
npm run test:coverage
npm run test:a11y
npm run build
npm run license:check
```

Dazu im Repo-Root `uv run python scripts/changelog_fragments.py check` und
`python3 scripts/check_code_refs.py`. Changelog als **Fragment** unter
`changelog.d/`, nicht in `CHANGELOG.md` (Verfahren in CONTRIBUTING.md).

### Gemessenes Ergebnis

| Gate | Ergebnis |
|---|---|
| `npm run lint` | Exit 0 — 0 errors, 68 vorbestehende Warnings (keine neue) |
| `npx tsc -b` | Exit 0 |
| `npm run test:coverage` | **207 Dateien, 1318 Tests, alle grün.** Statements 87,52 % · Branches **81,71 %** (Floor 79) · Functions 83,01 % · Lines 88,61 % |
| `npm run test:a11y` | 41 Dateien, 55 Fälle grün |
| `npm run build` | Exit 0 |
| `npm run license:check` | Exit 0 |
| `changelog_fragments.py check` | Exit 0, Fragment erkannt als `### Fixed` |
| `check_code_refs.py` | Exit 0, 0 errors |
| Grid-Gate aus AK 7 | liefert keine Zeile — vorher wie nachher |

Test-first-Protokoll: die 16 neuen Fälle liefen vor der Änderung rot (je mit
`expect(element).toHaveClass(...)`-Fehlschlag), die drei Nicht-Fund-Tests waren
von Anfang an grün — sie halten den gemessenen Ist-Zustand fest, damit
`w-24` und die Zählerzeile nicht ohne Messung „mitgefixt" werden.
