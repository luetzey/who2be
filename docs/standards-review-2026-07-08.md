# Standards-Review 2026-07-08

Repo-weites Audit gegen die sechs Engineering-Standards aus
[`docs/standards/`](standards/), durchgeführt von sechs parallelen
Prüf-Agenten (je Standard einer; Security über den Subagent
`security-reviewer`). Jeder Agent hat zuerst seinen Standard plus die
repo-spezifischen Quellen (CLAUDE.md, ADRs, Skills, Compliance-Docs) gelesen
und dann read-only mit belegten Fundstellen geprüft. Tooling-Gates wurden
real ausgeführt (ruff, mypy strict, tsc, ESLint, Lizenz-Gates); die
CI-Befunde sind gegen den echten Run #644 auf `main` verifiziert.

**Gesamtbild:** Substanz und Mikro-Ebene sind stark — alle lokalen
Tooling-Gates grün, Security ohne offenen Verstoß, Lizenz-Hygiene
vorbildlich, Testpyramide gesund. Die Schulden liegen fast durchgängig in
**Drift**: Doku/Status-Metadaten hinken der Realität 4–5 Wochen hinterher,
das Web-Coverage-Gate ist seit 2026-07-01 auf `main` rot (und maskiert drei
weitere Gates), Compliance-Dokumente und DSGVO-Purge kennen die neuen
personenbezogenen Tabellen nicht, und die ADR-0002-Schichtregel wird vom
Code real nicht mehr eingehalten.

| Standard | Ampel | ❌ | ⚠ | Kernbefund |
|---|---|---|---|---|
| Security | 🟢 | 0 | 3 | Keine Verstöße; nur dokumentiert-akzeptierte Rest-Risiken (ADR-0008/0035). TODO 1–3 + F-12 verifiziert geschlossen. |
| Coding | 🟡 | 3 | 6 | Tooling grün; ADR-0002-Schichtregel (fastapi/asyncpg-Grenzen) systematisch verletzt. |
| Testing | 🔴 | 4 | 8 | `main`-CI rot: Branch-Coverage 69,52 % < 79 % (exakt 241 Branches); DoD-Drift als Root-Cause; MCP-Paritätstest fehlt trotz „umgesetzt". |
| Frontend | 🟡 | 3 | 7 | ESLint-`FEATURES`-Liste verrottet → 7/11 Features ohne Cross-Feature-Gate, erster Verstoß durchgerutscht; A11y-Testlücke 23/32 Pages. |
| Compliance | 🟡 | 2 | 4 | DSGVO-Purge deckt `agent_feedback`/`usage_event`/`oauth_*` nicht ab; VVT stale gegenüber Schema 0062. |
| Engineering-Methode | 🟡 | 3 | 8 | Plan-first/ADR-Kultur vorbildlich gelebt; Document-Phase driftet (CLAUDE.md-Stand, Plan-README, ADR-Nummern/-Status). |

---

## 1. Befunde je Standard

### 1.1 Security-Standards — 🟢 konform

Verifiziert konform: parametrisiertes SQL (Identifier nur über Whitelists),
`require_role`/`require_capability` auf allen Mutationen, JWT-Validierung
(aud/iss/exp + Rollen-Whitelist), Workspace-Pinning fail-closed + RLS als
Zweitverteidigung, MCP als dünner Adapter ohne eigene Autorisierung,
Security-Header/CSP zentral im Caddyfile (F-12 geschlossen), kein
`dangerouslySetInnerHTML`, Open-Redirect-Schutz (`sanitize-next.ts`), keine
Secrets im Repo, `/docs` default-aus. Die im Backlog als offen geführten
Posten **TODO 1–3 und F-12 sind im Code gegengeprüft geschlossen**.

Rest-Risiken (alle bewusst/per ADR akzeptiert):

- ⚠ **SEC-1** `require_aal2` lässt On-Prem bei *fehlendem* `aal`-Claim durch
  (`apps/api/src/who2be_api/core/security.py:204-212`) — fail-open-Zweig
  ohne Sichtbarkeit. → Warn-Log/Metric + optionaler Config-Schalter
  `require_mfa_onprem`.
