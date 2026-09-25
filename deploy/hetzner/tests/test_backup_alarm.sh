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
#   6) fehlende Store-Konfiguration ist FATAL, nicht "still uebersprungen";
#   7) der Lauf VERBIEGT DEN SCHREIBPFAD DER API NICHT: ein `mode=ro`-Leser
#      legt die WAL-Seitendateien an, wenn sie fehlen — gehoeren sie danach dem
#      Backup-Nutzer statt der API, kann die API die Area still nicht mehr
#      schreiben. Fall 12 stellt das cross-uid nach (Backup als root, Store
#      unter fremder uid), was die Faelle 1–11 prinzipbedingt nicht messen
#      koennen: dort ist die Kennung beider Seiten dieselbe.
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

# Der Lauf darf im QUELLVERZEICHNIS nichts hinterlassen, das der API gehoeren
# muesste und ihr nicht gehoert. Ein `mode=ro`-Leser LEGT die WAL-Seitendateien
# an, wenn sie fehlen — nachts ist das der Regelfall, weil die API je Query
# oeffnet und schliesst. Gehoeren sie danach dem Backup-Nutzer statt der API,
# kann die API diese Area still nicht mehr schreiben.
assert_no_foreign_sidecars() {
  local dir="${2:-${TABLESTORE_SRC}}" db want owner side f bad=0
  while IFS= read -r db; do
    want="$(stat -c '%u' "${db}")"
    for side in '-wal' '-shm'; do
      f="${db}${side}"
      [[ -e "${f}" ]] || continue
      owner="$(stat -c '%u' "${f}")"
      if [[ "${owner}" != "${want}" ]]; then
        printf '    fremd: %s (uid %s, DB gehoert uid %s)\n' "${f##*/}" "${owner}" "${want}" >&2
        bad=1
      fi
    done
  done < <(find "${dir}" -type f -name '*.sqlite' | sort)
  (( bad == 0 )) || fail "$1: Backup-Lauf hinterlaesst fremde WAL-Seitendateien im Quellverzeichnis"
  ok "$1: keine fremden WAL-Seitendateien im Quellverzeichnis"
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
log "1/12 Erfolgsfall (drei Bestaende, Offsite, Heartbeat)"
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run success
assert_exit zero "Erfolgsfall"
assert_dump_present "Erfolgsfall"
assert_blob_mirror "Erfolgsfall"
assert_tablestore_snapshot "Erfolgsfall"
assert_no_foreign_sidecars "Erfolgsfall"
assert_pings 1 "Erfolgsfall"
assert_restic_tag dump "Erfolgsfall"

# --- 2) restic backup scheitert (Kernfall #541) --------------------------
log "2/12 restic backup scheitert — rot, Dump bleibt, kein Ping"
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
log "3/12 restic forget scheitert — rot, Dump bleibt, kein Ping"
STUB_RESTIC_FAIL="forget" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run restic-forget-fail
assert_exit nonzero "Forget-Fehlschlag"
assert_dump_present "Forget-Fehlschlag"
assert_pings 0 "Forget-Fehlschlag"

# --- 4) Ohne neue Variablen: Verhalten unveraendert ----------------------
log "4/12 Offsite-Erfolg ohne BACKUP_HEARTBEAT_URL — unveraendert"
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
  run no-heartbeat
assert_exit zero "Ohne Alarmweg"
assert_dump_present "Ohne Alarmweg"
assert_pings 0 "Ohne Alarmweg"

# --- 5) Lokal-only (RESTIC_REPOSITORY leer) ------------------------------
log "5/12 Lokal-only mit Alarmweg — Erfolg, Ping, alle drei Bestaende lokal"
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" run local-only
assert_exit zero "Lokal-only"
assert_dump_present "Lokal-only"
assert_blob_mirror "Lokal-only"
assert_tablestore_snapshot "Lokal-only"
assert_pings 1 "Lokal-only"

# --- 6) Stummer Alarmweg ist selbst ein Fehlschlag -----------------------
log "6/12 Heartbeat-Ping scheitert — Lauf ist rot, Dump bleibt"
STUB_CURL_FAIL=1 \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run heartbeat-fail
assert_exit nonzero "Stummer Alarmweg"
assert_dump_present "Stummer Alarmweg"

# --- 7) TEILERFOLG: Blob-Sync scheitert — die Kernzusage dieser Karte ----
# pg_dump lief, restic lief, nur der Objekt-Store fehlt. Genau hier haette die
# alte Fassung "alles gut" gemeldet, waehrend ein Drittel fehlt.
log "7/12 Blob-Sync scheitert bei sonst gruenem Lauf — KEIN gruener Heartbeat"
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
log "8/12 Tabellen-Snapshot scheitert — KEIN gruener Heartbeat"
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
log "9/12 Blob UND Tabellen-Store scheitern — beide Fehler im Log, kein Ping"
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
log "10/12 Store-Konfiguration fehlt — FATAL statt stillem Ueberspringen"
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
log "11/12 BACKUP_BLOBS=off / BACKUP_TABLESTORE=off — bewusste Abwahl, gruen"
BACKUP_BLOBS=off BACKUP_TABLESTORE=off \
WHO2BE_BLOBSTORE_ENDPOINT="" WHO2BE_TABLESTORE_DIR="/nonexistent" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run stores-off
assert_exit zero "Abwahl"
assert_dump_present "Abwahl"
assert_pings 1 "Abwahl"
assert_restic_tag dump "Abwahl"

printf '\033[1;32m[backup-alarm]\033[0m Faelle 1–11 gruen\n'

# --- 12) Der Lauf darf den Schreibpfad der API nicht verbiegen -----------
# Der Betriebsfall, den die Faelle 1–11 strukturell NICHT messen koennen: dort
# laeuft das Backup unter derselben Kennung wie die Fixture. Auf dem Server
# laeuft der Backup-Container als root, die API unter einer eigenen uid —
# und ein `mode=ro`-Leser LEGT die WAL-Seitendateien an, wenn sie fehlen
# (nachts der Regelfall, weil die API je Query oeffnet und schliesst).
# Gehoeren sie danach dem Backup-Nutzer, kann die API die Area still nicht
# mehr schreiben: lesen geht weiter, schreiben nicht.
#
# Nachgestellt in einem User-Namespace: der Lauf sieht sich als uid 0, die
# Store-Dateien gehoeren uid 1000. Fehlen unprivilegierte Namespaces (manche
# gehaerteten CI-Images), wird der Fall ausdruecklich uebersprungen statt
# stillschweigend als gruen gezaehlt.
#
# ZWEIMAL, und das ist der Punkt: SQLite zieht die Seitendateien selbst auf den
# Eigentuemer der Datenbank nach — aber nur MIT CAP_CHOWN. Faellt die Capability
# weg (`cap_drop`, `no-new-privileges`, userns-remap), bleiben sie beim
# Backup-Nutzer haengen. Fall 12 misst den bequemen Fall, Fall 13 den, der die
# Zusage wirklich traegt: ohne ihn waere dieser Test gegen die Vorfassung gruen
# (selbst gemessen) und damit kein Regressionsschutz.
log "12/13 Cross-UID mit CAP_CHOWN: Backup als root, Store gehoert der API"

if ! command -v unshare >/dev/null 2>&1 \
   || ! command -v setpriv >/dev/null 2>&1 \
   || ! unshare -rm --map-auto true 2>/dev/null; then
  printf '  ⚠ 12+13 uebersprungen: unprivilegierte User-Namespaces (unshare --map-auto) nicht verfuegbar\n'
  printf '\033[1;32m[backup-alarm]\033[0m alle lauffaehigen Faelle gruen\n'
  exit 0
fi

# Das Innere laeuft als uid 0 im Namespace. Alles, was der su-exec'te sqlite3
# (uid 1000) anfassen muss, liegt unter /tmp — der Testbaum selbst kann in
# einem Home liegen, das uid 1000 nicht durchqueren darf.
cat >"${ROOT}/case12-inner.sh" <<'INNER'
#!/usr/bin/env bash
set -uo pipefail
BACKUP_SH="$1"; BIN="$2"; DROP_CHOWN="${3:-}"
API_UID=1000

W="$(TMPDIR=/tmp mktemp -d)"; chmod 755 "${W}"
STORE="${W}/tablestore"; BACKUPS="${W}/backups"
mkdir -p "${STORE}/11111111-1111-1111-1111-111111111111" "${BACKUPS}"
sqlite3 "${STORE}/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite" \
  "PRAGMA journal_mode=WAL; CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT); INSERT INTO t (v) VALUES ('a'),('b');" \
  >/dev/null
chown -R "${API_UID}:${API_UID}" "${STORE}"

# su-exec-Stub: im Image liefert das Alpine-Paket den echten Befehl, hier
# genuegt setpriv mit derselben Aufrufform `su-exec uid:gid cmd...`.
cat >"${BIN}/su-exec" <<'STUB'
#!/usr/bin/env bash
spec="$1"; shift
exec setpriv --reuid "${spec%%:*}" --regid "${spec##*:}" --clear-groups "$@"
STUB
chmod +x "${BIN}/su-exec"

export HEARTBEAT_LOG="${W}/heartbeat.log" RESTIC_LOG="${W}/restic.log" AWS_LOG="${W}/aws.log"
: >"${HEARTBEAT_LOG}"; : >"${RESTIC_LOG}"; : >"${AWS_LOG}"

TMPDIR=/tmp PATH="${BIN}:${PATH}" \
POSTGRES_HOST=db POSTGRES_USER=u POSTGRES_DB=d PGPASSWORD=p \
BACKUP_GPG_RECIPIENT=backup@example.org \
BACKUP_DIR="${BACKUPS}" BACKUP_BLOBS=off \
WHO2BE_TABLESTORE_DIR="${STORE}" \
  ${DROP_CHOWN:+setpriv --bounding-set -chown} \
  bash "${BACKUP_SH}" >"${W}/stdout.log" 2>&1
rc=$?

db="${STORE}/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite"
echo "EXIT=${rc}"
echo "--- Quellverzeichnis nach dem Lauf ---"
ls -ln "$(dirname "${db}")" | tail -n +2 | awk '{printf "    %-46s uid=%s\n", $9, $3}'
for s in -wal -shm; do
  [[ -e "${db}${s}" ]] || continue
  [[ "$(stat -c '%u' "${db}${s}")" == "${API_UID}" ]] || echo "FOREIGN_SIDECAR=${db##*/}${s}"
done
snap="${BACKUPS}/tablestore/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite"
[[ -s "${snap}" ]] && [[ "$(sqlite3 "${snap}" 'SELECT count(*) FROM t')" == "2" ]] && echo "SNAPSHOT_OK"
printf -- '--- API (uid %s) schreibt danach: ' "${API_UID}"
if setpriv --reuid "${API_UID}" --regid "${API_UID}" --clear-groups \
     sqlite3 "${db}" "INSERT INTO t (v) VALUES ('c');" 2>/dev/null; then
  echo "OK"; echo "API_WRITE_OK"
else
  echo "FEHLGESCHLAGEN"
fi
rm -rf "${W}"
INNER

CASE12_OUT="${ROOT}/case12.log"
unshare -rm --map-auto bash "${ROOT}/case12-inner.sh" "${BACKUP_SH}" "${BIN}" >"${CASE12_OUT}" 2>&1 || true

assert_crossuid() {
  local out="$1" what="$2"
  sed 's/^/  /' "${out}"
  grep -q '^EXIT=0' "${out}" \
    || fail "${what}: Lauf endete nicht mit Exit 0"
  ok "${what}: Lauf endet mit Exit 0"
  grep -q '^SNAPSHOT_OK' "${out}" \
    || fail "${what}: Tabellen-Snapshot fehlt oder hat nicht die erwarteten Zeilen"
  ok "${what}: Tabellen-Snapshot lesbar mit den erwarteten Zeilen"
  if grep -q '^FOREIGN_SIDECAR=' "${out}"; then
    fail "${what}: Backup-Lauf hinterlaesst WAL-Seitendateien, die der API NICHT gehoeren"
  fi
  ok "${what}: alle WAL-Seitendateien gehoeren der API"
  grep -q '^API_WRITE_OK' "${out}" \
    || fail "${what}: die API kann nach dem Backup-Lauf nicht mehr schreiben"
  ok "${what}: die API kann nach dem Backup-Lauf weiterhin schreiben"
}

assert_crossuid "${CASE12_OUT}" "Cross-UID (mit CAP_CHOWN)"

# --- 13) Dasselbe OHNE CAP_CHOWN — der Fall, der die Zusage traegt -------
# Ohne die Capability kann SQLite die Seitendateien nicht mehr selbst auf den
# Eigentuemer der Datenbank ziehen. Genau hier scheitert die Vorfassung (selbst
# gemessen: root-eigene -wal/-shm, danach "attempt to write a readonly
# database"), und genau hier muss der Umbau tragen: der Lesevorgang laeuft
# unter der Kennung des Eigentuemers, und das Ergebnis wird geprueft statt
# geglaubt.
log "13/14 Cross-UID OHNE CAP_CHOWN — Zusage haengt nicht an einer Capability"
CASE13_OUT="${ROOT}/case13.log"
unshare -rm --map-auto bash "${ROOT}/case12-inner.sh" "${BACKUP_SH}" "${BIN}" drop-chown >"${CASE13_OUT}" 2>&1 || true
assert_crossuid "${CASE13_OUT}" "Cross-UID (ohne CAP_CHOWN)"

# --- 14) Volles Zieldateisystem: rot, und der letzte gute Stand bleibt ----
# Der Fall, den die Faelle 1–13 prinzipbedingt NICHT messen koennen: dort liegen
# Quelle, Vorlauf und Ziel im selben mktemp-Baum, also im selben Dateisystem.
# Im Container ist das anders — ${BACKUP_DIR} ist ein eigenes Volume. Liegt der
# Vorlauf woanders, wird das Schieben an seinen Platz zu einem echten
# Kopiervorgang ueber die Grenze: er kann an vollem Platz scheitern, und er
# ueberschreibt das Ziel waehrenddessen. Beides trifft die Kernzusage der Karte:
# ein gescheiterter Snapshot darf den Lauf nicht gruen lassen, und der letzte
# gute Stand ist genau der, auf den ein Restore zurueckfallen will.
#
# Nachgestellt mit einem eigenen, absichtlich zu kleinen Dateisystem fuer
# ${BACKUP_DIR}: Lauf 1 legt einen guten Snapshot an, danach waechst die Area
# ueber den freien Platz hinaus, Lauf 2 muss scheitern.
log '14/14 Backup-Ziel laeuft voll — Lauf rot, kein Ping, letzter guter Snapshot intakt'

cat >"${ROOT}/case14-inner.sh" <<'INNER'
#!/usr/bin/env bash
set -uo pipefail
BACKUP_SH="$1"; BIN="$2"

W="$(TMPDIR=/tmp mktemp -d)"
STORE="${W}/tablestore"; BACKUPS="${W}/backups"
mkdir -p "${STORE}/11111111-1111-1111-1111-111111111111" "${BACKUPS}"
DB="${STORE}/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite"
SNAP="${BACKUPS}/tablestore/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite"

# ${BACKUP_DIR} bekommt ein EIGENES, kleines Dateisystem — der Punkt des Falls.
mount -t tmpfs -o size=8M tmpfs "${BACKUPS}" || { echo "MOUNT_FAILED"; exit 0; }

sqlite3 "${DB}" \
  "PRAGMA journal_mode=WAL; CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT); INSERT INTO t (v) VALUES ('a'),('b');" \
  >/dev/null

export HEARTBEAT_LOG="${W}/heartbeat.log" RESTIC_LOG="${W}/restic.log" AWS_LOG="${W}/aws.log"

run_backup() {
  : >"${HEARTBEAT_LOG}"; : >"${RESTIC_LOG}"; : >"${AWS_LOG}"
  TMPDIR=/tmp PATH="${BIN}:${PATH}" \
  POSTGRES_HOST=db POSTGRES_USER=u POSTGRES_DB=d PGPASSWORD=p \
  BACKUP_GPG_RECIPIENT=backup@example.org \
  BACKUP_DIR="${BACKUPS}" BACKUP_BLOBS=off \
  BACKUP_HEARTBEAT_URL="https://status.internal.invalid/ping/who2be-backup" \
  WHO2BE_TABLESTORE_DIR="${STORE}" \
    bash "${BACKUP_SH}" >"${W}/stdout.log" 2>&1
  echo "$?"
}

rc1="$(run_backup)"
echo "RUN1_EXIT=${rc1}"
[[ -s "${SNAP}" ]] && echo "RUN1_SNAPSHOT_ROWS=$(sqlite3 "${SNAP}" 'SELECT count(*) FROM t' 2>&1)"

# Area ueber den freien Platz hinaus wachsen lassen. Der Store liegt NICHT im
# kleinen Dateisystem — nur das Backup-Ziel ist knapp.
sqlite3 "${DB}" \
  "INSERT INTO t (v) SELECT hex(randomblob(512)) FROM generate_series(1,20000);" >/dev/null 2>&1 \
  || sqlite3 "${DB}" \
       "WITH RECURSIVE c(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM c WHERE i<20000)
        INSERT INTO t (v) SELECT hex(randomblob(512)) FROM c;" >/dev/null
echo "SOURCE_BYTES=$(stat -c '%s' "${DB}")"
echo "FREE_ON_TARGET=$(df -k --output=avail "${BACKUPS}" | tail -1)K"

rc2="$(run_backup)"
echo "RUN2_EXIT=${rc2}"
echo "RUN2_PINGS=$(wc -l <"${HEARTBEAT_LOG}" | tr -d ' ')"
echo "--- Log von Lauf 2 (Tabellen-Store) ---"
grep -E 'Tabellen|FATAL|UNVOLLSTAENDIG|fertig' "${W}/stdout.log" | sed 's/^/    /'
if [[ -e "${SNAP}" ]]; then
  echo "RUN2_SNAPSHOT_CHECK=$(sqlite3 "${SNAP}" 'PRAGMA quick_check' 2>&1 | head -1)"
  echo "RUN2_SNAPSHOT_ROWS=$(sqlite3 "${SNAP}" 'SELECT count(*) FROM t' 2>&1 | head -1)"
else
  echo "RUN2_SNAPSHOT_CHECK=fehlt"
  echo "RUN2_SNAPSHOT_ROWS=fehlt"
fi
echo "LEFTOVER_SCRATCH=$(find "${BACKUPS}" -maxdepth 2 -name '.scratch.*' | wc -l | tr -d ' ')"
umount "${BACKUPS}" 2>/dev/null
rm -rf "${W}"
INNER

CASE14_OUT="${ROOT}/case14.log"
unshare -rm --map-auto bash "${ROOT}/case14-inner.sh" "${BACKUP_SH}" "${BIN}" >"${CASE14_OUT}" 2>&1 || true
sed 's/^/  /' "${CASE14_OUT}"

if grep -q '^MOUNT_FAILED' "${CASE14_OUT}"; then
  printf '  ⚠ 14 uebersprungen: eigenes tmpfs im User-Namespace nicht mountbar\n'
else
  grep -q '^RUN1_EXIT=0' "${CASE14_OUT}" \
    || fail "Volles Ziel: Vorlauf (Lauf 1) war schon nicht gruen — Aufbau taugt nicht"
  grep -q '^RUN1_SNAPSHOT_ROWS=2' "${CASE14_OUT}" \
    || fail "Volles Ziel: Lauf 1 hat keinen brauchbaren Snapshot hinterlassen"
  ok "Volles Ziel: Lauf 1 gruen, guter Snapshot am Ziel"

  grep -q '^RUN2_EXIT=0$' "${CASE14_OUT}" \
    && fail "Volles Ziel: Lauf 2 endete GRUEN, obwohl der Snapshot nicht geschrieben werden konnte"
  ok "Volles Ziel: Lauf 2 endet rot"
  grep -q '^RUN2_PINGS=0' "${CASE14_OUT}" \
    || fail "Volles Ziel: Heartbeat wurde trotz gescheitertem Snapshot gepingt"
  ok "Volles Ziel: 0 Heartbeat-Pings"

  # Blocker 3: der Stand, auf den ein Restore zurueckfallen will, darf nie ein
  # Torso sein — entweder der alte Snapshot oder gar keiner.
  if grep -qE '^RUN2_SNAPSHOT_CHECK=(ok|fehlt)$' "${CASE14_OUT}"; then
    ok "Volles Ziel: Ziel-Snapshot ist intakt oder fehlt — kein Torso"
  else
    fail "Volles Ziel: der letzte gute Snapshot wurde beschaedigt ($(grep '^RUN2_SNAPSHOT_CHECK=' "${CASE14_OUT}"))"
  fi
  grep -qE '^RUN2_SNAPSHOT_ROWS=(2|fehlt)$' "${CASE14_OUT}" \
    || fail "Volles Ziel: Ziel-Snapshot ist weder der alte Stand noch abwesend"
  ok "Volles Ziel: Ziel-Snapshot traegt den alten Stand oder fehlt"

  grep -q '^LEFTOVER_SCRATCH=0' "${CASE14_OUT}" \
    || fail "Volles Ziel: Vorlauf-Verzeichnis blieb im Backup-Ziel liegen"
  ok "Volles Ziel: kein Vorlauf-Rest im Backup-Ziel"
fi

printf '\033[1;32m[backup-alarm]\033[0m alle Faelle gruen\n'
