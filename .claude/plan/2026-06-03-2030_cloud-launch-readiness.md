# Cloud-Launch-Readiness: erst lokal (PC), dann Hetzner

**Status:** Plan (Brainstorming abgeschlossen, Entscheidungen final) — bereit zur Verteilung
**Datum:** 2026-06-03
**Vorgänger:** Feature-Expansion (A–H) + Follow-ups (I–L) — alle auf `main`.
**Leitlinie des Users:** Die Cloud-Edition zuerst **lokal auf dem privaten PC** vollständig lauffähig & testbar machen; **erst danach** Migration zu Hetzner.

> Living Document der Coder-Methode. Notion bekommt nur einen kurzen Pointer.

---

## 1. Entscheidungs-Ledger

| # | Thema | Entscheidung |
|---|---|---|
| CL1 | Lokale Cloud-Parität | Volle Parität lokal via compose-`cloud`-Profil: **Mailpit** (fängt Mails), **Redis**, App als `who2be_app` (**RLS aktiv**), `WHO2BE_EDITION=cloud`, **Mollie Test-Modus**, GoTrue-Mailer→Mailpit + `autoconfirm=false`. |
| CL2 | Skalierung | **Single-Node, Redis-ready:** Rate-Limit-Storage pluggable (`RATE_LIMIT_STORAGE_URI`), Redis lokal dabei, in Prod erst bei Skalierung scharf. |
| CL3 | Secrets | **SOPS+age in separatem PRIVATEM Repo/Submodule** — im (evtl. öffentlichen) Haupt-Repo nur `.env.example`. Deploy entschlüsselt out-of-tree. |
| CL4 | Legal | Pflichtseiten (Impressum/AGB/Datenschutz/DPA/Cookie-Consent) als Code **scaffolden** (Platzhalter + Routing + Footer); finaler Text später (selbst/Anwalt). |
| CL5 | Reihenfolge | **Phase 1 (lokal) zuerst und vollständig**, dann Phase 4 (Hetzner). Phasen 2–3 (App-Gaps, Legal) laufen parallel zu/nach Phase 1, sind aber edition-agnostisch und lokal testbar. |

### Offene Eingaben
- **Mollie Test-API-Key** (`test_…`) für den lokalen Billing-Test — Mollie-Konto nötig.
- **Optional:** Google/GitHub OAuth-Test-Apps (localhost-Redirect) für SSO lokal; sonst reicht E-Mail/Passwort.
- **Legal-Inhalt:** Firmendaten/Anwaltstext für die gescaffoldeten Seiten (blockt nur den finalen Text, nicht die Tracks).
- **Phase 4:** Hetzner-Box + Domain/DNS + Mollie-Live-Key + SMTP-Provider-Account + age-Key/privates Secrets-Repo.

---

## 2. Phasen & Tracks

**Phase 1 — Cloud-Edition lokal lauffähig & testbar (PC) — PRIORITÄT**
- **M** Local-Cloud-Stack (compose-`cloud`-Profil + Smoke-Doku)
- **N** Rate-Limit Redis-ready (pluggable Storage)

**Phase 2 — Launch-Gaps (edition-agnostisch, lokal testbar)**
- **O** Account-/Org-Lifecycle + GDPR-Export + Downgrade-Enforcement
- **P** Mollie-Härtung (Webhook-Idempotenz/Dedupe + Dunning/Grace)
- **Q** Security-Findings (F-Phase2-01 `write_limit` + F-12 Caddy-CSP/Header)

**Phase 3 — Legal/Compliance**
- **R** Pflichtseiten-Scaffold (Impressum/AGB/Datenschutz/DPA/Cookie-Consent)

**Phase 4 — Hetzner-Migration & Prod-Hardening (NACH lokalem Test; großteils Ops/user-gated)**
- **S** Provisioning + self-hosted Supabase-Stack + Domain/TLS
- **T** Prod-Hardening (SOPS+age aus privatem Repo · realer SMTP-Provider · Redis scharf · Observability live · Backup-Restore-Drill · CI/CD-Deploy)

**Reihenfolge/Disjunktheit:** Phase 1 zuerst (M dann N — beide klein, teilen `config.py`/`.env.example`). Phase 2/3 (O,P,Q,R) danach weitgehend parallel & datei-disjunkt. Phase 4 (S,T) zuletzt. Geteilte Dateien (`docker-compose*.yml`, `config.py`, `Caddyfile`) als „last-merged rebasen" markiert.

