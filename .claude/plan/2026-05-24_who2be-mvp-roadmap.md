# Who2Be — Vollstaendiger Phasenplan zum MVP

> Projekt-Blueprint-Output (Coder, Playbook V1.2).
> Notion-Projekt: PROJ-19 "Who2Be" (`364be537-2ab8-81ff-94e5-e8827c2228a4`).
> Architektur-Fundament: `docs/architecture.md` + 6 ADRs (Stand 2026-05-21) —
> wird hier NICHT wiederholt, nur referenziert.
>
> Hand-Off: 4 Milestones + 20 Tasks am 2026-05-24 in Notion angelegt
> (Milestones-DB `299d9d7d-5b70-421d-95f1-3c66c00759a7`, Tasks-DB
> `ba2ecc7c-4e1d-4132-9212-f554a85ddf5d`).

## Context

Why jetzt: API, MCP-Tools, Auth-Infrastruktur, Migrations und Web-Scaffold sind
implementiert (Straenge 1-6 der Roadmap aus `docs/architecture.md`, Phase 0/1/2
groesstenteils umgesetzt). Was zum MVP-Outcome — "Brainstormer-Stack laeuft
komplett auf Who2Be statt aus Notion" — fehlt, ist nicht mehr Architektur,
sondern: eine bedienbare Web-UI (heute nur Scaffold), die produktive
Hetzner-Instance mit self-hosted Supabase, ein Hardening-Pass und die
eigentliche Brainstormer-Migration als End-to-End-Verifikation.

Dieser Plan zerlegt diesen Rest in vier geordnete Milestones mit
ueberpruefbarem Zwischen-Outcome und schneidet pro Milestone die Tasks
entlang disjunkter Datei-Scopes (parallel-tauglich, Code-Task-Flow-Overlap-Check).

## Architektur-Referenz (unveraendert, nicht neu entscheiden)

- Modularer Monolith, geschichtet (`routers/ → services/ → repositories/`) —
  `docs/architecture.md` §2, ADR-0001/0002.
- Raw asyncpg + nummerierte SQL-Migrationen — ADR-0003,
  `apps/api/src/who2be_api/core/db.py`, `core/migrations.py`.
- Versionierung ueber `persona_version` / `playbook_version` History-Tabellen —
  ADR-0004, Migrations `0002_persona.sql` / `0003_playbook.sql`.
- MCP-Server = HTTP-Adapter zur API — ADR-0005, `apps/mcp/src/who2be_mcp/client.py`.
- Dual-Auth: Supabase-JWT (HS256, `JWT_SECRET`) + eigene API-Token-Tabelle
  (SHA-256-Hash, `w2b_`-Praefix) — ADR-0006, `apps/api/src/who2be_api/core/security.py`.

Alle wiederverwendbaren Bausteine fuer die folgenden Milestones existieren
bereits im Repo: `core/config.py`, `core/db.py`, `core/security.py`,
`core/migrations.py`, alle Pg*-Repositories, alle Services, der httpx-MCP-Client
sowie auf der Web-Seite `auth/SessionProvider`, `api/client` (typed `createApi`),
`hooks/usePersonas`, `hooks/usePlaybooks`. Nichts davon wird neu erfunden.

## Aktueller Stand (Was bereits steht)

- `/v1` REST-Endpoints fuer Health, Tokens, Personas, Playbooks und
  Persona-Playbook-Links (Routers + Services + Repositories durchgaengig).
- Migrations `0001_api_token`, `0002_persona`, `0003_playbook`,
  `0004_persona_playbook` + idempotenter Runner `who2be-migrate`.
- MCP-Tools `ping`, `get_persona`, `list_playbooks`, `fetch_playbook` gegen
  die API.
- Web-Scaffold: React-Router-Routen, `SessionProvider`, typisierter API-Client,
  Page-Stubs (`LoginPage`, `PersonasPage`, `PlaybooksPage`, Detail-Stubs).
- Tests: ~1300 Zeilen API/Models, drei Web-Unit-Tests, CI mit Postgres-Service
  in `.github/workflows/ci.yml`.

Was offen ist (Lueckenliste vs. Acceptance Criteria):

| AC | Anteil offen |
|---|---|
| AC1 (Login + API-Token) | Web-Seite **Tokens** + Bruecke Supabase-Session → API-Auth-Header (Web nutzt heute Supabase-JWT direkt). |
| AC2 (CRUD + Versionen per Web) | Editor-Pages + Versions-Liste; heute nur Stubs. |
| AC3 (MCP fuer Brainstormer) | Code steht; gegen produktive Instanz noch nicht verifiziert. |
| AC4 (Brainstormer auf Who2Be) | Hetzner-Deploy + Migration + Claude-Chat-Smoke. |

