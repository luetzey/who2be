# Mobil P5: Textfelder wachsen mit statt innen zu scrollen (Spec M5)

Karte t_752ce6e5 · Spec `/home/luetzey/recherche/mobile-spec-2026-09-29.md` §M5, §3 P5.
Basis: origin/main 5fa0cf81 (P3 #727 gemergt).

## Ziel / Completion-Condition

- Mit Seed-Daten hat keine Textarea `scrollHeight > clientHeight`, solange der
  Inhalt < 60 svh ist (vorher: Agent-Beschreibung 16,4×, Feedback-Notiz 8,5×,
  Tool-Fallback 4,8× bei 320 px). Gemessen im Browser gegen das gebaute
  Stylesheet bei 320/390/430 px.
- Der Fallback (`useAutoGrow`) greift nur ohne `CSS.supports('field-sizing','content')`;
  beide Pfade getestet (Vitest + Playwright mit erzwungenem Fallback).
- Fokus springt beim Wachsen nicht (E2E: Tippen im Feld, Fokus bleibt, Feld
  bleibt im Viewport).
- lint, tsc, i18n:check, test:coverage, build, license:check grün; Rot-Probe.

## Schnitt (Acht-Datei-Deckel)

- **PR A — Basis-Textarea** (8 Dateien): `components/ui/textarea.tsx`,
  neu `hooks/useAutoGrow.ts`, `components/ui/textarea.test.tsx` (Textarea +
  Hook, beide Pfade), `components/data/TokenSecretReveal.tsx`,
  `components/data/McpConfigCopy.tsx` (Opt-out `autoGrow={false}`),
  `e2e/scroll-guard.spec.ts`, Changelog-Fragment, dieser Plan.
- **PR B — Agent-Editor, Viewer-Ansicht** (3 Dateien, eigener Branch von
  origin/main, unabhängig von PR A): `AgentEditorForm.tsx` (nur lesend:
  `ExpandableText` mit 6 Zeilen statt gesperrter Textarea),
  `AgentEditorForm.test.tsx`, Changelog-Fragment.

## Schritte

1. [x] Vorher-Messung auf origin/main (eigener Stack `w2bd752`, Ports 56xxx).
2. [x] `Textarea`: Standard `field-sizing-content max-h-[60svh]`, `min-h-20`
   bleibt; `rows` bleibt Mindesthöhe (inline `min-height: max(5rem, calc(<rows>lh + 1rem + 2px))`,
   weil `field-sizing: content` `rows` sonst ignoriert). Prop `autoGrow` (Standard `true`).
3. [x] `useAutoGrow(ref, enabled, value)`: nur wenn
   `!CSS.supports('field-sizing','content')`; setzt `height = scrollHeight + Rahmen`
   bei `input`, Wertänderung und Breitenänderung (ResizeObserver); stellt die
   Scrollposition von Fenster und gescrollten Vorfahren wieder her, falls das
   kurze `height:auto` die Seite verschoben hat.
4. [x] Opt-out in `TokenSecretReveal` und `McpConfigCopy`.
5. [x] Tests + Rot-Probe; E2E in `scroll-guard.spec.ts` (native + fallback).
6. [ ] PR B: Viewer-Ansicht im Agent-Editor.
7. [x] Nachher-Messung, Screenshots hell/dunkel, DoD, PR A.

## Messung (Stack `w2bd752`, gebautes Stylesheet, Seed aus P3)

Tiefe = `scrollHeight / clientHeight`; 60 svh = 340 / 506 / 559 px.

| Feld | Breite | vorher | nachher | Inhalt < 60 svh? |
|---|---|---|---|---|
| Agent-Beschreibung (1.276 px Inhalt bei 320) | 320 | 78 px, 16,36× | 339 px, 3,76× | nein → Obergrenze greift |
| | 390 | 78 px, 11,74× | 504 px, 1,82× | nein |
| | 430 | 78 px, 9,95× | 557 px, 1,39× | nein |
| Tool-Fallback-Hinweis | 320 | 78 px, 4,82× | 339 px, 1,11× | nein (376 px) |
| | 390 | 78 px, 3,28× | 256 px, 1,00× | ja → kein innerer Scroll |
| | 430 | 78 px, 2,77× | 216 px, 1,00× | ja → kein innerer Scroll |
| Feedback-Notiz (Dialog) | 320 | 96 px, 8,50× | 339 px, 2,41× | nein |
| | 390 | 96 px, 6,00× | 504 px, 1,14× | nein |
| | 430 | 96 px, 5,17× | 496 px, 1,00× | ja → kein innerer Scroll |

Kein Feld mit Inhalt < 60 svh scrollt innen, in beiden Pfaden (nativ und
Fallback, gleiche Werte). Fallback belegt über `style.height` gesetzt
(z. B. 258 px), nativ ohne Inline-Höhe.

## Rot-Probe

`field-sizing-content` aus `textarea.tsx` entfernt und `useAutoGrow` auf No-op:
Vitest 7 rot (Klassenvertrag + 6 Fallback-Fälle), E2E `mobile-320` beide rot
(native: „innerer Scroll trotz Inhalt < 60 svh", 216 > 79; fallback: keine
Inline-Höhe). Zurückgebaut, danach 24/24 grün.