---

## 3. Cross-Cutting-Verträge

### 3.1 Env-Matrix (dev / cloud-local / prod)
| Schalter | dev (heute) | cloud-local (Phase 1) | prod (Hetzner) |
|---|---|---|---|
| `WHO2BE_EDITION` | `onprem` | `cloud` | `cloud` |
| DB-Connection App | `DATABASE_URL` (Owner) | `APP_DATABASE_URL` (`who2be_app`, RLS aktiv) | `APP_DATABASE_URL` |
| Mailer | autoconfirm | **Mailpit** SMTP, `autoconfirm=false` | echter SMTP-Provider |
| Rate-Limit-Storage | `memory://` | `redis://redis:6379` | `redis://…` (bei Skalierung) |
| Mollie | aus | **Test-Key** | Live-Key |
| Secrets | `.env` | `.env` (lokal, gitignored) | **SOPS+age aus privatem Repo** |

### 3.2 Downgrade-Enforcement (Track O + P)
Bei Entitlement→Free mit Über-Free-Limit-Daten: **kein Datenverlust**. Bestehende Inhalte bleiben **lesbar**; neue Mutationen, die das Free-Limit überschreiten (Quota/MCP), werden mit klarem 4xx + Upgrade-Hinweis geblockt. Dunning (Track P): failed payment → **Grace-Period** (Status bleibt aktiv, Banner), erst nach Ablauf → `inactive`/Free.

### 3.3 Secrets (Track T)
SOPS+age; verschlüsselte `secrets.<env>.env` im **separaten privaten** Repo (als Submodule oder Deploy-Pull). age-Private-Key nur auf der Box / im Betreiber-Keystore, **nie** im Repo. Haupt-Repo: nur `.env.example`. Pre-commit-Gate gegen versehentliche Klartext-Secrets.

### 3.4 Mailer (Track M lokal, T prod)
GoTrue-SMTP bleibt abstrahiert (nur Env). Lokal Mailpit (`smtp://mailpit:1025`, UI :8025). Prod: Provider-SMTP — Wahl bei Phase 4, kein Code-Change nötig.

---

## 4. Handoff-Prompts

> Gemeinsamer DoD: Python `uv run ruff check . && uv run mypy . && uv run pytest -q`;
> Web `npm run lint && npx tsc --noEmit && npm test && npm run build` — alle grün,
> lokal verifiziert. Security-sensible Stellen mit `security-reviewer`. Conventional
> Commits, Draft-PR nach `main`, Branch von `main`.

### Track M — Local-Cloud-Stack (Phase 1)
```
Repo who2be. Branch feat/cloud-local-stack von main. LIES ZUERST
.claude/plan/2026-06-03-2030_cloud-launch-readiness.md §3.1 (Env-Matrix) + §1 CL1.
CLAUDE.md strikt.

Ziel: Die Cloud-Edition vollständig LOKAL fahrbar machen (volle Prod-Parität).
1. docker-compose.cloud.yml (Overlay) ODER `cloud`-Profil in docker-compose.yml mit:
   - mailpit (SMTP :1025, UI :8025), redis :6379.
   - GoTrue: GOTRUE_MAILER_AUTOCONFIRM=false, SMTP→mailpit, Mailer-URL-Paths;
     Google/GitHub External Provider optional (Env, default aus).
   - api: WHO2BE_EDITION=cloud, APP_DATABASE_URL=postgresql://who2be_app:<pw>@db/who2be,
     RATE_LIMIT_STORAGE_URI=redis://redis:6379, MOLLIE_API_KEY (test), Webhook-URL.
   - Init-Schritt, der das who2be_app-Passwort setzt (Rolle kommt aus Migration 0036).
2. .env.example: alle cloud-local-Vars dokumentiert (klar getrennt von dev-Defaults).
3. docs/cloud-local-smoke.md: Schritt-für-Schritt der bezahlten Cloud-Reise LOKAL —
   signup → Verify-Mail in Mailpit → Login → Upgrade (Mollie-Test-Checkout) →
   Pro-Entitlement → MCP-Quota bis 429 → RLS aktiv (als who2be_app). Inkl.
   Troubleshooting + Hinweis, dass Browser-Pulls auf der Workstation laufen.

DATEIEN: docker-compose*.yml, .env.example, docs/cloud-local-smoke.md,
ggf. kleiner Init-/Entrypoint-Skript für das Rollen-Passwort. KEIN App-Code-Umbau.
NICHT anfassen: Rate-Limit-Code (Track N), Billing/Auth-Logik.
```

