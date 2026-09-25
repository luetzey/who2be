# Cloud-Edition: Erstinbetriebnahme — Vorbereitungsliste fuer den Owner

**Typ:** How-To · **Zielgruppe:** Owner/Betreiber · **Stand:** 2026-09-25,
gemessen gegen `main` @ `cee6478e`

Was hier steht: **alles, was der Owner selbst besorgen, entscheiden oder
anlegen muss**, um die Cloud-Edition auf einer frischen Box in Betrieb zu
nehmen und die Reise *Free → Kauf → Pro* einmal durchzuspielen. Sortiert nach
**Vorlaufzeit** — der erste Punkt dauert Tage und liegt nicht in deiner Hand,
der letzte zwei Minuten.

Was hier **nicht** steht, und wo es steht:

| Du brauchst | Dokument |
|---|---|
| Die Shell-Kommandos fuer Box, Docker, Firewall, DNS-Pruefung, TLS | [`deploy/hetzner/RUNBOOK.md`](../deploy/hetzner/RUNBOOK.md), Abschnitt „Provisioning" |
| Die Bring-up-Reihenfolge der beiden Stacks | [`deploy/hetzner/README.md`](../deploy/hetzner/README.md), Abschnitt „Cloud-Edition" |
| Die Abnahme-Reise mit allen `curl`s | [`cloud-prod-smoke.md`](cloud-prod-smoke.md) |
| Provider-Details (Google/GitHub/Apple im Portal) | [`deploy/hetzner/supabase/README.md`](../deploy/hetzner/supabase/README.md) |

Dieses Dokument wiederholt keine dieser Prozeduren. Es sagt dir, **in welcher
Reihenfolge** du sie brauchst und **was du vorher besorgt haben musst**.

> **Zeitrahmen, ehrlich:** zwei Tage reine Durchfuehrung reichen. Zwei Tage ab
> Null reichen nicht — Phase 0 unten hat Fremd-Vorlauf, den niemand
> beschleunigen kann. Fang mit Phase 0 an, bevor du irgendetwas anderes tust.

---

## Die gute Nachricht zuerst: SMTP brauchst du fuer den Testlauf wahrscheinlich nicht

Das ist die wichtigste Vereinfachung der ganzen Liste, deshalb steht sie oben.

