# Follow-ups: RLS-Cloud-Härtung, Mollie-Billing, User-Auth, FSL/Public-Prep

**Status:** Plan (Brainstorming abgeschlossen, Entscheidungen final) — bereit zur Verteilung
**Datum:** 2026-06-02
**Vorgänger:** `2026-06-02-1349_feature-expansion-*` (Tracks A–H, alle auf `main`).
**Methode:** 4 weitgehend datei-disjunkte Tracks (I/J/K/L), parallel verteilbar.

> Living Document der Coder-Methode. Notion bekommt nur einen kurzen Pointer.

---

## 1. Entscheidungs-Ledger

| # | Thema | Entscheidung |
|---|---|---|
| R1 | RLS-Tiefe | Eigener nicht-privilegierter App-DB-Role + per-Request `SET LOCAL app.current_tenant`/`app.current_org` an **einem** Choke-Point. `workspace_id` wird auf Version-/Link-Tabellen **denormalisiert** → einfache, schnelle Policies. App-seitige `WHERE`-Filter bleiben als Defense-in-Depth. |
| R2 | On-Prem-RLS | Identisches Schema; On-Prem-App-Role hat `BYPASSRLS` (bzw. Policies werten `current_setting('app.current_tenant', true)` als „kein Mandant = alles" nur unter `is_onprem()`). **Kein** App-SQL-Unterschied. |
| M1 | Plan-Tiers | **2 Tiers.** Free = core (1.000 MCP/Monat, 30/min). Pro = +`composite_playbooks`, `agents`, `audit_export` (100.000/Monat, 240/min). Eine recurring Mollie-Subscription; Free = ohne Abo. |
| M2 | Mollie-Modell | **Pull-after-Ping** (Mollie-spezifisch): Webhook liefert nur `id` → App fetcht via Mollie-API (`MOLLIE_API_KEY`) Status + Metadaten (`license_policy`/`mcp_monthly_quota`/`mcp_rate_per_min`) → Entitlement. Eigener Mollie-Adapter neben dem generischen HMAC-Adapter. |
| A1 | Auth-Provider | GoTrue/Supabase **behalten** (cloud + on-prem self-hosted). Kein Provider-Umbau. |
| A2 | Auth-Scope | Lücken füllen: Passwort-Reset, E-Mail-Verifikation, E-Mail/Passwort im Account ändern, Logout-all. **+ SSO/Social-Login** (Google + GitHub). First-Login-Provisioning (Personal-Org + Workspace) für neue Cloud-User sicherstellen. |
| A3 | SSO-Abgrenzung | Social-Login = Login-Methode, editionsunabhängig. Der `sso`-Feature-Code (Enterprise-SAML) im Entitlement bleibt **Future**, nicht Teil dieses Tracks. |
| L1 | Lizenz | FSL-1.1-Apache-2.0 (bereits entschieden, `…1935_license-fsl-setup`). Nur **Ausführung Phase A** + Public-**Vorbereitung**. |
| L2 | Public-Flip | **Noch nicht flippen.** GitHub-Settings/CLA/Branch-Protection/Advisories = separates explizites Go. Repo bleibt privat. |

### Geklärte Eingaben (2026-06-02)
- **Owner / Copyright:** `Yannick Lützenburg` → Copyright-Zeile `Copyright (c) 2026 Yannick Lützenburg`.
- **Commercial-Kontakt:** `luetzey@gmail.com` (bis `who2be`-Domain steht).
- **SSO-Provider:** Google + GitHub.

---

## 2. Track-Map (4 Tracks, parallel)

- **I** RLS-Cloud-Härtung (Backend/DB — invasivste, `security-reviewer` Pflicht)
- **J** Mollie-Adapter + Plan-Definition + Billing-UI
- **K** User-Auth (Reset/Verifikation/Account + SSO/Social + First-Login-Provisioning)
- **L** FSL-Lizenz + Public-Switch-Vorbereitung (kein Flip)

**Koordinations-Notizen (kleine geteilte Dateien, last-merged rebasen):**
- `core/config.py`: I (`APP_DATABASE_URL`/Role), J (`MOLLIE_*`), K (GoTrue-SSO-Env) — verschiedene Keys, triviale Merges.
- `apps/api/pyproject.toml`: J (Dependency `mollie-api-python`) + L (`license`/`authors`-Feld) — verschiedene Sektionen.
- `docker-compose.yml` / `deploy/hetzner/*`: J (`MOLLIE_*`), K (GoTrue-Mailer + OAuth-Env) — verschiedene Blöcke.

Keine harte Wellen-Reihenfolge nötig; jeder Track = eigener `feat/`-Branch + Draft-PR nach `main`.

---

## 3. Cross-Cutting-Verträge

### 3.1 RLS (Track I)
- **App-Role:** Migration legt Rolle `who2be_app` (NOSUPERUSER, NOBYPASSRLS) an + `GRANT SELECT/INSERT/UPDATE/DELETE` auf alle App-Tabellen. Migrationen laufen weiter als Owner/Superuser (`DATABASE_URL`); die App verbindet als `who2be_app` (`APP_DATABASE_URL`). On-Prem-Variante der Rolle: `BYPASSRLS`.
- **Tenant-Kontext-Choke-Point:** EIN request-scoped Pfad acquired eine Connection, setzt `SET LOCAL app.current_tenant = <workspace_id>` und `app.current_org = <org_id>` innerhalb einer Transaktion und reicht diese Connection an die Repos. Repos, die heute `pool.fetch()` direkt nutzen, werden auf den request-scoped Connection-Provider umgestellt (contextvar oder Dependency). **App-WHERE-Filter bleiben** (Defense-in-Depth).
- **Denormalisierung:** `workspace_id` (NOT NULL nach Backfill) auf `persona_version`, `playbook_version`, `resource_version`, `system_prompt_template_version`, `persona_playbook`, `playbook_resource_link`, `playbook_composition`, `resource_composition`. (`status_history` hat es bereits.)
- **Policies:** `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY tenant_isolation USING (workspace_id = current_setting('app.current_tenant')::uuid)` je workspace-Tabelle; org-Tabellen (`org_entitlement`, `mcp_usage`) analog mit `app.current_org`.
- **Verifikation:** Integrationstest, der mit gesetztem vs. fremdem `app.current_tenant` Cross-Workspace-Leak-Freiheit beweist (auch ohne App-WHERE). `security-reviewer` Pflicht.

### 3.2 Mollie (Track J)
- **Tiers (Single Source `docs/licensing/plans.md`):** Free = `{features: [], mcp_monthly_quota: 1000, mcp_rate_per_min: 30}` (== bestehendes `CLOUD_FREE_ENTITLEMENT`). Pro = `{features: ["composite_playbooks","agents","audit_export"], mcp_monthly_quota: 100000, mcp_rate_per_min: 240}`.
- **Metadaten-Konvention:** Werte liegen in der Mollie-Subscription-/Customer-Metadata (`org_id`, `license_policy`, `mcp_monthly_quota`, `mcp_rate_per_min`) — kein hartkodiertes Produkt→Feature-Mapping (Guardrail §3.6 des Vorgänger-Plans).
- **Pull-Adapter** `licensing/adapters/mollie.py`: Webhook (`POST /v1/billing/mollie/webhook`, form-encoded `id=`) → Mollie-API-Fetch (`MOLLIE_API_KEY`) → Status (`active`/`canceled`/`suspended`) + Metadaten → `EntitlementRepository.upsert(source="mollie", external_ref=<subscription_id>)`.
- **Checkout:** `POST /v1/workspaces/{ws}/billing/checkout` (admin) → erstellt Mollie-Customer + erste Subscription/Zahlung → liefert Hosted-Checkout-URL zurück. Cancel → Entitlement zurück auf Free.
- **Billing-UI:** Org-Settings-Billing-Slot zeigt aktuellen Plan + Monatsverbrauch (aus `GET …/billing/entitlement`) + Upgrade-CTA (→ Checkout-URL). On-Prem: ausgeblendet (`is_cloud()`).

### 3.3 User-Auth (Track K)
- **GoTrue bleibt** — neue Flows nutzen GoTrue-Endpoints (`/recover`, `/verify`, `updateUser`, external OAuth). Prod: `GOTRUE_MAILER_AUTOCONFIRM=false` + echter SMTP/Mail-Provider; Dev bleibt autoconfirm.
- **Reset:** Web `ResetPasswordPage` (Request → Mail → Set-Password via Recovery-Link, `next`-gehärtet).
- **Verifikation:** Sign-up sendet Confirm-Mail; unbestätigte Logins werden geführt.
- **Account-Self-Service** (`AccountPage`): Name/E-Mail ändern (E-Mail mit Re-Confirm), Passwort ändern, „Überall abmelden".
- **SSO/Social:** GoTrue External Provider **Google + GitHub** (Env: `GOTRUE_EXTERNAL_GOOGLE_*`, `GOTRUE_EXTERNAL_GITHUB_*`, Redirect-Allowlist gehärtet). Web „Mit Google/GitHub anmelden"-Buttons + Callback-Handling.
- **First-Login-Provisioning:** Neuer Cloud-User (E-Mail ODER Social) ohne Org → automatisch Personal-Org + Default-Workspace + `org_member(owner)` + `workspace_member(admin)` anlegen (analog On-Prem-Bootstrap-Service, aber pro neuem User). Idempotent. **Prüfen, ob bereits vorhanden; sonst ergänzen.**
- `security-reviewer` für OAuth-Redirects, Recovery-Token, E-Mail-Wechsel.

### 3.4 FSL/Public-Prep (Track L)
- `LICENSE.md` = unveränderter FSL-1.1-Apache-2.0-Standardtext (fsl.software) + Copyright `Copyright (c) 2026 Yannick Lützenburg`.
- `README.md` License-Sektion (1 Satz + Link + Commercial-Kontakt). `CONTRIBUTING.md` (CLA-Hinweis-Platzhalter, Branch-/Commit-Konventionen aus CLAUDE.md). `SECURITY.md` (private Advisory, 90-Tage-Disclosure).
- `license = "FSL-1.1-Apache-2.0"` + `authors` in Root-`pyproject.toml`, `apps/api`, `apps/mcp`, `packages/models`; `"license"` in `apps/web/package.json`.
- `docs/security-findings*.md` deferred Findings auf Public-Tauglichkeit reviewen (keine Exploit-Details offenlegen) — Befund dokumentieren.
- `.claude/project.json` → `.gitignore` + `.claude/project.example.json`-Template (Notion-IDs raus aus dem öffentlichen Verlauf).
- **KEIN** GitHub-Settings-Flip, **keine** CLA-Aktivierung, **keine** Branch-Protection — das ist der spätere explizite Public-Flip.

---

## 4. Handoff-Prompts

> Gemeinsamer DoD: Python `uv run ruff check . && uv run mypy . && uv run pytest -q`;
> Web `npm run lint && npx tsc --noEmit && npm test && npm run build` — alle grün,
> lokal verifiziert. Bugfix = erst reproduzierender failing Test. Conventional
> Commits, Draft-PR nach `main`, nicht direkt auf `main` pushen. Branch von `main`.

### Track I — RLS-Cloud-Härtung
```
Repo who2be. Branch feat/rls-cloud-hardening von main. LIES ZUERST
.claude/plan/2026-06-02-1819_followups-rls-mollie-auth-fsl.md §3.1 (+ §1 R1/R2).
CLAUDE.md + python-conventions strikt.

Setze Postgres-RLS als Cloud-Defense-in-Depth um (Entscheidung R1/R2):
1. Migration(en): App-Role who2be_app (NOSUPERUSER, NOBYPASSRLS) + GRANTs auf alle
   App-Tabellen. workspace_id auf die Version-/Link-Tabellen denormalisieren
   (persona_version, playbook_version, resource_version,
   system_prompt_template_version, persona_playbook, playbook_resource_link,
   playbook_composition, resource_composition) inkl. Backfill + NOT NULL.
   ENABLE RLS + CREATE POLICY tenant_isolation (workspace_id =
   current_setting('app.current_tenant')::uuid) je Tabelle; org_entitlement +
   mcp_usage analog via app.current_org. Idempotent, eindeutige Migrationsnummern
   (nächste freie ab 0035).
2. core/config.py: APP_DATABASE_URL (App-Role-Connection) neben DATABASE_URL
   (Owner, nur Migrationen).
3. core/db.py + ein request-scoped Connection-Provider: acquired Connection,
   SET LOCAL app.current_tenant=<workspace_id> + app.current_org=<org_id> in einer
   Transaktion; Repos nutzen diese Connection (contextvar oder Dependency). App-
   WHERE-Filter BLEIBEN (Defense-in-Depth). On-Prem: Role mit BYPASSRLS bzw.
   Policy-Bypass ohne gesetzten Tenant — kein App-SQL-Unterschied.
4. Integrationstest: mit fremdem app.current_tenant kein Cross-Workspace-Read,
   auch wenn der App-WHERE-Filter testweise entfällt.

security-reviewer ZWINGEND (Role-Grants, Policy-Abdeckung, Kontext-Reset bei
Connection-Release, Leak-Freiheit). DATEIEN: neue Migrationen, core/db.py,
core/config.py, neuer Tenant-Connection-Provider (z.B. core/tenancy.py), Repos
(nur Connection-Plumbing). NICHT anfassen: Billing/Auth/Lizenz.
```

### Track J — Mollie-Billing + Plan-Definition
```
Repo who2be. Branch feat/mollie-billing von main. LIES ZUERST den Plan §3.2
(+ §1 M1/M2) und den Vorgänger-Plan §3.5/§3.6 (Entitlement-SSoT, Guardrails).
CLAUDE.md + python/react-conventions strikt.

Track D hat einen generischen/Stripe-shaped HMAC-Webhook-Adapter gebaut; Mollie
braucht das PULL-Modell. Setze um:
1. docs/licensing/plans.md: 2 Tiers final (Free 1000/30, Pro [composite_playbooks,
   agents,audit_export] 100000/240) + Mollie-Metadaten-Konvention (org_id,
   license_policy, mcp_monthly_quota, mcp_rate_per_min).
2. licensing/adapters/mollie.py: POST /v1/billing/mollie/webhook (form id=) →
   Mollie-API-Fetch (MOLLIE_API_KEY) → Status + Metadaten → EntitlementRepository
   .upsert(source="mollie", external_ref=subscription_id). Cancel → Free.
3. POST /v1/workspaces/{ws}/billing/checkout (admin): Mollie-Customer + Subscription
   anlegen, Hosted-Checkout-URL zurückgeben.
4. config.py: MOLLIE_API_KEY (+ optional Webhook-Secret). apps/api/pyproject.toml:
   Dependency mollie-api-python. docker-compose/.env.example: MOLLIE_*.
5. Web Org-Settings-Billing-Slot: aktueller Plan + Monatsverbrauch (GET
   …/billing/entitlement) + Upgrade-CTA → Checkout. On-Prem ausgeblendet (is_cloud()).

security-reviewer für Webhook/Pull + API-Key-Handling. NICHT anfassen: RLS/Auth/
Lizenz. Hinweis: apps/api/pyproject.toml + config.py teilst du dir mit anderen
Tracks — bei Konflikt last-merged rebasen.
```

### Track K — User-Auth (Gaps + SSO/Social + First-Login-Provisioning)
```
Repo who2be. Branch feat/user-auth-gaps-sso von main. LIES ZUERST den Plan §3.3
(+ §1 A1/A2/A3). CLAUDE.md + react/python-conventions strikt. GoTrue BLEIBT.

Setze um:
1. Passwort-Reset: Web ResetPasswordPage (Request → GoTrue /recover → Mail →
   Recovery-Link → Set-Password), next-Param gehärtet.
2. E-Mail-Verifikation: Sign-up Confirm-Flow; Prod GOTRUE_MAILER_AUTOCONFIRM=false
   + echter Mailer (docker-compose/deploy + .env.example). Dev bleibt autoconfirm.
3. Account-Self-Service (AccountPage): Name/E-Mail ändern (E-Mail mit Re-Confirm),
   Passwort ändern, „Überall abmelden".
4. SSO/Social: GoTrue External Google + GitHub (GOTRUE_EXTERNAL_*-Env + Redirect-
   Allowlist), Web „Mit Google/GitHub anmelden"-Buttons + Callback-Handling.
5. First-Login-Provisioning: neuer Cloud-User (E-Mail ODER Social) ohne Org bekommt
   automatisch Personal-Org + Default-Workspace + org_member(owner) +
   workspace_member(admin). Idempotent. ERST PRÜFEN ob schon vorhanden; sonst
   ergänzen (analog services/bootstrap_service.py, aber pro neuem User).

security-reviewer ZWINGEND (OAuth-Redirects, Recovery-Token, E-Mail-Wechsel,
Provisioning-Pfad). NICHT anfassen: RLS/Billing/Lizenz.
```

### Track L — FSL-Lizenz + Public-Switch-Vorbereitung (KEIN Flip)
```
Repo who2be. Branch feat/fsl-license-public-prep von main. LIES ZUERST den Plan
§3.4 (+ §1 L1/L2) und .claude/plan/2026-05-27-1935_license-fsl-setup.md (Phase A)
+ 2026-05-27-2028_public-switch-github-repo.md (Phase 1-2). CLAUDE.md strikt.

Setze NUR Vorbereitung um (Repo bleibt PRIVAT, kein GitHub-Flip):
1. LICENSE.md = unveränderter FSL-1.1-Apache-2.0-Standardtext (fsl.software),
   Copyright "Copyright (c) 2026 Yannick Lützenburg".
2. README.md License-Sektion (1 Satz + Link + Commercial-Kontakt luetzey@gmail.com).
3. CONTRIBUTING.md (CLA-Hinweis-Platzhalter + Branch-/Commit-Konventionen aus CLAUDE.md).
4. SECURITY.md (private Advisory, 90-Tage-Disclosure).
5. license="FSL-1.1-Apache-2.0" + authors in Root-pyproject + apps/api + apps/mcp +
   packages/models; "license" in apps/web/package.json.
6. docs/security-findings*.md deferred Findings auf Public-Tauglichkeit reviewen,
   Befund kurz dokumentieren.
7. .claude/project.json → .gitignore + .claude/project.example.json-Template.

KEINE GitHub-Settings, KEINE CLA-Aktivierung, KEINE Branch-Protection (= späterer
Flip). NICHT anfassen: RLS/Billing/Auth-Code. Hinweis: pyproject.toml teilst du dir
mit Track J — bei Konflikt last-merged rebasen.
```

---

## 5. Out of Scope
- Tatsächlicher Public-Flip (GitHub-Settings, CLA-Aktivierung, Branch-Protection, Advisories) — separates Go (Public-Switch Phase 3–5).
- Enterprise-SAML-SSO (`sso`-Feature-Code), MFA/2FA, Auth-Audit-Log — Future.
- Mollie-Dunning/Retry/Idempotency-Key-Dedupe, mehrstufige Tiers > Pro — späterer Iterationsschritt.
- IP-Assignment / GmbH-Migration / MSA-DPA (FSL Phase C–D).

## 6. Notes
**2026-06-02** — V1.0: Initial-Anlage nach Brainstorming (4 Forks final: RLS denormalisiert + eigener Role; Mollie 2-Tier Pull-Adapter; Auth GoTrue + Gaps + Google/GitHub-SSO; FSL Phase A + Public-Prep ohne Flip).
