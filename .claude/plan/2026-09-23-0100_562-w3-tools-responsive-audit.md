# 562 — W3 Tools: Responsive-Audit von `features/tools` (4 Dateien)

Stand: 2026-09-23 · Branch `who2be/t_1ca8a551-562-w3-tools-responsive-audit-von-featur`
Basis: `origin/main` @ `b28c2ebd` · Issue: #562 (agent-ready) · Epic: #431 (W3)

## Auftrag

Die vier produktiven `.tsx` unter `apps/web/src/features/tools/` gegen die
sechspunktige Review-Checkliste aus `docs/frontend/design-language.md` §4.4
(Z. 218–233) prüfen; gefundene Defekte beheben, nicht gefundene begründet als
„kein Defekt" abhaken. Keine Änderung an geteilten Primitives.

## Ist-Zustand nachgemessen (auf `b28c2ebd`, nicht abgeschrieben)

```bash
find apps/web/src/features/tools -name '*.tsx' \
  ! -name '*.test.tsx' ! -name '*test-utils*' ! -path '*/test/*' | wc -l    # 4
grep -rnE 'grid-cols-|w-\[|min-w-|max-w-|justify-between|truncate|break-' \
  --include='*.tsx' apps/web/src/features/tools | grep -v '\.test\.tsx'     # (leer)
```

Bestätigt: kein Grid, keine feste Breite, keine `justify-between`-Zeile, **und
kein einziges `min-w-0` / `truncate` / `break-*`** in der gesamten Domäne.
Damit ist Weiche 2 des Issues (langer, umbruchfeindlicher Bezeichner) der
einzige realistische Kandidat — und er trifft zu.

## Befund je Datei

| Datei | §4.4-Punkt | Befund |
|---|---|---|
| `pages/ToolsPage.tsx` | 5 (Text bei 320 px) | **Defekt.** Der Alias steht in einem `Badge` mit `font-mono text-xs` ohne Umbruch-Regel. `alias` ist ein workspace-eindeutiger Fähigkeits-Alias (Migration 0065, serverseitig aus dem Namen abgeleitet, Unterstriche statt Leerzeichen) — also genau ein umbruchfeindliches Wort. Auf 320 px bleiben in der `EntityCard` nach `Container px-4`, Karten-`p-4` und Icon-Spalte ≈ 200 px; ein 30+-Zeichen-Alias in 12 px Mono misst ≈ 220 px und drückt die Karte auf. Dasselbe gilt für frei vergebene Tag-Badges. |
| `pages/ToolDetailPage.tsx` | 5 | **Defekt, gleiche Ursache.** Alias-Badge (`:112`) und Tag-Badges (`:121`) im `DetailHeader`-`badges`-Slot, ebenfalls ohne Umbruch-Regel. |
| `components/ToolEditorForm.tsx` | 1–6 | **Kein Defekt.** Einspaltig (`flex flex-col gap-6`), alle Felder sind Block-Elemente über die volle Breite. Der Alias steht hier in einem `<Input readOnly>` — ein natives Textfeld scrollt intern und läuft nicht über. Hilfetexte sind Fließtext mit Leerzeichen. |
| `pages/ToolNewPage.tsx` | 1–6 | **Kein Defekt.** `Container` + `Stack`, eine einzelne rechtsbündige Submit-Aktion; Buttons tragen `whitespace-nowrap`, der Text ist kurz. |

Punkte 2 (Grids) und 3 (feste Breiten): in der Domäne **nicht vorhanden**, Gate
unten gegengeprüft. Punkt 4 (Hit-Targets): siehe „Bewusst nicht geändert".
Punkt 6 (768/1024 px): einspaltiges Layout ohne Prefix skaliert monoton — die
Karten werden breiter, nichts schaltet um.

## Fix (minimal, ohne Breakpoint-Prefix)

Weiche 1 des Issues gilt: kein Prefix ohne gemessenen Defekt. Gegenmittel ist
die Umbruch-Regel am Badge selbst:

- Alias-Badge: `max-w-full break-all` — Mono-Bezeichner ohne Trennstellen
  dürfen mitten im Wort brechen, sonst bricht er gar nicht.
- Tag-Badge: `max-w-full break-words` — Tags sind Wörter, die an
  Wortgrenzen brechen sollen.

`Badge` ist `inline-flex`; `break-all`/`break-words` senkt die
min-content-Breite des Textinhalts, `max-w-full` deckelt die Badge gegen den
Flex-Container. Kein `min-w-0` nötig, weil die Badge kein Flex-Kind mit
Textüberlauf ist, sondern selbst der Überläufer.

Betroffen: `ToolsPage.tsx` (Alias + Tags), `ToolDetailPage.tsx` (Alias + Tags).
Vier `className`-Ergänzungen, keine Strukturänderung.

## Bewusst nicht geändert (mit Begründung)

1. **Hit-Targets (§4.4 Punkt 4).** In Reichweite dieser Domäne: CTA „Neues
   Tool" (`variant=brand`, `size` default → `h-10` = 40 px ✓), Filter-Reset
   (default ✓), Export-Button (`EntityExportButton`, default ✓), Danger-Zone-
   Toggle (`size="sm"` **mit** `h-auto … py-3` — `tailwind-merge` lässt
   `h-auto` gewinnen, effektiv ≈ 44 px ✓). Der Zurück-Link auf `ToolNewPage`
   ist `size="sm"` (36 px) — das ist **exakt** das Muster des geteilten
   `DetailHeader` (`components/data/DetailHeader.tsx`, Back-Button ebenfalls
   `size="sm"`). Eine Abweichung nur hier wäre Pattern-Drift in einer von
   dreizehn Domänen; gehört als repo-weite Entscheidung ins Primitive-Paket.
   → **Handoff-Meldung, keine lokale Änderung.**
2. **Beschreibungs- und Titelzeile.** `EntityCard`-`description` und die
   `DetailHeader`-`<h1>` rendern im Primitive ohne Umbruch-Regel. Ein sehr
   langer `mcp_server_name` ohne Trennzeichen bzw. ein langer Tool-Name kann
   dort überlaufen — betrifft alle dreizehn Domänen gleich.
   → **Handoff-Meldung, `components/*` ist Out of Scope.**

## Test-first

Neue Fälle als Klassen-Vertrag (Muster `components/ui/dialog.test.tsx`, das die
320-px-Eigenschaft ebenfalls über Klassen belegt — jsdom hat kein Layout):

- `ToolsPage.test.tsx`: Alias-Badge trägt `break-all`, Tag-Badge trägt
  `break-words`, beide `max-w-full`.
- `ToolDetailPage.test.tsx`: dasselbe für den `DetailHeader`-Badge-Slot.

Beide Blöcke laufen **vor** der Änderung rot (Beleg im PR-Verlauf: eigener
Commit „test(tools): …" vor dem Fix-Commit).

## Verifikation

```bash
cd apps/web
npm run lint
npx tsc -b
npm run test:coverage
npm run build
grep -rnE '(^|[^:a-z-])grid-cols-[2-9]' --include='*.tsx' \
  apps/web/src/features/tools | grep -v '\.test\.tsx'   # muss leer bleiben
```

## Changelog

Fragment unter `changelog.d/` (Verfahren seit PR #587), **nicht** direkt in
`CHANGELOG.md` — der CI-Guard `changelog-guard` weist das sonst ab.

## Grenzen

Nur `apps/web/src/features/tools/**` + Testnachbarn + `changelog.d/`.
Kein `components/ui/*`, kein `components/layout/*`, kein `components/data/*`.
Kein Merge, kein Push auf `main`.
