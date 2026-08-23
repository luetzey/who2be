# Lokaler Ein-Befehl-Start (Option A — Fundament)

Status: **aktiv** · Branch: `claude/autonomous-code-agent-role-2m4xgp`

## Ziel (User-Vorgabe)

> „Kann Software einfach auf lokalen Geraeten zum Laufen gebracht werden?
> Sodass jeder, der das Repo downloadet, diese einfach testen kann ohne
> Frust. […] Bedenke dabei, dass die User es auf lokalen Systemen mit
> Localhost oder einer IP aufrufen."

Gewaehlter Scope nach Drei-Optionen-Rueckfrage: **A — Fundament** (ohne
npm-CLI; `npx who2be up` bleibt als Folge-Scope B liegen und setzt auf
diesem Fundament auf).

## Completion-Condition (messbar)

Auf einer frischen Maschine mit ausschliesslich Docker:

1. `git clone … && cd who2be && docker compose up -d --wait` faehrt den Stack
   **ohne** `cp .env.example .env`, **ohne** uv und **ohne** Node hoch.
2. `http://localhost:5173` liefert eine bedienbare App: Signup → Login →
   Persona anlegen, ohne dass eine Env-Variable angefasst wurde.
3. Derselbe Stack ist von einem **zweiten Geraet im LAN** ueber
   `http://<host-ip>:5173` genauso bedienbar — Login und API-Aufrufe
   inklusive, ohne Rebuild und ohne Env-Aenderung.
4. `bash scripts/smoke.sh` bleibt gruen.
5. Web-DoD gruen: `npm run lint`, `npx tsc --noEmit`, `npm run test:coverage`,
   `npm run build`; Python-DoD gruen: `ruff`, `mypy`, `pytest --cov`.

Punkt 1–3 sind **Host-Abnahme** (die Sandbox hat keinen Docker-Daemon,
`docker compose version` ok, `docker info` faellt aus) — analog zu
`docs/local-smoke.md`. Der Agent verifiziert alles, was ohne Daemon geht:
`docker compose config`, Web-/Python-Gates, Unit-Tests der neuen Config-Logik.

## Befund (Ist-Stand, belegt)

| # | Blocker | Beleg |
|---|---|---|
| B1 | README-Quickstart ist der Dev-Pfad (Docker **+** uv **+** Node, API/Web separat) — der 1-Befehl-Weg steht nur in `docs/local-smoke.md` | `README.md:66-79` |
| B2 | Erststart baut API + Web aus Quellcode; die GHCR-Images sind anonym nicht ziehbar (Token-Check → 403) und das Web-Image ist mit Prod-Domains gebacken | `.github/workflows/deploy.yml:24-31`, GHCR-Probe |
| B3 | **IP-Zugriff unmoeglich:** `VITE_API_BASE_URL`/`VITE_SUPABASE_URL` sind Compile-Time und fest auf `localhost`; dazu `CORS_ORIGINS`, `GOTRUE_SITE_URL`, `GOTRUE_URI_ALLOW_LIST` = localhost | `apps/web/Dockerfile:17-31`, `apps/web/src/config.ts:23-53`, `docker-compose.yml` (auth/api/web) |
| B4 | ~~First-Run: Org + Workspace muessen manuell angelegt werden~~ — **entkraeftet**: `/v1/me` seedet beim ersten Aufruf transparent Personal-Org + Workspace | `repositories/me_repository.py:68-85` (`ensure_personal_workspace`) |

B3 ist die technische Weiche: solange die Ziel-URLs im Bundle einbetoniert
sind, hilft weder ein CLI noch bessere Doku.

## Loesungsweg

**Kern: Same-Origin statt fester Hosts.** Der Browser spricht nur noch mit
dem Origin, von dem er geladen wurde — egal ob `localhost`, LAN-IP oder
Domain. Der nginx des Web-Containers proxied `/v1/` → `api:8000` und
`/auth/v1/` → `auth-gateway:9999`. Damit entfaellt fuer den lokalen Betrieb
sowohl die URL-Konfiguration als auch CORS komplett.

**Darueber eine Runtime-Config** (`/config.js`, vom nginx-Entrypoint aus Env
geschrieben), damit Deployments mit getrennten Subdomains (Hetzner/Caddy:
`app.` / `api.` / `mcp.`) und spaeter der CLI explizite URLs setzen koennen —
**ein** Image fuer alle Umgebungen.

