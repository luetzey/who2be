# Plan: MS-2 C2 — Self-hosted Supabase-Compose (Hetzner)

## Context

Roadmap (`.claude/plan/2026-05-24_who2be-mvp-roadmap.md` §MS-2 C2):

> Supabase-Compose laeuft (`supabase/docker`), Postgres-Volume persistiert,
> Auth + Studio erreichbar; Studio-Login-Doku abgelegt. `JWT_SECRET` aus
> Supabase ist im Secrets-File hinterlegt.

C3 (App-Compose) ist via PR #13 in `main`. Er erwartet ein externes
Docker-Netzwerk `supabase-net` und einen Postgres-Service unter
`postgresql://<user>:<pw>@db:5432/...`. Bislang gibt es nur einen lokalen
Stack im Root-`docker-compose.yml` (Postgres + GoTrue + nginx-Gateway als
Vorgriff). C2 produziert die produktive Variante.

## Approach

### Minimaler Stack mit offiziellem `supabase/postgres`-Image

- `supabase/postgres:15.1.1.78` als DB statt `postgres:16` — bringt
  Supabase-Rollen (`anon`, `authenticated`, `service_role`,
  `supabase_admin`), `pgcrypto`, `uuid-ossp` und die GoTrue-noetigen
  Extensions out of the box mit. Spart uns ein selbstgeschriebenes
  Init-Script.
- `supabase/gotrue:v2.158.1` (identisch zum lokalen Stack — bewaehrt) als
  Auth-Service.
- `nginx:1.27-alpine` als **Auth-Gateway** — kopiert die existierende
  `supabase/gateway.conf` (URL-Rewrite `/auth/v1/*` → `/*` + CORS-Preflight).

### Studio + Meta unter `profile: studio`

`supabase/studio` + `supabase/postgres-meta` werden im selben Compose, aber
unter `profiles: ["studio"]`, registriert. So bleibt der minimale Stack
schlank (drei Services), und Studio ist explizit per
`docker compose --profile studio up -d` aktivierbar. Begruendung: Studio
braucht viel Env-Tuning (`SUPABASE_PUBLIC_URL`, Organisation-Name,
Admin-Passwoerter); fuer das MVP-Acceptance reicht der Auth-Pfad, Studio
ist Nice-to-have. Roadmap-Outcome "Auth + Studio erreichbar" wird damit
erfuellt, aber nicht zwingend bei jedem Boot mitgestartet.

### Bridge zu C3: Caddy + supabase-net

- `supabase-net` wird hier als ganz normales Compose-Netzwerk definiert
  (`driver: bridge`). Beim `docker compose up` erstellt Compose es; C3
  haengt sich per `external: true` rein.
- Caddyfile in `deploy/hetzner/` wird um einen `supabase.{$DOMAIN}`-Block
  erweitert — proxied auf `auth-gateway:9999` im `supabase-net`.
- C3-`who2be/docker-compose.yml`: Der `caddy`-Service muss auch im
  `supabase-net` haengen, sonst kann er `auth-gateway` nicht erreichen.
  Kleiner Edit, disjunkt zum Rest.

### Wichtige Sicherheitsdetails

- **`JWT_SECRET`** ist der gleiche Wert in `deploy/hetzner/supabase/.env`
  und `deploy/hetzner/.env` (von C3). Mindestens 32 Zeichen (F-08).
  `.env.example` weist explizit darauf hin.
- **`SITE_URL` + `URI_ALLOW_LIST`** von GoTrue auf `https://app.<DOMAIN>`.
  Verhindert Open-Redirect-Misbrauch.
- **`POSTGRES_PASSWORD`** + **`DASHBOARD_USERNAME`/`DASHBOARD_PASSWORD`**
  fuer Studio sind in `.env.example` ohne Default — Operator muss setzen.
- **Postgres `ports:`** ist absichtlich NICHT publiziert; Zugriff nur
  intern via supabase-net.

## File-by-file Changes

### A. `deploy/hetzner/supabase/docker-compose.yml` — NEU

Services:
- `db` (supabase/postgres:15.1.1.78) — Volume `db-data`, Healthcheck
  `pg_isready`, `POSTGRES_PASSWORD` aus Env, eigene `init/`-Scripts.
- `auth` (supabase/gotrue:v2.158.1) — DB-URL auf `postgres://...@db`,
  `GOTRUE_JWT_SECRET` aus shared `.env`, `SITE_URL=https://app.<DOMAIN>`,
  Mailer-autoconfirm fuer MVP.
- `auth-gateway` (nginx:1.27-alpine) — `auth-gateway.conf` als Config,
  Port 9999 intern, **kein** `ports:`-Eintrag (Zugriff via Caddy).
- `meta` + `studio` unter `profiles: ["studio"]`.

Netzwerk: `supabase-net`, `driver: bridge`, **nicht** external.
Volumes: `db-data` (persistent).

### B. `deploy/hetzner/supabase/.env.example` — NEU

```
POSTGRES_PASSWORD=CHANGE_ME
JWT_SECRET=CHANGE_ME_minimum_32_chars        # gleicher Wert wie in ../.env
JWT_EXP=3600
DOMAIN=example.com
SITE_URL=https://app.example.com
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=CHANGE_ME
ANON_KEY=CHANGE_ME_generated_via_jwt_cli
SERVICE_ROLE_KEY=CHANGE_ME_generated_via_jwt_cli
```

