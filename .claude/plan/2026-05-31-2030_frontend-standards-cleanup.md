# Plan — Frontend-Standards-Cleanup (Composite/Modi/Tags-UI)

**Datum:** 2026-05-31
**Anlass:** Audit der 15 neuen/geänderten Web-Dateien aus PR #80
(Composite-UI, Persona-Modi, Resource-Tags, Profil-Pill) gegen
`docs/frontend/design-language.md` (§2–13) + Notion-Playbook
„Frontend-Standards" + `CLAUDE.md` §Frontend-Standards/§Lint-Gates.
**Ziel:** Eigenständiger PR mit den verifizierten Design-Abweichungen.

## Branch & PR-Strategie

- **Basis-Branch:** `claude/modest-hamilton-OIyAE` (Feature-Branch von #80).
  Der zu fixende Code existiert **nur** dort, nicht auf `main`.
- **Neuer Branch:** `claude/frontend-standards-cleanup` (von HEAD des
  Feature-Branches).
- **Neuer PR (Draft):** Base = `claude/modest-hamilton-OIyAE` (gestackt, damit
  der Diff **nur** die Cleanups zeigt und #80 sauber bleibt).

## Verifikationslage (wichtig)

Das Roh-Audit hat überflaggt. Nach Gegenprüfung gegen die reale Codebasis
bleiben **drei** legitime Punkte. Verworfen:
- **Catalog-Showcases:** Es existiert **keine** Feature-Komponenten-Showcase im
  Repo (`app/catalog/showcases/` enthält ausschließlich `ui/`-Primitives).
  Showcases sind nicht die etablierte Konvention für Feature-Komponenten →
  **kein Fix**.
- **ASCII-Umlaute in Code-Kommentaren:** §13.7 erlaubt ASCII (`ue/oe/ae/ss`)
  ausdrücklich in Code-Identifiern, Datei-Kommentaren und Repo-Doku. Nur
  *sichtbarer UI-String* braucht Volltext-Umlaute → **kein Fix**.
- **FormSection-Einbettung:** bereits korrekt (PersonaModesEditor sitzt in
  `FormSection "Modi (optional)"`, ComposesPicker/ComposedByList in Cards).

---

## Fix 1 — Spacing außerhalb des 4px-Grids (§4.1, §13.3) · BLOCKER-nah

- **Datei:** `apps/web/src/features/playbooks/components/PlaybookComposesPicker.tsx:197`
- **Ist:** `className="flex cursor-pointer flex-col gap-0.5 font-normal"`
- **Problem:** `gap-0.5` = 2px liegt außerhalb der erlaubten Stufen
  `{1,2,3,4,6,8,12,16}`.
- **Fix:** `gap-0.5` → **`gap-1`** (4px). Optisch praktisch identisch, grid-konform.
- **Gegencheck:** kein weiterer `gap-0.5`/`p-0.5`/`*-0.5` in den neuen Dateien
  (per `git diff origin/main...HEAD` verifiziert — nur diese eine Stelle).

## Fix 2 — Brand-Tinte auf Nicht-CTA-Fläche (§2.2, §8) · diskutabel

- **Datei:** `apps/web/src/features/personas/components/PersonaModesEditor.tsx:89`
- **Ist:** `field.is_default && 'border-brand/40 bg-brand/5'` — markiert die
  Default-Modus-Karte mit Brand-Tinte.
- **Bewertung:** Opacity-Modifier auf Tokens sind im Repo idiomatisch
  (`bg-muted/30`, `border-border/40`, `text-muted-foreground/60` existieren).
  **Aber** die Designsprache reserviert die Brand-Tinte bewusst für die *eine*
  Primary-CTA pro Surface (§2.2) und verbietet Brand z.B. auf Icons (§8). Eine
  Brand-getönte Hintergrundfläche für einen passiven „Default"-Marker dehnt das.
- **Fix (Default-Empfehlung):** auf neutrale Hervorhebung wechseln, die schon
  im Repo etabliert ist:
  `field.is_default && 'border-border bg-muted/40'`
  Der „Default"-Status wird **zusätzlich** durch das bestehende Badge „Default"
  getragen (Information nicht allein über Farbe — §11). Damit bleibt die
  Brand-Tinte exklusiv den CTAs.
- **Hinweis:** Falls bewusst ein Brand-Akzent gewünscht ist (Produktentscheid),
  ist die saubere Alternative ein dedizierter Token (`--brand-subtle` o.ä.) in
  `globals.css` statt Inline-Opacity — das wäre aber Token-Arbeit + Mini-ADR
  und ist hier **out of scope**. Default ist die neutrale Variante.

## Fix 3 — A11y-Tests für neue interaktive Komponenten (§11, §13.8) · WICHTIG

§13.8: „Jede neue klickbare/eingebbare Komponente bekommt einen
`*.a11y.test.tsx` (`vitest-axe`)." Im Repo existieren Komponenten-a11y-Tests
(`tag-input.a11y.test.tsx`, `info-tooltip.a11y.test.tsx`,
`BranchStatus.a11y.test.tsx`) → das Muster ist etabliert. Zwei neue interaktive
Komponenten haben keinen:

- **`PersonaModesEditor`** (Field-Array-Form: Inputs, Textareas, Radio/Switch,
  Add/Remove-Buttons) →
  neu: `apps/web/src/features/personas/components/PersonaModesEditor.a11y.test.tsx`
- **`PlaybookComposesPicker`** (Dialog mit Multi-Select + Reorder) →
  neu: `apps/web/src/features/playbooks/components/PlaybookComposesPicker.a11y.test.tsx`

**Muster:** exakt `tag-input.a11y.test.tsx` / `BranchStatus.a11y.test.tsx`
spiegeln — `render(...)` in einen react-hook-form-`Form`-Harness (wie in den
bestehenden `*.test.tsx` derselben Komponenten), dann
`expect(await axe(container)).toHaveNoViolations()`. Für den Dialog-Fall den
geöffneten Zustand testen (Trigger klicken → Dialog-Content im DOM), damit axe
den Dialog-Inhalt sieht. Die vorhandenen `PersonaModesEditor.test.tsx` /
`PlaybookComposesPicker.test.tsx` liefern den fertigen Harness zum Wiederverwenden.

**Begleitcheck:** Falls beim Schreiben echte axe-Violations auftauchen (z.B.
Icon-only-Button ohne `aria-label`, fehlendes `label`/`aria-label` an einem
Reorder-Button), diese **mitfixen** (das ist der eigentliche Wert des Tests),
nicht die Assertion aufweichen.

---

## Nicht-Ziele (Out of Scope)

- Keine Logik-/Verhaltensänderung an Composite/Modi/Tags — reines
  Design-Standards-Alignment.
- Keine neuen Design-Tokens / kein ADR (Fix 2 nutzt Bestands-Tokens).
- Keine Catalog-Showcases (nicht die Repo-Konvention für Feature-Komponenten).
- Keine Touch an Backend, MCP, Doku.

## Umsetzung (ein Agent, da klein & fokussiert)

`frontend-developer` (Sonnet) auf Branch `claude/frontend-standards-cleanup`:
1. Fix 1 (gap-1), Fix 2 (neutrale Default-Markierung), Fix 3 (zwei a11y-Tests
   + ggf. axe-Violations beheben).
2. DoD (aus `apps/web/`): `npm run lint`, `npx tsc --noEmit`, `npm test`,
   `npm run build` — alle grün.
3. Conventional Commit; **nicht** pushen (Integration durch den Coder).

## DoD (gesamt)

- Vier Web-Gates grün, lokal verifiziert.
- Diff enthält **nur** die drei Fixes + zwei neue Test-Dateien.
- Separater Draft-PR gegen `claude/modest-hamilton-OIyAE`, Session-Link im Body.

## Offener Punkt (Bericht)

- Fix 2: neutrale Default-Markierung (Default) vs. dedizierter `--brand-subtle`-
  Token (Produktentscheid). Plan wählt neutral; bei Wunsch nach Brand-Akzent
  Rückmeldung → dann Token+ADR als Folge-PR.