Aufloesungsreihenfolge in `config.ts`:
`window.__WHO2BE_CONFIG__` (Runtime) → `import.meta.env.VITE_*` (Build-Zeit,
Rueckwaertskompatibilitaet Dev/Tests) → **Same-Origin-Default**.

## Arbeitspakete (datei-disjunkt)

### WP-1 — Runtime-Config im Web-Bundle
- `apps/web/src/config.ts`: neue Aufloesungskette; `read()` wirft im PROD-Build
  nur noch, wenn auch der Same-Origin-Fallback nicht greift (Anon-Key behaelt
  einen Default, GoTrue self-hosted validiert ihn nicht).
- `apps/web/src/vite-env.d.ts`: Typ fuer `window.__WHO2BE_CONFIG__`.
- `apps/web/index.html`: `<script src="/config.js">` **vor** dem Modul-Script.
- `apps/web/public/config.js`: leerer Default, damit der Vite-Dev-Server nicht
  404t; im Image ueberschreibt ihn der Entrypoint.
- `apps/web/src/config.test.ts` (neu): Reihenfolge Runtime > Vite-Env >
  Same-Origin; MCP-Ableitung unveraendert.

### WP-2 — Same-Origin-Proxy im Web-Container
- `apps/web/nginx.conf`: `location /v1/` → `api:8000`, `location /auth/v1/` →
  `auth-gateway:9999`; Docker-DNS per `resolver 127.0.0.11` + Variablen-
  `proxy_pass` (gleiche Begruendung wie in `supabase/gateway.conf`);
  `proxy_buffering off` fuer Streaming-/Export-Antworten; grosszuegige
  `client_max_body_size` fuer den Ingest-Upload.
- Upstream-Hosts aus Env, damit derselbe nginx auch ohne Compose-Namen laeuft.
- `apps/web/Dockerfile`: `docker-entrypoint.d`-Skript schreibt `/config.js`
  und die Upstream-Include-Datei aus Env; VITE_*-Args werden optional.

### WP-3 — Compose ohne Vorarbeit lauffaehig
- `docker-compose.yml`: `WHO2BE_PUBLIC_URL` (Default `http://localhost:5173`)
  speist `CORS_ORIGINS`, `GOTRUE_SITE_URL`, `GOTRUE_URI_ALLOW_LIST`,
  `WEB_BASE_URL`; `web` bekommt `depends_on` auf `auth-gateway`; Web-Build-Args
  entfallen (Runtime-Config).
- `.env` wird optional: alle Werte haben Compose-Defaults (`${VAR:-default}`).
- `.env.example`: `WHO2BE_PUBLIC_URL` dokumentiert (LAN-IP-Beispiel).

### WP-4 — Fertige Images statt Build (B2)
- `docker-compose.images.yml` (neu): Overlay, das `api`/`web`/`mcp` aus
  `ghcr.io/luetzey/who2be-*:${WHO2BE_IMAGE_TAG:-latest}` zieht statt zu bauen.
- `.github/workflows/deploy.yml`: Web-Image **ohne** `VITE_*`-Build-Args bauen
  (sonst sind die Prod-Domains eingebacken und das Image lokal unbrauchbar).
- `deploy/hetzner/who2be/docker-compose.yml`: die bisher gebackenen URLs als
  **Runtime-Env** am `web`-Service setzen — Prod bleibt explizit konfiguriert.
- **Owner-Aktion (nicht durch den Agenten):** GHCR-Packages `who2be-api`,
  `who2be-web`, `who2be-mcp` auf *public* stellen. Bis dahin bleibt der
  Build-Pfad der Default; das Overlay ist die schnellere Option danach.

### WP-5 — Doku
- `README.md`: Quickstart = **ein** Befehl (nur Docker), danach erst der
  Dev-Setup-Abschnitt (uv/Node) fuer Beitragende; eigener Abschnitt
  „Access from another device" mit LAN-IP; kurzer Troubleshooting-Block.
- `docs/local-smoke.md`: Verweis auf den neuen Quickstart, `.env` nicht mehr
  Pflicht.
- `CHANGELOG.md` (Unreleased) + `.claude/context/STATE.md`.

## Nicht in diesem Scope