## Milestone-Roadmap

Vier Milestones in strikter Reihenfolge — jede Phase produziert ein
ueberpruefbares Outcome, das die jeweils naechste Phase voraussetzt.
Schema je Task: **Outcome** (was muss gelten, damit die Task done ist),
**Context** (betroffene Dateien — disjunkt zu Geschwister-Tasks fuer Concurrency).

Notion-Links: MS-1 `36abe537-2ab8-81ce-9343-c514ce3c8c3d` ·
MS-2 `36abe537-2ab8-81df-b831-cf19269528da` ·
MS-3 `36abe537-2ab8-819e-be2b-fadc2e04f51b` ·
MS-4 `36abe537-2ab8-817d-8a36-ce600564779f`.

---

### MS-1 — Web-UI Minimal-funktional (Order 1)

**Outcome:** Ein angemeldeter User kann ueber die Web-UI vollstaendig Personas,
Playbooks und API-Tokens verwalten (Anlegen / Editieren erzeugt neue Version /
Verknuepfen / Versionsliste einsehen / Token erstellen+revoken). `npm run build`
und `npm test` gruen; Vitest deckt mindestens einen Happy-Path pro Page ab.
Keine Stilreferenz — "Funktion vor Schoenheit" gilt.

Scope-Entscheidung: **Minimal-funktional** (Textarea-Editor + Tag-/Trigger-Chips
+ Read-only Versions-Liste). Kein Markdown-Preview, kein Diff (siehe
`Out-of-Scope MS-1` unten).

**Tasks:**

1. **W1 — Auth-Bridge Supabase-Session ↔ API-Token**
   - Outcome: API-Calls aus dem Web tragen ein gueltiges `Authorization`-Bearer,
     das die API per `get_current_user` akzeptiert. Token-Quelle: Supabase-JWT
     (Default) ueber `session.access_token`; UI bietet im Settings-Bereich
     zusaetzlich `w2b_`-Token-Login (fuer kuenftige Headless-Use-Cases).
   - Context: `apps/web/src/auth/SessionProvider.tsx`,
     `apps/web/src/api/client.ts`, neu `apps/web/src/auth/useAuthToken.ts`.
   - Hinweis: `JWT_SECRET` in API muss mit Supabase-Project-JWT-Secret
     uebereinstimmen (Settings-Doku in `.env.example` ergaenzen).

2. **W2 — Token-Verwaltungsseite**
   - Outcome: `/settings/tokens` listet eigene Tokens, erlaubt Anlage (Klartext
     wird genau einmal als Copy-Banner gezeigt) und Revoke. Vitest: ein
     Render-/Submit-Test.
   - Context: neu `apps/web/src/pages/SettingsTokensPage.tsx`, neu
     `apps/web/src/hooks/useTokens.ts`, Eintrag in
     `apps/web/src/App.tsx` (Route) — keine Ueberlappung mit W3/W4.

3. **W3 — Persona-Editor + Versionsliste**
   - Outcome: `/personas` listet, `/personas/new` legt an, `/personas/:id`
     zeigt aktuelle Version + Editor (PUT → neue Version) + Read-only-Liste
     `GET /v1/personas/{id}/versions`. Vitest: Create-Flow + Version-Bump-Flow.
   - Context: `apps/web/src/pages/PersonasPage.tsx`,
     `apps/web/src/pages/PersonaDetailPage.tsx`,
     neu `apps/web/src/pages/PersonaNewPage.tsx`,
     `apps/web/src/hooks/usePersonas.ts`. Nutzt vorhandenen `createApi`-Client
     und `PersonaRead`/`PersonaCreate`/`PersonaUpdate` aus
     `apps/web/src/api/types.ts`.

4. **W4 — Playbook-Editor + Tag-/Trigger-Felder + Versionsliste**
   - Outcome: analog W3 fuer Playbooks; Tag-Chips (string[]) und
     Trigger-Textfeld werden bei Save mit gesendet. Listenseite filtert client-
     seitig nach Tag/Trigger (server-seitiger Filter wird in MS-4 B3 verifiziert).
   - Context: `apps/web/src/pages/PlaybooksPage.tsx`,
     `apps/web/src/pages/PlaybookDetailPage.tsx`,
     neu `apps/web/src/pages/PlaybookNewPage.tsx`,
     `apps/web/src/hooks/usePlaybooks.ts`.

