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
