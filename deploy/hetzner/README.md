# Hetzner-Deployment — Who2Be

Compose-Artefakte fuer die produktive Who2Be-Instanz auf einem Hetzner-Host.
Dieser Ordner deckt **MS-2 C3** (App-Stack + Reverse-Proxy) ab — Tasks C1
(Server-Provisioning), C2 (self-hosted Supabase), C4 (CI/CD-Deploy) und C5
(Backup-Runbook) sind disjunkt und kommen in eigenen Iterationen dazu.

## Layout

```
deploy/hetzner/
  Caddyfile                # Reverse-Proxy mit Auto-HTTPS + Security-Header
  .env.example             # Operator-Vars (kopieren nach .env)
  README.md                # dieses Dokument
  who2be/
    docker-compose.yml         # Prod-Compose (api + web + caddy + migrate)
    docker-compose.local.yml   # Override fuer lokale Smoke ohne C1/C2
```

## Voraussetzungen

- **C1 fertig:** Hetzner-Host mit Docker + Docker-Compose-v2, Ports 80/443
  durch Firewall offen, deploy-User mit Docker-Gruppen-Mitgliedschaft.
- **C2 fertig:** Supabase-Compose laeuft (`supabase/docker-compose.yml`,
  Setup siehe `supabase/README.md`). Konkret bedeutet das:
  - Das Netzwerk `supabase-net` existiert (wird vom C2-Compose erstellt).
  - Postgres ist via `db:5432` im `supabase-net` erreichbar.
  - `JWT_SECRET` (mind. 32 Zeichen) ist gewaehlt — **identischer Wert**
    in `supabase/.env` und `.env` (dieser Stack hier).
  - `ANON_KEY` ist mit demselben Secret signiert (per
    `scripts/gen_test_jwt.py --role anon`).
- **DNS:** A-Records `api.<DOMAIN>`, `app.<DOMAIN>` und
  `supabase.<DOMAIN>` zeigen auf den Hetzner-Host.

## Bring-up-Reihenfolge

```bash
# 1) Supabase-Stack (C2) — erzeugt supabase-net, faehrt Postgres + GoTrue an
docker compose \
  -f deploy/hetzner/supabase/docker-compose.yml \
  --env-file deploy/hetzner/supabase/.env \
  up -d --wait

# 2) App-Stack (C3) — haengt sich ueber supabase-net (external) ein
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  --env-file deploy/hetzner/.env \
  up -d --wait
```

## Produktiver Start

1. Repo auf den Host klonen (oder `git pull`).
2. `.env` anlegen:
   ```bash
   cp deploy/hetzner/.env.example deploy/hetzner/.env
   $EDITOR deploy/hetzner/.env
   ```
3. Sobald C4 GHCR-Images pusht: `docker compose ... pull`. Solange noch
   nicht: `docker compose ... build` baut lokal aus dem Repo:
   ```bash
   docker compose \
     -f deploy/hetzner/who2be/docker-compose.yml \
     --env-file deploy/hetzner/.env \
     build api web
   ```
4. Stack starten:
   ```bash
   docker compose \
     -f deploy/hetzner/who2be/docker-compose.yml \
     --env-file deploy/hetzner/.env \
     up -d --wait
   ```
5. Smoke:
   ```bash
   curl -fsS https://api.${DOMAIN}/v1/health
   # erwartete Antwort: {"status":"ok","version":"...","db":"ok"}
   ```
6. Logs:
   ```bash
   docker compose -f deploy/hetzner/who2be/docker-compose.yml \
     --env-file deploy/hetzner/.env logs -f caddy api
   ```

## Lokaler Smoke ohne Hetzner

Override-File spinnt einen lokalen Postgres an und mappt Caddy auf
Test-Ports 8080/8443:

```bash
cp deploy/hetzner/.env.example deploy/hetzner/.env  # Defaults reichen
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  -f deploy/hetzner/who2be/docker-compose.local.yml \
  --env-file deploy/hetzner/.env up -d --wait
curl -k -fsS https://localhost:8443/v1/health   # 502 erwartet ohne DNS
docker compose ... down -v
```

Caddy stolpert lokal ueber den ACME-Challenge gegen `example.com`; fuer
einen echten lokalen Smoke entweder `DOMAIN=localhost.test` in der `.env`
setzen + Caddy auf `auto_https off` umstellen oder direkt die Container
mit `docker compose exec api curl -fsS http://localhost:8000/v1/health`
ansprechen.

## MCP-Container (Profile `mcp`)

