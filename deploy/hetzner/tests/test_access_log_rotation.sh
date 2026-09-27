#!/usr/bin/env bash
# Rotation und Loeschfrist der Caddy-Access-Logs (W8/S1) — Wirkung, nicht Wortlaut.
#
# Warum dieser Test existiert: die Vorgaenger-Pruefungen suchten Zeichenketten in
# Markdown und blieben deshalb gruen, waehrend die Frist nicht griff. Dieser Test
# FUEHRT das Verfahren aus, gegen echte Verzeichnisse und (wo vorhanden) gegen das
# echte Caddy-Image.
#
# Faelle:
#   1) Es gibt keine aktive `access.log` (frischer Container, noch kein Request) —
#      die LOESCHUNG laeuft trotzdem, und der Lauf gilt als Erfolg. Das war der
#      Befund: als `&&`-Kette haengte die Loeschung an der Rotation und fiel jede
#      Nacht ohne Anfrage mit aus.
#   2) Beide Namensklassen werden geloescht: die Generationen dieses Skripts
#      (`access.log.<ts>.gz`) UND Caddys eigene groessenbedingte Generationen
#      (`access-<ts>.log.gz`). Sie sind disjunkt benannt; ein Loeschmuster fuer
#      nur eine Klasse laesst die andere unbegrenzt liegen.
#   3) Die Loeschschwelle trifft das gemeinte Fenster: eine Generation eine
#      Sekunde unterhalb der Schwelle bleibt, eine darueber verschwindet.
#      Gemessen, nicht aus der `find`-Semantik hergeleitet.
#   4) Rotation legt eine Generation an, und Caddy wird danach neu gestartet
#      (ohne Neustart entsteht keine neue `access.log` — der Prozess schreibt in
#      den umbenannten Inode weiter).
#   5) Ein Fehlschlag ist NICHT still: scheitert die Rotation oder der Neustart,
#      endet der Lauf mit Exit != 0, der Erfolgsstempel bleibt alt und ein
#      gesetzter Heartbeat wird NICHT gepingt.
#   6) Der Erfolgsstempel wird bei Erfolg geschrieben. Er ist der einzige
#      Unterschied zwischen „Cron lief und hatte nichts zu tun" und „Cron lief
#      nie" — ein leeres Log-Verzeichnis sieht in beiden Faellen gleich aus.
#
# Methode: `ACCESS_LOG_SH` bekommt eine Shell, die auf einem echten
# Temporaerverzeichnis arbeitet, `ACCESS_LOG_RESTART_CMD` einen Stub, der seinen
# Aufruf protokolliert. Ist `podman`/`docker` samt `caddy:2.8-alpine` verfuegbar,
# laeuft der Container-Teil im ECHTEN Image (busybox-`find`/`gzip` verhalten sich
# nicht wie GNU); sonst in der Host-Shell, mit sichtbarem Hinweis.
#
# Aufruf:
#   bash deploy/hetzner/tests/test_access_log_rotation.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROTATE_SH="${SCRIPT_DIR}/../scripts/rotate-access-log.sh"
CADDY_IMAGE="${CADDY_IMAGE:-docker.io/library/caddy:2.8-alpine}"

