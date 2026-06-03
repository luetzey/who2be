# Cloud-Edition LOKAL — Smoke der bezahlten Reise

End-to-End-Smoke der **Cloud-Edition** auf dem privaten PC, mit voller
Prod-Paritaet (Plan §3.1 / CL1): Mailpit faengt die Verify-Mail, Redis ist
Rate-Limit-Backend, die API verbindet als nicht-privilegierte Rolle
`who2be_app` (**RLS aktiv**), `WHO2BE_EDITION=cloud`, Mollie im **Test-Modus**.

Reise: **Signup → Verify-Mail (Mailpit) → Login → Upgrade (Mollie-Test) →
Pro-Entitlement → MCP-Quota bis 429 → RLS-Nachweis**.

> **Wer haakt ab?** Du (User). Alle Browser-Schritte (Mailpit-UI, Web-Login,
> Mollie-Test-Checkout) laufen auf **deiner Workstation** — der Sandbox-
> Container kann den Browser-Happy-Path nicht selbst fahren. Plan-Pointer:
> `.claude/plan/2026-06-03-2030_cloud-launch-readiness.md` (Track M).
>
> Abgrenzung zu `docs/local-smoke.md`: das ist der **dev**-Stack (onprem,
> autoconfirm, kein Billing). Diese Datei fuegt die Cloud-Schalter dazu.

---

## 0 — Voraussetzungen

- `docker` + `docker compose` (Docker Desktop oder Engine).
- Browser fuer Web-UI, Mailpit-UI und den Mollie-Test-Checkout.
- **Mollie-Test-Key** (`test_…`) aus dem Mollie-Dashboard
  (Developers → API keys) — fuer den Upgrade-Schritt.
- Optional fuer einen echten Webhook-Pull: ein Tunnel auf die API
  (`ngrok http 8000` oder `cloudflared tunnel --url http://localhost:8000`).
- `curl` + `uv` auf dem Host (fuer die MCP-/429-Checks).

## 1 — `.env` vorbereiten

```bash
cp .env.example .env
```

Im `.env` die cloud-local-Sektion entkommentieren/setzen (siehe
`=== Cloud-Edition LOKAL ===` in `.env.example`):

```dotenv
APP_DB_PASSWORD=who2be_app_local_pw          # frei waehlbar (lokal)
MOLLIE_API_KEY=test_xxxxxxxxxxxxxxxxxxxxxxxx  # dein Mollie-Test-Key
# Nur wenn du den Webhook-Pull live testen willst (sonst leer lassen):
# MOLLIE_WEBHOOK_URL=https://<tunnel-host>/v1/billing/mollie/webhook
```

`JWT_SECRET` / `VITE_*` bleiben auf den Defaults (passen zum Compose-Stack).

## 2 — Cloud-Stack starten (Overlay)

**Immer beide Compose-Files**, sonst laeuft der dev-Stack (onprem):

```bash
docker compose -f docker-compose.yml -f docker-compose.cloud.yml \
  up -d --build --wait --wait-timeout 240
```

Reihenfolge: `db` → `migrate` (alle SQL-Migrationen, inkl. `0036` Rolle
`who2be_app`) → `set-app-role-password` (One-Shot: setzt das Rollen-Passwort)
→ `auth` (GoTrue, SMTP→mailpit) + `redis` + `mailpit` → `api`
(`WHO2BE_EDITION=cloud`, verbindet als `who2be_app`) → `auth-gateway` + `web`.

Sanity-Check, dass die Cloud-Schalter greifen:

```bash
docker compose -f docker-compose.yml -f docker-compose.cloud.yml \
  exec api printenv WHO2BE_EDITION APP_DATABASE_URL RATE_LIMIT_STORAGE_URI
# → cloud / postgresql://who2be_app:***@db:5432/who2be / redis://redis:6379
```

> Tipp: Der lange `-f … -f …`-Aufruf laesst sich per Alias buendeln, z. B.
> `alias dcc='docker compose -f docker-compose.yml -f docker-compose.cloud.yml'`.
> Im Folgenden steht `dcc` fuer genau diesen Doppel-`-f`-Aufruf.

## 3 — Signup → Verify-Mail (Mailpit) → Login

Im Cloud-Overlay ist `GOTRUE_MAILER_AUTOCONFIRM=false` — Signups muessen die
E-Mail **bestaetigen** (echte Cloud-Reise). Die Mail landet in Mailpit.

1. **Signup** im Browser auf <http://localhost:5173/signup> (E-Mail +
   Passwort, ≥ 6 Zeichen). Alternativ per API:

   ```bash
   curl -s -X POST http://localhost:9999/auth/v1/signup \
     -H "apikey: dev-anon-key-not-used-by-gotrue" \
     -H "Content-Type: application/json" \
     -d '{"email":"pro@who2be.local","password":"streng-geheim"}'
   ```

