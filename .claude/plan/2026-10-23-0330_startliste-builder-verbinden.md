# Plan t_84aef25e — Startliste „Builder verbinden“ + Verbinden-Karte mobil (UX-Audit B1+B3)

Stand: origin/main 98adac59. Modus: produktiv (kein `mode` in .claude/project.json).

## Ziel / Completion-Condition
- Startliste: der offene Schritt vom Typ `first_mcp_call` hat den Knopf „Builder verbinden“
  auf `/w/<ws>/agents/<builder-id>#connect`. Builder = verwalteter Agent (`is_managed`),
  bevorzugt aktiv. Kein Builder oder Laden gescheitert → Rückfall „Zu den Agents“ auf `/agents`.
- Agent-Seite: `#connect` → Tab Überblick, die Karte „Verbindung“ wird angesprungen
  (scrollIntoView, Fokus auf die Kartenüberschrift).
- Unter `md`: Kopf-Aktionen hinter „…“ (`collapseActionsBelowMd`), ab `md` unverändert.
- Belege: Vitest Ziel-Route + Rückfall + Anker (mit Rot-Proben), Fotos 1280/390/320 hell+dunkel,
  measure.json, DoD Web, e2e-mobile in der CI.

## Messung vorher (Vite-Dev, gemockte API, `.shots/t_84aef25e/measure-vorher.json`)
Unterkante „Mit Claude verbinden“ bei direktem Aufruf: 1280 → 756, 390 → 1170, 320 → 1397.
Probe nur Einklappen: 390 → 1086, 320 → 1245. Einklappen allein reicht also nicht für 844 px.
Probe zusätzlich Hinweis „Vom System verwaltet“ unter md ausgeblendet: 390 → 890, 320 → 1004,
reicht ebenfalls nicht (und wäre ein Eingriff außerhalb des Umfangs). Die 844 px werden über
den Sprung aus der Startliste erreicht (Karte oben im Viewport). Der direkte Aufruf ohne Anker
verbessert sich um 84/152 px. Die Restlücke steckt in der Karte selbst (Programmwahl,
3 Schritte und Test-Satz vor dem Knopf). Sie wird im Handoff als Weiche gemeldet, weil
t_87ec1e7f die Karte ohnehin umbaut (Raster 2×3).

## Entscheidungen
- Muster: keine neue Abstraktion. Anker-Sprung wie `#memory`/`#delegations` (ANCHOR_TABS um
  `#connect` → overview, keepHash) plus ein kleiner Effekt in AgentDetailPage. Builder-Suche als
  lokaler Hook in TutorialChecklist (gleiche Regel wie `useBuilder` im WelcomeDialog). Kein
  Zusammenlegen, weil das eine 9. Datei wäre und der Dialog zusätzlich `activatable` verlangt.
- Anker-Konstante `AGENT_CONNECT_HASH` in `lib/installLinks.ts` (dort liegt alles zum Verbinden,
  das Dashboard lädt das Modul über den WelcomeDialog schon). Nicht in AgentConnectorSection,
  sonst landet der Baustein im Dashboard-Chunk.
- Agents/Agenten-Begriff: Out of Scope, der Rückfalltext bleibt „Zu den Agents“.

## Dateien (8)
1. apps/web/src/features/help/components/TutorialChecklist.tsx
2. apps/web/src/features/help/components/TutorialChecklist.test.tsx
3. apps/web/src/features/agents/pages/AgentDetailPage.tsx
4. apps/web/src/features/agents/pages/AgentDetailPage.test.tsx
5. apps/web/src/lib/installLinks.ts
6. apps/web/src/i18n/locales/de.json
7. apps/web/src/i18n/locales/en.json
8. changelog.d/startliste-builder-verbinden.changed.md

## Schritte
1. [x] installLinks: `AGENT_CONNECT_HASH`
2. [x] TutorialChecklist: useBuilderId + Knopf, i18n `checklist.connectBuilder`
3. [x] AgentDetailPage: collapseActionsBelowMd, `#connect` in ANCHOR_TABS, Sprung-Effekt
4. [x] Tests + Rot-Proben (Builder-Zweig aus → 1 rot; Hash-Bedingung falsch/entfernt → je 1 rot)
5. [x] Fotos/measure, DoD Web, Changelog, PR

## Ergebnis (measure-nachher.json)
- Sprung aus der Startliste: Karte oben (cardTop 16 mobil, 169 bei 1280), Knopf-Unterkante
  im Viewport 1280 → 514, 390 → 555, 320 → 621 (alle < 844), Fokus auf „Verbindung“.
- Direkter Aufruf ohne Anker: 390 → 1086 (vorher 1170), 320 → 1245 (vorher 1397).
- Kein Overflow: scrollWidth == clientWidth in allen 30 Messungen, keine pageerrors.
