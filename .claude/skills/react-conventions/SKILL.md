---
name: react-conventions
description: Code-, Komponenten- und Test-Konventionen fuer die React/TypeScript-Web-UI von Who2Be.
---

- Funktionale Komponenten + Hooks; Props typisiert; geteilte Logik in Custom Hooks.
- Server- und Client-State trennen; TS strict (`tsc --noEmit` fehlerfrei).
- MVP-Web-UI: Login, Liste, simpler Detail-Editor — Funktion vor Schoenheit.
- Tests (jest/vitest): Verhalten testen, nicht Implementierung; bei Bugfixes erst
  reproduzierender Test.
- Auth-Tokens nicht im localStorage halten; API-Base-URL ueber Env (`VITE_`).
- DoD: Tests gruen, lint ohne Findings, tsc fehlerfrei.

## Design-System (geplant, noch nicht umgesetzt)

Ziel-Stack: Tailwind v4 + shadcn/ui, vertikal geschnittene `features/<domain>/`,
Primitives in `components/ui/`. Plan:
`.claude/plan/2026-05-26-1530_web-ui-design-system-tailwind-shadcn.md`.

Bis zur Umsetzung gilt: **kein paralleles UI-System einfuehren** — keine neuen
CSS-Dateien, kein Mantine/MUI/Chakra, kein Inline-`style=`-Wildwuchs. Neue
Seiten weiter mit semantischem HTML wie bisher; visuelles Polish kommt mit
der Migration. Wer das Design-System umsetzt, aktualisiert _diesen_ Skill um
die finalen Regeln (Imports nur ueber `@/components/ui/*`, Tokens nur in
`styles/globals.css`, Cross-Feature-Imports verboten).
