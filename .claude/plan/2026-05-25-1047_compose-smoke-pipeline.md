# Plan — App-Smoke via Docker Compose + CI-Pipeline

## Context

**Warum jetzt:** Notion-Projekt PROJ-19 (Who2Be) ist code-seitig durch MS-1: API hat volles Persona/Playbook/Token-CRUD, Web hat Auth-Routing + CRUD-Pages, MCP hat 4 Tools, 75/6 Pytest + 24/24 Vitest grün. Die offene Stelle ist die Abnahme der lokalen Smoke-Checkliste (`docs/local-smoke.md`) — heute Drei-Terminal-Setup (Postgres-Stub via Compose, `uv` für API+Migrations, `npm` für Web) plus Supabase-Cloud-Projekt für Login plus manuelle Browser-Klicks. Der User möchte stattdessen: (a) die App per **`docker compose up`** ausprobieren, (b) eine **Pipeline** haben, die das automatisiert verifiziert.

**Designentscheidungen (User-bestätigt):**
1. **Self-hosted Supabase in Compose mit reinziehen** — Vorgriff auf MS-2 C1-C6 (Hetzner-Deploy + self-hosted Supabase). Keine Cloud-Abhängigkeit mehr für den lokalen Smoke.
2. **Pipeline-Tiefe:** lokaler 1-Befehl-Run + neuer CI-Job `compose-smoke` (curl-basiert, kein Browser). Playwright-E2E bleibt für später.
3. **Web im Compose:** Vite dev-server mit Hot-Reload (Volume-Mount, `HOST=0.0.0.0`, Port 5173).

**Outcome:** `docker compose up -d --wait` bringt Postgres + GoTrue (Supabase Auth) + API + MCP + Web hoch; `scripts/smoke.sh` verifiziert /v1/health, MCP-Tool-Listing, Web-Index. CI fährt denselben Smoke gegen denselben Stack. Constraint aus PROJ-19 ist gewahrt: Mono-Repo, FastAPI/FastMCP/Supabase/React-Stack bleiben unverändert. Vorgriff auf MS-2 C1-C6 wird im Notion-Doku-Log explizit vermerkt, damit die C-Tasks dort entsprechend angepasst werden können.

---

## Scope — was sich ändert

### Neu

- `apps/api/Dockerfile` — Python 3.11-slim + `uv sync --frozen` (multi-stage: builder/runtime), `uvicorn who2be_api.main:app --host 0.0.0.0 --port 8000`.
- `apps/mcp/Dockerfile` — analog, Entry: `python -m who2be_mcp.server`. (Standalone Container nur, falls wir MCP-HTTP-Transport nachrüsten; sonst optional — siehe "Offen".)
- `apps/web/Dockerfile` — Node 22-slim, `npm ci`, default `npm run dev -- --host 0.0.0.0`.
- `scripts/smoke.sh` — Bash-Wrapper: warte auf `/v1/health` mit `db:"ok"`, prüfe Vite-Index liefert 200, MCP-Tool-Liste (in-process via `python -c`).
- `scripts/gen_test_jwt.py` — kleines Helper-Skript, das ein HS256-JWT mit dem konfigurierten `JWT_SECRET` baut (für CI-Smoke ohne echten Supabase-Login).
- `supabase/` — Init-SQL für Supabase-Auth-Schema (oder offizielles Volume-Mount-Verzeichnis aus `supabase/docker`). Detail siehe "Supabase-Minimalset" unten.
- `.github/workflows/ci.yml` — neuer Job `compose-smoke` (siehe Pipeline-Sektion).

### Geändert

- `docker-compose.yml` — Erweiterung von Postgres-Stub auf Voll-Stack:
  - `db` (Postgres 16 mit Supabase-Schema-Init).
  - `auth` (`supabase/gotrue:v2.x` — die Login-Backend-Komponente).
  - `migrate` (Init-Container `apps/api`-Image, läuft `who2be-migrate` und exit; andere Services hängen über `depends_on: { migrate: { condition: service_completed_successfully } }`).
  - `api` (apps/api).
  - `mcp` (apps/mcp — stdio-only; optionaler Service, sinnvoll erst mit HTTP-Transport, siehe "Offen").
  - `web` (apps/web, Vite dev-server, Volume-Mount für Hot-Reload).
  - Healthchecks pro Service: `pg_isready` für db, HTTP `/health` für gotrue, HTTP `/v1/health` für api, HTTP `/` für web.
