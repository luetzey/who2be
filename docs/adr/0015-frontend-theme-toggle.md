# ADR-0015 — Frontend-Theme: Header-Toggle (light / dark / system) mit localStorage

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), Frontend-Umbau Phase 0

## Kontext

Der Dark-Mode wird heute ausschliesslich ueber `@media (prefers-color-scheme: dark)`
geschaltet — Nutzer:innen koennen das Theme nicht ueberschreiben. Standard-
shadcn-Pattern ist ein Header-Toggle mit drei Optionen (light, dark,
system), persistiert in `localStorage`. Das Frontend-Standards-Playbook
verlangt keinen Toggle explizit, aber Standard 6 ("UX-Kohaerenz") und
das Interaktions-Feedback durch Primitives sprechen dafuer, Theme als
First-Class-Setting im App-Shell zu fuehren.

## Optionen

- **A — Nur OS-prefers-color-scheme (IST).** Null Komplexitaet, kein
  Override fuer User:innen. Setzt einen passenden Default, aber kein
  User-Choice; bei Light-Mode-Maschinen mit Dark-Praeferenz Reibung.
- **B — Header-Toggle light/dark/system mit localStorage, Default `system`.**
  Standard-Pattern. Kostet 1 `ThemeProvider` + 1 `<ThemeToggle/>`-
  Primitive. `data-theme="light|dark"`-Attribut auf `<html>` ueberlagert
  die `prefers-color-scheme`-Tokens.
- **C — Flag-gated Toggle.** Toggle nur hinter Config-Flag aktiv.
  Sinnvoll erst bei Multi-Tenant; fuer Phase 0 Overkill.

## Entscheidung

**Option B — Header-Toggle (light / dark / system) mit localStorage,
Default `system`.**

Umsetzung in Phase 6:

- `apps/web/src/app/ThemeProvider.tsx`: liest `localStorage.theme`
  (`'light' | 'dark' | 'system'`, Default `'system'`), schreibt
  `data-theme="light"` bzw. `data-theme="dark"` auf `<html>` (oder
  loescht es bei `'system'`, dann greift `prefers-color-scheme`).
- `apps/web/src/components/ui/theme-toggle.tsx`: shadcn-typisches
  DropdownMenu mit drei Items + Icons; aria-Label `'Theme umschalten'`.
- `apps/web/src/components/layout/AppShell.tsx`: Slot im Header neben
  dem Sign-Out-Button.
- `apps/web/src/styles/globals.css`: Dark-Tokens zusaetzlich an
  `:root[data-theme="dark"]` (neben `prefers-color-scheme`), damit der
  Toggle die OS-Praeferenz ueberschreiben kann.

## Konsequenzen

- Drei-Punkt-API: Theme wird an genau einer Stelle gelesen
  (`ThemeProvider`), genau einer Stelle persistiert (`localStorage`) und
  genau einer Stelle geschaltet (`data-theme`-Attribut). Bricht Standard
  1 nicht.
- `localStorage` enthaelt nur den Theme-Choice (keine Tokens, keine
  Geheimnisse) — DSGVO-neutral.
- Default `'system'` bewahrt das heutige Verhalten fuer alle, die nicht
  toggeln. Kein Verhaltens-Regress.
- Bei Migrations-Schmerz (z.B. QA-Block) kann der Toggle hinter
  `import.meta.env.DEV` versteckt werden, ohne dass der Provider
  ausgebaut werden muss.