Der MCP-Server nutzt per Default stdio-Transport — er laeuft nicht als
Long-Running-Service hinter Caddy. Das Image ist im Compose unter
`profiles: ["mcp"]` versteckt und wird **nicht** beim normalen `up`
gestartet. Aufruf als interner Smoke-Harness:

```bash
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  --env-file deploy/hetzner/.env \
  run --rm mcp python -c "import who2be_mcp.server as s; print('ok')"
```

Falls spaeter Remote-MCP via HTTP-Transport gewuenscht ist: Profil von
`mcp` auf `default` kippen, Caddy-Route `mcp.${DOMAIN}` ergaenzen — eigene
Folge-Task.

## Security-Header / Proxy-Headers

- Caddy setzt HSTS, `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy` und je eine CSP fuer API und Web
  (siehe `Caddyfile`). Adressiert F-12 aus
  `docs/security-findings.md`.
- API laeuft mit `uvicorn --proxy-headers --forwarded-allow-ips *`. Sicher,
  weil der Container keinen `ports:`-Eintrag hat und nur Caddy ihn im
  internen Netzwerk erreicht. Adressiert F-02.

## Caddyfile-Syntax offline pruefen

```bash
docker run --rm \
  -v $(pwd)/deploy/hetzner/Caddyfile:/etc/caddy/Caddyfile:ro \
  -e DOMAIN=localhost.test -e ACME_EMAIL=test@example.com \
  -e VITE_SUPABASE_URL=http://localhost:9999 \
  caddy:2.8-alpine caddy validate \
    --config /etc/caddy/Caddyfile --adapter caddyfile
```

## CI/CD (MS-2 C4)

Workflow `.github/workflows/deploy.yml` triggert auf `push: main` (oder
manuell per `workflow_dispatch`):

1. **`build-and-push`** baut die drei Images parallel und pushed sie als
   `ghcr.io/luetzey/who2be-{api,web,mcp}:<sha>` und `:latest` ans
   GitHub Container Registry. Login per `GITHUB_TOKEN` (`packages: write`).
2. **`deploy`** ist conditional (`if: vars.DEPLOY_HOST != ''`): solange
   die Host-Konfig im Repo fehlt (C1 nicht fertig), ueberspringt der
   Job sich sauber. Sobald `DEPLOY_HOST` gesetzt ist, ruft er via SSH
   `deploy/hetzner/scripts/deploy.sh <commit-sha>` auf dem Host auf —
   dieses Skript checkt den SHA aus, setzt die `*_IMAGE_TAG`-Variablen
   in `.env` und macht `docker compose pull` + `up -d --wait`.

### Repository Variables

In **Settings → Secrets and variables → Actions → Variables** anlegen:

| Name                       | Beispiel                            | Zweck                                |
| -------------------------- | ----------------------------------- | ------------------------------------ |
| `VITE_API_BASE_URL`        | `https://api.example.com`           | Web-Build-Arg (Compile-Time)         |
| `VITE_SUPABASE_URL`        | `https://supabase.example.com`      | Web-Build-Arg                        |
| `VITE_SUPABASE_ANON_KEY`   | `<ANON_KEY aus supabase/.env>`      | Web-Build-Arg (oeffentlicher Key)    |
| `DEPLOY_HOST`              | `who2be.example.com`                | SSH-Host fuer Deploy-Job             |
| `DEPLOY_USER`              | `deploy`                            | SSH-User auf dem Host                |
| `DEPLOY_PROJECT_DIR`       | `/opt/who2be`                       | Repo-Klon auf dem Host (Default)     |
| `DEPLOY_SSH_KNOWN_HOSTS`   | Output von `ssh-keyscan -H <host>`  | Optional; sonst Auto-keyscan         |

### Repository Secrets

In **Secrets**:

| Name              | Inhalt                                     |
| ----------------- | ------------------------------------------ |
| `DEPLOY_SSH_KEY`  | Privater ED25519-SSH-Key des Deploy-Users  |

### Rollback

Auf dem Host:
```bash
/opt/who2be/deploy/hetzner/scripts/deploy.sh <alter-commit-sha>
```
Das Skript ist idempotent und kann auf einen frueheren SHA zurueckrollen,
solange dessen Images noch auf GHCR liegen.

## Verweis

- Operative Schritt-fuer-Schritt-Anleitungen (CVE-Response, Secret-Rotation,
  akzeptierte Vulnerabilities) in [`RUNBOOK.md`](./RUNBOOK.md).
- Backup/Restore-Pfad und Restore-Drill: kommt mit MS-2 C5 in `RUNBOOK.md`
  dazu.