5. **W5 — Persona↔Playbook-Verknuepfung im Persona-Detail**
   - Outcome: Im Persona-Detail erscheinen die verknuepften Playbooks
     (`GET /v1/personas/{id}/playbooks`), ein Multi-Select setzt die Liste
     ueber `PUT /v1/personas/{id}/playbooks`.
   - Context: nur `apps/web/src/pages/PersonaDetailPage.tsx` +
     neu `apps/web/src/hooks/usePersonaPlaybooks.ts`. (Disjunkt zu W4.)

6. **W6 — Web-Smoke gegen lokale API**
   - Outcome: Ein `docs/local-smoke.md` beschreibt den Happy-Path (uvicorn +
     `npm run dev` + Supabase-Login + Persona/Playbook anlegen + MCP-`get_persona`
     liefert die Daten). Manuell abgehakt, Screenshots oder Transkript-Log
     beigelegt.
   - Context: nur `docs/local-smoke.md` — laeuft parallel zu W3/W4/W5, blockt
     MS-1-Abschluss bis "abgehakt".

**Out-of-Scope MS-1** (bewusst, Konsistenz mit Notion-Out-of-Scope):
- Kein Markdown-Preview, kein Versions-Diff, kein Restore-from-Version-Button.
- Kein CSS-Framework — Basic Inline-Styles oder einfaches `index.css` reichen.
- Kein Reset-Password-Flow (Supabase-UI nutzbar).

---

### MS-2 — Cloud-Deploy auf Hetzner mit self-hosted Supabase (Order 2)

**Outcome:** Eine erreichbare HTTPS-Instanz `https://api.<domain>` (FastAPI) und
`https://app.<domain>` (Web), gespeist von einer self-hosted Supabase-Instanz
auf Hetzner. Migrations sind in der Cloud angewandt; Smoke-Curl gegen
`/v1/health` antwortet `{"db":"ok"}`; ein Test-User kann sich registrieren und
einen API-Token anlegen.

**Tasks:**

1. **C1 — Hetzner-Setup (Server + Firewall + SSH-Hardening)**
   - Outcome: Ein Hetzner-CX-Server laeuft Ubuntu 24.04, Firewall offen nur
     fuer 22/80/443, SSH-Key-only, Login als nicht-root-Deploy-User dokumentiert.
   - Context: neu `deploy/hetzner/README.md` (Setup-Schritte), neu
     `deploy/hetzner/firewall.md`. **Infra-only, kein App-Code**.

2. **C2 — Self-hosted Supabase via Docker-Compose**
   - Outcome: Supabase-Compose laeuft (`supabase/docker`), Postgres-Volume
     persistiert, Auth + Studio erreichbar; Studio-Login-Doku abgelegt.
     `JWT_SECRET` aus Supabase ist im Secrets-File hinterlegt.
   - Context: neu `deploy/hetzner/supabase/docker-compose.yml` (Anpassung des
     Upstream), neu `deploy/hetzner/supabase/.env.template`. Loest die
     Phase-0-TODO im Root-`docker-compose.yml` (Stub) endgueltig ab.

3. **C3 — App-Compose (API + MCP + Web) + Reverse-Proxy**
   - Outcome: Caddy (oder Traefik) terminiert HTTPS via Lets-Encrypt auf zwei
     Subdomains; API-Container fuehrt beim Boot `who2be-migrate` aus; MCP-
     Container faehrt mit `WHO2BE_API_BASE_URL` auf die interne API-Adresse;
     Web-Container serviert das Vite-Build statisch.
   - Context: neu `deploy/hetzner/who2be/docker-compose.yml`,
     neu `apps/api/Dockerfile`, neu `apps/mcp/Dockerfile`,
     neu `apps/web/Dockerfile` (multi-stage Build → `nginx:alpine`),
     neu `deploy/hetzner/Caddyfile`. Disjunkt zu C2.

4. **C4 — CI/CD-Pipeline (Image-Build + Deploy via SSH)**
   - Outcome: `.github/workflows/deploy.yml` baut die drei Images auf
     ghcr.io/luetzey/who2be-* und triggert per SSH `docker compose pull && up -d`
     auf dem Hetzner-Host. Trigger: push auf `main` nach gruener CI.
   - Context: neu `.github/workflows/deploy.yml`, neu
     `deploy/hetzner/scripts/deploy.sh`. Nutzt vorhandenes
     `.github/workflows/ci.yml` als Voraussetzung (separater Job mit `needs:`).