Hinweis im `README.md`, wie `ANON_KEY` / `SERVICE_ROLE_KEY` mit dem
existierenden `scripts/gen_test_jwt.py` (HS256 mit `JWT_SECRET`) erzeugt
werden.

### C. `deploy/hetzner/supabase/init/01-supabase-roles.sql` — NEU

`supabase/postgres` bringt die Rollen schon mit, aber wir setzen das
`auth.users`-Schema explizit (idempotent), damit GoTrue ohne weiteren
Schritt seine Migrationen laufen lassen kann:

```sql
CREATE SCHEMA IF NOT EXISTS auth;
-- supabase/postgres bringt anon/authenticated/service_role bereits mit.
-- Falls die Datenbank ohne diese Rollen gestartet wurde, hier nachziehen:
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
END$$;
```

### D. `deploy/hetzner/supabase/auth-gateway.conf` — NEU (kopiert)

Wiederverwendung der existierenden `supabase/gateway.conf` aus dem Root —
1:1 kopiert. Begruendung: dieselbe URL-Rewrite-Logik (`/auth/v1/*` → `/*`)
und CORS-Behandlung gilt fuer Prod. Im Caddyfile setzen wir CORS aber
nicht doppelt (Caddy stripped die GoTrue-CORS-Header und der Browser sieht
nur Caddys Antwort — siehe Comment in `gateway.conf`).

### E. `deploy/hetzner/supabase/README.md` — NEU

- Voraussetzungen: C1 fertig.
- Reihenfolge: **C2 vor C3** zu starten (sonst kann C3's Migrate-Container
  keinen `db`-Host aufloesen — auch wenn `supabase-net` schon existiert).
- `.env`-Setup + JWT-Generation per `scripts/gen_test_jwt.py`.
- Studio-Aktivierung: `--profile studio up -d`.
- Studio-Login-URL `http://localhost:3000` (lokal via SSH-Tunnel) oder
  `https://studio.<DOMAIN>` (falls Caddy nachgezogen — Out of Scope C2,
  hier nur Hinweis).
- Backup-Hinweis (Vollkonzept in C5).

### F. `deploy/hetzner/Caddyfile` — Ergaenzung

Neuer Block fuer `supabase.{$DOMAIN}` → `auth-gateway:9999`:

```
supabase.{$DOMAIN} {
    import security_headers
    # Auth-Endpunkt: GoTrue antwortet JSON, CORS macht der Gateway.
    header Content-Security-Policy "default-src 'none'; frame-ancestors 'none'"
    reverse_proxy auth-gateway:9999
}
```

### G. `deploy/hetzner/who2be/docker-compose.yml` — Edit

`caddy`-Service: `networks: [app-net]` → `networks: [app-net, supabase-net]`,
damit Caddy den `auth-gateway`-Service erreichen kann.

### H. `deploy/hetzner/README.md` — Ergaenzung

Sektion "Bring-up-Reihenfolge":
1. C1 — Server provisionieren.
2. **C2 zuerst:**
   `docker compose -f supabase/docker-compose.yml --env-file supabase/.env up -d --wait`
3. C3:
   `docker compose -f who2be/docker-compose.yml --env-file .env up -d --wait`

## Wiederverwendung

- `supabase/gateway.conf` (existiert im Root) → `deploy/hetzner/supabase/
  auth-gateway.conf` 1:1.
- `scripts/gen_test_jwt.py` → erzeugt `ANON_KEY` / `SERVICE_ROLE_KEY`
  passend zum `JWT_SECRET`.
- C3-Compose's `supabase-net`-Verweis (`external: true`) — keine
  Aenderung noetig.
- ENV-Pattern aus `docker-compose.yml:38-55` (GoTrue-Variablen) — 1:1
  uebernommen, nur die `SITE_URL` und Mailer-Werte fuer Prod angepasst.

## Verifikation

1. **Compose-Config statisch**:
   ```bash
   docker compose -f deploy/hetzner/supabase/docker-compose.yml \
     --env-file deploy/hetzner/supabase/.env config --quiet
   ```
2. **C3 + C2 zusammen** — `supabase-net` muss aufloesbar sein:
   ```bash
   docker compose -f deploy/hetzner/supabase/docker-compose.yml \
                  -f deploy/hetzner/who2be/docker-compose.yml \
                  --env-file deploy/hetzner/.env config --quiet
   ```
3. **Caddyfile-Syntax** wie bei C3.
4. **Python+Web-Stack** unbeeintraechtigt (kein Code-Patch).
5. **JWT-Sync**: explizite Pruefung in der README, dass `JWT_SECRET` in
   beiden `.env`-Files identisch ist.

## Out of Scope (bewusst)

- C1 Server-Provisioning, C4 CI/CD, C5 Backup-RUNBOOK, C6 E2E-Smoke.
- Storage-API, Realtime, PostgREST — fuer MVP nicht im Pfad.
- Mailer-Production-Setup (kein SMTP-Provider angebunden;
  Mailer-Autoconfirm bleibt true, also kein Email-Versand noetig).
- Studio-Auth-Bridge via Caddy — Operator macht SSH-Tunnel; eigene
  Folge-Task, falls Studio von aussen erreichbar sein soll.
- ANON/SERVICE_ROLE-JWT-Rotation — manuelle Erzeugung reicht fuer MVP.