- `.env.example` — neue Variablen:
  - `GOTRUE_JWT_SECRET` (= `JWT_SECRET`, identisch verwenden).
  - `GOTRUE_SITE_URL=http://localhost:5173`.
  - `GOTRUE_DISABLE_SIGNUP=false` (für lokale Test-User).
  - `VITE_SUPABASE_URL=http://localhost:9999` (direkter GoTrue-Port — Kong-Gateway sparen wir uns für MS-2).
  - `VITE_SUPABASE_ANON_KEY=<dev-anon-key>` — Default-Wert für lokale Entwicklung, in `.env.example` ausgewiesen als nicht-prod.
- `docs/local-smoke.md` — auf neue 1-Befehl-Variante umschreiben: Abschnitt "Voraussetzungen" verliert die Supabase-Cloud-Punkte, Abschnitt 2 wird zu `cp .env.example .env && docker compose up -d --wait && bash scripts/smoke.sh`. Browser-Happy-Path bleibt manuell.
- `apps/web/src/api/config.ts` — keine Code-Änderung; nur `.env.example`-Defaults verschieben sich.

### Nicht angefasst

- Architekturschichten (routers/services/repositories), ADRs 0001-0006.
- CRUD-Code in API/MCP/Web.
- Bestehende Pytest/Vitest-Suiten (laufen weiter wie bisher; CI-Job `python` / `web` bleibt unverändert).

---

## Supabase-Minimalset (self-hosted)

Volle Supabase-Compose hat ~10 Services (db, auth/gotrue, rest/postgrest, realtime, storage, imgproxy, edge-functions, studio, kong, vector). Für unser MS-1-Smoke-Bedürfnis ist nur **Auth** echtes Pflicht-Backend (Web-Login). Minimalset:

- **db** (Postgres 16, mit init-sql für `auth`-Schema, Migration-Skripte aus `supabase/docker/volumes/db/init/`).
- **auth** (`supabase/gotrue` — Email/Password-Login).
- *(Optional, später)* studio + kong fürs Web-Admin-UI.

Der Web-Code spricht heute `supabase-js.auth.signInWithPassword`, das callt `${VITE_SUPABASE_URL}/auth/v1/token?grant_type=password`. Wenn wir Kong weglassen, muss `VITE_SUPABASE_URL` GoTrue direkt erreichen (`http://localhost:9999`) und der Web-Client-Pfad `/auth/v1/...` matched dort.

**Verifizierungs-Schritt im Plan:** vor dem Compose-Schreiben einen kurzen Smoke gegen GoTrue lokal (`curl http://localhost:9999/health`) machen, um zu bestätigen, dass die Pfad-Annahme stimmt. Falls supabase-js doch zwingend Kong erwartet, ziehen wir Kong nach (zusätzlicher Service, +50 Zeilen Config).

---

## Pipeline (CI-Job `compose-smoke`)

Neuer Job in `.github/workflows/ci.yml`:

```yaml
compose-smoke:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Compose up
      run: |
        cp .env.example .env
        docker compose up -d --wait --wait-timeout 120
    - name: Smoke
      run: bash scripts/smoke.sh
    - name: Logs on failure
      if: failure()
      run: docker compose logs --no-color
```

`scripts/smoke.sh` (Skizze):
1. `curl -fsS http://localhost:8000/v1/health | jq -e '.db == "ok"'`
2. `curl -fsS http://localhost:5173/ | grep -q "<title>"`
3. **JWT-basiert** (kein Supabase-Login im CI): `python scripts/gen_test_jwt.py` → Token → `curl -H "Authorization: Bearer …" http://localhost:8000/v1/personas` → Liste leer, aber 200.
4. MCP-Tools verifizieren: `docker compose exec api python -c "from who2be_mcp.server import mcp; import asyncio; print(asyncio.run(mcp.list_tools()))"` und auf 4 Tools prüfen (`ping`, `get_persona`, `list_playbooks`, `fetch_playbook`).

→ Kein Browser, kein Supabase-Login im CI nötig. JWT_SECRET kommt aus `.env.example` (Dev-Wert, ausschließlich Test-Zweck).

---

## Verifikation (Definition of Done für diesen Plan)

End-to-end-Smoke auf der Workstation:

