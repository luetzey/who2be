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

## Cloud-Edition (Billing + RLS + Redis)

Der Default-Bring-up oben faehrt die **On-Prem-Edition** (kein Billing,
RLS-Bypass, In-Memory-Rate-Limit). Fuer die **Cloud-Edition** das Overlay
`who2be/docker-compose.cloud.yml` zusaetzlich laden (Plan Track S/T,
`.claude/plan/2026-06-03-2030_cloud-launch-readiness.md`). Es spiegelt das
lokale `docker-compose.cloud.yml` auf den Hetzner-Split-Stack.

Was das Overlay umstellt: `WHO2BE_EDITION=cloud`, API verbindet als Rolle
`who2be_app` (**RLS aktiv**) statt als Owner, Redis als Rate-Limit-Storage,
Mollie-Billing-Env, und es baut das `runtime-cloud`-Image (mit
`who2be-billing`-Paket). Details siehe Kopf des Overlay-Files.

```bash
# 0) .env um die Cloud-Vars ergaenzen (siehe .env.example, Sektion
#    "Cloud-Edition"): APP_DB_PASSWORD, SUPABASE_SERVICE_KEY, optional MOLLIE_*.

# 1) Supabase-Stack — fuer echte Cloud-Paritaet mit Mail-Pflicht + echtem SMTP
#    (supabase/.env: GOTRUE_MAILER_AUTOCONFIRM=false + GOTRUE_SMTP_*). Fuer einen
#    ersten Solo-Smoke darf autoconfirm voruebergehend true bleiben.
docker compose \
  -f deploy/hetzner/supabase/docker-compose.yml \
  --env-file deploy/hetzner/supabase/.env up -d --wait

# 2) Cloud-Image bauen (runtime-cloud) und Stack hochfahren — IMMER beide -f:
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  -f deploy/hetzner/who2be/docker-compose.cloud.yml \
  --env-file deploy/hetzner/.env build api migrate web
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  -f deploy/hetzner/who2be/docker-compose.cloud.yml \
  --env-file deploy/hetzner/.env up -d --wait
```

Reihenfolge intern: `migrate` (alle SQL inkl. `0036` Rolle `who2be_app` +
`0037` RLS) → `set-app-role-password` (One-Shot: setzt das Rollen-Passwort) →
`redis` → `api` (verbindet als `who2be_app`). Sanity-Check, dass die Schalter
greifen:

```bash
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  -f deploy/hetzner/who2be/docker-compose.cloud.yml \
  --env-file deploy/hetzner/.env \
  exec api printenv WHO2BE_EDITION APP_DATABASE_URL RATE_LIMIT_STORAGE_URI
# → cloud / postgresql://who2be_app:***@db:5432/postgres / redis://redis:6379
```

Abnahme-Reise (Signup → Verify → Pro-Entitlement → MCP-Quota 429 → Downgrade →
RLS-Nachweis): `docs/cloud-prod-smoke.md` gegen `https://api.${DOMAIN}` fahren.
Pro-Entitlement ohne Mollie ueber den auditierten Override-Endpoint (Admin +
aal2/MFA + `WHO2BE_BILLING_OVERRIDE_OPERATORS`):

```bash
curl -s -X POST https://api.${DOMAIN}/v1/workspaces/<WS_ID>/billing/override \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"plan":"pro","days":30,"reason":"cloud smoke"}'
```

> **Wichtig:** Ein Wechsel zwischen On-Prem und Cloud auf demselben Volume ist
> ein Edition-Wechsel der Laufzeit, kein Daten-Reset. Bleib pro Box bei **einer**
> Edition; das Cloud-Overlay baut ein eigenes `runtime-cloud`-Image und erzwingt
> es via `pull_policy: build`.

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

## MCP-Container — stdio (Profile `mcp`) + HTTP (Profile `mcp-http`)

Der MCP-Server unterstuetzt zwei Transports (ADR-0034). Beide nutzen dasselbe
Image; der Unterschied liegt in der `WHO2BE_TRANSPORT`-Env.

### Stdio (Default — Claude Desktop / Cursor lokal)

Profile `mcp`. Wird **nicht** beim normalen `up` gestartet. One-Shot:

```bash
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  --env-file deploy/hetzner/.env \
  run --rm mcp python -c "import who2be_mcp.server as s; print('ok')"
```

### Streamable-HTTP (Remote-Clients hinter Caddy)

Profile `mcp-http`. Long-Running, lauscht auf `0.0.0.0:8765/mcp`, Caddy
proxy'iert `mcp.${DOMAIN}` darauf. Aktivieren beim Bringup:

```bash
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  --env-file deploy/hetzner/.env \
  --profile mcp-http up -d --wait
```

