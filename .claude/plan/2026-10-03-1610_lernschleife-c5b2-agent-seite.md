# Lernschleife C5b-2 (Web): Agent-Seite auf gemeinsame Gedächtnis-Liste

Status: aktiv · Karte t_7fbb5c2b · Basis origin/main 8adad2df (C5b-1 #803 gemergt)
Spec: gedaechtnisverwaltung-design-spec-2026-10.md §6.6, §11.2, §13.4, §16 (C5b)

## Outcome
Die Agent-Seite zeigt an der Stelle der alten Gedächtnis-Karte die gemeinsame
`MemoryList` mit fest gesetztem Agenten (GET /memories?scope=agent&agent_id=…).
`AgentMemorySection` und `useAgentMemories` entfallen samt Tests und
verwaister i18n-Schlüssel.

## Entscheidungen (aus Spec/Repo belegt)
- Filterzustand der Karte lokal (React-State), nicht in der URL: die Agent-Seite
  hat keine Such-Parameter; „In der Gedächtnisverwaltung öffnen“ übergibt die
  gesetzten Filter an `/memory?tab=entries&agent=<id>&…` (§6.6).
- Kein Facetten-Spalte auf der Karte: Spec-Wireframe §6.6 zeigt nur
  [Suche] [Filter (n)] [Sortierung] → `FilterSheetButton` mit `alwaysButton`.
- Viewer: Karte wird nicht gerendert. Agentengedächtnis ist ab editor sichtbar
  (Server `_visibility`, C5a), keine toten Knöpfe.
- Gedächtnis aus (`tool_policy.memory_mode` = off/fehlt): AttentionBanner brand,
  Liste darunter nur lesend (`readOnly`: keine Checkbox, keine Zeilen-/Stapel-
  aktion); ohne Einträge nur der Banner.
- Füllstand aus `counts` (group_by=kind): Einträge ohne Agentennotizen gegen
  MEMORY_MAX_PER_AGENT=500, Notizen gegen MEMORY_MAX_NOTES_PER_AGENT=200
  (packages/models/.../memory.py), „fast voll“ ab 90 %.
- „Alle löschen“ im Overflow-Menü (DropdownMenu), Dialog mit Anzahl,
  DELETE /agents/{id}/memories.
- Deep-Link `#memory` (Pill der Agentenübersicht) bleibt: Karte trägt id und
  Hervorhebung wie bisher.

## Dateien (Zählregel: alle außer Plan, Grenze 12)
1. features/agents/components/AgentMemoryCard.tsx (neu)
2. features/agents/components/AgentMemoryCard.test.tsx (neu)
3. features/agents/pages/AgentDetailPage.tsx
4. features/agents/components/AgentMemorySection.tsx (gelöscht)
5. features/agents/components/AgentMemorySection.test.tsx (gelöscht)
6. features/agents/components/AgentMemorySection.responsive.test.tsx (gelöscht)
7. features/agents/hooks/useAgentMemories.ts (gelöscht)
8. components/memory/MemoryList.tsx (fixedAgentId, readOnly, emptyState)
9. components/memory/MemoryFacets.tsx (FilterSheetButton auch ab lg)
10. i18n/locales/de.json
11. i18n/locales/en.json
12. changelog.d/t-7fbb5c2b-agent-memory-list.changed.md

## Verifikation
- Node 22 (mise): lint, tsc -b, test:coverage, build, license:check, i18n:check
- Rot-Proben: agent_id fest im Request; keine Agent-Facette; Viewer ohne Karte;
  readOnly ohne Aktionen.
- Screenshots 1280/390 hell+dunkel mit scrollWidth<=clientWidth (Scratch-Spec,
  nicht committet); e2e scroll-guard agents/:id lokal.

## Fortschritt
- [ ] Umsetzung  - [ ] Tests  - [ ] DoD  - [ ] Screenshots  - [ ] PR
