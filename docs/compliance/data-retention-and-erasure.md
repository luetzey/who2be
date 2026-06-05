# Retention- & Loeschkonzept — Who2Be

> ⚠️ **Disclaimer:** Engineering-/Betriebs-Dokumentation, aus dem Loeschpfad
> (`core/purge.py`, `repositories/account_repository.py`), den Migrationen und
> dem Backup-Skript rekonstruiert. **Keine Rechtsberatung.** Fristen und
> Abwaegungen (insb. Aufbewahrung vs. Loeschung) sind rechtlich zu verifizieren.
> Alle `<PLATZHALTER: …>` sind vom Betreiber zu fuellen. Stand der abgeleiteten
> Fakten: 2026-06-05.

Dieses Dokument beschreibt, **wie lange welche Daten aufbewahrt** und **wie sie
geloescht** werden — und wie der Konflikt zwischen DSGVO-Loeschpflicht (Art. 17)
und gesetzlicher Aufbewahrung (GoBD/§147 AO) aufgeloest wird. Adressiert
Audit-Befund **P5**.

---

## 1 · Loesch-Lebenszyklus (Soft-Delete → Grace → Hard-Purge)

Who2Be loescht Konten und Organisationen **zweistufig**:

1. **Soft-Delete (Loeschwunsch):**
   - `DELETE /v1/me` → `request_account_deletion()`: schreibt
     `account_deletion (user_id, requested_at, purge_after = now() + 30 Tage)`.
   - `DELETE /v1/organizations/{id}` → `soft_delete_organization()`: setzt
     `organization.deleted_at = now()`, `organization.purge_after = now() + 30 Tage`.
   - Wirkung: Daten werden aus den Lese-Pfaden (`/v1/me`, `/v1/organizations`)
     **ausgeblendet**, bleiben aber zur **Wiederherstellung waehrend der Grace**
     physisch vorhanden.
2. **30-Tage-Grace:** Karenzzeit (Schutz vor versehentlicher Loeschung). Der
   `purge_after`-Zeitpunkt ist idempotent (mehrfacher Loeschwunsch behaelt den
   fruehesten Termin).
3. **Hard-Purge (`who2be-purge`, Cron):** `purge_expired()` laeuft als **Owner**
   (RLS-Bypass) und entfernt alles, dessen `purge_after <= now()`:
   - **Organisationen:** `DELETE FROM organization …` — per `ON DELETE CASCADE`
     atomar inkl. Workspaces → Personas/Playbooks/Resources/Agents (+ Versionen),
     `org_entitlement`, `mcp_usage`.
   - **Konten:** loescht `api_token`, `org_member`, `workspace_member`, die
     persoenliche Organisation des Nutzers und ruft die **GoTrue-Admin-API** zum
     Loeschen von `auth.users` (E-Mail/Auth-Daten). Erst nach bestaetigtem
     Auth-Delete wird `account_deletion.purged_at = now()` gesetzt
     (idempotenter Retry, falls der Auth-Call scheitert).

---

## 2 · Anonymisierung ueberlebender Audit-Referenzen (WP-D)

Einige Tabellen referenzieren `user_id`, ohne per CASCADE mitgeloescht zu werden
(append-only Audit-/Historie). Damit der **Personenbezug** entfernt wird, ohne
die **Audit-Integritaet** zu zerstoeren, anonymisiert der Hard-Purge diese
Referenzen auf einen Sentinel statt sie zu loeschen:

| Tabelle | Feld | Behandlung beim Purge |
|---|---|---|
| `status_history` | `changed_by` | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `audit_log` (WP-A/B) | `actor_id` | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `workspace_invitation` | `email` (Klartext) | Bereinigung bei `accepted_at IS NOT NULL OR expires_at < now()` (`cleanup_expired_invitations`) |

So bleibt nachvollziehbar, **dass** ein Statuswechsel/Audit-Ereignis stattfand,
aber nicht mehr **welche Person** dahinterstand. Diese Anonymisierung wird durch
**WP-D** umgesetzt (der Purge laeuft als Owner und darf trotz Append-only-REVOKE
aus WP-A das `UPDATE` ausfuehren).

> Hinweis: `audit_log`/`entitlement_history` sowie die Anonymisierungsschritte
> stammen aus den Schwester-Paketen **WP-A/B/D**; dieses Dokument beschreibt den
> Ziel-Stand (ADR-0031).

---

## 3 · Gesetzliche Ausnahme: `entitlement_history`

`entitlement_history` (Tarif-/Zahlungsjournal, Cloud-Edition) wird beim
Hard-Purge **bewusst nicht** geloescht oder anonymisiert:

- `org_id` ist **ohne** `ON DELETE CASCADE` modelliert — das Journal ueberlebt die
  Org-Loeschung.
- Rechtsgrundlage: gesetzliche Aufbewahrungspflicht (§14b UStG / §147 AO);
  Art. 17 Abs. 3 lit. b/e DSGVO erlaubt die Aufbewahrung trotz Loeschanspruch.
- Begruendung/Abwaegung dokumentiert in **ADR-0031** und der
  [GoBD-Verfahrensdokumentation](./gobd-verfahrensdokumentation.md).

`<PLATZHALTER: konkrete Aufbewahrungsfrist + Loeschung NACH Fristablauf>` — nach
Ablauf der gesetzlichen Frist ist auch dieses Journal zu loeschen; das Verfahren
dafuer ist vom Betreiber festzulegen.

---

## 4 · Backups & „Restore-only-Re-Deletion"

Backups (siehe `deploy/hetzner/scripts/backup.sh`,
[`RUNBOOK.md` §Backup & Restore](../../deploy/hetzner/RUNBOOK.md#backup--restore)):

| Pfad | Verfahren | Retention |
|---|---|---|
| Lokal (C5a) | `pg_dump -Fc \| gpg --encrypt` | Dumps aelter als **7 Tage** geloescht |
| Offsite (C5b) | `restic` via SFTP (Hetzner Storage-Box) | `keep-daily 7 / keep-weekly 4 / keep-monthly 6` + Prune |

**Problem:** Ein zwischen Loeschung und Backup-Ablauf gezogenes Backup enthaelt
noch die geloeschten Daten. Eine selektive Loeschung **innerhalb** verschluesselter,
inkrementeller Snapshots ist nicht praktikabel.

**Verfahren „Restore-only-Re-Deletion" (Vorschlag, vom Betreiber zu bestaetigen):**
- Backups werden **nicht** punktuell editiert.
- Personenbezogene Daten in Backups laufen ueber die **Retention** aus dem
  Snapshot-Fenster heraus (spaetestens nach ~6 Monaten / `keep-monthly 6`).
- **Wird** ein Backup im Loeschfenster tatsaechlich **wiederhergestellt**, ist die
  betroffene Loeschung **unmittelbar erneut auszufuehren** (der Hard-Purge bzw.
  die Anonymisierung wird auf der restaurierten Instanz wiederholt), bevor die
  Instanz wieder produktiv geht.
- Dokumentations-/Bestaetigungspflicht: `<PLATZHALTER: Bestaetigung des
  Verfahrens + maximale Backup-Verweildauer als verbindliche Aussage>`.

---

## 5 · Server-Logs / Zugriffsdaten

Reverse-Proxy-/App-Logs (IP, User-Agent, Zeitstempel) liegen ausserhalb der DB
(Caddy/Container-Logs). Retention/Loeschung: `<PLATZHALTER: konkrete Log-
Retention (z. B. 7–30 Tage) + Rotationsverfahren>`.

---

## 6 · Retention-Uebersicht (Kurzreferenz)

| Datenkategorie | Aufbewahrung | Loesch-/Anonymisierungsverfahren |
|---|---|---|
| Konto-/Inhalts-/Mitgliedsdaten | bis Loeschwunsch + 30 Tage Grace | Hard-Purge (CASCADE) inkl. `auth.users` |
| Einladungs-E-Mail (Klartext) | bis Annahme/Ablauf | `cleanup_expired_invitations` |
| `status_history.changed_by`, `audit_log.actor_id` | Eintrag dauerhaft | beim Purge **anonymisiert** (Sentinel) |
| `entitlement_history` | gesetzliche Frist (§147 AO/§14b UStG) | **keine** Loeschung im Purge; Loeschung erst nach Frist |
| Backups lokal / Offsite | 7 Tage / bis 6 Monate | Retention-Ablauf + Restore-only-Re-Deletion |
| Server-Logs | `<PLATZHALTER>` | Log-Rotation |

---

## 7 · Code-Referenzen (Stand 2026-06-05)

- `apps/api/src/who2be_api/core/purge.py` — `purge_expired()`, `PurgeResult`,
  CLI-Entrypoint `who2be-purge`.
- `apps/api/src/who2be_api/repositories/account_repository.py` —
  `request_account_deletion()`, `soft_delete_organization()`, Purge-Helper,
  (WP-D) `cleanup_expired_invitations()`.
- `apps/api/src/who2be_api/migrations/0038_account_org_lifecycle.sql` —
  `account_deletion`, Soft-Delete-Felder.
- `deploy/hetzner/scripts/backup.sh` — Backup-Retention.
- ADR-0031 — Append-only/Anonymisierung/Aufbewahrungs-Abwaegung.