Verifizieren (Streamable-HTTP-Endpunkt antwortet auf GET mit Accept-Header):

```bash
curl -fsS -H 'Accept: text/event-stream' \
  https://mcp.${DOMAIN}/mcp/ -m 5 | head
```

Auth: **per-Request-Bearer** (ADR-0034 Multi-Tenant). Caddy reicht
`Authorization` unveraendert weiter; der MCP-Server wertet pro Request den
mitgeschickten, agent-gebundenen `w2b_`-Token aus (`/v1/tokens` in den
Workspace-Settings) — jede Session agiert als ihr eigener, serverseitig
gescopter Agent. Kein globaler Server-Token mehr.

**OAuth-Remote-MCP-Connector (ADR-0036).** Mit aktivem `--profile mcp-http`
ist der MCP-Server zugleich OAuth-2.1-Resource-Server: ein LLM-Client
(Claude/ChatGPT) verbindet sich per `https://mcp.${DOMAIN}/mcp` ueber
Browser-Login + Agent-Wahl — ohne Token-Copy-Paste. Voraussetzung ist nur, dass
`api.${DOMAIN}` (Authorization-Server), `app.${DOMAIN}` (Consent-Seite) und
`mcp.${DOMAIN}` erreichbar sind; die OAuth-URLs leiten sich im Compose aus
`DOMAIN` ab (keine eigenen Vars). Discovery laeuft automatisch ueber die
Protected-Resource-Metadata des MCP-Servers.

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

1. **`build-and-push`** baut die Images parallel (Matrix) und pushed sie ans
   GitHub Container Registry (Login per `GITHUB_TOKEN`, `packages: write`):
   - On-Prem (Default-Target `runtime`, OHNE Billing):
     `ghcr.io/luetzey/who2be-{api,web,mcp}:<sha>` und `:latest`.
   - **Cloud-API** (Target `runtime-cloud`, MIT `who2be-billing`):
     `ghcr.io/luetzey/who2be-api-cloud:<sha>` und `:latest`. Eigenes Tag,
     damit das On-Prem-`who2be-api`-Image **unangetastet** bleibt. `mcp` hat
     keine Cloud-Variante; das **Cloud-Web-Bundle** (Build-Arg
     `VITE_WHO2BE_EDITION=cloud`, Billing-UI im Bundle — ADR-0029) wird nicht
     als GHCR-Image gepusht, sondern vom Cloud-Overlay auf dem Host gebaut
     (siehe unten).
