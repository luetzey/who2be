#!/usr/bin/env bash
# Rotation und Aufbewahrungsfrist der Caddy-Access-Logs (W8/S1).
#
# Warum ein Skript und keine Crontab-Zeile: die Aufgabe hat drei Teile, die
# unterschiedlich fehlschlagen duerfen. Als `&&`-Kette in der Crontab haengte
# der Loeschteil am Rotationsteil — und der Rotationsteil scheitert im
# Normalbetrieb regelmaessig, weil Caddy `access.log` erst beim ERSTEN Request
# anlegt. Eine Nacht ohne Anfrage liess damit auch die Loeschung ausfallen,
# geraeuschlos und jede Nacht erneut.
#
# Reihenfolge und Fehlerregel:
#   1. Aktive Datei rotieren — NUR wenn sie existiert. Fehlt sie, ist das kein
#      Fehler, sondern der normale Zustand eines Tages ohne Anfragen.
#   2. Generationen aelter als ${ACCESS_LOG_RETENTION_DAYS} Tage loeschen.
#      Laeuft IMMER, unabhaengig von Schritt 1, und deckt BEIDE Namensklassen:
#      `access.log.<datum>.gz` (dieses Skript) und `access-<ts>.log.gz`
#      (Caddys eigene groessenbedingte Rotation). Die beiden Mechanismen
#      erfassen je nur ihre eigene Klasse; deshalb raeumt dieses Skript beide.
#   3. Caddy neu starten — nur wenn rotiert wurde. Ohne Neustart schreibt der
#      Prozess in den umbenannten Inode weiter und es entsteht keine neue
#      `access.log`. Signale und `caddy reload` leisten das nicht (gemessen,
#      s. RUNBOOK §Access-Logs).
#
# Ein Fehlschlag ist nicht still: Exit != 0, und bei gesetztem
# ACCESS_LOG_HEARTBEAT_URL bleibt der Ping aus (gleiche Mechanik wie beim
# Backup, s. backup.sh / RUNBOOK §Alarmweg). Der Zeitstempel des letzten
# ERFOLGREICHEN Laufs landet in ${ACCESS_LOG_STAMP_FILE} — daran erkennt der
# Quartals-Check einen Cron, der nie durchgelaufen ist. Ein leeres
# Log-Verzeichnis allein sieht wie Erfolg aus.
#
# Env (alle mit Default, damit die Crontab-Zeile ein Wort bleibt):
#   ACCESS_LOG_DIR             Log-Verzeichnis IM Container (Default /var/log/caddy)
#   ACCESS_LOG_RETENTION_DAYS  Zugesagte Frist in Tagen (Default 14; Korridor 7-30
#                              aus docs/compliance/data-retention-and-erasure.md §5).
#                              Die Loeschschwelle liegt bewusst ZWEI Tage darunter,
#                              s. u. „Warum die Schwelle nicht die Frist ist".
#   ACCESS_LOG_SH              Kommando, das eine Shell IM Caddy-Container
#                              oeffnet und das Skript von stdin liest
#   ACCESS_LOG_RESTART_CMD     Kommando, das den Caddy-Container neu startet
#   ACCESS_LOG_STAMP_FILE      Zeitstempel des letzten Erfolgs (Host)
#   ACCESS_LOG_HEARTBEAT_URL   optionaler Dead-Man's-Switch, leer = aus
#   ACCESS_LOG_HEARTBEAT_TIMEOUT  Sekunden (Default 10)
#
# Die beiden Kommando-Variablen sind der Grund, warum dieser Ablauf ueberhaupt
# pruefbar ist: der Test setzt ACCESS_LOG_SH=sh und laesst die Dateioperationen
# in einem echten Temporaerverzeichnis laufen.

set -uo pipefail

COMPOSE_FILE="${ACCESS_LOG_COMPOSE_FILE:-deploy/hetzner/who2be/docker-compose.yml}"
LOG_DIR="${ACCESS_LOG_DIR:-/var/log/caddy}"
RETENTION_DAYS="${ACCESS_LOG_RETENTION_DAYS:-14}"
CONTAINER_SH="${ACCESS_LOG_SH:-docker compose -f ${COMPOSE_FILE} exec -T caddy sh}"
RESTART_CMD="${ACCESS_LOG_RESTART_CMD:-docker compose -f ${COMPOSE_FILE} restart caddy}"
STAMP_FILE="${ACCESS_LOG_STAMP_FILE:-/var/log/who2be-logrotate.stamp}"
HEARTBEAT_URL="${ACCESS_LOG_HEARTBEAT_URL:-}"
HEARTBEAT_TIMEOUT="${ACCESS_LOG_HEARTBEAT_TIMEOUT:-10}"

