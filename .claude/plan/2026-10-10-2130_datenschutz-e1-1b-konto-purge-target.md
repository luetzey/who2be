# Datenschutz E1-1b: Konto-Purge anonymisiert `audit_log.target`

Karte: t_aeb14a3f (Kanban, Rund machen). Befund t_cd986568 aus Review #911.
Owner E1a (2026-10-10), PM: gilt sinngemaess fuer den Konto-Purge.

## Completion-Condition

- Nach `purge_account_data(user)` steht die User-UUID weder in
  `audit_log.actor_id` noch in `audit_log.target` noch als Wert in
  `audit_log.detail` — belegt fuer `account.deletion_requested`,
  `member.role_changed`, `member.removed` (plus `memory.user_purged`, das
  ebenfalls `target=<user_id>` schreibt).
- Aktion, Scope, Zeitpunkt und die Allowlist-Schluessel von `detail` bleiben;
  `target` wird Sentinel (nicht NULL).
- Zeilen anderer Personen bleiben unveraendert; `anonymized_at` bleibt NULL
  (der Workspace lebt, die 12-Monats-Frist aus E1-2 gilt hier nicht).
- `who2be_app` hat weiterhin kein UPDATE auf `audit_log` (Test).
- Rot-Probe: ohne den Fix ist der neue Test rot.
- DoD aus CONTRIBUTING.md gruen.

## Entscheidungen (belegt)

- **Ein UPDATE statt zwei:** `actor_id`, `target` und `detail` in einer
  Anweisung, damit eine Zeile mit Akteur = Ziel (`account.deletion_requested`)
  im Rueckgabe-Zaehler nur einmal zaehlt (bestehende Tests zaehlen exakt).
- **`target` generisch per Wert**, nicht per Aktionsliste: jede Aktion, die
  die User-ID als Ziel schreibt, ist erfasst, auch kuenftige.
- **`detail` ueber `w2b_audit_anonymized_detail` (0106)** fuer Zeilen, deren
  Ziel der User ist oder deren `detail` die User-ID irgendwo als Wert traegt
  (`jsonb_path_exists '$.** ? (@ == $u)'`). Zeilen, in denen der User nur
  Akteur ist, behalten ihr `detail` (wie bisher, Scope lebt).
- **Kein `anonymized_at`**: Anker der Retention fuer geloeschte Scopes (E1-2).
- **Keine Migration**: Purge laeuft als Owner, Funktion existiert seit 0106.

## Dateien (max. 6)

1. `apps/api/src/who2be_api/repositories/account_repository.py`
2. `apps/api/tests/test_audit_log_anonymization.py`
3. `docs/compliance/data-retention-and-erasure.md` (§2, §6)
4. `changelog.d/t-aeb14a3f-account-purge-audit-target.fixed.md`
5. dieser Plan
