# C4a — Gedaechtnis-Abruf inkl. Nutzergedaechtnis, Push nur bestaetigt (API)

Status: umgesetzt, PR offen · Karte t_889762ed · ADR-0053 C4 (Teil a)
Folgekarte: C4b (t_748b77de, MCP) startet nach dem Merge.

## Ziel (Completion-Condition)

Der Abruf auf Anfrage (`GET /agent-memories/search`, `GET /agent-memories`)
liefert Agentengedaechtnis UND Nutzergedaechtnis des Token-Besitzers, nie
fremdes Nutzergedaechtnis, nie `lesson`; jeder Treffer traegt `kind`, `scope`,
`confirmed`. Der Push in `get_persona` zeigt nur bestaetigte Eintraege (M7 = a).
`POST /agent-memories` dokumentiert 200 mit `merged_into`. Gemessen an:
`apps/api/tests/test_memory_retrieval_scope_api.py` gruen, Rot-Probe je
Zusicherung rot, DoD aus CONTRIBUTING gruen, CI `all-green` auf dem Head.

## Befund (vor der Aenderung, cb8ffa72)

- `memory_repository.py` `search_active`/`list_active`: `agent_id = $2 AND scope = 'agent'`, SELECT nur `id, fact, category`.
- `MemoryHit` ohne `kind`/`scope`/`confirmed`.
- `_bump_retrieval` filtert auf `agent_id` — Nutzereintraege wuerden nie gezaehlt.
- `persona_service._memory_runtime_section` ohne Bestaetigt-Filter.
- `POST /agent-memories` in openapi.json nur mit 201.

## Umsetzung (8 Dateien + Plan)

1. `packages/models/.../memory.py` — `MemoryHit` + `kind`, `scope`, `confirmed` (Pflichtfelder).
2. `memory_repository.py` — ein gemeinsamer Filter `_retrieval_scope(agent_param, user_param)`:
   `status='active' AND kind <> 'lesson' AND ((scope='agent' AND agent_id=$a) OR (scope='user' AND subject_user_id=$u::uuid))`.
   Wird von Suche, Liste UND Nutzungs-Log-Bump genutzt (eine Quelle, kein Drift).
   `user_id=None` heisst: kein Nutzergedaechtnis (`= NULL` ist nie wahr).
   `list_active(..., confirmed_only=True)` fuer den Push. `_HIT_COLUMNS` mit
   `confirmed_at IS NOT NULL AS confirmed`. Vektor-Parameter rueckt auf `$7`.
3. `memory_service.py` — `search`/`list_active` reichen `ctx.user_id` durch.
4. `persona_service.py` — Push mit `user_id=ctx.user_id, confirmed_only=True`.
5. `routers/memory.py` — `responses={200: MemorySaveResult}` am Save-Endpunkt.
6. `docs/reference/openapi.json` — per `scripts/export_openapi.py`.
7. `apps/api/tests/test_memory_retrieval_scope_api.py` — fuenf Tests.
8. `changelog.d/t-889762ed-lernschleife-c4a-abruf-nutzergedaechtnis.changed.md`.

## Vorentschiedene Weichen (belegt)

- Push zeigt auch bestaetigtes Nutzergedaechtnis des Token-Besitzers: Owner-Wortlaut
  „Laufzeit-Push bleibt, zeigt nur bestaetigte Eintraege“; der Push nutzt denselben
  Geltungsbereich wie der Abruf, sonst entstuenden zwei Definitionen von „mein Gedaechtnis“.
- `lesson` zusaetzlich im SQL ausgeschlossen, obwohl der DB-CHECK `active` verbietet:
  Owner-Wortlaut „nie lesson“ als Zusicherung des Abrufs, nicht nur der Datenbank.
  Der Test entfernt den CHECK kurz, um genau diese zweite Linie zu pruefen.
- Rahmung/„unbestaetigt“ im Werkzeugtext gehoert zu C4b (MCP), nicht hierher.

## Rot-Proben (je Mutation ein Lauf, danach `git checkout`)

| Mutation | rot |
|---|---|
| `subject_user_id = $u` → `(… OR true)` | nie_fremdes, nutzungs_log, push |
| `kind <> 'lesson'` entfernt | lesson_nie_im_abruf |
| `confirmed` invertiert | kind_scope_confirmed |
| `_bump_retrieval` nur `agent_id` | nutzungs_log |
| `confirmed_only=False` im Push | push_zeigt_nur_bestaetigte |
| Service reicht `user_id=None` | nie_fremdes, kind_scope_confirmed, nutzungs_log |

## Offen fuer C4b

`search_memory`/`list_memories` im MCP: Rahmung „unbestaetigt“ je Treffer mit
`confirmed=false`; `save_memory` mit `origin`/`kind`/`scope`; `client.py` auf
`MemorySaveResult`; `propose_memory_change`; Werkzeugzahl + CLAUDE.md.