- npm-/npx-CLI (Scope B), Demo-Seed + Auto-Bootstrap-Admin (Scope C, B4).
- Slim-Profil ohne MinIO: Compose-`profiles` und `--wait` vertragen sich mit
  dem One-Shot `minio-bootstrap` nur mit Umbau der `depends_on`-Kette
  (`service_completed_successfully`). Bewusst zurueckgestellt — Nutzen (ein
  Image weniger) steht nicht gegen das Risiko, den `--wait`-Start zu brechen.
- Kein Anfassen von Repo-Settings; keine Aenderung der Prod-Domains.

## Risiken

| Risiko | Gegenmassnahme |
|---|---|
| Prod-Web bekommt nach dem Entfernen der Build-Args keine URLs mehr | Runtime-Env im Hetzner-Compose im selben PR; Caddy-CSP `connect-src` bleibt unveraendert gueltig |
| `/v1/`-Proxy kollidiert mit SPA-Routen | Web-Routen liegen unter `/w/…`, `/settings/…`, `/oauth/…` — kein `/v1`-Prefix im Router |
| nginx cached die Upstream-IP nach `compose up` | Variablen-`proxy_pass` + `resolver … valid=10s` (Muster aus `supabase/gateway.conf`) |
| End-to-End nicht in der Sandbox pruefbar | Host-Abnahme durch den User; `docker compose config` + Web-/Python-Gates laufen im Agenten |

## Umsetzung (2026-08-23)

Alle fuenf Arbeitspakete umgesetzt; zwei Abweichungen vom Plan:

- **WP-2 ohne Env-konfigurierbare Upstreams.** Die Proxy-Ziele sind die
  Compose-Service-Namen (`api:8000`, `auth-gateway:9999`). Mit
  Variablen-`proxy_pass` + Resolver scheitert ein nicht aufloesbarer Name erst
  beim Request, nicht beim Start — Deployments ohne diese Services (Caddy mit
  eigenen Subdomains) laufen unveraendert, der Proxy liegt dort brach. Ein
  envsubst-Template haette den nginx-Variablen (`$uri`, `$host`) in die Quere
  kommen koennen; der Gewinn stand nicht dafuer.
- **B4 gestrichen** (siehe Tabelle oben) — der Lazy-Seed existiert bereits.

Zusaetzlich zum Plan:

- `scripts/smoke.sh` prueft jetzt den **Browser-Pfad**: `/config.js`,
  `/v1/health` und `/auth/v1/health` ueber den Web-Origin. Ohne diesen Schritt
  koennte der Proxy brechen, ohne dass ein Check es merkt (Schritt 1-3 gehen
  direkt auf `:8000`). Der Compose-Job in `.github/workflows/ci.yml` faehrt
  diesen Smoke bei jedem Push — damit ist der localhost-Pfad CI-verifiziert.
- `deploy/dokploy/docker-compose.yml` bekam dieselbe Runtime-Env wie Hetzner.

### Verifikation

| Check | Ergebnis |
|---|---|
| `npm run lint` | 0 errors (64 vorbestehende Warnings) |
| `npx tsc -b` (via `npm run build`) | gruen — fing einen Typfehler im neuen Test |
| `npm run test:coverage` | 181 Dateien / 1020 Tests gruen; Statements 86.5 %, Branches 81.1 %, Functions 82.0 %, Lines 87.5 % (ueber allen Floors) |
| `npm run build` | gruen; `dist/config.js` + `<script src="/config.js">` im Output |
| `uv run ruff check .` | All checks passed |
| `docker compose config` (Basis, `+images`-Overlay, Hetzner, Dokploy) | alle valide |
| Entrypoint-Skript | `sh -n` + Trockenlauf gegen temporaeres Ziel |

### Offen

- **Host-Abnahme (User):** `docker compose up -d --wait` ohne `.env`, Bedienung
  ueber `http://localhost:5173` und ueber `http://<host-ip>:5173`,
  `bash scripts/smoke.sh`. Die Sandbox hat keinen Docker-Daemon.
- **Owner-Aktion:** GHCR-Packages `who2be-api|web|mcp` public schalten, sonst
  bleibt `docker-compose.images.yml` auf `docker login ghcr.io` angewiesen.
- **Scope B** (`npx who2be up`) und **Scope C** (Demo-Seed, Slim-Profil) offen.