5. **C5 — Backup + Restore (Postgres-Dump)**
   - Outcome: Ein Cron im Supabase-Compose dumpt Postgres taeglich nach
     `/var/backups/who2be`, halt 7 Tage; ein Restore-Drill ist in
     `deploy/hetzner/RUNBOOK.md` dokumentiert und einmal gegen leere Test-DB
     ausgefuehrt.
   - Context: neu `deploy/hetzner/RUNBOOK.md`, neu
     `deploy/hetzner/scripts/backup.sh`.

6. **C6 — End-to-End-Smoke gegen die produktive Instanz**
   - Outcome: Curl gegen `https://api.<domain>/v1/health` → 200,
     `POST /v1/tokens` mit echtem Web-Login-JWT funktioniert,
     `GET /v1/personas` antwortet leer aber 200. Eintrag im
     `deploy/hetzner/RUNBOOK.md`.
   - Context: nur `deploy/hetzner/RUNBOOK.md` (Smoke-Sektion).

---

### MS-3 — Hardening vor MVP-Abnahme (Order 3)

**Outcome:** Rate-Limiting greift auf Auth- und Mutating-Routen,
JSON-strukturierte Logs landen sammelbar im Container-stdout,
Restore-Drill ist live durchgefuehrt, `security-reviewer`-Subagent hat einen
Pass ohne offene Hochrisiko-Findings gemacht.

**Tasks:**

1. **H1 — Rate-Limiting (`slowapi`)**
   - Outcome: `POST /v1/tokens`, `POST /v1/personas`, `POST /v1/playbooks`,
     `PUT /v1/personas/{id}`, `PUT /v1/playbooks/{id}` und Login-Token-Exchange
     sind auf z.B. 30/min pro `owner_id` (bzw. IP fuer Pre-Auth) limitiert.
     Integrationstest belegt 429 nach Ueberschreitung.
   - Context: neu `apps/api/src/who2be_api/core/rate_limit.py`,
     Einbindung in `apps/api/src/who2be_api/main.py` + den genannten Routern
     (`routers/tokens.py`, `routers/personas.py`, `routers/playbooks.py`).

2. **H2 — Strukturierte JSON-Logs**
   - Outcome: API + MCP loggen JSON-Zeilen mit `request_id`, `owner_id`,
     `path`, `status`, `duration_ms`. `structlog` oder
     `logging.config.dictConfig`-Json — eine Wahl, im ADR-0007 festgehalten.
   - Context: neu `docs/adr/0007-strukturierte-logs.md`, neu
     `apps/api/src/who2be_api/core/logging.py`, Integration in
     `apps/api/src/who2be_api/main.py` und
     `apps/mcp/src/who2be_mcp/server.py`. Disjunkt zu H1.

3. **H3 — Security-Review-Pass**
   - Outcome: `security-reviewer`-Subagent geprueft: Auth-Pfad, SQL-Statements,
     Token-Hashing, CORS, Input-Validierung. Findings entweder behoben oder
     in `docs/security-findings.md` mit Risikoeinschaetzung dokumentiert und
     vom User abgenommen.
   - Context: neu `docs/security-findings.md` + ggf. punktuelle Patches in
     `core/security.py`, Routern. Wird sequentiell nach H1/H2 gefahren, damit
     der Review den finalen Stand sieht.

4. **H4 — Backup-Restore-Drill produktiv**
   - Outcome: Auf der Hetzner-Instanz einmal Backup abziehen, in eine leere
     Test-Datenbank zurueckspielen, `GET /v1/personas` gegen die Restore-DB
     liefert die identische Liste. Log-Eintrag im RUNBOOK.
   - Context: nur `deploy/hetzner/RUNBOOK.md` (Restore-Drill-Sektion).

---

### MS-4 — Brainstormer-Migration & MVP-Abnahme (Order 4)

**Outcome:** Alle vier Acceptance Criteria des Notion-Projekts sind gruen.
Brainstormer-Stack (1 Persona + 5 Playbooks) ist auf der Hetzner-Instanz
gepflegt; eine echte Claude-Chat-Session nutzt den Who2Be-MCP-Server statt
Notion und liefert die gleichen Antworten wie heute.

**Tasks:**

1. **B1 — Brainstormer-Export aus Notion**
   - Outcome: Skript `scripts/export_brainstormer.py` zieht die Brainstormer-
     Persona und ihre 5 Playbooks (Body, Tags, Triggers) aus Notion und
     schreibt JSON-Files unter `data/brainstormer/`.
   - Context: neu `scripts/export_brainstormer.py`, neu
     `data/brainstormer/.gitkeep`. Nutzt Notion-MCP zur Laufzeit, der Export
     selbst ist einmalig.

