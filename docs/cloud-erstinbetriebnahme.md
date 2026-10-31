# Cloud-Edition: Erstinbetriebnahme — Vorbereitungsliste fuer den Owner

**Typ:** How-To · **Zielgruppe:** Owner/Betreiber · **Stand:** 2026-09-25,
gemessen gegen `main` @ `53c4b854`; Rechnung (Schritt 15, Storno und
Erstattung) 2026-10-24 @ `2660d2c3`; Domain umziehen 2026-10-31 @ `14234887`

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
| Die Provider-Einrichtung in voller Tiefe (Google/GitHub) | [`deploy/hetzner/supabase/README.md`](../deploy/hetzner/supabase/README.md), Abschnitt „Cloud-Edition: nur externe Provider" |

Dieses Dokument wiederholt keine dieser Prozeduren. Es sagt dir, **in welcher
Reihenfolge** du sie brauchst und **was du vorher besorgt haben musst**.

> **Zeitrahmen, ehrlich:** zwei Tage reine Durchfuehrung reichen. Zwei Tage ab
> Null reichen nicht — Phase 0 unten hat Fremd-Vorlauf, den niemand
> beschleunigen kann. Fang mit Phase 0 an, bevor du irgendetwas anderes tust.

---

## Vorab: Die Cloud braucht Mailversand (SMTP)

Owner-Entscheidung vom 2026-10-02: **In der Cloud-Edition ist Mailversand
Pflicht.** Nur die lokale On-Prem-Edition laeuft bewusst ohne Mails. Deshalb
steht `GOTRUE_MAILER_AUTOCONFIRM` in der Cloud per Default auf `false` — im
Hetzner-Supabase-Stack ohnehin, im Dokploy-Weg ueber das Cloud-Overlay
`deploy/dokploy/docker-compose.cloud.yml`.

- [ ] **SMTP-Zugang bei einem Mail-Provider besorgen.**
      *Wer: nur du · Dauer: 30 min bis 1 Tag (Absender-Domain verifizieren,
      SPF/DKIM im DNS) · Danach anders: Bestaetigungs-, Einladungs- und
      Adresswechsel-Mails gehen raus.*
      Mitnehmen: `GOTRUE_SMTP_HOST`, `GOTRUE_SMTP_PORT` (meist `587`),
      `GOTRUE_SMTP_USER`, `GOTRUE_SMTP_PASS`, `GOTRUE_SMTP_ADMIN_EMAIL`
      (Absenderadresse) und optional `GOTRUE_SMTP_SENDER_NAME` (Default
      `Who2Be`). Der Mail-Provider ist ein weiterer Auftragsverarbeiter (siehe
      Phase 0 Punkt 5).

**Was ohne Mail trotzdem geht, und was nicht:**