2. **`deploy`** ist conditional (`if: vars.DEPLOY_HOST != ''`): solange
   die Host-Konfig im Repo fehlt (C1 nicht fertig), ueberspringt der
   Job sich sauber. Sobald `DEPLOY_HOST` gesetzt ist, ruft er via SSH
   `WHO2BE_EDITION=<edition> deploy/hetzner/scripts/deploy.sh <commit-sha>`
   auf dem Host auf — dieses Skript checkt den SHA aus, setzt die
   `*_IMAGE_TAG`-Variablen in `.env` und faehrt den Stack hoch. Die Edition
   steuert die Repo-Variable `WHO2BE_EDITION` (Default On-Prem):
   - **On-Prem** (`WHO2BE_EDITION` leer/`onprem`): ein Compose-File
     (`docker-compose.yml`), `docker compose pull api web migrate` + `up -d --wait`.
   - **Cloud** (`WHO2BE_EDITION=cloud`): **beide** `-f`-Files
     (`docker-compose.yml` + `docker-compose.cloud.yml`). Das Overlay (PR #181)
     pinnt `pull_policy: build` + `target: runtime-cloud` fuer `api`+`migrate`
     sowie `pull_policy: build` + Build-Arg `VITE_WHO2BE_EDITION=cloud` fuer
     `web` — Cloud-API **und** Cloud-Web-Bundle entstehen also auf dem Host aus
     dem ausgecheckten SHA (das GHCR-`who2be-web` ist On-Prem, ohne Billing-UI).
     Das in CI gepushte `who2be-api-cloud:<sha>` dient Paritaet/Verifikation
     und ist die SSoT, falls das Overlay spaeter auf Pull umgestellt wird.
     Reihenfolge intern (Overlay): `migrate` → `set-app-role-password` →
     `redis` → `api`.

   Idempotenz/Rollback bleiben in beiden Editionen erhalten: erneuter Aufruf mit
   demselben (oder einem frueheren) SHA setzt die Tags neu und faehrt den Stack
   ueber `up -d --wait --remove-orphans` zustandslos nach. Pro Box **eine**
   Edition behalten (Edition-Wechsel ist ein Laufzeit-, kein Daten-Reset).

### Repository Variables

In **Settings → Secrets and variables → Actions → Variables** anlegen:

> **Hinweis (Web-URLs):** Die drei `VITE_*`-Werte werden **nicht mehr ins
> Image gebaut** — das CI-Image ist host-neutral. Der `web`-Service in
> `deploy/hetzner/who2be/docker-compose.yml` reicht sie als
> `WHO2BE_API_BASE_URL`/`WHO2BE_SUPABASE_URL`/`WHO2BE_SUPABASE_ANON_KEY` an den
> Container, der daraus beim Start `/config.js` schreibt. Aus dem `.env` auf dem
> Host heraus bleibt die Bedienung damit unveraendert; ohne diese Werte spraeche
> die App Same-Origin (also `app.<domain>` statt `api.<domain>`).

| Name                       | Beispiel                            | Zweck                                |
| -------------------------- | ----------------------------------- | ------------------------------------ |
| `VITE_API_BASE_URL`        | `https://api.example.com`           | Web-Runtime-Config (siehe Hinweis)   |
| `VITE_SUPABASE_URL`        | `https://supabase.example.com`      | Web-Runtime-Config                   |
| `VITE_SUPABASE_ANON_KEY`   | `<ANON_KEY aus supabase/.env>`      | Web-Runtime-Config (oeffentl. Key)   |
| `DEPLOY_HOST`              | `who2be.example.com`                | SSH-Host fuer Deploy-Job             |
| `DEPLOY_USER`              | `deploy`                            | SSH-User auf dem Host                |
| `DEPLOY_PROJECT_DIR`       | `/opt/who2be`                       | Repo-Klon auf dem Host (Default)     |
| `DEPLOY_SSH_KNOWN_HOSTS`   | Output von `ssh-keyscan -H <host>`  | Optional; sonst Auto-keyscan         |
| `WHO2BE_EDITION`           | `cloud`                             | Optional; `cloud` → Cloud-Overlay. Leer/`onprem` = Default |

### Repository Secrets

In **Secrets**:

| Name              | Inhalt                                     |
| ----------------- | ------------------------------------------ |
| `DEPLOY_SSH_KEY`  | Privater ED25519-SSH-Key des Deploy-Users  |

### Rollback

Auf dem Host:
```bash
# On-Prem
/opt/who2be/deploy/hetzner/scripts/deploy.sh <alter-commit-sha>
# Cloud (gleiche Edition wie der Box-Zustand!)
WHO2BE_EDITION=cloud /opt/who2be/deploy/hetzner/scripts/deploy.sh <alter-commit-sha>
```
Das Skript ist idempotent und kann auf einen frueheren SHA zurueckrollen,
solange dessen Images noch auf GHCR liegen (Cloud-API baut den `runtime-cloud`-
Build lokal aus dem ausgecheckten SHA).

## Datenschutz / Compliance (At-Rest + Standort)

- **Verschluesselung at-Rest:** Das Postgres-Volume (`db-data`) muss at-Rest
  verschluesselt liegen — entweder ueber ein verschluesseltes Hetzner-Volume
  (Plattform-LUKS) oder selbst verwaltetes LUKS auf dem Host. Einrichtung +
  reproduzierbarer Verifikationsschritt (`lsblk` / `cryptsetup status`) und die
  Protokoll-Tabelle stehen im RUNBOOK unter
  [Verschluesselung at-Rest](./RUNBOOK.md#verschluesselung-at-rest-postgres-volume).
  Adressiert die Audit-Befunde P4/S2. **Keine** Schluessel/Passphrasen ins Repo.
- **RZ-Standort & Auftragsverarbeiter:** Hetzner-Region (DE: `nbg1`/`fsn1`,
  FI: `hel1` — alle EU/EWR) und die Sub-Processor-Liste (Hetzner, Mollie,
  self-hosted GoTrue, Mail) sind im RUNBOOK unter
  [Standort & Auftragsverarbeiter](./RUNBOOK.md#standort--auftragsverarbeiter)
  dokumentiert; die rechtsverbindliche Fassung fuehrt der Betreiber im VVT
  ([`docs/compliance/vvt.md`](../../docs/compliance/vvt.md)).

## Verweis

- Operative Schritt-fuer-Schritt-Anleitungen (CVE-Response, Secret-Rotation,
  At-Rest-Verschluesselung, Standort/Auftragsverarbeiter, akzeptierte
  Vulnerabilities) in [`RUNBOOK.md`](./RUNBOOK.md).
- Backup/Restore-Pfad und Restore-Drill: [`RUNBOOK.md` §Backup & Restore](./RUNBOOK.md#backup--restore).
- Compliance-Dokumente (VVT, GoBD, Retention, C5-Mapping):
  [`docs/compliance/`](../../docs/compliance/).
