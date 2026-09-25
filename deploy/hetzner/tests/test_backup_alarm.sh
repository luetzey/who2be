#!/usr/bin/env bash
# Alarm-Verhalten des Backup-Skripts (#541) + Vollstaendigkeit des Laufs (W8/M3).
#
# Belegt ohne Docker-Daemon und ohne Postgres, was die Issues verlangen:
#   1) ein fehlgeschlagener Offsite-Sync ist von aussen erkennbar (Exit != 0,
#      kein Heartbeat) — die Erfolgsmeldung faellt weg;
#   2) der lokale GPG-Dump bleibt dabei in JEDEM Fall erhalten (harte Bedingung,
#      Zusage aus backup.sh und ADR-0011 gilt unveraendert);
#   3) ohne gesetzte BACKUP_HEARTBEAT_URL ist das Verhalten unveraendert;
#   4) ein TEILERFOLG loest KEINEN gruenen Heartbeat aus (W8/M3): scheitert der
#      Blob-Sync oder ein Tabellen-Snapshot, endet der Lauf rot und ohne Ping —
#      auch dann, wenn pg_dump und restic sauber liefen;
#   5) ein unvollstaendiger Lauf markiert seinen restic-Snapshot als
#      `--tag incomplete`, damit er sich beim Restore nicht als vollstaendiger
#      Stand ausgeben kann;
#   6) fehlende Store-Konfiguration ist FATAL, nicht "still uebersprungen".
#
# Methode: pg_dump / gpg / restic / curl / aws werden durch PATH-Stubs ersetzt,
# die sich per Env-Schalter zum Scheitern bringen lassen. `sqlite3` ist echt —
# die Tests legen richtige SQLite-Dateien an und lassen `VACUUM INTO` real
# laufen. Getestet wird die Ablauf-Logik des Skripts, nicht restic selbst.
#
# Aufruf:
#   bash deploy/hetzner/tests/test_backup_alarm.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SH="${SCRIPT_DIR}/../scripts/backup.sh"

log()  { printf '\033[1;34m[backup-alarm]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[backup-alarm:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }
ok()   { printf '  ✓ %s\n' "$*"; }

[[ -r "${BACKUP_SH}" ]] || fail "backup.sh nicht gefunden: ${BACKUP_SH}"
command -v sqlite3 >/dev/null 2>&1 || fail "sqlite3 wird fuer die Tabellen-Store-Faelle gebraucht"

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/who2be-backup-alarm.XXXXXX")"
trap 'rm -rf "${ROOT}"' EXIT

BIN="${ROOT}/bin"
mkdir -p "${BIN}"

# --- Stubs ---------------------------------------------------------------
# pg_dump schreibt Pseudo-Inhalt, gpg reicht stdin nach --output durch: so
# entsteht ein nicht-leeres Dump-File wie im Echtlauf.
cat >"${BIN}/pg_dump" <<'STUB'
#!/usr/bin/env bash
printf 'PGDMP-fake-dump\n'
STUB

cat >"${BIN}/gpg" <<'STUB'
#!/usr/bin/env bash
target=""
prev=""
for arg in "$@"; do
  [[ "${prev}" == "--output" ]] && target="${arg}"
  prev="${arg}"
done
[[ -n "${target}" ]] || { echo "stub-gpg: kein --output" >&2; exit 1; }
cat >"${target}"
STUB

# restic: scheitert gezielt, wenn STUB_RESTIC_FAIL das Subkommando nennt.
# `cat config` meldet ein bestehendes Repo (kein init noetig). Jeder Aufruf
# wird mit vollstaendiger Argumentliste protokolliert — daran haengt die
# Tag-Pruefung (dump vs. incomplete).
cat >"${BIN}/restic" <<'STUB'
#!/usr/bin/env bash
sub="${1:-}"
printf '%s\n' "$*" >>"${RESTIC_LOG}"
case "${sub}" in
  cat) exit 0 ;;
esac
if [[ " ${STUB_RESTIC_FAIL:-} " == *" ${sub} "* ]]; then
  echo "stub-restic: ${sub} failed (simuliert)" >&2
  exit 1
fi
echo "stub-restic: ${sub} ok"
exit 0
STUB

# curl: protokolliert jeden Ping; scheitert, wenn STUB_CURL_FAIL=1.
cat >"${BIN}/curl" <<'STUB'
#!/usr/bin/env bash
url="${!#}"
printf '%s\n' "${url}" >>"${HEARTBEAT_LOG}"
if [[ "${STUB_CURL_FAIL:-0}" == "1" ]]; then
  echo "stub-curl: ping failed (simuliert)" >&2
  exit 22
fi
exit 0
STUB

