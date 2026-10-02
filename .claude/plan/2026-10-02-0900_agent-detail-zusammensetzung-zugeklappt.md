# Agent-Detail unter md: Karte „Zusammensetzung“ zugeklappt

Karte: t_cdb18cd8 · Status: in Arbeit · Basis: origin/main d0c357eb
Spec (verbindlich): Designer-Delta `agent-detail-mobil-hierarchie-2026-10.md`
(Karte t_42bff43b, Option a), Mobil-Spec M2 (Tab-Oberkante ≤ 1,2 bei 320,
≤ 0,9 bei 390).

## Completion-Condition

- Unter md ist die Karte beim Laden zu: ein `<button>` (≥ 44 px) mit
  „Zusammensetzung“ + „Persona · n Playbooks“, `aria-expanded`/`aria-controls`.
  Zugeklappter Inhalt trägt `hidden` (nicht im Tab-Fluss, nicht im A11y-Tree).
- Aufgeklappt Inhalt wie nach P7 (4 + 8, Live-Meldung, Fokus-Sprung).
- Ab md unverändert (kein Knopf, Überschrift wie heute).
- Gemessen im echten Stack (Chromium): 320 ≤ 1,2, 390 ≤ 0,9.
- Web-DoD (CONTRIBUTING.md) unter Node 22 grün, `i18n:check` grün.

## Vorentschiedene Weichen (aus der Spec)

- Startzustand nicht persistiert, State bleibt in der Komponente (Zahl der
  angezeigten Playbooks überlebt Zu-/Aufklappen).
- `hidden` statt Nicht-Rendern: `aria-controls` zeigt dann immer auf ein
  vorhandenes Element; Tailwind-Preflight setzt `[hidden]` mit `!important`
  auf `display: none`, die `flex`-Klasse überstimmt es also nicht.
- Keine Transition am Knopf, Chevron wird getauscht, nicht gedreht.
- Neue i18n-Schlüssel unter `agents.hierarchy.*` laut Spec §5, dazu
  `playbooksLinked_one`.

## Schritte

1. Ausgangsmessung im Stack (Skript im coder-Scratch `tcdb/shots.mjs`).
2. `AgentHierarchyView.tsx`: Disclosure unter md.
3. `de.json`/`en.json`: Schlüssel aus Spec §5.
4. Tests: Startzustand zu, Umschalten, ARIA, Zusammenfassung alle Zeilen aus
   §3.3 (DE + EN), kein Knopf ab md; M9-Suite klappt zuerst auf. Rot-Probe je
   Zusicherung.
5. e2e-mobile: Tab-Oberkante der Agent-Seite als Zusicherung.
6. Messung nachher, Screenshots 320/390 hell/dunkel.
7. Changelog-Fragment, DoD, PR.

## Messung

Echter Stack (Compose + Vite-Dev auf dem Arbeitsbaum), Chromium, Seed-Agent
mit Persona, System-Prompt und 14 Playbooks, nicht verwaltet, hell, de.
Skript: coder-Scratch `tcdb/shots.mjs`.

| Viewport | vorher | nachher (zu) | aufgeklappt |
|---|---|---|---|
| 320 × 568 | 1,80 (Karte 580 px) | **0,90** (Karte 66 px, Schalter 64 px) | 1,82 |
| 390 × 844 | 1,15 | **0,54** | 1,16 |
| 430 × 932 | 1,02 | 0,49 | 1,03 |
| 1440 × 900 | Tabs 1064 px, Karte 770 px | unverändert | – |

Hell und dunkel identisch. 1440: Pixel-Diff nur in der Playbook-Liste
(Reihenfolge der Seed-Playbooks gleicher Version wechselt zwischen zwei
Ladevorgängen), Layout und Maße gleich.

## Abweichung von der Spec

- §3.1 sieht einen nativen `<button>` vor. Die ESLint-Regel des Repos
  verbietet ihn („Verwende <Button>“). Umgesetzt mit `<Button variant="ghost">`
  und denselben Overrides wie der Zeilen-Schalter in `TestResultsPanel`, dazu
  `transition-none` gegen die Farb-Transition der Button-Basis (Spec §4).
- Zusammenfassungszeile bleibt auch aufgeklappt einzeilig (`truncate`).
  Spec-Abnahme 5 („Ellipse nur zugeklappt“) und §3.1 („Knopf ändert beim
  Umschalten seine Größe nicht“) widersprechen sich bei langen Namen; der
  erste Wurf mit Umbruch ließ den Schalter auf 84 px springen. §3.1 gewinnt,
  weil der volle Name aufgeklappt direkt darunter steht.

## Status

Umgesetzt; Ergebnisse im PR.
