# Cloud-Edition PROD — Abnahme der bezahlten Reise

End-to-End-Abnahme der **Cloud-Edition** auf der **produktiven Hetzner-Instanz**.
Das ist die Prod-Adaption von [`docs/cloud-local-smoke.md`](./cloud-local-smoke.md):
gleiche Reise, aber gegen `https://api.<DOMAIN>` statt `localhost` und mit einem
**echten Posteingang** statt Mailpit.

Reise: **Signup → Verify-Mail (echte Inbox) → Login → Pro-Entitlement
(Admin-Override **oder** Mollie-Test) → MCP-Quota bis 429 → Downgrade (402) →
RLS-Nachweis (`who2be_app`)**.

> **Voraussetzung:** Provisioning + erste Cloud-Inbetriebnahme sind durch —
> siehe [`deploy/hetzner/RUNBOOK.md` §Provisioning](../deploy/hetzner/RUNBOOK.md#provisioning-track-sc1)
> und [§Erste Inbetriebnahme der Cloud-Edition](../deploy/hetzner/RUNBOOK.md#erste-inbetriebnahme-der-cloud-edition).
> Der Cloud-Stack laeuft (`WHO2BE_EDITION=cloud`, API als `who2be_app`, Redis als
> Rate-Limit-Backend), DNS/TLS stehen, Header-Check ist gruen.

> **Wer haakt ab?** Du (User). Die Browser-Schritte (Mail-Postfach, Web-Login,
> optionaler Mollie-Test-Checkout) laufen auf **deiner Workstation** gegen die
> oeffentlichen `https://…`-URLs.

## 0 — Konventionen & Voraussetzungen

- Shell-Zugriff auf den Hetzner-Host als `deploy`-User, Repo unter `/opt/who2be`.
- `curl` + ein Browser (Web-UI, Mail-Postfach) auf deiner Workstation.
- Ein **API-Token** (`w2b_…`) eines **Admin**-Users im Ziel-Workspace
  (Web-UI → `/settings/tokens`). Der erste registrierte User ist Admin seiner
  Org — sein Token traegt die Admin-Rolle (Snapshot, ADR-0023).
- **Optional (nur Variante B, §4):** ein **Mollie-Test-Key** (`test_…`) in
  `deploy/hetzner/.env` (`MOLLIE_API_KEY`). Ohne Key faehrt der Stack genauso —
  Variante A (Admin-Override) deckt die Reise vollstaendig ab.

Auf dem Host bietet sich fuer die langen Compose-Aufrufe je ein Alias an — die
DB liegt im **Supabase**-Stack, der App-Stack im **who2be**-Cloud-Overlay:

```bash
cd /opt/who2be
# Cloud-App-Stack (api, redis, set-app-role-password, migrate):
alias dcc='docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  -f deploy/hetzner/who2be/docker-compose.cloud.yml \
  --env-file deploy/hetzner/.env'
# Supabase-Stack (db, auth/GoTrue, auth-gateway):
alias dsb='docker compose \
  -f deploy/hetzner/supabase/docker-compose.yml \
  --env-file deploy/hetzner/supabase/.env'
export DOMAIN=<deine-domain>     # z. B. example.com
```

> **Unterschied zu lokal:** Lokal liegt die DB im selben Compose, hier im
> separaten Supabase-Stack — `exec db …` laeuft deshalb ueber `dsb`, nicht `dcc`.
> DB-Name ist `postgres`, Owner `supabase_admin` (nicht `who2be`/`postgres` wie lokal).

## 1 — Stack-Gesundheit bestaetigen

```bash
# API gesund hinter Caddy (gueltiges LE-Cert ⇒ kein -k)
curl -fsS https://api.${DOMAIN}/v1/health
# → {"status":"ok","version":"…","db":"ok"}

# Cloud-Schalter greifen
dcc exec api printenv WHO2BE_EDITION APP_DATABASE_URL RATE_LIMIT_STORAGE_URI
# → cloud / postgresql://who2be_app:***@db:5432/postgres / redis://redis:6379
```

- [ ] `db:"ok"` und `WHO2BE_EDITION=cloud`.

## 2 — Signup → Verify-Mail (echte Inbox) → Login

In Prod ist `GOTRUE_MAILER_AUTOCONFIRM=false` und ein echter SMTP-Mailer aktiv
(siehe RUNBOOK-Checkliste §3) — Signups muessen die E-Mail **bestaetigen**, und
die Verify-Mail landet im **realen Postfach** der genutzten Adresse (kein Mailpit).

1. **Signup** im Browser auf <https://app.${DOMAIN}/signup> (E-Mail + Passwort,
   ≥ 6 Zeichen). Eine Adresse nutzen, deren Postfach du oeffnen kannst.
   Alternativ per API gegen GoTrue:

   ```bash
   curl -s -X POST https://supabase.${DOMAIN}/auth/v1/signup \
     -H "apikey: ${VITE_SUPABASE_ANON_KEY}" \
     -H "Content-Type: application/json" \
     -d '{"email":"pro@deine-domain.tld","password":"streng-geheim"}'
   ```

2. **Verify-Mail oeffnen:** im echten Postfach die „Confirm your signup"-Mail
   suchen (ggf. Spam pruefen) → **Confirm**-Link folgen. Der Link zeigt auf
   `https://app.${DOMAIN}/auth/callback#access_token=…`
   (`GOTRUE_MAILER_URLPATHS_CONFIRMATION=/auth/callback`, `SITE_URL=https://app.${DOMAIN}`).

   - [ ] Klick landet auf der Web-`/auth/callback`-Route und ist eingeloggt.

3. **Login** (falls die Session nicht direkt steht):
   <https://app.${DOMAIN}/login> → Redirect auf das Default-Workspace-Dashboard.

> Ohne Confirm bleibt der User **un-bestaetigt** und der Login schlaegt fehl —
> genau das belegt, dass die Mail-Pflicht in Prod greift. Kommt keine Mail an:
> `dsb logs auth` auf SMTP-Fehler pruefen (`GOTRUE_SMTP_*`).

## 3 — IDs ermitteln (Token / Org / Workspace)

```bash
export TOK=w2b_<dein-admin-token>     # aus /settings/tokens (Admin-User)

curl -s https://api.${DOMAIN}/v1/me -H "Authorization: Bearer $TOK" \
  | python3 -m json.tool
# → "organizations":[{"id":"<ORG_ID>","workspaces":[{"id":"<WS_ID>", …}]}]
```

`<WS_ID>` ist die Workspace-Id derselben Org. Alternativ direkt aus der DB
(ueber den Supabase-Stack):

```bash
dsb exec db psql -U supabase_admin -d postgres -c "SELECT id, name FROM organization;"
```

## 4 — Pro-Entitlement setzen

Frisch registrierte Cloud-Orgs starten auf **Free** (`mcp_monthly_quota=1000`,
`mcp_rate_per_min=30`, Featureset `core`). Auf **Pro** heben (Features
Composite/Agents/Audit-Export, `100_000` / `240`) geht auf zwei aequivalenten
Wegen.

### 4 — Variante A (Default, OHNE Mollie): Admin-Override

Der **admin-only Cloud-Endpunkt** `POST …/billing/override` schreibt ein
**befristetes** `manual_override` direkt in `org_entitlement` (auditiert via
`reason`/`created_by`, ADR-0028) — der Tier-Default (Features + Quota/Rate) kommt
aus `plans.py` (Single Source of Truth). Kein Mollie noetig.

```bash
curl -s -X POST https://api.${DOMAIN}/v1/workspaces/<WS_ID>/billing/override \
  -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
  -d '{"plan":"pro","days":30,"reason":"Solo-Smoke Prod-Abnahme"}' \
  | python3 -m json.tool
# → {"plan":"pro","expires_at":"…","features":["agents","audit_export","composite_playbooks","core"]}
```

> **Hinweis:** Das fruehere rohe CLI `who2be-set-entitlement` ist entfernt (G-3);
> es gibt keinen Tabellen-Write per CLI mehr. Der Admin-Override oben ist der
> kontrollierte, auditierte Ersatz — `pro` ist der einzige buchbare Tier
> (`plan_by_code`), `free` wird **nicht** ueber diesen Pfad gesetzt (Downgrade
> siehe §6). Der Override ist pflicht-befristet (`days` 1–365); fuer einen Test
> reicht eine kurze Laufzeit.

### 4 — Variante B (OPTIONAL, mit Mollie-Test-Key): Test-Checkout

Nur wenn ein **Mollie-Test-Key** in `deploy/hetzner/.env` (`MOLLIE_API_KEY=test_…`)
gesetzt ist (sonst 503). Belegt zusaetzlich den Pull-Adapter inkl. Webhook-Pfad —
und in Prod ist die Webhook-URL oeffentlich erreichbar (kein Tunnel noetig).

1. **Entitlement vorher** lesen (Free-Defaults bestaetigen):

   ```bash
   curl -s https://api.${DOMAIN}/v1/workspaces/<WS_ID>/billing/entitlement \
     -H "Authorization: Bearer $TOK" | python3 -m json.tool
   # → status:"active", mcp_monthly_quota:1000, mcp_rate_per_min:30
   ```

2. **Checkout starten** (admin-only) — in der Web-UI unter `/settings/billing`
   „Upgrade auf Pro", oder per API:

   ```bash
   curl -s -X POST https://api.${DOMAIN}/v1/workspaces/<WS_ID>/billing/checkout \
     -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
     -d '{"plan":"pro"}'
   # → {"checkout_url":"https://www.mollie.com/checkout/test-mode/…"}
   ```

3. **Test-Zahlung** im Browser: die `checkout_url` oeffnen → Mollie-Test-Modus
   → Status **„paid"** → Redirect zurueck auf `/settings/billing`.

4. **Webhook → Entitlement-Upsert.** Mollie ruft
   `POST https://api.${DOMAIN}/v1/billing/mollie/webhook` mit der Payment-`id`;
   die API pullt das Objekt aktiv und hebt das Entitlement auf Pro
   (`MOLLIE_WEBHOOK_URL` zeigt in der `.env` auf genau diese URL). Anders als
   lokal ist die URL hier oeffentlich — **kein** Tunnel/Replay noetig.

### Entitlement-Check (beide Varianten)

```bash
curl -s https://api.${DOMAIN}/v1/workspaces/<WS_ID>/billing/entitlement \
  -H "Authorization: Bearer $TOK" | python3 -m json.tool
# → mcp_monthly_quota:100000, mcp_rate_per_min:240,
#   features enthaelt composite_playbooks/agents/audit_export
```

- [ ] Quota + Features sind auf Pro angehoben.

## 5 — MCP-Quota bis 429

Das MCP-Limit-Gate greift **nur** in der Cloud-Edition und **nur** fuer
API-Token-Aufrufer (`w2b_…`) — Web-/JWT-Reads passieren ungehindert. Zwei
Schranken: **Per-Token-Rate/min** und das **Monats-Kontingent** (beide → **429**);
ein `inactive` Entitlement → 402.

Auf Pro ist die **Per-Minute-Rate (240/min)** die in Sekunden erreichbare
Schranke (das 100k-Monatskontingent von Hand auszuschoepfen ist unpraktikabel).
Ueber das Per-Token-Rate-Ceiling bursten:

```bash
for i in $(seq 1 260); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    https://api.${DOMAIN}/v1/workspaces/<WS_ID>/personas \
    -H "Authorization: Bearer $TOK"
done | sort | uniq -c
# → erst 200er, ab dem 240. Read innerhalb der Minute 429er
```

- [ ] Es erscheinen `429`-Antworten (`detail":"Token-Ratenlimit ueberschritten."`
      bzw. bei ausgeschoepftem Monatskontingent
      `"Monatliches MCP-Kontingent erschoepft."`).

> Der echte MCP-Pfad laeuft identisch — der Streamable-HTTP-Server hinter
> `mcp.${DOMAIN}` (`--profile mcp-http`) bzw. `dcc run --rm mcp …` nutzt dieselbe
> API; das Gate sitzt server-seitig in der API, nicht im MCP-Prozess.

## 6 — Downgrade-Enforcement (402)

Belegt den Fall „Kuendigung / Override abgelaufen": das Entitlement faellt zurueck
auf **Free** (gated Features weg, Free-Limits gelten). Da `free` kein buchbarer
Tier ist (§4), ist der reproduzierbare Weg das **Loeschen der Entitlement-Zeile** —
der Cloud-Adapter faellt dann auf `CLOUD_FREE_ENTITLEMENT` zurueck (gleicher
Default wie eine frische Org). Org-Scope ueber die `<ORG_ID>` aus §3:

```bash
dsb exec db psql -U supabase_admin -d postgres \
  -c "DELETE FROM org_entitlement WHERE org_id = '<ORG_ID>';"
```

Pruefen:

```bash
curl -s https://api.${DOMAIN}/v1/workspaces/<WS_ID>/billing/entitlement \
  -H "Authorization: Bearer $TOK" | python3 -m json.tool
# → mcp_monthly_quota:1000, mcp_rate_per_min:30, features:["core"]

# Gated Endpoint (Pro-Feature) ist jetzt blockiert (402):
curl -s -o /dev/null -w "%{http_code}\n" \
  https://api.${DOMAIN}/v1/workspaces/<WS_ID>/agents \
  -H "Authorization: Bearer $TOK"
# → 402
```

- [ ] `features` ist auf `["core"]` reduziert.
- [ ] Pro-gated Endpoint liefert `402 Payment Required`.

> In echtem Betrieb fuehrt der **Mollie-Webhook** (Cancel/Fehlzahlung) dasselbe
> Downgrade automatisch; das manuelle `DELETE` stellt die Wirkung fuer die
> Abnahme nach.

## 7 — RLS-Nachweis (App laeuft als `who2be_app`)

Beleg, dass die API zur Laufzeit als nicht-privilegierte Rolle mit aktiver
Row-Level-Security verbindet (nicht als Owner `supabase_admin`):

```bash
# Wer verbindet die API? -> who2be_app, NOSUPERUSER, NOBYPASSRLS
dsb exec db psql -U supabase_admin -d postgres -c \
  "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname='who2be_app';"
# → who2be_app | f | f

# RLS ist auf den App-Tabellen aktiviert (Migration 0037):
dsb exec db psql -U supabase_admin -d postgres -c \
  "SELECT relname, relrowsecurity FROM pg_class
     WHERE relname IN ('persona','playbook','organization') ORDER BY relname;"
# → relrowsecurity = t fuer alle drei
```

Funktionaler Beleg: Schritte 2–5 liefern Daten **nur** des eigenen Workspaces
(die API setzt den Tenant-Kontext pro Connection; `who2be_app` kann RLS nicht
umgehen). Ein zweiter User/Org sieht die Daten aus diesem Smoke **nicht**.

- [ ] `who2be_app`: `rolsuper=f`, `rolbypassrls=f`.
- [ ] RLS auf den App-Tabellen aktiv; Reads bleiben workspace-isoliert.

## 8 — Header-/Hardening-Check (H5)

```bash
export DOMAIN=<deine-domain>   # der Test leitet den Host-Header daraus ab
bash deploy/hetzner/tests/test_headers.sh https://api.${DOMAIN}
```

Prueft Security-Header (HSTS, XCTO, XFO, Referrer, Permissions, COOP, CSP inkl.
`object-src`/`form-action`), den `/v1/internal/*`-Block (403) und den
Docs-Toggle (`/docs` → 404 bei `WHO2BE_DOCS_PUBLIC=false`).

- [ ] „alle Header-Checks gruen ✓".

## 9 — Abnahme

| Schritt                              | Abgehakt am | Beleg |
|--------------------------------------|-------------|-------|
| 1 — Stack healthy (`cloud`)          |             |       |
| 2 — Signup + Verify (echte Inbox)    |             |       |
| 4 — Pro-Entitlement (Variante A oder B) |          |       |
| 5 — MCP-Quota 429                    |             |       |
| 6 — Downgrade-Enforcement (402)      |             |       |
| 7 — RLS aktiv (`who2be_app`)         |             |       |
| 8 — Header-Check gruen               |             |       |

Nach bestandener Abnahme einmal den **Restore-Drill (H4)** ziehen und in der
Tabelle unter [`RUNBOOK.md` §Backup & Restore](../deploy/hetzner/RUNBOOK.md#backup--restore)
protokollieren.

---

## Troubleshooting

- **`db:"unavailable"` + Logs `password authentication failed for user "who2be_app"`**
  → der One-Shot `set-app-role-password` lief nicht oder mit anderem
  `APP_DB_PASSWORD` als die API. `dcc logs set-app-role-password` pruefen; nach
  `.env`-Aenderung die Rolle neu setzen
  (`dcc run --rm set-app-role-password`) und `dcc up -d --force-recreate api`.

- **`set-app-role-password` bricht mit „role who2be_app does not exist" ab** →
  `migrate` lief nicht durch (Migration 0036). `dcc logs migrate` pruefen.

- **Keine Verify-Mail im echten Postfach** → `dsb logs auth` auf SMTP-Fehler;
  `GOTRUE_SMTP_HOST/PORT/USER/PASS/ADMIN_EMAIL` in `supabase/.env` gesetzt? Spam-
  Ordner pruefen, SPF/DKIM des Absenders. Fuer einen ersten Solo-Smoke notfalls
  `GOTRUE_MAILER_AUTOCONFIRM=true` (dann ohne Confirm) und `dsb up -d auth`.

- **Override liefert 404** → `WHO2BE_EDITION` ist nicht `cloud` (On-Prem hat den
  Pfad nicht) oder das `runtime-cloud`-Image fehlt. `dcc exec api printenv WHO2BE_EDITION`
  pruefen, ggf. mit beiden `-f`-Files neu bauen/hochfahren (README §Cloud-Edition).

- **Override liefert 403** → der Token ist kein **Admin**. Override/Checkout sind
  admin-only. Ein Admin-Token unter `/settings/tokens` erzeugen (erster Org-User
  ist Admin).

- **Checkout liefert 503** (nur Variante B) → `MOLLIE_API_KEY` fehlt/leer in
  `deploy/hetzner/.env`. Test-Key setzen und `dcc up -d api`. Oder Variante A
  (Admin-Override) nutzen — sie kommt ohne Mollie aus.

- **Keine `429` im 429-Check** → Edition pruefen (`dcc exec api printenv WHO2BE_EDITION`
  muss `cloud` sein) und dass ein **API-Token** (`w2b_…`), nicht ein Web-JWT,
  genutzt wird — nur Token-Reads unterliegen dem Gate. Die 240/min-Schranke
  braucht den Burst innerhalb derselben Minute.

- **TLS-/Cert-Fehler (`curl: SSL certificate problem`)** → DNS oder Port 80
  (ACME-Challenge) pruefen; `dcc logs caddy` zeigt die ACME-Fehler. Details:
  [`RUNBOOK.md` §Provisioning §7](../deploy/hetzner/RUNBOOK.md#provisioning-track-sc1).
</content>
</invoke>
