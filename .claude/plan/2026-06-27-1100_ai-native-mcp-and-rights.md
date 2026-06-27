# AI-native MCP-Toolset + feinkoerniges Rechtesystem

Stand: 2026-06-27 · Branch `claude/charming-pasteur-pxz2l8`

## Ziel (User-Request)

Das MCP-Toolset und das Rechtesystem so erweitern, dass Who2Be vom
„versionierten CRUD-Register" zum **AI-native, selbst-verbessernden AgentDB**
wird — und der User die Agenten-Rechte **detaillierter** einstellen kann.

Vier Tracks, in Aufwand-/Hebel-Reihenfolge. Jeder Track ist fuer sich
abschliessbar und liefert eigenstaendigen Wert.

## Ausgangsbefund (verifiziert)

- **Stark heute:** `fetch_agent` rendert den fertigen System-Prompt; der
  Draft→review→active-Workflow ist faktisch „Agent schlaegt vor, Mensch gibt
  frei". CRUD + Versionierung + Per-Agent-Policy-Grundgeruest sind vollstaendig.
- **Luecken:** (1) keine inhaltliche Suche — nur Volllisten + exakter Tag/Trigger;
  (2) kein Feedback-/Usage-Rueckkanal — `*Usage`-Models sind reine FK-Backlinks;
  (3) Reverse-Lookups + Versionshistorie/Diff existieren in REST, aber nicht im
  MCP; (4) Write-Rechte nur pro Domain an/aus, `promote_retire` global, keine
  Tag-/Collection-Scopes, keine TTL.

---

## Fortschritt

- **Track 1 — ERLEDIGT (2026-06-27):** `find_usages`, `list_versions`,
  `get_version`, `diff_versions` als MCP-Tools (Entity-Dispatch über
  Pfad-/Model-Maps im Client). 12 neue Tool-Tests + volle MCP-Suite grün (111),
  ruff/mypy sauber. Keine Migration. Branch `claude/charming-pasteur-pxz2l8`.
- **Track 3 — ERLEDIGT (2026-06-27):** Feedback-Flywheel. Migration 0053
  (append-only `usage_event` + `agent_feedback`, RLS + nur SELECT/INSERT-Grant),
  Models (`feedback.py`), Capability `feedback_write` (default True), Repo +
  Service + Router (`/usage-events`, `/feedback`, `/feedback/{type}/{id}`),
  MCP-Tools `record_usage`/`submit_feedback`/`get_feedback`, Tools-Übersicht.
  Tests: Gate (default True/disable), MCP-Adapter, DB-Integrationstest. ruff `.`
  + mypy (177 Source) clean; DB-freie Tests grün. Branch
  `claude/track3-feedback-flywheel` (gestapelt auf Track 1/Builder). Dashboard-
  Surfacing der Aggregate als Folge-Schritt vermerkt.
- **Track 2 — ERLEDIGT (2026-06-27):** Discovery/Search. Kein Migration —
  Runtime-FTS (`to_tsvector`/`plainto_tsquery`/`ts_rank`) über Name + Content der
  aktiven Version (Locale de). `SearchHit`-Model, Repo + Service (Read-Scope-
  Filter) + Router (`GET /search?q=&types=&limit=`), MCP-Tool `search`, Tools-
  Übersicht (`search`-read_domain). Tests: MCP-Adapter + DB-Integrationstest.
  ruff `.` + mypy (179 Source) clean; DB-freie Tests grün (246). Branch
  `claude/track2-search` (gestapelt auf Track 3). GIN-Index + pgvector (Stufe B)
  als Folge.
- **Track 4-A — ERLEDIGT (2026-06-27):** getrennte Promote/Retire pro Domain
  (`TransitionGrant` + `transition_grants`, Narrowing von `promote_retire`, Gate
  + `is_within`) + Token-TTL exponiert (`TokenCreate.expires_at`; Enforcement +
  Spalte existierten schon). Additiv, DB-frei verifiziert (ruff/mypy 181 Source
  clean, tool_policy-Tests 29 grün). Branch `claude/track4-finer-rights`.
- **Track 4-B — OFFEN:** Tag-Prädikat-Write-Scoping (`WriteScope tagged`),
  Write-Rate-Limit, **Web-Policy-Editor** (AgentEditorForm + whoami-Ausgabe).
  Braucht per-Service-Enforcement + Frontend (DB/Web-Verifikation).

## Track 1 — Read-only-Adapter-Tools (billigste Wins, kein neuer ADR)

Erweitert ADR-0030/0021. Reine MCP-Adapter ueber **bestehende** REST-Endpunkte;
keine Backend-Logik, nur Tool + 4xx-Mapping. Read-Scope/`status='active'` gelten
wie bei allen Reads.

Neue MCP-Tools in `apps/mcp/src/who2be_mcp/server.py` (+ `client.py`-Pfade):

- `find_usages(entity_type, entity_id)` → wrappt
  `GET …/playbooks/{id}/usages`, `…/resources/{id}/usages` (+ Persona-Usages,
  `PersonaUsage` existiert). Agent versteht Impact vor einem Edit.
- `list_versions(entity_type, entity_id, locale?)` → `GET …/{entity}/{id}/versions`.
- `diff_versions(entity_type, entity_id, version, against="active")` →
  `GET …/{entity}/{id}/versions/{v}/diff`. Agent kann Draft vor `promote`
  selbst-reviewen.
