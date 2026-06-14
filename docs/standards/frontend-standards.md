# Frontend-Standards

Die **verbindliche und vollständige** Quelle für die Web-UI ist
[`../frontend/design-language.md`](../frontend/design-language.md) (Token-Werte,
Komponenten-Muster, Motion, A11y, AI-Agenten-Vertrag). Diese Datei fasst nur die
tragenden Prinzipien zusammen und verlinkt — sie ist **kein** zweiter Standard.

Weitere repo-spezifische Quellen: [`../../CLAUDE.md`](../../CLAUDE.md)
§Frontend-Standards, Skill `.claude/skills/react-conventions`,
[`../frontend/architecture.md`](../frontend/architecture.md), ADR-0014–0018.

## Tragende Prinzipien

- **Single-Source pro Entscheidung** (eine Quelle pro Farbe/Token/Pattern).
- **Design-Tokens** statt `#hex`-/`px`-Literale im JSX
  (`apps/web/src/styles/globals.css`, Tailwind v4 `@theme inline`).
- **Komponenten-Bibliothek:** shadcn-Primitives unter `@/components/ui/*` —
  keine rohen `<button>/<input>/<textarea>/<a>` in Features/Layout/Data
  (ESLint-error).
- **Layout-Primitives** (`AppShell`, `PageHeader`, `Container`, `Section`, `Stack`).
- **Fünfschichtige UI-Architektur** + Feature-Ordnerbaum
  (`features/<domain>/{pages,components,...}`); keine Cross-Feature-Deep-Imports.
- **UX-Kohärenz** und **A11y-Minimum** (Focus-Ring, `*.a11y.test.tsx`, ADR-0016).
- **Keine Utility-Suppe** — Komponenten + Tokens statt Ad-hoc-Klassen.

## DoD (Frontend)

`npm run lint && npx tsc --noEmit && npm test && npm run build` — alle grün,
lokal verifiziert vor jedem Push.