# aws: simuliert `s3 sync`. Schreibt im Erfolgsfall eine Pseudo-Objektdatei in
# das Zielverzeichnis (letztes Argument); scheitert bei STUB_AWS_FAIL=1.
cat >"${BIN}/aws" <<'STUB'
#!/usr/bin/env bash
dest="${!#}"
printf '%s\n' "$*" >>"${AWS_LOG}"
if [[ "${STUB_AWS_FAIL:-0}" == "1" ]]; then
  echo "stub-aws: s3 sync failed (simuliert)" >&2
  exit 1
fi
mkdir -p "${dest}/blobs/ws-1"
printf 'fake-object\n' >"${dest}/blobs/ws-1/deadbeef"
exit 0
STUB

chmod +x "${BIN}"/*

HEARTBEAT_URL="https://status.internal.invalid/ping/who2be-backup"

# --- Tabellen-Store-Fixture ----------------------------------------------
# Echte SQLite-Dateien: `VACUUM INTO` und `PRAGMA quick_check` laufen real.
TABLESTORE_SRC="${ROOT}/tablestore"
mk_tablestore() {
  rm -rf "${TABLESTORE_SRC}"
  mkdir -p "${TABLESTORE_SRC}/11111111-1111-1111-1111-111111111111"
  sqlite3 "${TABLESTORE_SRC}/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite" \
    "PRAGMA journal_mode=WAL; CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT); INSERT INTO t (v) VALUES ('a'),('b');" \
    >/dev/null
}
mk_tablestore

# run <case-name> — fuehrt backup.sh in einer frischen Sandbox aus.
# Setzt: RUN_EXIT, RUN_DIR, RUN_PINGS, RUN_OUT
run() {
  local name="$1"
  RUN_DIR="${ROOT}/case-${name}"
  mkdir -p "${RUN_DIR}/backups"
  export HEARTBEAT_LOG="${RUN_DIR}/heartbeat.log"
  export RESTIC_LOG="${RUN_DIR}/restic.log"
  export AWS_LOG="${RUN_DIR}/aws.log"
  : >"${HEARTBEAT_LOG}"
  : >"${RESTIC_LOG}"
  : >"${AWS_LOG}"

  set +e
  PATH="${BIN}:${PATH}" \
  POSTGRES_HOST=db POSTGRES_USER=u POSTGRES_DB=d PGPASSWORD=p \
  BACKUP_GPG_RECIPIENT=backup@example.org \
  BACKUP_DIR="${RUN_DIR}/backups" \
  HEARTBEAT_LOG="${HEARTBEAT_LOG}" \
  RESTIC_LOG="${RESTIC_LOG}" \
  AWS_LOG="${AWS_LOG}" \
  WHO2BE_BLOBSTORE_ENDPOINT="${WHO2BE_BLOBSTORE_ENDPOINT-seaweedfs:8333}" \
  WHO2BE_BLOBSTORE_ACCESS_KEY="${WHO2BE_BLOBSTORE_ACCESS_KEY-who2be}" \
  WHO2BE_BLOBSTORE_SECRET_KEY="${WHO2BE_BLOBSTORE_SECRET_KEY-secret}" \
  WHO2BE_TABLESTORE_DIR="${WHO2BE_TABLESTORE_DIR-${TABLESTORE_SRC}}" \
    bash "${BACKUP_SH}" >"${RUN_DIR}/stdout.log" 2>&1
  RUN_EXIT=$?
  set -e

  RUN_PINGS="$(wc -l <"${HEARTBEAT_LOG}" | tr -d ' ')"
  RUN_OUT="$(find "${RUN_DIR}/backups" -maxdepth 1 -name 'dump-*.pgc.gpg' | wc -l | tr -d ' ')"
}

assert_exit() {
  local expected="$1" what="$2"
  case "${expected}" in
    zero)    [[ "${RUN_EXIT}" -eq 0 ]] || fail "${what}: Exit ${RUN_EXIT}, erwartet 0" ;;
    nonzero) [[ "${RUN_EXIT}" -ne 0 ]] || fail "${what}: Exit 0, erwartet != 0" ;;
  esac
  ok "${what}: Exit ${RUN_EXIT}"
}

assert_dump_present() {
  [[ "${RUN_OUT}" -eq 1 ]] \
    || fail "$1: lokaler Dump fehlt (gefunden: ${RUN_OUT})"
  ok "$1: lokaler GPG-Dump liegt vor"
}

assert_pings() {
  local expected="$1" what="$2"
  [[ "${RUN_PINGS}" -eq "${expected}" ]] \
    || fail "${what}: ${RUN_PINGS} Heartbeat-Pings, erwartet ${expected}"
  ok "${what}: ${RUN_PINGS} Heartbeat-Ping(s)"
}

assert_blob_mirror() {
  local n
  n="$(find "${RUN_DIR}/backups/blobs" -type f 2>/dev/null | wc -l | tr -d ' ')"
  [[ "${n}" -ge 1 ]] || fail "$1: Blob-Spiegel leer"
  ok "$1: Blob-Spiegel enthaelt ${n} Objekt(e)"
}

assert_tablestore_snapshot() {
  local snap="${RUN_DIR}/backups/tablestore/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite"
  [[ -s "${snap}" ]] || fail "$1: Tabellen-Snapshot fehlt"
  [[ "$(sqlite3 "${snap}" 'PRAGMA quick_check')" == "ok" ]] \
    || fail "$1: Tabellen-Snapshot besteht quick_check nicht"
  [[ "$(sqlite3 "${snap}" 'SELECT count(*) FROM t')" == "2" ]] \
    || fail "$1: Tabellen-Snapshot hat nicht die erwarteten Zeilen"
  ok "$1: Tabellen-Snapshot lesbar, quick_check ok, 2 Zeilen"
}

assert_restic_tag() {
  local expected="$1" what="$2"
  grep -q -- "backup .* --tag ${expected} " "${RUN_DIR}/restic.log" \
    || fail "${what}: restic-Snapshot traegt nicht --tag ${expected} (Log: $(tr '\n' '|' <"${RUN_DIR}/restic.log"))"
  ok "${what}: restic-Snapshot traegt --tag ${expected}"
}

assert_no_restic_backup() {
  if grep -q '^backup ' "${RUN_DIR}/restic.log"; then
    fail "$1: restic backup lief, obwohl kein Offsite erwartet war"
  fi
  ok "$1: kein restic-backup-Aufruf"
}

# --- 1) Erfolgsfall: alle drei Bestaende + Offsite + Alarmweg ------------
log "1/11 Erfolgsfall (drei Bestaende, Offsite, Heartbeat)"
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run success
assert_exit zero "Erfolgsfall"
assert_dump_present "Erfolgsfall"
assert_blob_mirror "Erfolgsfall"
assert_tablestore_snapshot "Erfolgsfall"
assert_pings 1 "Erfolgsfall"
assert_restic_tag dump "Erfolgsfall"

# --- 2) restic backup scheitert (Kernfall #541) --------------------------
log "2/11 restic backup scheitert — rot, Dump bleibt, kein Ping"
STUB_RESTIC_FAIL="backup" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run restic-backup-fail
assert_exit nonzero "Sync-Fehlschlag"
assert_dump_present "Sync-Fehlschlag"   # <- die harte Bedingung
assert_pings 0 "Sync-Fehlschlag"
grep -q 'lokaler Dump bleibt erhalten' "${RUN_DIR}/stdout.log" \
  || fail "Sync-Fehlschlag: Log nennt den erhaltenen lokalen Dump nicht"
ok "Sync-Fehlschlag: Log weist auf den erhaltenen lokalen Dump hin"
grep -q 'forget uebersprungen' "${RUN_DIR}/stdout.log" \
  || fail "Sync-Fehlschlag: restic forget wurde nicht uebersprungen"
ok "Sync-Fehlschlag: restic forget uebersprungen"

# --- 3) restic forget scheitert ------------------------------------------
log "3/11 restic forget scheitert — rot, Dump bleibt, kein Ping"
STUB_RESTIC_FAIL="forget" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run restic-forget-fail
assert_exit nonzero "Forget-Fehlschlag"
assert_dump_present "Forget-Fehlschlag"
assert_pings 0 "Forget-Fehlschlag"

# --- 4) Ohne neue Variablen: Verhalten unveraendert ----------------------
log "4/11 Offsite-Erfolg ohne BACKUP_HEARTBEAT_URL — unveraendert"
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
  run no-heartbeat
assert_exit zero "Ohne Alarmweg"
assert_dump_present "Ohne Alarmweg"
assert_pings 0 "Ohne Alarmweg"

# --- 5) Lokal-only (RESTIC_REPOSITORY leer) ------------------------------
log "5/11 Lokal-only mit Alarmweg — Erfolg, Ping, alle drei Bestaende lokal"
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" run local-only
assert_exit zero "Lokal-only"
assert_dump_present "Lokal-only"
assert_blob_mirror "Lokal-only"
assert_tablestore_snapshot "Lokal-only"
assert_pings 1 "Lokal-only"

# --- 6) Stummer Alarmweg ist selbst ein Fehlschlag -----------------------
log "6/11 Heartbeat-Ping scheitert — Lauf ist rot, Dump bleibt"
STUB_CURL_FAIL=1 \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run heartbeat-fail
assert_exit nonzero "Stummer Alarmweg"
assert_dump_present "Stummer Alarmweg"

# --- 7) TEILERFOLG: Blob-Sync scheitert — die Kernzusage dieser Karte ----
# pg_dump lief, restic lief, nur der Objekt-Store fehlt. Genau hier haette die
# alte Fassung "alles gut" gemeldet, waehrend ein Drittel fehlt.
log "7/11 Blob-Sync scheitert bei sonst gruenem Lauf — KEIN gruener Heartbeat"
STUB_AWS_FAIL=1 \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run blob-fail
assert_exit nonzero "Blob-Teilerfolg"
assert_dump_present "Blob-Teilerfolg"
assert_pings 0 "Blob-Teilerfolg"
assert_tablestore_snapshot "Blob-Teilerfolg"   # Stufe 3 lief trotz Stufe-2-Fehler
assert_restic_tag incomplete "Blob-Teilerfolg"
grep -q 'Backup UNVOLLSTAENDIG' "${RUN_DIR}/stdout.log" \
  || fail "Blob-Teilerfolg: Log meldet den Lauf nicht als unvollstaendig"
ok "Blob-Teilerfolg: Log meldet 'Backup UNVOLLSTAENDIG'"

# --- 8) TEILERFOLG: Tabellen-Snapshot scheitert --------------------------
# Eine kaputte Datei im Store: VACUUM INTO bzw. quick_check muss sie ablehnen,
# und der Lauf darf nicht gruen enden.
log "8/11 Tabellen-Snapshot scheitert — KEIN gruener Heartbeat"
BROKEN_STORE="${ROOT}/tablestore-broken"
rm -rf "${BROKEN_STORE}"
mkdir -p "${BROKEN_STORE}/33333333-3333-3333-3333-333333333333"
printf 'das ist keine sqlite-datei\n' \
  >"${BROKEN_STORE}/33333333-3333-3333-3333-333333333333/44444444-4444-4444-4444-444444444444.sqlite"
WHO2BE_TABLESTORE_DIR="${BROKEN_STORE}" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run tablestore-fail
assert_exit nonzero "Tabellen-Teilerfolg"
assert_dump_present "Tabellen-Teilerfolg"
assert_pings 0 "Tabellen-Teilerfolg"
assert_blob_mirror "Tabellen-Teilerfolg"       # Stufe 2 lief trotz Stufe-3-Fehler
assert_restic_tag incomplete "Tabellen-Teilerfolg"

# --- 9) Beide Zusatz-Stufen scheitern gleichzeitig -----------------------
log "9/11 Blob UND Tabellen-Store scheitern — beide Fehler im Log, kein Ping"
STUB_AWS_FAIL=1 \
WHO2BE_TABLESTORE_DIR="${BROKEN_STORE}" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run both-fail
assert_exit nonzero "Doppel-Teilerfolg"
assert_pings 0 "Doppel-Teilerfolg"
grep -q '2 Stufe(n) fehlgeschlagen' "${RUN_DIR}/stdout.log" \
  || fail "Doppel-Teilerfolg: Log zaehlt nicht beide Stufen"
ok "Doppel-Teilerfolg: beide Stufen im Abschlussbericht"

# --- 10) Fehlende Konfiguration ist FATAL, nicht "uebersprungen" ---------
log "10/11 Store-Konfiguration fehlt — FATAL statt stillem Ueberspringen"
WHO2BE_BLOBSTORE_ENDPOINT="" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run blob-unconfigured
assert_exit nonzero "Unkonfigurierter Objekt-Store"
assert_pings 0 "Unkonfigurierter Objekt-Store"
grep -q 'WHO2BE_BLOBSTORE_ENDPOINT' "${RUN_DIR}/stdout.log" \
  || fail "Unkonfiguriert: Log nennt die fehlende Variable nicht"
ok "Unkonfiguriert: Log nennt die fehlende Variable beim Namen"

# --- 11) Ausdrueckliche Abwahl ist erlaubt und gruen ---------------------
log "11/11 BACKUP_BLOBS=off / BACKUP_TABLESTORE=off — bewusste Abwahl, gruen"
BACKUP_BLOBS=off BACKUP_TABLESTORE=off \
WHO2BE_BLOBSTORE_ENDPOINT="" WHO2BE_TABLESTORE_DIR="/nonexistent" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run stores-off
assert_exit zero "Abwahl"
assert_dump_present "Abwahl"
assert_pings 1 "Abwahl"
assert_restic_tag dump "Abwahl"

printf '\033[1;32m[backup-alarm]\033[0m alle Faelle gruen\n'