In der Cloud-Edition meldest du dich ueber **Google oder GitHub** an (Apple
kommt dazu). Und GoTrue bestaetigt einen so angelegten Account **selbst**, ohne
eine einzige Mail: liefert der Provider eine als verifiziert markierte
E-Mail-Adresse mit, wird der Nutzer direkt bestaetigt — der Zweig
`CandidateEmail.Verified || Mailer.Autoconfirm` ruft `user.Confirm`
([GoTrue v2.196.0, `createAccountFromExternalIdentity`](https://github.com/supabase/auth/blob/v2.196.0/internal/api/external.go)).

**Fuer dich heisst das:**

- [ ] **Kein SMTP-Provider fuer den Solo-Testlauf.** Du brauchst weder einen
      Mail-Dienst noch `GOTRUE_MAILER_AUTOCONFIRM=true`. Voraussetzung ist
      allein, dass die E-Mail-Adresse deines Google- bzw. GitHub-Kontos dort
      **verifiziert** ist — bei einem normal genutzten Konto ist sie das.
      *Wer: du · Dauer: 0 · Danach anders: ein Beschaffungspunkt weniger, und
      Phase 1 verliert einen Schritt.*

**Die zwei Einschraenkungen, damit du nicht spaeter ueberrascht wirst:**

1. **Ist die Provider-Mail nicht verifiziert**, verschickt GoTrue doch eine
   Bestaetigungsmail und lehnt die Anmeldung mit
   `provider_email_needs_verification` ab — dann brauchst du entweder SMTP oder
   eine verifizierte Adresse beim Provider. Das Symptom ist eindeutig, du
   erkennst es sofort.
2. **Team-Einladungen und E-Mail-Adresswechsel gehen weiter per Mail** und
   brauchen SMTP (`apps/api/src/who2be_api/integrations/gotrue_mailer.py`).
   Beides ist **nicht** Teil des Testlaufs. Vor dem ersten echten Nutzer, den
   du einlaedst, brauchst du einen Mailversand — nicht vorher.

> **Fallback, falls du doch mit E-Mail/Passwort testen willst** (z. B. weil du
> keine OAuth-Apps anlegen magst): dann setze
> `GOTRUE_MAILER_AUTOCONFIRM=true` in `deploy/hetzner/supabase/.env` und
> ueberspringe Phase 0 Punkt 4. Der Prod-Default ist `false` und bedeutet ohne
> SMTP: keine Mail, Account unbestaetigt, Login schlaegt fehl. **Eines von
> beiden — echter Mailversand oder Autoconfirm — muss stehen, sonst kommst du
> nicht ueber den Signup hinaus.**

---

## Phase 0 · Sofort anfangen (Vorlauf: Tage, nicht in deiner Hand)

Diese vier Punkte kannst du heute vom Handy aus anstossen. Alles danach wartet
auf sie.

- [ ] **1 · Mollie-Konto eroeffnen und verifizieren, Test-API-Key (`test_…`)
      notieren.**
      *Wer: nur du · Dauer: 1–5 Werktage Vorlauf, 30 min eigene Arbeit ·
      Danach anders: der Kaufprozess wird testbar.*
      Ohne Test-Key antworten alle `/v1/billing`-Pfade mit **503** — Kauf und
      Webhook-Upgrade fallen aus dem Testlauf. Der Code unterscheidet Test- und
      Live-Key nicht; das macht allein das Key-Praefix. Es fliesst kein Geld.
      **Das ist der laengste Vorlauf der Liste. Fang damit an.**

- [ ] **2 · Domain + DNS-A-Records auf die Box-IP.**
      *Wer: nur du · Dauer: 15 min Arbeit, Minuten bis 24 h Propagation ·
      Danach anders: Caddy kann Let's-Encrypt-Zertifikate holen, und Mollie
      erreicht den Webhook.*

      | Record | Pflicht | wofuer |
      |---|---|---|
      | `api.<DOMAIN>` | ja | API + Mollie-Webhook-Rueckweg |
      | `app.<DOMAIN>` | ja | Web-App |
      | `supabase.<DOMAIN>` | ja | Auth (GoTrue) — **auch die OAuth-Redirect-URI** |
      | `mcp.<DOMAIN>` | optional | nur wenn der MCP-Server remote erreichbar sein soll |

      Alle auf dieselbe Box-IP. Pruefkommando und Reihenfolge: RUNBOOK
      „Provisioning" Schritt 5. **Erst pruefen, dann Caddy starten** — eine
      nicht aufgeloeste Domain laesst die ACME-Challenge scheitern, und
      wiederholte Fehlversuche laufen in Let's-Encrypt-Ratelimits.

- [ ] **3 · Hetzner-Box bestellen — und die At-Rest-Verschluesselung JETZT
      entscheiden.**
      *Wer: nur du · Dauer: 15 min bestellen, 1–2 h Grundeinrichtung ·
      Danach anders: du hast eine IP fuer Punkt 2.*
      EU/EWR-Region, bei Datenresidenz-Erwartung eine DE-Region. Ubuntu 24.04
      LTS, eigener SSH-Key, kein Passwort-Login.
      **Der Punkt, der hier wirklich zaehlt:** die Verschluesselung des
      Daten-Volumes wird **beim Provisioning** entschieden, nicht spaeter.
      Nachtraeglich ist es ein Daten-Umzug, kein Schalter. Varianten und
      Verifikation: RUNBOOK „Verschluesselung at-Rest", einzurichten **vor**
      dem ersten `docker compose up`.

- [ ] **4 · OAuth-Apps bei Google und GitHub anlegen.**
      *Wer: nur du · Dauer: 20–30 min je Provider, Google-Consent-Screen ggf.
      laenger · Danach anders: du kannst dich ueberhaupt anmelden.*
      Das ist der Punkt, an dem man ohne Vorlage scheitert, weil die
      Redirect-URI nicht erratbar ist. Sie lautet **fuer beide Provider
      identisch**, mit deiner Domain statt `<DOMAIN>`:

      ```
      https://supabase.<DOMAIN>/auth/v1/callback
      ```

      Also bei `DOMAIN=example.com` genau
      `https://supabase.example.com/auth/v1/callback`. Kein abschliessender
      Schraegstrich, `https` nicht `http`, und `/auth/v1/callback` vollstaendig
      — ein Zeichen daneben und der Login endet in `redirect_uri_mismatch`.
      Der Wert ist der Compose-Default
      (`GOTRUE_EXTERNAL_{GOOGLE,GITHUB}_REDIRECT_URI` im Supabase-Stack); wenn
      du ihn nicht ueberschreibst, musst du ihn nur im Portal eintragen.

      | Provider | Wo | Feld heisst dort |
      |---|---|---|
      | Google | Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID, Typ „Web application" | **Authorized redirect URIs** |
      | GitHub | Settings → Developer settings → OAuth Apps → New OAuth App | **Authorization callback URL** |

      Bei GitHub ist zusaetzlich die „Homepage URL" Pflicht:
      `https://app.<DOMAIN>`. Google verlangt fuer eine oeffentliche App einen
      konfigurierten Consent-Screen mit Links auf Datenschutz und AGB; die
      liegen unter `https://app.<DOMAIN>/legal/datenschutz` bzw.
      `https://app.<DOMAIN>/legal/agb`.

      Mitnehmen: je Provider **Client-ID** und **Client-Secret** (sechs Werte
      insgesamt, drei pro Provider inkl. des `ENABLED=true`-Schalters).

      > **Apple** ist aufwendiger und in der Einrichtung eigenstaendig: eigene
      > Services-ID, ein `.p8`-Key, und ein Client Secret, das **nach
      > spaetestens sechs Monaten ablaeuft und dann still ausfaellt**. Fuer den
      > Testlauf ist Apple **nicht** noetig — zwei Provider genuegen. Wenn du
      > Apple willst, mach es nach dem Testlauf; die Portal-Schritte und die
      > Erneuerungs-Prozedur stehen in
      > [`deploy/hetzner/supabase/README.md`](../deploy/hetzner/supabase/README.md).

---

## Phase 1 · Am Schreibtisch, bevor du die Box anfasst (Stunden)

- [ ] **5 · Secrets erzeugen und ablegen.**
      *Wer: du · Dauer: 45–60 min · Danach anders: die beiden `.env` sind
      vollstaendig, der Stack kann starten.*

      Es gibt **zwei** `.env`-Dateien, und eine Variable muss in beiden
      **identisch** stehen:

      | Wert | wohin | wie erzeugen |
      |---|---|---|
      | `JWT_SECRET` | **beide** `.env`, **identischer Wert**, >= 32 Zeichen | `openssl rand -base64 48` |
      | `POSTGRES_PASSWORD` | `supabase/.env` (+ `.env` fuer `--profile backup`) | >= 20 Zeichen, stark |
      | `APP_DB_PASSWORD` | `deploy/hetzner/.env` | stark; **nicht** dasselbe wie `POSTGRES_PASSWORD` |
      | `SEAWEEDFS_S3_SECRET_KEY` | `deploy/hetzner/.env` | stark — **hart Pflicht**, s. u. |
      | `ANON_KEY` | `supabase/.env` **und** als `VITE_SUPABASE_ANON_KEY` in `deploy/hetzner/.env` | Skript, s. u. |
      | `SERVICE_ROLE_KEY` | `supabase/.env` **und** als `SUPABASE_SERVICE_KEY` in `deploy/hetzner/.env` | Skript, s. u. |

      Die beiden JWTs erzeugt ein Skript im Repo, mit demselben `JWT_SECRET`:

      ```bash
      uv run python scripts/gen_test_jwt.py --secret "$JWT_SECRET" \
          --role anon         --ttl 315360000    # 10 Jahre
      uv run python scripts/gen_test_jwt.py --secret "$JWT_SECRET" \
          --role service_role --ttl 315360000
      ```

      Rechte setzen, beide Dateien:

      ```bash
      chmod 600 deploy/hetzner/.env deploy/hetzner/supabase/.env
      ```

      Zwei Fallen an dieser Stelle, beide teuer, weil die Fehlermeldung nichts
      sagt:

      - **`JWT_SECRET` weicht zwischen den beiden `.env` ab** ⇒ *jeder* Login
        schlaegt fehl, mit einer Meldung, die nicht auf das Secret zeigt. Wenn
        alles steht und niemand sich anmelden kann: **hier** zuerst schauen.
      - **`SEAWEEDFS_S3_SECRET_KEY` fehlt** ⇒ Compose laesst sich nicht einmal
        *aufloesen* (harter `:?`-Guard am `seaweedfs`-Service). Das ist
        Absicht: ein Objekt-Store mit vorhersagbaren Zugangsdaten auf einer
        oeffentlichen Maschine ist eine offene Tuer. Der Abbruch ist die
        richtige Reaktion, nicht ein Bug.

      Die restlichen Pflichtwerte (`DOMAIN`, `ACME_EMAIL`, `DATABASE_URL`,
      `SUPABASE_URL`, `CORS_ORIGINS`, `SITE_URL`, `VITE_*`) sind in beiden
      `.env.example` kommentiert — **jedes `CHANGE_ME` ersetzen**, keines
      stehen lassen.

- [ ] **6 · OAuth-Zugangsdaten eintragen — in dieser Reihenfolge.**
      *Wer: du · Dauer: 10 min · Danach anders: die Anmeldung funktioniert.*
      In `deploy/hetzner/supabase/.env`:

      ```dotenv
      GOTRUE_EXTERNAL_GOOGLE_ENABLED=true
      GOTRUE_EXTERNAL_GOOGLE_CLIENT_ID=<aus der Google Console>
      GOTRUE_EXTERNAL_GOOGLE_SECRET=<aus der Google Console>
      GOTRUE_EXTERNAL_GITHUB_ENABLED=true
      GOTRUE_EXTERNAL_GITHUB_CLIENT_ID=<aus GitHub>
      GOTRUE_EXTERNAL_GITHUB_SECRET=<aus GitHub>
      ```

      > **Die Reihenfolge ist kein Stil, sondern eine Sperre.** Falls du in der
      > Cloud E-Mail/Passwort abschaltest (`GOTRUE_EXTERNAL_EMAIL_ENABLED=false`):
      > diese Zeile **zuletzt**, erst wenn die sechs darueber wirklich stehen.
      > Umgekehrt sperrst du jeden Anmeldeweg aus — auch deinen eigenen.

---

## Phase 2 · Tag 1 auf der Box (halber Tag)

Ab hier folge den bestehenden Dokumenten. Die Liste sagt nur, **in welcher
Reihenfolge** und **wo die Reihenfolge nicht verhandelbar ist**.

- [ ] **7 · Provisioning durchziehen** — deploy-User, Docker, Firewall
      (22/80/443), Repo nach `/opt/who2be`, beide `.env` aus Phase 1 einsetzen.
      RUNBOOK „Provisioning" Schritte 2–6.
      *Wer: du · Dauer: 1–2 h · Danach anders: die Box kann Container fahren.*

- [ ] **8 · Stacks hochfahren — Supabase zuerst, dann das Cloud-Overlay.**
      `deploy/hetzner/README.md` §Cloud-Edition. **Immer beide `-f`-Dateien**,
      sonst laeuft der On-Prem-Kern und alle Cloud-Schalter sind wirkungslos.
      *Wer: du (oder ein Agent) · Dauer: 30–60 min · Danach anders: die API
      antwortet.*

- [ ] **9 · TLS + Security-Header gruen** — RUNBOOK „Provisioning" Schritt 7.
      *Wer: du · Dauer: 15 min, plus Wartezeit falls DNS noch propagiert ·
      Danach anders: `https://api.<DOMAIN>/v1/health` antwortet mit gueltigem
      Zertifikat.*
      Scheitert das Zertifikat, ist es fast immer DNS (Phase 0 Punkt 2) oder
      Port 80 in der Firewall — nichts an der Anwendung.

- [ ] **10 · Zum ersten Mal anmelden.** `https://app.<DOMAIN>` → „Mit Google
      anmelden" bzw. GitHub.
      *Wer: du · Dauer: 2 min · Danach anders: **jetzt erst** existieren deine
      User-UUID, deine Organisation und dein Workspace.*
      Persoenliche Org, Workspace, Admin-Rolle und Default-Templates entstehen
      beim ersten `/v1/me` automatisch — du legst nichts von Hand in der
      Datenbank an. Das Entitlement ist **Free**, ohne dass du es setzt.

      **Das ist der Reihenfolge-Stolperstein Nummer eins:** deine eigene
      User-UUID kannst du **vorher nicht kennen**. Alles, was sie braucht —
      insbesondere die Betreiber-Allowlist in Schritt 12 — geht erst **nach**
      diesem Signup.

- [ ] **11 · TOTP-Faktor anlegen und damit neu anmelden.**
      Web-UI → Konto-Einstellungen → Sicherheit → Zwei-Faktor → Authenticator
      hinzufuegen. Danach abmelden und **mit Code** neu anmelden.
      *Wer: du · Dauer: 10 min · Danach anders: deine Sitzung ist `aal2` — die
      Voraussetzung fuer jede administrative Aktion.*
      Details: [`mfa-admin.md`](mfa-admin.md).

      **Stolperstein Nummer zwei:** ohne verifizierten Faktor kommt keine
      Sitzung je auf `aal2`, und der Billing-Override in Schritt 12 antwortet
      garantiert `403`. Diesen Schritt nicht aufschieben.

- [ ] **12 · Betreiber-Allowlist fuellen und pruefen, dass sie ankommt.**
      Deine User-UUID (der `sub`-Claim deiner Sitzung) in
      `deploy/hetzner/.env`:

      ```dotenv
      WHO2BE_BILLING_OVERRIDE_OPERATORS=<deine-user-uuid>
      ```

      *Wer: du · Dauer: 15 min · Danach anders: du kannst Pro **ohne** Mollie
      setzen — und einen haengenden Webhook reparieren.*
      Danach die API neu erzeugen und **belegen**, dass die Variable im
      Container steht (`printenv WHO2BE_BILLING_OVERRIDE_OPERATORS`); eine
      leere Ausgabe heisst: der Aufruf in Phase 3 wird `403`. Das Kommando im
      Wortlaut steht in der RUNBOOK-Checkliste „Erste Inbetriebnahme".

      > **Stand `main`, ungeschminkt:** die Variable wird von der
      > Hetzner-Cloud-Overlay-Datei **noch nicht** an den Container
      > durchgereicht — sie in die `.env` zu schreiben genuegt heute nicht. Der
      > Fix ist zwei Zeilen und liegt als offener Pull Request bereit (#636).
      > **Pruefe vor dem Testlauf, ob er gemergt ist**; wenn nicht, ist der
      > `printenv`-Check oben der Beweis und Mollie (Phase 0 Punkt 1) der
      > einzige Weg zu Pro.

---

## Phase 3 · Tag 2 — die Reise fahren

Ab hier fuehrt [`cloud-prod-smoke.md`](cloud-prod-smoke.md). Nichts davon
wiederholt sich hier; das ist die Reihenfolge und die Erwartung je Abschnitt.

- [ ] **13 · Free-Grenzen gegen die Wand fahren.**
      *Wer: du · Dauer: 1–2 h · Danach anders: du hast gesehen, dass die
      Limits durchgesetzt werden und nicht nur angezeigt.*

      | Grenze | Free | Erwartung |
      |---|---|---|
      | MCP-Reads/Monat | 1 000 | `429` |
      | MCP-Rate/Minute | 30 | `429` mit `Retry-After` |
      | Entities/Workspace | 50 | `402` |
      | API-Tokens/Workspace | 3 | `402` |
      | Speicher/Workspace | 100 MiB | `402` |
      | Workspaces/Org | 1 | `402` |

      Wichtig zum Verstaendnis: geblockt wird nur das **Ueberschreiten**.
      Bestehendes bleibt les- und nutzbar — es gibt keine Kontosperre.
      Das MCP-Gate greift ausserdem nur fuer **API-Token**-Aufrufer (`w2b_…`);
      Aufrufe aus der Web-Sitzung laufen daran vorbei. Fuer die drei
      Tarif-Quoten (Speicher/Token/Workspaces) kommen die Smoke-Schritte mit
      PR #636 dazu; bis dahin musst du sie selbst herleiten.

- [ ] **14 · Kaufen — Mollie-Test-Checkout.** `cloud-prod-smoke.md` §4
      Variante B.
      *Wer: du · Dauer: 30 min · Danach anders: der Webhook hat das Entitlement
      auf Pro gehoben.*
      Im Mollie-Test-Modus Status „paid" waehlen; es fliesst kein Geld. Mollie
      ruft `https://api.<DOMAIN>/v1/billing/mollie/webhook` — auf der Box ist
      das oeffentlich erreichbar, **kein Tunnel noetig** (lokal braeuchte es
      ngrok/cloudflared).
      **Das Upgrade wirkt sofort**, es gibt keinen Cache zwischen Gate und
      Tabelle: der naechste Request sieht Pro. Kein Logout, keine
      Neuanmeldung.

      > **Kommt der Webhook nicht an** (Box down, falsche
      > `MOLLIE_WEBHOOK_URL`), bleibt das Entitlement auf Free — es gibt keinen
      > periodischen Abgleich, der das nachholt. Der vorgesehene Reparaturweg
      > ist genau der Override aus Schritt 12. Das ist der zweite Grund, warum
      > Schritt 12 vorher stehen muss.

- [ ] **15 · Pro-Grenzen gegenpruefen.** `cloud-prod-smoke.md` §4
      Entitlement-Check und §5.
      *Wer: du · Dauer: 30 min · Danach anders: die Reise ist belegt.*

      | Grenze | Pro |
      |---|---|
      | MCP-Reads/Monat | 100 000 |
      | MCP-Rate/Minute | 240 |
      | API-Tokens/Workspace | 25 |
      | Speicher/Workspace | 10 GiB |
      | Workspaces/Org | 5 |
      | Entities/Workspace | **unbegrenzt** |

      Das Entity-Limit ist unter Pro absichtlich **nicht** vorhanden — es gibt
      keins, also kannst du es auch nicht bis `402` fahren. Ein Testschritt
      weniger, kein Fehler. Praktisch erreichbar ist auf Pro die
      **Minuten-Rate** (240/min); 100 000 Reads von Hand auszuschoepfen ist
      nicht sinnvoll.

- [ ] **16 · Downgrade pruefen.** `cloud-prod-smoke.md` §6 — belegt den Fall
      „Kuendigung / Override abgelaufen": die Zahlen fallen auf Free zurueck,
      ein Pro-Endpunkt antwortet `402`.
      *Wer: du · Dauer: 15 min · Danach anders: auch der Rueckweg ist belegt.*

---

## Was garantiert schiefgeht, und wie du es erkennst

Die beiden ersten sind keine Vermutung — sie treffen jeden, der die Liste nicht
in dieser Reihenfolge abarbeitet.

| Symptom | Ursache | Abhilfe |
|---|---|---|
| **`403` beim Override, obwohl du Admin bist** | Du hast einen API-Token (`w2b_…`) benutzt. Der Endpunkt lehnt Maschinen-Tokens **kategorisch** ab — auch wenn du in der Allowlist stehst (`packages/billing/src/who2be_billing/router.py#_require_override_operator`). | Mit dem **Web-JWT deiner `aal2`-Sitzung** wiederholen, nicht mit `$TOK`. Der Smoke fuehrt dich sonst genau in diesen Fehler. |
| **`403` beim Override, auch mit Web-JWT** | Die Allowlist ist im Container leer — `.env` nicht gesetzt, API nicht neu erzeugt, oder die Variable wird vom Overlay gar nicht durchgereicht (Stand `main`, s. Schritt 12). Das Gate ist fail-closed: leere Liste ⇒ **immer** 403. | `printenv WHO2BE_BILLING_OVERRIDE_OPERATORS` im `api`-Container. Leer ⇒ Schritt 12. Steht dort wirklich die **User**-UUID, nicht die Org- oder Workspace-Id? |
| **`403` beim Override, Allowlist steht, Web-JWT benutzt** | Die Sitzung ist nur `aal1` — TOTP beim Login nicht beantwortet oder Sitzung abgelaufen. | Neu anmelden **inklusive Code** (Schritt 11). |
| **Niemand kann sich anmelden, Fehlermeldung nichtssagend** | `JWT_SECRET` weicht zwischen den beiden `.env` ab. | Beide Dateien vergleichen (Schritt 5). |
| **`redirect_uri_mismatch` beim Provider-Login** | Redirect-URI im Portal weicht ab — Schraegstrich, `http`, oder falsche Subdomain. | Exakt `https://supabase.<DOMAIN>/auth/v1/callback` (Phase 0 Punkt 4). |
| **`provider_email_needs_verification`** | Die E-Mail-Adresse beim Provider ist nicht verifiziert. | Beim Provider verifizieren — oder SMTP einrichten. |
| **Zertifikat wird nicht ausgestellt** | DNS noch nicht aufgeloest oder Port 80 zu. | `docker compose … logs caddy` nennt den ACME-Fehler im Klartext. Nicht in Schleife neu versuchen — Let's Encrypt hat Ratelimits. |
| **`503` auf Checkout/Webhook** | `MOLLIE_API_KEY` fehlt oder ist leer. | Test-Key setzen, `api` neu erzeugen. Oder den Override-Weg (Schritt 12) nehmen. |
| **Compose bricht ab, bevor irgendetwas startet** | `SEAWEEDFS_S3_SECRET_KEY` fehlt (harter Guard). | Wert setzen (Schritt 5). |
| **Kein `429` im MCP-Check** | Edition ist nicht `cloud`, oder du hast mit einem Web-JWT statt einem `w2b_…`-Token gerufen. | Beide `-f`-Dateien beim Bring-up, und einen API-Token verwenden. |

---

## Was du fuer den Testlauf **nicht** brauchst

Damit die Liste nicht laenger wirkt, als sie ist:

- **Kein SMTP-Provider** (siehe oben) — erst vor dem ersten eingeladenen Nutzer.
- **Kein Apple-Provider** — zwei Anmeldewege genuegen.
- **Keine CI/CD-Verdrahtung.** `DEPLOY_HOST`, `DEPLOY_USER`,
  `DEPLOY_SSH_KEY` und Freunde sind Komfort fuer kuenftige Rollouts; fuer den
  Testlauf reicht Compose von Hand bzw. `deploy/hetzner/scripts/deploy.sh`.
- **Kein Backup-Setup.** Die `RESTIC_*`/`BACKUP_*`-Variablen liest nur
  `--profile backup`. Vor echten Daten ist das Pflicht, fuer den Testlauf nicht.
- **Kein Rechnungs-/Umsatzsteuer-Thema.** Der Test-Modus erzeugt keinen Umsatz.
  Vor dem ersten *zahlenden* Kunden ist es ein harter Blocker mit Wochen
  Vorlauf — das ist ein eigenes Vorhaben, nicht Teil dieser Liste.
