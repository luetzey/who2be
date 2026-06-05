# Compliance-Remediation DE/SaaS — Ausführungsplan (Agenten-Pakete)

**Erstellt:** 2026-06-05 · **Branch dieses Plans:** `claude/serene-gauss-sZqMi`
**Grundlage:** Audit gegen das Notion-Composite *Compliance-Standards (DE/SaaS)*
(`376be537-2ab8-8150-a55d-e6906c200ae2`) und seine vier Atomics:
Privacy-by-Design, Legal-Texts, Security-Infra, Finance-Compliance.

> ⚠️ **Disclaimer (Pflichtbestandteil laut Composite):** Engineering-/Produkt-Checkliste
> mit zum Anlage-Zeitpunkt verifizierten Rechtsständen (Stand 2026-06-05, DE-Recht).
> **Keine** Rechts-/Steuerberatung. Vor jedem Launch konkrete Pflichten mit fachkundiger
> Stelle verifizieren. Inhaltliche Rechtstexte (Impressum, Datenschutz, AVV) bleiben
> Betreiber/Anwalt — die Agenten liefern nur Struktur, Gates und Checklisten, keinen
> verbindlichen Rechtstext.

---

## 1 · Zweck dieses Dokuments

Dieser Plan zerlegt die Audit-Befunde in **datei-disjunkte Arbeitspakete (WP)**, geordnet
in **Wellen nach Abhängigkeit**. Jedes WP hat unten einen **fertigen, selbst-enthaltenen
Agenten-Prompt** (Abschnitt 6), den du manuell in einer eigenen Claude-Code-Session starten
kannst. Die Pakete sind so geschnitten, dass parallel laufende Agenten nicht dieselben
Dateien anfassen.

**Wichtige Repo-Fakten (für jeden Agenten gültig):**
- uv-Workspace im Root. Python-DoD: `uv run ruff check .`, `uv run mypy .`, `uv run pytest -q`.
- Web in `apps/web/`: `npm run lint`, `npx tsc -b`, `npm test`, `npm run build`.
- Migrationen: `apps/api/src/who2be_api/migrations/NNNN_*.sql`, idempotent, in Reihenfolge
  via `uv run who2be-migrate`. **Nächste freie Nummer: `0044`.** Nur **WP-A** legt neue
  Migrationen an — alle anderen Pakete bauen darauf auf, damit es keine Nummern-Kollision gibt.
- **Privileg-Modell (zentral!):** Zur Laufzeit verbindet die App als Rolle `who2be_app`
  (`NOSUPERUSER, NOBYPASSRLS`). Migrations-Runner **und** Purge-Job (`core/purge.py`)
  verbinden als **Owner** über `DATABASE_URL` (RLS-Bypass, volle Rechte). „Append-only“
  wird also über `REVOKE UPDATE/DELETE` gegen `who2be_app` erzwungen — der Owner-Purge
  darf weiterhin anonymisieren/löschen. Dieses Split ist die tragende Idee hinter WP-A/WP-D.
- Nächste freie ADR-Nummer: `0031` (`docs/adr/`).
- Branch-Konvention: jedes WP auf eigenem Branch `feat/compliance-<wp>` → **Draft-PR**.
- Doku-Konvention (Coder): bei größeren WPs einen Detail-Plan unter `.claude/plan/` ablegen
  und nach Abschluss ein kurzes Change-Log in dieses Dokument (Abschnitt 7) eintragen.

---

## 2 · Audit-Befunde (Kurzfassung, priorisiert)

| # | Domäne | Befund | Schwere | WP |
|---|--------|--------|---------|----|
| P1 | Privacy | VVT (Art. 30) fehlt vollständig | HOCH | H |
| P2 | Privacy | Audit-Logs (`status_history.changed_by`) überleben Erasure-Purge (kein FK→keine CASCADE) | HOCH | D |
| P3 | Privacy | Rechtstexte (Datenschutz, AVV) reine Platzhalter | HOCH | I (Struktur) + Betreiber |
| P4 | Privacy | DB-Encryption-at-rest nicht belegt/dokumentiert | MITTEL | G |
| P5 | Privacy | Backup-/Log-Retention vs. Löschpflicht undokumentiert | MITTEL | H |
| P6 | Privacy | GDPR-Export deckt GoTrue-Profildaten (E-Mail) nicht ab | NIEDRIG | E |
| P7 | Privacy | `workspace_invitation.email` bleibt nach Accept/Ablauf liegen | NIEDRIG | D |
| L1 | Legal | Impressum-Pflichtangaben = Platzhalter (§5 DDG-Verweis aber korrekt ✔) | KRITISCH | Betreiber (Checkliste: I) |
| L2 | Legal | Datenschutzerklärung ohne Verantwortlichen/AV-Liste | KRITISCH | Betreiber (Checkliste: I) |
| L3 | Legal | AGB ohne B2B/B2C-Trennung, keine Widerrufsbelehrung | HOCH | I |
| L4 | Legal | Keine AGB/Datenschutz-Zustimmung im Signup | HOCH | I |
| L5 | Legal | SLA nicht definiert; AVV nur Web-Gerüst | MITTEL | I (Struktur) + Betreiber |
| S1 | Security | MFA für administrative Zugänge fehlt vollständig | HOCH | F |
| S2 | Security | At-Rest-Verschlüsselung Live-DB nicht nachweisbar | HOCH | G |
| S3 | Security | `status_history` DB-seitig nicht append-only (`who2be_app` hat UPDATE/DELETE); kein Admin-/RBAC-/Auth-Audit | MITTEL | A + B |
| S4 | Security | Last-Admin-Race nur READ-COMMITTED-sicher | MITTEL | B |
| S5 | Security | Kein `dependabot.yml` (nur reaktiver CI-Audit) | NIEDRIG | G |
| F1 | Finance | Kein unveränderbares, lückenloses Zahlungs-/Tarif-Journal (`org_entitlement` UPSERT überschreibt) | KRITISCH (Cloud) | A + C |
| F2 | Finance | GoBD-Verfahrensdokumentation fehlt | KRITISCH (Cloud) | H |
| F3 | Finance | USt-IdNr/Reverse-Charge nicht abgebildet | MITTEL (EU-B2B) | siehe §5 (deferred) |
| F4 | Finance | E-Rechnung EN 16931 | NICHT EINSCHLÄGIG (Who2Be stellt keine Rechnungen) | — |

---

## 3 · Wellen & Abhängigkeiten

