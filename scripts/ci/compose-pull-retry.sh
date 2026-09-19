#!/usr/bin/env bash
# Zieht die NICHT selbstgebauten Compose-Images vorab, mit Wiederholung.
#
# Warum: die Basis-Images kommen von Docker Hub (postgres/pgvector, redis,
# nginx, mailpit, gotrue, seaweedfs). Docker Hub setzt die Verbindung von
# GitHub-Runnern aus regelmaessig zurueck ("read: connection reset by peer",
# am 2026-09-19 dreimal an einem Tag). `docker compose up` bricht dann nach
# zwei Sekunden ab, bevor ein einziger Test laeuft — ein roter Lauf, der
# nichts ueber den Code aussagt.
#
# `--ignore-buildable` laesst die Services aus, die ohnehin lokal gebaut
# werden; gezogen wird nur, was von aussen kommt. Danach findet `up` alles
# im lokalen Cache.
#
# Aufruf: compose-pull-retry.sh [-f datei ...]
set -uo pipefail

attempts=3
for attempt in $(seq 1 "$attempts"); do
    if docker compose "$@" pull --ignore-buildable --quiet; then
        echo "Basis-Images vorhanden (Versuch ${attempt}/${attempts})."
        exit 0
    fi
    echo "Image-Pull fehlgeschlagen (Versuch ${attempt}/${attempts})."
    [ "$attempt" -lt "$attempts" ] && sleep $((attempt * 15))
done

echo "::error title=Basis-Images nicht ziehbar::Nach ${attempts} Versuchen kein \
Erfolg. Das ist ein Registry-/Netzwerkproblem, KEIN Code-Fehler — siehe Log."
exit 1
