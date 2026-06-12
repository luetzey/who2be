# Supabase-Stack (Hetzner, MS-2 C2)

Selbst-gehostete Supabase-Komponenten fuer den Hetzner-Host. Liefert
Postgres, GoTrue (Auth) und einen nginx-Auth-Gateway als minimalen
Stack; Studio + postgres-meta sind unter dem Profil `studio`
aktivierbar.

## Reihenfolge

1. **MS-2 C1** muss durch sein (Server, Docker, Firewall, deploy-User).
2. **Diesen Stack ZUERST** starten — er erstellt das Docker-Netzwerk
   `supabase-net`, an dem der App-Stack (MS-2 C3) per `external: true`
   haengt.
3. **Anschliessend** den App-Stack
   `deploy/hetzner/who2be/docker-compose.yml` starten.

## Setup

1. `.env` anlegen:
   ```bash
   cp deploy/hetzner/supabase/.env.example deploy/hetzner/supabase/.env
   $EDITOR deploy/hetzner/supabase/.env
   ```
2. `JWT_SECRET` waehlen (mindestens 32 Zeichen!). **Identischer Wert**
   muss anschliessend in `deploy/hetzner/.env` (C3) eingetragen werden —
   sonst akzeptiert die Who2Be-API kein GoTrue-Token.
