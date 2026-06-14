# Phase 6 — Theme-Toggle + OKLCH (M-FE-6)

Branch: `feat/frontend-phase-6`. Vorgaenger: Phase 5 (gemerged). Bezug:
Approved-Plan-Datei `2026-05-26-1530_web-ui-design-system-tailwind-shadcn.md`
sowie ADRs 0014 (OKLCH) und 0015 (Theme-Toggle).

## Ziel

- Color-Tokens in `apps/web/src/styles/globals.css` von HSL-Channel auf
  OKLCH umgestellt (Single Source of Truth, ADR 0014).
- `ThemeProvider` setzt `data-theme` auf `<html>`, Praeferenz
  `'light' | 'dark' | 'system'` in `localStorage` (Default `system`).
- `<ThemeToggle/>` (Dropdown-Menu mit Sun/Moon/Monitor) im AppShell-Header
  rechts neben „Abmelden".
- Dark-Tokens zusaetzlich an `:root[data-theme="dark"]` neben dem
  bestehenden `@media (prefers-color-scheme: dark)`-Block.

## Tasks (sequenziell)

- 6.1 globals.css — alle `--*`-Color-Tokens auf `oklch(...)`-Literale; die
  `@theme inline`-Aliase verlieren den `hsl(...)`-Wrapper.
- 6.2 `apps/web/src/app/ThemeProvider.tsx` (+ Test) — Context
  `{ preference, setPreference, resolved }`, Default `system`, persistiert
  in `localStorage` Key `who2be:theme`, reagiert auf
  `prefers-color-scheme`-Aenderungen wenn `preference === 'system'`. In
  `AppLayout` einhaengen.
- 6.3 `apps/web/src/components/ui/theme-toggle.tsx` (+ Test) —
  shadcn-Dropdown mit drei Items; consumes `useTheme()`. AppShell-Header
  bekommt Toggle vor dem Logout-Button.
- 6.4 globals.css — `:root[data-theme="dark"]` mit identischen Werten wie
  die Media-Query; explizite Praeferenz uebersteuert dann das System.

## Verifikation

- `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` alle gruen.
- Tests: ThemeProvider setzt `data-theme`, persistiert, reagiert auf
  System-Preference; ThemeToggle wechselt Praeferenz und Context-Wert.
- Manueller Side-by-Side Light/Dark vor und nach OKLCH-Konvertierung —
  keine sichtbare Regression (Token-Wahrnehmung bleibt nahe).
- `grep "hsl(var(--" apps/web/src/styles/globals.css` → leer.

## Out of Scope

- Visual-Regression-Tests (Playwright) — bleibt fuer spaeter (siehe ADR 0016
  Begruendung).
- Theme-Vorschau im Catalog — Phase 7.
