# MCP-Workspace aus dem Token statt aus `/v1/me` (Stufe 1)

_Angelegt: 2026-08-23 13:04 UTC — Coder / Code-Task-Flow_

## Anlass

Ein zweiter MCP-Connector (Workspace „YouTube") schlug bei **jedem** Tool mit
`403 Token gehoert nicht zu diesem Workspace (reason=forbidden_transition,
actionable_by=none)` fehl — auch bei `whoami`, das nur den Token aufloest.
Reproduziert am 2026-08-23 gegen den laufenden Stack: `Who2Be_Builder__whoami`
und `Who2Be_Coder__whoami` liefern sauber `workspace_id=0e77e512…`,
`YouTube_Builder__whoami` bricht mit obigem 403.

## Root Cause (belegt)

1. `apps/api/src/who2be_api/core/security.py:600` — `get_current_workspace`
   verlangt beim API-Token-Pfad `token_workspace_id == workspace_id` aus dem
   Pfad. Korrekt so (Defense gegen Cross-Workspace-Token-Reuse).
2. `apps/mcp/src/who2be_mcp/server.py:259-299` — `_resolve_workspace_id` nimmt
   den Workspace fuer genau diesen Pfad **nicht aus dem Token**, sondern aus
   `GET /v1/me` → `default_workspace_id`.
3. `apps/api/src/who2be_api/repositories/me_repository.py:58,107` —
   `default_workspace_id` ist die **erste Membership-Zeile** des Users, sortiert
   nach `o.created_at ASC, o.id ASC, m.joined_at ASC, w.id ASC`. Die
   Token-Bindung geht dort ueberhaupt nicht ein.

Ein an Workspace B gepinnter Token wird also auf `/v1/workspaces/A/...`
geschickt und laeuft ins Gate. Betrifft deterministisch **jeden User mit >= 2
Workspaces, sobald der Zweit-Workspace nicht der aelteste ist**.

**Nebenfund:** `reason="forbidden_transition"` ist falsch gemappt — der Code ist
in `packages/models/src/who2be_models/errors.py:27` und
`apps/api/src/who2be_api/main.py:199` als „Unzulaessiger Status-Uebergang"
definiert und gehoert zur Version-State-Machine
(`apps/api/src/who2be_api/services/version_status.py:77`). Cross-Workspace-
Token-Reuse ist kein Status-Uebergang. Die Taxonomie verspricht, dass ein Agent
deterministisch auf `reason` verzweigen kann — hier bekommt er einen
irrefuehrenden Schluessel.

## Scope

Stufe 1 = Hotfix. Das Zielbild (Principal aus der Token-Introspektion,
Wegfall von Zweit-Call und Prozess-Cache, geteilter HTTP-Pool) ist **Stufe 2**
und laeuft als ADR-Entwurf, nicht in diesem PR.

### Out of Scope (Stufe 1)

- Introspektions-Endpunkt / `AccessToken`-Claims (→ ADR Stufe 2).
- Wegfall von `_WS_CACHE` und dem zweiten `/v1/me`-Call (→ Stufe 2).
- Geteilter `httpx.AsyncClient` mit Connection-Pool (→ Stufe 2).
- `/v1/me`-Semantik fuer `default_workspace_id` aendern (bewusst verworfen,
  s. u.).

## Verworfene Alternativen

- **`/v1/me` umbiegen** (`default_workspace_id = token_workspace_id` bei
  Token-Auth): das Feld haette je nach Auth-Modus zwei Bedeutungen, und
  `/v1/me` ist zugleich die Quelle fuer den Web-Redirect `/w/{id}` und den
  Workspace-Switcher. Zwei Consumer, ein Feld, zwei Wahrheiten.
- **`WHO2BE_WORKSPACE_ID` pinnen**: in der Cloud ein Isolationsfehler — ein
  Prozess bedient alle Tenants, der Pin gewinnt fuer *jeden* Caller. Wird in
  diesem PR unter `transport=http` sogar aktiv verboten.

## Arbeitspakete

### AP1 — API: Token-Workspace in `/v1/me` ausweisen

- `packages/models/src/who2be_models/me.py`: `MeRead.token_workspace_id:
  UUID | None = None` (additiv, Default `None` → kein Breaking Change fuer Web).
- `apps/api/src/who2be_api/services/me_service.py`: `fetch(user_id,
  token_workspace_id=None)` setzt das Feld auf dem Repository-Ergebnis.
- `apps/api/src/who2be_api/routers/me.py`: Dependency von `get_current_user`
  auf `get_current_principal` umstellen, `principal.token_workspace_id`
  durchreichen. `DELETE /v1/me` bleibt unveraendert auf der User-ID.

### AP2 — API: eigener Taxonomie-Code fuer den Workspace-Mismatch

- `packages/models/src/who2be_models/errors.py`: `ProblemReason` um
  `workspace_mismatch` erweitern.
- `apps/api/src/who2be_api/main.py`: Titel in `_PROBLEM_TITLES`.
- `apps/api/src/who2be_api/core/security.py:600-608`:
  `reason="workspace_mismatch"`, `actionable_by="human"` (der Aufrufer kann es
  nicht selbst beheben, ein Mensch schon: richtigen Connector/Token waehlen).

### AP3 — MCP: Workspace aus dem Token bevorzugen + Pin-Guard

- `apps/mcp/src/who2be_mcp/server.py`: `_resolve_workspace_id` liest
  `token_workspace_id` und faellt nur ohne Token-Bindung (JWT) auf
  `default_workspace_id` zurueck.
- `apps/mcp/src/who2be_mcp/config.py`: `Settings`-Validator — `workspace_id`
  zusammen mit `transport="http"` ist ein Startup-Fehler (Multi-Tenant-Schutz).

### AP4 — Doku

- `CHANGELOG.md` (Unreleased): Fixed-Eintraege fuer den Workspace-Mismatch,
  den neuen `reason`-Code und den Pin-Guard.
- Repo-Memory: `STATE.md` + `DECISIONS.md`.

## Acceptance Criteria

1. Ein an Workspace B gepinnter Token spricht ueber den MCP-Server
   `/v1/workspaces/B/...` an — unabhaengig davon, welcher Workspace der
   aelteste des Users ist.
2. `GET /v1/me` traegt bei Token-Auth `token_workspace_id`; bei JWT-Auth
   bleibt es `None`, `default_workspace_id` unveraendert.
3. Cross-Workspace-Token-Reuse antwortet mit `reason="workspace_mismatch"`,
   `actionable_by="human"`, weiterhin 403.
4. `WHO2BE_WORKSPACE_ID` + `transport=http` bricht beim Start ab.
5. `uv run ruff check .`, `uv run mypy .`, `uv run pytest --cov
   --cov-fail-under=85` gruen.

## Verifikation

`uv run ruff check . && uv run ruff format --check . && uv run mypy . &&
uv run pytest --cov --cov-fail-under=85`

Web ist nicht betroffen (kein `apps/web`-Diff) — der Web-Stack wird nicht
angefasst.

## Uebergabe-Bericht

### (a) Betroffene Software-Elemente (per ripgrep rueckwaerts gesucht)

**DIREKT**

- `MeService.fetch` — 1 Aufrufer: `routers/me.py::get_me`.
- `MeRead` — konstruiert in `repositories/me_repository.py:109`, Response-Modell
  in `routers/me.py`. Feld ist additiv mit Default `None`.
- `get_current_workspace` — FastAPI-Dependency; nur der Fehlerzweig geaendert,
  keine Signatur.
- `_resolve_workspace_id` (MCP) — 1 Aufrufer: `server.py::build_client`.
- `Settings` (MCP) — neuer Validator; greift ueber `get_settings` beim Start.
- `ProblemReason` — konsumiert von `core/errors.py::ApiGateError`.

**TRANSITIV**

- Jeder `/v1/workspaces/...`-Endpunkt haengt an `get_current_workspace` — die
  Aenderung ist dort aber rein im Fehlerpfad (Status 403 unveraendert, nur
  `reason`/`actionable_by` neu).
- Jedes MCP-Tool haengt ueber `build_client` an `_resolve_workspace_id`.

**VERMUTET (unsicher, Laufzeit-Verdrahtung)**

- `apps/web/src/api/client.ts` — der TS-`Me`-Typ kennt `token_workspace_id`
  nicht. Eine strict-Validierung (zod `.strict()`) war in `apps/web/src/api/`
  nicht auffindbar, ein zusaetzliches Feld sollte also folgenlos sein. Nicht
  ausgefuehrt verifiziert (kein Web-Diff, Web-Suite nicht Teil dieses PR).
- Betreiber-Environments ausserhalb des Repos, die `WHO2BE_WORKSPACE_ID`
  zusammen mit `WHO2BE_TRANSPORT=http` setzen, brechen ab sofort beim Start ab.
  Im Repo (`deploy/`, Compose-Dateien, `.env.example`) kommt die Variable nicht
  vor — gewollter, lauter Fehlschlag statt stiller Tenant-Verletzung.

### (b) Rest-Test-Liste

**Diff-Coverage: nicht messbar in dieser Umgebung.** Die Sandbox hat keinen
Docker-Daemon und keine erreichbare Postgres — 448 Integrationstests werden
zentral uebersprungen (`conftest.py`), die Gesamt-Coverage faellt dadurch auf
63,07 % und das 85-%-Gate schlaegt an. Das ist eine Eigenschaft der Umgebung,
nicht des Diffs: **CI muss das Gate bestaetigen.** Unit-seitig gruen:
1300 passed, 448 skipped.

Neu abgedeckt: `_resolve_workspace_id` (Token-Vorrang + JWT-Fallback),
`Settings._reject_workspace_pin_on_http`, der Workspace-Mismatch-Zweig in
`get_current_workspace`, `MeService.fetch` (beide Pfade) und die Vollstaendigkeit
der `_PROBLEM_TITLES`-Tabelle.

Ungedeckt und manuell zu pruefen:

- `routers/me.py::get_me` — die Verdrahtung `principal.token_workspace_id` →
  `service.fetch` laeuft nur ueber DB-gestuetzte Integrationstests
  (`test_me.py`, hier uebersprungen). Manuell: `GET /v1/me` einmal mit
  `w2b_`-Token (Feld gesetzt, gleich der Token-Bindung) und einmal mit JWT
  (Feld `null`, `default_workspace_id` unveraendert).
- End-to-End nicht verifizierbar ohne laufenden Stack: ein Connector auf einen
  Zweit-Workspace muss `whoami` erfolgreich beantworten — das ist der
  Abnahme-Fall aus dem Anlass.

### Nebenbefund (nicht von diesem Diff verursacht)

`docs/reference/openapi.json` war bereits **stale**: die Regenerierung zieht
neben dem neuen `token_workspace_id`-Feld auch `OAuthConsentApprove.agent_id`
nach (optional statt required, aus #404). Die Datei ist generiert
(`scripts/export_openapi.py`) und laesst sich nicht sinnvoll teil-regenerieren —
der Nachzug bleibt daher im PR, ist aber fremd zum eigentlichen Fix. Dass die
Drift ueberhaupt entstehen konnte, heisst: kein CI-Gate prueft die eingecheckte
Spec gegen die App. Kandidat fuer den WP-14-Backlog.
