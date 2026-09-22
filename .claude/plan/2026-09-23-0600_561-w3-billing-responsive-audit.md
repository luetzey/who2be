# W3 Billing: Responsive-Audit von `features/billing` (Issue #561)

Stand: 2026-09-23 · Branch `who2be/t_e6fa9fa8-561-w3-billing-responsive-audit-von-feat`
Basis: `origin/main` @ `b28c2ebd` (der Worktree war 166 Dateien zurueck und wurde
per `git merge --ff-only origin/main` nachgezogen — der Ist-Zustand des Issues
wurde auf `87de64c` gemessen, siehe „Zeiger-Drift" unten).

## Ziel

`BillingPanel` im **Cloud-Build** gegen die sechspunktige Review-Checkliste aus
`docs/frontend/design-language.md` §4.4 pruefen; jeder Defekt behoben oder als
„kein Defekt" begruendet. Grenzen und Akzeptanzkriterien kommen unveraendert
aus #561.

## Zeiger-Drift gegenueber dem Issue

Das Issue nennt `BillingPanel.tsx:78`, `:134`, `:144` auf `87de64c`. Zwischen
`87de64c` und `b28c2ebd` hat #536 die `StorageBar` eingefuegt (+63 Zeilen), die
Zeilennummern sind verschoben. Symbolanker statt `datei:zeile`
(`docs/code-references.md`):

| Issue-Zeiger (`87de64c`) | Symbol auf `b28c2ebd` | Klassen |
|---|---|---|
| `:78` | `QuotaBar` — Label/Wert-Zeile | `flex items-center justify-between text-sm` |
| `:134` | `BillingPanel` — `CardHeader`-Zeile | `flex items-center justify-between gap-2` |
| `:144` | `BillingPanel` — `<dl>` | `grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2` — **erfuellt** (W2/#513) |

**Dritte Fundstelle derselben Defektklasse:** `StorageBar` traegt seit #536 die
identische Zeile (`flex items-center justify-between text-sm`, Label links,
`{formatBytes(used)} / {formatBytes(quota)}` rechts). Sie stand am Mess-Stichtag
des Issues noch nicht im Repo, liegt aber in derselben Datei, derselben Domaene
und unter demselben Akzeptanzkriterium. Sie wird mitbehoben — sie auszulassen
hiesse, denselben Defekt wissentlich stehen zu lassen.

## Befund je Checklistenpunkt (§4.4, Z. 222–233)

1. **320 px ohne horizontalen Scroll** — die drei `justify-between`-Zeilen sind
   der einzige Kandidat: zwei Flex-Kinder ohne `min-w-0`, beide mit
   `min-width: auto` (Default), also nicht unter ihre Inhaltsbreite
   schrumpfbar. Bei langem Label + langem Wert (`Belegter Speicher` /
   `100 MB / 100 MB`) laeuft die Zeile ueber statt zu kuerzen. → **Defekt**
2. **Mehrspaltige Grids an Prefix gebunden** — `<dl>` ist `grid-cols-1
   sm:grid-cols-2`. Gate aus AK 3 liefert keine Zeile. → **kein Defekt**
3. **Feste Breiten responsiv** — keine `w-*`/`max-w-*` ausser `w-full`
   (Buttons, Bars). → **kein Defekt**
4. **Hit-Targets ≥ 40 px unterhalb `md`** — der einzige Hit ist der CTA-Button
   in `size="default"` = `h-10` = 40 px (`components/ui/button.tsx`, Variante
   `size.default`). Kein `size="sm"` im Panel. → **kein Defekt**, wird durch
   einen Regressionstest festgenagelt.
5. **Text bei 320 px lesbar** — identisch zu Punkt 1. → **Defekt**
6. **768 px / 1024 px gegengeprueft** — `sm:grid-cols-2` greift ab 640 px, die
   Zeilen darueber sind unkritisch (mehr Platz). Der Fix ist rein additiv
   (`min-w-0`, `truncate`, `shrink-0`) und aendert oberhalb `sm` nichts, weil
   dort nichts kuerzt. → **kein Defekt**

## Fix (Weiche: `flex-wrap` vs. `min-w-0` + `truncate`)

AK 2 laesst beides zu. Gewaehlt: **`min-w-0` + `truncate` am Label,
`shrink-0` am Wert**, nicht `flex-wrap`.

**Weil** die rechte Seite in allen drei Zeilen die Information traegt
(`250 / 1000`, `25 MB / 100 MB`, Status-Badge) und `flex-wrap` sie auf eine
zweite Zeile linksbuendig unter das Label schiebe — die Label/Wert-Zuordnung
ginge verloren und die Zeilenhoehe spraenge. `truncate` kuerzt stattdessen das
Label (das aus dem Kontext erschliessbar bleibt) und haelt den Wert vollstaendig
und rechtsbuendig. Das entspricht Checklistenpunkt 5 („kein Wortsalat durch zu
schmale Flex-Kinder ohne `min-w-0`") woertlich.

Konkret, drei Zeilen in `BillingPanel.tsx`:

- `QuotaBar`/`StorageBar`: Zeilencontainer `+gap-2`; Label-`<span>`
  `+min-w-0 +truncate`; Wert-`<span>` `+shrink-0`.
- `CardHeader`: `CardTitle` `+min-w-0 +truncate`, `Badge` `+shrink-0`
  (className an der Aufrufstelle — das Primitive selbst bleibt unberuehrt,
  Grenze aus #561/W2).

`cn()`/`tailwind-merge`: keine der ergaenzten Klassen gehoert zur Familie einer
bestehenden (`min-w-*` vs. keine, `shrink-*` vs. keine, `truncate` vs. keine) —
es loescht nichts.

## Test-first

Neue Testfaelle in `BillingPanel.test.tsx`, Block „Responsive (#561, §4.4)":

1. `QuotaBar`-Zeile: Label `min-w-0` + `truncate`, Wert `shrink-0`.
2. `StorageBar`-Zeile: dito.
3. `CardHeader`-Zeile: Titel `min-w-0` + `truncate`, Badge `shrink-0`.
4. `<dl>` bleibt `grid-cols-1 sm:grid-cols-2` (Regression gegen W2/#513).
5. CTA-Button bleibt `h-10` (AK 4, ≥ 40 px).

Jeder Fall wird **vor** der Aenderung rot gefahren und das Ergebnis
protokolliert.

## Aus dem Scope genommen

`features/settings`/`OrgSettingsPage.tsx`, `components/ui/*`, jede andere
Domaene, W4/Playwright, ADR-0029 selbst, `apps/api`/`apps/mcp`/`packages/**`.

## Changelog

**Nicht** `CHANGELOG.md` (CI-Guard `changelog-guard` seit PR #587), sondern
`changelog.d/w3-billing-responsive.fixed.md`.

## Verifikation (Node 22 via `mise x`)

```bash
cd apps/web
npm run lint
npx tsc -b
VITE_WHO2BE_EDITION=cloud npm run test:coverage
npm run test:a11y
VITE_WHO2BE_EDITION=cloud npm run build
npm run license:check
npm run build && grep -rl 'BillingPanel' dist/assets/ ; # muss OK melden
uv run python scripts/changelog_fragments.py check
```
