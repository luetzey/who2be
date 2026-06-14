# Plan: MS-3 H3 — Security-Review-Pass

## Context

Stand: MS-3 H1 (Rate-Limiting, PR #9) und H2 (strukturierte JSON-Logs, PR #11)
sind gemergt. H3 ist gemaess Roadmap (`.claude/plan/2026-05-24_who2be-mvp-roadmap.md`
§MS-3) sequentiell nach H1/H2 vorgesehen, damit der Review den finalen
Hardening-Stand sieht. Outcome-Definition aus der Roadmap:

> `security-reviewer`-Subagent geprueft: Auth-Pfad, SQL-Statements, Token-Hashing,
> CORS, Input-Validierung. Findings entweder behoben oder in
> `docs/security-findings.md` mit Risikoeinschaetzung dokumentiert und vom User
> abgenommen.

H4 (Backup-Restore-Drill) ist durch MS-2 (Hetzner-Deploy) blockiert, H3 ist es
nicht — reiner Code-/Doku-Pass auf dem bestehenden Repo.

## Approach

Drei-Phasen-Schleife passend zur Coder-Methode:

1. **Discover** — `security-reviewer`-Subagent (definiert in `.claude/agents/`,
   Sprache deutsch, Scope FastAPI-Backend + React-Frontend) laeuft im
   Read-only-Modus ueber den genannten Scope. Kein Code-Edit im Subagent,
   nur Findings als strukturierter Report.
2. **Triage** — Findings nach Severity (Critical / High / Medium / Low / Info)
   einsortieren. Hochrisiko → patchen, Mittel/Niedrig → in
   `docs/security-findings.md` mit Risikoeinschaetzung + Followup-Hinweis
   abgelegt; Info-Notizen optional dort als Anhang.
3. **Document** — `docs/security-findings.md` neu anlegen (Template orientiert
   an ADR-Format: Stand, Scope, Methodik, Findings-Tabelle, Patches,
   Akzeptanz-Block fuer User-Abnahme).

## Scope (vom security-reviewer zu pruefen)

Gemaess Roadmap-Outcome und Code-Realitaet:

- **Auth-Pfad:** `apps/api/src/who2be_api/core/security.py` (JWT-Verifikation,
  Token-Hashing, `get_current_user`), `apps/api/src/who2be_api/routers/tokens.py`.
- **SQL-Statements / DB-Zugriff:** `apps/api/src/who2be_api/repositories/*`
  (asyncpg, parametrisierte Queries), `apps/api/src/who2be_api/core/db.py`,
  Migrations unter `apps/api/src/who2be_api/migrations/*.sql`.
- **Token-Hashing & Token-Lifecycle:** `core/security.py:hash_api_token` (oder
  Aequivalent), `routers/tokens.py` (Klartext nur einmal raus, Revoke-Pfad).
- **CORS & Security-Header:** `apps/api/src/who2be_api/main.py` (CORS-Middleware,
  Rate-Limit-Integration, Logging-Middleware).
- **Input-Validierung:** Pydantic-Models in `packages/models/`, Router-Signaturen,
  `Path`/`Query`-Constraints.
- **MCP-Adapter:** `apps/mcp/src/who2be_mcp/client.py` (Token-Forwarding,
  Fehlerleckage), `apps/mcp/src/who2be_mcp/server.py` (Tool-Inputs).
- **Web-Frontend (defensiv):** `apps/web/src/api/client.ts` (Auth-Header,
  Token-Speicherung), `apps/web/src/auth/*`, evtl. XSS-Vektoren in
  Editor-Pages.
- **Rate-Limit + Logging:** Konfigurations-Defaults aus H1/H2 — kein
  versehentliches Loggen von Secrets/Tokens/Bodies.

Bewusst out of scope:
- Penetration-Testing oder Fuzzing (kein Live-Target).
- Browser-/CSP-Hardening (gehoert zu MS-2 Reverse-Proxy/Caddyfile).
- Infrastruktur-/Deploy-Pfad (MS-2).
- Dependency-CVE-Scan (`npm audit` / `pip-audit`) — eigene Task, falls
  Findings das nahelegen.

## File-by-file Changes

### 1. `docs/security-findings.md` — NEU

Struktur:

```
# Security-Review — Stand 2026-05-25 (MS-3 H3)

## Scope
## Methodik
## Findings
| ID  | Severity | Bereich | Titel | Status |
| --- | -------- | ------- | ----- | ------ |
| F-01 | High     | Auth    | ...   | Fixed  |
| F-02 | Medium   | CORS    | ...   | Docs   |
## Detail je Finding
### F-01 — Titel
- **Bereich / Datei:Zeile**
- **Beschreibung**
- **Risiko**
- **Empfehlung / Patch**
- **Status** (Fixed in commit `<hash>` / Akzeptiert mit Rationale / Followup)
## Akzeptanz
```

### 2. Punkt-Patches (nur wenn Findings das verlangen)

Wahrscheinlich-betroffene Stellen — abhaengig vom Subagent-Report:
- `apps/api/src/who2be_api/core/security.py` (Auth-Logik / Constant-Time-Compare).
- `apps/api/src/who2be_api/main.py` (CORS-Defaults, Security-Header,
  Logging-Felder).
- `apps/api/src/who2be_api/routers/*.py` (Owner-Check, 404 vs. 403, Input-Limits).
- `apps/api/src/who2be_api/core/logging.py` (Sicherstellen: kein Token im Log).
- `apps/api/src/who2be_api/core/middleware.py` (Request-ID-Eingang sanitisieren).

Bei jedem Patch:
- Zuerst reproduzierender Test (falls automatisierbar) — `apps/api/tests/`.
- Dann Fix.
- Findings-Eintrag updaten (`Status: Fixed in commit <hash>`).

### 3. `docs/architecture.md` — optional

Falls neue Security-Note entsteht (z. B. CSP-Plan fuer MS-2), kurzer
Verweis-Absatz unter §Observability / §Security.

## Wiederverwendung (nicht neu erfinden)

- `security-reviewer`-Subagent-Definition (`.claude/agents/security-reviewer.md`)
  — kein Code-Edit, nur Read/Grep/Glob/Bash.
- Findings-Template am ADR-Aufbau orientieren (Kontext / Bewertung / Entscheidung).
- Test-Pattern aus `apps/api/tests/test_rate_limit.py` (TestClient + DB-Skip)
  fuer Auth-Tests.
- `structlog.testing.capture_logs()` (aus H2) zum Verifizieren, dass keine
  Tokens/Secrets im Log auftauchen.

## Verifikation

1. **Subagent-Run:** `security-reviewer` ueber den oben definierten Scope,
   Output als strukturierter Bericht.
2. **Triage-Doku:** `docs/security-findings.md` existiert, fuer jedes Finding
   Severity + Status; alle Hochrisiko-Findings haben Status `Fixed` oder
   ausdruecklich-akzeptiert mit Rationale.
3. **Tests:** `uv run pytest -q` gruen, inkl. ggf. neuer Auth-/Logging-Tests.
4. **Lint+Type:** `uv run ruff check . && uv run ruff format --check . &&
   uv run mypy .` gruen.
5. **Web-Stack:** falls Frontend-Patches noetig — `npm run lint &&
   npx tsc --noEmit && npm test` in `apps/web/`.
6. **User-Abnahme:** Akzeptanz-Block in `docs/security-findings.md` zeigt
   "User-Sign-Off pending" → User entscheidet pro offenes Finding ob OK.

## Out of Scope (bewusst)

- Penetrationstest gegen Live-Instanz (MS-2 nicht fertig).
- Dependency-CVE-Scan (`npm audit` / `pip-audit`) — eigene Task, optional.
- CSP / HSTS / Security-Header am Reverse-Proxy — gehoert zu MS-2.
- Multi-Tenancy / Rollen-Modell — Out of Scope MVP per ADR-0006.
- Audit-Log-Persistierung — kuenftige Hardening-Iteration.
