# Agents-Übersicht: Offene Gedächtniseinträge sichtbar machen

_Erstellt: 2026-07-24 16:23 · Branch: `claude/autonomous-code-agent-role-fn8oz1` · Status: Umsetzung_

## Ziel (/goal)

**Outcome:** In der Agenten-Übersicht (`/agents`) ist pro Agent sichtbar, ob und
wie viele Gedächtnis-Vorschläge (`agent_memory.status='pending'`, ADR-0044) auf
Freigabe warten. Ein Klick auf den Hinweis führt direkt zur Gedächtnis-Sektion
des Agenten, die beim Deep-Link sichtbar hervorgehoben wird.

**Messbare Completion-Condition:**
1. `GET /v1/workspaces/{ws}/agents` liefert pro Agent `pending_memory_count`
   (nur pending, workspace-korrekt, ein Batch-Roundtrip — kein N+1); durch
   Test belegt.
2. AgentsPage rendert bei `pending_memory_count > 0` einen Aufmerksamkeits-Pill
   mit Zähler, der auf `/agents/{id}#memory` verlinkt; bei 0 kein Pill; durch
   Test belegt.
3. AgentDetailPage scrollt bei Hash `#memory` zur Gedächtnis-Sektion und hebt
   sie visuell hervor (Triage-Block trägt bereits Zähler-Badge); durch Test
   belegt.
4. DoD beider Stacks grün: `ruff check`, `mypy`, `pytest --cov
   --cov-fail-under=85`; `npm run lint`, `npx tsc --noEmit`,
   `npm run test:coverage`, `npm run build`.

**Constraints/Leitplanken:** Kein neuer Endpoint (List-Enrichment-Muster wie
`playbook_count`); keine `HTTPException`/SQL in Services; UI nur über
`@/components/ui/*`-Primitives + Tokens (keine Hex/px); i18n de+en;
Feature-Branch + PR, kein Push auf main.

**Out of Scope:** Dashboard-KPI (existiert seit Plan 2026-07-22-1650 und
verlinkt bereits auf `/agents` — Ziel-Seite wird durch diesen Plan informativ);
MCP-Tools; Sortierung/Filter der Agenten-Liste nach pending-Memories.

## Kontext (gelesen)

- List-Enrichment: `AgentService._enrich` joint `AgentListMeta` aus
  `PgAgentRepository.list_meta` (Batch-Aggregat `= ANY($2)`,
  `apps/api/src/who2be_api/repositories/agent_repository.py:313`).
- `agent_memory` trägt `workspace_id` + `agent_id` + `status` (Migration 0066);
  Dashboard zählt pending bereits workspace-weit
  (`dashboard_repository.py::_ATTENTION_COUNTS`).
- UI: `EntityCard` (Stretched-Link; interaktive Kinder brauchen
  `relative z-10`), `MetaPill` (Ton `destructive` existiert als Warn-Muster),
  `AgentMemorySection` zeigt Triage-Block + `memory.pendingBadge`.

## Design-Entscheidung (dokumentiert, kein Blocker)

Anzeige als **klickbarer Aufmerksamkeits-Pill in der Meta-Zeile der Karte**
(Brain-Icon + „N zur Freigabe", Ton analog Warn-Muster) statt (a) eigener
Filter-Chip-Kategorie oder (b) Umsortierung der Liste. Begründung: minimal-
invasiv, folgt dem bestehenden Karten-Vokabular (`MetaPill`), und der
User-Wunsch ist explizit „Highlight am Agenten + Klick zur Übersicht". Filter/
Sortierung wären zusätzliche Konzepte ohne Anforderungsdeckung.

Deep-Link als **URL-Hash `#memory`** (kein Query-Param): Hash ist das
natürliche Vokabular für „scrolle zu Sektion", kollidiert nicht mit künftigen
List-Filter-Query-Params und ist reload-stabil.

## Arbeitspakete (klein — direkte Abarbeitung, keine Sub-Agents)

### WP1 — Backend: `pending_memory_count` im List-Endpoint
- [x] `packages/models/.../agent.py`: `AgentRead.pending_memory_count: int = 0`
      (List-Enrichment-Kommentar ergänzen).
- [x] `agent_repository.py`: `AgentListMeta.pending_memory_count`; `list_meta`-
      SQL um LEFT-JOIN-Aggregat auf `agent_memory` (`status='pending'`,
      `GROUP BY agent_id`) erweitern.
- [x] `agent_service.py::_enrich`: Feld mappen.
- [x] Tests: `test_list_enrichment.py` (Agent mit 2 pending + 1 active + 1
      rejected → Count 2; Agent ohne Memories → 0); Fake-Repos in
      `test_agent_read_gate.py` nachziehen.

### WP2 — Web: Pill in der Agenten-Übersicht
- [x] `api/types.ts`: `pending_memory_count?: number` am `Agent`.
- [x] `AgentsPage.tsx`: bei Count > 0 klickbaren Pill (Brain, Warn-/Brand-Ton,
      `relative z-10`-Link über dem Stretched-Link) → `#memory`-Deep-Link.
- [x] i18n de/en: `card.pendingMemories_one/_other` (+ aria).
- [x] Tests: Pill sichtbar mit Zähler + korrektem href; kein Pill bei 0.

### WP3 — Web: Deep-Link-Highlight in der Detail-Seite
- [x] `AgentMemorySection.tsx`: `id="memory"`; bei `location.hash === '#memory'`
      nach dem Laden `scrollIntoView` + Highlight-Ring (Token-basiert,
      zeitlich begrenzt via Motion-Token).
- [x] Tests: Hash → Sektion erhält Highlight-Klasse/scrollIntoView aufgerufen.

### WP4 — Konsolidierung + Doku
- [x] Beide Stacks: volle DoD-Gates lokal (Ergebnisse im PR dokumentiert).
- [x] STATE.md aktualisieren; PR geöffnet (Change-Log + Pointer auf diesen Plan).

## Verlauf

- 2026-07-24 16:23 — Plan angelegt, Umsetzung gestartet.
- 2026-07-24 16:40 — WP1–WP3 umgesetzt und verifiziert. DoD beider Stacks grün:
  Python ruff/format/mypy ohne Befund, pytest 1100 passed, Coverage 90,57 %
  (Gate 85); Web eslint 0 Errors, tsc grün, Vitest 920 passed (165 Dateien),
  Branches 81,18 % (Floor 79), Build grün. PR folgt.
