# Hetzner-Runbook — Who2Be Operator-Guide

Operative Schritt-fuer-Schritt-Anleitungen fuer die Who2Be-Hetzner-Instanz.
Dieses Dokument ist die **Quelle der Wahrheit** fuer Incident-Response,
CVE-Triage und Secret-Rotation. Setup-Anleitungen liegen in
`deploy/hetzner/README.md`.

Aktive Sektionen:

- [CVE-Response](#cve-response) — was tun, wenn der CI-`audit`-Job rot wird
- [Secret-Rotation](#secret-rotation) — pro Secret: Trigger / Schritte / Verifikation
- [Backup & Restore](#backup--restore) — verschluesselter pg_dump + restic-Offsite (C5a/C5b)
- [Akzeptierte Vulnerabilities](#akzeptierte-vulnerabilities) — bewusste Risikoabnahmen

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