1. **Frische Checkout-Simulation:** `git stash && cp .env.example .env`.
2. **Stack starten:** `docker compose up -d --wait --wait-timeout 180` — alle Services werden healthy gemeldet.
3. **API-Health:** `curl -s http://localhost:8000/v1/health` → `{"status":"ok","db":"ok"}`.
4. **Web-Index:** Browser auf `http://localhost:5173`, Login-Page rendert.
5. **Auth-Smoke** (manuell, einmalig): in Supabase-Studio (oder via GoTrue-API per curl) Test-User anlegen → einloggen → Persona anlegen → Versions-Bump → Playbook anlegen → verknüpfen. Genau die `docs/local-smoke.md`-Checkliste, jetzt ohne Cloud-Abhängigkeit.
6. **MCP-Smoke:** `docker compose exec api python -c "..."` (oder lokal `uv run python -m who2be_mcp.server` mit `WHO2BE_API_BASE_URL=http://localhost:8000`) — `ping`, `get_persona`, `list_playbooks`, `fetch_playbook` antworten.
7. **CI-Lauf:** PR pushen, `compose-smoke`-Job grün.
8. **Bestehende Suiten:** `uv run pytest -q` weiter 75/6, `cd apps/web && npm test` weiter 24/24.

---

## Kritische Dateien (Pointer)

| Datei | Aktion | Hinweis |
|---|---|---|
| `docker-compose.yml` | erweitern | aktuell nur Postgres-Stub |
| `apps/api/Dockerfile` | neu | uv-multi-stage |
| `apps/web/Dockerfile` | neu | Node 22, Vite dev |
| `apps/mcp/Dockerfile` | neu | optional bis MCP-HTTP-Transport |
| `scripts/smoke.sh` | neu | curl + jq, ausführbar |
| `scripts/gen_test_jwt.py` | neu | HS256 mit JWT_SECRET, 1h Gültigkeit |
| `supabase/init/*.sql` | neu | offizielle init-Scripts vendoren |
| `.env.example` | erweitern | GoTrue-Vars + dev-anon-key |
| `.github/workflows/ci.yml` | erweitern | Job `compose-smoke` |
| `docs/local-smoke.md` | anpassen | 1-Befehl statt 3 Terminals |
| `apps/api/src/who2be_api/main.py` | unverändert | CORS bereits drin (F1/F6) |
| `apps/api/src/who2be_api/core/config.py` | unverändert | `DATABASE_URL`/`JWT_SECRET`/`CORS_ORIGINS` schon vorhanden |

---

## Wiederverwendete Bausteine

- `who2be-migrate` Console-Script (`apps/api/src/who2be_api/core/migrations.py`) — wird im Init-Container 1:1 aufgerufen, kein neuer Code.
- `Settings.cors_origins: list[str]` (in `core/config.py`, nach F6 als CSV-Parser) — Compose setzt `CORS_ORIGINS=http://localhost:5173`.
- Bestehender Postgres-16-Service in `docker-compose.yml` — wird zum Voll-DB-Service erweitert (Volume-Mount + init.d).
- `apps/api/tests/test_health.py` Health-Shape (`{status, version, db}`) — `smoke.sh` matched genau diese Form.

---

## Reihenfolge der Implementierung

1. **Notion-Projekt:** kurzen Eintrag in PROJ-19 `## Notes` ankündigen — "Compose-Pipeline + self-hosted-Supabase als Vorgriff auf MS-2 C1-C6" — und einen Task in der Tasks-DB anlegen (Title z.B. "Local-Smoke via docker compose + CI-Job"), als Beleg/Anker.
2. **Dockerfiles** (api, web, optional mcp). Lokal einzeln bauen, smoke-test.
3. **Compose erweitern** ohne Supabase-Auth: db + migrate + api + web. `scripts/smoke.sh` v0 + lokaler Lauf.
4. **GoTrue dazu** + `.env.example` + Web-Anbindung verifizieren (Login gegen Container).
5. **CI-Job** `compose-smoke` + `scripts/gen_test_jwt.py`.
6. **`docs/local-smoke.md`** umschreiben.
7. **Notion-Doku-Log** schreiben (Coder-Phase 3): Change-Log in PROJ-19 `## Notes`, Pointer auf den Plan, MS-2 C1-C6 Tasks updaten (welche Vorarbeit jetzt schon im Compose lebt).

---

## Offene Punkte / bewusst aufgeschoben

- **MCP-Container:** macht erst Sinn, wenn FastMCP einen HTTP-Transport bekommt. Heute stdio-only → Container wäre nur für `docker compose exec mcp ...` interaktiv. Vorschlag: MCP-Service im Compose-File auskommentiert/dokumentiert ablegen, aber nicht aktiv starten.
- **Kong-Gateway:** Falls supabase-js direkt-GoTrue nicht akzeptiert, Kong nachschieben (+1 Service, +Config).
- **Playwright-E2E:** vom User explizit auf später vertagt (eigene Iteration).
- **Volume-Mount Web in CI:** im CI bauen wir das Image frisch und mounten nicht — Hot-Reload-Verhalten lokal only.
- **Supabase-Studio:** weggelassen für MS-1-Smoke; bei Bedarf später als optionaler Service nachreichbar.
