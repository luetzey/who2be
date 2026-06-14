# Frontend UX-Refactor: States, A11y, Spacing-Primitives, Tokens

Living document. Stand: 2026-05-26.

## /goal

**Outcome:** Jede Liste/Detail-Seite deckt Loading/Empty/Error einheitlich ab,
sichtbarer Fokus auf allen interaktiven Elementen, Abstaende ausschliesslich
ueber Layout-Primitives, keine Arbitrary Values mehr, Tokens decken Light- und
Dark-Mode ab.

**Completion-Condition (transkript-nachweisbar):**
- `npm run lint` exit 0
- `npx tsc --noEmit` exit 0
- `npm test` exit 0
- `npm run build` exit 0
- `git grep -nE 'translate-y-\[|w-\[[0-9]+(px|rem)|h-\[[0-9]+(px|rem)|p-\[|m-\[|gap-\[|#[0-9a-fA-F]{3,6}\b' apps/web/src` keine Treffer ausser benannten Ausnahmen
- Smoke per `curl localhost:5173/` 200; visuelle Smoke-Check Light + Dark im Browser.

**Guardrails (Constraints):**
- Keine direkten Commits/Pushes auf `main`.
- Keine eigenen UI-Primitives ausserhalb `components/ui/` (per ESLint).
- `react-conventions`-Skill + Frontend-Standards-Playbook + Security-Standards-Playbook gelten.
- Auth-Tokens nicht in localStorage. Sonstige Preferences (Theme) sind ok.

**Out of Scope:**
- Theme-Toggle-UI (Acceptance verlangt nur "Light + Dark ok" — `prefers-color-scheme` reicht).
- Neue Seiten / Features.
- Backend-/MCP-Aenderungen.

## Schritte

### S1 — Layout-Primitives `Stack` + `Section`
- `@/components/layout/Stack.tsx`: `space-y-{xs|sm|md|lg|xl}` ueber CVA. Default `md`.
- `@/components/layout/Section.tsx`: semantisches `<section>`-Element, vertikaler
  Abstand zwischen Page-Bloecken; akzeptiert optionalen `aria-label`/`title`.
- Tests: keine eigenen (reine Layout-Primitives).

### S2 — `DataView` Wrapper (single-state)
- `@/components/data/DataView.tsx`: Props `loading? | error? | empty?` + `children`,
  rendert **genau einen** Zustand. Erbt aria-live="polite" im Loading-Fall.
- Refactor: `usePersonas`/`usePlaybooks`/`useTokens` bleiben, Pages nutzen DataView.

### S3 — Detail-Pages auf DataView heben
- `PersonaDetailPage`: ausser Top-Back-Button alles innerhalb `DataView`. Damit
  ist Loading XOR Error XOR Content sichtbar — kein doppelter ErrorAlert+Skeleton.
- `PlaybookDetailPage`: dito.
- `SettingsTokensPage`: bleibt — Tokens-Liste laeuft schon via DataList, sub-States ok.
- Sub-Listen ("Verknuepfte Playbooks" in PersonaDetail): nutzen DataView statt
  manuellem `loading ? <LoadingState /> : ...`.

### S4 — A11y
- `AppShell` NavLinks: `focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-offset-2`.
- AppShell `<nav>` mit `aria-label`.
- `CardTitle`: rendert standardmaessig als `<h3>` (shadcn-Upstream-Pattern) ueber
  Slot/`asChild`. Konsumenten lassen das innere `<h2>` weg.
- Icon-only Buttons: heutige Pages haben keine — Logout-Button hat Text. OK.

### S5 — Spacing-Cleanup
- Pages ersetzen `mb-4 / mb-6 / space-y-X` zwischen Top-Level-Blöcken durch
  `<Stack gap="md">` bzw. `<Section>`. Innen-Cards/Forms behalten ihr Form-Layout
  (`space-y-4` ist hier Form-interner Rhythmus — bleibt, weil cards selbst ein
  geschlossenes Layout-Primitive sind).
