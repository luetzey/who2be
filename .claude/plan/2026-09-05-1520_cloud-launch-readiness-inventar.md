# Cloud-Launch-Readiness-Inventar (WP-1 von #428)

**Status:** abgeschlossen (read-only Inventar, kein Code)
**Datum:** 2026-09-05
**Vorgänger:** `.claude/plan/2026-06-03-2030_cloud-launch-readiness.md` (Juni-Bestandsaufnahme, Tracks M–T, Ledger CL1–CL5) — diese Datei schreibt ihn fort, ersetzt ihn nicht.
**Auftrag:** #434 · **Tracking:** #428

Status-Vokabular exakt drei Werte: `fertig` (im Code belegt), `fehlt` (nicht vorhanden,
Coder-Arbeit), `Owner-Schritt` (kann nur der Owner tun — Keys, Repo-Variablen, DNS,
Browser-Reise, Rechtstext). Eine `fertig`-Zeile trägt immer einen Beleg als `datei:zeile`
oder Testdatei; wo nur ein Live-Lauf den Beweis liefern kann, steht der Zusatz
**unbelegt (braucht Live-Lauf)** in der Notiz.

Tabelle nach Phase gruppiert (58 Stationen — die Gruppierung folgt der Vorgabe aus #434,
Abschnitt „Zusätzliche Grenzen").

---

## 1 · Editions-Gate und Mount

| Station | Status | Beleg | Owner | Notiz |
| --- | --- | --- | --- | --- |
| `WHO2BE_EDITION`-Schalter (`onprem`/`cloud`) | fertig | `apps/api/src/who2be_api/core/config.py:109` | Coder | Grundlage jeder Cloud-Verzweigung. |
| `is_cloud()`-Helfer | fertig | `apps/api/src/who2be_api/licensing/edition.py:13` | Coder | Einziger Einstieg für Editions-Abfragen im Kern. |
| Billing-Router optional gemountet | fertig | `apps/api/src/who2be_api/main.py:295` | Coder | `_register_billing_if_present` — On-Prem registriert die Routen physisch nicht. |
| Build-Isolation On-Prem vs. Cloud | fertig | `apps/api/Dockerfile:40`, `.github/workflows/deploy.yml:39` | Coder | `builder-cloud` zieht `packages/billing` per `uv sync --group billing`; On-Prem-Artefakt enthält das Mollie-SDK nicht (ADR-0029). |
| Web-Tree-Shaking `features/billing` | fertig | `apps/web/vite.config.ts:11` | Coder | `__CLOUD_BUILD__` aus `VITE_WHO2BE_EDITION`. |

## 2 · Mollie-Billing-Pfad

| Station | Status | Beleg | Owner | Notiz |
| --- | --- | --- | --- | --- |
| Checkout-Start (Customer + First Payment) | fertig | `packages/billing/src/who2be_billing/mollie.py:436`, `router.py:234` | Coder | Betrag korrekt als String (`mollie.py:301`), `metadata.org_id` gesetzt (`plans.py:47`). |
| Checkout-Endpunkt Erfolgspfad (HTTP 201) | fehlt | `packages/billing/tests/test_mollie_endpoint.py` deckt nur Reject-Pfade | Coder | Nur der nackte Service ist getestet, nicht der FastAPI-Roundtrip. |
| Mollie-Webhook-Endpunkt | fertig | `packages/billing/src/who2be_billing/router.py:210` | Coder | Nimmt Form-Feld `id`, ruft `service.handle_webhook`. |
| Verifikation per Pull-after-Ping | fertig | `packages/billing/src/who2be_billing/mollie.py:320` | Coder | `payments.get(payment_id)` holt den Status aktiv bei Mollie — das korrekte Modell, da klassische Mollie-Webhooks keine Signatur tragen. |
| Optionales Webhook-Query-Token | fertig | `packages/billing/src/who2be_billing/router.py:116` | Coder | `hmac.compare_digest`, zusätzliche Hürde vor dem Pull. |
| Replay-Schutz Mollie-Pfad | fertig | `packages/billing/src/who2be_billing/mollie.py:482`, `apps/api/src/who2be_api/migrations/0039_mollie_dunning_dedupe.sql:41` | Coder | Atomarer Claim `ON CONFLICT DO NOTHING`, Freigabe bei Fehler (`mollie.py:507`). |
| Replay-Schutz generischer Webhook | fehlt | `packages/billing/src/who2be_billing/router.py:149` ruft den Dedupe-Ledger nirgends | Coder | Zweiter Endpunkt `/v1/billing/webhook` (HMAC-signiert, `source="cloud"`). Geprüft nach `SECURITY.md`: heute nicht ausnutzbar, siehe Gegenprobe 3. Härtung in WP-4. |
| `org_entitlement`-Schreibpfad + Journal | fertig | `apps/api/src/who2be_api/repositories/entitlement_repository.py:61` | Coder | UPSERT + `entitlement_history` in einer Transaktion; Quellen `mollie`/`cloud`/`manual_override`. |
| Dunning/Grace bei Fehlzahlung | fertig | `packages/billing/src/who2be_billing/mollie.py:205` | Coder | `grace_until` = `expires_at`; Sperre läuft über `is_active()`, kein Zusatz-Job. |
| Kündigung am Periodenende | fertig | `packages/billing/src/who2be_billing/mollie.py:218` | Coder | Tier bis `next_payment_date`, danach Rückfall auf Free — nie voll gesperrt. |
| Statusmatrix aktiv/suspended/canceled | fertig | `packages/billing/src/who2be_billing/mollie.py:232` | Coder | Getestet in `test_mollie_adapter.py`. |
| Admin-Override-Endpunkt | fertig | `packages/billing/src/who2be_billing/router.py:337` | Coder | `require_role(admin)` + `require_aal2` + Operator-Allowlist (fail-closed), Befristung `1..365` Tage, `created_by`/`reason` auditiert. |
| Operator-Allowlist befüllt | Owner-Schritt | `packages/billing/src/who2be_billing/router.py:276` liest `WHO2BE_BILLING_OVERRIDE_OPERATORS` | Owner | Ohne echte Betreiber-UUIDs ist der Override vor Go-Live unbenutzbar (bewusst fail-closed). |
| Test: Checkout→Webhook→Entitlement→Gate | fehlt | kein Treffer für `has_feature`/`mcp_limit` in `packages/billing/tests/` | Coder | Jeder Baustein einzeln getestet, die Kette nie. Kernlücke für WP-2. |
| Test: generischer Webhook-Erfolgspfad | fehlt | `packages/billing/tests/test_webhook_endpoint.py:5` nennt ihn selbst „integration-gated" | Coder | Nur 404/400/200-ohne-Wirkung abgedeckt. |

## 3 · Durchsetzung der Nutzungsrechte

| Station | Status | Beleg | Owner | Notiz |
| --- | --- | --- | --- | --- |
| Free-Default-Entitlement (Cloud) | fertig | `apps/api/src/who2be_api/licensing/entitlement.py:126` | Coder | 1.000 Requests/Monat, 30/min, nur `core`. |
| Pro-Entitlement aus Plan-Metadaten | fertig | `packages/billing/src/who2be_billing/plans.py:74` | Coder | 100.000/Monat, 240/min, 29,00 €. Pro hebt das Limit **nicht auf**, es hebt es an. |
| Metadaten-Weg Mollie → `Entitlement` | fertig | `packages/billing/src/who2be_billing/mollie.py:176`, `plans.py:47` | Coder | Kein hartkodiertes Produkt→Feature-Mapping; der Anbieter trägt die Policy als Metadata. |
| Auflösung im Kern | fertig | `apps/api/src/who2be_api/licensing/adapters/cloud.py:26` | Coder | Fallback auf `CLOUD_FREE_ENTITLEMENT`, wenn keine Zeile existiert. |
| MCP-Request-Limit (Rate + Monat) | fertig | `apps/api/src/who2be_api/services/mcp_limit_service.py:71` | Coder | 402 ohne aktives Abo, 429 bei Rate, atomarer Check-and-Increment aufs Kontingent. |
| Verdrahtung des Request-Limits | fertig | `apps/api/src/who2be_api/routers/personas.py:116`, `playbooks.py:87`, `resources.py:73` u. a. | Coder | 12 Router-Module, 27 Endpunkte. |
| Request-Limit greift nur für API-Token | fertig | `apps/api/src/who2be_api/services/mcp_limit_service.py:75`, `core/security.py:637` | Coder | Früher Ausstieg bei Web-UI-Sessions. **Owner-Entscheidung 2026-09-05: so gewollt** — Agenten-Last ist die Kostenquelle, die UI ist Verwaltung. |
| Entity-Limit Free (50 Aggregate) | fertig | `apps/api/src/who2be_api/licensing/entitlement.py:52`, `services/entity_quota_service.py:86` | Coder | 402 beim Create; Bestand bleibt les- und editierbar. |
| Verdrahtung des Entity-Limits | fertig | `apps/api/src/who2be_api/routers/personas.py:101`, `agents.py:104`, `resources.py:96` | Coder | 6 Create-Endpunkte über 5 Aggregate. |
| Entity-Limit gilt auch für Web-UI | fertig | `apps/api/src/who2be_api/services/entity_quota_service.py:71` | Coder | Kein `is_api_token`-Check — anders als das Request-Limit. Zweites Gate, das im Browser wirkt. |
| Feature-Code `composite_playbooks` erzwungen | fehlt | `apps/api/src/who2be_api/routers/playbook_composition.py:45` ohne Entitlement-Dependency | Coder | Free kann Kompositionen anlegen. |
| Feature-Code `agents` erzwungen | fehlt | `apps/api/src/who2be_api/routers/agents.py:104` hängt nur am Entity-Limit | Coder | Kein `has_feature`-Gate. |
| Feature-Code `audit_export` erzwungen | fehlt | kein Audit-Export-Endpunkt im Repo; einziger Export `apps/api/src/who2be_api/routers/gdpr.py:30` ist ungegatet | Coder | Das beworbene Feature **existiert nicht als Funktion**. |
| Feature-Code `sso` erzwungen | fehlt | außerhalb von Planungsdokumenten nicht referenziert | Coder | Zukunftsplatzhalter. |
| `has_feature()` als Gate irgendwo | fehlt | repo-weiter Grep über `apps/api`, `apps/mcp`, `apps/web`, `packages/`: 0 Treffer | Coder | Nur Ausgabe (`routers/whoami.py:88`, `routers/entitlement.py:72`). |
| Tier-Umschaltung über Paid-Feature | fertig | `apps/api/src/who2be_api/licensing/entitlement.py:92` | Coder | `entity_limit()` prüft, ob **irgendein** Nicht-Core-Feature vorliegt — grobe Tier-Logik, keine Kontrolle der einzelnen Codes. |

## 4 · Web-Oberfläche

| Station | Status | Beleg | Owner | Notiz |
| --- | --- | --- | --- | --- |
| `BillingPanel` Zustand „aktiv" | fertig | `apps/web/src/features/billing/components/BillingPanel.tsx:69` | Coder | Zeigt Quota, Features, Rate-Limit. |
| `BillingPanel` Zustand „inaktiv" + Upgrade | fertig | `apps/web/src/features/billing/components/BillingPanel.tsx:110` | Coder | Upgrade-CTA, bei Pro deaktiviert. |
| `BillingPanel` Zustand „On-Prem" | fertig | `apps/web/src/features/billing/components/BillingPanel.tsx:57` | Coder | Rendert `null`. |
| `BillingPanel` Zustand „abgelaufen" | fehlt | Typ kennt nur `active`/`inactive` (`apps/web/src/api/types.ts:980`) | Coder | Ablauf nur indirekt über `expires_at` sichtbar. |
| `BillingPanel` Zustand „Override" | fehlt | keine Quellen-Unterscheidung im UI (`apps/web/src/api/types.ts:980`) | Coder | Mollie vs. `manual_override` ist für den Nutzer nicht erkennbar. |
| Pro-Feature-Liste im Panel | fertig | `apps/web/src/features/billing/components/BillingPanel.tsx:12` | Coder | Hartkodiertes Array, Duplikat der Doku-Tabelle. **Owner-Entscheidung 2026-09-05: auf Quota umstellen.** |
| Panel-Tests vorhanden | fertig | `apps/web/src/features/billing/components/BillingPanel.test.tsx:40` | Coder | 5 Tests: aktiv, On-Prem, inaktiv, Pro, Checkout-Redirect. |
| Panel-Tests Fehlerzweige | fehlt | `apps/web/src/features/billing/components/BillingPanel.test.tsx:40` deckt sie nicht | Coder | `notFound`, Entitlement-Ladefehler und fehlgeschlagener Checkout ungetestet. |
| i18n Billing DE/EN | fertig | `apps/web/src/features/billing/i18n.ts:1` | Coder | Bewusst separat von den zentralen Locales (Tree-Shaking, ADR-0029); Keysets identisch. |
| E2E-Journey „Upgrade auf Pro" | fehlt | kein Billing-Treffer in `apps/web/e2e/journeys.spec.ts` | Coder | Playwright fährt zudem nur Desktop Chrome (`apps/web/playwright.config.ts:23`). |

## 5 · Deploy und Betrieb

| Station | Status | Beleg | Owner | Notiz |
| --- | --- | --- | --- | --- |
| Image-Build und -Push (inkl. `api-cloud`) | fertig | `.github/workflows/deploy.yml:39` | Coder | Ziel GHCR, Tags `<sha>` und `latest`. |
| Deploy-Job vorhanden | fertig | `.github/workflows/deploy.yml:78` | Coder | `needs: build-and-push`. |
| Deploy-Job läuft nie | Owner-Schritt | `.github/workflows/deploy.yml:83` | Owner | `if: vars.DEPLOY_HOST != ''` — überspringt sich still, seit jeher. |
| Repo-Variablen für Deploy | Owner-Schritt | `.github/workflows/deploy.yml:87`, `deploy/hetzner/README.md:295` | Owner | Namen: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PROJECT_DIR`, `DEPLOY_SSH_KNOWN_HOSTS`, `WHO2BE_EDITION`, `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. |
| Repo-Secret für Deploy | Owner-Schritt | `.github/workflows/deploy.yml:101` | Owner | Name: `DEPLOY_SSH_KEY`. |
| Cloud-Deploy heute = Host-Build | fertig | `deploy/hetzner/who2be/docker-compose.cloud.yml:41`, `deploy/hetzner/scripts/deploy.sh:50` | Coder | `pull_policy: build` — die Cloud-API wird auf der Prod-Box aus dem Quellcode gebaut. |
| Cloud-Deploy per Registry-Pull | fehlt | `deploy/hetzner/README.md:267` nennt den Pull-Weg ausdrücklich als noch nicht umgestellt | Coder | **Owner-Entscheidung 2026-09-05: Registry-Pull wird Regelweg.** Das ist die Umkehrung des heutigen Zustands, nicht nur Doku. |
| Notfallpfad „Registry nicht erreichbar" | fehlt | keine Sektion in `deploy/hetzner/RUNBOOK.md:167` | Coder | Gehört als Runbook-Abschnitt nach dem Umbau, Format analog Secret-Rotation. |
| Runbook „Erste Inbetriebnahme" | fertig | `deploy/hetzner/RUNBOOK.md:167` | Coder | 9-Punkte-Checkliste vorhanden; nach dem Pull-Umbau nachzuziehen. |
| Reverse-Proxy + Security-Header | fertig | `deploy/hetzner/Caddyfile:1`, `deploy/hetzner/README.md:295` | Coder | Vier vhosts, per-Subdomain-CSP, `/v1/internal/*` blockiert. |
| Cloud-Compose lokal | fertig | `docker-compose.cloud.yml:1` | Coder | Mailpit, Redis, App-Rolle, Cloud-Overrides — volle Parität auf dem Dev-Rechner. |
| Env-Vorlage vollständig | fertig | `deploy/hetzner/.env.example:1`, `deploy/hetzner/README.md:295` | Coder | Alle nötigen Variablennamen dokumentiert. |
| Mollie-Werte gesetzt | Owner-Schritt | `deploy/hetzner/.env.example:85` | Owner | Namen `MOLLIE_API_KEY`, `MOLLIE_WEBHOOK_SECRET`, `MOLLIE_WEBHOOK_URL` — Werte leer. |
| Übrige Prod-Secrets gesetzt | Owner-Schritt | `deploy/hetzner/.env.example:15` | Owner | `JWT_SECRET`, `DATABASE_URL`, `APP_DB_PASSWORD`, `SUPABASE_SERVICE_KEY`, `POSTGRES_PASSWORD`, `RESTIC_PASSWORD` tragen `CHANGE_ME`. |
| Smoke-Skript vorhanden | fertig | `scripts/smoke.sh:26` | Coder | Sechs Checks: Health, Web-Title, `/v1/me`, MCP-Tools, Same-Origin, MCP-HTTP-401. |
| Smoke prüft Billing | fehlt | `scripts/smoke.sh:26` enthält keine Billing-Route | Coder | Nötig: Cloud antwortet auf `…/billing/entitlement`, On-Prem 404 auf `…/billing/checkout`. |
| Restore-Drill protokolliert | Owner-Schritt | `deploy/hetzner/RUNBOOK.md:704` | Owner | Protokollzeilen leer — Compliance-Nachweis vor Launch. |

## 6 · Smoke-Reise lokal (`docs/cloud-local-smoke.md`)

| Station | Status | Beleg | Owner | Notiz |
| --- | --- | --- | --- | --- |
| §0 Voraussetzungen | fertig | `docs/cloud-local-smoke.md:1` | Owner | Docker, Browser, optional Mollie-Test-Key + Tunnel. |
| §1 `.env` vorbereiten | Owner-Schritt | `docs/cloud-local-smoke.md:1` | Owner | Cloud-Sektion inkl. `VITE_WHO2BE_EDITION`. |
| §2 Cloud-Stack starten | fertig | `docker-compose.cloud.yml:1` | Owner | Overlay-Aufruf dokumentiert; unbelegt (braucht Live-Lauf). |
| §3 Signup → Verify-Mail → Login | Owner-Schritt | `docs/cloud-local-smoke.md:11` | Owner | Browser-Reise über Mailpit. |
| §3b Social-Login optional | Owner-Schritt | `docs/cloud-local-smoke.md:11` | Owner | GoTrue-Env, kein Supabase-Dashboard. |
| §4 Pro-Entitlement setzen | Owner-Schritt | `docs/cloud-local-smoke.md:11` | Owner | Variante A SQL, Variante B Mollie-Test-Checkout. |
| §5 MCP-Quota bis 429 | fertig | `apps/api/src/who2be_api/services/mcp_limit_service.py:88` | Owner | Gate im Code belegt; der Lauf selbst unbelegt (braucht Live-Lauf). |
| §6 Downgrade-Enforcement | fertig | `packages/billing/src/who2be_billing/mollie.py:218` | Owner | Rückfall auf Free belegt; 402-Nachweis unbelegt (braucht Live-Lauf). |
| §7 RLS-Nachweis (`who2be_app`) | Owner-Schritt | `docs/cloud-local-smoke.md:11` | Owner | Rolle + Workspace-Isolation prüfen. |
| §8 Abnahme | Owner-Schritt | `docs/cloud-local-smoke.md:11` | Owner | Abnahme-Tabelle mit Datum/Beleg. |
| §9 Teardown | fertig | `docker-compose.cloud.yml:1` | Owner | Rückbau inkl. Volumes. |

## 7 · Smoke-Reise Produktion (`docs/cloud-prod-smoke.md`)

| Station | Status | Beleg | Owner | Notiz |
| --- | --- | --- | --- | --- |
| §0 Konventionen und Zugriff | fertig | `docs/cloud-prod-smoke.md:17` | Owner | Doku nennt Shell-User und Projektverzeichnis. |
| §1 Stack-Gesundheit | fertig | `scripts/smoke.sh:27` | Owner | `/v1/health` automatisiert; Cloud-Schalter im Container unbelegt (braucht Live-Lauf). |
| §2 Signup → echte Inbox → Login | Owner-Schritt | `docs/cloud-prod-smoke.md:17` | Owner | Browser + echtes SMTP-Postfach. |
| §3 IDs ermitteln | Owner-Schritt | `docs/cloud-prod-smoke.md:17` | Owner | Admin-Token, Org-ID, Workspace-ID. |
| §4 Pro-Entitlement setzen | Owner-Schritt | `packages/billing/src/who2be_billing/router.py:337` | Owner | Override-Endpunkt oder Mollie-Test-Checkout. |
| §5 MCP-Quota bis 429 | Owner-Schritt | `docs/cloud-prod-smoke.md:17` | Owner | 240/min gegen Prod. |
| §6 Downgrade auf 402 | Owner-Schritt | `docs/cloud-prod-smoke.md:17` | Owner | Entitlement-Zeile löschen, 402 prüfen. |
| §7 RLS-Nachweis | Owner-Schritt | `docs/cloud-prod-smoke.md:17` | Owner | Nicht-privilegierte DB-Rolle in Prod. |
| §8 Header-/Hardening-Check | fertig | `deploy/hetzner/Caddyfile:1`, `docs/cloud-prod-smoke.md:17` | Owner | Skript `test_headers.sh` vorhanden; Lauf unbelegt (braucht Live-Lauf). |
| §9 Abnahme + Restore-Drill | Owner-Schritt | `deploy/hetzner/RUNBOOK.md:704` | Owner | Protokoll noch leer. |

## 8 · Compliance (kein Rechtsrat)

Reine Bestandsaufnahme der Artefakte. Keine juristische Bewertung, keine Empfehlung —
Inhalte sind Sache des Betreibers bzw. einer anwaltlichen Prüfung (Ledger CL4).

| Station | Status | Beleg | Owner | Notiz |
| --- | --- | --- | --- | --- |
| Route Impressum | fertig | `apps/web/src/app/routes.tsx:306` | Owner | Struktur vorhanden, Text ist Platzhalter. |
| Route AGB | fertig | `apps/web/src/app/routes.tsx:306` | Owner | Platzhalter laut `apps/web/src/features/legal/pages/TermsPage.tsx:8`. |
| Route Datenschutzerklärung | fertig | `apps/web/src/app/routes.tsx:306` | Owner | Text ausstehend. |
| Route DPA/AVV | fertig | `apps/web/src/app/routes.tsx:306` | Owner | Text ausstehend. |
| Widerrufsbelehrung | fertig | `apps/web/src/app/routes.tsx:306` | Owner | Keine eigene Seite, Klausel innerhalb der AGB. |
| Cookie-Consent-Banner | fertig | `apps/web/src/features/legal/components/CookieConsentBanner.tsx:1` | Owner | Opt-in, kein Tracking vor Entscheidung. |
| Rechnungsangaben / Rechnungs-PDF | fehlt | kein Rechnungs-Artefakt im Repo | Owner | Von #428 ausdrücklich als Out of Scope geführt (eigenes Compliance-Thema). |
| DSGVO-Datenexport | fertig | `apps/api/src/who2be_api/routers/gdpr.py:30` | Coder | Art.-20-Export vorhanden, für alle Tarife offen. |
| Finaler Rechtstext | Owner-Schritt | `apps/web/src/features/legal/pages/TermsPage.tsx:8` | Owner | Vor Launch mit Endkunden nötig. |

---

## Gegenprobe — was gegen Launch-Bereitschaft spricht

Fünf Punkte, jeder belegt. Sie sind der Grund, warum „der Code ist fertig" die falsche
Zusammenfassung wäre.

1. **Der Cloud-Deploy-Weg existiert nicht in der beschlossenen Form.** Die Entscheidung
   vom 2026-09-05 lautet Registry-Pull als Regelweg. Heute baut die Prod-Box aus dem
   Quellcode (`deploy/hetzner/who2be/docker-compose.cloud.yml:41`, `pull_policy: build`);
   Registry-Pull ist für die Cloud-API **überhaupt nicht implementiert**
   (`deploy/hetzner/README.md:267`). Das ist Umbauarbeit an Overlay und `deploy.sh`,
   nicht der Runbook-Abschnitt, den die Entscheidung erwarten ließ.
2. **Der bezahlte Pfad ist nie als Kette getestet.** Kein Test verbindet Checkout,
   Webhook, `org_entitlement` und ein wirksames Gate; jeder Baustein ist für sich
   geprüft. Damit ist nirgends belegt, dass ein bezahltes Abo tatsächlich höhere
   Limits freischaltet.
3. **Ein zweiter Schreibpfad ohne Replay-Schutz.** `/v1/billing/webhook`
   (`packages/billing/src/who2be_billing/router.py:149`) schreibt Entitlements nach
   HMAC-Prüfung, ohne den Dedupe-Ledger zu befragen, den der Mollie-Pfad nutzt
   (`mollie.py:482`). Die Prüfung nach `SECURITY.md` ist erfolgt und ergibt: **heute nicht
   ausnutzbar.** Es gibt keinen Anbieter, der auf diesen Pfad sendet — das Repo hängt allein
   an `mollie-api-python`, und Mollie signiert nicht —, und ohne gesetztes
   `billing_webhook_secret` (Default leer, `apps/api/src/who2be_api/core/config.py:191`)
   beantwortet der Endpunkt jede Anfrage mit 400. Es bleibt eine Härtungsaufgabe für den
   Tag, an dem ein signierender Anbieter dazukommt; die Maßnahmen stehen in WP-4.
4. **Das Verkaufsversprechen deckt sich nicht mit dem Verhalten.** `docs/licensing/plans.md`
   und das Panel bewerben `composite_playbooks`, `agents` und `audit_export` als
   Pro-Leistungen. Keiner der drei Codes wird erzwungen, und für `audit_export` existiert
   nicht einmal ein Endpunkt (`apps/api/src/who2be_api/routers/gdpr.py:30` ist der einzige
   Export und für alle offen).
5. **Der Deploy-Job hat sich noch nie ausgeführt.** `.github/workflows/deploy.yml:83`
   überspringt ihn, solange `DEPLOY_HOST` fehlt. Es gibt damit keinen einzigen Lauf, gegen
   den sich das Runbook je bewährt hätte.

## Vorschlag: Zuschnitt WP-2 bis WP-5

Kein Issue wird hier angelegt (Scope von #434). Der Vorschlag ordnet die `fehlt`-Zeilen.

- **WP-2 Tarif-Wahrheit herstellen** (`size/S`, Web + Doku): `docs/licensing/plans.md` und
  `BillingPanel.tsx:12` auf das Quota-Modell umstellen — Requests/Monat, Rate/Minute,
  Entity-Limit statt Feature-Codes. Die Codes bleiben technisch im Entitlement (ADR-0028,
  On-Prem-Lizenzen), verschwinden aus dem Verkaufsversprechen. Voraussetzung für ehrliche
  UI vor dem Launch.
- **WP-3 Registry-Pull als Regelweg** (`size/M`, Deploy): Hetzner-Overlay und
  `deploy/hetzner/scripts/deploy.sh` auf Pull von `ghcr.io/…/who2be-api-cloud:<sha>`
  umstellen, Host-Build als Notfallpfad ins Runbook, DECISIONS-Eintrag. **Blockiert WP-5.**
- **WP-4 Cloud-Pfad testen und härten** (`size/M`, API + Web): Integrationstest über die
  ganze Kette; `scripts/smoke.sh` um den Billing-Check erweitern; die drei fehlenden
  `BillingPanel`-Testzweige; E2E-Journey „Upgrade auf Pro". Dazu die Härtung des generischen
  Webhook-Pfads aus der Sicherheitsprüfung, nach Priorität: eine Ablauffrist für Grant-Events
  erzwingen, statt `expires_at=None` zu übernehmen (`webhook.py:211`); den Dedupe-Ledger auch
  hier aufrufen (`router.py:167`); das Signatur-Zeitfenster schema-unabhängig prüfen, nicht
  nur im Stripe-Zweig (`webhook.py:71`); den Upsert monoton machen, damit ein älteres Event
  keinen neueren Stand überschreibt (`entitlement_repository.py:91`); den Router nur mounten,
  wenn ein Secret gesetzt ist (`packages/billing/src/who2be_billing/__init__.py:29`).
- **WP-5 Deploy-Verifikation** (`size/S` Coder-Anteil, Rest Owner): Repo-Variablen und
  Secrets setzen, `deploy.yml` einmal real laufen lassen, Runbook gegen die Realität
  abgleichen. Setzt #429 (Coming-soon-Modus) und WP-3 voraus; schließt #341 WP-10.
- **WP-6 Launch** (Owner): Live-Keys, Testkauf mit Erstattung, Webhook-Log, Smoke gegen
  Prod, Monitoring für Webhook-Fehler, Registrierung freigeben.

Nicht einsortiert, weil außerhalb von #428: Rechnungs-PDF/E-Rechnung (eigenes
Compliance-Thema), finale Rechtstexte (Owner), Playwright-Mehrbrowser-Ausbau (#431).

## Owner-Entscheidungen vom 2026-09-05

Beide Weichen aus dem `needs-decision`-Kommentar auf #428 sind beantwortet; sie gehören
zusätzlich als DECISIONS-Eintrag ins Repo.

- **Gating-Modell:** Quota statt Feature-Gates. Das Request-Limit bleibt auf API-Token
  beschränkt (`apps/api/src/who2be_api/services/mcp_limit_service.py:75`), weil die
  Agenten-Last die Kostenquelle ist. `plans.md` und das Panel werden auf das Quota-Modell
  umgestellt (WP-2); die Feature-Codes bleiben als technisches Konstrukt bestehen.
- **Cloud-Image-Deploy:** Registry-Pull als Regelweg, Host-Build als dokumentierter
  Notfallpfad im Runbook (Variante C zu `docs/standards-review-2026-07-20.md` §4 Nr. 5).
  Aufwand höher als bei der Entscheidung angenommen — siehe Gegenprobe Punkt 1.