- ⚠ **SEC-2** Supabase-Session im `sessionStorage`
  (`apps/web/src/lib/supabase.ts:13-33`) — per ADR-0035 gedeckte Ausnahme;
  Re-Visit-Trigger (Auth-BFF → httpOnly-Cookies) bleibt bestehen.
- ⚠ **SEC-3** Token-Hash-Lookup ohne Constant-Time-Vergleich
  (`token_repository.py`, F-04) — per ADR-0008 akzeptiert, Re-Eval-Trigger
  über Metric beobachten.

### 1.2 Coding-Standards — 🟡

Konform: ruff/mypy strict (302 Dateien)/tsc/ESLint alle grün, kein blankes
`except:`, 25+ Repository-Protocols mit Fake-Repos in Unit-Tests, geteilte
Pydantic-Models als SSoT, Migrationen fortlaufend (ADR-0003), MCP-Tools
dünn, TS strict.

- ❌ **COD-1** Raw SQL + asyncpg-Pool direkt in ~10 Services statt hinter
  Repository-Protocols (ADR-0002): `services/version_status.py:314-529`,
  `bootstrap_service.py`, `oauth_service.py`, `gdpr_export_service.py`,
  `entity_export_service.py`, `entity_quota_service.py`, `token_service.py`,
  `mcp_limit_service.py`, `services/entity_sql.py`, Placeholder-Resolver.
- ❌ **COD-2** SQL im Router: `routers/entitlement.py:58` und
  `routers/whoami.py:31-42`, inkl. copy-gepastetem `_resolve_org_id`.
- ❌ **COD-3** `fastapi`-Import (direkte `HTTPException`) in 23
  Service-Modulen — ADR-0002 sagt „fastapi nur in routers/main".
- ⚠ **COD-4** Export-Endpoint 3× copy-gepastet
  (`routers/personas.py:145-180`, `playbooks.py:163-199`,
  `resources.py:~150-190`).
- ⚠ **COD-5** `-> Any` an der API-Grenze (die drei Export-Endpoints).
- ⚠ **COD-6** 4× `as any` im Web ohne Begründungstext
  (BlockNote-Editor-Stellen).
- ⚠ **COD-7** ~32× `react-hooks/set-state-in-effect`-Warnings durch
  N-fach kopiertes fetch-in-useEffect-Muster in den Daten-Hooks.
- ⚠ **COD-8** `text-[10px]` in `PersonaEditorForm.tsx:62` (= FE-3).
- ⚠ **COD-9** `assert` als Laufzeit-Validierung in `routers/whoami.py:41`.

**Kernentscheidung:** ADR-0002 entweder durchsetzen (Domain-Exceptions +
zentraler Handler, SQL in Repos) oder per Amendment ehrlich an die gelebte
Architektur anpassen — aktuell erzählen Doku und Code zwei verschiedene
Architekturen.

### 1.3 Testing-Standards — 🔴

Konform: gesunde Pyramide (955 Python-Tests, 79 % unit-schnell; 450
Vitest; dünne E2E-Spitze), DB-Skip-Guard (`WHO2BE_REQUIRE_DB=1` +
`--strict-markers`), RBAC-/Auth-/Transition-Pfade stark getestet, 2 von 3
Contract-Nähten vorhanden, Coverage-Ratchets konfiguriert.