1. **OAuth-Anmeldung mit verifizierter Provider-Mail.** In der Cloud meldest
   du dich ueber **Google oder GitHub** an — E-Mail/Passwort ist dort
   abgeschaltet. Liefert der Provider eine als verifiziert markierte Adresse
   mit, bestaetigt GoTrue den Account selbst, ohne Mail — der Zweig
   `CandidateEmail.Verified || Mailer.Autoconfirm` ruft `user.Confirm`
   ([GoTrue v2.196.0, `createAccountFromExternalIdentity`](https://github.com/supabase/auth/blob/v2.196.0/internal/api/external.go)).
   Ist die Provider-Mail **nicht** verifiziert, verschickt GoTrue eine
   Bestaetigungsmail und lehnt die Anmeldung mit
   `provider_email_needs_verification` ab — ohne SMTP kommt diese Mail nie an.
2. **Team-Einladungen und E-Mail-Adresswechsel gehen immer per Mail** und
   brauchen SMTP (`apps/api/src/who2be_api/integrations/gotrue_mailer.py`).
   Welche Mailpfade in der Cloud aktiv bleiben, steht als Tabelle im
   [Supabase-README](../deploy/hetzner/supabase/README.md), Abschnitt
   „Cloud-Edition: nur externe Provider".

Fuer einen allerersten Solo-Smoke ohne SMTP laesst sich
`GOTRUE_MAILER_AUTOCONFIRM=true` per Environment voruebergehend setzen — das
ist eine Ausnahme fuer den Smoke, nicht der Cloud-Betrieb.

> **Kein Fallback ueber E-Mail/Passwort.** In der Cloud ist der Weg
> zugeschaltet-aus: das Web-Bundle laeuft mit `VITE_WHO2BE_EDITION=cloud` und
> zeigt kein Passwortformular, und mit
> `GOTRUE_EXTERNAL_EMAIL_ENABLED=false` antwortet GoTrue auf Signup mit `422
> email_provider_disabled`. Die beiden OAuth-Apps aus Phase 0 Punkt 4 sind
> damit **nicht optional** — sie sind der einzige Anmeldeweg.

---

## Phase 0 · Sofort anfangen (Vorlauf: Tage, nicht in deiner Hand)

Diese Punkte kannst du heute vom Handy aus anstossen. Alles danach wartet
auf sie.

- [ ] **1 · Mollie-Konto eroeffnen und verifizieren, Test-API-Key (`test_…`)
      notieren.**
      *Wer: nur du · Dauer: 1–5 Werktage Vorlauf, 30 min eigene Arbeit ·
      Danach anders: der Kaufprozess wird testbar.*
      Ohne Test-Key antworten alle Billing-Pfade mit **503** (Checkout unter
      `/v1/workspaces/{workspace_id}/billing/…`, Webhook unter
      `/v1/billing/mollie/webhook`) — Kauf und
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

- [ ] **3 · Hetzner-Box bestellen — und die At-Rest-Verschluesselung (LUKS)
      JETZT einplanen.**
      *Wer: nur du · Dauer: 15 min bestellen, 1–2 h Grundeinrichtung ·
      Danach anders: du hast eine IP fuer Punkt 2.*
      EU/EWR-Region, bei Datenresidenz-Erwartung eine DE-Region (`nbg1`/`fsn1`).
      Ubuntu 24.04 LTS, eigener SSH-Key, kein Passwort-Login. Server-Typ fuer
      den Testlauf: **CX32** (4 vCPU shared, 8 GB) — Owner-Entscheidung vom
      2026-09-25. Das RUNBOOK nennt an dieser Stelle noch CPX31/CPX41 als
      Beispiel; fuer den Testlauf gilt CX32.
      **Der Punkt, der hier wirklich zaehlt:** die Verschluesselung des
      Daten-Volumes wird **beim Provisioning** eingerichtet, nicht spaeter.
      Nachtraeglich ist es ein Daten-Umzug, kein Schalter. Es gibt dabei
      **nichts zu entscheiden**: Hetzner verschluesselt Volumes **nicht**
      serverseitig (laut eigener TOM Kundenpflicht), also ist selbst
      verwaltetes **LUKS** der einzige gueltige Weg. Kommandos und
      Verifikation: RUNBOOK-Abschnitt Verschluesselung at-Rest, einzurichten
      **vor** dem ersten `docker compose up`.

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
      > Testlauf ist Apple **nicht** noetig — zwei Provider genuegen. Und es
      > gibt dafuer im Repo **noch keine Anleitung**: weder die Portal-Schritte
      > noch die Erneuerungs-Prozedur sind irgendwo dokumentiert, die
      > Apple-Karte ist offen. Wenn du Apple willst, mach es nach dem Testlauf
      > — und rechne damit, dass du die Schritte selbst zusammensuchst.

- [ ] **5 · AVV mit Hetzner abschliessen.**
      *Wer: nur du · Dauer: 15 min in der Console, Gegenzeichnung kann Tage
      dauern · Danach anders: die Datenschutzerklaerung traegt.*
      Hetzner verarbeitet als Hoster die gesamte Datenbank und die Backups in
      deinem Auftrag. Der Auftragsverarbeitungsvertrag wird in der
      Hetzner-Console unter den Vertragsdokumenten abgeschlossen. Ohne ihn
      fehlt der Unterbau fuer die Aussagen, die die Datenschutzerklaerung ueber
      den Hoster macht — und der Eintrag im Verzeichnis der Verarbeitungen
      bleibt ein Platzhalter (`docs/compliance/vvt.md`, Zeile Hetzner). Dasselbe
      gilt fuer die weiteren Verarbeiter, sobald sie im Spiel sind
      (Mail-Provider, Mollie, Cloudflare bei aktivem Captcha).
      **Kein Rechtsrat** — welche Fassung du brauchst und was in die Texte
      gehoert, klaert der Betreiber bzw. eine anwaltliche Pruefung;
      `docs/compliance/legal-texts-checklist.md` listet den Inhalt.

---

## Phase 1 · Am Schreibtisch, bevor du die Box anfasst (Stunden)

- [ ] **6 · Secrets erzeugen und ablegen.**
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

- [ ] **7 · OAuth-Zugangsdaten eintragen — in dieser Reihenfolge.**
      *Wer: du · Dauer: 10 min · Danach anders: die Anmeldung funktioniert.*
      In `deploy/hetzner/supabase/.env`:

      ```dotenv
      GOTRUE_EXTERNAL_GOOGLE_ENABLED=true
      GOTRUE_EXTERNAL_GOOGLE_CLIENT_ID=<aus der Google Console>
      GOTRUE_EXTERNAL_GOOGLE_SECRET=<aus der Google Console>
      GOTRUE_EXTERNAL_GITHUB_ENABLED=true
      GOTRUE_EXTERNAL_GITHUB_CLIENT_ID=<aus GitHub>
      GOTRUE_EXTERNAL_GITHUB_SECRET=<aus GitHub>

      # Erst danach, nie davor:
      GOTRUE_EXTERNAL_EMAIL_ENABLED=false
      ```

      > **Die Reihenfolge ist kein Stil, sondern eine Sperre.**
      > `GOTRUE_EXTERNAL_EMAIL_ENABLED=false` zuerst zu setzen, ohne dass ein
      > Provider laeuft, sperrt **jeden** Anmeldeweg aus — auch deinen eigenen.
      > Der Compose-Default ist `true`; fuer die Cloud gehoert die Zeile in
      > `deploy/hetzner/supabase/.env`, und das Web-Bundle bekommt das
      > Gegenstueck `VITE_WHO2BE_EDITION=cloud` aus dem Cloud-Overlay, damit
      > die UI das Passwortformular gar nicht erst zeigt.

---

## Phase 2 · Tag 1 auf der Box (halber Tag)

Ab hier folge den bestehenden Dokumenten. Die Liste sagt nur, **in welcher
Reihenfolge** und **wo die Reihenfolge nicht verhandelbar ist**.

- [ ] **8 · Provisioning durchziehen** — deploy-User, Docker, Firewall
      (22/80/443), Repo nach `/opt/who2be`, beide `.env` aus Phase 1 einsetzen.
      RUNBOOK „Provisioning" Schritte 2–6.
      *Wer: du · Dauer: 1–2 h · Danach anders: die Box kann Container fahren.*

- [ ] **9 · Stacks hochfahren — Supabase zuerst, dann das Cloud-Overlay.**
      `deploy/hetzner/README.md` §Cloud-Edition. **Immer beide `-f`-Dateien**,
      sonst laeuft der On-Prem-Kern und alle Cloud-Schalter sind wirkungslos.
      *Wer: du (oder ein Agent) · Dauer: 30–60 min · Danach anders: die API
      antwortet.*

- [ ] **10 · TLS + Security-Header gruen** — RUNBOOK „Provisioning" Schritt 7.
      *Wer: du · Dauer: 15 min, plus Wartezeit falls DNS noch propagiert ·
      Danach anders: `https://api.<DOMAIN>/v1/health` antwortet mit gueltigem
      Zertifikat.*
      Scheitert das Zertifikat, ist es fast immer DNS (Phase 0 Punkt 2) oder
      Port 80 in der Firewall — nichts an der Anwendung.

- [ ] **10b · Hintergrund-Routinen: Worker healthy, erster Lauf sichtbar.**
      *Wer: du · Dauer: 5 min, plus ein Blick ins Protokoll nach dem ersten
      Lauf · Danach anders: belegt ist, dass der DSGVO-Purge laeuft und
      unbestaetigte Gedaechtnis-Eintraege nach 30 Tagen verfallen, wie die
      Oberflaeche es zusagt.*
      Einzuplanen ist nichts mehr: `who2be-purge` und
      `who2be-memory-expire` laufen als Routinen `purge` und `memory-expire`
      im Compose-Dienst `worker`, der mit dem Stack startet (ADR-0057). Beim
      ersten Start holt er beide einmal nach, danach laufen sie taeglich um
      03:30 bzw. 03:45 UTC. Pruefen, Hetzner-Box: RUNBOOK-Checkliste „Erste
      Inbetriebnahme" Schritt 7b. Instanz auf Dokploy:
      [Hintergrundjobs auf Dokploy](#hintergrundjobs-auf-dokploy)
      unten. Abgehakt ist der Punkt erst, wenn der Container `worker` healthy
      ist und je Routine ein `succeeded`-Lauf im Log bzw. in `routine_run`
      steht — der laufende Dienst allein reicht nicht.

- [ ] **11 · Zum ersten Mal anmelden.** `https://app.<DOMAIN>` → „Mit Google
      anmelden" bzw. GitHub.
      *Wer: du · Dauer: 2 min · Danach anders: **jetzt erst** existieren deine
      User-UUID, deine Organisation und dein Workspace.*
      Persoenliche Org, Workspace, Admin-Rolle und Default-Templates entstehen
      beim ersten `/v1/me` automatisch — du legst nichts von Hand in der
      Datenbank an. Das Entitlement ist **Free**, ohne dass du es setzt.

      **Das ist der Reihenfolge-Stolperstein Nummer eins:** deine eigene
      User-UUID kannst du **vorher nicht kennen**. Alles, was sie braucht —
      insbesondere die Betreiber-Allowlist in Schritt 13 — geht erst **nach**
      diesem Signup.

- [ ] **12 · TOTP-Faktor anlegen und damit neu anmelden.**
      Web-UI → Konto-Einstellungen → Sicherheit → Zwei-Faktor → Authenticator
      hinzufuegen. Danach abmelden und **mit Code** neu anmelden.
      *Wer: du · Dauer: 10 min · Danach anders: deine Sitzung ist `aal2` — die
      Voraussetzung fuer jede administrative Aktion.*
      Details: [`mfa-admin.md`](mfa-admin.md).

      **Stolperstein Nummer zwei:** ohne verifizierten Faktor kommt keine
      Sitzung je auf `aal2`, und der Billing-Override in Schritt 13 antwortet
      garantiert `403`. Diesen Schritt nicht aufschieben.

- [ ] **13 · Betreiber-Allowlist fuellen und pruefen, dass sie ankommt.**
      Deine User-UUID (der `sub`-Claim deiner Sitzung) in
      `deploy/hetzner/.env`:

      ```dotenv
      WHO2BE_BILLING_OVERRIDE_OPERATORS=<deine-user-uuid>
      ```

      *Wer: du · Dauer: 15 min · Danach anders: du kannst Pro **ohne** Mollie
      setzen — und einen haengenden Webhook reparieren.*
      Danach die API neu erzeugen und **belegen**, dass die Variable im
      Container ankommt:

      ```bash
      docker compose \
        -f deploy/hetzner/who2be/docker-compose.yml \
        -f deploy/hetzner/who2be/docker-compose.cloud.yml \
        --env-file deploy/hetzner/.env \
        exec api printenv WHO2BE_BILLING_OVERRIDE_OPERATORS
      ```

      Eine leere Ausgabe heisst: der Aufruf in Phase 3 wird `403`.

      > **Stand `main`, gepruefter Beleg:** die Variable wird vom
      > Hetzner-Cloud-Overlay als
      > `WHO2BE_BILLING_OVERRIDE_OPERATORS: ${WHO2BE_BILLING_OVERRIDE_OPERATORS:-}`
      > durchgereicht — ein `.env`-Eintrag kommt also im Container an. Der
      > `printenv`-Check oben ist trotzdem der Beweis, denn ein vergessenes
      > `--force-recreate api` sieht genauso aus wie eine fehlende Variable.
      > Dieselben Teilschritte stehen als RUNBOOK-Checkliste „Erste
      > Inbetriebnahme" Schritt 6b, dort mit dem `up -d --force-recreate api`
      > davor.

---

## Phase 3 · Tag 2 — die Reise fahren

Ab hier fuehrt [`cloud-prod-smoke.md`](cloud-prod-smoke.md). Nichts davon
wiederholt sich hier; das ist die Reihenfolge und die Erwartung je Abschnitt.

- [ ] **14 · Free-Grenzen gegen die Wand fahren.**
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
      Tarif-Quoten (Speicher/Token/Workspaces) fuehrt dich
      `cloud-prod-smoke.md` §5b Schritt fuer Schritt.

- [ ] **15 · Kaufen — Mollie-Test-Checkout.** `cloud-prod-smoke.md` §4
      Variante B.
      *Wer: du · Dauer: 30 min · Danach anders: der Webhook hat das Entitlement
      auf Pro gehoben, und zur Zahlung liegt eine archivierte Test-Rechnung.*

      Zwei Voraussetzungen, sonst bricht der Checkout ab, bevor Mollie
      gefragt wird:

      - **Steuermodus gesetzt.** `WHO2BE_INVOICE_TAX_MODE` (`regular` oder
        `small_business`) steht in `deploy/hetzner/.env` bzw. in Dokploy →
        Environment, `api` und `worker` sind danach neu erzeugt. Ohne Wert
        antwortet der Checkout `503 Rechnungsstellung nicht konfiguriert.`
        Welcher Wert fuer den Echtbetrieb gilt, legst du vor dem ersten
        zahlenden Kunden fest; fuer den Testlauf zaehlt nur, dass einer
        gesetzt ist. `WHO2BE_INVOICE_PRICE_BASIS` bleibt ohne Eintrag auf
        `net`. Beide Schalter: ADR-0061 §5,
        [GoBD-Verfahrensdokumentation](compliance/gobd-verfahrensdokumentation.md)
        §5.2.
      - **Rechnungsdaten gespeichert.** Im Billing-Bereich der Web-App
        Kundentyp, Name bzw. Firma und Adresse eintragen (Platzhalterwerte
        genuegen im Test-Modus). Ohne sie antwortet der Checkout `409`.

      Im Mollie-Test-Modus Status „paid" waehlen; es fliesst kein Geld. Mollie
      ruft `https://api.<DOMAIN>/v1/billing/mollie/webhook` — auf der Box ist
      das oeffentlich erreichbar, **kein Tunnel noetig** (lokal braeuchte es
      ngrok/cloudflared).
      **Das Upgrade wirkt sofort**, es gibt keinen Cache zwischen Gate und
      Tabelle: der naechste Request sieht Pro. Kein Logout, keine
      Neuanmeldung.

      Die Rechnung stellt der Worker aus (Routine `invoice-retry`, alle
      5 min). Spaetestens nach dem naechsten Lauf:

      ```bash
      docker exec -i "$DB" psql -U supabase_admin -d postgres -c \
        "SELECT status, invoice_number, tax_mode, price_basis, last_error
           FROM billing_invoice ORDER BY created_at DESC LIMIT 5"
      # → status = archived, invoice_number gesetzt
      ```

      `$DB` wie unter [Worker pruefen](#worker-pruefen-ohne-dokploy-ui).
      Steht die Zeile auf `pending` mit `last_error = hold:…`, nennt der Text
      nach `hold:` den Grund (Tabelle unten).

      > **Kommt der Webhook nicht an** (Box down, falsche
      > `MOLLIE_WEBHOOK_URL`), bleibt das Entitlement auf Free — es gibt keinen
      > periodischen Abgleich, der das nachholt. Der vorgesehene Reparaturweg
      > ist genau der Override aus Schritt 13. Das ist der zweite Grund, warum
      > Schritt 13 vorher stehen muss.

- [ ] **16 · Pro-Grenzen gegenpruefen.** `cloud-prod-smoke.md` §4
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

- [ ] **17 · Downgrade pruefen.** `cloud-prod-smoke.md` §6 — belegt den Fall
      „Kuendigung / Override abgelaufen": die Zahlen fallen auf Free zurueck,
      ein Pro-Endpunkt antwortet `402`.
      *Wer: du · Dauer: 15 min · Danach anders: auch der Rueckweg ist belegt.*

---

## Hintergrundjobs auf Dokploy

Gehoert zu Schritt 10b. Der DSGVO-Purge und der Verfall unbestaetigten
Gedaechtnisses laufen als Routinen `purge` und `memory-expire` im
Compose-Dienst `worker` (ADR-0057). Eine Instanz aus
`deploy/dokploy/docker-compose.yml` (mit oder ohne Cloud-Overlay) bringt ihn
mit; er erscheint mit dem naechsten Deploy in der Dienstliste, ohne
UI-Schritt. **Ein Dokploy-Schedule wird nicht mehr angelegt.** Betrieb,
Zeitplaene, Overrides und Notfallweg stehen im RUNBOOK unter
[Hintergrund-Routinen (Worker)](../deploy/hetzner/RUNBOOK.md#hintergrund-routinen-worker);
dieser Abschnitt nennt nur, was auf Dokploy anders ist.
[`oauth-e2e-dokploy.md`](oauth-e2e-dokploy.md) verweist hierher.

Wer einen Zeitplan per `WHO2BE_ROUTINE_*` oder den Worker per
`WHO2BE_WORKER_ENABLED` aendert, erzeugt danach `worker` **und** `api` neu:
auf Dokploy per Redeploy, auf Hetzner mit `$COMPOSE up -d worker api` (RUNBOOK).
`api` liest dieselben Variablen fuer die Betreiber-Uebersicht
`GET /v1/system/routines`; bleibt `api` auf dem alten Stand, zeigt sie
weiter die alten Zeitplaene, obwohl der Worker schon nach den neuen laeuft.

| Routine | Zeitplan (UTC) | Was sie tut |
|---|---|---|
| `purge` | `30 3 * * *` | DSGVO-Hard-Purge nach der 30-Tage-Grace, dazu die WorkArea-/KB-Sweeps (abgelaufene Artifacts, verwaiste Blobs, geloeschte Area-Stores) |
| `memory-expire` | `45 3 * * *` | setzt unbestaetigte Gedaechtnis-Eintraege nach Ablauf der 30-Tage-Frist auf `expired` (ADR-0053 3.1.3), loescht nichts |
| `audit-retention` | `0 4 * * *` | loescht den anonymen Audit-Rest geloeschter Workspaces/Orgs 12 Monate nach der Anonymisierung (Owner E1a) |
| `usage-retention` | `10 4 * * *` | loescht Nutzungs-Rohzeilen (`usage_event`) aelter als 13 Monate (Owner E4b) |
| `routine-run-retention` | `15 4 * * *` | loescht das eigene Laufprotokoll nach 90 Tagen |
| `invoice-retry` | alle 5 min | nur Cloud: stellt vorgemerkte Rechnungen bei Mollie aus und archiviert das PDF (ADR-0061 §4); braucht im `worker` `MOLLIE_API_KEY` und `WHO2BE_INVOICE_TAX_MODE` |

Alle Routinen sind idempotent. Beim ersten Start holt der Worker Purge,
Verfall, Audit- und Nutzungs-Aufbewahrung einmal nach; danach gelten die
Zeiten der Tabelle.

### Schedules loeschen, falls angelegt

Instanzen, die vor dem Worker in Betrieb gingen, haben im Dienst `api` noch
je einen Schedule `who2be-purge` und `who2be-memory-expire` (Tab
**Schedules**). Sie schaden nicht: laeuft gerade der Worker-Lauf derselben
Routine, endet der Schedule-Lauf mit der Meldung `Routine … uebersprungen`,
sonst ist er ein No-op. Gebraucht werden sie aber nicht mehr.

1. Erst die [Pruefung unten](#worker-pruefen-ohne-dokploy-ui) machen: Worker
   healthy, je Routine ein `succeeded`-Lauf.
2. Im Compose-Service, Tab **Schedules**, beide Eintraege loeschen. Ihre
   Log-Historie geht damit verloren; das Laufprotokoll des Workers steht in
   `routine_run`.

Wer es vergisst, bekommt eine Erinnerung: laeuft eine Routine an zwei
aufeinanderfolgenden Tagen per CLI, schreibt der Worker taeglich
`Externer Zeitplan erkannt: Routine …` ins Log.

### Worker pruefen (ohne Dokploy-UI)

Auf dem Host. Laufen dort mehrere Compose-Projekte mit Diensten `worker` bzw.
`db`, liefert der Filter mehrere Container — dann zusaetzlich nach
`label=com.docker.compose.project=<name>` filtern.

```bash
W="$(docker ps -q --filter label=com.docker.compose.service=worker)"
DB="$(docker ps -q --filter label=com.docker.compose.service=db)"

# 1) Gesund? Healthcheck = `who2be-worker check` (Heartbeat juenger als 2 min).
docker inspect -f '{{.State.Health.Status}}' "$W"
# → healthy

# 2) Wirksame Zeitplaene:
docker exec "$W" who2be-worker list
# → audit-retention, purge, memory-expire, routine-run-retention,
#   usage-retention, invoice-retry, alle "on"

# 3) Erste Laeufe im Protokoll:
docker exec -i "$DB" psql -U supabase_admin -d postgres -c \
  "SELECT routine, trigger, status, started_at, result
     FROM routine_run ORDER BY started_at DESC LIMIT 10"
# → je Routine mindestens ein Lauf mit status = succeeded
```

In der Dokploy-Oberflaeche zeigt der Dienst `worker` dieselben Informationen
unter **Logs**: beim Start die Zeile `… Effektive Zeitplaene (UTC):` mit der
Tabelle, je Lauf `Routine <name>, Slot …: succeeded {…}`.

Optional, fuer den Verfall in der Datenbank:

```bash
docker exec -i "$DB" psql -U supabase_admin -d postgres -tAc \
  "SELECT count(*) FROM agent_memory_event WHERE event = 'expired' AND actor_kind = 'system'"
```

Die Zahl waechst nur, wenn wirklich etwas faellig war.

Was auf ein Problem zeigt, Dokploy-spezifisch (alle weiteren Meldungen: RUNBOOK
[Worker pruefen](../deploy/hetzner/RUNBOOK.md#worker-pruefen)):

| Befund | Bedeutung | Abhilfe |
|---|---|---|
| Dienst `worker` fehlt in der Dienstliste | Deploy noch auf einem Stand vor dem Worker | neu deployen |
| `worker` ist `unhealthy` | kein Heartbeat seit 2 min, meist `db` nicht erreichbar oder `DATABASE_URL` falsch | Logs des Dienstes `worker` lesen, Dienst `db` pruefen |
| `(kein BlobStore konfiguriert)` bzw. `blobstore_skipped: 1` im Purge-Ergebnis | `WHO2BE_BLOBSTORE_*` fehlt im Worker | Environment pruefen; sonst bleiben Objekte liegen |

### Manueller Lauf

Statt eines Schedules: `docker exec "$W" who2be-worker run-once purge` (bzw.
`memory-expire`). Laeuft die Routine gerade, endet der Aufruf als `skipped`.
Den Notfallweg ohne laufenden Worker beschreibt das RUNBOOK unter
[Manueller Lauf und Notfallweg](../deploy/hetzner/RUNBOOK.md#manueller-lauf-und-notfallweg);
auf Dokploy laeuft `who2be-purge` bzw. `who2be-memory-expire` dafuer per
`docker exec` im Container des Dienstes `api`.

Anhalten geht ueber den Dienst `worker` (Stop in der Oberflaeche); der
naechste Deploy startet ihn wieder. Wer anhaelt, setzt die Zusagen aus: kein
DSGVO-Purge, kein Verfall. Was ein Lauf schon getan hat, nimmt das Anhalten
nicht zurueck.

---

## Storno und Erstattung

Gehoert zum Betrieb, nicht zum Testlauf. Grundlage: ADR-0061 §8 und
[GoBD-Verfahrensdokumentation](compliance/gobd-verfahrensdokumentation.md) §5.3.

Who2Be aendert eine ausgestellte Rechnung **nie** und erkennt eine Erstattung
oder Rueckbuchung heute **nicht** von selbst: ein zweiter Webhook zur selben
Zahlung ist ein No-op. Mollie Invoicing kennt weder Gutschrift noch
Stornorechnung. Den Fall bearbeitest du deshalb von Hand:

1. **Rechnung finden.** Rechnungsnummer zur Zahlung (`tr_…`):

   ```bash
   docker exec -i "$DB" psql -U supabase_admin -d postgres -c \
     "SELECT invoice_number, status, issued_at, pdf_key
        FROM billing_invoice WHERE payment_id = '<tr_…>'"
   ```

2. **Erstattung in Mollie ausloesen** (Dashboard, bei der Zahlung). Eine
   Rueckbuchung durch die Bank siehst du ebenfalls nur dort.
3. **Korrekturbeleg erstellen**, mit Bezug auf die Originalnummer. Welcher
   Beleg noetig ist, legst du einmal fest und haeltst es in der
   GoBD-Verfahrensdokumentation §6 fest.
4. **Korrekturbeleg ablegen**, neben dem Original:
   `<PLATZHALTER: Ablageort fuer Korrekturbelege>`. Who2Be hat dafuer heute
   keinen Upload; das Original bleibt unveraendert im Archiv.
5. **Nicht tun:** die Rechnung in Mollie auf `payment-reversed` setzen oder
   loeschen, die Zeile in `billing_invoice` aendern. Der Trigger lehnt
   Aenderungen an Nummer, Betrag, Steuerangaben und PDF einer ausgestellten
   Rechnung ab; geloescht wird erst nach Ablauf der Aufbewahrungsfrist.
6. **Abo und Tarif** sind davon getrennt: kuendigen ueber Mollie bzw. den
   Override (Schritt 13), wie im Downgrade-Fall (Schritt 17).

Steht eine Zeile auf `failed` (ERROR-Zeile im Worker-Log
`Rechnung … endgueltig fehlgeschlagen`): im Mollie-Dashboard pruefen, ob zur
Zahlung schon eine Rechnung existiert, und sie sonst dort von Hand ausstellen.

---

## Domain umziehen

Gehoert zum Betrieb, nicht zum Testlauf. Anlass ist die Owner-Entscheidung vom
2026-10-27: Zum Cloud-Release laeuft die Cloud unter der Produktdomain, also
`DOMAIN=who2be.de` und damit `app.`, `api.`, `supabase.` und `mcp.who2be.de`.
Der Apex `who2be.de` bleibt die Website, an seinen Records aenderst du nichts.

Unten steht `<DOMAIN>` fuer die neue Domain und `<ALT_DOMAIN>` fuer die
bisherige. `<BOX_IP>` ist die oeffentliche Adresse der Box.

**Was der Stack selbst nachzieht.** Im Dokploy-Stack leiten sich alle
Hostnamen aus `DOMAIN` ab: die Traefik-Router, Supabase-Auth (`SITE_URL`,
Allow-List, JWT-Issuer, Provider-Redirect), CORS, der OAuth-Issuer, die
Consent-URL und die MCP-Resource, dazu die API-, Supabase- und MCP-URLs der
Web-App. Das Inventar mit Datei und Zeile steht in
[`.claude/plan/2026-10-31-0056_domain-umzug.md`](../.claude/plan/2026-10-31-0056_domain-umzug.md).

**Was du von Hand umstellst, weil es nicht im Repo liegt:** die DNS-Records,
`MOLLIE_WEBHOOK_URL`, eventuell uebersteuerte Env-Werte, die
Traefik-Datei `who2be-headers.yml`, die Provider-Konsolen bei Google, GitHub
und Apple, die laufenden Mollie-Subscriptions, die Connectoren deiner Nutzer
sowie die Links auf der Website und die Uptime-Checks.

**Folgen, die du einplanen musst:**

- **Alle Nutzer melden sich neu an.** Die neue Web-Adresse ist ein neuer
  Origin, die Browser-Sitzung der alten liegt dort nicht. Ausserdem traegt
  jedes Supabase-JWT den alten Issuer, und den lehnt die API ab
  (`apps/api/src/who2be_api/core/security.py#_jwt_issuer`).
- **Jeder Connector muss neu verbunden werden**, das betrifft Claude, ChatGPT,
  Claude Code und Hermes. Die Tokens selbst bleiben gueltig, nur erreicht der
  Client sie nicht mehr. Die Begruendung steht in Schritt U5.
- **Mail-Links von vor dem Umzug sind tot.** Das betrifft offene Einladungen,
  Bestaetigungs- und Adresswechsel-Mails, denn sie zeigen auf
  `supabase.<ALT_DOMAIN>`.

Waehle ein ruhiges Fenster ohne laufende Checkouts. Der Rueckweg
(Schritt U8) ist nur in den ersten Stunden billig.

### U1 · DNS-Records anlegen, TTL vorher senken (Vorlauf: mindestens 24 h)

- [ ] Bei den **bisherigen** Records `api.`, `app.`, `supabase.` und
      `mcp.<ALT_DOMAIN>` die TTL auf `300` senken, und zwar mindestens eine
      alte TTL vor dem Umzug. Die Records selbst bleiben stehen, bis das
      Rueckweg-Fenster zu ist (Schritt U8).
- [ ] Fuer die **neuen** Hosts je einen Record auf die Box anlegen, mit
      TTL `300`. Das darf Tage vor dem Umzug passieren: Bis Schritt U3 hat
      Traefik keinen Router fuer die neuen Namen und antwortet nur mit `404`.

      | Record | Typ | Ziel |
      |---|---|---|
      | `api.<DOMAIN>` | A (+ AAAA) | `<BOX_IP>` |
      | `app.<DOMAIN>` | A (+ AAAA) | `<BOX_IP>` |
      | `supabase.<DOMAIN>` | A (+ AAAA) | `<BOX_IP>` |
      | `mcp.<DOMAIN>` | A (+ AAAA) | `<BOX_IP>` |

      Ein AAAA-Record nur dann, wenn die Box per IPv6 auf Port 80 und 443
      antwortet. Let's Encrypt prueft bevorzugt ueber IPv6, ein AAAA ins Leere
      laesst die Zertifikatsausstellung scheitern.
- [ ] Am Apex nach CAA-Records sehen. Gibt es welche, muss
      `letsencrypt.org` darunter sein.

**Pruefen** (Workstation):

```bash
D=<DOMAIN>
for s in api app supabase mcp; do
  printf '%-9s A=%s AAAA=%s\n' "$s" "$(dig +short A $s.$D)" "$(dig +short AAAA $s.$D)"
done                                   # → jeweils <BOX_IP>, AAAA leer oder die v6 der Box
dig +short CAA "$D"                    # → leer oder enthaelt letsencrypt.org
dig +noall +answer api.<ALT_DOMAIN>    # → zweite Spalte (TTL) ≤ 300
# Die Box antwortet unter dem neuen Namen. Vor Schritt U3 ist 404 oder ein
# 30x richtig, ein Timeout oder "Could not resolve host" ist falsch:
curl -4 -s -o /dev/null -w '%{http_code}\n' "http://app.$D/"
curl -6 -s -o /dev/null -w '%{http_code}\n' "http://app.$D/"   # nur mit AAAA
```

### U2 · Env-Werte in Dokploy und Provider-Konsolen

Erst die Konsolen, dann Dokploy, denn Google und Apple vertragen mehrere
Redirect-URIs parallel.

- [ ] **Google** (Cloud Console → *APIs & Services*): Unter *Credentials* beim
      OAuth-Client `https://supabase.<DOMAIN>/auth/v1/callback` **zusaetzlich**
      eintragen, die alte URI bleibt. Unter *OAuth consent screen* →
      *Authorized domains* die neue Domain ergaenzen; Homepage, Datenschutz-
      und AGB-Link auf `https://app.<DOMAIN>/…` umstellen (Pfade wie in
      Phase 0 Punkt 4). Google verlangt fuer eine neue Authorized Domain einen
      Besitznachweis in der Search Console. Das hat Vorlauf, also mit Schritt U1
      anfangen.
- [ ] **Apple** (nur wenn aktiv; Services ID → *Sign in with Apple*): unter
      *Domains and Subdomains* `supabase.<DOMAIN>` und unter *Return URLs*
      `https://supabase.<DOMAIN>/auth/v1/callback` **ergaenzen**. Das
      Client-Secret-JWT haengt nicht an der Domain und bleibt.
- [ ] **GitHub**: Eine OAuth-App kennt genau **eine** Callback-URL. Sie wird
      deshalb erst im Umschaltmoment geaendert, direkt nach dem Deploy in
      Schritt U3, auf `https://supabase.<DOMAIN>/auth/v1/callback`; die
      Homepage-URL auf `https://app.<DOMAIN>`. Zwischen Deploy und Aenderung
      scheitert der GitHub-Login mit `redirect_uri_mismatch`.
- [ ] **Dokploy → Projekt → Environment:**
      - `DOMAIN=<DOMAIN>`
      - `MOLLIE_WEBHOOK_URL=https://api.<DOMAIN>/v1/billing/mollie/webhook`
        (ist `MOLLIE_WEBHOOK_SECRET` gesetzt, mit `?token=<secret>` dahinter,
        wie bisher). Das ist der **einzige** Hostname, den der Stack nicht aus
        `DOMAIN` ableitet.
      - Stehen `WEB_BASE_URL` oder `GOTRUE_EXTERNAL_{GOOGLE,GITHUB,APPLE}_REDIRECT_URI`
        ausdruecklich im Environment, diese Zeilen loeschen. Dann greift der
        aus `DOMAIN` abgeleitete Default.
      - Banner fuer die Nutzer, die sich neu anmelden, z. B.
        `WHO2BE_NOTICE_DE="Neue Adresse: Bitte verbinde deine Connectoren neu (Agent → Verbindung)."`
        und `WHO2BE_NOTICE_EN` (Werte: [`signup-and-invites.md`](signup-and-invites.md)).
        Nach zwei Wochen wieder leeren.
      - Im Environment-Editor nach `<ALT_DOMAIN>` suchen. Am Ende darf nur
        noch eine Absenderadresse `GOTRUE_SMTP_ADMIN_EMAIL` uebrig sein, falls
        sie bewusst bei der alten Mail-Domain bleibt.
- [ ] **Dokploy → Compose → Domains:** Steht dort ein Eintrag mit
      `<ALT_DOMAIN>`, auf `<DOMAIN>` umstellen. Das Routing tragen die
      Traefik-Labels aus dem Repo, ein vergessener UI-Eintrag hielte den alten
      Host halb am Leben.
- [ ] **Traefik → File System → `dynamic/who2be-headers.yml`** (falls nach
      RUNBOOK §Dokploy-Stack Schritt 1 angelegt): In `who2be-csp-web` →
      `connect-src` beide Hosts auf `<DOMAIN>` umstellen. Sonst blockiert die
      CSP der neuen Web-App ihre eigene API.

**Pruefen:** Die Suche nach `<ALT_DOMAIN>` im Dokploy-Environment und in
`who2be-headers.yml` findet nichts mehr, ausser einer bewusst behaltenen
Absenderadresse. In der Google-Konsole stehen beide Redirect-URIs, und die
Authorized Domain gilt als verifiziert. Die Werte im Container prueft
Schritt U3.

### U3 · Neu ausrollen (Deploy, nicht Restart)

- [ ] In Dokploy **Deploy** ausloesen. Ein *Restart* reicht nicht: Er startet
      die alten Container mit alten Labels und altem Environment. Die
      Traefik-Router und das Web-Bundle entstehen erst beim Neuerzeugen.
- [ ] Direkt danach die GitHub-Callback-URL umstellen (Schritt U2).
- [ ] Beim ersten Aufruf je Host holt Traefik das Zertifikat. Das dauert ein
      paar Sekunden, also nicht in Schleife neu laden (Let's-Encrypt-Ratelimits).

**Pruefen** (Workstation und Box):

```bash
D=<DOMAIN>
curl -fsS "https://api.$D/v1/health"                                   # → "db":"ok"
curl -fsS -o /dev/null -w 'app %{http_code}\n' "https://app.$D/"         # → 200
curl -fsS "https://supabase.$D/auth/v1/health"                         # → JSON mit "version"
curl -fsS -o /dev/null -w 'mcp %{http_code}\n' \
  "https://mcp.$D/.well-known/oauth-protected-resource/mcp"            # → 200
for s in api app supabase mcp; do
  echo | openssl s_client -connect "$s.$D:443" -servername "$s.$D" 2>/dev/null \
    | openssl x509 -noout -issuer -subject
done                                   # → issuer Let's Encrypt, subject CN = <s>.<DOMAIN>
curl -fsS "https://app.$D/config.js" | grep -E 'apiBaseUrl|mcpUrl|supabaseUrl'
                                       # → alle drei auf <DOMAIN>
# Auf der Box: der Webhook-Wert ist im Container angekommen.
docker exec "$(docker ps -q --filter label=com.docker.compose.service=api)" \
  printenv MOLLIE_WEBHOOK_URL WEB_BASE_URL   # → beide mit <DOMAIN>
```

### U4 · Supabase-Auth-URLs

Im Dokploy-Stack gibt es hier nichts mehr zu setzen: `GOTRUE_SITE_URL`,
`GOTRUE_URI_ALLOW_LIST`, `GOTRUE_JWT_ISSUER`, `API_EXTERNAL_URL` und die
Provider-Redirects kommen aus `DOMAIN`
(`deploy/dokploy/docker-compose.yml#auth`). Du pruefst nur, dass sie
angekommen sind.

- [ ] Offene Einladungen zurueckziehen und neu senden (Einstellungen →
      Mitglieder), denn ihr Mail-Link zeigt auf den alten Host.

**Pruefen:**

```bash
D=<DOMAIN>
# Der Provider-Start zeigt mit der NEUEN Callback-URL zum Provider
# (provider=google bzw. github, je nachdem, was aktiv ist):
curl -s -o /dev/null -w '%{redirect_url}\n' "https://supabase.$D/auth/v1/authorize?provider=google" \
  | grep -o 'redirect_uri=[^&]*'       # → redirect_uri=https%3A%2F%2Fsupabase.<DOMAIN>%2Fauth%2Fv1%2Fcallback
# CORS: die API erlaubt den neuen Web-Origin.
curl -s -o /dev/null -D - -X OPTIONS "https://api.$D/v1/health" \
  -H "Origin: https://app.$D" -H 'Access-Control-Request-Method: GET' \
  | grep -i '^access-control-allow-origin'   # → https://app.<DOMAIN>
```

Im Browser `https://app.<DOMAIN>` aufrufen und je aktivem Provider
anmelden. Richtig ist: Du landest nach dem Provider wieder auf
`app.<DOMAIN>`, ohne `redirect_uri_mismatch` und ohne Umweg ueber den alten
Host. Danach eine Testeinladung an eine eigene Zweitadresse schicken: Der Link
in der Mail zeigt auf `<DOMAIN>`, nicht auf `<ALT_DOMAIN>`.

### U5 · OAuth-Connectoren: neue URL, Hinweis an die Nutzer

**Was mit bestehenden Connector-Tokens passiert.** Serverseitig bleiben sie
gueltig. Der Access-Token ist ein gewoehnlicher `w2b_…`-Token, 8 h gueltig,
der Refresh-Token 30 Tage
(`apps/api/src/who2be_api/services/oauth_service.py#_ACCESS_TTL`). Beide haengen
weder am Issuer noch an der Audience: Die Resource wird nur im 60-s-Code
geprueft (`OAuthService.consent`), der Refresh prueft Client und Mitgliedschaft
(`OAuthService.exchange_refresh`), und der MCP-Server prueft den Bearer per
`GET /v1/me` (`apps/mcp/src/who2be_mcp/auth.py#Who2BeTokenVerifier`).

Trotzdem funktioniert danach **kein** bestehender Connector mehr, denn
der Client spricht weiter `mcp.<ALT_DOMAIN>` an und erneuert seinen Token bei
`api.<ALT_DOMAIN>/oauth/token`. Fuer diese Namen hat Traefik nach Schritt U3
keinen Router mehr. Der Nutzer sieht also keine Anmeldeaufforderung, sondern
einen Verbindungsfehler: eine Zertifikatswarnung oder Traefiks
`404 page not found`. Wie das aussieht, haengt vom Client ab. Claude und
ChatGPT zeigen den Connector als nicht erreichbar, Werkzeugaufrufe schlagen
fehl.

Was der Nutzer tun muss:

| Client | Schritt |
|---|---|
| Claude, ChatGPT (OAuth) | Alten Connector entfernen, neuen mit der Adresse von *Agent → Verbindung* anlegen, Consent bestaetigen. |
| Claude Code, Hermes mit `--auth oauth` | Server entfernen und mit der neuen Adresse neu hinzufuegen. |
| Claude Code, Hermes mit festem `w2b_…`-Token im Header | Nur die URL tauschen, der Token bleibt gueltig. |

Die alten OAuth-Tokens verfallen von selbst. Wer aufraeumen will, widerruft sie
unter *API-Tokens*.

- [ ] **Vorab-Hinweis** an alle aktiven Nutzer, mit Datum und Uhrzeit. Ein
      Muster:

      > Am <Datum> um <Uhrzeit> zieht Who2Be auf `app.<DOMAIN>` um. Danach
      > meldest du dich dort einmal neu an. Deine Connectoren in Claude,
      > ChatGPT oder Claude Code verbindest du bitte neu: Die neue Adresse
      > steht beim Agenten unter *Verbindung*. Deine Daten bleiben, wie sie
      > sind.
- [ ] Nach erfolgreicher Pruefung (Schritt U7) den Hinweis als „ist erledigt"
      noch einmal schicken. Das Banner aus Schritt U2 sehen nur Nutzer, die die
      neue Adresse schon kennen.

**Pruefen:**

```bash
D=<DOMAIN>
curl -fsS "https://api.$D/.well-known/oauth-authorization-server" | jq -r .issuer
                                       # → https://api.<DOMAIN>
curl -fsS "https://mcp.$D/.well-known/oauth-protected-resource/mcp" | jq -c '{resource, authorization_servers}'
                                       # → {"resource":"https://mcp.<DOMAIN>/mcp","authorization_servers":["https://api.<DOMAIN>"]}
curl -s -i -X POST "https://mcp.$D/mcp" -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}' \
  | grep -iE '^HTTP/|^www-authenticate'  # → 401, resource_metadata="https://mcp.<DOMAIN>/…"
```

Danach in Claude einen Connector mit der Adresse aus *Agent → Verbindung*
anlegen. Er muss bis zum Consent auf `app.<DOMAIN>` laufen, zurueckkehren und
die Werkzeuge listen. Zum Abschluss einen Werkzeugaufruf machen, etwa
`whoami`.

### U6 · Mollie-Webhook

Die Webhook-URL setzt Schritt U2. Neue Zahlungen und Subscriptions nehmen den
neuen Wert mit, denn er wird bei jedem Payment und bei jeder Subscription an
Mollie uebergeben (`packages/billing/src/who2be_billing/router.py#create_checkout`).
Laufende Objekte tragen dagegen ihren alten Wert selbst.

- [ ] **Laufende Subscriptions umschreiben.** Den Key nicht in die
      Shell-History tippen:

      ```bash
      read -rs MOLLIE_API_KEY; export MOLLIE_API_KEY
      NEW='https://api.<DOMAIN>/v1/billing/mollie/webhook'   # ggf. mit ?token=…
      curl -s "https://api.mollie.com/v2/subscriptions?limit=250" \
        -H "Authorization: Bearer $MOLLIE_API_KEY" \
        | jq -r '._embedded.subscriptions[] | select(.status=="active" or .status=="pending")
                 | [.customerId, .id, .webhookUrl] | @tsv' > subs.tsv
      while IFS=$'\t' read -r cst sub _; do
        curl -s -X PATCH "https://api.mollie.com/v2/customers/$cst/subscriptions/$sub" \
          -H "Authorization: Bearer $MOLLIE_API_KEY" -H 'Content-Type: application/json' \
          -d "{\"webhookUrl\":\"$NEW\"}" | jq -r '[.id, .webhookUrl] | @tsv'
      done < subs.tsv
      ```
- [ ] **Zahlungen, die vor dem Umzug offen waren**, schicken ihren Webhook an
      den alten Host. Ist eine davon nach dem Umzug bezahlt worden, loest du
      den Webhook selbst aus. Das ist gefahrlos, weil die API den Status bei
      Mollie nachliest und dem Aufruf nicht glaubt:

      ```bash
      curl -s -X POST "https://api.<DOMAIN>/v1/billing/mollie/webhook" -d id=<tr_…>   # ggf. ?token=…
      ```
- [ ] Im Mollie-Dashboard unter *Website-Profil* steht die Website, also der
      Apex. Sie bleibt.

**Pruefen:**

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST "https://api.<DOMAIN>/v1/billing/mollie/webhook"
                                       # → 422 (Route erreicht, `id` fehlt); 404 = Overlay fehlt
curl -s "https://api.mollie.com/v2/subscriptions?limit=250" -H "Authorization: Bearer $MOLLIE_API_KEY" \
  | jq -r '._embedded.subscriptions[] | select(.status=="active") | .webhookUrl' | sort -u
                                       # → nur noch die neue URL
```

Danach einen Test-Checkout ueber die Web-App wie in Phase 3 Schritt 15 machen. Mollie
leitet zurueck auf `https://app.<DOMAIN>/settings/billing`, der Tarif steht
auf Pro, und im Mollie-Dashboard zeigt die Zahlung unter *Webhook* den neuen
Host mit Status `200`.

### U7 · Abnahme

Erst wenn jede Zeile stimmt, ist der Umzug durch. Jede Pruefung steht oben im
jeweiligen Schritt.

| # | Pruefung | Erwartet | Schritt |
|---|---|---|---|
| 1 | `curl` je Subdomain (`api` Health, `app`, `supabase` Health, `mcp` PRM) | `200`, gueltiges Zertifikat je Host | U3 |
| 2 | `config.js` der Web-App | alle URLs auf `<DOMAIN>` | U3 |
| 3 | Login je aktivem Provider | landet auf `app.<DOMAIN>` | U4 |
| 4 | Testeinladung | Mail-Link auf `<DOMAIN>` | U4 |
| 5 | OAuth-Metadaten und PRM | Issuer und Resource auf `<DOMAIN>` | U5 |
| 6 | Neuer Connector in Claude | Consent, Werkzeugliste, ein Aufruf | U5 |
| 7 | Test-Checkout | Pro aktiv, Webhook `200` auf dem neuen Host | U6 |
| 8 | Uptime-Checks (RUNBOOK §Waechter-Server) auf die neuen Hosts umgestellt | gruen | — |
| 9 | Links der Website zur App | zeigen auf `app.<DOMAIN>` | — |

### U8 · Rueckweg

Der Rueckweg setzt voraus, dass die alten DNS-Records stehen (Schritt U1) und
die alten Redirect-URIs bei Google und Apple nicht geloescht sind. Er ist
symmetrisch: Connectoren, die im neuen Fenster angelegt wurden, muessen danach
wieder neu verbunden werden. Darum faellt die Entscheidung in den ersten
Stunden, vor dem „ist erledigt"-Hinweis.

- [ ] Dokploy-Environment: `DOMAIN=<ALT_DOMAIN>`,
      `MOLLIE_WEBHOOK_URL=https://api.<ALT_DOMAIN>/v1/billing/mollie/webhook`
      (ggf. mit `?token=…`), Banner leeren.
- [ ] `who2be-headers.yml` und gegebenenfalls Dokploy → Domains zurueck auf
      `<ALT_DOMAIN>`.
- [ ] Dokploy **Deploy**, danach die GitHub-Callback-URL zurueck auf
      `https://supabase.<ALT_DOMAIN>/auth/v1/callback`.
- [ ] Subscriptions, die Schritt U6 umgeschrieben hat oder die im Fenster
      entstanden sind, mit derselben Schleife auf die alte URL setzen. Bezahlte
      Zahlungen aus dem Fenster per Webhook-Aufruf gegen `api.<ALT_DOMAIN>`
      nachziehen.
- [ ] Nutzer informieren: Die alte Adresse gilt wieder.

**Pruefen:** Die Schleifen aus Schritt U3 und U5, mit
`D=<ALT_DOMAIN>`. Danach ein Login und ein bestehender, nicht neu verbundener
Connector: Er laeuft wieder, ohne neuen Consent, sofern sein Refresh-Token
juenger als 30 Tage ist.

**Aufraeumen, wenn kein Rueckweg mehr noetig ist** (fruehestens nach
14 Tagen): die alten DNS-Records und Redirect-URIs entfernen, das Banner
leeren und die TTL der neuen Records wieder anheben.

> **Hetzner/Caddy-Stack statt Dokploy:** Dort leitet sich weniger aus
> `DOMAIN` ab. In `deploy/hetzner/.env` gehoeren zusaetzlich `CORS_ORIGINS`,
> `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_MCP_URL` und
> `MOLLIE_WEBHOOK_URL` umgestellt, in `deploy/hetzner/supabase/.env` `DOMAIN`
> und `SITE_URL`. Danach beide Stacks mit `up -d`, Caddy eingeschlossen.
> Zusaetzlich gilt: Passkeys haengen dort an `GOTRUE_WEBAUTHN_RP_ID=app.${DOMAIN}`.
> Wer einen Passkey als zweiten Faktor hat, muss ihn nach dem Umzug neu
> registrieren. Die Werte mit Datei und Zeile stehen im Inventar (Abschnitt C).

---

## Was garantiert schiefgeht, und wie du es erkennst

Die beiden ersten sind keine Vermutung — sie treffen jeden, der die Liste nicht
in dieser Reihenfolge abarbeitet.

| Symptom | Ursache | Abhilfe |
|---|---|---|
| **`403` beim Override, obwohl du Admin bist** | Du hast einen API-Token (`w2b_…`) benutzt. Der Endpunkt lehnt Maschinen-Tokens **kategorisch** ab — auch wenn du in der Allowlist stehst (`packages/billing/src/who2be_billing/router.py#_require_override_operator`). | Mit dem **Web-JWT deiner `aal2`-Sitzung** wiederholen, nicht mit `$TOK`. Der Smoke fuehrt dich sonst genau in diesen Fehler. |
| **`403` beim Override, auch mit Web-JWT** | Die Allowlist ist im Container leer — `.env` nicht gesetzt oder die API nach der Aenderung nicht neu erzeugt. Das Gate ist fail-closed: leere Liste ⇒ **immer** 403. | `printenv WHO2BE_BILLING_OVERRIDE_OPERATORS` im `api`-Container (Kommando in Schritt 13). Leer ⇒ Schritt 13. Steht dort wirklich die **User**-UUID, nicht die Org- oder Workspace-Id? |
| **`403` beim Override, Allowlist steht, Web-JWT benutzt** | Die Sitzung ist nur `aal1` — TOTP beim Login nicht beantwortet oder Sitzung abgelaufen. | Neu anmelden **inklusive Code** (Schritt 12). |
| **Niemand kann sich anmelden, Fehlermeldung nichtssagend** | `JWT_SECRET` weicht zwischen den beiden `.env` ab. | Beide Dateien vergleichen (Schritt 6). |
| **`redirect_uri_mismatch` beim Provider-Login** | Redirect-URI im Portal weicht ab — Schraegstrich, `http`, oder falsche Subdomain. | Exakt `https://supabase.<DOMAIN>/auth/v1/callback` (Phase 0 Punkt 4). |
| **`provider_email_needs_verification`** | Die E-Mail-Adresse beim Provider ist nicht verifiziert. | Beim Provider verifizieren — oder SMTP einrichten. |
| **Zertifikat wird nicht ausgestellt** | DNS noch nicht aufgeloest oder Port 80 zu. | `docker compose … logs caddy` nennt den ACME-Fehler im Klartext. Nicht in Schleife neu versuchen — Let's Encrypt hat Ratelimits. |
| **`503` auf Checkout/Webhook** | `MOLLIE_API_KEY` fehlt oder ist leer. | Test-Key setzen, `api` neu erzeugen. Oder den Override-Weg (Schritt 13) nehmen. |
| **`503 Rechnungsstellung nicht konfiguriert.` beim Checkout** | `WHO2BE_INVOICE_TAX_MODE` ist im `api`-Container leer (fail closed, ADR-0061 §5). | Wert setzen (Schritt 15), `api` und `worker` neu erzeugen, mit `printenv WHO2BE_INVOICE_TAX_MODE` im Container pruefen. |
| **`409` beim Checkout** | Fuer die Organisation sind keine Rechnungsdaten gespeichert. | Rechnungsdaten im Billing-Bereich speichern (Schritt 15). |
| **Container `api` oder `worker` startet nicht, Meldung zu `invoice_tax_mode`/`invoice_price_basis`** | Tippfehler im Schalter. Erlaubt sind nur `regular`/`small_business` bzw. `net`/`gross`. | Wert korrigieren, neu erzeugen. |
| **Pro aktiv, aber keine Rechnung (`billing_invoice` bleibt `pending`)** | `last_error` nennt den Grund: `hold:tax_mode_missing` (Schalter fehlt im `worker`), `hold:profile_missing`, `hold:email_missing`, `hold:amount_mismatch`. Ohne `hold:`: Worker-Log `invoice-retry: MOLLIE_API_KEY fehlt` heisst, der Key fehlt im `worker`. | Schalter bzw. Key im `worker` setzen, Daten nachtragen; der Worker prueft zurueckgehaltene Rechnungen stuendlich erneut. |
| **`billing_invoice` auf `failed`** | 8 technische Fehlversuche, ERROR-Zeile im Worker-Log. | Abschnitt [Storno und Erstattung](#storno-und-erstattung), letzter Absatz. |
| **Compose bricht ab, bevor irgendetwas startet** | `SEAWEEDFS_S3_SECRET_KEY` fehlt (harter Guard). | Wert setzen (Schritt 6). |
| **Kein `429` im MCP-Check** | Edition ist nicht `cloud`, oder du hast mit einem Web-JWT statt einem `w2b_…`-Token gerufen. | Beide `-f`-Dateien beim Bring-up, und einen API-Token verwenden. |

---

## Was du fuer den Testlauf **nicht** brauchst

Damit die Liste nicht laenger wirkt, als sie ist:

- **Kein Apple-Provider** — zwei Anmeldewege genuegen, und im Repo gibt es
  dafuer noch keine Anleitung.
- **Keine CI/CD-Verdrahtung.** `DEPLOY_HOST`, `DEPLOY_USER`,
  `DEPLOY_SSH_KEY` und Freunde sind Komfort fuer kuenftige Rollouts; fuer den
  Testlauf reicht Compose von Hand bzw. `deploy/hetzner/scripts/deploy.sh`.
- **Kein Backup-Setup.** Die `RESTIC_*`/`BACKUP_*`-Variablen liest nur
  `--profile backup`. Vor echten Daten ist das Pflicht, fuer den Testlauf nicht.
- **Keine endgueltige Steuer-Festlegung.** Der Test-Modus erzeugt keinen
  Umsatz; fuer den Testlauf genuegt ein gesetzter Steuermodus (Schritt 15).
  Welche Schalterwerte im Echtbetrieb gelten, legst du vor dem ersten
  *zahlenden* Kunden fest — ein harter Blocker mit Vorlauf, aber nicht Teil
  dieser Liste. Offene Punkte: GoBD-Verfahrensdokumentation §6.