2. **B2 — Import in Who2Be-Instanz (Hetzner)**
   - Outcome: Skript `scripts/import_to_who2be.py` ruft `/v1/personas` und
     `/v1/playbooks` per API-Token gegen die Hetzner-API auf; im Web sind
     Persona + 5 Playbooks sichtbar; `GET /v1/personas/{id}/playbooks` listet
     die 5 Links.
   - Context: neu `scripts/import_to_who2be.py`. Disjunkt zu B1 (Skript-
     Datei), nutzt B1-Output.

3. **B3 — MCP-Endpunkt-Verifikation gegen Hetzner**
   - Outcome: Lokaler MCP-Client (`uv run python -m who2be_mcp.server`) zeigt
     mit `WHO2BE_API_BASE_URL=https://api.<domain>` und gueltigem
     `WHO2BE_API_TOKEN`, dass `get_persona("brainstormer")`,
     `list_playbooks(tag="brainstorming")`, `fetch_playbook(id)` korrekt
     antworten. Integrations-/Smoke-Test ergaenzen unter
     `apps/mcp/tests/test_against_remote.py` (skippt, wenn Env nicht gesetzt).
   - Context: neu `apps/mcp/tests/test_against_remote.py`. Disjunkt zu B1/B2.

4. **B4 — Claude-Chat-Smoke (AC4)**
   - Outcome: Im echten Claude-Chat ist die Who2Be-MCP-Konfiguration aktiv;
     der Brainstormer agiert identisch zur Notion-Variante. Beleg: Chat-
     Transkript-Snippet im RUNBOOK + Notes-Log auf der Notion-Projektseite.
   - Context: nur Notion-Doku und `deploy/hetzner/RUNBOOK.md` (Acceptance-
     Section). Letzte Task — schliesst das Projekt formal ab.

---

## Quer durch alle Milestones

- **Test-Disziplin:** Bei Bugfixes immer zuerst ein reproduzierender, fehl-
  schlagender Test (Repo-CLAUDE.md + Persona). Vor jedem Commit `uv run ruff
  check . && uv run mypy . && uv run pytest -q` bzw. `npm run lint && npx tsc
  --noEmit && npm test` im jeweiligen Stack.
- **Branch-/Commit-Konvention:** `feat/<kurz>` bzw. `fix/<kurz>`,
  Conventional Commits. Cloud-Branch-Praefix `claude/` (z. B.
  `claude/who2be-complete-plan-n6r3u`).
- **Notion-Doku:** Pro abgeschlossener Task ein Notes-Eintrag auf der Projekt-
  Seite (kurz + Pointer auf den jeweiligen `.claude/plan/`-Detail-Plan, der
  beim Code-Task-Flow pro Task entsteht).

## Verifikation der MVP-Completion-Condition

Der MVP ist abgenommen, wenn folgender End-to-End-Lauf transkript-nachweisbar
gruen ist:

1. Lokal `uv run pytest -q` (alle 3 Pakete) und `npm test` gruen — laufende
   CI-Greenmarker.
2. `curl https://api.<domain>/v1/health` → 200 mit `db:"ok"` (MS-2).
3. Web-Login → Persona anlegen → Playbook anlegen → Verknuepfen → Versions-
   Liste sichtbar (MS-1 + MS-2).
4. MCP-Smoke gegen Hetzner: `get_persona("brainstormer")` liefert Inhalt
   (MS-4 B3).
5. Claude-Chat mit aktivierter Who2Be-MCP-Konfiguration: Brainstormer-Persona
   und Playbooks werden geladen, Chat-Antwort entspricht Notion-Baseline
   (MS-4 B4 → AC4).

Wenn 1-5 dokumentiert gruen sind, ist die Notion-Project-Page auf
`Status: Done` zu setzen und der MVP-Outcome erfuellt.

## Hand-Off an Code-Task-Flow (erledigt 2026-05-24)

1. **Milestones in Notion angelegt** (Milestones-DB
   `299d9d7d-5b70-421d-95f1-3c66c00759a7`): MS-1 bis MS-4 mit `Order`,
   `Outcome`, `Status=Planned`, `Project`-Relation auf PROJ-19.
2. **Tasks in Notion angelegt** (Tasks-DB
   `ba2ecc7c-4e1d-4132-9212-f554a85ddf5d`): 6+6+4+4 = 20 Tasks, jede mit
   `Milestone`-Relation, `Project`-Relation, `Context`-Feld, `Type`,
   `Priority=P0`, `Assignee` und `Status=Backlog`.
3. **Erste Task zum Anziehen:** W1 — Auth-Bridge — oeffnet MS-1 und entblockt
   W2-W5 (alle vier sind danach disjunkt und koennen parallel laufen).
