# Audit A8 Teil 2 (Web): Playbook-Detail auf DetailHeader

Status: aktiv · Karte t_8d2e750d · Basis origin/main ea59865b (#796, #798, #800, #816, #818 gemergt)
Norm: `docs/frontend/design-language.md` §4.4 „Kopf der Detailseiten“ (aus #796)

## Outcome
`PlaybookDetailPage` rendert `components/data/DetailHeader.tsx` mit `status`,
`version`, `locale` und `tags`. Statt des Einzel-Chips `Aktiv · v1` stehen
dort zwei Chips, Status und Version. Die Reihenfolge
`Status · Version · Sprache · Slug · Tags` legt der Header fest. Die Tabs
lauten `Bearbeiten · Beziehungen · Prüffälle · Versionen`, und Feedback und
Export liegen unter `md` hinter „Mehr“.

## Vorher (gemessen, Stack w2b327, Vite 5211)
- Kein Overflow bei 1280 und 390 px, hell und dunkel.
- Chips: `Aktiv · v1` als ein Chip, dazu `DE`. Die Tags fehlen im Kopf.
- Die Trigger-Leiste steht schon in der Zielreihenfolge (`PlaybookDetailTabs.tsx`).
  Abweichend ist nur `PLAYBOOK_TABS` in der Page (`edit, relations, versions, tests`),
  also eine zweite Kopie der Reihenfolge.
- Bei 390 px liegen Feedback und Export offen, die Tab-Leiste beginnt bei y=426.

## Entscheidungen
- **Eine Quelle für die Tab-Reihenfolge:** `PlaybookDetailTabs.tsx` exportiert
  `PLAYBOOK_DETAIL_TABS`, abgeleitet aus `TABS`. Die Page nutzt diese Liste
  statt der eigenen Konstante.
- **Icon-Kachel:** Die Kachel behält ihr Typ-Icon und die Tönung je Typ, wie in
  Liste und Leerzustand. `typeMeta.ts` bekommt dafür ein Feld `tone: EntityTone`.
  Die Tönung entspricht genau der bisherigen `tint`, es entsteht also keine
  zweite Farbtabelle. Die Alternative `iconTone="playbook"` für alle Typen
  hätte die bekannte Typfarbe im Detail stillschweigend geändert.
- **Zurück-Link bleibt in der Page** und wird nicht über `backHref` gebaut. Er
  steht außerhalb von `DataView`, damit er auch bei Ladefehlern sichtbar bleibt,
  und hält das 40-px-Ziel aus #573 AK 5 (`min-h-10 md:min-h-0`, Test vorhanden).
  `DetailHeader` rendert ihn ohne diese Klasse.
- **Slug:** Playbooks haben keinen `slug` (`api/types.ts` Playbook). Der Slot
  bleibt deshalb leer und entfällt.
- **Tags:** `TagList` mit `Badge variant="secondary"` wie bei Resource. Unter `md`
  werden es höchstens 3 plus „+n“.
- **Status:** `StatusBadge` mit `pendingDraft`, wie bei Persona und Resource.
- **Aktionen:** Feedback (admin/editor) und Export mit `collapseActionsBelowMd`.
  Beides sind Sekundäraktionen, die Statusaktionen bleiben im ReviewBanner.

## Dateien (Budget 8)
1. `apps/web/src/features/playbooks/pages/PlaybookDetailPage.tsx`
2. `apps/web/src/features/playbooks/pages/PlaybookDetailPage.test.tsx` (Tests für Chip- und Tab-Reihenfolge und „Mehr“; der alte Chip-Test wird angepasst)
3. `apps/web/src/features/playbooks/components/PlaybookDetailTabs.tsx` (Export der Reihenfolge)
4. `apps/web/src/features/playbooks/lib/typeMeta.ts` (`tone`)
5. `docs/frontend/design-language.md` §4.4 (Beispielliste)
6. `changelog.d/playbook-detail-header.changed.md`
7. dieser Plan

## Verifikation
- Rot-Proben: In `DetailHeader` wird LocaleBadge vor den Status gezogen, dann wird der Chip-Test rot. In `TABS` werden Prüffälle und Versionen getauscht, dann wird der Tab-Test rot.
- In `apps/web` unter Node 22.23.3: `npm run lint`, `npx tsc -b`, `npm run i18n:check`,
  `npm run test:coverage`, `npm run build`, `npm run license:check`.
- Nachher-Screenshots und measure.json mit demselben Skript wie beim Vorher-Lauf
  (`~/.hermes/profiles/coder/cache/scratch/a8shots/`).
- Die CI `all-green` muss gegen den Head-SHA laufen. Die E2E-Specs `scroll-guard`
  und `status-actions-viewport` laufen in der CI.

## Nachher (gemessen, derselbe Lauf)
| Zustand | scrollWidth/clientWidth | Chips | min. Kontrast Chip / Tab / Beschreibung | Tabs ab y |
|---|---|---|---|---|
| 1280 hell | 1280/1280 | Aktiv · v1 · DE · onboarding · vertrieb · kundenservice · nord | 4,58 / 4,74 / 4,74 | 292 (vorher 272) |
| 1280 dunkel | 1280/1280 | dto. | 7,08 / 7,66 / 7,66 | 292 |
| 390 hell | 390/390 | Aktiv · v1 · DE · 3 Tags + „+1“ | 4,58 / 4,74 / 4,74 | 450 (vorher 426), „Mehr“ sichtbar |
| 390 dunkel | 390/390 | dto. | 7,08 / 7,66 / 7,66 | 450, „Mehr“ aufgeklappt 506 |

Der Mindestwert 4,58 gehört zum Status-Label „Aktiv“ in hell (StatusBadge,
`text-muted-foreground` auf `bg-muted/40`). Es ist dasselbe Bauteil wie auf
Persona und Resource. Vorher lag der Wert bei 4,74 auf weißem Grund, beide
Werte liegen über AA 4,5. Die Tab-Leiste rückt bei 390 um 24 px nach unten,
weil die Tags jetzt im Kopf stehen (zwei Zeilen). „Mehr“ spart die Zeile mit
Feedback und Export (56 px).

## Fortschritt
- [x] Vorher-Screenshots und Messung
- [x] Umsetzung
- [x] Tests mit Rot-Proben (DetailHeader-Reihenfolge vertauscht: Chip-Test rot; TABS getauscht: Tab-Test rot; alter Page-Code: 3 Tests rot)
- [x] DoD lokal
- [x] Nachher-Screenshots
- [ ] Push, PR