- ❌ **TST-1** `main`-CI seit 2026-07-01 rot: Branch-Coverage **69,52 %
  (1766/2540) < 79 %** — exakt 241 fehlende Branches (Run #644).
  Größte Posten: `api/client.ts` (758 Zeilen vs. 95 Test-Zeilen),
  `AccountPage`, `LoginPage`, `ResourceDetailPage`, `OAuthConsentPage`,
  `PlaybookDetailPage`.
- ❌ **TST-2** Folgeschaden: A11y-, Build- und Billing-Bundle-Gate werden
  auf `main` seit ≥ 1 Woche geskippt (hängen hinter dem roten Coverage-Step).
- ❌ **TST-3** DoD-Drift als Root-Cause: CONTRIBUTING/CLAUDE.md nennen
  `npm test` (ohne Coverage) bzw. `pytest -q` (ohne `--cov-fail-under=85`),
  CI fährt die Gates.
- ❌ **TST-4** REST↔MCP-Paritätstest fehlt, obwohl ADR-0032 ihn beschließt
  und der Plan als „✅ umgesetzt" geflippt ist; `contract`-Marker nie
  registriert.
- ⚠ **TST-5** Alle 4 E2E-Kern-Journeys sind `test.fixme`
  (`apps/web/e2e/journeys.spec.ts:18-35`) — der grüne e2e-Job prüft fast
  nichts Authentifiziertes.
- ⚠ **TST-6** e2e-`continue-on-error: true` obwohl die
  Soft-Gate-Bedingung (instabile CI-Infra) entfallen ist.
- ⚠ **TST-7** Ganze Feature-Pages ohne Unit-Test: system-prompts (4 Pages),
  AgentsPage/AgentDetailPage, legal-Pages.
- ⚠ **TST-8** Coverage ohne `all: true` — komplett ungetestete Module
  drücken die Metrik nicht (Ratchet blind für neue Module).
- ⚠ **TST-9** A11y-Testlücke: 16 axe-Dateien vs. 32 Pages (= FE-8).
- ⚠ **TST-10** 55 Test-Dateien mit Inline-`_db_reachable`-Boilerplate
  (ADR-0032 wollte inkrementelle Migration; Bestand wächst).
- ⚠ **TST-11** `apps/api/tests/qa_run_personas_playbooks.py` matcht das
  pytest-Pattern nicht → wird nie collectet.
- ⚠ **TST-12** Python-DoD lokal ohne Coverage-Floor (gleiche
  Drift-Mechanik wie im Web möglich).

### 1.4 Frontend-Standards — 🟡

Konform: Single-Source-Tokens (nur `globals.css`, OKLCH, kein
`tailwind.config.*`), keine hex/rgb-Literale im JSX, rohes-HTML-Gate dicht,
Forms durchgängig react-hook-form+zod+shadcn, Motion sauber,
Security-Header nur im Caddyfile, `npm run lint` 0 Errors.

- ❌ **FE-1** Cross-Feature-Deep-Import
  `features/personas/components/PersonaModesEditor.tsx:16` →
  `@/features/resources/components/ResourceEditor`.
- ❌ **FE-2** ESLint-`FEATURES`-Liste veraltet
  (`apps/web/eslint.config.js:14`): 5 Einträge (inkl. nicht mehr
  existentem `tokens`) vs. 11 reale Features — `agents`, `billing`,
  `feedback`, `legal`, `resources`, `settings`, `system-prompts` sind ohne
  Import-Gate.
- ❌ **FE-3** `text-[10px]` + Off-Scale-Spacing in
  `PersonaEditorForm.tsx:62`.
- ⚠ **FE-4** Feature-Barrels exportieren mehr als Pages (billing, legal,
  settings).
- ⚠ **FE-5** Routing importiert an Barrels vorbei (`app/routes.tsx:18-19`).
- ⚠ **FE-6** Icons in Brand-Farbe entgegen design-language §8
  (`OrgSettingsPage.tsx:156`, `ManagedNotice.tsx:28`).
- ⚠ **FE-7** Off-Scale-Spacing (`mt-10`, `p-5`, `pl-9`); zudem
  Widerspruch design-language §4.1 ↔ §10.2 (`py-10`-Beispiel).
- ⚠ **FE-8** A11y-Tests fehlen für 23 von 32 Pages (u. a. komplette
  Features agents, system-prompts, auth).
- ⚠ **FE-9** 41 React-Compiler-Warnings (bewusst `warn`, Bestand wächst).
- ⚠ **FE-10** Doku-Drift in design-language.md (referenziert entferntes
  `tokens`-Feature/`SettingsTokensPage`; „bis D2/D5"-Marker abgelaufen).

### 1.5 Compliance-Standards — 🟡

Konform: LICENSE.md (FSL-1.1) konsistent referenziert, OSS-Lizenz-Gate
fail-closed in CI und **heute empirisch grün** (107 Python-Pakete ohne
GPL/AGPL/LGPL/UNKNOWN; Web-Gate exit 0; einziges Copyleft MPL-2.0 = per
Policy erlaubt), keine Secrets im Repo, Audit-Journale (ADR-0031),
Editions-Trennung (ADR-0029) ohne statischen Billing-Import,
Pflichtdokumente mit Disclaimern vorhanden, SECURITY.md mit Coordinated
Disclosure.

- ❌ **CMP-1** `purge_account_data()`
  (`repositories/account_repository.py:172-203`) anonymisiert
  `agent_feedback.actor_id`, `usage_event.actor_id` (Migration 0053) und
  `oauth_authorization_code.user_id` (0049) **nicht**; für konsumierte/
  abgelaufene `oauth_*`-Rows existiert kein Cleanup (kein `DELETE FROM
  oauth…` im Code). Art.-17-/Datenminimierungs-Lücke.
- ❌ **CMP-2** VVT (`docs/compliance/vvt.md`, Stand 2026-06-05) kennt
  weder OAuth-Connector noch Usage/Feedback-Events — Schema läuft bis 0062;
  die Pflege-Pflicht aus `docs/compliance/README.md` ist verletzt.
- ⚠ **CMP-3** C5-Mapping führt Admin-MFA als „offen", obwohl
  `require_aal2` implementiert ist.
- ⚠ **CMP-4** CLA nur Platzhalter (`CONTRIBUTING.md:6-17`) — Blocker vor
  Freischaltung externer Beiträge (FSL-Relicensing braucht Rechte an
  Fremdbeiträgen).
- ⚠ **CMP-5** Betreiber-/AVV-Platzhalter in VVT/Retention/Legal-Checkliste
  offen (bewusst markiert; Launch-Blocker, kein Repo-Verstoß).
- ⚠ **CMP-6** Private Gmail-Adresse als offizieller Kontakt in README/
  SECURITY.md/`pyproject.toml`-authors — vor Public-Switch projektbezogene
  Adresse erwägen.

### 1.6 Engineering-Methode — 🟡

Konform: Plan-first gelebt (97 Plan-Dateien, jede STATE-Einheit verlinkt
ihren Plan), 41 ADRs mit gepflegten Supersedes, Conventional Commits (25/25
geprüft), Bugfix-Regel „erst reproduzierender Test" belegt, Verify mit
konkreten Zahlen, **keine toten Links** in CLAUDE.md/AGENTS.md/standards.

- ❌ **ENG-1** CLAUDE.md „Aktueller Stand" endet bei ADR-0032 (2026-06-05)
  und behauptet „kein aktiver Plan" — Realität: ADR-0033–0040, OAuth-MCP,
  Feedback-Flywheel, Builder-Lock, MFA, MCP-Discovery-Fixes. Die jede
  Session geladene Datei lenkt aktiv falsch.
- ❌ **ENG-2** ADR-Nummer **0032 doppelt vergeben**
  (`0032-single-element-delete-export.md` + `0032-test-strategie-pyramide.md`)
  — Querverweise mehrdeutig.
- ❌ **ENG-3** `.claude/plan/README.md` (selbsterklärt autoritative
  Status-Übersicht) endet bei Phase 3; ~45 Pläne seit 2026-05-30 fehlen.
- ⚠ **ENG-4** ADR-Status 0037/0038/0040 stehen auf „Proposed", obwohl
  implementiert + gemerged.
- ⚠ **ENG-5** `_done.md`-Rename-Regel der Methode wird von 0/97 Plänen
  befolgt — Standard und gelebte Praxis (STATE.md als Reconciliation-Ort)
  widersprechen sich.
- ⚠ **ENG-6** DoD-Definition inkonsistent über 4 Quellen (nur
  CONTRIBUTING nennt `ruff format --check` + Lizenz-Gates).
- ⚠ **ENG-7** Verify-Lücke real eingetreten (= TST-1/TST-3).
- ⚠ **ENG-8** STATE.md-Kopfdatum (2026-07-05) widerspricht dem obersten
  Eintrag (2026-07-07).
- ⚠ **ENG-9** DECISIONS.md-Präambel nennt veralteten ADR-Umfang
  („0001–0036").
- ⚠ **ENG-10** 8 Plan-Dateien ohne HHmm im Namensschema.
- ⚠ **ENG-11** Pläne werden nicht als living document mit ✅ geführt
  (Reconciliation passiert in STATE.md).

---

## 2. Change-Log für die Umsetzung

Geordnete Arbeitspakete; jedes Paket ist ein eigener PR-Kandidat mit
eigener DoD. Reihenfolge = Priorität (CI entsperren → strukturelle
Drift-Ursachen schließen → Substanz → Kosmetik). Owner-Entscheidungen sind
markiert.

### WP-1 — CI entsperren: dedizierter Web-Coverage-PR ⬅ zuerst
_Behebt: TST-1, TST-2, TST-7, TST-8, TST-9/FE-8. Floor bleibt 79 %
(Owner-Entscheidung 2026-07-05)._

- [ ] Tests für die 241 fehlenden Branches, größte Posten zuerst:
      `api/client.ts` (Fehlerpfade), `AccountPage`, `LoginPage`,
      `OAuthConsentPage`, `ResourceDetailPage`, `PlaybookDetailPage`.
- [ ] Komplett ungetestete Pages mitnehmen: system-prompts (4 Pages),
      `AgentsPage`/`AgentDetailPage`, legal-Pages.
- [ ] A11y-(axe-)Tests für die Form-lastigen Pages im selben Zug
      (gleiche Render-Fixtures): Auth-Flow, Detail-Editoren, agents,
      system-prompts.
- [ ] `coverage.all: true` (bzw. `include: ['src/**']`) in
      `apps/web/vite.config.ts` aktivieren, Floors auf die neue ehrliche
      Baseline ratchen (nie senken).
- DoD: `npm run test:coverage` lokal grün; CI-Job `web` inkl. A11y-, Build-
  und Bundle-Step wieder grün auf `main`.

### WP-2 — DoD-Drift strukturell schließen
_Behebt: TST-3, TST-12, ENG-6. Verhindert die nächste Schuldenwelle._

- [ ] CONTRIBUTING.md + CLAUDE.md §Befehle/DoD: Web-Test-Kommando auf
      `npm run test:coverage`, Python auf
      `uv run pytest --cov --cov-fail-under=85` umstellen.
- [ ] AGENTS.md + `docs/standards/engineering-method.md`: Kommando-Listen
      durch Verweis auf CONTRIBUTING §DoD ersetzen (Verlink-statt-Kopieren-
      Prinzip) — eine DoD-Quelle statt vier.

### WP-3 — DSGVO-Purge + Compliance-Doku nachziehen
_Behebt: CMP-1, CMP-2, CMP-3._

- [ ] `purge_account_data()` erweitern: `agent_feedback.actor_id` +
      `usage_event.actor_id` auf Sentinel anonymisieren;
      `oauth_authorization_code.user_id`-Rows des Users löschen.
- [ ] Expiry-/Consumed-Cleanup für `oauth_authorization_code` /
      `oauth_refresh_token` (analog `cleanup_expired_invitations`).
- [ ] `docs/compliance/data-retention-and-erasure.md` §2/§6 um die neuen
      Tabellen ergänzen; VVT §2/§3 um OAuth-Connector + Usage/Feedback-
      Events erweitern; C5-Mapping: Admin-MFA auf „umgesetzt"; Stand-Daten
      aktualisieren.
- DoD: Purge-Test erweitert (reproduziert vorher die Lücke), pytest grün.

### WP-4 — Doku-/Status-Drift beheben (Document-Phase)
_Behebt: ENG-1, ENG-2, ENG-3, ENG-4, ENG-8, ENG-9._

- [ ] CLAUDE.md „Aktueller Stand" auf Post-Phase-3-Realität heben
      (OAuth/MCP-HTTP, Builder-Lock, Feedback-Flywheel, MFA) — oder radikal
      kürzen und STATE.md als SSoT deklarieren; MCP-Tool-Liste in §Struktur
      aktualisieren (search, whoami, Feedback-Tools).
- [ ] ADR-Doppelnummer auflösen: `0032-test-strategie-pyramide.md` →
      `0041-…` umnummerieren + Verweis-Sweep (docs/, CLAUDE.md, .claude/).
- [ ] ADR-Status 0037/0038/0040 → Accepted.
- [ ] `.claude/plan/README.md` nachziehen (Juni/Juli-Blöcke mit
      PR-Nummern) oder Vorrang-Klausel streichen.
- [ ] DECISIONS.md-Präambel: ADR-Bereichsangabe entfernen; STATE.md-
      Kopfdatum korrigieren.

### WP-5 — Frontend-Gates + Konsistenz-Pass
_Behebt: FE-1, FE-2, FE-3, FE-5, FE-6, FE-7, FE-10, COD-6, COD-8._

- [ ] `FEATURES` in `apps/web/eslint.config.js` dynamisch aus
      `src/features/*` ableiten (statt harter Liste).
- [ ] `PersonaModesEditor → ResourceEditor` auflösen: `ResourceEditor`
      nach `@/components/editor/` hochziehen, dann greift das Gate.
- [ ] Kosmetik: `text-[10px]` → `text-xs`; Brand-Icons →
      `text-muted-foreground`; Off-Scale-Spacing (`mt-10`, `p-5`) auf
      Skala; `app/routes.tsx` über das legal-Barrel importieren.
- [ ] 4× `as any` (BlockNote) je einen Begründungssatz geben oder einen
      typisierten Insert-Wrapper bauen.
- [ ] design-language.md-Doku-Pass: `tokens`-Feature-Referenzen entfernen,
      §4.1↔§10.2-Widerspruch auflösen, „bis D2/D5"-Marker abräumen;
      Barrel-Ausnahme (Layout-/Slot-Exports) entweder dokumentieren oder
      Slots nach `@/components/` verschieben (FE-4).

### WP-6 — Architektur-Entscheidung ADR-0002 + Backend-Quick-Wins
_Behebt: COD-1, COD-2, COD-3, COD-4, COD-5, COD-9. **Owner-Entscheidung
nötig:** enforce vs. amend._

- [ ] Entscheidung treffen und als ADR festhalten: ADR-0002 durchsetzen
      (Domain-Exceptions + zentraler Exception-Handler; SQL der ~10
      Services hinter Repository-Protocols, beginnend mit
      `version_status.py`) **oder** Amendment „HTTPException in Services
      zulässig / benannte Query-Services mit Pool" — Doku und Code müssen
      wieder dieselbe Architektur erzählen.
- [ ] Unabhängig davon (Quick-Wins): `_resolve_org_id` aus
      `routers/entitlement.py`/`whoami.py` in einen gemeinsamen
      Repo-Helper; die 3 Export-Endpoints in einen typisierten Helper
      konsolidieren (löst auch `-> Any`); `assert` in `whoami.py:41` durch
      expliziten Check ersetzen.

### WP-7 — Test-Nähte vervollständigen
_Behebt: TST-4, TST-5, TST-6, TST-10, TST-11._

- [ ] REST↔MCP-Paritätstest bauen (Seed mit draft+active; REST-Read vs.
      MCP `fetch_*` feldweise; `contract`-Marker registrieren); Plan-/
      ADR-0032-Status ehrlich korrigieren.
- [ ] E2E-Journeys aktivieren (Login-/Seed-Helper laut TODO im Spec),
      danach `continue-on-error` im e2e-Job entfernen — in dieser
      Reihenfolge.
- [ ] `qa_run_personas_playbooks.py` → `test_qa_…`-Namen oder nach
      `scripts/` verschieben.
- [ ] Review-Regel „kein neues Inline-`_db_reachable`" + Abbau-Ticket
      (55 Dateien).

### WP-8 — Security-Sichtbarkeit (klein)
_Behebt: SEC-1; SEC-2/SEC-3 bleiben beobachtete ADR-Trigger._

- [ ] Warn-Log/Metric (`aal_missing_onprem`) in den On-Prem-fail-open-Pfad
      von `require_aal2`; optional Config-Schalter `require_mfa_onprem`.
- [ ] Keine Aktion für SEC-2/SEC-3 — Re-Eval-Trigger (Auth-BFF,
      `who2be_auth_token_attempts_total`) sind in ADR-0035/0008 definiert.

### WP-9 — Public-Switch-Blocker (manuell, Owner)
_Behebt: CMP-4, CMP-5, CMP-6. Kein Code — Checklisten-Punkte für
`…2028_public-switch-github-repo`._

- [ ] CLA-Assistant **vor** Freischaltung externer Beiträge aktivieren.
- [ ] AVV-Status Hetzner/Mollie klären + in VVT eintragen; Log-Retention
      festlegen; Rechtstexte finalisieren.
- [ ] Projektbezogene Kontakt-Adresse (security@/licensing@) statt privater
      Gmail in README/SECURITY.md/pyproject-authors erwägen.

## 3. Umsetzungsstand (2026-07-08, PR #299)

Die Umsetzung lief noch am Audit-Tag in zwei Agenten-Wellen auf demselben
Branch. Stand nach Abschluss:

| WP | Status | Beleg |
|---|---|---|
| WP-1 Coverage-PR | ✅ umgesetzt (6 Teilpakete) | Branches **69,52 % → 80,64 %** (Floor 79), Statements 87,2 %, Functions 83,5 %, Lines 88 %; 450 → **734 Tests**; `client.ts` 100 % Branches; A11y-Tests für Auth-/Detail-/agents-/system-prompts-/legal-Pages. Offen: `coverage.all: true` (bewusst zurückgestellt — senkt die Messbasis, Owner-Entscheidung zu neuen Floors). |
| WP-2 DoD-Drift | ✅ umgesetzt | CONTRIBUTING §DoD führt; CLAUDE.md/AGENTS.md/Standards verweisen statt kopieren. |
| WP-3 DSGVO-Purge + Doku | ✅ umgesetzt | Purge deckt `agent_feedback`/`usage_event`/`oauth_*` ab + `cleanup_expired_oauth()`; VVT (V15/V16), Retention, C5 nachgezogen. Testgetrieben (Repro-Test zuerst). |
| WP-4 Doku-/Status-Drift | ✅ umgesetzt | CLAUDE.md-Stand aktuell (STATE.md = SSoT), Test-Strategie-ADR **0032 → 0041** inkl. Sweep (Doku + Code-Kommentare), 0037/0038/0040 → Accepted, Plan-README nachgezogen. |
| WP-5 Frontend-Gates | ✅ umgesetzt | `FEATURES` dynamisch, personas→resources-Import via `@/components/editor/ResourceEditor` aufgelöst, Kosmetik + design-language-Doku-Pass. |
| WP-6 Quick-Wins | ✅ umgesetzt; **Grundsatzfrage offen** | `resolve_org_id`-Helper, Export-Triplikat → `routers/_export.py`, `assert` ersetzt. Die ADR-0002-Entscheidung (enforce vs. amend, COD-1/COD-3) braucht den Owner. |
| WP-7 Test-Nähte | ✅ umgesetzt (Kern) | REST↔MCP-Paritätstest + `contract`-Marker (960 pytest, `-m contract`: 5); QA-Skript → `scripts/`. Offen: E2E-Journeys aktivieren (TST-5, braucht Auth-Seed-Helper), erst danach Soft-Gate härten (TST-6, so im ci.yml dokumentiert). |
| WP-8 Security-Sichtbarkeit | ✅ umgesetzt | Warn-Event `aal_missing_onprem` + Schalter `WHO2BE_REQUIRE_MFA_ONPREM`. |
| WP-9 Public-Switch-Blocker | ⬜ offen (Owner, kein Code) | CLA, AVV-/Rechtstext-Platzhalter, Kontakt-Adresse. |

Neue Befunde aus der Umsetzung (Folge-Kandidaten): `PlaceholderHelpContent`
rendert `h3` direkt unter `h1` (axe heading-order, im Test begründet
deaktiviert); toter `bodyIsBlockNote`-false-Pfad in `PlaybookDetailPage`
(~10 untestbare Branches); stale i18n-Kommentar in `features/legal/index.ts`;
`client.contract.test.ts` referenziert noch ADR-0032 (Test-Strategie).

### Bewusst nicht adressiert

- **ENG-5/ENG-10/ENG-11** (Plan-`_done`-Renames, HHmm-Schema, ✅-Marker):
  Empfehlung ist, den **Standard an die gelebte Praxis anzupassen**
  (STATE.md als Reconciliation-Ort, Uhrzeit optional) statt 97 Dateien
  umzubenennen — Teil von WP-2/WP-4, keine eigene Migration.
- **FE-9/COD-7** (React-Compiler-Warnings): Abbau gehört zur geplanten
  Compiler-Migration; bis dahin gilt „Bestand nicht wachsen lassen".