2. **Verify-Mail oeffnen:** Mailpit-UI auf <http://localhost:8025>. Die
   „Confirm your signup"-Mail anklicken → **Confirm**-Link folgen. Der Link
   zeigt auf `http://localhost:5173/auth/callback#access_token=…`
   (`GOTRUE_MAILER_URLPATHS_CONFIRMATION=/auth/callback`).

   - [ ] Klick landet auf der Web-`/auth/callback`-Route und ist eingeloggt.

3. **Login** (falls die Session nicht direkt steht): <http://localhost:5173/login>
   mit denselben Credentials → Redirect auf das Default-Workspace-Dashboard.

> Ohne Confirm bleibt der User **un-bestaetigt** und der Login schlaegt fehl —
> genau das verifiziert, dass die Mail-Pflicht lokal greift.

## 4 — Upgrade: Mollie-Test-Checkout → Pro-Entitlement

Frisch registrierte Cloud-Orgs starten auf **Free** (`mcp_monthly_quota=1000`,
`mcp_rate_per_min=30`). Upgrade auf **Pro** (`100_000` / `240`,
Features Composite/Agents/Audit-Export).

1. **Entitlement vorher** lesen (Free-Defaults bestaetigen). Token aus
   `/settings/tokens` in der Web-UI erstellen (`w2b_…`), dann:

   ```bash
   export TOK=w2b_<dein-token>
   curl -s http://localhost:8000/v1/workspaces/<ws-id>/billing/entitlement \
     -H "Authorization: Bearer $TOK" | python3 -m json.tool
   # → "status":"active", mcp_monthly_quota:1000, mcp_rate_per_min:30
   ```

2. **Checkout starten** (admin-only) — in der Web-UI unter
   `/settings/billing` „Upgrade auf Pro", oder per API:

   ```bash
   curl -s -X POST http://localhost:8000/v1/workspaces/<ws-id>/billing/checkout \
     -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
     -d '{"plan":"pro"}'
   # → {"checkout_url":"https://www.mollie.com/checkout/test-mode/..."}
   ```

3. **Test-Zahlung** im Browser: die `checkout_url` oeffnen → Mollie-Test-Modus
   → Status **„paid"** waehlen → Redirect zurueck auf `/settings/billing`.

4. **Webhook → Entitlement-Upsert.** Mollie ruft `POST …/billing/mollie/webhook`
   mit der Payment-`id`; die API **pullt** das Objekt aktiv und hebt das
   Entitlement auf Pro.

   - **Mit Tunnel** (`MOLLIE_WEBHOOK_URL` gesetzt): passiert automatisch.
   - **Ohne Tunnel** (localhost ist fuer Mollie nicht erreichbar): den Ping
     manuell nachstellen, sobald die Test-Zahlung „paid" ist —

     ```bash
     curl -s -X POST http://localhost:8000/v1/billing/mollie/webhook \
       -H "Content-Type: application/x-www-form-urlencoded" \
       -d "id=<payment-id-aus-checkout-url>"
     ```

5. **Entitlement nachher** erneut lesen:

   ```bash
   curl -s http://localhost:8000/v1/workspaces/<ws-id>/billing/entitlement \
     -H "Authorization: Bearer $TOK" | python3 -m json.tool
   # → mcp_monthly_quota:100000, mcp_rate_per_min:240,
   #   features enthaelt composite_playbooks/agents/audit_export
   ```

   - [ ] Quota + Features sind auf Pro angehoben.

## 5 — MCP-Quota bis 429

Das MCP-Limit-Gate greift **nur** in der Cloud-Edition und **nur** fuer
API-Token-Aufrufer (der MCP-Server) — Web-/JWT-Reads passieren ungehindert.
Zwei Schranken: **Per-Token-Rate/min** (schnell zu treffen) und das
**Monats-Kontingent** (beide → **429**); ein `inactive` Entitlement → 402.

Am schnellsten ueber die **Per-Minute-Rate** sichtbar. Auf **Free** (30/min)
ein MCP-Read im Loop hammern:

```bash
export WHO2BE_API_BASE_URL=http://localhost:8000
export WHO2BE_API_TOKEN=w2b_<dein-token>
for i in $(seq 1 40); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    http://localhost:8000/v1/workspaces/<ws-id>/personas \
    -H "Authorization: Bearer $WHO2BE_API_TOKEN"
done | sort | uniq -c
# → erst 200er, ab Ueberschreiten des Token-Rate-Ceilings 429er
```

- [ ] Es erscheinen `429`-Antworten (`detail":"Token-Ratenlimit ueberschritten."`).
- [ ] Optional Monats-Kontingent: auf Free 1000 Reads/Monat — danach
      `detail":"Monatliches MCP-Kontingent erschoepft."` (ebenfalls 429).