### Track N — Rate-Limit Redis-ready (Phase 1)
```
Repo who2be. Branch feat/rate-limit-redis-ready von main. LIES §1 CL2 + §3.1.
CLAUDE.md + python-conventions strikt.

Ziel: Rate-Limit-Storage pluggable, ohne Verhalten im Default zu ändern.
1. core/config.py: RATE_LIMIT_STORAGE_URI (Default "memory://").
2. core/rate_limit.py: slowapi-Limiter mit storage_uri konfigurieren; den custom
   TokenRateLimiter (per-Token-Ceiling) bei gesetztem redis://-URI Redis-backed
   ausführen (sonst In-Memory wie bisher). Sliding-Window-Semantik beibehalten.
3. Dependency redis/limits ergänzen (apps/api/pyproject.toml). Tests: memory-Pfad
   unverändert grün + ein Test, dass die Storage-URI korrekt durchgereicht wird.

DATEIEN: core/rate_limit.py, core/config.py, apps/api/pyproject.toml, tests.
NICHT anfassen: compose (Track M), Billing/Auth.
```

### Track O — Account/Org-Lifecycle + GDPR + Downgrade (Phase 2)
```
Repo who2be. Branch feat/account-lifecycle-gdpr von main. LIES §3.2 (Downgrade).
CLAUDE.md + python/react-conventions strikt. security-reviewer ZWINGEND.

1. Account-Löschung (self) + Org-Löschung (nur owner): Soft-Delete mit 30-Tage-
   Grace (deleted_at) + Hard-Purge-Job danach; alle Daten kaskadieren sauber.
   GoTrue-User-Löschung anstoßen (Service-Key) bei Account-Delete.
2. GDPR-Datenexport: GET …/export → JSON-Bündel (Orgs/Workspaces/Personas/
   Playbooks/Resources/Agenten/Versionen des Users). Rate-limitiert.
3. Downgrade-Enforcement (§3.2): bei Free-Entitlement Mutationen über Free-Limit
   (Entity-/MCP-Quota) mit 4xx + Upgrade-Hinweis blocken; Bestand bleibt lesbar.
4. Web: Account-Seite (Export + „Konto löschen"), Org-Settings („Org löschen").

DATEIEN: neue Migration (deleted_at/grace), routers (me/organizations/neuer gdpr-
Router), services, web settings/account + org pages. NICHT anfassen: Mollie-Adapter
(Track P besitzt den Webhook/Dunning), Rate-Limit-Core.
```

### Track P — Mollie-Härtung (Phase 2)
```
Repo who2be. Branch feat/mollie-hardening von main. LIES §3.2 (Dunning).
CLAUDE.md + python-conventions strikt. security-reviewer für Webhook.

1. Webhook-Idempotenz/Dedupe: processed-events-Tabelle (provider event/payment id,
   unique) — wiederholte Pings sind no-op.
2. Dunning/Grace: failed payment → Entitlement bleibt aktiv mit grace_until (Banner-
   Signal via entitlement-Read), erst nach Ablauf → inactive/Free. Cancel am
   Periodenende statt sofort.
3. Tests: Replay-Webhook, failed→grace→expire-Übergänge.

DATEIEN: licensing/adapters/mollie.py, routers/billing.py, neue Migration
(processed_events + grace_until auf org_entitlement), tests. NICHT anfassen:
Downgrade-Enforcement-Logik (Track O), Rate-Limit.
```

