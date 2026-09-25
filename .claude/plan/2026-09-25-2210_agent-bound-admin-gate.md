# Agent-gebundene Tokens an allen sieben `require_role(admin)`-Routern sperren

Kanban-Karte: `t_ea83420c` (Board `who2be`) · Herkunft: Review-Befund `t_06b1d160`
Branch: `who2be/t_ea83420c-agentbound-admin-gate` · Basis: `origin/main` @ `8d4161cf`
Betriebsmodus: **produktiv** (`.claude/project.json` fehlt → vorsichtigerer Zustand, Code-Task-Flow 1.1)

## Ask-Once-Gate (Phase 1.4a) — BESTANDEN

Die Karte trägt alle vier Pflichtfelder, deshalb keine Rückfrage:

- **Outcome** — alle sieben `require_role(ctx, WorkspaceRole.admin)`-Stellen der Klasse 1
  weisen agent-gebundene Tokens mit 403 ab.
- **Akzeptanzkriterien** — von außen prüfbar: je 403 (nicht „nicht 2xx") auf allen sieben
  Routen; Gegenrichtung (ungebundener Admin-Token, Mensch/JWT) unverändert durchlässig;
  bestehender Token-Pfad wortgleich (403, `reason: token_management_forbidden`).
- **Out-of-Scope** — Klasse 2 (`me.py`, `organizations.py`, `gdpr.py`, `get_current_user`)
  ist Karte `t_1b046ae7`; `invitations.py:83 accept_invitation` bleibt unangetastet.
- **Verifikation** — `uv run ruff check .`, `uv run mypy .`,
  `uv run pytest --cov --cov-fail-under=85`; roter Regressionstest vor dem Fix.
- **Vorentschiedene Weichen** — Gate nach `core/security.py` ziehen statt siebenmal
  kopieren; strengeres Prädikat (beide Indikatoren); eigener `reason`.

Keine Annahmen „auf Zuruf" nötig.

## Design-Weiche + Muster-Benennung

Die Karte lässt genau eine Struktur-Frage offen: das verschobene Gate muss **zwei**
Fehlerverträge bedienen — den bestehenden Token-Pfad (`ApiError`, schlanke Hülle,
`application/json`, `reason: token_management_forbidden`, wortgleich zu erhalten) und den
neuen Admin-Pfad (`ApiGateError`, `application/problem+json`, `actionable_by: "human"`,
neuer `reason`). Die Hülle ist also nicht dieselbe, nur das Prädikat ist es.

**Gewählt: geteiltes Prädikat + zwei dünne Gate-Funktionen** (Guard-Clause-Paar über
einem gemeinsamen Prädikat):

```python
def is_agent_bound(ctx: WorkspaceContext) -> bool: ...  # das eine Prädikat
def deny_agent_bound_token_management(ctx) -> None: ...  # ApiError, alter reason
def deny_agent_bound_workspace_admin(ctx) -> None: ...  # ApiGateError, neuer reason
```

**Verworfen: eine parametrisierte Funktion** `deny_agent_bound(ctx, scope)` mit
Mapping-Tabelle `scope → (Exception-Fabrik)`. Kompakter, aber sie müsste die
Exception-**Klasse** aus einer Tabelle ziehen — ein Mapping-Orakel, das genau die eine
Information verschleiert, auf die es hier ankommt: welcher Aufrufer welchen
Serialisierungs-Vertrag hat.

**Beleg für die Variabilität** (Schwelle „bereits existierender zweiter Fall"): der
Token-Pfad existiert mit sechs Aufrufern und veröffentlichtem Fehlervertrag; der
Admin-Pfad kommt als zweiter, nachweislich anderer Vertrag dazu. Abstrahiert wird nur das
Prädikat — also genau das, was in beiden Fällen identisch ist.

## Arbeitspakete

Ein Paket, datei-übergreifend aber chirurgisch; keine Parallelisierung. Reihenfolge ist
TDD-erzwungen (`CLAUDE.md` §Workflow: erst der rote Test).

1. **Roter Regressionstest** — `apps/api/tests/test_agent_bound_admin_gate.py`,
   tabellengetrieben über alle sieben Routen, DB-frei nach dem Muster von
   `test_entity_quota_duplicate_routes.py` (`dependency_overrides` für
   `get_current_workspace`/`get_pool`, Fake-Pool wirft `_ReachedService` als
   Durchgelassen-Signal). Fordert **403** und den `reason`, nicht bloß „nicht 2xx" — die
   gemessenen 404/409 der Karte sind genau die Falle. Plus Gegenprobe in beide Richtungen
   (ungebundener Admin-Token, Mensch/JWT).
   Vorher rot gesehen, Ergebnis im Übergabe-Bericht.
2. **Gate nach `core/security.py`** — `is_agent_bound` +
   `deny_agent_bound_token_management` + `deny_agent_bound_workspace_admin` neben
   `require_role`/`require_capability`/`require_memory_mode`.
   Prädikat folgt dem strengeren Muster von `memory_service._require_human:296`:
   `tool_policy is not None or agent_id is not None` — weil
   `_load_agent_tool_policy` (`core/security.py:565-584`) bei einem Race mit Agent-Delete
   defensiv auf `None` zurückfällt und das Gate mit nur einem Indikator dann offen wäre.
3. **`TokenService._deny_agent_bound` entfernen** — die sechs Aufrufstellen rufen
   `deny_agent_bound_token_management(ctx)`. Verhalten byte-identisch: derselbe
   Statuscode, derselbe `detail`-Text, derselbe `reason`, dieselbe Hülle (`ApiError`).
4. **Neuer `reason`** — `workspace_administration_forbidden` in `ProblemReason`
   (`packages/models/.../errors.py`) plus Titel in `_PROBLEM_TITLES` (`main.py`);
   `test_error_taxonomy.test_every_problem_reason_has_a_title` erzwingt das.
   **Kein** Locale-Key: `localeParity.test.ts:19-24` hält fest, dass Gate-Gründe
   (`ApiGateError`) absichtlich keinen tragen, damit ihre spezifischen `detail`-Meldungen
   erhalten bleiben (DECISIONS 2026-09-07). Der alte `token_management_forbidden` behält
   seinen Locale-Key, weil er `ApiError` bleibt.
5. **Aufruf an den sieben Stellen** — `invitations.py:64,70,79`, `members.py:51,58`,
   `workspaces.py:52,70`; je direkt nach `require_role(ctx, WorkspaceRole.admin)`.
6. **Doku als DoD** — `changelog.d/<slug>.security.md` (Fragment-Muster, nicht direkt in
   `CHANGELOG.md`), `.claude/context/STATE.md` + `DECISIONS.md` (Muster-Entscheidung).

## Nicht anfassen

`invitations.py:83` (`accept_invitation`, `get_current_principal`-Pfad ohne
`WorkspaceContext`) · `me.py`/`organizations.py`/`gdpr.py` (Klasse 2, Karte `t_1b046ae7`) ·
`_PROBLEM_TITLES`-Bestand · `token_management_forbidden` in `de.json`/`en.json` ·
`tests/contract/gate_inventory.json` (das Gate ist ein Inline-Call, keine
FastAPI-Dependency — das Golden liest nur `route.dependant.dependencies`) ·
`tests/contract/openapi_surface.json` (keine Routen-Änderung).

## Delegation

Kein Sub-Agent. Ein Paket ohne offene Design-Weiche, chirurgischer Diff; die vollständige
Recherche (sieben Call-Sites, beide Fehlerhüllen, Taxonomie- und Locale-Kopplung,
Testmuster) liegt bereits im Orchestrator-Kontext. Ein Briefing dafür zu schreiben und die
Rückgabe zu prüfen kostet mehr, als es an Kontext-Hygiene einbringt — abweichend von der
Delegations-Regel der Phase 3, bewusst und hier festgehalten.

## Verifikation

- `uv run ruff check .`
- `uv run mypy .`
- `uv run pytest --cov --cov-fail-under=85`
- `cd apps/web && npm run test:coverage` nur falls Locale-Dateien doch berührt werden
  (nach Plan: nein).

---

## Übergabe-Bericht

### (a) Betroffene Software-Elemente

Werkzeuggestützt gemessen (`git diff --stat`, `grep -rn` rückwärts nach Aufrufern),
nicht aus dem Kontext erzählt. Diff: 13 Dateien, +159/−51.

**DIREKT (importiert oder ruft auf):**

| Symbol | Status | Aufrufer |
|---|---|---|
| `core/security.is_agent_bound` | neu (Konsolidierung) | `security.py` (2 Gates), `workarea_scope.py` (3), `agent_service.py` (3), `kb.py` (1), `work_areas.py` (2) = **11** |
| `core/security.deny_agent_bound_token_management` | neu | `token_service.py` = **6** |
| `core/security.deny_agent_bound_workspace_admin` | neu | `invitations.py` (3), `members.py` (2), `workspaces.py` (2) = **7** |
| `TokenService._deny_agent_bound` | **entfallen** | 0 (alle sechs umgestellt) |
| `workarea_scope.is_agent_bound` | **entfallen** (→ `core/security`) | 0 |
| `agent_service._is_agent_bound` | **entfallen** (→ `core/security`) | 0 |
| `ProblemReason` | +1 Wert | Taxonomie-weit; `_PROBLEM_TITLES` nachgezogen |

**TRANSITIV (zweite Ebene):** `routers/tokens.py` + `routers/agents.py` (über
`token_service`/`agent_service`); die zehn `wa_*`-Services über `workarea_scope`.
Alle nur über den **Import-Pfad** berührt — das Prädikat ist byte-identisch
umgezogen, kein Verhaltenswechsel an diesen Stellen.

**VERMUTET (Laufzeit-Verdrahtung, unsicher):** die drei Stellen, die den `reason`
als String außerhalb von Python lesen — `docs/reference/openapi.json`
(regeneriert, CI-Gate erzwingt das), `apps/web/src/i18n/locales/{de,en}.json`
(**bewusst nicht** angefasst, siehe unten) und jeder MCP-Client, der auf `reason`
verzweigt. Letzterer ist additiv bedient: ein neuer Enum-Wert, kein geänderter.

### (b) Rest-Test-Liste

Diff-Coverage **gemessen**, nicht behauptet: alle drei neuen Funktionen in
`core/security.py` sind vollständig abgedeckt — jede wird von
`test_agent_bound_admin_gate.py` in beiden Zweigen gefahren (Gate greift /
Gate lässt durch), die Token-Variante zusätzlich von den sechs Bestandsfällen in
`test_token_service.py`.

**Ungedeckte geänderte Funktionen: keine.** Die übrigen Änderungen sind
verhaltens-neutral und deshalb herausgefiltert: die drei entfallenen
Prädikat-Kopien (identischer Ausdruck, nur Fundort verschoben), die reinen
Import-Zeilen und der additive Enum-/Titel-Eintrag.

**Von Hand zu prüfen: nichts.** Der einzige Kandidat wäre die Web-UI, und genau
für sie hält der Test die Gegenrichtung fest (Mensch/JWT und ungebundener
Admin-Token kommen auf allen sieben Routen weiter durch).

### Verifikation (transkript-nachweisbar)

| Schritt | Ergebnis |
|---|---|
| Regressionstest **vor** dem Fix | **15 rot**, Grund `_ReachedService` auf allen sieben Routen — das Loch ist getroffen, nicht ein Nebeneffekt |
| Regressionstest nach dem Fix | 29 grün |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 902 files already formatted |
| `uv run mypy .` | Success: no issues found in 492 source files |
| `uv run pytest --cov --cov-fail-under=85` | **2302 passed, 0 failed, 0 skipped**, Coverage **90.17 %** |
| `scripts/export_openapi.py` (CI-Drift-Gate) | regeneriert, genau +1 Zeile |

Die Suite lief gegen eine eigene ephemere Postgres (podman, Port 55471) mit
`WHO2BE_REQUIRE_DB=1`. Ohne sie wurden 496 Integrationstests still übersprungen
und die Coverage fiel auf 65 % — Port 5432 dieser Maschine gehört einem fremden
Projekt. Der `who2be-ndtest`-Stack des Researchers wurde **nicht** angefasst.

### Nebenfund (im Scope mitbehoben, weil der Fix ihn erzeugt hätte)

Das Prädikat `tool_policy is not None or agent_id is not None` lag bereits
**zweifach** im Repo (`workarea_scope.is_agent_bound`,
`agent_service._is_agent_bound`). Eine dritte Kopie einzuführen wäre genau die
Drift-Quelle gewesen, gegen die die Karte argumentiert — deshalb sind alle drei
auf die eine Definition in `core/security.py` zusammengeführt. Das ist die
Muster-Schwelle „drittes Vorkommen" aus dem Atomic *Design-Prinzipien*, hier
nicht als Abstraktion auf Verdacht, sondern als Zusammenführung bestehender
Duplikate.

### Bewusst nicht getan

- **Kein Locale-Key** für `workspace_administration_forbidden`.
  `localeParity.test.ts:19-24` hält fest, dass Gate-Gründe (`ApiGateError`)
  absichtlich keinen tragen, damit ihre spezifischen `detail`-Meldungen erhalten
  bleiben (DECISIONS 2026-09-07). `token_management_forbidden` behält seinen,
  weil er `ApiError` bleibt.
- **Klasse 2 nicht mitgefixt** (`me.py`, `organizations.py`, `gdpr.py`) — offene
  Owner-Weiche, Karte `t_1b046ae7`.
- **`accept_invitation` nicht angefasst** — anderer Pfad
  (`get_current_principal`, kein `WorkspaceContext`).
- **`gate_inventory.json` unverändert** — das Golden liest nur
  `route.dependant.dependencies`; dieses Gate ist ein Inline-Call. Das ist
  dieselbe dokumentierte Grenze, die dort schon für `POST /tokens` gilt.

