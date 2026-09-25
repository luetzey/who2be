#!/usr/bin/env bash
# Who2Be-Backup — alle drei Datenbestaende (C5a) + optionaler restic-Offsite-Sync (C5b).
#
# Gesichert wird, was ein Restore zusammen braucht (ADR-0011 Nachtrag 2026-09-25):
#   1. Postgres        — verschluesselter pg_dump (Katalog + Stammdaten)
#   2. Objekt-Store    — SeaweedFS-Bucket (ADR-0048); Postgres kennt davon nur den
#                        Katalog `wa_blob`. Ohne Objekte zeigen alle Blob-Referenzen
#                        eines Restores ins Leere.
#   3. Tabellen-Store  — SQLite je WorkArea (ADR-0049); Postgres kennt nur `wa_table`.
#                        Ohne diese Dateien liefert ein Restore leere Tabellen.
# Alle drei landen unter ${BACKUP_DIR} und damit in EINEM restic-Snapshot.
#
# Pflicht-Env:
#   POSTGRES_HOST, POSTGRES_USER, POSTGRES_DB, PGPASSWORD
#   BACKUP_GPG_RECIPIENT      — GPG-Key-ID oder Email; pg_dump-Strom wird damit verschluesselt
#
# Objekt-Store (Stufe 2) — Pflicht, ausser BACKUP_BLOBS=off:
#   BACKUP_BLOBS              — "off" schaltet die Stufe ab (On-Prem ohne Objekt-Store).
#                               JEDER andere Wert (inkl. leer) laesst sie PFLICHT sein:
#                               fehlende Konfiguration ist FATAL, nicht "uebersprungen".
#   WHO2BE_BLOBSTORE_ENDPOINT — host:port der S3-API (ohne Schema), z. B. seaweedfs:8333
#   WHO2BE_BLOBSTORE_ACCESS_KEY / WHO2BE_BLOBSTORE_SECRET_KEY
#   WHO2BE_BLOBSTORE_BUCKET   — Default who2be-blobs
#   WHO2BE_BLOBSTORE_SECURE   — "true" => https, sonst http (Default false, internes Netz)
#
# Tabellen-Store (Stufe 3) — Pflicht, ausser BACKUP_TABLESTORE=off:
#   BACKUP_TABLESTORE         — "off" schaltet die Stufe ab. Sonst Pflicht (s. o.).
#   WHO2BE_TABLESTORE_DIR     — Mount des API-Volumes, Default /data/tablestore.
#                               Der Mount ist bewusst NICHT read-only: eine
#                               WAL-SQLite laesst sich nur lesen, wenn ihr
#                               WAL-Index (<db>-shm) gemappt werden kann. Der
#                               Schreibschutz sitzt stattdessen in der
#                               Verbindung (file:<pfad>?mode=ro). Der Lesevorgang
#                               laeuft zudem unter der Kennung des Datei-
#                               Eigentuemers (su-exec), damit erzeugte
#                               WAL-Seitendateien nicht dem Backup-Nutzer
#                               gehoeren und der Schreibpfad der API unberuehrt
#                               bleibt — geprueft wird das je Area, siehe Stufe 3.
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
# Teilerfolg ist KEIN Erfolg (#541-Linie, W8/M3): scheitert eine der drei Stufen,
# endet der Lauf mit Exit != 0 und der Heartbeat bleibt aus. Der restic-Snapshot
# wird trotzdem geschrieben — aber mit --tag incomplete statt --tag dump, damit er
# sich beim Restore nicht als vollstaendiger Stand ausgeben kann.
#
# Retention:
#   lokal:   dumps aelter als 7 Tage geloescht. Blob-Spiegel und Tabellen-Snapshots
#            sind je GENAU EINE Kopie (in place ueberschrieben) — sie vervielfachen
#            sich NICHT mit der 7-Tage-Retention. Die Historie traegt restic.
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
BACKUP_BLOBS="${BACKUP_BLOBS:-on}"
BACKUP_TABLESTORE="${BACKUP_TABLESTORE:-on}"

BLOB_MIRROR_DIR="${BACKUP_DIR}/blobs"
TABLESTORE_SNAPSHOT_DIR="${BACKUP_DIR}/tablestore"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="${BACKUP_DIR}/dump-${ts}.pgc.gpg"