### Track Q — Security-Findings F-Phase2-01 + F-12 (Phase 2)
```
Repo who2be. Branch feat/security-findings-prelaunch von main. LIES
docs/security-findings-phase-2.md §F-Phase2-01 + docs/security-findings.md §F-12.
CLAUDE.md + security-reviewer.

1. F-Phase2-01: @limiter.limit(write_limit) auf ALLE mutierenden Member-/Link-/
   Composition-/Resource-Link-Endpoints, die es heute nicht haben (Liste in §8 der
   Findings-Datei). Test je Endpoint, dass Rate-Limit greift.
2. F-12: Caddy-Security-Header/CSP-Snippet in deploy/hetzner/Caddyfile finalisieren
   (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-
   Policy + per-Subdomain CSP) — Lücken schließen, Befund in den Findings-Dateien
   auf „closed" aktualisieren.

DATEIEN: betroffene Router (nur Decorator), deploy/hetzner/Caddyfile,
docs/security-findings*.md. NICHT anfassen: Billing/Auth-Logik.
```

### Track R — Legal-Seiten-Scaffold (Phase 3)
```
Repo who2be. Branch feat/legal-pages-scaffold von main. LIES §1 CL4.
CLAUDE.md + react-conventions strikt.

Scaffolde die Pflichtseiten als Code mit strukturierten Platzhaltern:
Impressum, AGB/ToS, Datenschutzerklärung, DPA, Cookie-Consent-Banner.
Routing (public, /legal/*), Footer-Links, Consent-Banner (opt-in, kein Tracking
ohne Zustimmung). Platzhalter klar als <PLATZHALTER: …> markiert.

DATEIEN: apps/web/src/features/legal/**, Footer-Komponente, routes.tsx.
NICHT anfassen: Backend.
```

### Track S — Hetzner-Provisioning + Supabase + Domain/TLS (Phase 4)
```
Repo who2be. Branch feat/hetzner-provisioning von main. LIES deploy/hetzner/README.md
+ RUNBOOK.md + .claude/plan/2026-05-26-0942_h5-c5a-c5b-cloud-prep.md.
GROSSTEILS OPS/USER-GATED (braucht Hetzner-Box + Domain).

Self-hosted Supabase-Stack + who2be-app + web + Caddy (auto-TLS) auf der Box zum
Laufen bringen; Migrationen als Owner, App als who2be_app (RLS aktiv); WHO2BE_EDITION
=cloud. Runbook aktualisieren (Provisioning-Schritte, DNS, TLS, Health-Checks).
Was NICHT automatisierbar ist (Box anlegen, DNS), als Runbook-Schritte dokumentieren.

DATEIEN: deploy/hetzner/**, RUNBOOK.md. NICHT anfassen: App-Code.
```

### Track T — Prod-Hardening (Phase 4)
```
Repo who2be. Branch feat/prod-hardening von main. LIES §3.3 (Secrets) + §3.4 (Mailer).
security-reviewer ZWINGEND.

1. Secrets: SOPS+age — separates privates Secrets-Repo/Submodule; Deploy entschlüsselt
   auf der Box; age-Key out-of-tree. Pre-commit-Gate gegen Klartext-Secrets.
2. Realer SMTP-Provider in GoTrue-Prod-Env (Provider-Wahl beim Deploy, Sender-Domain
   SPF/DKIM/DMARC dokumentiert).
3. Redis im Prod-Compose scharf (RATE_LIMIT_STORAGE_URI=redis://…).
4. Observability live: Prometheus+Grafana (H7) hinter Basic-Auth + Alerting-Regeln.
5. Backup-Restore-Drill (H4) durchführen + dokumentieren.
6. CI/CD-Deploy (C4): Push-to-Deploy-Pipeline auf die Box.

DATEIEN: deploy/hetzner/**, .github/workflows/**, docker-compose.prod, RUNBOOK.md.
NICHT anfassen: App-Feature-Code.
```

---

## 5. Out of Scope (vorerst)
- Finaler Rechtstext (kommt vom User/Anwalt in die gescaffoldeten Seiten).
- Multi-Replica/Autoscaling-Betrieb (Redis ist vorbereitet, scharf erst bei Bedarf).
- Enterprise-SAML-SSO, MFA, Audit-Log-Export.
- Tatsächlicher Public-Flip des Repos (separates Go; FSL/Prep ist erledigt).

## 6. Notes
**2026-06-03** — V1.0: Initial-Anlage. Phasen 1–4 (lokal-zuerst), Tracks M–T.
Entscheidungen: volle Cloud-Parität lokal (Mailpit/Redis/RLS/Mollie-Test),
Single-Node Redis-ready, Secrets via SOPS+age im privaten Repo, Legal scaffolden.
