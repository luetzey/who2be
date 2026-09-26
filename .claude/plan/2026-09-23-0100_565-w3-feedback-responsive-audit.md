# #565 W3 Feedback — Responsive-Audit `features/feedback` (6 Dateien)

Branch: `who2be/t_8b228bda-565-w3-feedback-responsive-audit-von-fea`
Basis: `origin/main` @ `b28c2ebd` (fast-forward nachgezogen)
Spezifikation: Issue #565 (agent-ready, keine offene Entscheidung)
Norm: `docs/frontend/design-language.md` §4.4 (sechspunktige Review-Checkliste),
§11 (A11y-Minimum)

## Befund je Datei (gegen die §4.4-Checkliste, 320/375/768/1024 px)

| Datei | Befund | Aktion |
|---|---|---|
| `pages/FeedbackOverviewPage.tsx` | **Defekt (Punkt 2/3).** Die Kurations-Zeile trägt drei feste Anteile in einer `flex`-Reihe: `w-52 flex-none` (208 px) + `min-w-[7.5rem] flex-1` (120 px) + `w-24 flex-none` (96 px) = **424 px** plus 3×`gap-4` (48 px) plus Chevron — auf 320 px rechnerisch nicht darstellbar. Kein Breakpoint-Prefix in der Datei. | Zeile unterhalb `md` stapeln (Weiche 1); die drei Breiten `md:`-präfixieren, der erklärende Kommentar wird mitgezogen (Weiche 2); dekorativer Chevron nur ab `md` |
| `pages/FeedbackDetailPage.tsx` | **Defekt (Punkt 1)** an drei `justify-between`-Zeilen ohne `flex-wrap`: Erfolgsquote-Zeile, `CardHeader` „Signale", `CardHeader` „Ereignisse" (Titel + Button nebeneinander erzwungen). `max-w-5xl … sm:px-6` und `md:grid-cols-2` **erfüllt**. `labelWidth="w-24"`/`"w-20"`: **kein Defekt** — auf 320 px bleiben dem Balken nach Label (96) + 2×`gap-3` (24) + Zahl `w-8` (32) noch ~90 px; Weiche 4 greift nur bei gemessenem Überlauf, `DataList`/`MeterRow`-Prop bleibt unangetastet. | `flex-wrap` an den drei Zeilen (Weiche 3) |
| `pages/FeedbackItemDetailPage.tsx` | **Defekt (Punkt 1)** an `DefRow` (`flex items-start justify-between gap-3`, `dt` ist `flex-none`) und an der Signal-Zeile (`flex items-center gap-2`, Label + Badge). `max-w-5xl … sm:px-6` und `md:grid-cols-2` **erfüllt**; `min-w-0` am `dd` **erfüllt**. `CardTitle` mit `History`-Icon (`flex items-center gap-2`): **kein Defekt** — das Icon ist `size-4 flex-none`, der Titel ein anonymes Flex-Item, das im Container normal umbricht; ein `flex-wrap` würde Icon und Titel ohne Not trennen. | `flex-wrap` an `DefRow` und der Signal-Zeile |
| `components/ResolutionSegments.tsx` | **Defekt (Punkt 1 + 4).** Vier Segmente `h-7` (**28 px**) liegen unter dem §11-Hit-Target-Floor; die Gruppe ist `inline-flex` **ohne `flex-wrap`** und damit auf 320 px nicht schrumpffähig (vier Labels ≈ 240 px in einer Karte, die nach Page- und Card-Padding ~240 px breit ist). | `flex-wrap` an der Gruppe; Segment-Höhe `h-10` unterhalb `md`, `md:h-7` darüber |
| `components/FeedbackInbox.tsx` | **kein Defekt.** `sm:grid-cols-2 lg:grid-cols-3` mobile-first gebunden; Filter-Chip-Reihe trägt `flex-wrap`; `StatusChip` ist `h-8` (32 px) und liegt auf dem §11-Floor; der Karteninhalt (Betreff, Melder, Zeitstempel) rendert über `EntityCard`/`MetaPill` — geteilte Primitives unter `components/data/`, **out of scope** (Issue #565 §Out of scope). | — |
| `components/ReportProblemDialog.tsx` | **kein Defekt.** `DialogContent` ohne eigene Breitenklasse erbt den W2-Default (`w-[calc(100vw-2rem)] max-w-lg` + `max-h`/Scroll, #513). Beide Formularfelder tragen `w-full` in einem `flex-col`-Label; der `DialogFooter` bricht über das Primitive um. | — |

**Breakpoint-Abdeckung danach: 5 von 6** (`ReportProblemDialog` braucht keinen —
er erbt die Abfederung aus dem Primitive).

## Weichen — geerbt aus dem Issue, nicht neu entschieden

1. `FeedbackOverviewPage`: **stapeln unterhalb `md`**, nicht Breiten verkleinern.
2. `min-w-[7.5rem]`: **`md:`-präfixieren, nicht entfernen**; Kommentar mitziehen.
3. `justify-between`-Zeilen: **`flex-wrap`**, keine zweite Render-Variante.
4. `labelWidth`-Prop: **nur bei gemessenem Überlauf** — hier gemessen: kein
   Überlauf, also unangetastet. `DataList`/`MeterRow` bleiben unberührt.
5. Tests: `*.test.tsx` neben die geänderte Datei, Klassen-Assertion; die
   visuelle Gegenprobe ist W4.

Schwelle `md` folgt #500 (`hooks/useMediaQuery.ts`) — die Prefixe sind `md:`.

### Hit-Target: der verbindliche Floor ist 32 px, nicht 40 px

Das Issue nennt in AK 5 „≥ 40 px (§11 A11y-Minimum)". §11 selbst schreibt:
„Buttons `size="default"` = 40px (HIG-konform ≥ 32px), Mobile-Hits bevorzugt
44px" — der **Floor** ist 32 px, 40 px ist der Wert der Default-Variante. Die
Schwesterkarte zum Dashboard-Paket (#563 / PR #596) hat das mit dem PM geklärt.
`ResolutionSegments` liegt mit `h-7` (28 px) **unter beiden** Lesarten und wird
deshalb behoben — mit `h-10` (40 px) unterhalb `md`, womit auch die wörtliche
AK-Fassung erfüllt ist. `StatusChip` (`h-8`, 32 px) und die Sortier-Buttons der
Kuration (`h-8`) liegen auf dem Floor und bleiben unverändert.

## Schritte

1. **Rot:** Klassen-Assertions schreiben und fallen sehen
   - `FeedbackOverviewPage.test.tsx`: die drei Spalten der Kurations-Zeile
     tragen ihre festen Breiten nur noch `md:`-präfixiert; die Zeile ist
     `flex-col md:flex-row`.
   - `FeedbackDetailPage.test.tsx` (**neu**): die drei `justify-between`-Zeilen
     tragen `flex-wrap`.
   - `FeedbackItemDetailPage.test.tsx`: `DefRow` und die Signal-Zeile tragen
     `flex-wrap`.
   - `ResolutionSegments.test.tsx` (**neu**): Gruppe trägt `flex-wrap`,
     Segmente tragen `h-10 md:h-7` und kein nacktes `h-7`.
2. **Grün:** die vier Änderungen anwenden.
3. **Gates:** Grid-Gate aus AK 4; `npm run lint`, `npx tsc -b`,
   `npm run test:coverage` (Branches-Floor 79), `npm run build`,
   `npm run i18n:check`, `npm run license:check`.
4. **Changelog:** Fragment `changelog.d/feedback-responsive-audit.changed.md`
   (Fragment-Verfahren, **nicht** `CHANGELOG.md` — PM-Korrektur zur
   Issue-Anweisung „§Unreleased, als letzter Commit").
5. Commit, Push, PR gegen `main`, `all-green` am exakten Head-SHA abwarten.

## Grenzen

Nur `apps/web/src/features/feedback/**` + Testnachbarn + `changelog.d/` +
diese Plan-Datei. Keine Änderung unter `components/ui/**`,
`components/layout/**` oder `components/data/**`. Kein neuer i18n-Schlüssel
(die Änderungen sind rein layoutseitig).
