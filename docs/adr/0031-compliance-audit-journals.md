# ADR-0031 — Compliance-Audit-Journale (Append-only, GoBD-Aufbewahrung)

- Status: Akzeptiert
- Datum: 2026-06-05
- Kontext: Compliance-Remediation DE/SaaS — Plan
  `.claude/plan/2026-06-05-1311_compliance-de-saas-remediation.md` (WP-A/B/C/D)
- Bezug: ADR-0028 (Entitlement-Schreibquellen), ADR-0029 (Build-Isolation
  Billing), Migrationen 0036 (App-Rolle), 0037 (RLS), 0012 (status_history),
  0030/0043 (org_entitlement)

## Kontext

Der Audit gegen das Notion-Composite *Compliance-Standards (DE/SaaS)* hat zwei
zusammenhaengende Luecken gefunden:

1. **`status_history` ist DB-seitig nicht append-only.** Migration 0036 vergibt
   `SELECT, INSERT, UPDATE, DELETE` an die Laufzeitrolle `who2be_app`. Ein
   Audit-Trail, der ueberschreibbar ist, ist kein Audit-Trail. Hinzu kommen
   bisher gar nicht protokollierte Admin-/Security-Events (Member-Rollenwechsel,
   Token/Invitation-Issue/Revoke, Account-/Org-Loeschung).
2. **`org_entitlement` ueberschreibt sich per UPSERT.** Damit existiert kein
   lueckenloses Zahlungs-/Tarif-Journal — ein GoBD-Mangel (Aufbewahrungs- und
   Unveraenderbarkeitspflicht buchungsrelevanter Vorgaenge, §§ 14b UStG, 147 AO).

Zugleich besteht ein Konflikt mit **DSGVO Art. 17 (Erasure)**: der Hard-Purge
(WP-D) muss Audit-Eintraege bereinigen koennen, ohne die Audit-Integritaet zu
zerstoeren — und finanzielle Journaleintraege duerfen er per gesetzlicher
Ausnahme **nicht** loeschen.

## Optionen

- **A — Application-Level-Audit-only.** Append-only nur im Code (Repository
  vergibt kein UPDATE/DELETE). Verworfen: nicht durchsetzbar, sobald jemand
  manuell SQL absetzt; widerspricht dem Defense-in-Depth-Ansatz von 0036/0037.
- **B — Trigger-basierte Unveraenderbarkeit.** `BEFORE UPDATE/DELETE`-Trigger,
  die jede Aenderung abweisen. Verworfen: Trigger sind in `pg_*`-System-Views
  nicht so klar wie Grants; Owner-Bypass muesste explizit codiert werden;
  schlechter zu reviewen.
- **C — Privileg-Split via `REVOKE` gegen `who2be_app`, Owner behaelt
  Vollzugriff (gewaehlt).** Saubere zweischichtige Verteidigung: die
  Laufzeitrolle kann nur INSERT, der Owner (Migrationen + `core/purge.py`) darf
  weiter UPDATE/DELETE — genau die Operation, die der DSGVO-Purge fuer die
  Anonymisierung braucht. Append-only ist damit per Privileg erzwungen.

## Entscheidung

### 1. Append-only fuer die Laufzeitrolle (`who2be_app`)

Migration **0044** (`0044_audit_append_only.sql`):

- `REVOKE UPDATE, DELETE ON status_history FROM who2be_app` — der Audit-Trail
  bestehender Status-Wechsel wird gegen die App-Rolle DB-seitig unveraenderbar.
- **Neue Tabelle `audit_log`** fuer Admin-/Security-Events
  (`member.role_changed`, `member.removed`, `token.issued`, `token.revoked`,
  `invitation.issued`, `invitation.revoked`, `account.deletion_requested`,
  `org.soft_deleted`). Grants: nur `SELECT, INSERT` an `who2be_app`.

Migration **0045** (`0045_entitlement_history.sql`): neues
`entitlement_history`-Journal (siehe Punkt 2), gleicher Grant-Schnitt.

Der **Owner** (Migrations-Runner und Purge-Job, beide ueber `DATABASE_URL`)
behaelt UPDATE/DELETE bewusst. Ohne diese Asymmetrie waere DSGVO-Erasure auf
ueberlebenden Audit-Referenzen nicht moeglich — siehe Punkt 3.

### 2. `entitlement_history` als unveraenderbares GoBD-Journal

`org_entitlement` bleibt die SSoT (aktueller Stand, einmal pro Org). Jede
Mutation (`upsert(...)` in `entitlement_repository.py`, WP-C) schreibt zusaetzlich
einen Journaleintrag — atomar in derselben Transaktion. Das Journal traegt:

- alle inhaltlichen Felder (`status`, `features`, `expires_at`,
  `mcp_monthly_quota`, `mcp_rate_per_min`, `grace_until`),
- die Herkunft (`source`, `external_ref`, `created_by`, `reason`),
- den Zeitpunkt (`recorded_at`).

`org_id` referenziert `organization` **ohne** `ON DELETE CASCADE`: das Journal
ueberlebt eine Org-Loeschung. Das ist der bewusste Retention-Konflikt zugunsten
der gesetzlichen Aufbewahrung (§ 14b UStG, § 147 AO) — die DSGVO erlaubt diese
Ausnahme. Operativ heisst das: bei einem Hard-Purge der Org bleiben die
Journalzeilen als verwaiste Org-ID stehen (siehe Punkt 3).

### 3. Erasure-Vertrag (DSGVO Art. 17) versus Audit-Integritaet

Der Hard-Purge (`core/purge.py`, WP-D) laeuft als Owner und

- **anonymisiert** `status_history.changed_by` und `audit_log.actor_id` auf den
  Sentinel `'00000000-0000-0000-0000-000000000000'` (nicht loeschen — die
  Reihenfolge der Wechsel bleibt nachweisbar);
- **bereinigt** abgelaufene/akzeptierte `workspace_invitation`-Zeilen
  (Klartext-`email` weg);
- **fasst `entitlement_history` bewusst nicht an** — gesetzliche Aufbewahrung
  gilt. Die personenbezogene Verknuepfung (`created_by`) wird zusammen mit dem
  GoTrue-User entfernt, das Journal bleibt org-bezogen vorhanden.

Dieser Konflikt ist explizit zugunsten der Aufbewahrungspflicht aufgeloest und
wird in `docs/compliance/data-retention-and-erasure.md` (WP-H) operativ
beschrieben.

## Konsequenzen

- App-Code, der bisher UPDATE/DELETE auf `status_history` versuchen koennte,
  bricht zur Laufzeit (`InsufficientPrivilege`). Aktuell ist nur ein
  INSERT-Pfad vorhanden (`status_history_repository.insert`).
- Neue Audit-Inserts (WP-B) gehen ueber `audit_log_repository.insert` — INSERT-only.
- `entitlement_repository.upsert` (WP-C) wird atomar erweitert (UPSERT + Journal-Insert
  in einer Transaktion). Cloud-Webhook-Pfad ist Owner — RLS irrelevant; App-Pfade
  setzen ohnehin `app.current_org` (siehe 0037).
- Schema-Migrationen bleiben idempotent: `REVOKE` ist no-op ohne vorheriges Grant,
  Tabellen via `IF NOT EXISTS`, Grants/Policies via `DROP IF EXISTS`+`CREATE`.
- Tests: `test_audit_append_only.py` (WP-A) beweist den Privileg-Split,
  `test_purge_*` (WP-D) belegen die Anonymisierung + Retention von
  `entitlement_history`.