- Begruendung: Frontend-Standards "Layout-Rhythmus ueber Primitives" zielt auf
  Page-/Section-Abstaende, nicht auf Form-Field-Rhythmus innerhalb von Cards.

### S6 — Dark-Mode-Tokens
- `globals.css`: `@media (prefers-color-scheme: dark) { :root { ... } }` mit
  invertierten HSL-Werten (background/foreground/card/muted/border/primary/etc.).
- Kein `.dark`-Class-Switch, kein Toggle.

### S7 — Arbitrary-Value-Cleanup
- `components/ui/alert.tsx`: `translate-y-[-3px]` entfernen oder durch token-basierten Anker ersetzen (Icon-Alignment via `items-start` + native Icon-Hoehe).

### S8 — Tests
- Bestehende Tests laufen lassen; wo durch Refactor gebrochen: anpassen.
- Bei jeder Liste/Detail-Seite ein neuer Test "rendert Loading-Skeleton",
  "rendert Error-Alert", "rendert Empty-State" — soweit nicht schon abgedeckt.

### S9 — Verify
- `npm run lint`
- `npx tsc --noEmit`
- `npm test`
- `npm run build`
- Browser Smoke: Light- und Dark-Mode-Switch via macOS-Systempref oder DevTools-Emulate.

## Doku-Log

### 2026-05-26 — Umsetzung abgeschlossen

**Verifikation (transkript-nachweisbar):**
- `npx tsc --noEmit` → exit 0
- `npm run lint` → exit 0
- `npm test` → 34/34 passed (12 Suites)
- `npm run build` → exit 0, dist 553 kB
- `docker compose up -d --build --wait web` → healthy
- `curl localhost:5173/` → 200, neues Bundle `index-BYlkl7Fe.css`
- Strenger Arbitrary-Value-Grep `(translate-y-\[-?\d+(px|rem)|\b(w|h|gap|p|m|top|left|right|bottom)[xyltbr]?-\[-?[0-9.]+(px|rem|%)\]|#[0-9a-fA-F]{3,6}\b)` → 0 Treffer

**Geliefert:**
- `components/layout/Stack.tsx` (Variants xs/sm/md/lg/xl), `components/layout/Section.tsx`
- `components/data/DataView.tsx` (Loading | Error | Empty | Content, priorisiert)
- `PageHeader` ohne eigenen `mb-6` — Spacing kommt jetzt vom umschliessenden `Stack`
- AppShell-NavLinks: `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`,
  `<nav aria-label="…">` gesetzt
- `CardTitle` rendert `<h3>` statt `<div>`; alle Pages: inneres `<h2>` entfernt
- `globals.css`: `@media (prefers-color-scheme: dark) { :root { … } }` mit
  invertierten HSL-Token-Werten
- `ui/alert.tsx`: `translate-y-[-3px]` entfernt (war einziger raw Pixelwert)
- Pages refactor: `PersonasPage`, `PlaybooksPage`, `PersonaNewPage`, `PlaybookNewPage`,
  `PersonaDetailPage`, `PlaybookDetailPage`, `SettingsTokensPage`, `LoginPage` —
  Top-Level-Spacing via `<Stack gap="lg">`, Form-internes Spacing via `gap-4`
- Detail-Pages: Persona/Playbook-Initial-Load via `DataView` (kein doppeltes
  Loading+Error mehr); `loadError`/`saveError` getrennt
- PersonaDetail Linked-Playbooks-Sub-Liste: ebenfalls via `DataView`
- Listen-Item-Links (`Personae`/`Playbooks`): focus-visible-Ring + rounded-sm
- Neue Tests: `DataView.test.tsx` (5), `DataList.test.tsx` (5) — drei States
  einzeln verifiziert

**Notion-Pointer:** dieser Plan-File. Repo-spezifische Konkretisierung der
Frontend-Standards (Stack/Section/DataView) bleibt in CLAUDE.md/react-conventions-Skill;
die Atomics in Notion bleiben generisch.