```
Welle 1 (Fundament, zuerst):
  WP-A  DB-Schema: Append-only-Erzwingung + audit_log + entitlement_history (nur Migrationen + Schema-Test)

Welle 2 (Verdrahtung, parallel — alle hängen nur an WP-A):
  WP-B  Admin/Security-Audit-Log verdrahten (+ Last-Admin Advisory-Lock)
  WP-C  GoBD Entitlement-Journal (entitlement_repository → entitlement_history)
  WP-D  Erasure-Vollständigkeit (Purge anonymisiert überlebende PII; Invitation-Cleanup)
  WP-E  GDPR-Export um GoTrue-Profildaten erweitern

Welle 3 (unabhängig — können jederzeit, auch sofort, laufen):
  WP-F  MFA für Admin-Zugänge (GoTrue + AAL2-Gate + Enrollment-UI)
  WP-G  Infra/Supply-Chain: dependabot.yml + DB-FDE-Doku + Hetzner-Standort-Doku
  WP-H  Compliance-Dokumente: VVT (Art. 30) + GoBD-Verfahrensdoku + Retention-Konzept
  WP-I  Legal-Struktur: AGB B2B/B2C, Signup-Consent, SLA-Gerüst + Betreiber-Checkliste
```

**Datei-Disjunktheit (warum parallel sicher):**
- WP-A: nur neue Migrationsdateien + neuer Schema-Test. Niemand sonst legt Migrationen an.
- WP-B: `audit_log_repository.py` (neu), `audit_service.py` (neu), `routers/members.py`,
  `services/workspace_member_service.py`, `services/token_service.py`,
  `services/invitation_service.py`, `services/account_lifecycle_service.py`.
- WP-C: nur `repositories/entitlement_repository.py` (+ Test). Disjunkt zu B.
- WP-D: `repositories/account_repository.py`, `core/purge.py`, `services/invitation_service.py`
  ⚠️ **Konflikt mit WP-B** (beide würden `invitation_service.py` anfassen). → Siehe Auflösung unten.
- WP-E: nur `services/gdpr_export_service.py` (+ Test). Disjunkt.
- WP-F: `core/security.py`, `docker-compose*.yml`, `deploy/…`, `apps/web/src/features/settings/**`, Doku.
- WP-G: `.github/dependabot.yml` (neu), `deploy/hetzner/RUNBOOK.md`, Doku. Disjunkt.
- WP-H: nur `docs/compliance/**` (neu). Disjunkt.
- WP-I: `apps/web/src/features/legal/**`, `apps/web/src/features/auth/**` (Signup-Consent). Disjunkt von WP-F (settings).

**Konflikt-Auflösung WP-B vs WP-D (`invitation_service.py`):**
- WP-B fügt Audit-Inserts bei Invitation-**Issue/Revoke** hinzu.
- WP-D fügt einen Invitation-**Cleanup** (Email-Bereinigung) hinzu — der gehört eher in den
  **Purge/Lifecycle-Pfad**, nicht in `invitation_service.py`. **Regelung:** WP-D fasst
  `invitation_service.py` NICHT an, sondern legt die Bereinigung als Teil des Purge/Cleanup-
  Jobs in `repositories/account_repository.py` + `core/purge.py` ab (eigene Methode
  `cleanup_expired_invitations`). Damit bleibt die Disjunktheit erhalten. Falls beide doch
  kollidieren: **WP-B zuerst mergen, WP-D danach rebasen.**

---

## 4 · Detail je Arbeitspaket

### WP-A — DB-Schema: Append-only + Audit/Journal-Tabellen
**Befunde:** S3 (DB-Teil), F1 (Schema-Teil). **Abhängigkeit:** keine. **Welle 1.**

**Ziel:** Das Fundament legen, ohne App-Verdrahtung: (1) `status_history` DB-seitig append-only
gegen die Laufzeitrolle; (2) generische `audit_log`-Tabelle für Admin-/Security-Events;
(3) `entitlement_history`-Tabelle als unveränderbares GoBD-Journal.

**Schritte:**
1. Migration `0044_audit_append_only.sql`:
   - `REVOKE UPDATE, DELETE ON status_history FROM who2be_app;` (idempotent — REVOKE ist no-op
     wenn nicht vorhanden). Kommentar: append-only für die Laufzeitrolle; Owner (Migration/Purge)
     behält Vollzugriff bewusst für Erasure-Anonymisierung (WP-D).
   - `CREATE TABLE audit_log` (idempotent via `IF NOT EXISTS`): Spalten `id uuid PK default
     gen_random_uuid()`, `org_id uuid` (nullable, für org-scoped Events), `workspace_id uuid`
     (nullable), `actor_id uuid` (nullable — kann nach Erasure auf Sentinel gesetzt werden),
     `action text NOT NULL` (z.B. `member.role_changed`, `member.removed`, `token.issued`,
     `token.revoked`, `invitation.issued`, `invitation.revoked`, `account.deletion_requested`,
     `org.soft_deleted`), `target text` (z.B. betroffene user_id/token_id als Text),
     `detail jsonb`, `created_at timestamptz NOT NULL DEFAULT now()`. Index auf
     `(org_id, created_at DESC)` und `(workspace_id, created_at DESC)`.
   - Grants: `GRANT SELECT, INSERT ON audit_log TO who2be_app;` (kein UPDATE/DELETE → append-only).
