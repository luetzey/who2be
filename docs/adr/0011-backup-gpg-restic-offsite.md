# ADR-0011 — Backup: GPG-verschluesselter Dump + restic auf Hetzner Storage Box

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), MS-2 C5 / Plan-Review 2026-05-26

## Kontext

Der urspruengliche MS-2-C5-Plan sah `pg_dump` nach `/var/backups/who2be`
mit 7-Tage-Retention vor — alle Backups auf demselben Host wie die
Datenbank. Bei Host-Kompromittierung oder Hardware-Verlust gehen Daten
und Backups gemeinsam verloren. Fuer eine self-hosted AgentDB mit
versioniertem Prompt-Engineering ist das Risiko zu hoch.

## Optionen

- **A — Lokal-only (Status-quo-Plan).** Einfach, null Drittabhaengigkeit;
  kein Schutz gegen Host-Loss/Compromise. RPO 24h / RTO ≤30min nur,
  solange der Host lebt.
- **B — Lokal + Offsite (Hetzner Storage Box, restic, GPG).** Lokaler
  `pg_dump -Fc` wird mit GPG verschluesselt, `restic backup` synct
  inkrementell + deduplizert ins Hetzner-Storage-Box-Repo. Drittsystem
  ist im selben Hetzner-RZ → kein Egress-Cost. RPO 24h / RTO ≤2h.
- **C — Managed Postgres (Hetzner Managed DB / Supabase Cloud).**
  Backups, PITR und Patching outsourced. Bricht das "self-hosted"-
  Outcome des Projekts und kostet dauerhaft ≥ €30/Monat.

## Entscheidung

**B — GPG-encrypted Dump + restic auf Hetzner Storage Box.**

- `deploy/hetzner/scripts/backup.sh` macht
  `pg_dump -Fc | gpg --batch --yes -e -r <recipient>` → lokale Datei
  `/var/backups/who2be/dump-<ts>.pgc.gpg`, anschliessend
  `restic -r sftp:storagebox:/who2be backup /var/backups/who2be`.
- Retention: `restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6`.
- Cron taeglich 03:15 UTC im Compose-Stack (separater `backup`-Container
  oder Host-Cron, je nach Hetzner-Setup; Entscheidung in der konkreten
  C5b-Task).
- GPG-Public-Key wird per Secrets-File in den Container injiziert;
  Private-Key liegt **nicht** auf dem Host (Restore erfordert
  Operator-Key) — verhindert, dass ein kompromittierter Host die
  Backup-Inhalte entschluesseln kann.
- restic-Repo-Passphrase + Storage-Box-Credentials liegen im selben
  Secrets-File, eigene Sektion (`STORAGE_BOX_*`).
- `deploy/hetzner/scripts/restore.sh` macht den inversen Pfad gegen
  eine leere Test-DB; ist Vertrag fuer MS-3 H4 (produktiver Drill).

## Konsequenzen

- Neue Secrets-Eintraege: `STORAGE_BOX_HOST`, `STORAGE_BOX_USER`,
  `STORAGE_BOX_PASSWORD` (oder SSH-Key), `RESTIC_PASSWORD`,
  `BACKUP_GPG_RECIPIENT` (Key-ID).
- Operator muss den GPG-Private-Key sicher off-host verwahren — wird
  als RUNBOOK-Schritt dokumentiert.
- restic dedupliziert: 30 Tage Backups passen typischerweise in
  < 5 GB Storage-Box-Quota fuer eine kleine AgentDB.
- Restore-Drill (MS-3 H4) ist Pflicht — ohne dokumentierte
  Restore-Probe ist ein Backup ein Gefuehl, kein Wiederherstellungspfad.
- Secret-Rotation der Storage-Box-Credentials ist in MS-3 H8
  beschrieben (gemeinsame Rotation-Runbook).
</content>
</invoke>