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
#      schreiben. Fall 15 stellt das cross-uid nach (Backup als root, Store
#      unter fremder uid), was die Faelle 1–14 prinzipbedingt nicht messen
#      koennen: dort ist die Kennung beider Seiten dieselbe.
#   8) ein LEERER Bestand ist kein Erfolg: fehlt im Store eine Area, die der
#      Postgres-Katalog (`wa_table`) nennt, oder traegt das Bucket weniger
#      Objekte als `wa_blob`, ist der Lauf rot — und der Verwaisten-Sweep bzw.
#      `s3 sync --delete` raeumt den letzten guten lokalen Spiegel NICHT.
#      Der legitime Leerfall (leerer Katalog, leerer Store) bleibt gruen; genau
#      dafuer braucht es die zweite Wahrheitsquelle.
#
# Methode: pg_dump / gpg / restic / curl / aws / psql werden durch PATH-Stubs
# ersetzt, die sich per Env-Schalter zum Scheitern bringen lassen. `sqlite3` ist
# echt — die Tests legen richtige SQLite-Dateien an und lassen `VACUUM INTO`
# real laufen. Getestet wird die Ablauf-Logik des Skripts, nicht restic selbst.
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

# aws: simuliert `s3 sync` und `s3 ls`. `sync` schreibt im Erfolgsfall eine
# Pseudo-Objektdatei in das Zielverzeichnis (letztes Argument) und raeumt bei
# STUB_AWS_EMPTY_BUCKET=1 stattdessen wie `--delete` auf einem leeren Bucket.
# `ls` nennt so viele Objekte, wie STUB_AWS_BUCKET_OBJECTS sagt (Default 1).
cat >"${BIN}/aws" <<'STUB'
#!/usr/bin/env bash
dest="${!#}"
printf '%s\n' "$*" >>"${AWS_LOG}"
if [[ "${STUB_AWS_FAIL:-0}" == "1" ]]; then
  echo "stub-aws: failed (simuliert)" >&2
  exit 1
fi
if [[ " $* " == *" ls "* ]]; then
  n="${STUB_AWS_BUCKET_OBJECTS:-1}"
  for ((i = 0; i < n; i++)); do
    printf '2026-09-26 03:15:00         12 blobs/ws-1/obj%s\n' "${i}"
  done
  exit 0