2. Migration `0045_entitlement_history.sql`:
   - `CREATE TABLE entitlement_history` (append-only Journal): `id uuid PK`, `org_id uuid NOT NULL`
     (**ohne** `ON DELETE CASCADE** — GoBD-Aufbewahrung überlebt Org-Löschung; lawful basis
     §14b UStG / §147 AO), `status text`, `features jsonb`, `expires_at timestamptz`,
     `mcp_monthly_quota int`, `mcp_rate_per_min int`, `grace_until timestamptz`,
     `source text NOT NULL`, `external_ref text`, `created_by uuid`, `reason text`,
     `recorded_at timestamptz NOT NULL DEFAULT now()`. Index `(org_id, recorded_at DESC)`.
   - RLS: org-scoped Policy analog `org_entitlement` (siehe `0037_rls_policies.sql`) — `USING
     (org_id = current_setting('app.current_org')::uuid)`. **Nur** `GRANT SELECT, INSERT … TO
     who2be_app;` (append-only).
   - Hinweis in Migrationskommentar: bewusst **nicht** in `0036`-Grants aufnehmen; eigene Grants hier.
3. Test `apps/api/tests/test_audit_append_only.py`: verbindet als `who2be_app` (analog
   vorhandenem RLS-Isolations-Test — Muster suchen via `grep -rn "who2be_app" apps/api/tests`),
   prüft: INSERT in `audit_log`/`entitlement_history` ok; `UPDATE`/`DELETE` auf `status_history`,
   `audit_log`, `entitlement_history` → `InsufficientPrivilege`. Als Owner: alles erlaubt.
4. ADR `docs/adr/0031-compliance-audit-journals.md`: dokumentiert das Append-only-Privileg-Split
   und die GoBD-Aufbewahrung von `entitlement_history` trotz DSGVO-Erasure (Retention-Konflikt
   bewusst zugunsten gesetzlicher Aufbewahrung aufgelöst; siehe WP-H).

**DoD:** `uv run ruff check . && uv run mypy . && uv run pytest -q` grün; neuer Test deckt
Append-only ab; Migrationen idempotent (zweiter `who2be-migrate`-Lauf = No-op).

---

### WP-B — Admin/Security-Audit-Log verdrahten (+ Last-Admin Advisory-Lock)
**Befunde:** S3 (App-Teil), S4. **Abhängigkeit:** WP-A (`audit_log`). **Welle 2.**

**Ziel:** Sicherheitskritische Aktionen in `audit_log` protokollieren und die Last-Admin-Invariante
race-fest machen.

**Schritte:**
1. `repositories/audit_log_repository.py` (neu): Protocol + `PgAuditLogRepository` mit
   `async def insert(self, conn_or_pool, *, action, org_id=None, workspace_id=None, actor_id,
   target=None, detail=None)`. INSERT-only. Optional Connection-Param (für Transaktions-Teilnahme
   analog `status_history_repository.py`).
2. `services/audit_service.py` (neu): dünner Wrapper, der pro Event die Felder normalisiert.
3. Verdrahten (jeweils im selben Tx-Pfad wie die Mutation, wo möglich):
   - `routers/members.py` / `services/workspace_member_service.py`: `member.role_changed`,
     `member.removed` (actor = ctx-User, target = betroffene user_id, detail = alt/neu-Rolle).
   - `services/token_service.py`: `token.issued`, `token.revoked`.
   - `services/invitation_service.py`: `invitation.issued`, `invitation.revoked`.
   - `services/account_lifecycle_service.py`: `account.deletion_requested`, `org.soft_deleted`.
4. **Last-Admin Advisory-Lock:** in `workspace_member_service.py` vor Rollen-Downgrade/Removal
   `SELECT pg_advisory_xact_lock(hashtext('ws_admins:'||$workspace_id))` in der Transaktion,
   dann Admin-Count prüfen. Verhindert den parallelen Drop zweier Admins
   (`docs/security-findings-phase-2.md:171-179`).
5. Tests: je Event ein Audit-Eintrag; Last-Admin-Race-Test (zwei nebenläufige Removals → genau
   einer schlägt fehl, mind. 1 Admin bleibt).

**DoD:** Python-DoD grün; jede genannte Mutation erzeugt genau einen Audit-Eintrag; Race-Test grün.

---

### WP-C — GoBD Entitlement-Journal
**Befunde:** F1 (App-Teil). **Abhängigkeit:** WP-A (`entitlement_history`). **Welle 2.**

**Ziel:** Jede Entitlement-Änderung (Mollie/Cloud/manual_override/signed_license) zusätzlich als
unveränderbaren Journaleintrag schreiben — der UPSERT auf `org_entitlement` bleibt der „aktuelle
Stand“, `entitlement_history` wird das lückenlose Protokoll.

**Schritte:**
1. `repositories/entitlement_repository.py`: `upsert(...)` so erweitern, dass im **selben
   Aufruf/Transaktion** zusätzlich ein `INSERT INTO entitlement_history (...)` erfolgt
   (alle Felder + `source`, `external_ref`, `created_by`, `reason`, `recorded_at = now()`).
   `_pool.execute` → `async with self._pool.acquire() as conn, conn.transaction():` mit beiden
   Statements, damit UPSERT und Journal atomar sind.
2. Sicherstellen, dass der org-scoped RLS-Kontext (`app.current_org`) beim Webhook-/Cloud-Pfad
   gesetzt ist; falls der Schreibpfad ohne `tenant_scope` läuft (Owner/Service), Journal-Insert
   funktioniert ohnehin (Owner bypasst RLS) — verifizieren und im Kommentar festhalten.
3. Test: zwei aufeinanderfolgende `upsert`-Calls (z.B. free→pro→manual_override) → genau drei
   `entitlement_history`-Zeilen in zeitlicher Reihenfolge, `org_entitlement` zeigt den letzten
   Stand. `UPDATE`/`DELETE` auf `entitlement_history` als `who2be_app` schlägt fehl (Cross-Check
   mit WP-A-Test, hier nur falls separat sinnvoll).

**DoD:** Python-DoD grün; Journal-Lückenlosigkeit per Test belegt. Liegt im `who2be-billing`-/Cloud-
Pfad — Tests laufen unter `uv sync --group billing` (CI installiert das ohnehin).

---

### WP-D — Erasure-Vollständigkeit (DSGVO Art. 17)
**Befunde:** P2, P7. **Abhängigkeit:** WP-A (`audit_log` existiert, damit Anonymisierung greifen
kann). **Welle 2.** ⚠️ Fasst `invitation_service.py` **nicht** an (siehe §3-Konflikt-Auflösung).

**Ziel:** Beim Hard-Purge die PII-Referenzen mitnehmen, die heute verwaist überleben — ohne die
gesetzlich aufzubewahrenden Finanzdaten (`entitlement_history`) zu löschen.

**Schritte:**
1. `repositories/account_repository.py` → `purge_account_data(user_id)` erweitern (läuft als Owner,
   darf UPDATE trotz Append-only-REVOKE):
   - `UPDATE status_history SET changed_by = '00000000-0000-0000-0000-000000000000' WHERE
     changed_by = $1;` (Anonymisierung statt Löschung — Audit-Integrität bleibt, PII-Bezug weg).
   - `UPDATE audit_log SET actor_id = '000…0' WHERE actor_id = $1;` (analog).
   - Kommentar: `entitlement_history` wird **bewusst nicht** angefasst (gesetzliche Aufbewahrung,
     §14b UStG; Verweis auf ADR-0031 + WP-H Retention-Konzept).
2. Neue Methode `cleanup_expired_invitations()` in `account_repository.py` + Aufruf im Purge-Lauf
   (`core/purge.py`): angenommene/abgelaufene `workspace_invitation` mit Klartext-`email` bereinigen
   (z.B. `email` auf NULL setzen oder Zeile löschen, sobald `accepted_at IS NOT NULL OR expires_at
   < now()`). Genaues Schema vorher prüfen (`migrations/0017_workspace_invitation.sql`).
3. `PurgeResult` ggf. um Zähler erweitern (anonymisierte Audit-Zeilen, bereinigte Invitations).
4. Tests in `apps/api/tests/` (Purge-Test-Datei suchen, `grep -rn "purge" apps/api/tests`):
   nach Purge sind `status_history.changed_by`/`audit_log.actor_id` des Users = Sentinel;
   abgelaufene Invitations ohne Klartext-Email; `entitlement_history` unverändert vorhanden.

**DoD:** Python-DoD grün; Purge-Test belegt Anonymisierung + Invitation-Cleanup + Retention der
Finanzdaten.

---

### WP-E — GDPR-Export um GoTrue-Profildaten erweitern
**Befunde:** P6. **Abhängigkeit:** WP-A nicht nötig (rein lesend). **Welle 2 (oder jederzeit).**

**Ziel:** Art.-15-Vollständigkeit — der Export soll die in GoTrue (`auth.users`) liegenden
Profildaten des Users (mindestens E-Mail, `created_at`, Auth-Metadaten) mit ausgeben.

**Schritte:**
1. `services/gdpr_export_service.py`: einen `account`-Block ergänzen, der `email` (+ ggf.
   `created_at`, `last_sign_in_at`, Provider) aus `auth.users` liest. Muster für den Lesezugriff
   in `repositories/me_repository.py:95-119` (`_lookup_email`, `auth.users`-Query, Fehler → None,
   robust gegen fehlende `auth.users` in Test-DBs).
2. Block ins Export-JSON aufnehmen (klar als „account/identity“ benannt), unter Beibehaltung der
   bestehenden RLS-konformen Workspace-Iteration.
3. Test: Export enthält den `account`-Block mit E-Mail (Test-DB mit gestubbter `auth.users`-Zeile),
   degradiert sauber zu `null`/leer, wenn `auth.users` fehlt.

**DoD:** Python-DoD grün; Export-Test deckt den neuen Block ab.

---

### WP-F — MFA für administrative Zugänge
**Befunde:** S1. **Abhängigkeit:** keine. **Welle 3.** *(Größtes Paket — bei Bedarf weiter splitten:
F1 Backend-Gate, F2 Frontend-Enrollment.)*

**Ziel:** GoTrue-MFA (TOTP) aktivieren, Enrollment-UI bereitstellen und für Admin-Aktionen AAL2
erzwingen.

**Schritte:**
1. **GoTrue-Config:** MFA/TOTP-Faktoren in den GoTrue-Env-Variablen aktivieren
   (`docker-compose.yml`, `docker-compose.cloud.yml`, `deploy/hetzner/**`, `.env.example`).
   Genaue Variablen aus der GoTrue-Version `v2.158.1` (in `docker-compose.yml`) verifizieren
   (`GOTRUE_MFA_*`).
2. **Backend-Gate:** in `core/security.py` den JWT-`aal`-Claim auswerten. `require_role(ctx,
   admin)` (bzw. eine neue `require_aal2`-Hilfsfunktion, an Admin-Mutationen gehängt) verlangt
   `aal == "aal2"`, sonst `403` mit klarer Fehlermeldung („MFA erforderlich für Admin-Aktionen“).
   Betroffene Stellen: alle `require_role(ctx, WorkspaceRole.admin)`-Aufrufe — Re-Use über eine
   zentrale Hilfsfunktion, nicht dupliziert.
3. **Frontend-Enrollment:** in `apps/web/src/features/settings/**` eine MFA-Sektion (TOTP-Enroll
   via GoTrue-`/factors`, QR/Secret anzeigen, Verify, Liste/Unenroll). shadcn-Primitives, Tokens,
   Design-Language (`docs/frontend/design-language.md` zuerst lesen). Forms via `react-hook-form` +
   `zod`.
4. **Doku:** RUNBOOK + `docs/` um MFA-Pflicht für Admins ergänzen; SSH-Host-Zugang ist bereits
   key-only (`deploy.yml`) — MFA-Empfehlung für die Hetzner-Konsole dokumentieren.
5. Tests: Backend — Admin-Mutation mit `aal1`-Token → 403, mit `aal2` → ok. Web — Enrollment-
   Komponente rendert + A11y (axe) grün.

**DoD:** Python-DoD + Web-DoD (`npm run lint && npx tsc -b && npm test && npm run build`) grün;
Admin-Aktion ohne AAL2 wird geblockt; Enrollment-Flow vorhanden.

---

### WP-G — Infra-Härtung & Supply-Chain
**Befunde:** P4, S2, S5 (+ Hetzner-Standort-Doku). **Abhängigkeit:** keine. **Welle 3.**

**Ziel:** Proaktive Patch-PRs, dokumentierte At-Rest-Verschlüsselung der Live-DB, Standort-Nachweis.

**Schritte:**
1. `.github/dependabot.yml` (neu): Ecosystems `pip`/`uv` (Python), `npm` (`apps/web`),
   `github-actions`, `docker`. Wöchentlich, gruppiert, Labels. (Ergänzt den bestehenden reaktiven
   `audit`-Job in `.github/workflows/ci.yml`, ersetzt ihn nicht.)
2. **DB-At-Rest-Verschlüsselung:** in `deploy/hetzner/RUNBOOK.md` (+ ggf. `deploy/hetzner/README.md`)
   ein Verfahren dokumentieren und – wo möglich – verifizierbar machen: LUKS/Full-Disk-Encryption
   des Postgres-Volumes (`docker-compose.yml` Volume `db-data`) bzw. verschlüsseltes Hetzner-Volume.
   Kein Geheimnis ins Repo; nur Procedure + Verifikationsschritt (`lsblk`/`cryptsetup status`).
3. **Standort/AV-Doku:** Hetzner-RZ-Standort (DE/FI) explizit dokumentieren; Auftragsverarbeiter
   (Hetzner, Mollie, ggf. Mail-Provider) als Liste für AVV/VVT festhalten (Querverweis WP-H).
4. **C5-Mapping (optional, leichtgewichtig):** kurze Tabelle in `docs/` (z.B.
   `docs/compliance/c5-mapping.md`) — Mandantentrennung/OPS-18/IAM/CRY auf vorhandene Belege.

**DoD:** `dependabot.yml` valide; RUNBOOK-Abschnitt vorhanden + reproduzierbarer Verifikationsschritt;
keine Secrets im Repo. (Kein Python/Web-Build betroffen — ggf. nur Markdown-/YAML-Lint.)

---

### WP-H — Compliance-Dokumente (VVT, GoBD-Verfahrensdoku, Retention)
**Befunde:** P1, P5, F2. **Abhängigkeit:** keine (referenziert WP-A/D-Entscheidungen). **Welle 3.**

**Ziel:** Die fehlenden Pflicht-/Nachweisdokumente als gepflegte Repo-Dokumente anlegen — aus der
Code-Realität rekonstruiert, mit klar markierten Betreiber-Platzhaltern.

**Schritte:** neues Verzeichnis `docs/compliance/`:
1. `vvt.md` — Verzeichnis von Verarbeitungstätigkeiten (Art. 30): Verarbeitungstätigkeiten,
   Datenkategorien, Betroffenenkreise, Empfänger/Auftragsverarbeiter (Hetzner, Mollie, GoTrue/
   self-hosted, Mail), Drittland, Löschfristen. Datenkategorien aus dem Schema ableiten
   (Migrationen + `packages/models`). `<Platzhalter: Verantwortlicher/Kontakt>` wo Betreiber-Input nötig.
2. `gobd-verfahrensdokumentation.md` — wie buchungsrelevante Vorgänge entstehen/verarbeitet/
   archiviert werden: Mollie als PSP/Beleg-Stelle, `org_entitlement` (aktueller Stand) +
   `entitlement_history` (unveränderbares Journal, WP-A/C), Aufbewahrung §14b UStG / §147 AO,
   keine eigene Rechnungsausstellung (E-Rechnung nicht einschlägig — explizit benennen).
3. `data-retention-and-erasure.md` — Retention vs. Löschpflicht: 30-Tage-Grace + Hard-Purge,
   Anonymisierung überlebender Audit-Referenzen (WP-D), restic-Backup-Retention (~6 Monate) und
   das „Restore-only-Re-Deletion“-Verfahren für Backups, gesetzliche Ausnahme für `entitlement_history`.
4. `README.md` in `docs/compliance/` als Einstieg + Verweis auf das Notion-Composite und diesen Plan.

**DoD:** Dokumente vollständig strukturiert, Betreiber-Platzhalter eindeutig markiert, keine
erfundenen Rechts-/Steueraussagen (Disclaimer in jedem Dokument). Querverweise zu ADR-0031.

---

### WP-I — Legal-Struktur: AGB B2B/B2C, Signup-Consent, SLA
**Befunde:** L3, L4, L5 (Struktur) + Checkliste für L1/L2. **Abhängigkeit:** keine. **Welle 3.**

**Ziel:** Die strukturellen/technischen Legal-Lücken schließen (was Code ist), und eine präzise
Betreiber-Checkliste für die inhaltlichen Rechtstexte liefern. **Keine erfundenen Rechtstexte.**

**Schritte:** (Design-Language zuerst lesen; Lint-Gates: nur Primitives aus `@/components/ui/*`)
1. `apps/web/src/features/legal/pages/TermsPage.tsx`: AGB strukturell in B2B- vs. B2C-Abschnitte
   trennen (Mischvertrag Miete+Dienstleistung), Widerrufsbelehrung-Abschnitt für Verbraucher als
   eigener Block, Hinweis-Abschnitt „elektronische Rechnung — Zustimmung des Empfängers (B2C)“.
   Inhalte bleiben markierte `<Placeholder>` (Komponente existiert: `components/Placeholder.tsx`).
2. **Signup-Consent:** in `apps/web/src/features/auth/**` (Registrierung) eine Pflicht-Checkbox
   „AGB & Datenschutz akzeptiert“ mit Verlinkung auf `/legal/agb` und `/legal/datenschutz`
   ergänzen (react-hook-form + zod-Validierung, Submit erst bei Zustimmung). Primitive `Checkbox`
   aus `@/components/ui/*`.
3. **SLA:** SLA-Abschnitt (Verfügbarkeit/Reaktionszeiten) als strukturiertes Gerüst — entweder in
   `TermsPage.tsx` oder eigene `/legal/sla`-Seite (Routing in `apps/web/src/app/routes.tsx`,
   Footer-Link in `components/layout/Footer.tsx`). Konkrete Werte als Platzhalter.
4. **Betreiber-Checkliste** `docs/compliance/legal-texts-checklist.md`: exakt auflisten, welche
   Inhalte Impressum (§5 DDG — Firmendaten, Vertretung, Register, USt-IdNr, OS-Plattform-Link,
   Verbraucherschlichtung) und Datenschutzerklärung (Verantwortlicher, AV-Liste, Drittland,
   Speicherdauer, Aufsichtsbehörde) noch brauchen. Querverweis auf vorhandene korrekte
   Paragraphen-Verweise (§5 DDG ✔, TDDDG ✔ — nicht verschlechtern!).
5. Tests/DoD: Web — neue/geänderte Komponenten rendern, Signup blockt ohne Consent, A11y (axe) grün.

**DoD:** Web-DoD grün; Signup erzwingt Consent; AGB strukturell B2B/B2C getrennt; Checkliste
vollständig. **Wichtig:** korrekte Verweise (§5 DDG, TDDDG) nicht durch Platzhalter zerstören.

---

## 5 · Bewusst NICHT in diesem Plan (deferred / nicht einschlägig)

- **F4 E-Rechnung EN 16931 / XRechnung / ZUGFeRD:** nicht einschlägig — Who2Be stellt keine
  Rechnungen aus (Mollie/Betreiber). Erst relevant, falls eine eigene Rechnungsfunktion (z.B.
  geplante Enterprise-SKU mit Stripe-Invoicing) gebaut wird → dann eigener Plan.
- **F3 USt-IdNr-Erfassung + Reverse-Charge:** nur bei EU-B2B-Direktverkauf durch den Betreiber
  einschlägig. Heute übernimmt Mollie die Steuerbehandlung. **Offene Betreiber-Frage** (in WP-H
  als Klärungspunkt vermerken), kein Code-WP, solange Mollie fakturiert.
- **Inhaltliche Rechtstexte (L1/L2):** Anwalts-/Betreiber-Aufgabe; WP-I liefert nur die Checkliste.
- **C5-Testat:** Orientierung, kein Testat — kommt vom Wirtschaftsprüfer. Nicht „bestanden“ behaupten.

---

## 6 · Fertige Agenten-Prompts (zum manuellen Start kopieren)

> Jeder Prompt ist selbst-enthalten. Starte ihn in einer **eigenen** Claude-Code-Session.
> Reihenfolge: **WP-A zuerst** (Welle 1). Danach B/C/D/E parallel. F/G/H/I jederzeit.
> Jeder Agent: eigener Branch `feat/compliance-<wp>`, Draft-PR, Coder-Methode (erst lesen,
> verifizieren mit Tests, knappes Change-Log in Abschnitt 7 dieses Plans).

### Prompt WP-A
```
Du bist Coder im Repo who2be (uv-Workspace). Aufgabe: WP-A aus
.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md — DB-Fundament für
Compliance-Audit/Journale. Lies zuerst diesen Plan (Abschnitt WP-A) UND
apps/api/src/who2be_api/migrations/0036_rls_app_role.sql, 0037_rls_policies.sql,
0012_status_history.sql, 0030_org_entitlement.sql, 0043_entitlement_write_sources.sql sowie
core/migrations.py.

Setze um:
1. Migration 0044_audit_append_only.sql: REVOKE UPDATE, DELETE ON status_history FROM who2be_app;
   + CREATE TABLE audit_log (id, org_id, workspace_id, actor_id, action, target, detail jsonb,
   created_at) idempotent; Indizes; GRANT SELECT, INSERT ON audit_log TO who2be_app (kein UPDATE/DELETE).
2. Migration 0045_entitlement_history.sql: CREATE TABLE entitlement_history (Felder analog
   org_entitlement + source/external_ref/created_by/reason/recorded_at), org_id OHNE ON DELETE CASCADE
   (GoBD-Aufbewahrung), org-scoped RLS-Policy wie in 0037, nur GRANT SELECT, INSERT TO who2be_app.
3. Test apps/api/tests/test_audit_append_only.py: who2be_app darf INSERT, aber UPDATE/DELETE auf
   status_history/audit_log/entitlement_history schlägt fehl; Owner darf alles. Muster für die
   who2be_app-Verbindung: grep -rn "who2be_app" apps/api/tests.
4. ADR docs/adr/0031-compliance-audit-journals.md: Append-only-Privileg-Split + GoBD-Retention
   trotz DSGVO-Erasure dokumentieren.

Privileg-Modell beachten: App-Laufzeit = Rolle who2be_app (NOBYPASSRLS); Migrationen + Purge laufen
als Owner (RLS-Bypass) — Append-only gilt nur gegen who2be_app, Owner behält Vollzugriff (bewusst,
für Erasure in WP-D). Migrationen müssen idempotent sein (IF NOT EXISTS / guarded REVOKE).

Branch feat/compliance-wp-a. DoD: uv run ruff check . && uv run mypy . && uv run pytest -q grün,
zweiter who2be-migrate-Lauf = No-op. Danach pushen, Draft-PR erstellen, Change-Log in Abschnitt 7
des Plans ergänzen.
```

### Prompt WP-B
```
Du bist Coder im Repo who2be. Aufgabe: WP-B aus
.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md — Admin/Security-Audit-Log
verdrahten + Last-Admin Advisory-Lock. VORAUSSETZUNG: WP-A (audit_log-Tabelle) ist gemergt/vorhanden
— sonst zuerst dessen Migrationen 0044/0045 mergen.

Lies zuerst: den Plan (WP-B), repositories/status_history_repository.py (Muster für INSERT-only-Repo
mit optionaler Connection), routers/members.py, services/workspace_member_service.py,
services/token_service.py, services/invitation_service.py, services/account_lifecycle_service.py,
docs/security-findings-phase-2.md:171-179 (Last-Admin-Race).

Setze um:
1. repositories/audit_log_repository.py (neu, INSERT-only, Protocol + PgAuditLogRepository).
2. services/audit_service.py (neu, dünner Wrapper).
3. Audit-Inserts (im selben Tx-Pfad wo möglich) für: member.role_changed, member.removed (members),
   token.issued, token.revoked, invitation.issued, invitation.revoked, account.deletion_requested,
   org.soft_deleted.
4. Last-Admin Advisory-Lock: pg_advisory_xact_lock vor Rollen-Downgrade/Removal in
   workspace_member_service, dann Admin-Count prüfen.
5. Tests: je Event ein Audit-Eintrag; Race-Test (zwei nebenläufige Admin-Removals → genau einer
   schlägt fehl).

Fasse invitation_service.py NUR für Audit-Inserts an (Issue/Revoke) — die Email-Bereinigung gehört
zu WP-D, nicht hierher. Branch feat/compliance-wp-b. DoD: Python-DoD grün. Pushen, Draft-PR,
Change-Log in Abschnitt 7.
```

### Prompt WP-C
```
Du bist Coder im Repo who2be. Aufgabe: WP-C aus
.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md — GoBD Entitlement-Journal.
VORAUSSETZUNG: WP-A (entitlement_history-Tabelle) vorhanden.

Lies zuerst: den Plan (WP-C), repositories/entitlement_repository.py (UPSERT-Stelle),
migrations/0030_org_entitlement.sql, 0043_entitlement_write_sources.sql, 0045_entitlement_history.sql.

Setze um: entitlement_repository.upsert(...) so erweitern, dass im selben Transaktions-Pfad
zusätzlich ein INSERT INTO entitlement_history (alle Felder + source/external_ref/created_by/reason/
recorded_at=now()) erfolgt — UPSERT (aktueller Stand) und Journal (lückenlos) atomar. RLS/Owner-Pfad
verifizieren und kommentieren. Test: free→pro→manual_override erzeugt genau 3 Journalzeilen in
Reihenfolge, org_entitlement zeigt letzten Stand.

Nur repositories/entitlement_repository.py + Test anfassen. Tests unter uv sync --group billing.
Branch feat/compliance-wp-c. DoD: uv run ruff check . && uv run mypy . && uv run pytest -q grün.
Pushen, Draft-PR, Change-Log in Abschnitt 7.
```

### Prompt WP-D
```
Du bist Coder im Repo who2be. Aufgabe: WP-D aus
.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md — Erasure-Vollständigkeit (DSGVO
Art. 17). VORAUSSETZUNG: WP-A (audit_log existiert). Falls WP-B noch nicht gemergt: kein Problem,
WP-D fasst invitation_service.py NICHT an.

Lies zuerst: den Plan (WP-D), core/purge.py, repositories/account_repository.py,
migrations/0012_status_history.sql, 0017_workspace_invitation.sql; grep -rn "purge" apps/api/tests.

Setze um (Purge läuft als Owner → darf UPDATE trotz Append-only-REVOKE aus WP-A):
1. purge_account_data: status_history.changed_by und audit_log.actor_id des gelöschten Users auf
   Sentinel '00000000-0000-0000-0000-000000000000' anonymisieren (nicht löschen). entitlement_history
   BEWUSST NICHT anfassen (gesetzliche Aufbewahrung §14b UStG, ADR-0031).
2. Neue Methode cleanup_expired_invitations() in account_repository.py + Aufruf in core/purge.py:
   workspace_invitation mit Klartext-email bereinigen, sobald accepted_at IS NOT NULL OR expires_at
   < now() (Schema vorher prüfen).
3. PurgeResult um Zähler erweitern.
4. Purge-Test: nach Purge sind changed_by/actor_id = Sentinel, abgelaufene Invitations ohne
   Klartext-Email, entitlement_history unverändert.

Branch feat/compliance-wp-d. DoD: Python-DoD grün. Pushen, Draft-PR, Change-Log in Abschnitt 7.
```

### Prompt WP-E
```
Du bist Coder im Repo who2be. Aufgabe: WP-E aus
.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md — GDPR-Export um GoTrue-Profildaten
(Art. 15). Unabhängig von WP-A.

Lies zuerst: den Plan (WP-E), services/gdpr_export_service.py, repositories/me_repository.py:95-119
(Muster für auth.users-Zugriff, robust gegen fehlende auth.users in Test-DB).

Setze um: einen account/identity-Block im Export ergänzen (email + ggf. created_at/last_sign_in_at/
Provider aus auth.users), RLS-konforme Workspace-Iteration unverändert lassen, sauber zu null
degradieren wenn auth.users fehlt. Test: Export enthält den Block mit Email (gestubbte auth.users),
degradiert sauber.

Nur services/gdpr_export_service.py + Test anfassen. Branch feat/compliance-wp-e. DoD:
uv run ruff check . && uv run mypy . && uv run pytest -q grün. Pushen, Draft-PR, Change-Log Abschnitt 7.
```

### Prompt WP-F
```
Du bist Coder im Repo who2be. Aufgabe: WP-F aus
.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md — MFA für administrative Zugänge.
Unabhängiges Paket. Bei Bedarf in F1 (Backend-Gate) und F2 (Frontend-Enrollment) splitten.

Lies zuerst: den Plan (WP-F), core/security.py (require_role/JWT-Auswertung), docker-compose.yml +
docker-compose.cloud.yml + deploy/hetzner/** (GoTrue v2.158.1 Env), apps/web/src/features/settings/**,
docs/frontend/design-language.md (Pflichtlektüre vor UI-Änderung).

Setze um:
1. GoTrue-MFA/TOTP per Env aktivieren (GOTRUE_MFA_* in compose + .env.example + deploy), Variablen
   gegen die GoTrue-Version verifizieren.
2. Backend: JWT aal-Claim auswerten; zentrale Hilfsfunktion require_aal2, an alle Admin-Mutationen
   (require_role(ctx, admin)) hängen → 403 ohne AAL2.
3. Frontend: MFA-Sektion in features/settings (TOTP enroll/verify/list/unenroll via GoTrue /factors),
   shadcn-Primitives, Tokens, react-hook-form+zod.
4. Doku: RUNBOOK/docs um Admin-MFA-Pflicht ergänzen.
5. Tests: Admin-Mutation mit aal1 → 403, mit aal2 → ok; Web-Komponente rendert + axe grün.

Branch feat/compliance-wp-f. DoD: Python-DoD UND Web-DoD (npm run lint && npx tsc -b && npm test &&
npm run build) grün. Pushen, Draft-PR, Change-Log Abschnitt 7. Bei Design-Weichen: drei Optionen
mit Trade-offs rückfragen statt still entscheiden.
```

### Prompt WP-G
```
Du bist Coder im Repo who2be. Aufgabe: WP-G aus
.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md — Infra-Härtung & Supply-Chain.
Unabhängig.

Lies zuerst: den Plan (WP-G), .github/workflows/ci.yml (vorhandener audit-Job), deploy/hetzner/RUNBOOK.md,
deploy/hetzner/README.md, docker-compose.yml (Volume db-data).

Setze um:
1. .github/dependabot.yml: pip/uv (Python), npm (apps/web), github-actions, docker; wöchentlich,
   gruppiert, Labels. Ergänzt den audit-Job, ersetzt ihn nicht.
2. RUNBOOK (+ README): Verfahren für At-Rest-Verschlüsselung des Postgres-Volumes (LUKS/verschlüsseltes
   Hetzner-Volume) + reproduzierbarer Verifikationsschritt (lsblk/cryptsetup status). Keine Secrets ins Repo.
3. Hetzner-RZ-Standort (DE/FI) dokumentieren; Auftragsverarbeiter-Liste (Hetzner, Mollie, Mail) für AVV/VVT.
4. Optional: docs/compliance/c5-mapping.md (Mandantentrennung/OPS-18/IAM/CRY → Belege).

Branch feat/compliance-wp-g. DoD: dependabot.yml valide, RUNBOOK-Abschnitt + Verifikationsschritt
vorhanden, keine Secrets. Pushen, Draft-PR, Change-Log Abschnitt 7.
```

### Prompt WP-H
```
Du bist Coder im Repo who2be. Aufgabe: WP-H aus
.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md — Compliance-Dokumente. Unabhängig
(referenziert Entscheidungen aus WP-A/C/D — ADR-0031).

Lies zuerst: den Plan (WP-H), die Migrationen in apps/api/src/who2be_api/migrations/ + packages/models
(Datenkategorien ableiten), packages/billing (Mollie-Rolle), core/purge.py + account_repository.py
(Lösch-/Retention-Realität), deploy/hetzner/scripts/backup.sh (Backup-Retention).

Lege docs/compliance/ an:
1. vvt.md — Verzeichnis Verarbeitungstätigkeiten (Art. 30), Datenkategorien aus Schema, Empfänger/
   Auftragsverarbeiter (Hetzner, Mollie, self-hosted GoTrue, Mail), Drittland, Löschfristen,
   <Platzhalter> für Betreiber-Angaben.
2. gobd-verfahrensdokumentation.md — Beleg-/Buchungsfluss: Mollie als PSP, org_entitlement (Stand) +
   entitlement_history (Journal), Aufbewahrung §14b UStG/§147 AO, keine eigene Rechnungsausstellung
   (E-Rechnung nicht einschlägig). USt-IdNr/Reverse-Charge als offene Betreiber-Frage vermerken.
3. data-retention-and-erasure.md — 30-Tage-Grace + Hard-Purge, Anonymisierung überlebender Audit-
   Referenzen (WP-D), restic-Backup-Retention + Restore-only-Re-Deletion, Ausnahme entitlement_history.
4. README.md — Einstieg + Verweis auf Notion-Composite und diesen Plan.

Jedes Dokument mit Disclaimer (keine Rechts-/Steuerberatung), Betreiber-Platzhalter eindeutig markiert,
keine erfundenen Rechtsaussagen. Branch feat/compliance-wp-h. DoD: Dokumente vollständig, Querverweis
ADR-0031. Pushen, Draft-PR, Change-Log Abschnitt 7.
```

### Prompt WP-I
```
Du bist Coder im Repo who2be. Aufgabe: WP-I aus
.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md — Legal-Struktur (AGB B2B/B2C,
Signup-Consent, SLA) + Betreiber-Checkliste. Unabhängig. KEINE erfundenen Rechtstexte.

Lies zuerst: den Plan (WP-I), docs/frontend/design-language.md (Pflicht vor UI-Änderung),
apps/web/src/features/legal/** (Placeholder-Komponente, ImpressumPage, PrivacyPage, TermsPage, DpaPage),
apps/web/src/features/auth/** (Signup), apps/web/src/app/routes.tsx, components/layout/Footer.tsx.
Lint-Gates beachten: nur Primitives aus @/components/ui/* (kein nacktes <button>/<input>/<a>).

Setze um:
1. TermsPage: AGB strukturell B2B vs. B2C trennen, Widerrufsbelehrung-Block (Verbraucher), Hinweis
   „elektronische Rechnung — Empfängerzustimmung (B2C)“. Inhalte bleiben markierte <Placeholder>.
2. Signup-Consent: Pflicht-Checkbox „AGB & Datenschutz akzeptiert“ mit Links auf /legal/agb und
   /legal/datenschutz; Submit erst bei Zustimmung (react-hook-form + zod, Checkbox aus @/components/ui/*).
3. SLA-Abschnitt/-Seite (Verfügbarkeit/Reaktionszeiten) als Gerüst; falls eigene Seite: Route +
   Footer-Link. Werte als Platzhalter.
4. docs/compliance/legal-texts-checklist.md: exakt auflisten, welche Inhalte Impressum (§5 DDG) und
   Datenschutzerklärung noch brauchen.

WICHTIG: korrekte Verweise nicht zerstören — § 5 DDG (nicht TMG) und TDDDG (nicht TTDSG) müssen
erhalten bleiben. Branch feat/compliance-wp-i. DoD: Web-DoD grün, Signup blockt ohne Consent, axe grün.
Pushen, Draft-PR, Change-Log Abschnitt 7. Bei Design-Weichen drei Optionen rückfragen.
```

---

## 7 · Change-Log (von den ausführenden Agenten zu pflegen)

> Jeder WP-Agent trägt hier nach Abschluss eine Zeile ein: `YYYY-MM-DD — WP-x — <PR-Link/Branch> —
> Kurzbeschreibung + DoD-Status`. Spiegelbild kurz nach Notion-Projekt-`## Notes` (Coder-Doku-Konvention).

- 2026-06-05 — **WP-F** — Branch `claude/lucid-allen-lFw4Z` (Draft-PR) — MFA für
  administrative Zugänge. GoTrue-TOTP per Env aktiviert
  (`GOTRUE_MFA_TOTP_ENROLL_ENABLED`/`VERIFY_ENABLED`/`MAX_ENROLLED_FACTORS`,
  verifiziert gegen GoTrue v2.158.1 — kein Top-Level `GOTRUE_MFA_ENABLED`) in
  `docker-compose.yml`, `docker-compose.cloud.yml` (vererbt), `deploy/hetzner/supabase/docker-compose.yml`
  + beide `.env.example`. Backend: `aal`-Claim ausgewertet
  (`verify_supabase_jwt`), zentrale Hilfsfunktion `require_aal2` an
  `require_role(ctx, admin)` gehängt → 403 ohne AAL2. **Design-Entscheidungen
  (mit Betreiber abgestimmt):** API-Token exempt (Maschinen-Pfad), fehlender
  `aal`-Claim fail-open (nur expliziter Nicht-aal2-Wert blockt — produktive
  GoTrue-JWTs tragen `aal` immer). Frontend: MFA-Sektion in der Konto-Security-
  Card (`features/settings/components/MfaSection.tsx`, TOTP enroll/verify/list/
  unenroll via `supabase.auth.mfa`), keine neue Route. Doku: `docs/mfa-admin.md`.
  Tests: `test_mfa_aal2.py`, `test_security.py` (aal-Claim), `MfaSection.test.tsx`
  + `MfaSection.a11y.test.tsx`. **DoD grün:** ruff/mypy/pytest (553 passed) +
  Web lint/tsc/test (357 passed)/build. Grenzen eingehalten (von `apps/api` nur
  `core/security.py`; RUNBOOK/routes.tsx/auth/legal nicht angefasst).
- 2026-06-05 — WP-A — `feat/compliance-backend` — Migrationen 0044 (Append-only/audit_log) + 0045 (entitlement_history, ohne FK auf organization → GoBD-Aufbewahrung); ADR-0031; `test_audit_append_only.py` belegt Privileg-Split; DoD grün.
- 2026-06-05 — WP-B — `feat/compliance-backend` — `audit_log_repository` + `audit_service` neu; Wiring für member.role_changed/removed (in-Tx), token.issued/revoked, invitation.issued/revoked, account.deletion_requested, org.soft_deleted; PG-Advisory-Lock `ws_admins:<ws_id>` serialisiert parallele Admin-Drops; `test_audit_service.py` mit Fake-Repo + Race-Integrationstest; DoD grün.
- 2026-06-05 — WP-C — `feat/compliance-backend` — `entitlement_repository.upsert` schreibt SSoT + `entitlement_history`-Journal atomar in einer Transaktion; `test_entitlement_history.py` belegt 3 Journalzeilen (free→pro→manual_override) und Survival nach Org-Delete; DoD grün.
- 2026-06-05 — WP-D — `feat/compliance-backend` — `purge_account_data` anonymisiert `status_history.changed_by`/`audit_log.actor_id` auf Sentinel `00000000-…`; `cleanup_expired_invitations` redacted Klartext-`email` accepted/expired Invitations; `PurgeResult` zählt anonymisierte Zeilen + Invitations; `test_purge_erasure.py` deckt Anonymisierung + Cleanup + Retention von `entitlement_history` ab; DoD grün.
- 2026-06-05 — WP-E — `feat/compliance-backend` — `gdpr_export_service.export` ergänzt `account`-Block (id/email/created_at/last_sign_in_at aus `auth.users`, robust gegen fehlendes Schema); `test_gdpr_export_account.py` (Unit) + `test_gdpr_export.py` (Integration) decken Block ab; DoD grün.

---

## 8 · Offene Entscheidungen für den Betreiber (nicht Code)

1. **Rechtstext-Inhalte** (Impressum, Datenschutzerklärung, AVV) — Anwalt. WP-I liefert die Checkliste.
2. **Vertriebsmodell / USt:** Wer stellt die umsatzsteuerlich maßgebliche Rechnung an B2B-Kunden aus
   (Mollie-Receipt vs. ordnungsgemäße Rechnung)? Davon hängt ab, ob F3 (USt-IdNr/Reverse-Charge) und
   F4 (E-Rechnung) Code-Arbeit werden.
3. **C5:** Orientierung vs. angestrebtes Testat (Wirtschaftsprüfer) — bestimmt die Tiefe von WP-G.
4. **Backup-Erasure-Verfahren:** Restore-only-Re-Deletion bestätigen (WP-H dokumentiert den Vorschlag).