3. `ANON_KEY` und `SERVICE_ROLE_KEY` mit dem `JWT_SECRET` erzeugen. Beide sind
   HS256-JWTs, signiert mit demselben `JWT_SECRET`, nur die `role`-Claim
   unterscheidet sie (`anon` vs. `service_role`). `--ttl` ist die Lebensdauer in
   Sekunden — `315360000` = 10 Jahre, damit die Keys nicht im laufenden Betrieb
   ablaufen (es sind langlebige Projekt-Keys, keine User-Sessions):
   ```bash
   # Aus dem Repo-Root. SECRET einmal aus der .env ziehen:
   SECRET="$(grep ^JWT_SECRET deploy/hetzner/supabase/.env | cut -d= -f2-)"

   # ANON_KEY (role=anon):
   uv run python scripts/gen_test_jwt.py --secret "$SECRET" \
       --role anon --ttl 315360000

   # SERVICE_ROLE_KEY (role=service_role):
   uv run python scripts/gen_test_jwt.py --secret "$SECRET" \
       --role service_role --ttl 315360000
   ```
   Uebernahme der beiden Ausgaben (zeichengenau, je ein langes JWT):

   | Token              | In dieser `.env` (Supabase) | Zusaetzlich in `deploy/hetzner/.env` (C3) |
   |--------------------|------------------------------|--------------------------------------------|
   | `ANON_KEY`         | `ANON_KEY=…`                 | `VITE_SUPABASE_ANON_KEY=…`                 |
   | `SERVICE_ROLE_KEY` | `SERVICE_ROLE_KEY=…`         | `SUPABASE_SERVICE_KEY=…`                   |

   > **`SERVICE_ROLE_KEY` ⇒ `SUPABASE_SERVICE_KEY`:** Das Cloud-Overlay
   > (`deploy/hetzner/who2be/docker-compose.cloud.yml`, PR #181) reicht
   > `SUPABASE_SERVICE_KEY` an die API durch — sie braucht das `service_role`-JWT
   > fuer die GoTrue-Admin-Calls (Invitation-Mail, Account-Loeschung). Fehlt der
   > Wert, werden Invitation-Mails still uebersprungen (best-effort, ADR-0023) —
   > der Token bleibt zwar gueltig, aber niemand bekommt die Mail. Der Wert in
   > beiden Files MUSS identisch sein.

4. Stack starten:
   ```bash
   docker compose \
     -f deploy/hetzner/supabase/docker-compose.yml \
     --env-file deploy/hetzner/supabase/.env \
     up -d --wait
   ```
5. Health-Check:
   ```bash
   docker compose -f deploy/hetzner/supabase/docker-compose.yml exec \
     auth-gateway wget -qO- http://127.0.0.1:9999/health
   # Erwartet: ok
   ```

## Mailer (Verify- + Invitation-Mails)

Die Cloud-Reise **Signup → Verify-Mail → Invitation** haengt an echter
Mail-Zustellung. GoTrue verschickt drei Mail-Typen ueber den konfigurierten
SMTP: Signup-Confirm, Password-Recovery und Invitation-Magic-Link.

**Erst-Smoke (Solo, ohne SMTP):** Fuer einen ersten Allein-Test darf
`GOTRUE_MAILER_AUTOCONFIRM=true` **voruebergehend** gesetzt werden — Signups
sind dann sofort bestaetigt, ohne Mail-Klick. Das ist ausdruecklich nur die
Ausnahme; sobald ein zweiter User per Invitation dazukommen soll, braucht es
echte Zustellung (`GOTRUE_MAILER_AUTOCONFIRM=false` + SMTP), sonst kommt die
Magic-Link-Mail nicht an.

**Produktiv (Confirm-Pflicht, `GOTRUE_MAILER_AUTOCONFIRM=false`):** SMTP-Provider
waehlen (z. B. Postmark, Mailgun, AWS SES, Brevo) und die Sender-Domain sauber
verdrahten. Checkliste fuer `GOTRUE_SMTP_ADMIN_EMAIL=no-reply@<sender-domain>`:

- [ ] **SPF**: TXT-Record der Sender-Domain listet den Provider als erlaubten
      Absender (`v=spf1 include:<provider> ~all`).
- [ ] **DKIM**: Vom Provider ausgegebene CNAME-/TXT-Records gesetzt; Signatur
      validiert (im Provider-Dashboard „verified").
- [ ] **DMARC**: `_dmarc.<sender-domain>` TXT-Record vorhanden
      (`v=DMARC1; p=quarantine; rua=mailto:…`), mindestens `p=none` zum
      Mitschneiden.
- [ ] **SMTP-Port 587** (STARTTLS) am Hetzner-Host ausgehend offen — manche
      Provider blocken 25; 587/465 sind Standard.
- [ ] **Testmail** nach dem Hochfahren: Signup mit einer Wegwerf-Adresse, in
      einem externen Postfach (nicht nur Provider-Log) den Eingang + den
      Confirm-Link pruefen.

**Mail-Link-Ziele (`GOTRUE_MAILER_URLPATHS_*`) — gegen das Web verifiziert:**
Die Pfade im Compose decken sich mit den React-Routen in
`apps/web/src/app/routes.tsx`:

| GoTrue-URLPATH        | Compose-Wert             | Web-Route (`routes.tsx`)            |
|-----------------------|--------------------------|-------------------------------------|
| `CONFIRMATION`        | `/auth/callback`         | `/auth/callback` ✓                  |
| `EMAIL_CHANGE`        | `/auth/callback`         | `/auth/callback` ✓                  |
| `RECOVERY`            | `/onboarding/set-password` | `/onboarding/set-password` ✓      |
| `INVITE`              | `/invitations`           | (Fallback — siehe Hinweis)          |

In der Praxis liefern alle App-Flows ein explizites `redirect_to` mit, das den
statischen URLPATH **ueberschreibt**: Signup/OAuth `→ /auth/callback`, Recovery
`→ /onboarding/set-password`, und die Invitation-Mail zeigt API-seitig auf
`{WEB_BASE_URL}/invitations/{token}/accept?via=magic`
(`apps/api/.../integrations/gotrue_mailer.py`). Die echte Accept-Route ist also
`/invitations/:token/accept` (Token im Pfad) — `GOTRUE_MAILER_URLPATHS_INVITE`
bleibt nur ein harmloser Default. Wichtig ist, dass `SITE_URL` dem App-Origin
(`WEB_BASE_URL`, Default `https://app.<DOMAIN>`) entspricht, damit das
`redirect_to`-Ziel die GoTrue-Allowlist (`${SITE_URL},${SITE_URL}/*`) passiert.

## Studio (Profil `studio`)

```bash
docker compose \
  -f deploy/hetzner/supabase/docker-compose.yml \
  --profile studio \
  --env-file deploy/hetzner/supabase/.env up -d --wait
```

Studio laeuft auf Port 3000 im `supabase-net` — vom Server aus per
SSH-Tunnel erreichbar:
```bash
ssh -L 3000:127.0.0.1:3000 <user>@<host>
# danach lokal http://localhost:3000 + DASHBOARD_USERNAME/PASSWORD
```

Eine `studio.<DOMAIN>`-Caddy-Route ist bewusst nicht im Caddyfile —
Studio sollte nicht oeffentlich erreichbar sein.

## Bekannte Gotchas

- `JWT_SECRET` muss in **drei** Files identisch sein:
  `deploy/hetzner/supabase/.env`, `deploy/hetzner/.env` (C3) und
  (falls Studio aktiv) `deploy/hetzner/supabase/.env` `AUTH_JWT_SECRET`
  (wird aus derselben Variable gelesen — kein doppelter Eintrag noetig).
- `supabase/postgres` initialisiert das DB-Volume nur beim **ersten**
  Start. Wenn das Volume schon existiert, werden die `init/`-Scripts
  nicht erneut ausgefuehrt — Aenderungen an `init/*.sql` greifen erst
  bei `down -v`.
- `GOTRUE_MAILER_AUTOCONFIRM` ist im Compose default `false` (Confirm-Pflicht,
  Cloud-Paritaet). Fuer einen ersten Solo-Smoke OHNE SMTP darf der Wert in der
  `.env` voruebergehend auf `true` (siehe Abschnitt „Mailer"); produktiv bleibt
  er `false` + echter SMTP-Provider.
- Ohne gesetzten `SERVICE_ROLE_KEY` (bzw. `SUPABASE_SERVICE_KEY` in `../.env`)
  werden Invitation-Mails still uebersprungen — der Klartext-Token im 201-Body
  bleibt der einzige Weg, jemanden einzuladen.

## Verweis

- App-Stack: `../who2be/docker-compose.yml` (MS-2 C3).
- Backup/Restore: `../RUNBOOK.md` (kommt mit MS-2 C5).
- CI/CD: `.github/workflows/deploy.yml` (kommt mit MS-2 C4).