> Der echte MCP-Pfad laeuft identisch — `uv run python -m who2be_mcp.server`
> mit denselben Env-Vars, Tools `get_persona` / `list_playbooks` /
> `fetch_playbook` (siehe `docs/local-smoke.md` §4). Das Gate sitzt
> server-seitig in der API, nicht im MCP-Prozess.

## 6 — RLS-Nachweis (App laeuft als `who2be_app`)

Beleg, dass die API zur Laufzeit als nicht-privilegierte Rolle mit aktiver
Row-Level-Security verbindet (nicht als Owner `postgres`):

```bash
# Wer verbindet die API? -> who2be_app, NOSUPERUSER, NOBYPASSRLS
docker compose -f docker-compose.yml -f docker-compose.cloud.yml \
  exec db psql -U postgres -d who2be -c \
  "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname='who2be_app';"
# → who2be_app | f | f

# RLS ist auf den App-Tabellen aktiviert (Migration 0037):
docker compose -f docker-compose.yml -f docker-compose.cloud.yml \
  exec db psql -U postgres -d who2be -c \
  "SELECT relname, relrowsecurity FROM pg_class
     WHERE relname IN ('persona','playbook','organization') ORDER BY relname;"
# → relrowsecurity = t fuer alle drei
```

Funktionaler Beleg: Schritt 3–5 liefern Daten **nur** des eigenen Workspaces
(die API setzt den Tenant-Kontext pro Connection; `who2be_app` kann RLS nicht
umgehen). Ein zweiter User/Org sieht die Personas aus Schritt 4 **nicht**.

- [ ] `who2be_app`: `rolsuper=f`, `rolbypassrls=f`.
- [ ] RLS auf den App-Tabellen aktiv; Reads bleiben workspace-isoliert.

## 7 — Abnahme

| Schritt                          | Abgehakt am | Beleg |
|----------------------------------|-------------|-------|
| 2 — Cloud-Stack healthy          |             |       |
| 3 — Signup + Verify (Mailpit)    |             |       |
| 4 — Upgrade → Pro-Entitlement    |             |       |
| 5 — MCP-Quota 429                 |             |       |
| 6 — RLS aktiv (`who2be_app`)     |             |       |

## 8 — Teardown

```bash
docker compose -f docker-compose.yml -f docker-compose.cloud.yml down -v
```

`-v` loescht das Postgres-Volume (frischer Start; das `who2be_app`-Passwort
wird beim naechsten Hochfahren erneut gesetzt).

---

## Troubleshooting

- **API startet nicht / `db:"unavailable"` und Logs zeigen
  `password authentication failed for user "who2be_app"`** → der One-Shot
  `set-app-role-password` lief nicht oder mit anderem `APP_DB_PASSWORD` als die
  API. Beide lesen `${APP_DB_PASSWORD}` aus `.env`; nach einer Aenderung
  `down -v` und neu hochfahren (sonst haelt das alte Passwort im Volume).
  `dcc logs set-app-role-password` zeigt „Passwort gesetzt".

- **`set-app-role-password` bricht mit „role who2be_app does not exist" ab** →
  `migrate` lief nicht durch (Migration 0036). `dcc logs migrate` pruefen.

- **Keine Mail in Mailpit** → `dcc logs auth` auf SMTP-Fehler pruefen;
  `GOTRUE_SMTP_HOST=mailpit`/`PORT=1025` muessen gesetzt sein (nur im Overlay).
  Sicherstellen, dass **beide** `-f`-Files mitgestartet wurden.

- **Login schlaegt trotz Signup fehl** → User ist noch un-bestaetigt: in
  Mailpit den Confirm-Link klicken. (Im dev-Stack waere autoconfirm an — hier
  bewusst nicht.)

- **Checkout liefert 503** → `MOLLIE_API_KEY` fehlt/leer. Test-Key in `.env`
  setzen und `dcc up -d api` neu ausrollen.

- **Mollie ruft den Webhook nicht** → localhost ist fuer Mollie nicht
  erreichbar. Entweder Tunnel + `MOLLIE_WEBHOOK_URL` setzen, oder den Webhook-
  Ping nach „paid" manuell nachstellen (Schritt 4.4).

- **Keine `429` im 429-Check** → Edition pruefen (`dcc exec api printenv
  WHO2BE_EDITION` muss `cloud` sein) und dass ein **API-Token** (`w2b_…`),
  nicht ein Web-JWT, genutzt wird — nur Token-Reads unterliegen dem Gate.

- **Browser-Schritte:** Mailpit-UI, Web-Login und der Mollie-Test-Checkout
  laufen auf deiner **Workstation** (nicht im Sandbox-Container). Ports 5173 /
  8025 / 8000 / 9999 muessen vom Host erreichbar sein (Compose mappt sie).
