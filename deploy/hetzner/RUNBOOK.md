# Hetzner-Runbook — Who2Be Operator-Guide

Operative Schritt-fuer-Schritt-Anleitungen fuer die Who2Be-Hetzner-Instanz.
Dieses Dokument ist die **Quelle der Wahrheit** fuer Incident-Response,
CVE-Triage und Secret-Rotation. Setup-Anleitungen liegen in
`deploy/hetzner/README.md`.

Aktive Sektionen:

- [Provisioning (Track S/C1)](#provisioning-track-sc1) — leere Hetzner-Box → laufender Stack (Box/Docker/Firewall/deploy-User/DNS/TLS)
- [Erste Inbetriebnahme der Cloud-Edition](#erste-inbetriebnahme-der-cloud-edition) — Bring-up-Checkliste (Service-Key, Mailer, Deploy-Pipeline)
- [CVE-Response](#cve-response) — was tun, wenn der CI-`audit`-Job rot wird
- [Secret-Rotation](#secret-rotation) — pro Secret: Trigger / Schritte / Verifikation
- [Verschluesselung at-Rest](#verschluesselung-at-rest-postgres-volume) — LUKS/verschl. Hetzner-Volume + Verifikation (Befund P4/S2)
- [Standort & Auftragsverarbeiter](#standort--auftragsverarbeiter) — RZ-Standort + Sub-Processor-Liste (DSGVO/AVV)
- [Backup & Restore](#backup--restore) — verschluesselter pg_dump + restic-Offsite (C5a/C5b)
- [Akzeptierte Vulnerabilities](#akzeptierte-vulnerabilities) — bewusste Risikoabnahmen

---

## Provisioning (Track S/C1)

Von der **leeren Hetzner-Box** bis zum laufenden Stack. Diese Sektion deckt
**C1** (Server-Provisioning) ab — die Compose-Bring-up-Reihenfolge selbst steht
in [`README.md`](./README.md) (§Bring-up-Reihenfolge / §Cloud-Edition), die
Cloud-Abnahme in [`docs/cloud-prod-smoke.md`](../../docs/cloud-prod-smoke.md).

> ⚠️ **Nicht automatisierbar (manuell, einmalig):** Das Bestellen der Box
> (Schritt 1) und das Setzen der DNS-A-Records (Schritt 5) laufen ueber die
> Hetzner-Console bzw. den DNS-Anbieter — kein Skript im Repo macht das. Alle
> uebrigen Schritte sind reproduzierbare Shell-Kommandos auf dem Host.

### 1 — Box anlegen (manuell, Hetzner-Console)

- Server-Typ: Hetzner Cloud (z. B. CPX31/CPX41) **oder** dedizierter Root-Server.
- **Region:** eine **EU/EWR-Region** waehlen — fuer DE-SaaS mit Datenresidenz-
  Erwartung eine **DE-Region** (`nbg1`/`fsn1`). Die Wahl gehoert in die
  Protokoll-Tabelle unter [Standort & Auftragsverarbeiter](#standort--auftragsverarbeiter).
- **OS:** Ubuntu 24.04 LTS. Beim Anlegen den eigenen **SSH-Public-Key**
  hinterlegen (kein Passwort-Login).
- **At-Rest-Verschluesselung** des Daten-Volumes ist Pflicht und wird beim
  Provisioning entschieden — Variante + Verifikation siehe
  [Verschluesselung at-Rest](#verschluesselung-at-rest-postgres-volume). Bei
  Variante B (LUKS) **vor** dem ersten `docker compose up` einrichten.

### 2 — deploy-User + Grund-Hardening

Als `root` (oder via initialem Cloud-User) den unprivilegierten `deploy`-User
anlegen, der spaeter den Stack faehrt und das CI/CD-Deploy-Ziel ist
(`DEPLOY_USER`, siehe [README §CI/CD](./README.md#cicd-ms-2-c4)):

```bash
adduser --disabled-password --gecos "" deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
# Den Deploy-SSH-Public-Key (CI: Gegenstueck zu DEPLOY_SSH_KEY) eintragen:
$EDITOR /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
```

### 3 — Docker + Compose-v2

```bash
# Offizielles Convenience-Skript (Docker Engine inkl. Compose-v2-Plugin)
curl -fsSL https://get.docker.com | sh
# deploy-User darf Docker ohne sudo fahren
usermod -aG docker deploy
# Verifikation (frische Login-Shell des deploy-Users)
sudo -iu deploy docker compose version   # → Docker Compose version v2.x
```

### 4 — Firewall (Ports 80/443, SSH 22)

Caddy braucht **80** (ACME-HTTP-Challenge + Redirect) und **443** (HTTPS)
eingehend; **22** fuer SSH/Deploy. Alles andere bleibt zu — die API-, Web-,
Redis- und DB-Container haben bewusst **kein** `ports:` und sind nur im internen
Docker-Netz erreichbar.

```bash
# Variante a) UFW auf dem Host
ufw default deny incoming && ufw default allow outgoing
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp
ufw enable && ufw status verbose
```

> Bei Hetzner Cloud zusaetzlich/alternativ eine **Cloud-Firewall** in der
> Console anlegen (Inbound nur 22/80/443) und der Box zuweisen — sie wirkt vor
> der VM und ist die robustere Schranke.

### 5 — DNS-A-Records (manuell, DNS-Anbieter)

Beim DNS-Provider drei (optional vier) **A-Records** auf die oeffentliche
Box-IP zeigen lassen — die Subdomains, die der Caddyfile bedient:

| Record               | Ziel       | Pflicht | Backend (Caddyfile)        |
| -------------------- | ---------- | ------- | -------------------------- |
| `api.<DOMAIN>`       | `<BOX_IP>` | ja      | `api:8000`                 |
| `app.<DOMAIN>`       | `<BOX_IP>` | ja      | `web:80`                   |
| `supabase.<DOMAIN>`  | `<BOX_IP>` | ja      | `auth-gateway:9999`        |
| `mcp.<DOMAIN>`       | `<BOX_IP>` | optional| `mcp-http:8765` (`--profile mcp-http`) |

`mcp.<DOMAIN>` nur anlegen, wenn der MCP-Streamable-HTTP-Endpunkt remote
erreichbar sein soll (siehe [README §MCP-Container](./README.md#mcp-container--stdio-profile-mcp--http-profile-mcp-http)).
Auflösung pruefen, **bevor** Caddy startet (sonst schlaegt die ACME-Challenge fehl):

```bash
for sub in api app supabase; do dig +short ${sub}.${DOMAIN}; done
# Jede Zeile muss die Box-IP zeigen.
```

### 6 — Repo + .env auf den Host

```bash
sudo -iu deploy
sudo install -d -o deploy -g deploy /opt/who2be   # DEPLOY_PROJECT_DIR-Default
git clone https://github.com/luetzey/who2be.git /opt/who2be
cd /opt/who2be

# App-Stack-.env
cp deploy/hetzner/.env.example deploy/hetzner/.env
$EDITOR deploy/hetzner/.env            # DOMAIN, ACME_EMAIL, JWT_SECRET, …
chmod 600 deploy/hetzner/.env

# Supabase-Stack-.env (identisches JWT_SECRET!)
cp deploy/hetzner/supabase/.env.example deploy/hetzner/supabase/.env
$EDITOR deploy/hetzner/supabase/.env   # POSTGRES_PASSWORD, JWT_SECRET, SMTP, …
chmod 600 deploy/hetzner/supabase/.env
```

Welche Vars Pflicht sind (inkl. der Cloud-Edition-Secrets `APP_DB_PASSWORD`,
`SUPABASE_SERVICE_KEY`), steht in der
[Erste-Inbetriebnahme-Checkliste](#erste-inbetriebnahme-der-cloud-edition) unten.
Stack hochfahren: [README §Bring-up-Reihenfolge](./README.md#bring-up-reihenfolge)
(On-Prem) bzw. [README §Cloud-Edition](./README.md#cloud-edition-billing--rls--redis).

### 7 — TLS via Caddy (Auto-HTTPS) + Verifikation

Caddy holt sich beim ersten Start **automatisch** Let's-Encrypt-Zertifikate fuer
`api`/`app`/`supabase` (+ `mcp`, falls aktiv) — Voraussetzung: DNS aufgeloest
(Schritt 5) und Ports 80/443 offen (Schritt 4). `ACME_EMAIL` aus der `.env` ist
der LE-Kontakt. Kein manueller Cert-Schritt noetig. Nach dem Bring-up
verifizieren:

```bash
# 1) HTTPS terminiert + API gesund (gueltiges LE-Cert ⇒ kein -k noetig)
curl -fsSI https://api.${DOMAIN}/v1/health | head -1   # → HTTP/2 200

# 2) Zertifikats-Aussteller + Laufzeit pruefen
echo | openssl s_client -connect api.${DOMAIN}:443 -servername api.${DOMAIN} 2>/dev/null \
  | openssl x509 -noout -issuer -dates
#   issuer= …Let's Encrypt… / notAfter ~90 Tage in der Zukunft

# 3) HTTP→HTTPS-Redirect (Caddy macht das automatisch)
curl -sI http://api.${DOMAIN}/v1/health | grep -i '^location:'   # → https://…

# 4) Security-Header / Hardening (H5) gegen alle drei Subdomains
export DOMAIN=<deine-domain>   # noetig: der Test setzt den Host-Header daraus
bash deploy/hetzner/tests/test_headers.sh https://api.${DOMAIN}
```

Schlaegt die Cert-Ausstellung fehl, sind fast immer DNS (Schritt 5) oder die
Firewall (Schritt 4, Port 80 fuer die ACME-Challenge) die Ursache —
`docker compose … logs caddy` zeigt die ACME-Fehler im Klartext.

---

## Erste Inbetriebnahme der Cloud-Edition

Kompakte Bring-up-Checkliste fuer die **erste** Cloud-Inbetriebnahme nach dem
[Provisioning](#provisioning-track-sc1). Sie verzahnt die drei Vorarbeiten —
**Service-Key**, **Mailer** und **Deploy-Pipeline** — mit dem Compose-Bring-up
und der Abnahme. Reihenfolge einhalten:

- [ ] **0 — Provisioning steht:** Box, Docker, Firewall (80/443/22), deploy-User,
      DNS-A-Records aufgeloest, At-Rest-Verschluesselung verifiziert
      ([Provisioning](#provisioning-track-sc1)).
- [ ] **1 — Secrets in `deploy/hetzner/.env` (Mode 600):** `DOMAIN`, `ACME_EMAIL`,
      `JWT_SECRET` (≥ 32 Zeichen, **identisch** zu `supabase/.env`), `DATABASE_URL`,
      `SUPABASE_URL`, `CORS_ORIGINS`, `VITE_*`. Cloud-Sektion zusaetzlich:
      `APP_DB_PASSWORD` (Passwort der RLS-Rolle `who2be_app`) und —
- [ ] **2 — Service-Key (GoTrue-Admin):** `SUPABASE_SERVICE_KEY` setzen. Erzeugen
      mit demselben `JWT_SECRET` wie der ANON_KEY:
      ```bash
      uv run python scripts/gen_test_jwt.py --secret "$JWT_SECRET" --role service_role
      ```
      Ohne ihn schlagen Invitation-/Account-Loesch-Mails fehl (GoTrue-Admin-Calls).
- [ ] **3 — Mailer scharf (echter Posteingang, kein Mailpit):** in
      `deploy/hetzner/supabase/.env` `GOTRUE_MAILER_AUTOCONFIRM=false` **und**
      `GOTRUE_SMTP_HOST/PORT/USER/PASS/ADMIN_EMAIL` setzen. Pflicht, sobald
      Autoconfirm aus ist — sonst kommt keine Verify-Mail an. (Fuer einen ersten
      Solo-Smoke darf `autoconfirm` voruebergehend `true` bleiben, dann ohne SMTP.)
- [ ] **4 — Stacks hochfahren** (Supabase zuerst, dann Cloud-Overlay) gemaess
      [README §Cloud-Edition](./README.md#cloud-edition-billing--rls--redis).
      Interne Reihenfolge: `migrate` → `set-app-role-password` → `redis` → `api`.
- [ ] **5 — Cloud-Schalter greifen:**
      ```bash
      docker compose \
        -f deploy/hetzner/who2be/docker-compose.yml \
        -f deploy/hetzner/who2be/docker-compose.cloud.yml \
        --env-file deploy/hetzner/.env \
        exec api printenv WHO2BE_EDITION APP_DATABASE_URL RATE_LIMIT_STORAGE_URI
      # → cloud / postgresql://who2be_app:***@db:5432/postgres / redis://redis:6379
      ```
- [ ] **6 — TLS + Header gruen:** [Provisioning §7](#provisioning-track-sc1) inkl.
      `bash deploy/hetzner/tests/test_headers.sh https://api.${DOMAIN}`.
- [ ] **7 — Deploy-Pipeline (optional, fuer kuenftige Rollouts):** Repository-
      Variables/Secrets (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, …) gemaess
      [README §CI/CD](./README.md#cicd-ms-2-c4) hinterlegen. Danach deployt jeder
      `push: main` via `deploy/hetzner/scripts/deploy.sh <sha>`; Rollback identisch
      mit altem SHA.
- [ ] **8 — Abnahme-Reise fahren:** [`docs/cloud-prod-smoke.md`](../../docs/cloud-prod-smoke.md)
      (Signup → Verify → Pro → MCP-Quota 429 → Downgrade 402 → RLS-Nachweis).

---

## CVE-Response

Der CI-Job `audit` (`.github/workflows/ci.yml`) faehrt bei jedem Push und PR:

- **Python:** `pip-audit` gegen `uv export --no-emit-workspace` → failt bei jedem **High/Critical**.
- **Web (Prod):** `npm audit --omit=dev --audit-level=high` in `apps/web/` → failt bei jedem **High/Critical** in der Prod-Dependency-Closure.

Moderate Findings failen den Job bewusst **nicht** — sie kommen entweder
direkt in den naechsten Patch oder werden mit Begruendung unten unter
[Akzeptierte Vulnerabilities](#akzeptierte-vulnerabilities) gelistet.

### Triage-Pfad bei rotem audit-Job

1. **Logs lesen:** der pip-audit-Step listet `Name / Version / ID / Fix Versions`. Der npm-audit-Step gibt JSON; `npm audit --omit=dev --audit-level=high --json` lokal nachstellen.
2. **Severity & Reachability einschaetzen:**
   - Ist der verwundbare Code-Pfad bei uns aktiv? (z.B. Host-Header-Parsing → ja, weil Caddy/FastAPI das Host-Feld nutzen)
   - Ist es Prod-Surface (Web/API) oder nur Dev-Tooling (vitest, ruff)?
3. **Fix-Optionen, in dieser Reihenfolge:**
   - **a)** Direkt-Upgrade: `uv lock --upgrade-package <name>` (Python) bzw. `npm i -E <name>@<fix>` in `apps/web` (Web). `uv sync` / `npm test` lokal verifizieren.
   - **b)** Transitiv: bei Sub-Dep nur via Parent-Upgrade fixbar — Parent-Bump triggern, falls semver-vertraeglich.
   - **c)** Override: wenn (a)/(b) blocken, `tool.uv.override-dependencies` (Python) bzw. `npm overrides` (Web) als temporaere Bruecke. Akzeptanz-Eintrag unten Pflicht.
   - **d)** Akzeptieren: nur wenn Severity ≤ moderate **und** nicht-erreichbar im Prod-Pfad. Begruendung unten eintragen, Re-Eval-Datum setzen.
4. **PR aufmachen:** Branch `fix/cve-<id>`; Commit-Message `fix(deps): bump <name> to <fix> (CVE-<id>)`. Audit-Job muss im PR wieder gruen sein.
5. **Doku:** Wenn akzeptiert: Eintrag in [Akzeptierte Vulnerabilities](#akzeptierte-vulnerabilities). Wenn gefixt: kein Doku-Eintrag noetig, Commit ist Beleg.

### Bypass (Notfall)

Wenn ein Critical-Fix prod-blockierend ist und kein Upgrade verfuegbar ist:

- `audit`-Job temporaer auf `continue-on-error: true` in einem expliziten PR setzen, **plus** Issue-Tracking mit Frist
- Niemals den Job aus `ci.yml` loeschen. Niemals ohne dokumentiertes Re-Eval-Datum.

---

## Secret-Rotation

Alle Secrets leben in `deploy/hetzner/.env` auf dem Hetzner-Host
(Mode 600, Owner `deploy`). `.env.example` ist die Vorlage.

**Routine-Rotation:** alle 6 Monate. **Ausserordentlich:** sofort bei
Kompromittierungs-Verdacht, Personalwechsel oder Audit-Befund.

### JWT_SECRET (Supabase + API)

- **Was:** HS256-Signing-Key, mit dem GoTrue Tokens ausstellt und FastAPI sie verifiziert. **Identischer Wert** in `supabase/.env` und `deploy/hetzner/.env`.
- **Trigger:** Kompromittierungs-Verdacht (Leak in Logs, Repo, Backup), Personalwechsel mit Host-Zugriff, Routine 6 Monate.

**Schritte:**

```bash
# 1) Neues Secret generieren (mind. 32 Zeichen, base64-safe)
openssl rand -base64 48

# 2) In beiden .env-Dateien ersetzen (identischer Wert!)
$EDITOR deploy/hetzner/supabase/.env       # JWT_SECRET=...
$EDITOR deploy/hetzner/.env                # JWT_SECRET=...

# 3) ANON_KEY neu signieren (JWT mit role=anon, signed mit neuem JWT_SECRET)
uv run python scripts/gen_test_jwt.py --role anon --secret "$NEW" \
  > /tmp/anon.jwt
# Wert in supabase/.env als ANON_KEY eintragen.

# 4) Beide Stacks neustarten (Supabase zuerst, App danach)
docker compose -f deploy/hetzner/supabase/docker-compose.yml \
  --env-file deploy/hetzner/supabase/.env up -d --force-recreate
docker compose -f deploy/hetzner/who2be/docker-compose.yml \
  --env-file deploy/hetzner/.env up -d --force-recreate
```

**Verifikation:**

```bash
# Bestehende User-Sessions sind invalidiert — neuer Login muss klappen
curl -sf "https://supabase.${DOMAIN}/auth/v1/token?grant_type=password" \
  -H "apikey: ${NEW_ANON_KEY}" \
  -d '{"email":"…","password":"…"}' | jq .access_token

# Mit dem frischen access_token gegen die API
curl -sf "https://api.${DOMAIN}/v1/personas" \
  -H "Authorization: Bearer <access_token>" | jq length
```

**Side-Effects:** alle aktiven Supabase-Sessions im Web werden invalidiert
(Re-Login noetig). API-Tokens (`w2b_…`) bleiben gueltig — die haengen nicht
am JWT_SECRET.

### WHO2BE_API_TOKEN (Agent-Tokens, `w2b_…`)

- **Was:** Pro-Agent-Bearer-Tokens, Klartext-Praefix `w2b_`, im Backend SHA-256-gehashed gespeichert (`api_token`-Tabelle, ADR-0006).
- **Trigger:** Token-Leak (z.B. in Notion-Doku, MCP-Config-Repo), Verlust eines Geraets, Agent-Decommission, Routine 6 Monate.

**Schritte:**

```bash
# 1) Im Web-UI: /settings/tokens → Token revoken (DELETE /v1/tokens/{id})
#    Alternativ direkt per API:
curl -sf -X DELETE "https://api.${DOMAIN}/v1/tokens/${OLD_TOKEN_ID}" \
  -H "Authorization: Bearer <user-jwt>"

# 2) Neuen Token erzeugen (Klartext nur einmal sichtbar!)
curl -sf -X POST "https://api.${DOMAIN}/v1/tokens" \
  -H "Authorization: Bearer <user-jwt>" \
  -d '{"label":"brainstormer-claude-2026q2"}' | jq .token

# 3) Neuen Token im Agent-Setup eintragen
#    - Claude Code MCP-Server: ~/.claude.json `WHO2BE_API_TOKEN` ueberschreiben
#    - claude mcp remove who2be && claude mcp add who2be -s local ...
#      (siehe docs/mcp-claude-code.md)
```

**Verifikation:**

```bash
# Alter Token muss 401 liefern
curl -sw '%{http_code}\n' -o /dev/null "https://api.${DOMAIN}/v1/personas" \
  -H "Authorization: Bearer ${OLD_TOKEN}"   # erwartet: 401

# Neuer Token muss 200 liefern
curl -sw '%{http_code}\n' -o /dev/null "https://api.${DOMAIN}/v1/personas" \
  -H "Authorization: Bearer ${NEW_TOKEN}"   # erwartet: 200
```

**Side-Effects:** der spezifische Agent bricht ab, bis der neue Token in seiner Config steht. Andere Tokens bleiben unberuehrt.

### APP_DB_PASSWORD (Cloud-Edition, Rolle `who2be_app`)

- **Was:** Passwort der nicht-privilegierten Laufzeit-Rolle `who2be_app`, mit der die API in der **Cloud-Edition** verbindet (RLS aktiv, Migration 0036/0037). Nur relevant mit dem Cloud-Overlay (`who2be/docker-compose.cloud.yml`). On-Prem verbindet die API als Owner und liest diese Var nicht.
- **Trigger:** Kompromittierungs-Verdacht, Personalwechsel mit Host-Zugriff, Routine 6 Monate.

**Schritte:**

```bash
# 1) Neues Passwort generieren
openssl rand -base64 32

# 2) In deploy/hetzner/.env ersetzen (APP_DB_PASSWORD=...)
$EDITOR deploy/hetzner/.env

# 3) Rollen-Passwort in der DB neu setzen (One-Shot liest die .env)
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  -f deploy/hetzner/who2be/docker-compose.cloud.yml \
  --env-file deploy/hetzner/.env \
  run --rm set-app-role-password

# 4) API neu starten, damit APP_DATABASE_URL das neue Passwort traegt
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  -f deploy/hetzner/who2be/docker-compose.cloud.yml \
  --env-file deploy/hetzner/.env up -d --force-recreate api
```

**Verifikation:**

```bash
# API verbindet als who2be_app und ist healthy
curl -fsS https://api.${DOMAIN}/v1/health   # erwartet: db:"ok"
```

**Side-Effects:** kurze API-Downtime beim Recreate. Reihenfolge wichtig — erst Rollen-Passwort setzen (Schritt 3), dann API recreaten (Schritt 4); sonst verbindet die API mit dem alten Passwort gegen die geaenderte Rolle und failt der Healthcheck.

### STORAGE_BOX_USER / STORAGE_BOX_HOST / STORAGE_BOX_SSH_KEY

- **Was:** Hetzner-Storage-Box-Zugangsdaten fuer den restic-Offsite-Backup-Pfad (ADR-0011, MS-2 C5b).
- **Trigger:** SSH-Key-Leak, neuer Backup-Host, Routine 12 Monate (SSH-Keys altern langsamer).

**Schritte:**

```bash
# 1) Neuen ED25519-Keypair fuer den Backup-User generieren (am besten lokal)
ssh-keygen -t ed25519 -f ~/.ssh/who2be-backup-2026 -C "who2be-backup"

# 2) Public-Key in der Storage-Box-Verwaltung (Hetzner-Console) hinterlegen,
#    alten Key DEAKTIVIEREN (nicht loeschen, bis Schritt 5 verifiziert)

# 3) Private-Key auf den Hetzner-App-Host kopieren
scp ~/.ssh/who2be-backup-2026 deploy@hetzner:/home/deploy/.ssh/who2be-backup
ssh deploy@hetzner 'chmod 600 ~/.ssh/who2be-backup'

# 4) .env updaten
$EDITOR deploy/hetzner/.env
#   STORAGE_BOX_SSH_KEY=/home/deploy/.ssh/who2be-backup

# 5) Backup-Job ein-Schuss laufen lassen (Cron oder bash deploy/hetzner/scripts/backup.sh)

# 6) Erst nach gruen aus Schritt 5: alten Public-Key in Storage-Box loeschen
```

**Verifikation:**

```bash
# restic-Snapshot des Tages muss in der Liste sein
restic -r sftp:${STORAGE_BOX_USER}@${STORAGE_BOX_HOST}:/who2be snapshots \
  | tail -3
```

**Side-Effects:** keine — Backup-Pfad ist read-only fuer den restoring-Host. Bei zu fruehem Loeschen des alten Keys bricht der naechste Backup-Lauf.

### RESTIC_PASSWORD

- **Was:** Symmetrisches Master-Passwort fuer den restic-Repo. Mit dem Verlust dieses Passworts ist das Repo **unwiederherstellbar** — entsprechend offline + redundant zu sichern.
- **Trigger:** Verdacht auf Repo-Kompromittierung (jemand hat unbefugt das Passwort gesehen), Routine 12 Monate.

**Schritte:**

```bash
# 1) Neues starkes Passwort generieren und offline notieren (Pass-Manager + Hardcopy)
openssl rand -base64 32

# 2) Im restic-Repo das Passwort hinzufuegen (zweites Slot, dann alten loeschen)
RESTIC_PASSWORD=${OLD} restic -r sftp:… key add
# restic fragt nach dem neuen Passwort

# 3) Mit neuem Passwort verifizieren, dass der Zugriff klappt
RESTIC_PASSWORD=${NEW} restic -r sftp:… snapshots | head -3

# 4) Alten Passwort-Slot loeschen
RESTIC_PASSWORD=${NEW} restic -r sftp:… key list
RESTIC_PASSWORD=${NEW} restic -r sftp:… key remove <old-key-id>

# 5) .env updaten + Backup-Stack restarten
$EDITOR deploy/hetzner/.env
#   RESTIC_PASSWORD=...
```

**Verifikation:**

```bash
# Restore-Test (kleine Datei) muss klappen
RESTIC_PASSWORD=${NEW} restic -r sftp:… restore latest \
  --target /tmp/restic-rotation-test --include '/etc/hostname'
diff /etc/hostname /tmp/restic-rotation-test/etc/hostname  # erwartet: identisch
```

**Side-Effects:** keine, **wenn Schritte 1-4 in dieser Reihenfolge ausgefuehrt werden**. Bei vertauschter Reihenfolge: Repo bleibt mit altem Passwort nutzbar, aber `.env` zeigt auf Stand, der nicht greift → Backup-Cron bricht still ab.

### BACKUP_GPG_RECIPIENT (lokaler pg_dump-Pfad, ADR-0011 C5a)

- **Was:** GPG-Schluessel-ID (oder Email), an die `pg_dump | gpg --encrypt` adressiert wird. Lokaler Backup-Pfad neben dem restic-Offsite-Pfad.
- **Trigger:** GPG-Key abgelaufen, Personalwechsel beim Recipient, Routine 12 Monate.

**Schritte:**

```bash
# 1) Neuen GPG-Key generieren (oder vorhandenen ED25519/RSA-4096 wiederverwenden)
gpg --quick-generate-key "who2be-backup@example.org" ed25519 sign,encrypt 2y

# 2) Public-Key auf den Hetzner-Host pushen und importieren
gpg --export --armor who2be-backup@example.org > /tmp/who2be-backup.pub
scp /tmp/who2be-backup.pub deploy@hetzner:/tmp/
ssh deploy@hetzner 'gpg --import /tmp/who2be-backup.pub && rm /tmp/who2be-backup.pub'

# 3) Vertrauen setzen (sonst weigert sich --encrypt)
ssh deploy@hetzner 'echo -e "5\ny\n" | gpg --command-fd 0 --edit-key who2be-backup@example.org trust quit'

# 4) .env updaten
$EDITOR deploy/hetzner/.env
#   BACKUP_GPG_RECIPIENT=who2be-backup@example.org

# 5) Backup-Cron einmal manuell triggern
bash deploy/hetzner/scripts/backup.sh
```

**Verifikation:**

```bash
# Frisches *.sql.gpg-File muss da sein
ls -la /var/backups/who2be/*.sql.gpg | tail -2

# Decrypt-Probe (auf dem Recipient-Host, NICHT auf dem Hetzner-Host)
gpg --decrypt /tmp/latest.sql.gpg | head -5   # erwartet: '-- PostgreSQL database dump'
```

**Side-Effects:** alte `*.sql.gpg`-Dateien bleiben mit dem alten Key entschluesselbar — der Schluessel muss also weiter erreichbar bleiben, bis die letzte alte Backup-Generation aus dem Retention-Fenster faellt.

---

## Verschluesselung at-Rest (Postgres-Volume)

> ⚠️ **Disclaimer:** Engineering-/Betriebs-Checkliste, **keine** Rechts- oder
> Zertifizierungsberatung. Adressiert die Audit-Befunde **P4** (Encryption-at-Rest
> nicht belegt) und **S2** (At-Rest-Verschluesselung Live-DB nicht nachweisbar)
> aus `.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md`. Die
> tatsaechlich umgesetzte Variante ist vom Betreiber je nach Hetzner-Produkt zu
> waehlen und unten zu protokollieren.

Die Live-Datenbank liegt im Docker-Volume `db-data` (siehe `docker-compose.yml`
bzw. den self-hosted-Supabase-Stack). „At-Rest" heisst: die Bytes auf dem
Block-Device, auf dem dieses Volume liegt, sind im Ruhezustand verschluesselt —
ein gestohlenes/aussortiertes Laufwerk gibt ohne Schluessel keine Klartextdaten
preis. Anwendungs-/Transport-Verschluesselung (TLS via Caddy) und Backup-
Verschluesselung (GPG + restic, siehe unten) sind **separat** und ersetzen das
nicht.

Es gibt zwei betrieblich uebliche Wege auf Hetzner — **genau einen** waehlen und
die Wahl in der Protokoll-Tabelle unten festhalten:

### Variante A — verschluesseltes Hetzner Cloud Volume / Storage

Hetzner Cloud Volumes werden serverseitig at-Rest verschluesselt (LUKS auf der
Plattform-Ebene). Wenn das `db-data`-Volume auf einem Cloud-Volume liegt:

1. Bestaetigen, dass das Datenverzeichnis auf dem Cloud-Volume-Mount liegt
   (nicht auf der lokalen Boot-Disk):

   ```bash
   # Wo liegt der Docker-Volume-Mountpoint physisch?
   docker volume inspect who2be_db-data --format '{{ .Mountpoint }}'
   # Den Pfad gegen die Mounts halten — muss auf dem Cloud-Volume-Device sitzen:
   findmnt -no SOURCE,TARGET --target "$(docker volume inspect who2be_db-data --format '{{ .Mountpoint }}')"
   lsblk -o NAME,FSTYPE,MOUNTPOINT,SIZE
   ```

2. **Nachweis** ist die Hetzner-Console/-API-Eigenschaft des Volumes
   (Encryption „aktiv") plus ein Screenshot/Export in der Betreiber-Doku.
   `<PLATZHALTER: Volume-ID + Hetzner-Console-Beleg>`.

> Hinweis: Bei reiner Plattform-Verschluesselung ist auf OS-Ebene **kein**
> `crypt`-Device sichtbar (`lsblk` zeigt das Volume als normales `ext4`/`xfs`),
> weil die Verschluesselung unterhalb der VM passiert. Der Beleg kommt dann aus
> der Hetzner-Console, nicht aus `cryptsetup`.

### Variante B — LUKS-Full-Disk-Encryption auf dem Host (selbst verwaltet)

Wenn das Volume auf einem dedizierten/Root-Server liegt, wird LUKS selbst
eingerichtet (einmalig bei Provisioning, **vor** dem ersten `docker compose up`):

1. Block-Device als LUKS-Container initialisieren (Beispiel-Device — am realen
   Setup anpassen, **keine** Passphrase ins Repo):

   ```bash
   sudo cryptsetup luksFormat /dev/sdb           # einmalig, zerstoert Daten
   sudo cryptsetup open /dev/sdb cryptdata        # mappt nach /dev/mapper/cryptdata
   sudo mkfs.ext4 /dev/mapper/cryptdata
   sudo mkdir -p /opt/who2be/data
   sudo mount /dev/mapper/cryptdata /opt/who2be/data
   ```

2. Auto-Unlock beim Boot ueber ein Keyfile (Mode 600, **nicht** im Repo, nicht im
   Backup-Klartext) in `/etc/crypttab` + `/etc/fstab` verdrahten. Schluessel-
   verwahrung: `<PLATZHALTER: Keyfile-/Passphrase-Verwahrung (z. B. versiegelter
   Umschlag / HSM / Passwort-Manager)>`.
3. Den Docker-Volume-Pfad bzw. `data_directory` auf den entschluesselten
   Mountpoint legen, sodass `db-data` physisch im LUKS-Container landet.

### Reproduzierbarer Verifikationsschritt

Nach jedem (Re-)Provisioning bzw. Host-Wechsel ausfuehren und das Ergebnis in der
Tabelle unten protokollieren:

```bash
# Variante B (LUKS sichtbar auf OS-Ebene): Datentyp muss "crypto_LUKS" sein,
# das Mapper-Device aktiv.
lsblk -o NAME,FSTYPE,MOUNTPOINT,SIZE
sudo cryptsetup status cryptdata     # erwartet: "is active", cipher/keysize sichtbar

# Variante A (Plattform-Volume): Mount auf dem Cloud-Volume-Device nachweisen
findmnt --target /opt/who2be/data    # bzw. der reale Daten-Mount
# Encryption-Beleg = Hetzner-Console-Eigenschaft des Volumes (siehe oben).
```

**Akzeptanzkriterium:** Bei Variante B zeigt `cryptsetup status cryptdata`
`is active` und `lsblk` `crypto_LUKS` fuer das Daten-Device; bei Variante A liegt
der Daten-Mount nachweislich auf dem verschluesselten Hetzner-Volume + Console-
Beleg. **Keine** Passphrase/kein Keyfile-Inhalt wird je ins Repo, in Logs oder in
Klartext-Backups geschrieben.

| Datum | Variante (A/B) | Host/Volume | Verifikations-Output abgelegt | Ausgefuehrt von |
|---|---|---|---|---|
| — | — | — | — | — |

---

## Standort & Auftragsverarbeiter

> ⚠️ **Disclaimer:** Betriebs-/Nachweis-Dokumentation, **keine** Rechtsberatung.
> Die vollstaendige, rechtsverbindliche Auftragsverarbeiter-Liste fuehrt der
> Betreiber im AVV/VVT (siehe `docs/compliance/vvt.md`). Diese Tabelle ist der
> technische Stand aus den Deploy-Artefakten.

**Rechenzentrums-Standort (Hetzner):** Who2Be wird auf Hetzner betrieben.
Verfuegbare Hetzner-Regionen sind Deutschland (Nuernberg `nbg1`, Falkenstein
`fsn1`) und Finnland (Helsinki `hel1`) — alle innerhalb der EU/des EWR. Der
konkret gewaehlte Standort: `<PLATZHALTER: gewaehlte Hetzner-Region, z. B. fsn1 (DE)>`.
Empfehlung fuer DE-SaaS mit Datenresidenz-Erwartung: eine **DE-Region** waehlen
und das hier sowie im VVT festhalten.

**Auftragsverarbeiter / Sub-Processors (technischer Stand):**

| Empfaenger | Rolle | Datenkategorien | Standort | Beleg |
|---|---|---|---|---|
| Hetzner Online GmbH | Hosting/IaaS (Server, Volume, Storage-Box) | gesamte DB at-Rest, Backups | DE/FI (EU/EWR) | `docker-compose.yml`, `deploy/hetzner/**` |
| Mollie B.V. | Zahlungsdienstleister (PSP) | Zahlungs-/Abodaten (Mollie-seitig); App speichert nur Entitlement-Status + `external_ref` | NL (EU/EWR) | `packages/billing/**` |
| GoTrue (self-hosted, Supabase) | Authentifizierung | E-Mail, Auth-Metadaten (`auth.users`) | selbst gehostet (= Hetzner-Standort) | `docker-compose.yml` (`supabase/gotrue`) |
| Mail-/SMTP-Provider | Transaktionsmails (Verify/Invite/Reset) | E-Mail-Adresse, Mail-Inhalt | `<PLATZHALTER: Mail-Provider + Standort>` | GoTrue-SMTP-Env |

Drittland-Transfer: nach aktuellem technischem Stand **keiner** (alle benannten
Verarbeiter EU/EWR) — Ausnahme: ein etwaiger Mail-/SMTP- oder OAuth-Provider
(Google/GitHub-Login, falls aktiviert) ist vom Betreiber zu pruefen und im VVT zu
ergaenzen. Querverweis: `docs/compliance/vvt.md`, `docs/compliance/c5-mapping.md`.

---

## Backup & Restore

Zwei-Stufen-Backup pro ADR-0011:

- **C5a — lokal:** `pg_dump -Fc | gpg --encrypt -r $BACKUP_GPG_RECIPIENT` ablegen unter
  `/var/backups/who2be/dump-<ts>.pgc.gpg`. Retention 7 Tage.
- **C5b — offsite:** `restic` schiebt das ganze Backup-Verzeichnis via SFTP auf eine
  Hetzner-Storage-Box. Retention `keep-daily 7 / keep-weekly 4 / keep-monthly 6` + Prune.

Beide Schritte fahren im selben Container (`backup`-Service, `--profile backup`).
Wenn `RESTIC_REPOSITORY` leer ist, laeuft nur Schritt 1 — Lokal-only-Modus fuer
Probelaeufe ohne Storage Box.

### Initial-Setup (einmalig nach C1-Hetzner-Provisioning)

```bash
# 1) GPG-Recipient-Key auf dem Host importieren und Trust setzen
gpg --import /tmp/who2be-backup.pub
echo -e "5\ny\n" | gpg --command-fd 0 --edit-key who2be-backup@example.org trust quit

# 2) Secrets-Verzeichnis fuer die Volume-Mounts anlegen
sudo mkdir -p /opt/who2be/secrets/gpg /opt/who2be/secrets/ssh
sudo cp -a ~/.gnupg/. /opt/who2be/secrets/gpg/
sudo chmod -R 700 /opt/who2be/secrets/gpg

# 3) SSH-Key fuer die Hetzner-Storage-Box erzeugen + auf dem Robot hinterlegen
ssh-keygen -t ed25519 -f /opt/who2be/secrets/ssh/storage_box_ed25519 -N "" \
  -C "who2be-backup"
# Public-Key (storage_box_ed25519.pub) im Hetzner-Robot bei der Storage Box eintragen.

# 4) .env auf dem Host fuellen (deploy/hetzner/.env):
#    POSTGRES_PASSWORD, BACKUP_GPG_RECIPIENT, RESTIC_REPOSITORY, RESTIC_PASSWORD

# 5) Erstlauf — restic init passiert idempotent im Script
cd /opt/who2be && docker compose --profile backup run --rm backup
```

### Trigger (Routine)

```bash
# Host-Crontab fuer den Deploy-User (crontab -e):
15 3 * * * cd /opt/who2be && docker compose --profile backup run --rm backup >> /var/log/who2be-backup.log 2>&1
```

Bewusst Host-Cron, nicht Compose-Sidecar — spart den Dauerlauf eines Backup-Containers.

### Verifikation

```bash
# Lokaler Dump vom heutigen Tag muss da sein
ls -la /var/backups/who2be/dump-*.pgc.gpg | tail -3

# Offsite-Snapshot juenger als 26h
restic -r "${RESTIC_REPOSITORY}" \
  -o "sftp.args=-i ${BACKUP_SSH_HOME}/storage_box_ed25519 -o StrictHostKeyChecking=accept-new" \
  snapshots --last 3
```

### Restore (Recovery)

Vollwiederherstellung gegen eine leere Test-DB:

```bash
# 1) Optional offsite holen, sonst direkt /var/backups/who2be nutzen
restic -r "${RESTIC_REPOSITORY}" restore latest --target /tmp/restore

# 2) GPG-entschluesseln (Recipient-Private-Key muss verfuegbar sein)
LATEST=$(ls -1t /tmp/restore/var/backups/who2be/dump-*.pgc.gpg | head -1)
gpg --decrypt "$LATEST" > /tmp/dump.pgc

# 3) Leere Ziel-DB anlegen + pg_restore
docker compose exec db psql -U supabase_admin postgres \
  -c "CREATE DATABASE who2be_restore"
docker compose exec -T db pg_restore -U supabase_admin -d who2be_restore \
  --clean --if-exists < /tmp/dump.pgc

# 4) Verifizieren: Persona-Count entspricht der prod-DB
docker compose exec db psql -U supabase_admin who2be_restore \
  -c "SELECT count(*) FROM persona"
```

**H4-Restore-Drill** ist ein vollstaendiger Probelauf der obigen Schritte (lokaler
Dump + Restore in `who2be_restore` + Count-Vergleich), nach jedem prod-Cutover
einmal durchziehen und Datum hier protokollieren:

| Datum | Backup-Quelle | Restore-Ziel | Persona-Count match | Ausgefuehrt von |
|---|---|---|---|---|
| — | — | — | — | — |

## MinIO-/BlobStore-Backup (ADR-0048)

Der `pg_dump`-Pfad oben sichert **nur Postgres**. Die Binaerinhalte der
WorkArea (PDFs, Textdateien, abgerufene Seiten) liegen als Objekte im MinIO-
Bucket `who2be-blobs` unter `blobs/{workspace_id}/{sha256}`. Postgres kennt
davon nur den Katalog (`wa_blob`): **ein Restore ohne Objekte ergibt eine DB,
deren Blob-Referenzen ins Leere zeigen.** Beide Stufen gehoeren zusammen.

Der Dienst laeuft als Container `minio` (+ One-Shot `minio-bootstrap`, der den
Bucket idempotent anlegt und terminiert); Daten liegen im Volume `minio-data`.

```bash
# 1) Bucket in das Backup-Verzeichnis spiegeln (mc mirror ist inkrementell)
docker compose run --rm --entrypoint /bin/sh minio-bootstrap -c '
  mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" &&
  mc mirror --overwrite --remove local/who2be-blobs /backup/blobs
'
# Dafuer /var/backups/who2be als /backup in den One-Shot mounten
# (deploy/hetzner/docker-compose.yml, gleiches Muster wie der backup-Service).

# 2) restic nimmt das Verzeichnis mit — es liegt unter /var/backups/who2be,
#    das der bestehende C5b-Lauf ohnehin sichert. Kein zweites Repo noetig.
```

- **Retention:** faellt mit dem restic-Repo zusammen (`keep-daily 7 /
  keep-weekly 4 / keep-monthly 6`).
- **`--remove`** loescht im Spiegel, was im Bucket nicht mehr existiert —
  gewollt, damit ein GDPR-Purge nicht ueber das Backup wieder auflebt.
  Die Snapshot-Historie haelt die Objekte dennoch bis zum Retention-Ablauf;
  es gilt „Restore-only-Re-Deletion" wie fuer die DB (Loeschkonzept §4).
- **Verschluesselung:** GPG wie beim Dump ist hier unnoetig — restic
  verschluesselt das Repo selbst.

**Restore:** erst Objekte, dann DB (oder umgekehrt — die Reihenfolge ist egal,
solange beide aus demselben Snapshot stammen).

```bash
restic -r "${RESTIC_REPOSITORY}" restore latest --target /tmp/restore
docker compose run --rm --entrypoint /bin/sh minio-bootstrap -c '
  mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" &&
  mc mb --ignore-existing local/who2be-blobs &&
  mc mirror --overwrite /backup/blobs local/who2be-blobs
'
# Konsistenz-Check: jede wa_blob-Zeile muss ein Objekt haben
docker compose exec db psql -U supabase_admin who2be -tAc \
  "SELECT count(*) FROM wa_blob"
docker compose run --rm --entrypoint /bin/sh minio-bootstrap -c '
  mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" &&
  mc ls --recursive local/who2be-blobs | wc -l
'
```

> Die Objekt-Zahl darf **groesser** sein als die Zeilen-Zahl (Rueckstaende
> gescheiterter Ingests, die der Purge-Sweep noch nicht geholt hat) — aber nie
> kleiner. Ist sie kleiner, fehlen Blobs.

---

## Tabellen-Store-Backup (SQLite je WorkArea, ADR-0049)

Die Zeilen der Agenten-Tabellen liegen **nicht in Postgres**, sondern in einer
SQLite-Datei pro WorkArea:

```
${WHO2BE_TABLESTORE_DIR}/{workspace_id}/{area_id}.sqlite
# Compose: Volume `tablestore-data`, im API-Container /data/tablestore
```

In Postgres steht nur der Katalog (`wa_table`, Schema + Name). **Ein
`pg_dump`-Restore liefert also leere Tabellen**, wenn dieses Verzeichnis fehlt.

**Nicht einfach kopieren:** eine SQLite-Datei im WAL-Modus ist waehrend eines
laufenden Imports kein konsistenter Stand. Der Store bringt deshalb
`VACUUM INTO` mit (`TableStore.snapshot_to`) — das erzeugt unter dem
Area-Write-Lock eine kompaktierte, eigenstaendig lesbare Kopie.

```bash
# Konsistente Snapshots aller Area-Dateien in das Backup-Verzeichnis
docker compose exec api python - <<'PY'
import asyncio, pathlib
from who2be_api.services.tablestore_provider import get_table_store

async def main() -> None:
    store = get_table_store()
    target_root = pathlib.Path("/backup/tablestore")
    for workspace_dir in store.base_dir.iterdir():
        if not workspace_dir.is_dir():
            continue
        for path in workspace_dir.glob("*.sqlite"):
            target = target_root / workspace_dir.name / path.name
            target.unlink(missing_ok=True)   # VACUUM INTO lehnt ein existierendes Ziel ab
            await store.snapshot_to(
                __import__("uuid").UUID(workspace_dir.name),
                __import__("uuid").UUID(path.stem),
                target,
            )
            print("snapshot", target)

asyncio.run(main())
PY
```

- `/backup/tablestore` liegt unter `/var/backups/who2be` und faellt damit in
  denselben restic-Lauf wie Dump und Blob-Spiegel.
- **Restore:** Snapshot-Dateien zurueck nach
  `${WHO2BE_TABLESTORE_DIR}/{workspace_id}/{area_id}.sqlite` kopieren
  (WAL-/SHM-Seitendateien werden **nicht** mitgesichert und sind nicht noetig —
  der Snapshot ist in sich vollstaendig), danach die API neu starten.
- **Verifikation:** `sqlite3 <datei> "PRAGMA integrity_check"` muss `ok`
  liefern; die Tabellennamen muessen zu `wa_table.name` derselben Area passen.

> **Manuelle Nachbereinigung nach einem Hard-Purge:** Der Purge-Sweep
> `cleanup_deleted_area_stores` loescht nur Dateien von Areas, deren
> **Workspace noch existiert** (Schutz gegen einen Lauf gegen die falsche DB).
> Nach einem Org-/Workspace-Hard-Purge bleiben die Verzeichnisse liegen und
> werden nur gemeldet (`unknown_store_dirs` in der Purge-Ausgabe + WARNING im
> Log). Diese Verzeichnisse sind manuell zu loeschen — sie enthalten
> personenbezogene Daten (Loeschkonzept §4a).

```bash
# Kandidaten: Verzeichnisse ohne Workspace-Zeile
docker compose exec db psql -U supabase_admin who2be -tAc \
  "SELECT id FROM workspace" | sort > /tmp/ws-live.txt
docker compose exec api ls /data/tablestore | sort > /tmp/ws-dirs.txt
comm -13 /tmp/ws-live.txt /tmp/ws-dirs.txt   # -> nach Pruefung loeschen
```

---

## Retention-Cron (`who2be-purge`)

Ein Lauf erledigt beides: den DSGVO-Hard-Purge (Orgs/Accounts nach der
30-Tage-Grace) **und** die drei WorkArea-/KB-Sweeps. Alle Schritte sind
idempotent — ein Lauf ohne faellige Daten ist ein No-op, ein abgebrochener
Lauf wird vom naechsten fortgesetzt.

```bash
# Host-Crontab des Deploy-Users (crontab -e):
30 3 * * * cd /opt/who2be && docker compose run --rm api who2be-purge >> /var/log/who2be-purge.log 2>&1
```

Der Lauf braucht `DATABASE_URL` (Owner-Rolle, RLS-Bypass), und fuer die
Objekt-/Datei-Sweeps dieselben `WHO2BE_BLOBSTORE_*`- und
`WHO2BE_TABLESTORE_DIR`-Werte wie die API — `docker compose run api` bringt
beides mit, ein Lauf ausserhalb des Compose-Kontexts nicht.

Ausgabe (zwei Zeilen, beide ins Log):

```
Purge: 0 Org(s), 0 Account(s) geloescht; 0 Audit-Zeile(n) anonymisiert, …
Retention: 12 Artifact(s) abgelaufen, 3 Blob-Zeile(n) + 3 Objekt(e) verwaist, 1 Area-Store(s) entfernt
```

Worauf im Log zu achten ist:

| Meldung | Bedeutung | Aktion |
|---|---|---|
| `(kein BlobStore konfiguriert)` | `WHO2BE_BLOBSTORE_*` fehlt im Purge-Kontext | Env pruefen — sonst bleiben Objekte dauerhaft liegen |
| `… unbekannte(s) Store-Verzeichnis(se) gemeldet` | Tabellen-Store-Verzeichnis ohne Workspace | manuelle Bereinigung (s. o.) |
| `Objekt-Sweep bei 500 Loeschungen gedeckelt` | Deckel erreicht | normal nach grossem Purge; naechster Lauf macht weiter |
| `liefert kein Objekt-Alter` | Store ohne `last_modified` | nur bei Fremd-Adaptern; MinIO kann es |

---

## Betrieb der Compose-Dienste `minio` / `minio-bootstrap`

- **`minio`** — S3-API auf `9000`, Web-Console auf `9001`, beide bewusst nur
  auf `127.0.0.1` gebunden (Dev laeuft mit Default-Credentials und darf nie im
  LAN haengen). In Prod `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` setzen und den
  Zugriff ueber das Docker-Netz bzw. Caddy fuehren, nicht ueber den Host-Port.
  Image ist **gepinnt** (kein `latest`) — Objekt-Storage soll nicht an einem
  impliziten Image-Sprung haengen.
- **`minio-bootstrap`** — One-Shot: legt `who2be-blobs` idempotent an und
  terminiert (`restart: "no"`). Die App legt **nie** selbst Buckets an. Der
  `api`-Dienst haengt per `service_completed_successfully` daran; ein
  fehlgeschlagener Bootstrap haelt also den Start auf — das ist Absicht.
- **Healthcheck:** `mc ready local`. Rot? → `docker compose logs minio`,
  meist ein Volume-/Rechteproblem auf `minio-data`.
- **Degradation:** ohne `WHO2BE_BLOBSTORE_*` in der API laeuft der Stack
  vollstaendig weiter; nur Ingest und Blob-Reads antworten 503
  `blobstore_unconfigured` (ADR-0048). Das ist ein gueltiger Betriebsmodus,
  kein Fehlerzustand.
- **Tabellen-Store** braucht keinen eigenen Dienst — nur das Volume
  `tablestore-data` (gemountet auf `/data/tablestore`). Es muss in die
  Backup-Routine (s. o.); ein verlorenes Volume bedeutet verlorene
  Tabellen-Zeilen bei intaktem Katalog.

```bash
# Smoke nach dem Deploy
docker compose ps minio minio-bootstrap        # minio healthy, bootstrap exited 0
docker compose exec api python -c \
  "from who2be_api.blobstore import build_blob_store; print(build_blob_store())"
# -> MinioBlobStore-Instanz (nicht None), sonst fehlt WHO2BE_BLOBSTORE_*
```

---

### Verifikation der Caddy-Hardening (H5)

Nach jedem Caddy-/Compose-Deploy gegen Prod:

```bash
bash deploy/hetzner/tests/test_headers.sh https://api.${DOMAIN}
```

Prueft Security-Header, `/v1/internal/*`-Block (403) und den Docs-Toggle.

---

## Akzeptierte Vulnerabilities

Bewusste Risikoabnahmen (Severity ≤ moderate, kein Prod-Surface).
**Re-Eval-Pflicht** bei jedem Eintrag.

| Datum | Komponente | Advisory | Severity | Begruendung | Re-Eval |
|---|---|---|---|---|---|
| 2026-05-26 | — | — | — | Stand `npm audit` und `pip-audit` sind **clean**. Keine offenen Akzeptanzen. | — |

Wenn ein neuer Akzeptanz-Eintrag faellig wird: Datum + Advisory + Severity +
**warum nicht fixbar** + **warum nicht prod-erreichbar** + Re-Eval-Datum (≤ 90 Tage).
