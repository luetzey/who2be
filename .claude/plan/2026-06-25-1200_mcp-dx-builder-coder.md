# Plan: MCP-DX Builder/Coder — Reibungspunkte beheben & Agenten orchestrieren

**Datum:** 2026-06-25
**Status:** offen
**Issues:** #253–#259 (Epic: #259)
**Branch (Plan-Doc):** `claude/bold-carson-565cib`
**Persona:** Coder (orchestriert Sub-Agents pro Arbeitspaket)

---

## 1. Ziel & Leitlinie

Acht beobachtete Reibungspunkte aus realer MCP-Builder/Coder-Nutzung beheben.
Sie verdichten sich (siehe Epic #259) auf **zwei Wurzelursachen + ein fehlendes
Primitiv**:

- **A — keine maschinenlesbare Fehler-/Status-Taxonomie** (#254)
- **B — Builder-Identität ≠ Runtime-Identität** (#255, #256)
- **Fehlendes Primitiv — `whoami`/Capability-Introspektion** (#253)

**Leitlinie für jeden Sub-Agent:** *Erst reproduzieren, dann bauen.* Das
Codelesen (siehe §2) hat gezeigt, dass die Codebase reifer ist als das Feedback
annahm — mehrere „fehlende" Dinge existieren teilweise schon. Jedes Arbeitspaket
startet daher mit einem **Reproduktions-/Audit-Gate (Gate 0)**, dessen Ergebnis
ich (Coder) prüfe, bevor Code geschrieben wird. Ein WP kann an Gate 0 als
„bereits gelöst → Issue umschreiben/schließen" enden.

---

## 2. Architektur-Befunde (verbindlich, aus Codelesen 2026-06-25)

Diese Fakten sind der gemeinsame Kontext aller Sub-Agents. Abweichungen beim
Reproduzieren → an Coder eskalieren, nicht raten.

1. **Auth/Gates** sitzen in `apps/api/src/who2be_api/core/security.py`:
   - `WorkspaceContext` trägt `role`, `is_api_token`, `agent_id`, `tool_policy`.
   - `require_role(ctx, min)` → 403 mit deutschem `detail`; admin erzwingt zusätzlich `require_aal2`.
   - `require_capability(ctx, cap)` → No-Op wenn `tool_policy is None` (Mensch/JWT/ungebundener Token); sonst 403 mit `_CAPABILITY_LABELS`-Text.
   - `WorkspaceContext.sees_drafts(capability)` existiert bereits und entscheidet Draft-Sichtbarkeit.
2. **`"No approval received."` stammt NICHT aus diesem Repo** — es ist die
   Harness-seitige MCP-Approval-Prompt-Meldung (`apps/web/src/i18n/locales/*.json`
   enthält nur UI-Strings). Die API liefert echte 403/409 mit `detail`-Strings.
   → **Scope-Grenze (#254):** Wir können die Harness-Meldung nicht ändern, aber
   die API-Fehler **strukturieren**, damit sie — wo immer sie durchgereicht
   werden — den Aktor (`agent`/`human`/`none`) und den Grund tragen.
3. **State-Machine** lebt in `who2be_models` (`ALLOWED_TRANSITIONS`,
   `status.py`), erzwungen in `services/version_status.py`:
   `draft→review`, `review→active|draft`, `active→inactive`, `inactive→draft`.
   `validate_transition` wirft 409 `_forbidden_transition`. Promote/Retire
   (→active/→inactive) verlangen `admin`-Rolle + `promote_retire`-Capability.
4. **Draft-Sichtbarkeit ist bereits konsistent verdrahtet** (`active_only =
   not ctx.sees_drafts(CAP)`) in: `persona_service`, `playbook_service`,
   `resource_service`, `playbook_composition_service`, `resource_composition_service`,
   `persona_playbook_service`. Die Repositories (`*_repository.py`) tragen den
   `active_only`-Schalter durch (`_select_active` vs. `_select_current`).
   → **Folge für #255:** Mechanik existiert; offene Frage ist nur, ob der
   konkrete Pfad (LIST-Katalog, frischer Draft direkt nach `create`) ihn
   überall greift, und ob die Capability tatsächlich gehalten wird.
5. **Composite-„aktive-Kinder"-Regel ist im Service-/Promote-Code NICHT zu
   finden:** `set_composition` (`playbook_composition_service.py`) prüft keinen
   Kind-Status; `promote_validation.py` prüft nur Pflichtfelder. → **#256 ist
   vermutlich eine reine Doku-Regel in der MCP-Tool-Beschreibung, nicht
   erzwungen.** Gate 0 muss klären, wo (wenn überhaupt) sie greift.
6. **MCP-Server** (`apps/mcp/src/who2be_mcp/server.py`) ist ein dünner Adapter,
   der per HTTP gegen die API spricht (`client.py`); Tool-Beschreibungen
   (Docstrings) leben hier. Autorisierung passiert serverseitig in der API.

---

## 3. Arbeitspakete

Jedes WP: **Gate 0 (Reproduktion)** → **Implementierung** → **DoD**. Gate 0 wird
von Coder abgenommen, bevor Implementierung startet. DoD-Befehle pro Stack siehe
§6.

### WP-1 — `whoami` / Capability-Introspektion (#253) · P1 · Backend+MCP

- **Gate 0:** Bestätigen, dass `WorkspaceContext` alle nötigen Daten trägt
  (role, agent_id, tool_policy/Capabilities) und kein bestehender Endpunkt das
  schon liefert (`routers/workspaces.py`, `/v1/me` in `routers/*`).
- **Umsetzung:**
  - API: neuer Read-Endpunkt `GET /v1/workspaces/{ws_id}/whoami` (Viewer-offen,
    **kein** `require_role`/`require_capability`-Gate), liefert:
    `{ user_id, workspace_id, role, is_api_token, agent_id|null,
    capabilities: [..], domains: {persona,playbook,resource,agent: enabled} }`.
    Capabilities aus `ctx.tool_policy` (None ⇒ „alle", da ungated); Domains aus
    Policy + Editions-Flags.
  - Pydantic-Model `WhoAmI` in `packages/models` (von API+MCP geteilt).
  - MCP: Tool `whoami()` in `server.py` + `client.py`, **nicht** deferred-only
    sinnvoll dokumentiert; verweist von `ping` (bleibt auth-frei) hierher.
- **Betroffen:** `routers/workspaces.py` (o. neuer `routers/whoami.py`),
  `packages/models/src/who2be_models/`, `apps/mcp/src/who2be_mcp/{server,client}.py`,
  Tests in `apps/api/tests/` + `apps/mcp/tests/`.
- **DoD:** Endpunkt + MCP-Tool getestet (gültiger Token → Identität+Caps;
  ungebundener/JWT → role, keine Policy-Restriktion; ungültiger Token → 401).
  `ping` bleibt unverändert auth-frei.

### WP-2 — Strukturierte Fehler-Taxonomie (#254) · P1 · Backend

- **Gate 0:** Inventar aller relevanten 403/409 aus `require_role`,
  `require_capability`, `validate_transition`, `_require_transition_capability`.
  Prüfen, wie `main.py` heute Fehler serialisiert (es gibt bereits einen
  `problem+json`-Handler für `PromoteValidationError`) — **diesem Muster folgen**.
- **Umsetzung:**
  - Strukturierter Body (problem+json o. `detail`-Objekt):
    `{ error, actionable_by: agent|human|none, reason: missing_capability|
    approval_pending|domain_disabled|forbidden_transition|insufficient_role,
    detail, request_id|null }`. **Primärachse = `actionable_by`** (wer handelt).
  - `require_capability`/`require_role`/`_forbidden_transition` auf die neue
    Struktur heben (zentrale Helper, nicht an jeder Call-Site dupliziert).
  - Gesperrte Domänen/Reads → `reason: domain_disabled` (nicht generisch).
- **Betroffen:** `core/security.py`, `services/version_status.py`, `main.py`
  (Exception-Handler), evtl. `packages/models` (Error-Model), Tests
  `test_security.py`, `test_rbac_matrix.py`, `test_tool_policy.py`.
- **DoD:** Bestehende Tests grün/angepasst; neue Tests prüfen `actionable_by` +
  `reason` für je einen Fall pro Kategorie. Keine deutschen Klartext-`detail` als
  einzige Signalquelle mehr.

### WP-3 — Draft-Sichtbarkeit reproduzieren & schließen/fixen (#255) · P1 · Backend(+Doku)

- **Gate 0 (entscheidend):** Mit einem Builder-Token, das `resource_write` hält:
  `create_resource` (Draft) → `list_resources`/`fetch_resource`. Sieht der
  Aufrufer den Draft? Erwartung laut §2.4: **ja**. 
  - Falls **ja** → #255 ist gelöst; Issue umschreiben auf „dokumentieren, dass
    Drafts sichtbar sind, sobald die Write-Capability gehalten wird; via `whoami`
    (#253) erkennbar" → WP entfällt als Code-Change.
  - Falls **nein** → Lücke lokalisieren (LIST-Katalog-Endpunkt? Capability nicht
    gesetzt? `create` vs. Read unterschiedliche Cap?) und punktuell schließen.
- **Umsetzung:** nur falls Gate 0 eine echte Lücke zeigt — minimaler Fix am
  betroffenen Service/Repo-Pfad, **strikt owner-/workspace-scoped**.
- **Betroffen:** je nach Befund `services/resource_service.py` +
  `repositories/resource_repository.py` (LIST-Pfad), Tests `test_resources.py`,
  `test_read_scope_*`.
- **DoD:** Test, der „create→read eigener Draft sichtbar; fremder Draft
  unsichtbar; Runtime-Konsument sieht nur active" absichert — oder begründetes
  Schließen des Issues mit verlinktem Reproduktions-Test.

### WP-4 — Composite-Invariante: Link-Zeit vs. Promote-Zeit (#256) · P2 · Backend(+Doku)

- **Gate 0:** Wo wird „nur aktive Kinder verlinken" erzwungen? `set_composition`
  und `promote_validation.py` zeigen es nicht (§2.5). MCP-Tool-Docstring von
  `set_playbook_composes` lesen — ist es nur Doku? Reproduzieren: Draft-Kind
  verlinken → erlaubt? Composite mit Draft-Kind auf `active` promoten → was passiert?
- **Umsetzung (Zielbild):**
  - Link auf Draft-Kinder **erlauben** (falls heute geblockt: Block entfernen).
  - Aktiv-Prüfung des Composite-Graphen an **`transition_playbook → active`**
    hängen (in `validate_promote_playbook` o. `version_status._transition`):
    Promote schlägt mit klarer, strukturierter Meldung (welches Kind) fehl, wenn
    ein referenziertes Kind nicht `active` ist.
  - Irreführende MCP-Doku korrigieren.
- **Betroffen:** `services/promote_validation.py` **oder** `version_status.py`,
  `services/playbook_composition_service.py`, MCP-Docstring in `server.py`,
  Tests `test_promote_validation.py`, `test_playbook_composition*.py`.
- **DoD:** Test deckt vollen Pfad: Kinder als Drafts → Composite verketten →
  Kinder aktivieren → Eltern aktivieren (grün); Promote mit Draft-Kind → 409 mit
  benanntem Kind. **Achtung Wechselwirkung mit WP-2** (strukturierte Fehler) —
  WP-4 nutzt das WP-2-Format; sequenzieren (§4).

### WP-5 — State-Machine-Doku in allen drei `transition_*`-Tools (#257) · P3 · MCP-Doku

- **Gate 0:** Docstrings der drei MCP-Transition-Tools in `server.py` vergleichen.
- **Umsetzung:** identischen State-Machine-Hinweis (inkl. „`draft→active` direkt
  verboten, `review`-Zwischenstopp") in alle drei setzen — als geteilte Konstante/
  Doc-Fragment, um künftiges Auseinanderlaufen zu verhindern.
- **Betroffen:** `apps/mcp/src/who2be_mcp/server.py`, ggf. Tool-Snapshot-Tests.
- **DoD:** Alle drei Tools tragen den Hinweis; `npx`/`pytest`-Doc-/Snapshot-Tests grün.

### WP-6 — Block-Anker auflisten (#258) · P3 · Backend+MCP

- **Gate 0:** Wie werden Resource-Block-IDs/Anker heute vergeben/gespeichert
  (BlockNote-Body in `resource_repository`/`resource_service`)? Liefert
  `create_resource` sie schon zurück?
- **Umsetzung:** Read `list_resource_blocks(resource_id)` **oder** saubere
  Anker-Liste im `create_resource`-Response; Empfehlung: explizite Anker auf
  Heading-Blocks zum erwarteten Pfad machen.
- **Betroffen:** `services/resource_service.py`, ggf. neuer Router-Endpunkt,
  `apps/mcp/.../server.py` + `client.py`, Tests.
- **DoD:** Anker einer Resource ohne Raten lesbar; `set_playbook_resource_links`
  verlässlich dagegen setzbar (Test).

---

## 4. Abhängigkeiten & Reihenfolge

```
WP-5 (Doku)        ─┐  unabhängig, sofort, parallel
WP-6 (Anker)       ─┘  unabhängig, parallel

WP-1 (whoami)      ── unabhängig; liefert Modell-Muster für Fehler-Surface
WP-2 (Taxonomie)   ── Basis für WP-4; vor WP-4 mergen
WP-3 (Draft-Repro) ── Gate 0 zuerst; oft Doku-/Close-Ergebnis

WP-2 ──▶ WP-4 (nutzt strukturiertes Fehlerformat)
```

- **Welle 1 (parallel, worktree-isoliert):** WP-1, WP-2, WP-3-Gate0, WP-5, WP-6.
- **Welle 2:** WP-4 (nach WP-2-Merge), WP-3-Fix (nur falls Gate 0 Lücke zeigt).
- **Konfliktflächen:** WP-2 und WP-4 fassen beide `version_status.py`/`security.py`
  an → **nicht gleichzeitig** denselben File; WP-2 zuerst landen, WP-4 darauf rebasen.
  WP-1 und WP-2 berühren beide ggf. `packages/models` (Error- vs. WhoAmI-Model) —
  getrennte Dateien, unkritisch.

---

## 5. Orchestrierungs-Modell (so betreuen wir die Agenten)

**Ein Sub-Agent pro Arbeitspaket**, gestartet via Agent-Tool mit
`isolation: "worktree"` (parallele File-Mutationen an `apps/api` würden sonst
kollidieren). Pro Agent ein eigener Branch + eigener **Draft-PR**.

**Agent-Prompt-Skelett (pro WP):**
1. Kontext: dieser Plan (§2 Befunde + das jeweilige WP) + das GitHub-Issue.
2. Auftrag: **Gate 0 zuerst** — reproduzieren, Ergebnis als kurzen Befund
   zurückgeben und **stoppen für Coder-Review**, falls das Ergebnis das WP
   verändert (z. B. „bereits gelöst").
3. Bei grünem Gate 0: implementieren nach WP-DoD, Tests + Lint + Typecheck des
   betroffenen Stacks lokal grün (§6), committen (Conventional Commits), Branch
   pushen, Draft-PR öffnen, PR mit Issue verlinken (`Closes #NNN`).
4. Rückgabe an Coder: Befund, Diff-Zusammenfassung, PR-Link, offene Risiken.

**Review-Gates (Coder = ich):**
- **Gate 0-Abnahme:** Ich prüfe jeden Reproduktions-Befund, bevor Code entsteht
  (verhindert Bauen gegen Phantom-Probleme — siehe #255/#256).
- **PR-Review:** `security-reviewer`-Subagent auf jeden PR, der Auth/Gates/Reads
  berührt (WP-1, WP-2, WP-3, WP-4) — CLAUDE.md-Pflicht.
- **Merge-Reihenfolge** nach §4; ich rebase/merge, nicht die Sub-Agents.

**Fortschritt nach GitHub:** Jeder PR `Closes #NNN`; Epic #259-Checkliste
abhaken, wenn ein WP gemmerged ist. Sparsam kommentieren (CLAUDE.md-Etikette) —
nur bei Befund-Eskalation oder Abschluss.

**Parallelität:** Welle-1-Agenten in **einer** Nachricht starten (gleichzeitig).
Welle 2 erst nach den jeweiligen Merges.

---

## 6. DoD-Befehle (vor jedem Push, lokal verifiziert)

- **Python:** `uv run ruff check .` · `uv run ruff format --check .` ·
  `uv run mypy .` · `uv run pytest -q`
- **Web** (nur falls UI berührt — hier voraussichtlich nicht): `npm run lint` ·
  `npx tsc --noEmit` · `npm test` · `npm run build`
- **Bugfix-Regel:** erst reproduzierender, failing Test, dann Fix (CLAUDE.md §Workflow).

---

## 7. Gesamt-Definition-of-Done

- [ ] WP-1 `whoami` gemerged; `ping` bleibt auth-frei.
- [ ] WP-2 strukturierte Fehler mit `actionable_by`/`reason` gemerged.
- [ ] WP-3 reproduziert: Draft-Sichtbarkeit bestätigt (Issue geschlossen/umgeschrieben) **oder** Lücke gefixt.
- [ ] WP-4 Composite-Invariante an Promote-Zeit; Doku korrigiert.
- [ ] WP-5 Transition-Doku in allen drei Tools.
- [ ] WP-6 Block-Anker lesbar.
- [ ] Epic #259-Checkliste vollständig; alle PRs `Closes #NNN`; security-reviewer
      auf Auth-/Read-berührenden PRs durchlaufen.
- [ ] `.claude/context/STATE` + (bei Architekturwirkung) `DECISIONS` gepflegt.
