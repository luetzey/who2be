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

## 3a. Gate-0-Ergebnisse (2026-06-25, Audit abgeschlossen)

Fünf parallele Read-only-Audits gelaufen; Verdicts verbindlich für die
Umsetzung. Reihenfolge nach Folgenschwere:

### WP-3 (#255) → **VERDICT (A): bereits im Code gelöst — kein Read-Path-Change**

`WorkspaceContext.sees_drafts(cap)` durchzieht **alle** Resource-Lesepfade:
`ResourceService.get` (`resource_service.py:182`) **und** `list_all`
(`:159`) setzen `active_only=not ctx.sees_drafts(resource_write)`. Der
geseedete Builder hat `resource_read=ReadScope.all` + `resource_write`
(`workspace_repository.py:411` `_builder_tool_policy`) → sieht seinen frischen
Draft via fetch UND list. Das Feedback-Szenario ist in sich widersprüchlich:
`create_resource` verlangt `require_capability(resource_write)` — dieselbe
Capability schaltet via `sees_drafts` das Draft-Lesen frei. Wahre Ursache eines
historischen Reports lag vermutlich in **fehlender Capability** (→ #254/#253),
nicht in einem Read-Filter. Persona-/Playbook-LIST honorieren `sees_drafts`
ebenso (`persona_service.py:154`, `playbook_service.py:220`).

→ **#255 umwidmen auf Doku statt Code:**
1. Veralteten Docstring `apps/mcp/src/who2be_mcp/server.py:441`
   („Laedt die aktive Version") korrigieren — beschreibt das Draft-Lese-Verhalten
   falsch.
2. Mechanik dokumentieren („wer schreiben darf, sieht Drafts").
3. Effektive Policy via `whoami` (#253) sichtbar machen — schließt den Loop.
4. Secure-by-default-Note: ein `assigned`-scoped Agent mit `*_write` sähe eine
   frisch erstellte, unverlinkte Resource **nicht** (nicht in Assigned-Closure →
   404). Bewusst so; betrifft den Builder (`all`) nicht.

→ **Aufwand: XS (Doku).** Issue als „already solved" schließen oder zur
Doku-Aufgabe umschreiben. **Kein eigener Build-PR nötig** — Punkte 1–2 fließen
in den WP-1-PR (whoami) als zugehörige Doku ein.

### WP-2 (#254) → **tragfähig; folgt `PromoteValidationError`-Muster 1:1**

Vorbild: `main.py:100–118` + `:162` (`app.add_exception_handler` →
`JSONResponse(media_type="application/problem+json")`, RFC-7807). Zweiter
Präzedenzfall: `DeleteBlocked` (`packages/models/.../links.py:34`).
Raise-Inventar: `core/security.py` (require_aal2 :212, require_role :231,
require_capability :264 + 3 sekundäre im `get_current_workspace`-Pfad) und
`version_status.py` (`_forbidden_transition` :64, `_invariant_violation` :71,
Template-Block :140). Test-Blast-Radius **klein** — nur ~3 `detail`-Substring-
Asserts (alle `test_mfa_aal2.py`); `test_rbac_matrix`/`test_tool_policy`/
`test_security` prüfen nur Statuscodes.

→ **Festgezurrte Entscheidungen (Coder, gültig sofern kein Einspruch):**
- **D1 — `reason`-Enum erweitern:** Die fünf Werte decken MFA + Concurrency-Race
  nicht. **+`mfa_required`** (für `require_aal2`) **+`concurrent_conflict`**
  (für `_invariant_violation`, der einzige echte Retry-Fall).
- **D2 — eigene Exception statt nackter `HTTPException`:** neue `ApiGateError`
  + **ein** zentraler `problem+json`-Handler (wie PromoteValidationError), damit
  `type`/`title`/`request_id` einmal im Handler gesetzt werden und Call-Sites
  nur `(status, reason, actionable_by, detail)` liefern. `request_id` aus dem
  bestehenden `RequestIDMiddleware`.
- **D3 — `actionable_by`-Achse = „wer kann den nächsten produktiven Schritt
  tun?":** `missing_capability`→**`human`** (Agent kann sich Caps nicht selbst
  geben; Owner schaltet frei), `insufficient_role`→`human`,
  `mfa_required`→`human`, `forbidden_transition`→`none`,
  `concurrent_conflict`→**`agent`** (Retry sinnvoll), Template-Sperre→`none`,
  Org-deleted→`domain_disabled`/`human`.
- Neues Model `ApiProblem` in `packages/models/.../errors.py` (RFC-7807 +
  `actionable_by`/`reason`/`request_id`).

→ **Aufwand: M.** Basis für WP-4 — vor WP-4 mergen.

### WP-1 (#253) → **tragfähig; Scope = inkl. Entitlement-Features (User-Entscheid)**

`/v1/me` ist workspace-agnostisch (`get_current_user`) → kein Ersatz. Eigener
Router nach Vorlage `routers/dashboard.py` → `/v1/workspaces/{ws_id}/whoami`,
Dependency `get_current_workspace`. `AgentToolPolicy` hat **keinen**
Capability-Lister → additiven Helper `granted_capabilities()` am Model ergänzen
+ die 3 Read-Scopes (`*_read`) separat ausgeben. **`tool_policy is None` =
„keine Pro-Agent-Restriktion"**, nicht „nichts erlaubt" — explizit so
darstellen. **User-Entscheid: Entitlement-Features mitliefern** → zusätzlicher
org-scoped `EntitlementPort.resolve(org_id)`-Call (Muster `routers/entitlement.py:71`).

→ **Aufwand: M** (Identität S + Entitlement-Achse). WP-3-Doku (Docstring-Fix +
sees_drafts-Doku) reist in diesem PR mit.

### WP-5 (#257) → **bestätigt, Aufwand S**

Nur `transition_persona` (`server.py:528`) trägt die Aufzählung;
`transition_playbook` (:594) / `transition_resource` (:673) verweisen nur „wie
bei Persona". Keine Tests brechen. **SSoT:** Konstante `TRANSITION_RULE_DOC` in
`packages/models/.../status.py` neben `ALLOWED_TRANSITIONS`, per f-String in alle
drei Docstrings (FastMCP liest `__doc__` zur Laufzeit). Optional neuer
Description-Konsistenz-Test in `apps/mcp/tests/test_server.py`.

### WP-6 (#258) → **Option (a) `list_resource_blocks`, Aufwand S–M**

Heading-Extraktion existiert serverseitig wiederverwendbar
(`playbook_resource_link_repository.py`: `is_heading_block`,
`block_section_text`, `load_resource_blocks`). Neuer Read
`GET …/resources/{id}/blocks` + MCP-Tool + Client + Read-Model
`ResourceBlockAnchor{block_id, level, text}`. **Nebenbefund:**
`set_playbook_resource_links` erkennt einen **nicht existierenden** Anker heute
nicht als Fehler (stiller toter Link) — der neue Read macht Raten überflüssig;
„unbekannter Anker → 422" ist eine kleine Folgeentscheidung (separat halten).
**Stolperstein:** `load_resource_blocks` pinnt die Active-Variante hart auf
Locale `'de'` (`:211`) — für Multi-Locale parametrisieren.

---

## 4. Abhängigkeiten & Reihenfolge

**Aktualisiert nach Gate 0 (§3a):** WP-3 ist kein Code-WP mehr (Doku, reist in
WP-1 mit). Verbleibende Build-WPs: WP-1, WP-2, WP-4, WP-5, WP-6.

```
WP-5 (Doku)        ─┐  unabhängig, sofort, parallel
WP-6 (Anker)       ─┘  unabhängig, parallel

WP-1 (whoami+WP-3-Doku) ── unabhängig
WP-2 (Taxonomie)        ── Basis für WP-4; vor WP-4 mergen

WP-2 ──▶ WP-4 (nutzt strukturiertes Fehlerformat)
```

- **Welle 1 (parallel, worktree-isoliert):** WP-1 (inkl. WP-3-Doku), WP-2, WP-5, WP-6.
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
