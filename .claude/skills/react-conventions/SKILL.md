---
name: react-conventions
description: Code-, Komponenten- und Test-Konventionen fuer die React/TypeScript-Web-UI von Who2Be.
---

- Funktionale Komponenten + Hooks; Props typisiert; geteilte Logik in Custom Hooks.
- Server- und Client-State trennen; TS strict (`tsc --noEmit` fehlerfrei).
- Tests (vitest): Verhalten testen, nicht Implementierung; bei Bugfixes erst
  reproduzierender Test. Bei UI-Refactors `data-testid` setzen, statt Tests
  auf DOM-Struktur umzuschreiben.
- Auth-Tokens nicht im localStorage halten; API-Base-URL ueber Env (`VITE_`).
- DoD: `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` — alle
  gruen, lokal verifiziert vor jedem Push.

## Design-System (Pflicht)

Stack: Tailwind v4 + shadcn-aequivalente Primitives. Migration ist umgesetzt
(Plan: `.claude/plan/2026-05-26-1530_web-ui-design-system-tailwind-shadcn.md`).
ESLint erzwingt die wichtigsten Regeln — Verstoesse brechen den Build.

### Imports & Primitives

- Buttons, Inputs, Textareas, Forms, Dialoge, Dropdowns nur via
  `@/components/ui/*` — direkter `<button>`, `<input>`, `<textarea>` ist im
  Feature-Code ESLint-Error.
- Links nur via `<Link>` aus `react-router-dom` (ggf.
  `<Button asChild><Link/></Button>`); blanker `<a>` ist Error.
- Neue UI-Primitives kommen via `npx shadcn add <component>` (oder von Hand
  nach gleichem Muster: `cva` fuer Varianten, `cn` fuer Klassen-Merge,
  Radix-Slot fuer Polymorphie). Keine handgerollten Buttons/Inputs neben
  `components/ui/*`.

### Struktur

- Domaenen-Code lebt vertikal in `src/features/<domain>/` mit Unter-Ordnern
  `pages/`, `components/`, optional `hooks/`, `lib/`. Pro Feature ein
  `index.ts`-Barrel, das **nur Pages** exportiert.
- Routing in `App.tsx` (spaeter `app/routes.tsx`) importiert ausschliesslich
  ueber das Feature-Barrel `@/features/<x>`.
- Cross-Feature-Deep-Imports sind ESLint-Error
  (`@/features/<a>/components/* → features/<b>/...` verboten). Geteiltes
  wandert nach `@/components/` oder `@/hooks/`.
- Globale Layout-Bausteine in `@/components/layout/` (`AppShell`,
  `PageHeader`, `Container`), domaenen-agnostische Daten-UI in
  `@/components/data/` (`DataList`, `EmptyState`, `ErrorAlert`,
  `LoadingState`).

### Styling & Tokens

- Design-Tokens (Farben, Radius, Typo) leben ausschliesslich in
  `src/styles/globals.css` (`:root` + `@theme inline`). Keine `#hex`-Literale,
  keine `px`-Werte im JSX, keine eigenen CSS-Dateien.
- Klassen-Reihenfolge wird via `eslint-plugin-tailwindcss` automatisch
  korrigiert (`classnames-order`, `no-contradicting-classname`).
- Klassen-Merge ueber `cn()` aus `@/lib/utils` (`clsx` + `tailwind-merge`);
  Varianten ueber `class-variance-authority` (`cva`).

### Forms

- Editor-Forms nutzen `react-hook-form` + `zod` + shadcn `Form`-Wrapper
  (`FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormMessage`).
  Kein roher `useState`-Form-State mehr fuer neue Editoren.
