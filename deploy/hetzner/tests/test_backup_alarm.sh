#!/usr/bin/env bash
# Alarm-Verhalten des Backup-Skripts (#541).
#
# Belegt ohne Docker-Daemon und ohne Postgres, was das Issue verlangt:
#   1) ein fehlgeschlagener Offsite-Sync ist von aussen erkennbar (Exit != 0,
#      kein Heartbeat) — die Erfolgsmeldung faellt weg;
#   2) der lokale GPG-Dump bleibt dabei in JEDEM Fall erhalten (harte Bedingung,
#      Zusage aus backup.sh und ADR-0011 gilt unveraendert);
#   3) ohne gesetzte BACKUP_HEARTBEAT_URL ist das Verhalten unveraendert.
#
# Methode: pg_dump / gpg / restic / curl werden durch PATH-Stubs ersetzt, die
# sich per Env-Schalter zum Scheitern bringen lassen. Getestet wird die
# Ablauf-Logik des Skripts, nicht restic selbst.
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
# `cat config` meldet ein bestehendes Repo (kein init noetig).
cat >"${BIN}/restic" <<'STUB'
#!/usr/bin/env bash
sub="${1:-}"
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

chmod +x "${BIN}"/*

HEARTBEAT_URL="https://status.internal.invalid/ping/who2be-backup"

# run <case-name> — fuehrt backup.sh in einer frischen Sandbox aus.
# Setzt: RUN_EXIT, RUN_DIR, RUN_PINGS, RUN_OUT
run() {
  local name="$1"
  RUN_DIR="${ROOT}/case-${name}"
  mkdir -p "${RUN_DIR}/backups"
  export HEARTBEAT_LOG="${RUN_DIR}/heartbeat.log"
  : >"${HEARTBEAT_LOG}"

  set +e
  PATH="${BIN}:${PATH}" \
  POSTGRES_HOST=db POSTGRES_USER=u POSTGRES_DB=d PGPASSWORD=p \
  BACKUP_GPG_RECIPIENT=backup@example.org \
  BACKUP_DIR="${RUN_DIR}/backups" \
  HEARTBEAT_LOG="${HEARTBEAT_LOG}" \
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

# --- 1) Erfolgsfall mit Offsite + Alarmweg -------------------------------
log "1/6 Erfolgsfall (Offsite + Heartbeat)"
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run success
assert_exit zero "Erfolgsfall"
assert_dump_present "Erfolgsfall"
assert_pings 1 "Erfolgsfall"

# --- 2) restic backup scheitert (Kernfall des Issues) --------------------
log "2/6 restic backup scheitert — rot, Dump bleibt, kein Ping"
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
log "3/6 restic forget scheitert — rot, Dump bleibt, kein Ping"
STUB_RESTIC_FAIL="forget" \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run restic-forget-fail
assert_exit nonzero "Forget-Fehlschlag"
assert_dump_present "Forget-Fehlschlag"
assert_pings 0 "Forget-Fehlschlag"

# --- 4) Ohne neue Variablen: Verhalten unveraendert ----------------------
log "4/6 Offsite-Erfolg ohne BACKUP_HEARTBEAT_URL — unveraendert"
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
  run no-heartbeat
assert_exit zero "Ohne Alarmweg"
assert_dump_present "Ohne Alarmweg"
assert_pings 0 "Ohne Alarmweg"

# --- 5) Lokal-only (RESTIC_REPOSITORY leer) ------------------------------
log "5/6 Lokal-only mit Alarmweg — Erfolg, Ping"
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" run local-only
assert_exit zero "Lokal-only"
assert_dump_present "Lokal-only"
assert_pings 1 "Lokal-only"

# --- 6) Stummer Alarmweg ist selbst ein Fehlschlag -----------------------
log "6/6 Heartbeat-Ping scheitert — Lauf ist rot, Dump bleibt"
STUB_CURL_FAIL=1 \
RESTIC_REPOSITORY="local:${ROOT}/repo" RESTIC_PASSWORD=x \
BACKUP_HEARTBEAT_URL="${HEARTBEAT_URL}" \
  run heartbeat-fail
assert_exit nonzero "Stummer Alarmweg"
assert_dump_present "Stummer Alarmweg"

printf '\033[1;32m[backup-alarm]\033[0m alle Faelle gruen\n'