mkdir -p "${BACKUP_DIR}"

log() { printf '[backup] %s\n' "$*"; }

# --- Fehler-Sammler ------------------------------------------------------
# Die drei Datenstufen brechen NICHT beim ersten Fehler ab: scheitert der
# Blob-Sync, ist der Tabellen-Snapshot trotzdem einen Versuch wert — der
# Operator soll nach einem Lauf alle Baustellen kennen, nicht nur die erste.
# Gesammelt wird dennoch hart: jeder Eintrag hier macht den Lauf rot und
# verhindert den Heartbeat.
FAILURES=()
fail_stage() {
  FAILURES+=("$1")
  log "FEHLER: $1"
}

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

# --- Abschluss: Teilerfolg ist kein Erfolg -------------------------------
# Die einzige Stelle, an der dieses Skript mit 0 endet — und sie ist an eine
# LEERE Fehlerliste gebunden. Damit kann ein halbes Backup strukturell keinen
# gruenen Heartbeat ausloesen: der Ping haengt nicht an Disziplin beim
# Codelesen, sondern an dieser Bedingung.
finish() {
  if (( ${#FAILURES[@]} > 0 )); then
    log "FATAL: Backup UNVOLLSTAENDIG — ${#FAILURES[@]} Stufe(n) fehlgeschlagen:"
    local f
    for f in "${FAILURES[@]}"; do
      log "       - ${f}"
    done
    log "       KEIN Heartbeat — ein Teilerfolg darf nicht als Erfolg gemeldet werden."
    log "       lokaler Dump bleibt erhalten: ${out}"
    exit 1
  fi
  heartbeat_or_fail || exit 1
  log "fertig ✓ (Postgres + Objekt-Store + Tabellen-Store)"
  exit 0
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

# --- Stufe 2: Objekt-Store spiegeln (ADR-0048) ---------------------------
# Bis 2026-09-25 stand dieser Block als Handarbeit im RUNBOOK. Der naechtliche
# Lauf sicherte damit nur Postgres — ein Restore haette eine DB ergeben, deren
# Blob-Referenzen ins Leere zeigen. Der Spiegel liegt unter ${BACKUP_DIR} und
# faellt damit in denselben restic-Snapshot; ein zweites Repo braucht es nicht.
backup_blobs() {
  if [[ "${BACKUP_BLOBS}" == "off" ]]; then
    log "BACKUP_BLOBS=off — Objekt-Store bewusst abgewaehlt"
    return 0
  fi

  # Fehlende Konfiguration ist FATAL, nicht "uebersprungen": ein stilles
  # Ueberspringen waere genau die Luecke, die dieser Umbau schliesst.
  local endpoint="${WHO2BE_BLOBSTORE_ENDPOINT:-}"
  local access="${WHO2BE_BLOBSTORE_ACCESS_KEY:-}"
  local secret="${WHO2BE_BLOBSTORE_SECRET_KEY:-}"
  local bucket="${WHO2BE_BLOBSTORE_BUCKET:-who2be-blobs}"
  local missing=()
  [[ -n "${endpoint}" ]] || missing+=("WHO2BE_BLOBSTORE_ENDPOINT")
  [[ -n "${access}" ]]   || missing+=("WHO2BE_BLOBSTORE_ACCESS_KEY")
  [[ -n "${secret}" ]]   || missing+=("WHO2BE_BLOBSTORE_SECRET_KEY")
  if (( ${#missing[@]} > 0 )); then
    fail_stage "Objekt-Store nicht konfiguriert (${missing[*]}) — setze BACKUP_BLOBS=off, wenn dieser Stack keinen Objekt-Store hat"
    return 1
  fi
  if ! command -v aws >/dev/null 2>&1; then
    fail_stage "Objekt-Store: aws-cli fehlt im Backup-Image"
    return 1
  fi

  local scheme="http"
  [[ "${WHO2BE_BLOBSTORE_SECURE:-false}" == "true" ]] && scheme="https"

  mkdir -p "${BLOB_MIRROR_DIR}"
  log "s3 sync ${scheme}://${endpoint}/${bucket} → ${BLOB_MIRROR_DIR} (inkrementell)"

  # --delete raeumt im Spiegel, was im Bucket nicht mehr existiert — gewollt,
  # damit ein DSGVO-Purge nicht ueber das Backup wieder auflebt. Die
  # Snapshot-Historie haelt die Objekte bis zum Retention-Ablauf
  # ("Restore-only-Re-Deletion", Loeschkonzept §4).
  if ! AWS_ACCESS_KEY_ID="${access}" \
       AWS_SECRET_ACCESS_KEY="${secret}" \
       AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}" \
       aws --endpoint-url "${scheme}://${endpoint}" \
           s3 sync --delete "s3://${bucket}" "${BLOB_MIRROR_DIR}"; then
    fail_stage "Objekt-Store: s3 sync fehlgeschlagen (Bucket ${bucket} @ ${endpoint})"
    return 1
  fi

  log "Objekt-Spiegel: $(find "${BLOB_MIRROR_DIR}" -type f | wc -l | tr -d ' ') Objekte, $(du -sh "${BLOB_MIRROR_DIR}" | cut -f1)"
}

# --- Stufe 3: Tabellen-Store-Snapshots (ADR-0049) ------------------------
# Eine SQLite-Datei im WAL-Modus ist waehrend eines laufenden Imports kein
# konsistenter Stand — sie darf nicht einfach kopiert werden. `VACUUM INTO`
# laeuft als Leser in einer Transaktion und erzeugt eine kompaktierte,
# eigenstaendig lesbare Kopie; WAL-/SHM-Seitendateien werden nicht gebraucht.
#
# GRENZE (RUNBOOK → Tabellen-Store-Backup): der API-interne Area-Write-Lock
# (TableStore.snapshot_to) wirkt prozesslokal und wird hier NICHT gehalten. Ein
# fachlicher Vorgang ueber mehrere SQLite-Transaktionen kann deshalb mittendrin
# erwischt werden — das Ergebnis ist eine technisch intakte Datei mit einem
# fachlich halben Import, nie eine korrupte Datei.
#
# ZWEITE GRENZE — der Lauf darf den Schreibpfad der API nicht beruehren:
# Die Seitendateien einer WAL-Datenbank (<db>-wal, <db>-shm) entstehen BEIM
# OEFFNEN, auch bei einem reinen Leser und auch bei `mode=ro`. Die API oeffnet
# je Query eine kurzlebige Verbindung (tablestore/engine.py); nachts liegt der
# Store still, die Seitendateien existieren also in aller Regel NICHT — und
# damit legt sie der Backup-Prozess an, unter SEINER Kennung. Der Backup-
# Container laeuft als root, die API unter einer eigenen uid: danach stuenden
# fremde Seitendateien neben der Datenbank. Die API koennte weiter lesen, aber
# nicht mehr schreiben — ein stiller Fehlermodus, der erst auffiele, wenn ein
# Nutzer eine Tabelle aendern will.
#
# Gegenmittel, zwei Lagen:
#
# (a) Der Lesevorgang laeuft unter der Kennung des DATEI-EIGENTUEMERS (su-exec),
#     nicht unter der des Containers. Dann gehoeren erzeugte Seitendateien von
#     vornherein der API. Geloescht werden sie NICHT — ein paralleler Leser der
#     API koennte den WAL-Index gerade gemappt haben.
#
#     Warum nicht auf SQLite verlassen: SQLite zieht die Seitendateien zwar
#     selbst auf den Eigentuemer der Datenbank nach — aber nur, solange der
#     Prozess CAP_CHOWN besitzt (selbst gemessen: ohne die Capability bleiben
#     sie beim Backup-Nutzer haengen, und der naechste Schreibzugriff der API
#     scheitert). Diese Zusage darf nicht an einer Capability haengen, die
#     jemand berechtigterweise entzieht.
#
#     Warum nicht die Datei vorher kopieren: `cp` einer WAL-Datenbank waehrend
#     eines Schreibvorgangs liefert genau den zerrissenen Stand, den
#     `VACUUM INTO` vermeiden soll.
#
# (b) Danach wird GEMESSEN statt geglaubt: gehoeren die Seitendateien nach dem
#     Lauf nicht der Datenbank, ist diese Area ein Fehlschlag. Das faengt jede
#     Restkonstellation (su-exec fehlt, CAP_SETUID entzogen, fremde Kennung im
#     Volume) laut auf, statt den Schreibpfad der API still zu verbiegen.
tablestore_runas() {
  # Setzt RUNAS als Kommando-Praefix fuer sqlite3 — leer, wenn der laufende
  # Prozess ohnehin die Kennung des Eigentuemers traegt.
  RUNAS=()
  local db="$1" owner_uid owner_gid
  owner_uid="$(stat -c '%u' "${db}" 2>/dev/null)" || return 0
  owner_gid="$(stat -c '%g' "${db}" 2>/dev/null)" || return 0
  [[ "${owner_uid}" == "$(id -u)" ]] && return 0
  command -v su-exec >/dev/null 2>&1 || return 0
  RUNAS=(su-exec "${owner_uid}:${owner_gid}")
}

# Messung zu (b): nennt die Seitendateien, die NICHT der Datenbank gehoeren.
tablestore_foreign_sidecars() {
  local db="$1" want side f owner
  want="$(stat -c '%u' "${db}" 2>/dev/null)" || return 0
  for side in '-wal' '-shm'; do
    f="${db}${side}"
    [[ -e "${f}" ]] || continue
    owner="$(stat -c '%u' "${f}" 2>/dev/null)" || continue
    [[ "${owner}" == "${want}" ]] || printf '%s ' "$(basename "${f}")"
  done
}

backup_tablestore() {
  if [[ "${BACKUP_TABLESTORE}" == "off" ]]; then
    log "BACKUP_TABLESTORE=off — Tabellen-Store bewusst abgewaehlt"
    return 0
  fi

  local src="${WHO2BE_TABLESTORE_DIR:-/data/tablestore}"
  if [[ ! -d "${src}" ]]; then
    fail_stage "Tabellen-Store-Verzeichnis fehlt: ${src} — setze BACKUP_TABLESTORE=off, wenn dieser Stack keinen Tabellen-Store hat"
    return 1
  fi
  if ! command -v sqlite3 >/dev/null 2>&1; then
    fail_stage "Tabellen-Store: sqlite3 fehlt im Backup-Image"
    return 1
  fi

  mkdir -p "${TABLESTORE_SNAPSHOT_DIR}"
  log "VACUUM INTO-Snapshots ${src} → ${TABLESTORE_SNAPSHOT_DIR}"

  # Die Merkliste liegt BEWUSST ausserhalb von ${BACKUP_DIR}: dort wuerde ein
  # harter Abbruch zwischen Anlage und Aufraeumen sie in den restic-Snapshot
  # tragen. Dasselbe gilt fuer das Scratch-Verzeichnis, in das VACUUM INTO
  # schreibt: es traegt 1777, damit auch der Eigentuemer der Datenbank
  # hineinschreiben kann, wenn der Lesevorgang unter dessen Kennung laeuft.
  # Der trap raeumt beides auch bei hartem Abbruch.
  local snapshots=0 errors=0 seen scratch
  seen="$(mktemp "${TMPDIR:-/tmp}/who2be-tablestore-seen.XXXXXX")"
  scratch="$(mktemp -d "${TMPDIR:-/tmp}/who2be-tablestore-scratch.XXXXXX")"
  chmod 1777 "${scratch}"
  trap 'rm -rf "${seen}" "${scratch}"' RETURN

  local db rel target tmp foreign
  while IFS= read -r db; do
    rel="${db#"${src}"/}"
    target="${TABLESTORE_SNAPSHOT_DIR}/${rel}"
    tmp="${scratch}/snap.sqlite"
    mkdir -p "$(dirname "${target}")"
    rm -f "${tmp}"
    # Unter der Kennung des Datei-Eigentuemers lesen (s. o.), damit etwaige
    # WAL-Seitendateien nicht dem Backup-Nutzer gehoeren.
    tablestore_runas "${db}"
    if ! "${RUNAS[@]}" sqlite3 "file:${db}?mode=ro" "VACUUM INTO '${tmp}'" 2>&1; then
      log "  ✗ ${rel}: VACUUM INTO fehlgeschlagen"
      rm -f "${tmp}"
      errors=$((errors + 1))
      continue
    fi
    # Gemessener Nachweis, dass der Lauf den Schreibpfad der API nicht
    # verbogen hat. Schlaegt das fehl, ist die Area ein Fehlschlag — lieber ein
    # roter Lauf als eine API, die diese Tabelle still nicht mehr schreiben kann.
    foreign="$(tablestore_foreign_sidecars "${db}")"
    if [[ -n "${foreign}" ]]; then
      log "  ✗ ${rel}: fremde WAL-Seitendateien nach dem Lauf (${foreign% })"
      rm -f "${tmp}"
      errors=$((errors + 1))
      continue
    fi
    # quick_check statt integrity_check: gleiche Aussagekraft fuer
    # Strukturfehler, deutlich kuerzere Laufzeit auf grossen Dateien.
    if [[ "$(sqlite3 "${tmp}" 'PRAGMA quick_check' 2>&1)" != "ok" ]]; then
      log "  ✗ ${rel}: quick_check nicht ok"
      rm -f "${tmp}"
      errors=$((errors + 1))
      continue
    fi
    # Erst nach bestandener Pruefung ueber den Vorlauf schieben: so bleibt der
    # letzte gute Snapshot stehen, wenn dieser Lauf fuer diese Area scheitert.
    mv -f "${tmp}" "${target}"
    printf '%s\n' "${rel}" >>"${seen}"
    snapshots=$((snapshots + 1))
  done < <(find "${src}" -type f -name '*.sqlite' | sort)

  # Verwaiste Snapshots raeumen: eine geloeschte Area soll nicht ueber den
  # lokalen Spiegel weiterleben (gleiche Begruendung wie --delete oben).
  local orphan
  while IFS= read -r orphan; do
    rel="${orphan#"${TABLESTORE_SNAPSHOT_DIR}"/}"
    if ! grep -qxF "${rel}" "${seen}"; then
      log "  · verwaisten Snapshot entfernt: ${rel}"
      rm -f "${orphan}"
    fi
  done < <(find "${TABLESTORE_SNAPSHOT_DIR}" -type f -name '*.sqlite' 2>/dev/null | sort)
  find "${TABLESTORE_SNAPSHOT_DIR}" -type d -empty -delete 2>/dev/null || true
  rm -rf "${seen}" "${scratch}"
  trap - RETURN

  if (( errors > 0 )); then
    fail_stage "Tabellen-Store: ${errors} von $((snapshots + errors)) Area-Snapshots fehlgeschlagen"
    return 1
  fi
  log "Tabellen-Snapshots: ${snapshots} Datei(en), $(du -sh "${TABLESTORE_SNAPSHOT_DIR}" | cut -f1)"
}

backup_blobs || true
backup_tablestore || true

# --- C5b: Offsite via restic ---------------------------------------------
# Der Snapshot traegt --tag dump NUR, wenn alle drei Stufen sauber liefen. Sonst
# --tag incomplete: die Daten gehen offsite (ein Blob-Ausfall soll den Dump nicht
# am Boden halten), aber der Snapshot darf sich beim Restore nicht als
# vollstaendiger Stand ausgeben. RUNBOOK-Restore filtert auf --tag dump.
if (( ${#FAILURES[@]} > 0 )); then
  restic_tag="incomplete"
else
  restic_tag="dump"
fi

if [[ -z "${RESTIC_REPOSITORY:-}" ]]; then
  log "RESTIC_REPOSITORY leer — Offsite-Sync uebersprungen (lokal-only Modus)"
  finish
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
log "restic backup ${BACKUP_DIR} (tag ${restic_tag})"
if ! restic_cmd backup "${BACKUP_DIR}" --tag "${restic_tag}" --host who2be-prod; then
  log "FATAL: restic backup fehlgeschlagen — KEIN Offsite-Backup aus diesem Lauf"
  log "       lokaler Dump bleibt erhalten: ${out}"
  log "       lokale Daten bleiben erhalten: ${BACKUP_DIR}"
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

# Erst hier ist der Lauf vollstaendig — finish() pingt den Dead-Man's-Switch
# ausschliesslich bei leerer Fehlerliste.
finish