fi
# sync
if [[ "${STUB_AWS_EMPTY_BUCKET:-0}" == "1" ]]; then
  # Genau das Verhalten, um das es geht: `--delete` auf einem leeren Bucket
  # raeumt den Spiegel leer und meldet Erfolg.
  rm -rf "${dest:?}"/*
  exit 0
fi
mkdir -p "${dest}/blobs/ws-1"
printf 'fake-object\n' >"${dest}/blobs/ws-1/deadbeef"
exit 0
STUB

# psql: der Katalog als zweite Wahrheitsquelle. Beantwortet genau die drei
# Abfragen, die backup.sh stellt — gesteuert ueber Env:
#   STUB_PSQL_FAIL=1              -> jede Abfrage scheitert
#   STUB_PSQL_NO_CATALOG=1        -> to_regclass sagt "Tabelle gibt es nicht"
#   STUB_PSQL_AREAS="a/b.sqlite"  -> Zeilen der wa_table-Abfrage (leer = Soll 0)
#   STUB_PSQL_BLOBS=N             -> count(*) aus wa_blob (Default 0)
cat >"${BIN}/psql" <<'STUB'
#!/usr/bin/env bash
sql=""
prev=""
for arg in "$@"; do
  [[ "${prev}" == "-c" ]] && sql="${arg}"
  prev="${arg}"
done
printf '%s\n' "${sql//$'\n'/ }" >>"${PSQL_LOG}"
if [[ "${STUB_PSQL_FAIL:-0}" == "1" ]]; then
  echo "stub-psql: connection failed (simuliert)" >&2
  exit 2
fi
case "${sql}" in
  *to_regclass*)
    if [[ "${STUB_PSQL_NO_CATALOG:-0}" == "1" ]]; then echo "f"; else echo "t"; fi
    ;;
  *wa_table*)
    [[ -n "${STUB_PSQL_AREAS:-}" ]] && printf '%s\n' "${STUB_PSQL_AREAS}"
    ;;
  *wa_blob*)
    echo "${STUB_PSQL_BLOBS:-0}"
    ;;
  *)
    echo "stub-psql: unerwartete Abfrage: ${sql}" >&2
    exit 3
    ;;
esac
exit 0
STUB

chmod +x "${BIN}"/*

HEARTBEAT_URL="https://status.internal.invalid/ping/who2be-backup"

# --- Tabellen-Store-Fixture ----------------------------------------------
# Echte SQLite-Dateien: `VACUUM INTO` und `PRAGMA quick_check` laufen real.
TABLESTORE_SRC="${ROOT}/tablestore"
# Derselbe relative Pfad, den der Katalog nennen wuerde:
# {workspace_id}/{area_id}.sqlite (tablestore/engine.py).
TABLESTORE_REL="11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite"
mk_tablestore() {
  rm -rf "${TABLESTORE_SRC}"
  mkdir -p "${TABLESTORE_SRC}/11111111-1111-1111-1111-111111111111"
  sqlite3 "${TABLESTORE_SRC}/${TABLESTORE_REL}" \
    "PRAGMA journal_mode=WAL; CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT); INSERT INTO t (v) VALUES ('a'),('b');" \
    >/dev/null
}
mk_tablestore

# run <case-name> — fuehrt backup.sh in einer frischen Sandbox aus.
# Setzt: RUN_EXIT, RUN_DIR, RUN_PINGS, RUN_OUT
#
# Die Katalog-Antworten (psql-Stub) haben Defaults, die zum Fixture passen: der
# Katalog nennt genau die Area, die auch im Store liegt, und keine Blobs. Faelle,
# die den Soll-Ist-Abgleich pruefen, ueberschreiben STUB_PSQL_* gezielt.
run() {
  local name="$1"
  RUN_DIR="${ROOT}/case-${name}"
  mkdir -p "${RUN_DIR}/backups"
  export HEARTBEAT_LOG="${RUN_DIR}/heartbeat.log"
  export RESTIC_LOG="${RUN_DIR}/restic.log"
  export AWS_LOG="${RUN_DIR}/aws.log"
  export PSQL_LOG="${RUN_DIR}/psql.log"
  : >"${HEARTBEAT_LOG}"
  : >"${RESTIC_LOG}"
  : >"${AWS_LOG}"
  : >"${PSQL_LOG}"

  set +e
  PATH="${BIN}:${PATH}" \
  POSTGRES_HOST=db POSTGRES_USER=u POSTGRES_DB=d PGPASSWORD=p \
  BACKUP_GPG_RECIPIENT=backup@example.org \
  BACKUP_DIR="${RUN_DIR}/backups" \
  HEARTBEAT_LOG="${HEARTBEAT_LOG}" \
  RESTIC_LOG="${RESTIC_LOG}" \
  AWS_LOG="${AWS_LOG}" \
  PSQL_LOG="${PSQL_LOG}" \
  STUB_PSQL_AREAS="${STUB_PSQL_AREAS-${TABLESTORE_REL}}" \
  STUB_PSQL_BLOBS="${STUB_PSQL_BLOBS-0}" \
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
log "1/17 Erfolgsfall (drei Bestaende, Offsite, Heartbeat)"
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
log "2/17 restic backup scheitert — rot, Dump bleibt, kein Ping"
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
log "3/17 restic forget scheitert — rot, Dump bleibt, kein Ping"
STUB_RESTIC_FAIL="forget" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run restic-forget-fail
assert_exit nonzero "Forget-Fehlschlag"
assert_dump_present "Forget-Fehlschlag"
assert_pings 0 "Forget-Fehlschlag"

# --- 4) Ohne neue Variablen: Verhalten unveraendert ----------------------
log "4/17 Offsite-Erfolg ohne BACKUP_HEARTBEAT_URL — unveraendert"
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
  run no-heartbeat
assert_exit zero "Ohne Alarmweg"
assert_dump_present "Ohne Alarmweg"
assert_pings 0 "Ohne Alarmweg"

# --- 5) Lokal-only (RESTIC_REPOSITORY leer) ------------------------------
log "5/17 Lokal-only mit Alarmweg — Erfolg, Ping, alle drei Bestaende lokal"
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" run local-only
assert_exit zero "Lokal-only"
assert_dump_present "Lokal-only"
assert_blob_mirror "Lokal-only"
assert_tablestore_snapshot "Lokal-only"
assert_pings 1 "Lokal-only"

# --- 6) Stummer Alarmweg ist selbst ein Fehlschlag -----------------------
log "6/17 Heartbeat-Ping scheitert — Lauf ist rot, Dump bleibt"
STUB_CURL_FAIL=1 \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run heartbeat-fail
assert_exit nonzero "Stummer Alarmweg"
assert_dump_present "Stummer Alarmweg"

# --- 7) TEILERFOLG: Blob-Sync scheitert — die Kernzusage dieser Karte ----
# pg_dump lief, restic lief, nur der Objekt-Store fehlt. Genau hier haette die
# alte Fassung "alles gut" gemeldet, waehrend ein Drittel fehlt.
log "7/17 Blob-Sync scheitert bei sonst gruenem Lauf — KEIN gruener Heartbeat"
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
log "8/17 Tabellen-Snapshot scheitert — KEIN gruener Heartbeat"
BROKEN_STORE="${ROOT}/tablestore-broken"
BROKEN_REL="33333333-3333-3333-3333-333333333333/44444444-4444-4444-4444-444444444444.sqlite"
rm -rf "${BROKEN_STORE}"
mkdir -p "${BROKEN_STORE}/33333333-3333-3333-3333-333333333333"
printf 'das ist keine sqlite-datei\n' \
  >"${BROKEN_STORE}/${BROKEN_REL}"
# Der Katalog nennt genau diese Area — sie LIEGT ja da, sie ist nur kaputt.
# Der Fall misst damit den Snapshot-Fehler und nicht den Soll-Ist-Abgleich.
WHO2BE_TABLESTORE_DIR="${BROKEN_STORE}" \
STUB_PSQL_AREAS="${BROKEN_REL}" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run tablestore-fail
assert_exit nonzero "Tabellen-Teilerfolg"
assert_dump_present "Tabellen-Teilerfolg"
assert_pings 0 "Tabellen-Teilerfolg"
assert_blob_mirror "Tabellen-Teilerfolg"       # Stufe 2 lief trotz Stufe-3-Fehler
assert_restic_tag incomplete "Tabellen-Teilerfolg"

# --- 9) Beide Zusatz-Stufen scheitern gleichzeitig -----------------------
log "9/17 Blob UND Tabellen-Store scheitern — beide Fehler im Log, kein Ping"
STUB_AWS_FAIL=1 \
WHO2BE_TABLESTORE_DIR="${BROKEN_STORE}" \
STUB_PSQL_AREAS="${BROKEN_REL}" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run both-fail
assert_exit nonzero "Doppel-Teilerfolg"
assert_pings 0 "Doppel-Teilerfolg"
grep -q '2 Stufe(n) fehlgeschlagen' "${RUN_DIR}/stdout.log" \
  || fail "Doppel-Teilerfolg: Log zaehlt nicht beide Stufen"
ok "Doppel-Teilerfolg: beide Stufen im Abschlussbericht"

# --- 10) Fehlende Konfiguration ist FATAL, nicht "uebersprungen" ---------
log "10/17 Store-Konfiguration fehlt — FATAL statt stillem Ueberspringen"
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
log "11/17 BACKUP_BLOBS=off / BACKUP_TABLESTORE=off — bewusste Abwahl, gruen"
BACKUP_BLOBS=off BACKUP_TABLESTORE=off \
WHO2BE_BLOBSTORE_ENDPOINT="" WHO2BE_TABLESTORE_DIR="/nonexistent" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run stores-off
assert_exit zero "Abwahl"
assert_dump_present "Abwahl"
assert_pings 1 "Abwahl"
assert_restic_tag dump "Abwahl"

# --- 12) LEERER Bestand ist kein Erfolg (Kernzusage dieser Karte) --------
# Bis 2026-09-26 war ein vorhandenes, LEERES Store-Verzeichnis nicht von einem
# legitim leeren Stand zu unterscheiden: `[[ ! -d ]]` passierte, die
# find-Schleife lief null Mal, die Merkliste blieb leer — und der
# Verwaisten-Sweep hielt damit JEDEN vorhandenen Snapshot fuer verwaist. Der
# Lauf endete gruen, pingte den Heartbeat, trug --tag dump und raeumte im
# Vorbeigehen den letzten lokalen Spiegel.
#
# Zwei Laeufe auf DASSELBE ${BACKUP_DIR}, weil nur so messbar ist, dass der
# Spiegel nicht geraeumt wird: Lauf 1 legt einen guten Snapshot an, Lauf 2
# sieht ein leeres Store-Verzeichnis bei nichtleerem Katalog.
log "12/17 Leerer Store bei nichtleerem Katalog — rot, kein Ping, Spiegel bleibt"
SHARED_DIR="${ROOT}/case-empty-store/backups"
mkdir -p "${SHARED_DIR}"

run_shared() {
  RUN_DIR="${ROOT}/case-empty-store"
  export HEARTBEAT_LOG="${RUN_DIR}/heartbeat.log"
  export RESTIC_LOG="${RUN_DIR}/restic.log"
  export AWS_LOG="${RUN_DIR}/aws.log"
  export PSQL_LOG="${RUN_DIR}/psql.log"
  : >"${HEARTBEAT_LOG}"
  : >"${RESTIC_LOG}"
  : >"${AWS_LOG}"
  : >"${PSQL_LOG}"
  set +e
  PATH="${BIN}:${PATH}" \
  POSTGRES_HOST=db POSTGRES_USER=u POSTGRES_DB=d PGPASSWORD=p \
  BACKUP_GPG_RECIPIENT=backup@example.org \
  BACKUP_DIR="${SHARED_DIR}" BACKUP_BLOBS=off \
  HEARTBEAT_LOG="${HEARTBEAT_LOG}" RESTIC_LOG="${RESTIC_LOG}" \
  AWS_LOG="${AWS_LOG}" PSQL_LOG="${PSQL_LOG}" \
  BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
  STUB_PSQL_AREAS="${STUB_PSQL_AREAS-${TABLESTORE_REL}}" \
  STUB_PSQL_BLOBS=0 \
  WHO2BE_TABLESTORE_DIR="$1" \
    bash "${BACKUP_SH}" >"${RUN_DIR}/stdout.log" 2>&1
  RUN_EXIT=$?
  set -e
  RUN_PINGS="$(wc -l <"${HEARTBEAT_LOG}" | tr -d ' ')"
  RUN_OUT="$(find "${SHARED_DIR}" -maxdepth 1 -name 'dump-*.pgc.gpg' | wc -l | tr -d ' ')"
}

SHARED_SNAP="${SHARED_DIR}/tablestore/${TABLESTORE_REL}"

# Lauf 1: echter Store — legt den Spiegel an, auf den ein Restore zurueckfallen
# koennen muss.
run_shared "${TABLESTORE_SRC}"
assert_exit zero "Leerer Store/Vorlauf"
[[ -s "${SHARED_SNAP}" ]] \
  || fail "Leerer Store/Vorlauf: Lauf 1 hat keinen Snapshot hinterlassen — Aufbau taugt nicht"
ok "Leerer Store/Vorlauf: Lauf 1 gruen, guter Spiegel am Ziel"

# Lauf 2: vorhandenes, LEERES Store-Verzeichnis. Der Katalog nennt weiter eine
# Area — also ist das Datenverlust und kein Leerlauf.
EMPTY_STORE="${ROOT}/tablestore-empty"
mkdir -p "${EMPTY_STORE}"
run_shared "${EMPTY_STORE}"
assert_exit nonzero "Leerer Store"
assert_dump_present "Leerer Store"
assert_pings 0 "Leerer Store"
assert_restic_tag incomplete "Leerer Store"
grep -q "erwartete Area-Datei(en) fehlen" "${RUN_DIR}/stdout.log" \
  || fail "Leerer Store: Log benennt die fehlende Area nicht"
ok "Leerer Store: Log benennt die laut Katalog fehlende Area"
# Die dritte Zusage der Karte: kein Lauf loescht den letzten guten Spiegel,
# waehrend er selbst scheitert.
[[ -s "${SHARED_SNAP}" ]] \
  || fail "Leerer Store: der letzte gute Spiegel wurde im gescheiterten Lauf geraeumt"
[[ "$(sqlite3 "${SHARED_SNAP}" 'SELECT count(*) FROM t')" == "2" ]] \
  || fail "Leerer Store: der letzte gute Spiegel traegt nicht mehr den alten Stand"
ok "Leerer Store: letzter guter Spiegel unangetastet (2 Zeilen, lesbar)"
grep -q 'Stufe rot — verwaiste Snapshots werden NICHT geraeumt' "${RUN_DIR}/stdout.log" \
  || fail "Leerer Store: Log erklaert nicht, warum der Sweep ausblieb"
ok "Leerer Store: Log erklaert den ausgesetzten Verwaisten-Sweep"

# --- 13) Der LEGITIME Leerfall bleibt gruen ------------------------------
# Ein frischer Stack hat Areas noch gar nicht: leerer Katalog, leerer Store.
# Genau das ist der Grund, warum diese Pruefung eine zweite Wahrheitsquelle
# braucht und nicht einfach "0 Dateien = Fehler" sagen kann.
log "13/17 Leerer Katalog + leerer Store — legitimer Leerfall, gruen"
EMPTY_STORE2="${ROOT}/tablestore-empty-legit"
mkdir -p "${EMPTY_STORE2}"
WHO2BE_TABLESTORE_DIR="${EMPTY_STORE2}" \
STUB_PSQL_AREAS="" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run empty-legit
assert_exit zero "Legitimer Leerfall"
assert_dump_present "Legitimer Leerfall"
assert_pings 1 "Legitimer Leerfall"
assert_restic_tag dump "Legitimer Leerfall"
grep -q 'Tabellen-Snapshots: 0 Datei(en)' "${RUN_DIR}/stdout.log" \
  || fail "Legitimer Leerfall: Log meldet nicht null Snapshots"
ok "Legitimer Leerfall: null Snapshots, Lauf trotzdem gruen"

# Dasselbe, wenn die Katalog-Tabelle noch gar nicht existiert (Stack vor
# Migration 0078): auch das ist Soll 0 und kein Fehler.
log "13b/17 Katalog-Tabelle existiert noch nicht — ebenfalls gruen"
WHO2BE_TABLESTORE_DIR="${EMPTY_STORE2}" \
STUB_PSQL_NO_CATALOG=1 \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run no-catalog
assert_exit zero "Kein Katalog"
assert_pings 1 "Kein Katalog"
assert_restic_tag dump "Kein Katalog"

# Und der Gegenpol: ist der Katalog NICHT befragbar, ist das ein Fehlschlag und
# kein stilles Soll 0 — sonst waere die Zusage mit einem psql-Ausfall abwaehlbar.
log "13c/17 Katalog nicht befragbar — rot statt stillem Soll 0"
WHO2BE_TABLESTORE_DIR="${EMPTY_STORE2}" \
STUB_PSQL_FAIL=1 \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run catalog-down
assert_exit nonzero "Katalog unerreichbar"
assert_pings 0 "Katalog unerreichbar"
assert_restic_tag incomplete "Katalog unerreichbar"

# --- 14) Dieselbe Klasse in Stufe 2: leeres Bucket + --delete ------------
# `aws s3 sync --delete` auf einem leeren oder falschen Bucket leert den
# Blob-Spiegel und meldet Exit 0. Der Abgleich zaehlt das Bucket-Inventar VOR
# dem Sync, damit --delete in diesem Fall gar nicht erst laeuft.
log "14/17 Leeres Bucket bei nichtleerem wa_blob-Katalog — rot, Spiegel bleibt"
BLOB_SHARED="${ROOT}/case-empty-bucket/backups"
mkdir -p "${BLOB_SHARED}"

run_blob_shared() {
  RUN_DIR="${ROOT}/case-empty-bucket"
  export HEARTBEAT_LOG="${RUN_DIR}/heartbeat.log"
  export RESTIC_LOG="${RUN_DIR}/restic.log"
  export AWS_LOG="${RUN_DIR}/aws.log"
  export PSQL_LOG="${RUN_DIR}/psql.log"
  : >"${HEARTBEAT_LOG}"
  : >"${RESTIC_LOG}"
  : >"${AWS_LOG}"
  : >"${PSQL_LOG}"
  set +e
  PATH="${BIN}:${PATH}" \
  POSTGRES_HOST=db POSTGRES_USER=u POSTGRES_DB=d PGPASSWORD=p \
  BACKUP_GPG_RECIPIENT=backup@example.org \
  BACKUP_DIR="${BLOB_SHARED}" BACKUP_TABLESTORE=off \
  HEARTBEAT_LOG="${HEARTBEAT_LOG}" RESTIC_LOG="${RESTIC_LOG}" \
  AWS_LOG="${AWS_LOG}" PSQL_LOG="${PSQL_LOG}" \
  BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
  WHO2BE_BLOBSTORE_ENDPOINT=seaweedfs:8333 \
  WHO2BE_BLOBSTORE_ACCESS_KEY=who2be WHO2BE_BLOBSTORE_SECRET_KEY=secret \
  STUB_PSQL_BLOBS="$1" \
  STUB_AWS_BUCKET_OBJECTS="$2" \
  STUB_AWS_EMPTY_BUCKET="${3:-0}" \
    bash "${BACKUP_SH}" >"${RUN_DIR}/stdout.log" 2>&1
  RUN_EXIT=$?
  set -e
  RUN_PINGS="$(wc -l <"${HEARTBEAT_LOG}" | tr -d ' ')"
  RUN_OUT="$(find "${BLOB_SHARED}" -maxdepth 1 -name 'dump-*.pgc.gpg' | wc -l | tr -d ' ')"
}

# Lauf 1: Katalog nennt 1 Blob, Bucket traegt 1 — Spiegel entsteht.
run_blob_shared 1 1 0
assert_exit zero "Leeres Bucket/Vorlauf"
assert_blob_mirror "Leeres Bucket/Vorlauf"

# Lauf 2: das Bucket ist leer (umbenannt / falscher Endpoint), der Katalog
# nennt weiter 1 Objekt. Der Sync darf nicht laufen.
run_blob_shared 1 0 1
assert_exit nonzero "Leeres Bucket"
assert_dump_present "Leeres Bucket"
assert_pings 0 "Leeres Bucket"
assert_restic_tag incomplete "Leeres Bucket"
assert_blob_mirror "Leeres Bucket"   # <- --delete lief NICHT
grep -q 'Sync NICHT ausgefuehrt' "${RUN_DIR}/stdout.log" \
  || fail "Leeres Bucket: Log sagt nicht, dass der Sync unterblieb"
ok "Leeres Bucket: Log nennt den unterbliebenen Sync"
grep -q 's3 sync' "${RUN_DIR}/aws.log" \
  && fail "Leeres Bucket: s3 sync --delete lief trotzdem"
ok "Leeres Bucket: kein s3-sync-Aufruf im aws-Log"

printf '\033[1;32m[backup-alarm]\033[0m Faelle 1–14 gruen\n'

# --- 15) Der Lauf darf den Schreibpfad der API nicht verbiegen -----------
# Der Betriebsfall, den die Faelle 1–14 strukturell NICHT messen koennen: dort
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
# Backup-Nutzer haengen. Fall 15 misst den bequemen Fall, Fall 16 den, der die
# Zusage wirklich traegt: ohne ihn waere dieser Test gegen die Vorfassung gruen
# (selbst gemessen) und damit kein Regressionsschutz.
log "15/17 Cross-UID mit CAP_CHOWN: Backup als root, Store gehoert der API"

if ! command -v unshare >/dev/null 2>&1 \
   || ! command -v setpriv >/dev/null 2>&1 \
   || ! unshare -rm --map-auto true 2>/dev/null; then
  printf '  ⚠ 15+16+17 uebersprungen: unprivilegierte User-Namespaces (unshare --map-auto) nicht verfuegbar\n'
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
PSQL_LOG="${W}/psql.log" \
STUB_PSQL_AREAS="11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite" \
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

# --- 16) Dasselbe OHNE CAP_CHOWN — der Fall, der die Zusage traegt -------
# Ohne die Capability kann SQLite die Seitendateien nicht mehr selbst auf den
# Eigentuemer der Datenbank ziehen. Genau hier scheitert die Vorfassung (selbst
# gemessen: root-eigene -wal/-shm, danach "attempt to write a readonly
# database"), und genau hier muss der Umbau tragen: der Lesevorgang laeuft
# unter der Kennung des Eigentuemers, und das Ergebnis wird geprueft statt
# geglaubt.
log "16/17 Cross-UID OHNE CAP_CHOWN — Zusage haengt nicht an einer Capability"
CASE13_OUT="${ROOT}/case13.log"
unshare -rm --map-auto bash "${ROOT}/case12-inner.sh" "${BACKUP_SH}" "${BIN}" drop-chown >"${CASE13_OUT}" 2>&1 || true
assert_crossuid "${CASE13_OUT}" "Cross-UID (ohne CAP_CHOWN)"

# --- 17) Volles Zieldateisystem: rot, und der letzte gute Stand bleibt ----
# Der Fall, den die Faelle 1–16 prinzipbedingt NICHT messen koennen: dort liegen
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
log '17/17 Backup-Ziel laeuft voll — Lauf rot, kein Ping, letzter guter Snapshot intakt'

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
export PSQL_LOG="${W}/psql.log"
# Der Katalog nennt genau die Area, die im Store liegt — der Fall misst das
# volle Zieldateisystem, nicht den Soll-Ist-Abgleich.
export STUB_PSQL_AREAS="11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.sqlite"

run_backup() {
  : >"${HEARTBEAT_LOG}"; : >"${RESTIC_LOG}"; : >"${AWS_LOG}"; : >"${PSQL_LOG}"
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
