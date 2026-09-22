# Cloud-Hosting bei Hetzner — Owner-Leitfaden (1.000 Nutzer)

> ⚠️ **Kein Rechtsrat.** Die Compliance-Abschnitte sagen, *welche* Artefakte
> und Schalter vorhanden bzw. offen sind. Die inhaltliche Fassung von
> Impressum, AGB, Datenschutzerklärung und AVV gehört zum Betreiber bzw. zur
> anwaltlichen Prüfung.
>
> Stand: 2026-09-19. Quellen sind im Repo belegt (`datei:zeile`); wo eine
> Aussage nur ein Live-Lauf beweisen kann, steht das dabei.
>
> **Charakter:** Analyse- und Vorschlagspapier, Stand 2026-09-19 — Teile davon
> sind Empfehlungen, nicht der aktuelle Zustand (z. B. der vorgeschlagene
> Team-Tarif für 99 €, den es nicht gibt). Verbindlich für Tarife und Limits
> sind `docs/licensing/plans.md` und der Code. Einzelne hier beschriebene
> Lücken sind inzwischen geschlossen und unten entsprechend markiert.

Dieses Dokument beantwortet vier Fragen an einem Stück: **Brauche ich einen
Server? Wie schütze ich die App gegen Last-Missbrauch? Wie kassiere ich
monatlich? Wie speichere ich Nutzer-Prompts rechtssicher und krisenfest?**
Es ersetzt nicht das [RUNBOOK](../deploy/hetzner/RUNBOOK.md) (operative
Kommandos) und nicht das
[Launch-Readiness-Inventar](../.claude/plan/2026-09-05-1520_cloud-launch-readiness-inventar.md)
(Stations-Inventar) — es ordnet beides in eine Reihenfolge und ergänzt die
Punkte, die in keinem der beiden stehen.

---

## 0 · Kurzantwort

**Ja, du brauchst einen Server.** Who2Be ist ein Docker-Compose-Stack aus
neun Diensten (API, Web, Caddy, Redis, SeaweedFS, MCP-HTTP, Backup + der
separate Supabase-Stack mit Postgres und GoTrue). Es gibt keinen
Serverless-/Managed-Pfad im Repo. Eine **Hetzner-Cloud-VM** genügt für die
ersten 1.000 Nutzer — ein dedizierter Root-Server lohnt erst später.

