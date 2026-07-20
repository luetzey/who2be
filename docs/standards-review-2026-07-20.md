# Standards-Review 2026-07-20 — Pflege-Lauf (Delta-Audit)

**Anlass:** Pflege-Lauf über die Code-Standards („Repo aufräumen, sortieren, prüfen").
**Prüfnorm:** Coding-Standards-Composite (12 Atomics) aus der AgentDB; repo-spezifische
Konkretisierung (CLAUDE.md, ADRs, `docs/standards/`, `docs/frontend/design-language.md`)
hat Vorrang. **Methode:** je Standard ein read-only Prüf-Agent (12 parallel), Security als
gespawnte Security-Fokus-Rolle; Tooling-Gates real ausgeführt (exakte CI-Kommandos),
CI-Behauptungen gegen echte Actions-Läufe verifiziert. **Vorgänger:**
[`standards-review-2026-07-08.md`](standards-review-2026-07-08.md) — offene Befunde dort
wurden auf heutigen Stand geprüft; Owner-Entscheidungen nicht neu bewertet.

## 1 Ampel-Übersicht

| # | Standard | Ampel | ❌ | ⚠ | Kernbefund |
|---|---|---|---|---|---|
| 1 | Architektur | 🟡 | 2* | 3 | ADR-0002-Schichtregel (Owner-offen) wächst weiter (23→25 Service-Module); neu: Schichtumkehr `repositories→services` |
| 2 | Deployment | 🟡 | 2 | 6 | Cloud-Deploy liefert On-Prem-Web-Bundle (Billing-UI fehlt in Cloud); MCP-Image enthält Billing-Quellcode |
| 3 | Design-Prinzipien | 🟡 | 1 | 7 | Versions-Workflow 5× nahezu wortgleich in der Service-Schicht; Repo-Teilkopien mit belegtem Bug-Kostenpunkt |
| 4 | Frontend | 🟡 | 2 | 10 | Gates lokal grün; Barrel-Export umgeht Cross-Feature-Gate; Hooks-Warning-Bestand 41→47 gewachsen |
| 5 | Warm Citrus | 🟡 | 1 | 13 | Token-Disziplin im Kern vorbildlich; 1 Brand-Regelbruch + Off-Scale-Streuung; AgentDB-Norm driftet gegen design-language.md |
| 6 | Clean-Code-Style | 🟢 | 0 | 5 | ruff/format/mypy alle Exit 0 (334 Dateien); Restbefunde nur Funktionslängen/Begründungen |
| 7 | Security | 🟡 | 1 | 2 | External-Tool-Export umgeht Read-Scope-Gate (Policy-Bypass inkl. Drafts); 2 Rate-Limit-Lücken (ADR-0044-Kette im Default unvollständig) |
| 8 | Test/QA | ⏳ | – | – | (läuft — Sektion 2.8 folgt) |
| 9 | Licensing | 🟡 | 1 | 4 | `manual_override` ist Kunden-Self-Service statt Ops-Override — Cloud-Kunde kann sich selbst Pro-Entitlement schreiben |
| 10 | OSS-Compliance | 🟢 | 0 | 3 | Beide Lizenz-Gates real grün; nur Härtung (UNKNOWN im Web-Gate), NOTICES, SBOM offen |
| 11 | Git | 🟡 | 3* | 6 | Commit-/PR-Disziplin 100 % konform; aber keine Branch-Protection + CI seit 2026-07-19 ausgefallen (Actions-Billing bestätigt) |
| 12 | Repo-Memory | 🟡 | 1 | 8 | STATE.md = 636-Zeilen-Changelog statt Snapshot (6,4× Budget); Plan-README driftet erneut |

\* enthält als „offen (Owner)" markierte Wiedervorlagen aus dem Vorgänger-Audit.

**Gesamtbild:** Kein 🔴. Die Substanz-Funde des Laufs sind drei echte Lücken in seit dem
letzten Audit neuem Code (SEC-1 Export-Gate, LIC-1 Override-Gate, DEP-1 Cloud-Web-Bundle) —
alle drei von derselben Fehlerklasse „neuer Endpunkt/Pfad vergisst ein Bestands-Gate".
Der Rest ist Drift-Management (wachsender ADR-0002-Bestand, Warning-Bestand, STATE-Format)
und Kosmetik.

## 2 Befunde je Standard

### 2.1 Architektur (ARC)

- **ARC-1 ❌ offen (Owner):** `HTTPException`/`fastapi` in 25 Service-Modulen (168 Vorkommen), u. a. `apps/api/src/who2be_api/services/version_status.py`, `services/memory_service.py:25`, `services/external_tool_service.py:15`. Regel: ADR-0002 „fastapi nur in routers/main". 23→25 seit 07-08. → Owner-Entscheidung enforce vs. amend (WP-6 alt).
- **ARC-2 ❌ offen (Owner):** Rohes SQL in 12 Service-Dateien (43 Vorkommen), u. a. `services/version_status.py:344,351,382,504,548`; neu `services/placeholders/resolvers/tool_ref.py:109`. Regel: ADR-0002 „asyncpg nur repositories/core-db".
- **ARC-3 ⚠ neu:** Bestand wächst trotz schwebender Entscheidung — `memory_service.py` (11× HTTPException), `external_tool_service.py` (10×), `tool_ref.py` (SQL), alle nach 2026-07-08 entstanden. Fix: Interims-Leitplanke „kein neues HTTPException/SQL in services/" in CLAUDE.md.
- **ARC-4 ⚠ neu:** Schichtumkehr — `repositories/versioned_repository.py:30` importiert `who2be_api.services.entity_sql`; `entity_sql` ist eine DB-nahe Utility im falschen Paket. Fix: nach `core/` verschieben + Import-Sweep.
- **ARC-5 ⚠:** `.claude/context/STATE.md:3` Kopfdatum hinkt dem Inhalt hinterher (Wiederkehr ENG-8).

Konform: modularer Monolith (ADR-0001); `models` importiert nie api/mcp; MCP ohne SQL; Billing nur dynamisch (`main.py:208`); COD-2 (SQL im Router) geschlossen; 44 ADRs lückenlos, Status gepflegt; Norm ↔ `docs/standards/coding-standards.md` §1 deckungsgleich.

### 2.2 Deployment (DEP)

- **DEP-1 ❌:** Hetzner-Cloud-Deploy baut das Web mit dem On-Prem-Bundle — `deploy/hetzner/who2be/docker-compose.yml:62-69` reicht `VITE_WHO2BE_EDITION` nicht durch, das Cloud-Overlay überschreibt `web` nicht, `apps/web/Dockerfile:27` defaultet `onprem`; `OrgSettingsPage.tsx:53` ist Compile-Time. Folge: Billing-UI fehlt in der bezahlten Cloud-Edition. Fix: Build-Arg durchreichen + im Overlay pinnen, `.env.example` + `docs/cloud-local-smoke.md` nachziehen.
- **DEP-2 ❌:** `apps/mcp/Dockerfile:20` `COPY packages packages` → Billing-Quellcode im On-Prem-MCP-Image (Bruch der ADR-0029-Garantie; das API-Dockerfile macht es richtig). Fix: `COPY packages/models packages/models`.
- **DEP-3 ⚠ offen (Owner):** On-Prem läuft als Owner mit RLS-Bypass (`core/config.py:171-177`) — begründet, aber ohne ADR. Entscheidung: `who2be_app` auch On-Prem oder Abweichung als ADR.
- **DEP-4 ⚠:** Dokploy-Stack (Traefik) ohne Security-Header/CSP (`deploy/dokploy/docker-compose.yml:126-131` u. a.) — F-12 „eine Quelle" greift dort nicht. Fix: headers-Middleware oder „nicht öffentlich"-Deklaration.
- **DEP-5 ⚠:** `core/config.py:102-104` Stale-Kommentar „Ein Build, ein Image" widerspricht ADR-0029 (= LIC-2).
- **DEP-6 ⚠:** CI prüft nur das On-Prem-Bundle-Negativ (`ci.yml:111-118`), nie das Cloud-Positiv — genau deshalb blieb DEP-1 unentdeckt. Fix: zweiter Web-Build mit `VITE_WHO2BE_EDITION=cloud` + Positiv-Assert.
- **DEP-7 ⚠ offen (Owner):** Cloud-API-Image wird auf dem Host gebaut statt aus der Registry gepullt (`docker-compose.cloud.yml:43-51`).
- **DEP-8 ⚠ minor:** `config.py:42` Dev-DB-URL als Code-Default (12-Factor III).

Konform: 12-Factor-Config; API-Billing-Isolation (Dockerfile-Stages korrekt); Web-Tree-Shaking-Mechanik intakt; Security-Header zentral im Hetzner-Caddyfile inkl. Header-Test; JSON-Logs; DB-Schema-Symmetrie + Cloud-RLS; dokumentierte Norm-Abweichungen per ADR-0029.

### 2.3 Design-Prinzipien (DSN)

- **DSN-1 ❌ (DRY):** Versions-Workflow 5× nahezu wortgleich in der Service-Schicht — `_draft_conflict` in `persona_service.py:126` / `playbook_service.py:103` / `resource_service.py:101` / `system_prompt_template_service.py:48` / `external_tool_service.py:56`; `restore`+`diff`+`_resolve_against`: `resource_service.py:389-458` ≙ `playbook_service.py:349-424`. Beim External-Tool-Aggregat (ADR-0043) erneut kopiert. Fix: generischer `VersionedAggregateService` analog zur Repo-Basis (STR-1-Muster eine Schicht hochziehen).
- **DSN-2 ⚠:** `playbook_repository.py:370-660` re-implementiert Basis-Kerne („Option B"); die Kopie erzeugte bereits den `is_managed`-Bug (Fix 2026-06-27). Fix: `AggregateTables` um Extra-Spalten-Hook erweitern, Playbook auf Basis-Kerne heben.
- **DSN-3 ⚠:** `system_prompt_template_repository.py` (409 Z.) komplett handgerollt; Nebeneffekt: Export/GDPR-Pfade decken das Aggregat nicht ab (`entity_sql.py:16-18`). Fix: fk-Override (`template_id`), migrieren; danach Owner-Frage entity_sql-Whitelist.
- **DSN-4 ⚠:** Versions-Endpoint-Blöcke 5× im Router (`personas.py:217-247` ≙ …). Fix: Router-Factory oder als Idiom dokumentieren.
- **DSN-5 ⚠ (SRP):** `workspace_repository.py` (1050 Z.) mischt Workspace-Persistenz + komplettes Builder-Content-System (`sync_managed_builder_content` 293 Z. = CODE-1). Fix: `repositories/builder_content.py` extrahieren.
- **DSN-6 ⚠ (KISS):** `apps/mcp/src/who2be_mcp/server.py` 1425 Z., 58 Tools in einer Datei. Fix: Registrierung pro Domäne.
- **DSN-7 ⚠ (YAGNI):** `core/tenancy.py:56` `current_tenant_context()` toter Export. Fix: entfernen.
- **DSN-8 ⚠:** = ARC-3 (Wachstum auf offenem Befund).

Konform: `versioned_repository` (STR-1) vorbildlich; Web-DRY (`useListData`, `client.ts`); Export-Triplikat abgeräumt; 25+ Protocols mit Fake-Repos; `tool_requirements`-SSoT + Drift-Guards; keine toten `__all__`-Exporte; keine spekulative Generik.

### 2.4 Frontend (FE)

Gates (exakt CI, lokal): `npm run lint` 0 Errors/55 Warnings · `npx tsc -b` clean · `npm run build` clean · On-Prem-Bundle-Assert grün.

- **FE-1 ❌:** `features/feedback/index.ts:2` exportiert `GiveFeedbackDialog` (Regel: „Barrel exportiert nur Pages") — importiert von 3 Detail-Pages anderer Features; das ESLint-Gate blockt nur Deep-Imports, nicht Barrels. Fix: nach `@/components/feedback/` verschieben.
- **FE-2 ❌:** `components/data/EntityIcon.tsx:63` `text-[11px]` (= WC-6). Fix: `text-xs`.
- **FE-3 ⚠:** `FeedbackOverviewPage.tsx:164` `border-l-[3px]` (= WC-5). Fix: `border-l-2`.
- **FE-4 ⚠:** `gap-5` 5× off-scale (= WC-7). Fix: `gap-4`/`gap-6`.
- **FE-5 ⚠:** `pl-9` ohne Pflicht-Kommentar (= WC-8): `AgentsPage.tsx:247`, `SubResourcePicker.tsx:296`.
- **FE-6 ⚠:** Brand-Tinte außerhalb CTA: `SubResourcePicker.tsx:317` (Icon erbt `text-brand`, = WC-4); `FeedbackOverviewPage.tsx:233` Ghost-Button per Call-Site umgefärbt. Fix: neutral bzw. `variant="link"`.
- **FE-7 ⚠:** 14 von 37 Pages ohne A11y-Test (u. a. 5 Auth-Folgeseiten) — Besserung ggü. 23, Rest offen.
- **FE-8 ⚠:** React-Hooks-Warnings 41→47 gewachsen („Bestand nicht wachsen lassen" verletzt; 37× `set-state-in-effect`). Fix: geteilter Fetch-Hook + Warning-Ratchet.
- **FE-9 ⚠:** DoD-Drift: design-language §13.10 (`npm test`, `tsc --noEmit`) und CLAUDE.md (`tsc --noEmit`) vs. CI (`test:coverage`, `tsc -b`). Fix: auf CONTRIBUTING §DoD verweisen, Kommando vereinheitlichen.
- **FE-10 ⚠:** `app/routes.tsx:18` + `:164-172` — legal-Barrel statisch und dynamisch importiert → `INEFFECTIVE_DYNAMIC_IMPORT`, Legal-Pages im Hauptchunk. Fix: Layout-Exports vom Pages-Barrel trennen.
- **FE-11 ⚠:** `features/legal/index.ts:1-2` stale i18n-Kommentar (Folge-Kandidat aus 07-08, offen).
- **FE-12 ⚠ Hinweis:** Chunks > 500 kB (`comments` 726 kB, `index` 660 kB).

Konform: alte ❌ (FEATURES-Liste dynamisch, ResourceEditor-Hebung, `text-[10px]`) verifiziert behoben; Roh-HTML-Gate dicht (inkl. `<label>`); keine Cross-Feature-Deep-Imports; keine hex/rgb im JSX; Motion tokenbasiert; Barrel-Ausnahmen (§12) eingehalten.

### 2.5 Warm Citrus (WC)

- **WC-1…3 ⚠ Norm-Drift (AgentDB, kein Repo-Fix):** Das Playbook „Design-Sprache: Warm Citrus" widerspricht der verbindlichen `design-language.md` (Schatten-Level, px-Werte/Skalen, Listen-Pattern). → Kurations-Hand-Off via `submit_feedback` (erfolgt), Playbook nachziehen.
- **WC-4 ❌:** `SubResourcePicker.tsx:317-318` Brand-Icon (§8 „Nie `text-brand`" für Icons) — deckungsgleich FE-6a.
- **WC-5…9, 12…14 ⚠:** Off-Scale-Sweep: `border-l-[3px]`, `text-[11px]`, `gap-5`/`p-5` (6 Stellen), `pl-9`-Kommentare, `text-3xl` auf Admin-Page (`FeedbackDetailPage.tsx:198`), `size-3`-Icons (14 Stellen), `ui/alert.tsx:7` `pl-7`, `min-w-[7.5rem]` ohne Kommentar, `globals.css:532` 10px-Literal.
- **WC-10 ⚠:** `ResolutionSegments.tsx:61` aktives Segment mit Brand-Fill statt neutralem Heben.
- **WC-11 ⚠:** Zwei konkurrierende Link-Stile (`text-brand`-Links vs. Button-`link`-Variante) — eine Linie festlegen.

Konform: 0 hex/rgb/oklch im JSX; `style={{}}` nur mit `var(--status-*)`; 0 `transition-all`; 25× Token-Motion; Reduced-Motion global; Brand-CTA-Singularität auf den geprüften Pages.

### 2.6 Clean-Code-Style (CODE)

Gates (exakt CI): `uv run ruff check .` ✅ · `uv run ruff format --check .` ✅ (334 Dateien) · `uv run mypy .` ✅ (strict, 0 Issues).

- **CODE-1 ⚠:** `workspace_repository.py:757` `sync_managed_builder_content` = 294 Zeilen (6× dasselbe Muster). Fix: per-Aggregat-Helper (= DSN-5).
- **CODE-2 ⚠:** `workspace_repository.py:569` `_seed_default_agents` = 186 Zeilen.
- **CODE-3 ⚠:** `SystemPromptEditor.test.tsx:193,207,215,223,261` — 5× `{} as any` mit nacktem eslint-disable ohne Begründung. Fix: ein typisierter `editorStub`.
- **CODE-4 ⚠:** `apps/web/e2e/journeys.spec.ts:11` — einziges TODO des Repos (~4 Wochen, TST-5-gebunden; Voraussetzung, um `continue-on-error` des e2e-Jobs zu entfernen).
- **CODE-5 ⚠:** Mega-Tests (`test_oauth.py:336` 220 Z., `test_builder_content_sync.py:77`, `test_purge_erasure.py:196`).

Konform: 0 blanke `except:`; 57 `type: ignore` alle mit Code; 12 `noqa` alle mit Code; Produktions-`as any` nur 4 begründete BlockNote-Grenzstellen; kein auskommentierter Code, keine Debug-Reste; Kommentar-Kultur Warum-orientiert.

### 2.7 Security (SEC)

- **SEC-1 ❌:** `routers/external_tools.py:124-138` — `export_external_tool` ruft `export_entity` ohne `require_external_tool_read` und ohne `scope` auf. Ein Agent-Token mit `external_tool_read='none'` erhält das komplette Bundle **inkl. unveröffentlichter Drafts** (Vergleich: `routers/resources.py:192`, `playbooks.py:192` übergeben `scope`). Mit Ausbaustufe C (ADR-0043) würde die Lücke kritisch. Fix: Gate + Draft-Sichtbarkeit im Handler, Parity-Test für alle 4 Export-Endpunkte.
- **SEC-2 ⚠:** `routers/memory.py:53-69` — die Memory-Reads sind die einzigen agent-gerichteten Read-Routen ohne `enforce_mcp_read_limit`; Reads triggern zudem einen DB-Write (`_bump_retrieval`). Fix: Dependency ergänzen.
- **SEC-3 ⚠:** `routers/memory.py:46-50` — `save_memory` ohne `@limiter.limit(write_limit)`; `require_write_rate` ist im Default (`write_rate_limit=None`) No-Op → die in ADR-0044 §7 zugesagte Wächter-Kette existiert im Default nicht. Fix: Limiter-Decorator (+ `memory-guard`-PUT).

Referenziert (ADR-dokumentierte Rest-Risiken, nicht neu): Injection-Regex als Vorfilter (ADR-0044), aal2-on-prem-Schalter, sessionStorage (ADR-0035), Token-Hash (ADR-0008).

Konform: Memory-Autorisierung fail-closed; Kurations-Schleuse race-fest, `MemoryHit` schmal; Wächter Bypass-fest (re.escape, Span-Überdeckung); SQL parametrisiert + doppelt gescoped; RLS symmetrisch (0065/0066); External-Tool-Writes voll gegated; keine Secrets in getrackten Dateien; kein `dangerouslySetInnerHTML`; OAuth seit 07-08 unverändert.

### 2.8 Test/QA (TST)

_(Sektion folgt — Agent läuft; wird vor Commit ergänzt.)_

### 2.9 Licensing (LIC)

- **LIC-1 ❌:** `packages/billing/src/who2be_billing/router.py:277-314` — der `manual_override`-Endpoint ist nur mit `_require_cloud` + Workspace-`admin`-Rolle des **Kunden** gegated (kein Ops-Gate, kein `require_aal2`). ADR-0028 definiert den Writer als „Cloud-**Ops**-Override". Folge: `POST …/billing/override {"plan":"pro","days":365}` = Entitlement-Self-Service, beliebig erneuerbar — das Monetarisierungsmodell ist per API umgehbar. Fix: Plattform-Operator-Gate + `require_aal2`; Mechanik-Wahl (Ops-Capability/Allowlist/interner Kanal) als Owner-Review im PR.
- **LIC-2 ⚠:** „Ein Build, ein Image"-Kommentare in `core/config.py:101-104` + `licensing/edition.py:3-5` widersprechen ADR-0029 (= DEP-5).
- **LIC-3 ⚠:** ADR-0028:58-61 beschreibt `license install` mit Persistenz; implementiert ist verify-only + Env. Fix: ADR-Nachtrag (Q2).
- **LIC-4 ⚠:** `runtime-cloud`-Docker-Target wird in CI nie gebaut (ADR-0029 „CI prüft beide Profile"). Fix: Build-only-Step.
- **LIC-5 ⚠:** `routers/entitlement.py` editionsunabhängig vs. ADR-0029 „unter Cloud-Guard". Fix: ADR-Nachtrag, kein Code-Fix.

Konform: SSoT nur via `EntitlementPort` (kein Umgehungs-Read/-Write, grep-belegt); Schreibquellen-CHECK (0043) + Audit-Journal; Ed25519 fail-closed inkl. Tamper-Test, kein Phone-Home; Webhook-HMAC konstant-zeitlich + Mollie-Pull-Kompensation; Build-Isolation testerzwungen (`test_no_billing_in_core.py`).

### 2.10 OSS-Compliance (OSS)

Scans (real, exakt CI): Python-Gate ✅ (105 Pakete, 2× MPL-2.0) · Web-Gate ✅ (191 Pakete, 6× MPL-2.0). Kein GPL/AGPL/LGPL/SSPL/UNKNOWN. Neue Deps seit 07-08 (mcp-CVE-Bump, Mollie/OAuth-Stack) alle permissiv.

- **OSS-1 ⚠:** Kein THIRD-PARTY-NOTICES-/Attribution-Artefakt für distribuierte Artefakte (MPL-2.0 §3.2, MIT/BSD/Apache-Notices). Fix: NOTICES generieren, vor Public-Switch.
- **OSS-2 ⚠:** Web-Gate-`failOn` ohne `UNKNOWN` (+ CPL/CPAL-Asymmetrie zu Python) — `apps/web/package.json:15` vs. `ci.yml:56`. Fix: angleichen.
- **OSS-3 ⚠:** SBOM (ADR-0033 WP-1.3, optional) weiter offen. Fix: CycloneDX-CI-Step.

### 2.11 Git (GIT)

Statistik: 100 Commits → 0 Conventional-Verstöße; first-parent 0 Direkt-Commits ohne PR; 64 Remote-Branches (~55 gemergt/verwaist); CI: 10/10 letzte Failures ≤6 s seit 2026-07-19, `runner_id: 0`, keine Logs; Dependabot-Runs grün → **Actions-Billing-These bestätigt**.

- **GIT-1 ❌ offen (Owner):** Keine Branch-Protection auf `main` (`"protected": false`). Fix: Required Checks + 1 Review + Force-Push-Verbot.
- **GIT-2 ❌ offen (Owner):** CI-Gate seit 2026-07-19 vollständig ausgefallen (Actions-Billing). Fix: Spending-Limit/Zahlung, dann Re-Runs.
- **GIT-3 ❌:** Merges trotz rotem CI (#328, #329) — mitigiert durch lokale DoD, aber unbelegt im PR. Fix: bis Billing-Fix DoD-Nachweis im PR (operationalisiert durch PR-Template, s. WP).
- **GIT-4 ⚠:** ~55 gemergte Remote-Branches. Fix: „Auto-delete head branches" (Owner) + Aufräumaktion.
- **GIT-5 ⚠:** Monolithische Commits (Max 42 Dateien/+3726).
- **GIT-6 ⚠ offen (Owner):** Merge-Strategie-Mix (38 Merge/12 Squash) — Setting vereinheitlichen.
- **GIT-7 ⚠:** Dependabot-Stau (#240/242/243/245 seit 06-22).
- **GIT-8 ⚠:** Kein PR-Template. Fix: Template mit DoD-Checkliste + Session-Link.
- **GIT-9 ⚠:** Keine lokalen Git-Hooks (pre-commit). Fix: ruff-check/-format-Hooks.

Konform: 100 % Conventional Commits; PR-Flow ohne Ausnahme; `ci.yml` vollständig + vorbildlich; goldene Regel bei geteilten Branches; CONTRIBUTING deckungsgleich mit CLAUDE.md; CVE-Response zeitnah.

### 2.12 Repo-Memory (MEM)

- **MEM-1 ❌:** `STATE.md` = 636 Zeilen / 44 KB Changelog („Funktioniert" mit 13× „UMGESETZT (Datum)") — Norm: Snapshot, ~100 Zeilen, „pro Run überschrieben"; Anti-Pattern wörtlich getroffen. Kostet ~10 KTokens pro Session. Fix: auf Snapshot eindampfen, Historie lebt in `.claude/plan/*`.
- **MEM-2 ⚠:** `.claude/plan/README.md` Stand 2026-07-08 — 9 Plan-Dateien vom 07-10…07-19 fehlen (Wiederkehr nach WP-4 alt). Fix: nachziehen + Pflege in den Closeout verdrahten.
- **MEM-3 ⚠:** STATE-Kopfdatum hinkt (= ARC-5).
- **MEM-4 ⚠:** `DECISIONS.md:100` — Eintrag mittig eingefügt statt append-only.
- **MEM-5 ⚠:** `DECISIONS.md` 347 Zeilen (3,5× Budget). Fix: ADR-gedeckte Einträge auf Pointer kürzen (append-only-konform als Konsolidierungs-Eintrag).
- **MEM-6 ⚠:** `PROJECT.md` ohne Pointer auf `.github/PROJECT.md` (Norm V1.1).
- **MEM-7 ⚠:** `CLAUDE.md:59` nennt den erledigten Web-Coverage-PR als offenes Beispiel — realer Blocker ist CI-Billing.
- **MEM-8 ⚠:** `plan/README.md:19` — Eintrag mit „✅ (PR #301)" steht unter „Aktiv".
- **MEM-9 ⚠:** ADR-Status-Vokabel de/en gemischt.

Konform: alle 4 Kontext-Dateien existieren + strukturkonform; Pflege wird gelebt (#327–#329 abgedeckt); CLAUDE.md „Aktueller Stand" aktuell; ADRs 0001–0044 lückenlos, keine Duplikate, kein falsches „Proposed"; alle 16 geprüften CLAUDE.md-Referenzpfade existieren.

## 3 Change-Log — Arbeitspakete (Reihenfolge = Priorität)

Priorisierung nach Playbook: CI entsperren → strukturelle Drift-Ursachen → Substanz → Kosmetik.
CI-Entsperrung ist hier ein reiner **Owner-Punkt** (Actions-Billing), daher beginnt die
Repo-Umsetzung bei der Substanz. **Owner-Entscheidungen werden nicht autonom getroffen** (§4).

| WP | Befunde | Inhalt | DoD |
|---|---|---|---|
| **WP-1** | SEC-1 | Export-Gate `external_tools`: `require_external_tool_read` + Draft-Sichtbarkeit; Repro-Test (`read='none'` → 403/404); Parity-Check aller 4 Export-Endpunkte | pytest grün inkl. neuer Tests |
| **WP-2** | SEC-2, SEC-3 | Rate-Limit-Parität: `enforce_mcp_read_limit` an beide Memory-Reads; `@limiter.limit(write_limit)` an `save_memory` + `memory-guard`-PUT; Tests | pytest grün |
| **WP-3** | LIC-1 | Override-Endpoint härten: `require_aal2` + Plattform-Operator-Gate (fail-closed); Tests. Mechanik-Wahl im PR-Review bestätigen lassen | Billing-Tests grün |
| **WP-4** | DEP-2 | MCP-Dockerfile: nur `packages/models` kopieren | Dockerfile-Diff, Build-Smoke |
| **WP-5** | DEP-1, DEP-6, LIC-4 | Hetzner-Web-Build-Arg + Cloud-Overlay-Pin; CI: Cloud-Bundle-Positiv-Assert + `runtime-cloud`-Build-Step; `.env.example`/Smoke-Doku | CI-YAML valide, Asserts lokal nachgestellt |
| **WP-6** | FE-1 | `GiveFeedbackDialog` nach `@/components/feedback/`, Barrel-Export entfernen | lint/tsc/Vitest/build grün |
| **WP-7** | FE-2…6, WC-4…10, 12…14, CODE-3 | Frontend-Kosmetik-Sweep: Off-Scale-Werte, Brand-Disziplin, `pl-9`-Kommentare, `editorStub` statt 5× `as any` | lint/tsc/Vitest/build grün |
| **WP-8** | FE-10, FE-11 | Legal-Barrel: Layout-Exports trennen (Code-Splitting), stale Kommentar löschen | build ohne `INEFFECTIVE_DYNAMIC_IMPORT` |
| **WP-9** | MEM-1…8, ARC-5, MEM-7 | Repo-Memory-Pflege: STATE→Snapshot, Plan-README-Juli-Block, PROJECT-Pointer, CLAUDE.md-Beispiel, DECISIONS-Konsolidierung | Dateien < Budget-Nähe, Links valide |
| **WP-10** | DEP-5, LIC-2, LIC-3, LIC-5 | Doku-/ADR-Hygiene: 2 Kommentare, ADR-0028/0029-Nachträge | mypy/ruff unverändert grün |
| **WP-11** | OSS-2 | Web-Lizenz-Gate härten: `UNKNOWN` + CPL/CPAL-Angleich (package.json, ci.yml, ADR-0033-Snippets) | `npm run license:check` grün |
| **WP-12** | ARC-4 | `entity_sql` von `services/` nach `core/` + Import-Sweep | pytest/mypy grün |
| **WP-13** | GIT-8 | PR-Template mit DoD-Checkliste + Session-Link-Feld | Datei vorhanden |
| **WP-14** | DSN-1…6, CODE-1/2, FE-7/8, OSS-1/3, GIT-9, TST-Reste | **Folge-Backlog (nicht dieser Lauf):** `VersionedAggregateService`, Repo-Basis-Vervollständigung, Builder-Content-Extraktion, MCP-Modularisierung, `useApiData`+Warning-Ratchet, A11y-Rest, NOTICES/SBOM, pre-commit | je eigener PR |

## 4 Owner-Entscheidungen (offen, nicht autonom entschieden)

1. **ADR-0002 enforce vs. amend** (ARC-1/2, DSN-8) — seit 07-08 offen, Bestand wächst; Interims-Leitplanke in WP-9 ergänzt.
2. **Actions-Billing** (GIT-2) — CI-Gate seit 2026-07-19 tot; ohne Fix bleiben alle CI-Runs rot.
3. **Branch-Protection + Auto-delete + Merge-Strategie** (GIT-1/4/6) — Repo-Settings.
4. **On-Prem-RLS** (DEP-3) — `who2be_app` auch On-Prem oder ADR für Owner-Bypass.
5. **Cloud-Image-Deploy** (DEP-7) — Registry-Pull statt Host-Build.
6. **LIC-1-Mechanik** — das Gate wird in WP-3 fail-closed gehärtet; die endgültige Ops-Identitäts-Mechanik bitte im PR-Review bestätigen.
7. **`coverage.all` / E2E-Gate-Härtung / WP-9 alt (CLA/AVV/Kontakt)** — unverändert aus dem Vorgänger-Audit.

## 5 Umsetzungsstand (Phase B)

_(wird nach den Umsetzungs-Wellen ergänzt)_