log()  { printf '\033[1;34m[access-log-rotation]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[access-log-rotation:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }
ok()   { printf '  ✓ %s\n' "$*"; }

[[ -r "${ROTATE_SH}" ]] || fail "rotate-access-log.sh nicht gefunden: ${ROTATE_SH}"

ROOT="$(mktemp -d "${TMPDIR:-/tmp}/who2be-access-log.XXXXXX")"

# Aufraeumen. Unter Docker laufen die Container als root, die erzeugten
# Generationen gehoeren dann root und ein `rm -rf` als Runner-Nutzer scheitert.
# Deshalb zuerst der Versuch, den Inhalt im Container zu entfernen (dort ist man
# root), dann regulaer. Bewusst best-effort: das Aufraeumen darf das Testergebnis
# nicht kippen.
cleanup() {
    local status=$?
    if [[ -n "${CONTAINER_RUNTIME:-}" ]]; then
        "${CONTAINER_RUNTIME}" run --rm -v "${ROOT}:/cleanup" "${CADDY_IMAGE}" \
            sh -c 'rm -rf /cleanup/* /cleanup/.[!.]* 2>/dev/null || true' >/dev/null 2>&1 || true
    fi
    rm -rf "${ROOT}" 2>/dev/null || true
    exit "${status}"
}
trap cleanup EXIT

# --- Ausfuehrungsumgebung waehlen ---------------------------------------
# Das echte Image ist der Maszstab: die Kommandos im Skript laufen dort unter
# busybox, nicht unter GNU-coreutils.
CONTAINER_RUNTIME=""
for candidate in podman docker; do
    if command -v "${candidate}" >/dev/null 2>&1 &&
        "${candidate}" image exists "${CADDY_IMAGE}" >/dev/null 2>&1; then
        CONTAINER_RUNTIME="${candidate}"
        break
    fi
    # `docker` kennt kein `image exists`.
    if command -v "${candidate}" >/dev/null 2>&1 &&
        "${candidate}" image inspect "${CADDY_IMAGE}" >/dev/null 2>&1; then
        CONTAINER_RUNTIME="${candidate}"
        break
    fi
done

if [[ -n "${CONTAINER_RUNTIME}" ]]; then
    log "Container-Teil laeuft im echten Image (${CONTAINER_RUNTIME}, ${CADDY_IMAGE})"
else
    log "HINWEIS: ${CADDY_IMAGE} nicht verfuegbar — Container-Teil laeuft in der"
    log "         Host-Shell. Die Ablauf-Logik wird voll geprueft, das"
    log "         busybox-Verhalten von find/gzip NICHT."
fi

# Setzt ACCESS_LOG_SH fuer ein gegebenes Log-Verzeichnis.
# `:Z` (SELinux-Relabeling) nur unter podman: Docker akzeptiert die Option
# zwar, aber sie ist dort nicht noetig und auf Runnern ohne SELinux
# irrelevant — eine Laufzeit-Eigenheit soll den Test nicht tragen.
container_sh_for() {
    local dir="$1" mount_opts=""
    if [[ "${CONTAINER_RUNTIME}" == "podman" ]]; then
        mount_opts=":Z"
    fi
    if [[ -n "${CONTAINER_RUNTIME}" ]]; then
        # Bewusst OHNE `--user`: unter podman rootless bildet der Namespace den
        # Host-Nutzer auf root ab, eine explizite Host-UID hat dort dann KEINE
        # Schreibrechte auf dem Mount (gemessen). Die Aufraeum-Frage, die
        # `--user` loesen sollte, loest stattdessen der trap unten.
        printf '%s run --rm -i -v %s:/var/log/caddy%s %s sh' \
            "${CONTAINER_RUNTIME}" "${dir}" "${mount_opts}" "${CADDY_IMAGE}"
    else
        printf 'sh'
    fi
}

# Legt ein frisches Log-Verzeichnis an und gibt seinen Pfad aus.
new_case() {
    local name="$1" dir="${ROOT}/${1}/logs"
    mkdir -p "${dir}"
    printf '%s' "${dir}"
}

# Fuehrt das Skript fuer ein Verzeichnis aus. Zusaetzliche Env via Aufrufer.
run_rotate() {
    local dir="$1" restart_marker="$2" stamp="$3"
    shift 3
    local sh_cmd log_dir
    sh_cmd="$(container_sh_for "${dir}")"
    if [[ -n "${CONTAINER_RUNTIME}" ]]; then
        log_dir="/var/log/caddy"
    else
        log_dir="${dir}"
    fi
    env \
        ACCESS_LOG_DIR="${log_dir}" \
        ACCESS_LOG_SH="${sh_cmd}" \
        ACCESS_LOG_RESTART_CMD="touch ${restart_marker}" \
        ACCESS_LOG_STAMP_FILE="${stamp}" \
        "$@" \
        bash "${ROTATE_SH}"
}

# Legt eine Datei mit definiertem Alter in SEKUNDEN an.
age_file() {
    local path="$1" seconds="$2"
    printf 'log-line\n' >"${path}"
    touch -d "@$(($(date +%s) - seconds))" "${path}"
}

# --- Fall 1 + 2 + 6: keine aktive Datei, beide Namensklassen, Stempel ----
log "Fall 1/2/6 — kein Request seit dem Start: Loeschung laeuft trotzdem"
dir="$(new_case no-active-file)"
stamp="${ROOT}/no-active-file/stamp"
restart="${ROOT}/no-active-file/restarted"
age_file "${dir}/access.log.20260101000000.gz" $((20 * 86400))
age_file "${dir}/access-2026-08-26T00-00-00.000.log.gz" $((30 * 86400))
age_file "${dir}/access.log.20260924000000.gz" $((1 * 86400))
[[ ! -f "${dir}/access.log" ]] || fail "Aufbau falsch: aktive Datei darf hier fehlen"

run_rotate "${dir}" "${restart}" "${stamp}" >"${ROOT}/no-active-file/out.txt" 2>&1 ||
    fail "fehlende aktive Datei ist kein Fehler, das Skript endete aber rot:
$(cat "${ROOT}/no-active-file/out.txt")"
ok "Exit 0, obwohl keine aktive Datei existierte"

[[ ! -f "${dir}/access.log.20260101000000.gz" ]] ||
    fail "alte Cron-Generation nicht geloescht — genau der gemeldete Befund"
ok "alte Generation dieses Skripts (access.log.<ts>.gz) geloescht"

[[ ! -f "${dir}/access-2026-08-26T00-00-00.000.log.gz" ]] ||
    fail "alte Caddy-Generation (access-<ts>.log.gz) nicht geloescht — die beiden
Namensklassen sind disjunkt, ein Muster fuer nur eine laesst die andere liegen"
ok "alte Caddy-eigene Generation (access-<ts>.log.gz) geloescht"

[[ -f "${dir}/access.log.20260924000000.gz" ]] ||
    fail "junge Generation wurde mitgeloescht — Frist zu scharf"
ok "junge Generation blieb erhalten"

[[ ! -f "${restart}" ]] ||
    fail "Caddy wurde neu gestartet, obwohl nichts rotiert wurde (unnoetige Unterbrechung)"
ok "kein Neustart ohne Rotation"

[[ -s "${stamp}" ]] || fail "Erfolgsstempel nicht geschrieben"
ok "Erfolgsstempel geschrieben ($(cat "${stamp}"))"

# --- Fall 3: die Loeschschwelle trifft das gemeinte Fenster --------------
# Erwartet wird die Kette aus dem Skript: Schwelle = Frist - 2, und `-mtime +N`
# greift ab einem Alter von mehr als N vollen Tagen. Bei Frist 14 heisst das:
# 13 Tage weg, 12 Tage bleiben. Gemessen, nicht hergeleitet.
log "Fall 3 — Loeschschwelle: 13 Tage weg, 12 Tage bleiben (Frist 14)"
dir="$(new_case threshold)"
stamp="${ROOT}/threshold/stamp"
restart="${ROOT}/threshold/restarted"
age_file "${dir}/access.log.keep12.gz" $((12 * 86400 + 3600))
age_file "${dir}/access.log.drop13.gz" $((13 * 86400 + 3600))
run_rotate "${dir}" "${restart}" "${stamp}" >/dev/null 2>&1 ||
    fail "Schwellen-Fall endete rot"

[[ -f "${dir}/access.log.keep12.gz" ]] ||
    fail "12 Tage alte Generation geloescht — die Schwelle liegt zu niedrig"
[[ ! -f "${dir}/access.log.drop13.gz" ]] ||
    fail "13 Tage alte Generation blieb liegen — bei zugesagten 14 Tagen waere ein
Eintrag darin bis zu 15 Tage alt, die Frist waere ueberschritten"
ok "Fenster trifft: 12 Tage bleiben, 13 Tage werden geloescht"

# Gegenprobe zur Frist-Kette: mit ACCESS_LOG_RETENTION_DAYS=7 muss die Schwelle
# mitwandern (5 → loescht ab 6 Tagen). Ein hart verdrahtetes +14 fiele hier auf.
log "Fall 3b — Frist ist parametrisch: 7 Tage Frist loescht eine 6 Tage alte Generation"
dir="$(new_case threshold-7)"
stamp="${ROOT}/threshold-7/stamp"
restart="${ROOT}/threshold-7/restarted"
age_file "${dir}/access.log.age4.gz" $((4 * 86400 + 3600))
age_file "${dir}/access.log.age6.gz" $((6 * 86400 + 3600))
run_rotate "${dir}" "${restart}" "${stamp}" ACCESS_LOG_RETENTION_DAYS=7 >/dev/null 2>&1 ||
    fail "parametrischer Fall endete rot"
[[ -f "${dir}/access.log.age4.gz" ]] || fail "4 Tage alt geloescht bei Frist 7"
[[ ! -f "${dir}/access.log.age6.gz" ]] ||
    fail "6 Tage alt blieb liegen bei Frist 7 — Schwelle wandert nicht mit der Frist"
ok "Schwelle folgt der Frist statt hart verdrahtet zu sein"

# --- Fall 4: Rotation + Neustart ----------------------------------------
log "Fall 4 — aktive Datei vorhanden: rotiert, komprimiert, Caddy neu gestartet"
dir="$(new_case rotate)"
stamp="${ROOT}/rotate/stamp"
restart="${ROOT}/rotate/restarted"
printf '{"level":"info"}\n' >"${dir}/access.log"
run_rotate "${dir}" "${restart}" "${stamp}" >/dev/null 2>&1 ||
    fail "Rotationsfall endete rot"

[[ ! -f "${dir}/access.log" ]] ||
    fail "aktive Datei liegt noch da — nicht rotiert"
generations=("${dir}"/access.log.*.gz)
[[ -f "${generations[0]}" ]] ||
    fail "keine komprimierte Generation entstanden: $(ls -A "${dir}")"
ok "aktive Datei rotiert und komprimiert ($(basename "${generations[0]}"))"

[[ -f "${restart}" ]] ||
    fail "Caddy NICHT neu gestartet — ohne Neustart schreibt der Prozess in den
umbenannten Inode weiter und es entsteht keine neue access.log"
ok "Caddy nach der Rotation neu gestartet"

# --- Fall 5: Fehlschlaege sind nicht still ------------------------------
log "Fall 5a — Neustart scheitert: Exit != 0, kein Stempel, kein Heartbeat"
dir="$(new_case restart-fails)"
stamp="${ROOT}/restart-fails/stamp"
printf 'alt\n' >"${stamp}"
printf '{"level":"info"}\n' >"${dir}/access.log"
pinged="${ROOT}/restart-fails/pinged"
sh_cmd="$(container_sh_for "${dir}")"
if [[ -n "${CONTAINER_RUNTIME}" ]]; then log_dir="/var/log/caddy"; else log_dir="${dir}"; fi
# Heartbeat-Stub: eine URL, die es nicht gibt, wuerde auch scheitern — deshalb
# ein PATH-Stub, der seinen Aufruf protokolliert. So ist „nicht gepingt"
# unterscheidbar von „Ping fehlgeschlagen".
STUBBIN="${ROOT}/restart-fails/bin"
mkdir -p "${STUBBIN}"
printf '#!/usr/bin/env bash\ntouch %s\nexit 0\n' "${pinged}" >"${STUBBIN}/curl"
chmod +x "${STUBBIN}/curl"
env \
    PATH="${STUBBIN}:${PATH}" \
    ACCESS_LOG_DIR="${log_dir}" \
    ACCESS_LOG_SH="${sh_cmd}" \
    ACCESS_LOG_RESTART_CMD="false" \
    ACCESS_LOG_STAMP_FILE="${stamp}" \
    ACCESS_LOG_HEARTBEAT_URL="http://heartbeat.invalid/ping" \
    bash "${ROTATE_SH}" >"${ROOT}/restart-fails/out.txt" 2>&1
status=$?
((status != 0)) || fail "gescheiterter Neustart endete mit Exit 0 — stiller Fehlschlag"
ok "Exit ${status} bei gescheitertem Neustart"

[[ "$(cat "${stamp}")" == "alt" ]] ||
    fail "Erfolgsstempel nach Fehlschlag ueberschrieben — ein Waechter, der den
Stempel prueft, saehe einen erfolgreichen Lauf"
ok "Erfolgsstempel unveraendert"

[[ ! -f "${pinged}" ]] ||
    fail "Heartbeat trotz Fehlschlag gepingt — der Dead-Man's-Switch waere blind"
ok "kein Heartbeat nach Fehlschlag"

grep -q "FEHLER" "${ROOT}/restart-fails/out.txt" ||
    fail "Fehlschlag ohne FEHLER-Zeile in der Ausgabe: $(cat "${ROOT}/restart-fails/out.txt")"
ok "Fehlschlag steht als FEHLER in der Ausgabe"

log "Fall 5b — Erfolg pingt den Heartbeat"
dir="$(new_case heartbeat-ok)"
stamp="${ROOT}/heartbeat-ok/stamp"
pinged="${ROOT}/heartbeat-ok/pinged"
STUBBIN="${ROOT}/heartbeat-ok/bin"
mkdir -p "${STUBBIN}"
printf '#!/usr/bin/env bash\ntouch %s\nexit 0\n' "${pinged}" >"${STUBBIN}/curl"
chmod +x "${STUBBIN}/curl"
sh_cmd="$(container_sh_for "${dir}")"
if [[ -n "${CONTAINER_RUNTIME}" ]]; then log_dir="/var/log/caddy"; else log_dir="${dir}"; fi
env \
    PATH="${STUBBIN}:${PATH}" \
    ACCESS_LOG_DIR="${log_dir}" \
    ACCESS_LOG_SH="${sh_cmd}" \
    ACCESS_LOG_RESTART_CMD="true" \
    ACCESS_LOG_STAMP_FILE="${stamp}" \
    ACCESS_LOG_HEARTBEAT_URL="http://heartbeat.invalid/ping" \
    bash "${ROTATE_SH}" >/dev/null 2>&1 ||
    fail "Erfolgsfall mit Heartbeat endete rot"
[[ -f "${pinged}" ]] || fail "Heartbeat bei Erfolg NICHT gepingt"
ok "Heartbeat bei Erfolg gepingt"

log "alle Faelle gruen"
