#!/usr/bin/env bash
# Who2Be-Backup — verschluesselter pg_dump (C5a) + optionaler restic-Offsite-Sync (C5b).
#
# Pflicht-Env:
#   POSTGRES_HOST, POSTGRES_USER, POSTGRES_DB, PGPASSWORD
#   BACKUP_GPG_RECIPIENT      — GPG-Key-ID oder Email; pg_dump-Strom wird damit verschluesselt
#
# Optional:
#   BACKUP_DIR                — Default /var/backups/who2be (Volume-Mount im Compose)
#   RESTIC_REPOSITORY         — leer = lokal-only; sftp:user@host:/path fuer Hetzner-Storage-Box
#   RESTIC_PASSWORD           — Pflicht wenn RESTIC_REPOSITORY gesetzt ist
#   RESTIC_SSH_KEY            — Pfad zum SSH-Key fuer SFTP-Backend (Default /secrets/storage_box_ed25519)
#
# Retention:
#   lokal:   dumps aelter als 7 Tage geloescht
#   restic:  keep-daily 7 / keep-weekly 4 / keep-monthly 6 + prune
#
# Trigger (Host-Cron auf Hetzner, dokumentiert im RUNBOOK):
#   15 3 * * * cd /opt/who2be && docker compose --profile backup run --rm backup

set -euo pipefail

: "${POSTGRES_HOST:?required}"
: "${POSTGRES_USER:?required}"
: "${POSTGRES_DB:?required}"
: "${PGPASSWORD:?required}"
: "${BACKUP_GPG_RECIPIENT:?required}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/who2be}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="${BACKUP_DIR}/dump-${ts}.pgc.gpg"

mkdir -p "${BACKUP_DIR}"

log() { printf '[backup] %s\n' "$*"; }

# --- C5a: lokal verschluesselter Custom-Format-Dump ----------------------
log "pg_dump ${POSTGRES_DB}@${POSTGRES_HOST} → gpg(${BACKUP_GPG_RECIPIENT}) → ${out}"
pg_dump -Fc -h "${POSTGRES_HOST}" -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
  | gpg --batch --yes --trust-model always \
        --encrypt --recipient "${BACKUP_GPG_RECIPIENT}" \
        --output "${out}"

if [[ ! -s "${out}" ]]; then
  log "FATAL: dump-File ist leer"
  exit 1
fi
log "dump erstellt ($(stat -c %s "${out}") bytes)"

log "lokale Retention: dumps aelter als 7 Tage loeschen"
find "${BACKUP_DIR}" -maxdepth 1 -name 'dump-*.pgc.gpg' -mtime +7 -delete

# --- C5b: Offsite via restic ---------------------------------------------
if [[ -z "${RESTIC_REPOSITORY:-}" ]]; then
  log "RESTIC_REPOSITORY leer — Offsite-Sync uebersprungen (lokal-only Modus)"
  exit 0
fi

: "${RESTIC_PASSWORD:?required when RESTIC_REPOSITORY is set}"
export RESTIC_REPOSITORY RESTIC_PASSWORD

# SFTP-Backend: SSH-Key + StrictHostKeyChecking-Schalter via sftp.args.
ssh_args=""
if [[ "${RESTIC_REPOSITORY}" == sftp:* ]]; then
  RESTIC_SSH_KEY="${RESTIC_SSH_KEY:-/secrets/storage_box_ed25519}"
  if [[ -r "${RESTIC_SSH_KEY}" ]]; then
    ssh_args="-i ${RESTIC_SSH_KEY} -o StrictHostKeyChecking=accept-new"
    log "restic SFTP via ${RESTIC_SSH_KEY}"
  else
    log "FATAL: RESTIC_SSH_KEY unleserlich: ${RESTIC_SSH_KEY}"
    exit 1
  fi
fi

restic_cmd() {
  if [[ -n "${ssh_args}" ]]; then
    restic "$@" -o "sftp.args=${ssh_args}"
  else
    restic "$@"
  fi
}

# Idempotenter Init beim ersten Lauf.
if ! restic_cmd cat config >/dev/null 2>&1; then
  log "restic init (Erst-Anlage des Repos)"
  restic_cmd init
fi

# restic-Backup und restic-Forget sind nicht-fatal: lokaler Dump bleibt erhalten,
# wenn die Offsite-Box temporaer nicht erreichbar ist. Cron-Lauf wirft die Fehler
# trotzdem als Nicht-Null in den Stderr-Logs aus (siehe `|| log`).
log "restic backup ${BACKUP_DIR}"
restic_cmd backup "${BACKUP_DIR}" --tag dump --host who2be-prod \
  || { log "WARN: restic backup failed (non-fatal, lokal-Dump bleibt erhalten)"; exit 0; }

log "restic forget (keep-daily 7 / keep-weekly 4 / keep-monthly 6 + prune)"
restic_cmd forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune \
  || log "WARN: restic forget failed (non-fatal)"

log "fertig ✓"