- `get_version(entity_type, entity_id, version)` → einzelne Version.

DoD-Add: Tabellen-Test Tool→REST-Mapping, 403 bei fehlendem Read-Scope.
Keine Migration. Kein ADR (Notiz in ADR-0030 „erweitert um Reverse-/Version-Reads").

---

## Track 2 — Discovery & Search (ADR-0037)

Volltext jetzt, Vektor-bereit. Details: `docs/adr/0037-mcp-discovery-search.md`.

- **Models:** `SearchHit{type,id,name,snippet,score}` in `packages/models`.
- **Migration:** `tsvector`-generated-columns + GIN-Indizes auf
  Persona/Playbook/Resource-Content (aktive Version: Titel + Tags + Body).
- **Backend:** `routers/search.py`, `SearchService`, `SearchRepository`
  (`ts_rank`); Read-Scope-Filter **vor** Ranking via `visible_*_ids`;
  nur `status='active'`.
- **REST:** `GET /v1/workspaces/{ws}/search?q=&types=&tags=&limit=`.
- **MCP:** Tool `search(query, types?, tags?, limit=20)`; `tools-overview`-Filter.
- **Web (optional, Folge):** globale Such-Leiste nutzt denselben Endpunkt.
- Stufe B (pgvector/semantisch) = eigener Plan, gleicher Tool-Vertrag (`mode`).

---

## Track 3 — Usage- & Feedback-Flywheel (ADR-0038)

Der zentrale AI-native-Hebel. Details: `docs/adr/0038-agent-usage-feedback-flywheel.md`.

- **Migration:** `usage_event`, `agent_feedback` — append-only, immutable,
  Index auf `(workspace_id, entity_type, entity_id)`; `agent_id`, `actor`,
  `created_at`, optional `version`.
- **Models:** `UsageEvent`, `AgentFeedback`, `FeedbackSummary` (Aggregat).
- **Backend:** `routers/feedback.py`, `FeedbackService`/`UsageService`-Erweiterung;
  `feedback_write`-Capability-Gate (Default True); `record_usage` an Read-Scope
  gebunden; `get_feedback` `editor`-gated.
- **REST:** `POST …/usage-events`, `POST …/feedback`, `GET …/{entity}/{id}/feedback`.
- **MCP:** `record_usage`, `submit_feedback`, `get_feedback`.
- **Dashboard:** Aggregate „meistgenutzt / als veraltet / fehlerhaft gemeldet"
  → Kurations-Backlog (Dashboard-Endpoint + -Page erweitern).
- **Wichtig:** Feedback fliesst NIE in einen gerenderten Prompt (kein
  Injection-Vektor, ADR-0038 §Abgrenzung); `note` wird escaped angezeigt.

---

## Track 4 — Feinkoernige Write-Rechte + Policy-UI (ADR-0039)

Der „detaillierter einstellbar"-Kern. Details:
`docs/adr/0039-fine-grained-agent-write-scoping.md`.

- **Model (`tool_policy.py`):** `WriteScope{all|assigned|tagged}`,
  `WriteGrant{enabled,scope}`; Write-Domains von `bool` → `WriteGrant`
  (legacy `true` ⇒ `{enabled,scope:all}`). `transition_grants: dict[domain,
  {promote,retire}]` ueberlagert `promote_retire`. `is_within` + `allows`
  (Ziel-Tags) erweitern. JSONB-abwaertskompatibel (ADR-0009), kein
  destruktiver Migrationsschritt fuer `agent.tool_policy`.
- **Migration:** nur `api_token.expires_at` (nullable) [+ optional
  `write_rate_limit`]; abgelaufener Token ⇒ 401.
- **Backend:** Service-Gates (`require_capability`) um Ziel-Tag-Pruefung
  erweitern; Transition-Gate liest `transition_grants`; Token-Auth prueft
  `expires_at`. Rollen-Eskalation (admin fuer Promote/Retire) bleibt unberuehrt.
- **Web:** `AgentEditorForm` — pro Domain Scope-Auswahl (all/assigned/tagged +
  Tag-Picker), Promote/Retire-Switches je Domain; Token-Binding mit Ablaufdatum.
- **Introspektion:** `whoami` gibt effektive Scopes/Transition-Rechte/Ablauf aus.

---

## Sequenzierung & Abhaengigkeiten

1. **Track 1** zuerst (klein, risikoarm, sofort Mehrwert, keine Migration).
2. **Track 3** (Flywheel) — groesster AI-native-Hebel; unabhaengig von 2/4.
3. **Track 2** (Search) — unabhaengig; profitiert spaeter von Embeddings.
4. **Track 4** (Rechte) — unabhaengig, aber groesste Test-Matrix; bewusst zuletzt.

Jeder Track = eigener Commit/PR-faehiger Schritt. ADRs sind `Proposed` → bei
Umsetzung auf `Accepted` flippen.

## DoD (alle Tracks)

- Python: `uv run ruff check . && uv run mypy . && uv run pytest -q`.
- Web: `npm run lint && npx tsc --noEmit && npm test && npm run build`.
- `security-reviewer`-Subagent ueber jeden neuen Auth-/Write-/Input-Pfad
  (Search-Injection, Feedback-Free-Text, Scope-Durchsetzung).
- `.claude/context/STATE` + `DECISIONS` nach jedem Track pflegen.
