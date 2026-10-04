# Plan: `pending_memory_count` aus GET /agents entfernen

Karte t_23d4c254 (Wurzel t_10e7bfce, Entscheidung t_1ecc3088: (a) entfernen,
Analyse t_6150384b). Schritt 2 von 2: das Web zaehlt den Pill seit #812 ueber
`/memories/counts`; hier faellt das API-Feld weg.

## Warum

`AgentRepository.list_meta` zaehlte `agent_memory WHERE status='pending'` pro
Agent, ohne `kind='lesson'` auszuschliessen. `GET /agents` hat kein
`require_role`, also sahen viewer und agent-gebundene Tokens (MCP
`list_agents`) eine Zahl ueber Agentengedaechtnis, das erst ab editor sichtbar
ist, und lessons zaehlten mit. Das verletzt ADR-0053 6.4.1. Ein 3.1.1-Leak
(fremdes Nutzergedaechtnis) liegt nicht vor: `scope='user'` hat per CHECK
`agent_memory_user_scope_check` immer `agent_id IS NULL`. Es bleibt bei genau
einem Zaehlweg mit einer Sichtbarkeitsregel (`/memories/counts`,
`_memory_where`).

## Schritte

1. Rot-Probe in `test_list_enrichment.py`: viewer und editor, Seed pending
   lesson + pending `scope='agent'`-Fakt; `pending_memory_count` fehlt in jedem
   Listeneintrag, kein Fakt im Antworttext. Gegen alten Code rot belegen.
2. Repository: Subquery und Feld in `AgentListMeta` entfernen.
3. Service `_enrich`: Mapping entfernen.
4. Modell `AgentRead`: Feld + Kommentar entfernen.
5. `docs/reference/openapi.json` per `scripts/export_openapi.py` neu erzeugen.
6. Web: `types.ts`-Feld, Fixtures in `AgentsPage.test.tsx`.
7. Tests anpassen: `test_list_enrichment.py` (alter Zaehler-Abschnitt),
   `test_agent_read_gate.py` (Fake-Meta, Assertions).
8. `changelog.d/agent-pending-memory-count.removed.md`.
9. MCP `list_agents` pruefen (reicht `AgentRead` durch, keine Aenderung).
10. Python-DoD (ruff, format, mypy, pytest mit DB), Web: tsc + betroffene Tests.

## Nicht im Scope

de.json/en.json, ADR-Text (optionaler Satz in 6.4.1 entfaellt, um den PR
schmal zu halten), andere Count-Endpunkte.