# --- Warum die Schwelle nicht die Frist ist ------------------------------
# Eine rotationsbasierte Loeschung haelt die Frist nur als OBERGRENZE, wenn sie
# drei Verzoegerungen mitrechnet, die sich addieren:
#   * Rotationsfenster: ein Eintrag von 04:31 wird erst beim naechsten Lauf
#     (24 h spaeter) in eine Generation verschoben. Die mtime der Generation ist
#     der Rotations-, nicht der Schreibzeitpunkt (busybox-`gzip` erhaelt die
#     mtime nicht — gemessen), sie liegt also bis zu 24 h nach dem Eintrag.
#   * `-mtime +N` ist wahr ab einem Alter von N+1 vollen Tagen (Ganzzahl-
#     Trunkierung), nicht ab N — ein Tag mehr.
#   * Der Loeschlauf ist taeglich, trifft also den Moment nicht genau.
# Mit 14 als Schwelle waere ein Eintrag im schlechtesten Fall 16 Tage alt.
# Mit Frist minus 2 gilt: Generation wird bei einem Alter von
# (Frist-1) Tagen geloescht, ihr aeltester Eintrag ist dann hoechstens
# (Frist-1) + 1 = Frist Tage alt. 14 Tage sind damit die Obergrenze, nicht der
# Mittelwert. `test_compose_hardening.py` rechnet diese Kette nach.
DELETE_THRESHOLD_DAYS=$((RETENTION_DAYS - 2))
if ((DELETE_THRESHOLD_DAYS < 1)); then
    printf '[access-log-rotate] FEHLER: ACCESS_LOG_RETENTION_DAYS=%s ist zu klein (mindestens 3)\n' \
        "${RETENTION_DAYS}" >&2
    exit 1
fi

log() { printf '[access-log-rotate] %s\n' "$*"; }

# Der Teil, der im Container laeuft: POSIX-sh/busybox, kein bash.
# `printf` statt Heredoc, damit das Skript ueber stdin in `exec -T` passt.
inner_script() {
    cat <<INNER
set -u
rc=0
dir='${LOG_DIR}'
days='${DELETE_THRESHOLD_DAYS}'

if [ -f "\$dir/access.log" ]; then
    gen="\$dir/access.log.\$(date -u +%Y%m%d%H%M%S)"
    if mv "\$dir/access.log" "\$gen"; then
        # Die mtime der Generation ist die der KOMPRIMIERUNG, nicht die des
        # letzten Schreibzugriffs (busybox-gzip erhaelt sie nicht — gemessen).
        # Das ist hier der konservative Bezugspunkt: die Frist zaehlt ab dem
        # Rotationszeitpunkt, also ab dem SPAETESTEN moeglichen Eintrag.
        gzip -f "\$gen" || rc=1
        echo 'who2be-rotated'
    else
        echo 'who2be-rotate-failed' >&2
        rc=1
    fi
else
    # Kein Fehler: Caddy legt die Datei erst beim ersten Request an.
    echo 'who2be-no-active-file'
fi

# Laeuft in JEDEM Fall — auch wenn oben nichts zu rotieren war. Beide
# Namensklassen, weil die Generationen dieses Skripts und die von Caddy
# selbst erzeugten unterschiedlich heissen.
find "\$dir" -maxdepth 1 -type f -name 'access.log.*' -mtime "+\$days" -delete || rc=1
find "\$dir" -maxdepth 1 -type f -name 'access-*.log*' -mtime "+\$days" -delete || rc=1

exit \$rc
INNER
}

# shellcheck disable=SC2086  # ACCESS_LOG_SH ist bewusst ein Kommando mit Argumenten.
output="$(inner_script | ${CONTAINER_SH} 2>&1)"
status=$?
[[ -n "${output}" ]] && log "${output//$'\n'/ | }"

if ((status != 0)); then
    log "FEHLER: Rotation/Loeschung im Container fehlgeschlagen (exit ${status})"
    exit 1
fi

if [[ "${output}" == *who2be-rotated* ]]; then
    # shellcheck disable=SC2086  # dito.
    if ! ${RESTART_CMD}; then
        log "FEHLER: Caddy-Neustart fehlgeschlagen — es entsteht keine neue access.log,"
        log "        bis der Dienst wieder oeffnet. Sofort nachsehen."
        exit 1
    fi
    log "rotiert und Caddy neu gestartet"
else
    log "keine aktive Datei — nichts zu rotieren, Loeschung lief trotzdem"
fi

# Erfolgsstempel. Ohne ihn sieht ein Cron, der nie lief, genauso aus wie einer,
# der nichts zu tun hatte (leeres Verzeichnis).
if ! date -u +%Y-%m-%dT%H:%M:%SZ >"${STAMP_FILE}"; then
    log "FEHLER: Erfolgsstempel ${STAMP_FILE} nicht schreibbar"
    exit 1
fi

if [[ -n "${HEARTBEAT_URL}" ]]; then
    if command -v curl >/dev/null 2>&1; then
        curl --fail --silent --show-error --max-time "${HEARTBEAT_TIMEOUT}" \
            --retry 3 -o /dev/null "${HEARTBEAT_URL}" || {
            log "FEHLER: Heartbeat-Ping fehlgeschlagen — Rotation lief, der Alarmweg ist stumm"
            exit 1
        }
    elif command -v wget >/dev/null 2>&1; then
        wget --quiet --timeout="${HEARTBEAT_TIMEOUT}" --tries=3 \
            -O /dev/null "${HEARTBEAT_URL}" || {
            log "FEHLER: Heartbeat-Ping fehlgeschlagen — Rotation lief, der Alarmweg ist stumm"
            exit 1
        }
    else
        log "FEHLER: ACCESS_LOG_HEARTBEAT_URL gesetzt, aber weder curl noch wget vorhanden"
        exit 1
    fi
fi

exit 0
