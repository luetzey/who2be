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
#   BACKUP_HEARTBEAT_URL      — Dead-Man's-Switch (#541). Leer = aus (Default, Verhalten
#                               unveraendert). Wird NUR bei vollstaendigem Erfolg gepingt;
#                               alarmiert wird durch das AUSBLEIBEN des Pings. Der
#                               Empfaenger ist self-hosted — kein externer Dienst, damit
#                               kein Auftragsverarbeiter und kein VVT-Eintrag entsteht
#                               (Owner-Entscheidung 2026-09-21). RUNBOOK → "Alarmweg".
#   BACKUP_HEARTBEAT_TIMEOUT  — Sekunden fuer den Ping (Default 10)
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
BACKUP_HEARTBEAT_URL="${BACKUP_HEARTBEAT_URL:-}"
BACKUP_HEARTBEAT_TIMEOUT="${BACKUP_HEARTBEAT_TIMEOUT:-10}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="${BACKUP_DIR}/dump-${ts}.pgc.gpg"

mkdir -p "${BACKUP_DIR}"

log() { printf '[backup] %s\n' "$*"; }

# --- Dead-Man's-Switch (#541) --------------------------------------------
# Pingt den self-hosted Empfaenger — NUR bei vollstaendigem Erfolg, als letzte
# Aktion des Laufs. Alarmiert wird durch das AUSBLEIBEN des Pings: das faengt
# zusaetzlich die Faelle, die ein Exit-Code prinzipiell nicht fangen kann
# (Cron deaktiviert, Container weg, Host aus).
heartbeat_tool=""
if [[ -n "${BACKUP_HEARTBEAT_URL}" ]]; then
  if command -v curl >/dev/null 2>&1; then
    heartbeat_tool="curl"
  elif command -v wget >/dev/null 2>&1; then
    heartbeat_tool="wget"
  else
    # Bewusst frueh und hart: ein Alarmweg, der erst nach dem pg_dump am
    # fehlenden Werkzeug scheitert, ist genau die stille Luecke aus #541.
    log "FATAL: BACKUP_HEARTBEAT_URL gesetzt, aber weder curl noch wget vorhanden"
    exit 1
  fi
fi

heartbeat_ok() {
  [[ -n "${BACKUP_HEARTBEAT_URL}" ]] || return 0
  log "heartbeat → ${BACKUP_HEARTBEAT_URL}"
  case "${heartbeat_tool}" in
    curl)
      curl --silent --show-error --fail \
           --max-time "${BACKUP_HEARTBEAT_TIMEOUT}" --retry 3 \
           -o /dev/null "${BACKUP_HEARTBEAT_URL}"
      ;;
    wget)
      wget --quiet --timeout="${BACKUP_HEARTBEAT_TIMEOUT}" --tries=3 \
           -O /dev/null "${BACKUP_HEARTBEAT_URL}"
      ;;
  esac
}

# Ein stummer Alarmweg ist derselbe Fehler wie ein stummer Backup-Fehlschlag:
# schlaegt der Ping fehl, ist der Lauf rot, obwohl die Daten gesichert sind.
heartbeat_or_fail() {
  heartbeat_ok && return 0
  log "FATAL: heartbeat-Ping fehlgeschlagen — Backup-Daten sind gesichert,"
  log "       aber der Alarmweg ist stumm (${BACKUP_HEARTBEAT_URL})"
  return 1
}

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
  heartbeat_or_fail || exit 1
  log "fertig ✓"
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

# restic-Backup und restic-Forget waren bis 2026-09-21 bewusst NICHT-FATAL: der
# lokale Dump sollte erhalten bleiben, wenn die Offsite-Box temporaer nicht
# erreichbar ist (ADR-0011, C5a/C5b).
#
# REVISION 2026-09-21 (Issue #541, Owner-Entscheidung, ADR-0011 Nachtrag):
# Die Zusage "lokaler Dump bleibt erhalten" gilt unveraendert — der Dump oben ist
# zu diesem Zeitpunkt bereits geschrieben und wird hier nicht mehr angefasst.
# Weggefallen ist nur die ERFOLGSMELDUNG: ein gescheiterter Offsite-Sync beendet
# den Lauf mit Exit != 0, weil die alte Fassung den Fehlschlag so still machte,
# dass ein monatelang fehlendes Offsite-Backup erst beim Restore auffiel. Die
# alte Entscheidung stammt aus der Zeit vor einer Betriebs-Alarmierung; beides
# — lokaler Pfad UND ehrlicher Exit-Code — ist gleichzeitig erreichbar.
log "restic backup ${BACKUP_DIR}"
if ! restic_cmd backup "${BACKUP_DIR}" --tag dump --host who2be-prod; then
  log "FATAL: restic backup fehlgeschlagen — KEIN Offsite-Backup aus diesem Lauf"
  log "       lokaler Dump bleibt erhalten: ${out}"
  log "       restic forget uebersprungen (ohne neuen Snapshot sinnlos)"
  exit 1
fi

log "restic forget (keep-daily 7 / keep-weekly 4 / keep-monthly 6 + prune)"
if ! restic_cmd forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune; then
  log "FATAL: restic forget fehlgeschlagen — Snapshot liegt offsite, aber die"
  log "       Retention greift nicht (Repo laeuft langfristig voll)"
  log "       lokaler Dump bleibt erhalten: ${out}"
  exit 1
fi

# Erst hier ist der Lauf vollstaendig — nur jetzt darf der Dead-Man's-Switch
# gepingt werden.
heartbeat_or_fail || exit 1

log "fertig ✓"
