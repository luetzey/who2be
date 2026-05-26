# apps/web

React/TypeScript-Web-UI fuer Who2Be (Vite).

## Befehle

```bash
npm ci         # Dependencies
npm run dev    # Dev-Server
npm test       # Tests (vitest)
npm run lint   # ESLint
npm run build  # Production-Build
```

## UI-Konventionen

Stack: Tailwind v4 + shadcn-aequivalente Primitives in `src/components/ui/`,
vertikal geschnittene Features in `src/features/<domain>/` mit `pages/` und
`components/`, geteilte Layout-/Data-Bausteine in `src/components/`.
Design-Tokens nur in `src/styles/globals.css`.

ESLint erzwingt die wichtigsten Regeln (kein direkter `<button>`/`<input>`/
`<a>` in Feature-Code, keine Cross-Feature-Deep-Imports). Die vollstaendigen
Konventionen stehen im Skill `.claude/skills/react-conventions/SKILL.md`;
der Ursprungsplan unter
`.claude/plan/2026-05-26-1530_web-ui-design-system-tailwind-shadcn.md`.
