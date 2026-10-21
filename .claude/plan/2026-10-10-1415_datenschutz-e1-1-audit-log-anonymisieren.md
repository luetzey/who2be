# Datenschutz E1-1: audit_log beim Workspace-/Org-Purge anonymisieren

Karte t_d01cea8b. Basis `origin/main` @ `3583274b`. Owner-Entscheidung E1a
(2026-10-10): „Beim Loeschen bleiben Aktion, Zeitpunkt und Scope; Akteur, Ziel
und personenbezogene Details werden geleert. Nach 12 Monaten loescht der Worker
auch den anonymen Rest." Dieses Paket: nur die Anonymisierung. Die
12-Monats-Routine ist t_8ca9cda6.

## Ist

`audit_log` (0044) hat keinen FK auf `workspace`/`organization`. Nach
`DELETE /v1/workspaces/{id}` und nach `purge_organization` bleiben die Zeilen
mit `actor_id`, `target` und `detail` stehen
(`test_audit_log_survives_workspace_delete_and_org_purge_as_is`).

## Soll (Migration 0106)

- `w2b_audit_detail_allowlist()`: jsonb `{action: [erlaubte detail-Schluessel]}`.
  **Single Source of Truth.** Eine Aktion ohne Eintrag verliert beim
  Anonymisieren das ganze `detail` (fail-closed).
- `w2b_audit_anonymized_detail(action, detail)`: filtert `detail` auf die
  Allowlist. Ist `detail` kein Objekt, wird `{}` zurueckgegeben.
- Spalte `audit_log.anonymized_at timestamptz` (NULL = nicht anonymisiert).
  Sie ist der Anker fuer die 12-Monats-Routine, die damit ab der Loeschung
  zaehlen kann statt ab `created_at`.
- `AFTER DELETE`-Trigger auf `workspace` (Zeilen mit `workspace_id = OLD.id`)
  und auf `organization` (Zeilen mit `org_id = OLD.id`). Die Trigger setzen:
  `actor_id` auf den Sentinel `00000000-…` (NULL bleibt NULL), `target` auf
  NULL, `detail` auf den Allowlist-Filter und `anonymized_at` auf `now()`.
  `action`, `created_at`, `org_id` und `workspace_id` bleiben.
- Bestand: Zeilen, deren Workspace bzw. Org schon weg ist, werden einmalig
  genauso anonymisiert.

## Weichen (aus dem Repo entschieden)

- **Trigger statt FK.** E1a verlangt, dass der Scope bleibt. `ON DELETE SET
  NULL` wuerde ihn loeschen, `CASCADE` die ganze Zeile. Der Trigger greift auf
  jedem Loeschweg: API-Workspace-Delete, Org-Purge und Personal-Org im
  Konto-Purge. Das ist dieselbe Linie wie 0104/0105.
- **`SECURITY DEFINER`.** `DELETE /v1/workspaces/{id}` laeuft als
  `who2be_app`, und diese Rolle hat auf `audit_log` nur SELECT und INSERT
  (0044, append-only). Die Trigger-Funktion laeuft deshalb als Owner.
  Gehaertet wie 0090/0093: fester `search_path`, Tabellen schema-qualifiziert,
  EXECUTE fuer PUBLIC entzogen. Eine Trigger-Funktion ist nicht direkt
  aufrufbar, die App bekommt also kein allgemeines UPDATE-Recht.
- **Allowlist in SQL.** Die Durchsetzung passiert in der DB, also liegt die
  Allowlist dort. Eine Python-Kopie gibt es nicht. Der Guard-Test sammelt alle
  Aktionen aus dem Code (`action=`-Argumente, `*_AUDIT_ACTION`-Konstanten,
  INSERTs in Migrationen) und verlangt fuer jede einen Eintrag. Eine neue
  Aktion bekommt ihren Eintrag ueber eine neue Migration mit
  `CREATE OR REPLACE FUNCTION w2b_audit_detail_allowlist()`.
- **Konto-Loeschung unveraendert.** Gleiche Linie: Sentinel fuer `actor_id`.
  Der Konto-Purge anonymisiert weiterhin nur den Akteur, weil Workspace und
  Ziel dort weiter bestehen.

## Allowlist (behalten wird nur Nicht-Personenbezogenes)

| action | behaltene detail-Schluessel |
|---|---|
| member.role_changed | from, to |
| member.removed | role |
| invitation.issued | role |
| invitation.revoked | — |
| token.issued | role, via |
| token.renamed / token.rotated / token.revoked | — |
| token.role_capped | from_role, to_role, via |
| agent.model_config_changed | model_provider, model_name |
| account.deletion_requested / org.soft_deleted | purge_after |
| workarea.rules_reapplied | — |
| memory.deleted / case.deleted | — |
| memory.auto_policy.enabled / .disabled | row, origin |
| memory.user_purged | count |

Weggefiltert werden Freitext (Token-Name, Regel-Muster und -Kategorie) und
IDs von Agenten, Regeln und OAuth-Clients.

## Dateien (Budget 8)

1. `apps/api/src/who2be_api/migrations/0106_audit_log_anonymize_on_purge.sql` (neu)
2. `apps/api/tests/test_kb_chunk_workspace_erasure.py` (Ist-Test umgestellt)
3. `apps/api/tests/test_audit_log_anonymization.py` (neu: App-Rolle, Bestand, Allowlist, Guard)
4. `docs/compliance/data-retention-and-erasure.md`
5. `docs/compliance/vvt.md`
6. `changelog.d/t-d01cea8b-audit-log-anonymize.changed.md`
7. dieser Plan

## Verifikation

DoD aus CONTRIBUTING.md auf eigener DB `who2be_t_d01cea8b`.

- Rot vorher: der umgestellte Test ist auf main rot.
- Rot-Probe Guard: eine zusaetzliche `action="probe.x"` im Code macht den
  Guard rot.
- Rot-Probe Trigger: ohne den Workspace-Trigger wird der Test rot.

Fotos entfallen, die Aenderung hat keine sichtbare UI-Wirkung.