**Der Code ist für die Cloud-Edition weitgehend fertig.** Was fehlt, sind
(a) Owner-Schritte, die kein Agent tun kann (Keys, DNS, Repo-Variablen,
Rechtstexte, Testkauf) und (b) **fünf inhaltliche Lücken**, die vor dem
ersten zahlenden Kunden geschlossen sein sollten — sie stehen in
[§4](#4--missbrauchsschutz-die-fünf-offenen-lücken) und
[§5](#5--bezahlung-was-fehlt-für-echtes-geld).

**Die teuerste Lücke ist nicht die Request-Zahl, sondern der Speicher.**
Requests sind gedeckelt (`mcp_monthly_quota`, pro Org atomar gezählt).
Hochgeladene Dateien sind es **nicht**: es gibt im ganzen Repo keine
Speicher-Quota. Ein Pro-Kunde für 29 €/Monat darf heute unbegrenzt viele
20-MiB-Dateien ablegen. Das ist der einzige Posten, bei dem ein einzelner
Kunde dich real Geld kosten kann.

---

## 1 · Ist-Stand: was steht, was fehlt

### Steht (im Code belegt)

| Baustein | Beleg |
|---|---|
| Editions-Schalter On-Prem/Cloud | `apps/api/src/who2be_api/core/config.py:109` |
| Mollie-Checkout + Webhook (Pull-after-Ping) | `packages/billing/src/who2be_billing/mollie.py:320` |
| Entitlement als einzige gelesene SSoT | `apps/api/src/who2be_api/repositories/entitlement_repository.py:61` |
| MCP-Limit: Rate/min + Monats-Kontingent | `apps/api/src/who2be_api/services/mcp_limit_service.py:75` |
| Entity-Limit Free (50 Aggregate), 402 statt Sperre | `apps/api/src/who2be_api/services/entity_quota_service.py:86` |
| RLS in der Cloud-Edition (Rolle `who2be_app`) | `deploy/hetzner/who2be/docker-compose.cloud.yml` |
| Redis als geteilter Rate-Limit-Storage | `apps/api/src/who2be_api/core/rate_limit.py` |
| Caddy: TLS, Security-Header, 32-MB-Body-Cap, `/v1/internal/*` geblockt | `deploy/hetzner/Caddyfile` |
| Backup: GPG-pg_dump + restic-Offsite | `deploy/hetzner/scripts/backup.sh` |
| Lösch-Lebenszyklus Soft-Delete → 30 Tage → Hard-Purge | `docs/compliance/data-retention-and-erasure.md` |
| DSGVO-Datenexport (Art. 20) | `apps/api/src/who2be_api/routers/gdpr.py:32` |
| Coming-Soon-Modus (Registrierung zu, Login offen) | `apps/web/src/features/auth/pages/SignupPage.tsx:74` |
| CI baut + pusht `who2be-api-cloud` nach GHCR | `.github/workflows/deploy.yml` |

### Fehlt — Owner-Schritte (kann nur der Owner)

1. Hetzner-Box bestellen, DNS setzen, At-Rest-Verschlüsselung wählen.
2. Repo-Variablen `DEPLOY_HOST` / `DEPLOY_USER` / `DEPLOY_PROJECT_DIR` und
   das Secret `DEPLOY_SSH_KEY` setzen. **Solange `DEPLOY_HOST` fehlt,
   überspringt sich der Deploy-Job still** (`.github/workflows/deploy.yml:83`)
   — die Pipeline war nie rot, aber auch nie verifiziert.
3. Alle `CHANGE_ME` in `deploy/hetzner/.env` und
   `deploy/hetzner/supabase/.env` ersetzen.
4. `WHO2BE_BILLING_OVERRIDE_OPERATORS` mit der eigenen User-UUID füllen —
   sonst ist der Kulanz-/Support-Pfad bewusst fail-closed unbenutzbar.
5. Mollie-Konto + Live-Key, echter SMTP-Provider.
6. Rechtstexte füllen (`docs/compliance/legal-texts-checklist.md`).
7. **Restore-Drill einmal fahren und protokollieren** — die Protokolltabelle
   im RUNBOOK ist leer.

### Fehlt — Code (die fünf Lücken)

Siehe [§4](#4--missbrauchsschutz-die-fünf-offenen-lücken) und
[§5](#5--bezahlung-was-fehlt-für-echtes-geld). Kurz: Speicher-Quota,
Token-Anzahl-Cap, Signup-Captcha, Rechnung — plus das Org-weite
Rate-Ceiling, das als L2 beschrieben, inzwischen aber geschlossen ist
(#537, PR #555). Es bleiben also die fünf Lücken der Analyse, von denen
eine erledigt ist.

---

## 2 · Schritt-für-Schritt: von null auf produktiv

Die Kommandos stehen ausführlich im
[RUNBOOK §Provisioning](../deploy/hetzner/RUNBOOK.md#provisioning-track-sc1).
Hier die Reihenfolge mit den Entscheidungen, die *dabei* fallen.

### Schritt 1 — Box bestellen

- **Typ:** Hetzner Cloud, **CCX23** (4 dedizierte vCPU, 16 GB RAM, 160 GB
  NVMe) als Startpunkt für 1.000 Nutzer. CPX41 ist billiger, teilt sich die
  CPU aber mit Nachbarn — bei einer Datenbank merkt man das. Preise vor der
  Bestellung in der Hetzner-Konsole gegenprüfen, sie ändern sich.
- **Region: `nbg1` oder `fsn1` (Deutschland).** Das ist keine Technikfrage,
  sondern die Antwort auf „wo liegen meine Daten" in der
  Datenschutzerklärung. Die Wahl gehört in die Protokolltabelle im
  [RUNBOOK §Standort](../deploy/hetzner/RUNBOOK.md#standort--auftragsverarbeiter).
- **OS:** Ubuntu 24.04 LTS, SSH-Public-Key beim Anlegen hinterlegen, **kein**
  Passwort-Login.
- **Zusätzliches Volume** (z. B. 100 GB) für die Daten — getrennt vom
  System-Volume, weil es wachsen soll und weil die Verschlüsselung daran
  hängt.
- **AVV mit Hetzner abschließen** — in der Hetzner-Konsole unter den
  Vertragsdokumenten. Ohne den ist der Rest der Datenschutzerklärung
  wertlos.

### Schritt 2 — At-Rest-Verschlüsselung (VOR dem ersten `docker compose up`)

Zwei Varianten, beide im
[RUNBOOK §Verschlüsselung at-Rest](../deploy/hetzner/RUNBOOK.md#verschluesselung-at-rest-postgres-volume):

- **Variante A:** verschlüsseltes Hetzner-Cloud-Volume (Plattform-LUKS).
  Einfach, der Nachweis ist eine Eigenschaft in der Hetzner-Konsole.
- **Variante B:** selbst verwaltetes LUKS auf dem Host. Mehr Kontrolle,
  aber: **Der Passphrase-Prompt beim Boot bedeutet, dass ein Neustart
  manuelle Arbeit ist.** Wer nachts nicht aufstehen will, nimmt A oder legt
  sich ein Key-File plus dokumentiertes Risiko zurecht.

Nachträglich lässt sich das nur mit Downtime und Datenumzug nachholen —
deshalb jetzt.

### Schritt 3 — Grund-Hardening

`deploy`-User anlegen, Docker + Compose v2 installieren, Firewall auf
22/80/443 (RUNBOOK Schritte 2–4). Zusätzlich empfohlen, weil im RUNBOOK
nicht enthalten:

```bash
# SSH: nur Key-Login, kein root
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/;s/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl reload ssh
# Automatische Sicherheitsupdates
sudo apt-get install -y unattended-upgrades fail2ban
```

**Zusätzlich die Hetzner-Cloud-Firewall** (nicht nur UFW auf dem Host)
aktivieren: sie filtert, bevor Pakete die VM erreichen, und überlebt einen
Konfigurationsfehler im Host.

### Schritt 4 — DNS

Vier A-Records auf die Box-IP: `app`, `api`, `supabase`, `mcp`. Alle vier
werden gebraucht — der OAuth-Remote-MCP-Connector (ADR-0036) funktioniert
nur, wenn alle drei beteiligten Hostnamen erreichbar sind.

### Schritt 5 — Secrets und `.env`

```bash
cp deploy/hetzner/.env.example          deploy/hetzner/.env
cp deploy/hetzner/supabase/.env.example deploy/hetzner/supabase/.env
```

Fallstricke, die jeweils eine Stunde Fehlersuche kosten:

- `JWT_SECRET` muss in **beiden** Dateien **identisch** sein.
- `ANON_KEY` muss mit **genau diesem** Secret signiert sein
  (`scripts/gen_test_jwt.py --role anon`).
- `GOTRUE_MAILER_AUTOCONFIRM=false` + echter SMTP — sonst kann sich jeder
  mit einer erfundenen Adresse registrieren.
- `WHO2BE_DOCS_PUBLIC` bleibt aus (Default). Caddy hat keinen Auth-Layer vor
  `/docs`.

### Schritt 6 — Stacks hochfahren (Reihenfolge zählt)

```bash
# 1) Supabase zuerst — erzeugt das Netzwerk supabase-net
docker compose -f deploy/hetzner/supabase/docker-compose.yml \
  --env-file deploy/hetzner/supabase/.env up -d --wait

# 2) App-Stack, Cloud-Edition: IMMER beide -f-Files
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  -f deploy/hetzner/who2be/docker-compose.cloud.yml \
  --env-file deploy/hetzner/.env build web
docker compose \
  -f deploy/hetzner/who2be/docker-compose.yml \
  -f deploy/hetzner/who2be/docker-compose.cloud.yml \
  --env-file deploy/hetzner/.env --profile mcp-http up -d --wait
```

> **Eine Box, eine Edition.** Ein Wechsel zwischen On-Prem und Cloud auf
> demselben Volume ist ein Laufzeit-Wechsel, kein Daten-Reset — aber
> RLS-Rolle und Billing-Routen ändern sich darunter. Nicht hin- und
> herschalten.

Prüfen, dass die Schalter wirklich greifen:

```bash
docker compose ... exec api printenv WHO2BE_EDITION APP_DATABASE_URL RATE_LIMIT_STORAGE_URI
# → cloud / postgresql://who2be_app:***@db:5432/postgres / redis://redis:6379
```

`who2be_app` statt `supabase_admin` ist der Beweis, dass **RLS aktiv** ist.
Steht dort die Owner-Rolle, läuft die Mandantentrennung nur auf
Anwendungsebene — die zweite Verteidigungslinie fehlt dann.

### Schritt 7 — Abnahme

```bash
bash scripts/smoke.sh                       # 6 Checks
bash deploy/hetzner/tests/test_headers.sh   # Security-Header gegen alle Subdomains
```

Dann die Reise aus [`docs/cloud-prod-smoke.md`](cloud-prod-smoke.md) von
Hand: Signup → echte Inbox → Login → Pro-Entitlement → MCP-Quota bis 429 →
Downgrade auf 402 → RLS-Nachweis. **Diese Reise ist der eigentliche
Launch-Beweis** — alles davor beweist nur, dass Container laufen.

### Schritt 8 — Coming-Soon-Modus, dann CI/CD

Bis alles steht: `WHO2BE_LAUNCH_MODE=coming_soon` (Registrierung zu, Login
für dich offen). Danach Repo-Variablen setzen (`DEPLOY_HOST` etc.), einmal
`deploy.yml` real laufen lassen und das RUNBOOK gegen die Realität
abgleichen.

### Schritt 9 — Backup scharf schalten und einmal restoren

Siehe [§7](#7--backup-und-serverausfall). **Ein Backup, das nie
zurückgespielt wurde, ist kein Backup.**

---

## 3 · Limits: die Diskussion

### Heutiger Stand

| Tier | Preis | MCP-Req/Monat | Req/Minute | Entities/Workspace | Speicher | Seats |
|---|---|---|---|---|---|---|
| Free | 0 € | 1.000 | 30 | 50 | **unbegrenzt** | **unbegrenzt** |
| Pro | 29 €/Mon | 100.000 | 240 | **unbegrenzt** | **unbegrenzt** | **unbegrenzt** |

Quelle: `docs/licensing/plans.md`, `packages/billing/src/who2be_billing/plans.py:69`.

### Was daran nicht passt

**1. „Unbegrenzt" steht dreimal in der Tabelle, und jedes Mal an einer
Stelle, wo es Geld kostet.** Requests sind gedeckelt und werden atomar pro
Org gezählt (`mcp_limit_service.py:117`). Speicher, Sitze und Entities im
Pro-Tarif sind es nicht. Ein einziger Kunde mit einem Ingest-Skript kann für
29 €/Monat dein Volume füllen — das Ingest-Limit von 20 MiB gilt **pro
Datei** (`config.py:159`), nicht in Summe.

**2. Das Minutenlimit hängt am Token, nicht an der Org.** `rate_limit_key()`
ist der SHA-256 des Bearer-Tokens (`core/rate_limit.py:46`). Wer zwanzig
Agent-Tokens anlegt, hat zwanzigmal 240 req/min. Das Monats-Kontingent
fängt den Gesamtverbrauch ab, aber **nicht die Spitze**: 4.800 req/min gegen
die Datenbank reichen, um allen anderen Kunden die Antwortzeit zu ruinieren,
bis das Kontingent leer ist. Es gibt keinen Cap auf die Anzahl der Tokens.

*Nachtrag: seit #537 (PR #555) deckelt `mcp_rate_per_min` zwei
Sliding-Windows mit demselben Ceiling — pro Token und pro Org; effektiv gilt
das Minimum. Die hier beschriebene Token-Multiplikation existiert nicht mehr.*

**3. Das Request-Limit gilt nur für API-Tokens.** `enforce()` steigt bei
Web-Sessions früh aus (`mcp_limit_service.py:79`) — bewusst so entschieden
(2026-09-05: „die Agenten-Last ist die Kostenquelle, die UI ist
Verwaltung"). Die Entscheidung ist nachvollziehbar, hat aber eine Kante: ein
Skript mit einem GoTrue-JWT liest **ungedrosselt**. Für Schreibzugriffe
greift `rate_limit_write` (30/min), für Lesezugriffe nichts.

**4. Sitze werden nicht bepreist.** RBAC und Einladungen existieren
(ADR-0023). Eine 30-köpfige Firma zahlt heute 29 € — genauso viel wie eine
Einzelperson. Das ist bei B2B-SaaS die teuerste unbeabsichtigte Preisstufe.

### Vorschlag

Drei Tarife statt zwei, und jedes „unbegrenzt" durch eine Zahl ersetzt, die
hoch genug ist, dass ehrliche Nutzer sie nie sehen:

| | **Free** | **Pro** 29 €/Mon | **Team** 99 €/Mon |
|---|---|---|---|
| MCP-Req/Monat (Org) | 1.000 | 100.000 | 500.000 |
| Req/Minute **pro Org** | 60 | 300 | 900 |
| Req/Minute pro Token | 30 | 240 | 240 |
| Entities je Workspace | 50 | 2.000 | 10.000 |
| **Speicher (Blobs+Tabellen)** | **100 MB** | **10 GB** | **100 GB** |
| Agent-Tokens | 3 | 25 | 100 |
| Sitze (Mitglieder/Org) | 1 | 5 | 25 |
| Workspaces | 1 | 5 | unbegrenzt |

**Die Begründungen, kurz:**

- **Req/Minute pro Org** ist die wichtigste Ergänzung. Sie schließt die
  Token-Multiplikation, ohne dem Kunden das Anlegen mehrerer Agenten zu
  verbieten. Das Per-Token-Limit bleibt daneben bestehen — es schützt vor
  *einem* durchgedrehten Agenten, das Org-Limit vor *einem Kunden*.
- **Speicher-Quota ist die einzige echte Kostenbremse.** 10 GB entsprechen
  bei Hetzner Cent-Beträgen; die Zahl ist nicht knapp, sie ist nur endlich.
  Ohne sie ist dein Deckungsbeitrag pro Kunde unbestimmt.
- **2.000 statt unbegrenzt bei Entities** kostet dich keinen echten Kunden
  und hält den Free→Pro-Sprung trotzdem groß (40×).
- **Sitze** sind der Hebel, mit dem aus 29 € irgendwann 99 € werden. Ohne
  Sitz-Grenze im Pro-Tarif gibt es keinen Grund, je auf Team zu wechseln.
- **Was du *nicht* limitieren solltest:** Versionen pro Element und
  Lesezugriffe im Web-UI. Beides ist billig und beides ist der Grund, warum
  jemand das Produkt überhaupt mag.

**Harte Obergrenzen unabhängig vom Tarif** (Missbrauchsschutz, nicht
Verkauf): 20 MiB pro Datei (existiert), SQL-Zeit- und Größenbudgets
(existieren, ADR-0049), 32 MB Request-Body an Caddy (existiert), dazu neu:
Ingest-Vorgänge pro Tag und Org.

### Zwei Entscheidungen, die du treffen musst

1. **Pro pro Workspace oder pro Organisation?** Heute hängt das Entitlement
   an der **Org** (`org_entitlement`), das Entity-Limit zählt aber **pro
   Workspace** (`entity_quota_service.py:16`). Für den Free-Tarif
   (eine Org = ein Workspace) ist das deckungsgleich, für Pro nicht. Wenn du
   Workspaces limitierst (Vorschlag oben), bleibt es sauber — sonst wird
   „unbegrenzt viele Workspaces à 2.000 Entities" zur Hintertür.
2. **Wie viel Speicher ist im Preis?** Das ist der einzige Posten, bei dem
   ein Kunde dich Geld kosten kann. Meine Empfehlung: großzügig ansetzen
   (10 GB) und Überschreitung nicht sperren, sondern nur neue Uploads
   blocken — genau wie das Entity-Limit heute (402, Bestand bleibt lesbar).

---

## 4 · Missbrauchsschutz: die fünf offenen Lücken

Nach Priorität. Jede ist im Repo belegt, keine ist heute katastrophal —
aber alle fünf werden es mit echten Nutzern. **Hinweis:** L2 ist seit
Erstellung dieser Analyse geschlossen (#537, PR #555); die Überschrift
bleibt aus Anker-Gründen unverändert.

### L1 — Keine Speicher-Quota (Kostenrisiko)

Repo-weiter Grep nach `storage_quota`/`storage_limit`/`max_storage`: null
Treffer. Ingest begrenzt nur die Einzeldatei auf 20 MiB
(`config.py:159`). **Nötig:** Summe der `wa_blob`-Bytes je Org gegen ein
Entitlement-Feld, 402 beim Überschreiten, Anzeige im BillingPanel.

### L2 — Kein Org-weites Rate-Ceiling (Verfügbarkeitsrisiko)

**Status: geschlossen durch #537 (PR #555).** Der beschriebene zweite
Limiter-Aufruf existiert; `mcp_rate_per_min` gilt pro Token *und* pro Org.
Der folgende Text beschreibt den damaligen Zustand.

Siehe §3. **Nötig:** ein zweiter Limiter-Aufruf in
`mcp_limit_service.enforce()` mit `org_id` als Key, zusätzlich zum
Token-Key. Redis ist bereits als geteiltes Backend verdrahtet
(`RedisTokenRateLimiter`), die Mechanik existiert also — es fehlt der
zweite Schlüssel.

### L3 — Keine Obergrenze für Agent-Tokens

`POST /v1/tokens` ist nur durch `write_limit` (30/min) gebremst. 30 Tokens
pro Minute, unbegrenzt lange. **Nötig:** Cap pro Workspace aus dem
Entitlement.

### L4 — Kein Captcha bei der Registrierung

GoTrue bringt hCaptcha/Turnstile mit (`GOTRUE_SECURITY_CAPTCHA_*`), in
`deploy/hetzner/supabase/.env.example` ist davon nichts gesetzt. Mit
Confirm-Pflicht (`GOTRUE_MAILER_AUTOCONFIRM=false`) ist Massen-Signup
unattraktiv, aber jeder Versuch kostet dich eine SMTP-Zustellung und kann
deine Absender-Reputation beschädigen. **Nötig:** Turnstile aktivieren —
reine Konfiguration, kein Code.

### L5 — Kein Rate-Limit an der Kante

Caddy begrenzt den Body (32 MB), nicht die Rate. Alles, was drosselt, läuft
**in** der Anwendung — also erst, nachdem Starlette, die DB-Session und die
Entitlement-Auflösung schon Arbeit geleistet haben. **Nötig:** entweder das
`caddy-ratelimit`-Modul einbauen (braucht einen eigenen `xcaddy`-Build) oder
ein grobes Per-IP-Limit über fail2ban auf den Caddy-Logs. Für 1.000 Nutzer
reicht Variante zwei.

### Und eine Beobachtung, die keine Lücke ist

Die Kombination aus **402 statt Sperre** (Bestand bleibt lesbar) und
**Rückfall auf Free statt Vollsperre bei Zahlungsausfall**
(`mollie.py:218`) ist richtig gebaut. Ein Kunde, dessen Karte platzt,
verliert nie den Zugriff auf seine Daten. Das ist nicht nur freundlich,
sondern erspart dir den größten Teil des Supports, den Sperrlogik erzeugt.

---

## 5 · Bezahlung: was fehlt für echtes Geld

**Die Mechanik steht.** Checkout → Mollie-Webhook → Pull-after-Ping →
`org_entitlement` → Gate. Der Pull-after-Ping ist die richtige Bauweise für
Mollie (deren Webhooks sind nicht signiert) und der Replay-Schutz sitzt
atomar in der DB (`mollie.py:482`).

**Drei Dinge fehlen, bevor du Geld nehmen kannst:**

1. **Die Kette ist nie als Kette getestet.** Jeder Baustein ist geprüft,
   aber kein Test verbindet Checkout, Webhook, Entitlement und ein
   wirksames Limit. Es ist damit **nirgends belegt**, dass ein bezahltes Abo
   die Limits tatsächlich anhebt. Ersatzweise: der Testkauf gegen Prod mit
   anschließender Erstattung (Issue #454) — der ist ohnehin Pflicht.
2. **Keine Rechnung.** Es gibt kein Rechnungs-Artefakt im Repo. Mollie ist
   Zahlungsdienstleister, nicht Rechnungssteller — die Rechnung an deinen
   Kunden musst **du** ausstellen, mit fortlaufender Nummer und, sobald du
   nicht Kleinunternehmer bist, mit Umsatzsteuerausweis. Die
   GoBD-Verfahrensdokumentation im Repo
   (`docs/compliance/gobd-verfahrensdokumentation.md`) beschreibt den
   Rahmen, das Artefakt fehlt.
3. **Umsatzsteuer bei EU-Kunden.** Digitale Leistungen an Verbraucher in
   anderen EU-Ländern werden dort besteuert (OSS-Verfahren). Mollie nimmt
   dir das nicht ab.

**Die Weiche, die hier wirklich zählt:** Punkt 2 und 3 sind zusammen mehrere
Wochen Arbeit plus laufende Pflicht. Ein **Merchant of Record** (Paddle,
Lemon Squeezy) tritt selbst als Verkäufer auf, stellt die Rechnung und
führt die Steuer ab — dafür ~5 % statt Mollies ~1,8 %. Bei 50 Kunden ×
29 € sind das ~46 €/Monat Unterschied; dagegen steht die gesamte
Rechnungs- und Steuerlogik, die du nicht baust. **Empfehlung: für den Start
MoR.** Der Umbau ist überschaubar, weil das Entitlement-Modell
anbieteragnostisch ist (ADR-0028) und der generische HMAC-Webhookpfad
bereits existiert — der bräuchte dann allerdings die Härtung aus WP-4
(Replay-Schutz, Ablauffrist, monotoner Upsert), die für den Mollie-Pfad
schon da ist.

---

## 6 · Prompts und Nutzerdaten: rechtssicher und technisch sicher

### Was du rechtlich bist

Deine Kunden legen bei dir Personas, Playbooks und Ressourcen ab. Steckt
darin ein Personenbezug — und in Prompts steckt er oft, und sei es durch
Beispieldaten — bist du **Auftragsverarbeiter**. Das heißt konkret:

- **Du musst deinen Kunden einen AVV anbieten.** Die Route existiert
  (`apps/web/src/app/routes.tsx:306`), der Text ist ein Platzhalter. Ohne
  AVV darf ein Geschäftskunde dich rechtlich nicht einsetzen.
- **Du brauchst selbst AVVs** mit Hetzner, dem Mail-Provider und Mollie und
  musst sie als Unterauftragsverarbeiter benennen (`docs/compliance/vvt.md`).
- **Betroffenenrechte:** Export nach Art. 20 existiert
  (`routers/gdpr.py:32`), das Löschkonzept ist ausgearbeitet und umgesetzt
  (Soft-Delete → 30 Tage Karenz → Hard-Purge mit Anonymisierung der
  überlebenden Audit-Referenzen auf einen Sentinel). Das ist überdurchschnittlich
  gut für ein Produkt dieser Größe.
- **Die Rechtstexte sind Platzhalter.** Die Liste, was hineingehört, steht
  fertig in `docs/compliance/legal-texts-checklist.md` — inklusive der
  richtigen Paragraphen (§ 5 DDG, § 25 TDDDG). Diese Liste einem Anwalt zu
  geben ist deutlich billiger, als ihn bei null anfangen zu lassen.

### Was technisch schützt — und was nicht

**Schützt heute:**

- TLS überall, HSTS, restriktive CSP je Subdomain (`Caddyfile`).
- **RLS in Postgres** als zweite Verteidigungslinie unter der
  Anwendungslogik — in der Cloud-Edition verbindet die API als
  nicht-privilegierte Rolle.
- Workspace-Präfix im BlobStore als Mandantengrenze
  (`blobs/{workspace_id}/{sha256}`, ADR-0048).
- Eine SQLite-Datei pro WorkArea als Isolationsgrenze, read-only auf
  Engine-Ebene (ADR-0049).
- Backups sind **GPG-verschlüsselt**, das restic-Repo zusätzlich.
- MFA-Step-up für privilegierte Aktionen, Agent-Zugriffe werden protokolliert
  (`agent_access_log`, ADR-0047).

**Schützt nicht:**

- **Prompt-Inhalte liegen in Postgres im Klartext.** Die Verschlüsselung
  ist auf **Volume-Ebene** (LUKS) — sie schützt gegen eine gezogene
  Festplatte, nicht gegen jemanden mit Datenbankzugang. Das schließt **dich**
  ein: Du kannst jeden Prompt jedes Kunden lesen.

Das ist für ein SaaS dieser Größe eine **normale und vertretbare**
Architektur — aber du musst sie kennen und behandeln:

1. **Schreib es in die Datenschutzerklärung**, statt „Ende-zu-Ende
   verschlüsselt" zu behaupten. Eine falsche Aussage dort ist ein größeres
   Problem als die fehlende Verschlüsselung selbst.
2. **Zugriffsdisziplin statt Technik:** eine schriftliche Regel, dass
   Kundeninhalte nur auf ausdrückliche Support-Anfrage und mit Protokoll
   angesehen werden. Klingt nach Bürokratie, ist aber genau das, was ein
   B2B-Kunde in der Lieferantenprüfung fragt.
3. **Logs prüfen:** Strukturierte Logs (ADR-0007) dürfen keine
   Prompt-Inhalte enthalten. Das ist vor dem Launch einmal aktiv zu
   verifizieren — ein Log landet in Backups, in Monitoring und potenziell
   bei Dritten.
4. **Wenn ein Kunde mehr verlangt** (Gesundheits-, Rechts-, Finanzdaten):
   Spalten-Verschlüsselung für die Inhaltsfelder mit einem Schlüssel pro
   Org. Das ist eine eigene, größere Entscheidung — sie bricht Volltextsuche
   und Reverse-Lookups. **Nicht** vorsorglich bauen.

---

## 7 · Backup und Serverausfall

### Was läuft

Täglich um 03:15 UTC: `pg_dump -Fc` → GPG → lokal unter
`/var/backups/who2be`, dann restic nach Hetzner Storage Box. Retention
lokal 7 Tage, offsite 7 täglich / 4 wöchentlich / 6 monatlich. Dazu
dokumentierte Pfade für den Blob-Store (SeaweedFS) und die
SQLite-Tabellenspeicher.

### Vier Dinge, die du wissen musst

**1. Dein RPO ist 24 Stunden.** Ein Dump pro Tag heißt: bei einem
Totalausfall um 03:14 Uhr ist ein Tag Kundenarbeit weg. Für ein kostenloses
Produkt vertretbar, für 29 €/Monat grenzwertig. **Empfehlung:**
WAL-Archivierung dazu (pgBackRest oder WAL-G gegen dieselbe Storage Box)
— damit sinkt der RPO auf Minuten. Alternative für den Anfang: den
Backup-Cron auf alle 6 Stunden stellen, das kostet nichts außer Platz.

**2. Backup-Fehler sind nicht mehr still** (seit 2026-09-21, Issue #541).
Früher waren `restic backup` und `restic forget` bewusst nicht-fatal: schlug der
Offsite-Sync fehl, blieb der lokale Dump erhalten **und das Skript meldete
Erfolg**. Damit hättest du monatelang nicht gemerkt, dass es kein Offsite-Backup
mehr gibt. Heute gilt beides gleichzeitig: der **lokale Dump bleibt unverändert
erhalten**, aber ein gescheiterter Sync beendet den Lauf mit **Exit != 0**.

Zusätzlich gibt es einen Dead-Man's-Switch: setzt du `BACKUP_HEARTBEAT_URL`
(leer = aus), pingt das Skript diese URL nur bei vollständigem Erfolg — und *das
Ausbleiben* des Pings alarmiert dich. Das fängt auch die Fälle, die ein Exit-Code
nicht fangen kann: Cron deaktiviert, Container weg, Host aus. **Der Empfänger ist
bewusst self-hosted** (kein healthchecks.io o. ä.) — ein gehosteter Dienst wäre
Auftragsverarbeiter für deine Betriebsmetadaten und bräuchte einen VVT-Eintrag.
Einrichtung und **Testanleitung** stehen im RUNBOOK unter „Backup & Restore“ →
„Alarmweg (Dead-Man's-Switch)“. **Richte ihn ein und löse ihn einmal absichtlich
aus** — ein nie ausgelöster Alarm ist so viel wert wie ein ungetestetes Backup.

**3. Die Blob-Backup-Kommandos sind ungetestet.** Beim SeaweedFS-Umstieg am
2026-09-19 wurden die alten `mc`-Kommandos ersetzt; der Ersatz ist im
RUNBOOK als offen markiert. **Einmal durchfahren, bevor echte Dateien
drinliegen.**

**4. Der Restore-Drill hat nie stattgefunden.** Die Protokolltabelle im
RUNBOOK ist leer. Das ist der wichtigste offene Punkt dieses ganzen
Dokuments — ein ungetestetes Backup ist eine Vermutung.

### Empfohlener Aufbau (drei Ebenen)

| Ebene | Was | Wogegen |
|---|---|---|
| 1 | Hetzner-Snapshot der VM, wöchentlich | Fehlkonfiguration, kaputtes Update |
| 2 | pg_dump + GPG lokal, alle 6 h | versehentliches Löschen, Datenfehler |
| 3 | restic → Hetzner Storage Box (anderes RZ) | Totalverlust der Box, Ransomware |

Ebene 3 muss in einem **anderen Rechenzentrum** liegen als die Box —
Storage Box in FSN, wenn die VM in NBG steht. Und der Backup-Key gehört
**nicht** auf den Server, den er sichert.

### Der Ausfall-Fall

Bei Totalverlust: neue Box, Repo klonen, `.env` aus dem Passwortmanager,
restic-Snapshot holen, GPG-entschlüsseln, `pg_restore`, Stack hochfahren,
DNS umbiegen. Realistisch **2–4 Stunden**, wenn du es einmal geübt hast —
und ein unbekannt langer Tag, wenn nicht. Was dafür außerhalb des Servers
liegen muss: `.env`-Werte, GPG-Private-Key, `RESTIC_PASSWORD`,
SSH-Keys. In einem Passwortmanager, und die GPG-Passphrase zusätzlich auf
Papier.

---

## 8 · Kosten und Dimensionierung für 1.000 Nutzer

### Lastabschätzung

1.000 registrierte Nutzer heißt nicht 1.000 gleichzeitige. Rechne mit
5–10 % zahlend und der üblichen Verteilung:

- 900 Free × 1.000 Req/Monat = 900.000
- 100 Pro × 100.000 Req/Monat (Vollausschöpfung, unrealistisch hoch) = 10 Mio.

Selbst diese pessimistische Rechnung sind **~4 Requests/Sekunde im Mittel**.
Die Requests sind überwiegend indizierte Lesezugriffe. Eine CCX23 langweilt
sich dabei. Der Engpass wird nicht die CPU sein, sondern **Plattenplatz**
(Blobs) und **RAM für Postgres** — und, bei Spitzen, die fehlende
Org-weite Drosselung aus L2.

### Vorschlag

| Was | Empfehlung |
|---|---|
| App-Server | 1 × CCX23 (4 dedizierte vCPU, 16 GB) |
| Daten-Volume | 100 GB verschlüsselt, wachsend |
| Backup | Hetzner Storage Box BX11 (1 TB), anderes RZ |
| Mail | SMTP-Provider mit gutem Ruf, EU (nicht der eigene Server) |
| Monitoring | Uptime-Check extern + Dead-Man's-Switch fürs Backup |

Größenordnung: **niedriger zweistelliger Euro-Bereich pro Monat**, plus
Mail und Domain. Preise vor der Bestellung prüfen.

### Wann es eng wird — und was dann

Der Stack ist ein **modularer Monolith** (ADR-0001) auf einer Box. Das ist
für diese Größe die richtige Entscheidung. Die Ausbaustufen in der
Reihenfolge, in der sie fällig werden:

1. **Box vergrößern** (CCX33/CCX43). Deckt dich bis weit über 1.000 Nutzer.
2. **Postgres auf eine eigene Box.** Der erste echte Schnitt — trennt die
   Ressource, die am schlechtesten teilt, von allen anderen.
3. **API horizontal skalieren.** Vorbereitet: die API ist zustandslos, der
   Rate-Limit-Storage liegt bereits in Redis, damit mehrere Repliken
   dasselbe Fenster sehen (`core/rate_limit.py`). Davor ein Hetzner Cloud
   Load Balancer statt des einzelnen Caddy.
4. **SeaweedFS auf eigenen Speicher.**

**Was du jetzt schon nicht tun solltest:** Kubernetes. Der Stack hat keinen
einzigen Baustein, der davon profitiert, und du handelst dir eine zweite
Vollzeit-Betriebsaufgabe ein.

---

## 9 · Reihenfolge

**Vor dem ersten Nutzer:**

1. Box + verschlüsseltes Volume + Hardening + DNS (§2, Schritte 1–4)
2. AVV mit Hetzner abschließen
3. Stacks hochfahren, `WHO2BE_LAUNCH_MODE=coming_soon` (§2, Schritte 5–6)
4. Backup einrichten **und einmal restoren** (§7)
5. Smoke + Prod-Reise aus `docs/cloud-prod-smoke.md` (§2, Schritt 7)
6. Deploy-Variablen setzen, `deploy.yml` einmal real laufen lassen

**Vor dem ersten zahlenden Kunden:**

7. L1 Speicher-Quota und L2 Org-Rate-Ceiling schließen (§4)
8. L4 Captcha aktivieren (reine Konfiguration)
9. Entscheidung Mollie vs. Merchant of Record (§5)
10. Rechtstexte füllen lassen, AVV-Angebot online (§6)
11. Testkauf mit Erstattung, Webhook-Log prüfen (Issue #454)
12. Monitoring + Dead-Man's-Switch fürs Backup

**Danach, in Ruhe:**

13. L3 Token-Cap, L5 Kanten-Rate-Limit
14. WAL-Archivierung für RPO in Minuten
15. Tarif-Umstellung auf das Drei-Stufen-Modell aus §3

---

## Verweise

- Operative Kommandos: [`deploy/hetzner/RUNBOOK.md`](../deploy/hetzner/RUNBOOK.md)
- Bring-up und CI/CD: [`deploy/hetzner/README.md`](../deploy/hetzner/README.md)
- Abnahme-Reise Prod: [`docs/cloud-prod-smoke.md`](cloud-prod-smoke.md)
- Tarife (SSoT): [`docs/licensing/plans.md`](licensing/plans.md)
- Compliance-Artefakte: [`docs/compliance/`](compliance/)
- Stations-Inventar: [`.claude/plan/2026-09-05-1520_cloud-launch-readiness-inventar.md`](../.claude/plan/2026-09-05-1520_cloud-launch-readiness-inventar.md)
- Offene Owner-Schritte: Issues #428, #454, #338
