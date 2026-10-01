# C1b — Compliance-Naben fuer Gedaechtnis 2.0 (Kanban t_450c0bae)

Status: aktiv · Basis: origin/main 30b2f83d · ADR-0053 Anhang A.1 (Compliance), A.2 (C1b)

## Outcome

Fertig heisst: das in C1a (Migration 0091) eingefuehrte Nutzergedaechtnis
(`agent_memory.scope='user'`, `subject_user_id`) und die Historie
`agent_memory_event` sind in Auskunft (Art. 15/20) und Loeschung (Art. 17)
eingebunden, und VVT + Loeschkonzept beschreiben beides samt Verfallsfrist.

## Befund vor Beginn

`GdprExportService._export_workspace` liest `agent_memory` workspace-weit ohne
Filter. Seit 0091 liegen dort auch Nutzerfakten (`scope='user'`) — in einem
geteilten Workspace enthielte der Export von Nutzer A das Nutzergedaechtnis von
Nutzer B. Das widerspricht ADR-0053 3.1.1 (Inhalt nur fuer den Nutzer selbst)
und wird hier mit geschlossen.

## Schritte

1. Export (`services/gdpr_export_service.py`)
   - `agent_memories`: nur `scope='agent'`, Spaltenliste um die 0091-Spalten
     erweitert, je Eintrag `events` (Historie) verschachtelt.
   - neu `user_memories`: nur `scope='user' AND subject_user_id = <user>`,
     ebenfalls mit `events`.
2. Purge (`repositories/account_repository.py#purge_account_data`)
   - Nutzergedaechtnis des Users loeschen (`scope='user' AND subject_user_id`),
     je Zeile `audit_log` `memory.deleted` ohne Inhalt (Konstante aus
     `memory_repository`, Akteur NULL = System). Historie faellt per Cascade.
     Reihenfolge NACH dem Personal-Org-Delete: was dort per Cascade faellt,
     bekommt keine Audit-Zeile (Regel aus 0091, Kopf „Loeschkette Workspace").
   - Personenverweise in ueberlebenden Zeilen auf den Sentinel:
     `agent_memory.confirmed_by`, `agent_memory_event.actor_id` (nur
     `actor_kind='human'`) — Muster B1c (`test_case.created_by` nur bei human).
3. Tests (`tests/test_memory_compliance.py`, neu) gegen echte DB, je
   Zusicherung eine Rot-Probe (Mutation zurueckdrehen → Test rot).
4. Doku: VVT (V17, Datenkategorien, Loeschfristen), Loeschkonzept (§2, neuer
   §4c, §6). Verfall 30 Tage fuer unbestaetigte Eintraege (ADR 3.1.3, gesetzte
   Annahme Anhang B) — Verfall setzt `expired`, loescht NICHT; Job folgt in C2b.
5. Changelog-Fragment.

## Weichen (aus dem Repo entschieden)

- Akteur der Purge-Audit-Zeile: NULL. Beleg: `audit_log.actor_id` ist nullable
  „falls System-Events ohne Akteur entstehen" (0044). Die User-ID waere
  ohnehin im selben Lauf auf den Sentinel gesetzt worden.
- Keine Migration noetig (Schema ist C1a). PM-Reservierung 0094 bleibt frei.
- Anonymisierung `confirmed_by`/`actor_id`: gleiche Begruendung wie B1c — in
  fremden Workspaces ueberleben die Zeilen den Account.

## Verifikation

```bash
WHO2BE_REQUIRE_DB=1 uv run pytest apps/api/tests/test_memory_compliance.py \
  apps/api/tests/test_memory.py apps/api/tests/test_test_case_compliance.py \
  apps/api/tests/test_purge_erasure.py apps/api/tests/test_gdpr_export.py -q
```
plus volle DoD aus CONTRIBUTING.md.

## Out of Scope

Schema (C1a), Service-Logik/Verfallsjob (C2a/C2b).
