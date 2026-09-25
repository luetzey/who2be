#!/bin/sh
# Schreibt `/etc/nginx/resolver.conf` beim Container-Start aus der DNS-Adresse,
# die der Container tatsaechlich hat.
#
# Warum: `apps/web/nginx.conf` und `supabase/gateway.conf` nutzen
# Variablen-`proxy_pass` (`set $upstream "http://auth:9999"; proxy_pass
# $upstream;`), damit nginx den Upstream-Namen pro Request neu aufloest statt
# die IP einmal beim Worker-Start zu cachen und nach einem `compose up`-Recreate
# am alten Wert festzuhaengen (502). Diese Konstruktion BRAUCHT ein
# `resolver`-Directive, und dessen Adresse stand bislang fest im Klartext:
# `127.0.0.11` — Dockers eingebettetes DNS.
#
# Unter rootless Podman ist das eine andere Adresse (z. B. `10.89.1.1`, sie
# haengt am Netz und ist nicht vorhersagbar). Mit dem festen Docker-Wert lief
# dort JEDER Signup in ein HTTP 502, im Browser ohne verwertbare Meldung — das
# Formular scheiterte stumm. Deshalb fragt der Container jetzt sich selbst.
#
# Reihenfolge:
#   1. `$WHO2BE_DNS_RESOLVER` — expliziter Override (Notausgang fuer exotische
#      Netze, etwa ein externes DNS vor den Container-Namen).
#   2. erster `nameserver` aus `/etc/resolv.conf` — der Normalfall. Unter Docker
#      steht dort `127.0.0.11`, das Ergebnis ist also bitgleich zu vorher.
#   3. `127.0.0.11` als letzter Fallback, falls `/etc/resolv.conf` fehlt oder
#      keinen `nameserver` enthaelt.
#
# Bewusst nur der ERSTE Nameserver: nginx verteilt Anfragen ueber alle
# genannten Resolver. Stuende ein oeffentliches DNS (8.8.8.8 o. ae.) mit in der
# Liste, wuerden Container-Namen sporadisch mit NXDOMAIN beantwortet — ein
# Fehler, der nur unter Last und nur manchmal auftritt.
#
# Laeuft als Teil der nginx-Entrypoint-Kette (`/docker-entrypoint.d`, alle
# Skripte dort werden vor dem nginx-Start ausgefuehrt). Praefix `10-`, also vor
# `40-who2be-runtime-config.sh`.
set -eu

TARGET="${WHO2BE_NGINX_RESOLVER_CONF:-/etc/nginx/resolver.conf}"
FALLBACK="127.0.0.11"

resolver="${WHO2BE_DNS_RESOLVER:-}"
source="env WHO2BE_DNS_RESOLVER"

if [ -z "$resolver" ] && [ -r /etc/resolv.conf ]; then
    # Erste `nameserver`-Zeile, zweites Feld. `awk` statt `grep|head|cut`:
    # ein Prozess, und `exit` bricht nach dem ersten Treffer ab.
    resolver="$(awk '$1 == "nameserver" { print $2; exit }' /etc/resolv.conf)"
    source="/etc/resolv.conf"
fi

if [ -z "$resolver" ]; then
    resolver="$FALLBACK"
    source="fallback"
fi

# `ipv6=off`: die Compose-Bridge (Docker) wie das rootless Podman-Netz fahren
# hier nur IPv4; ohne das Flag fragt nginx zusaetzlich AAAA ab und wartet auf
# ein NXDOMAIN, das pro Request Latenz kostet.
# `valid=10s`: kurzer TTL, damit ein Container-Recreate selbst abgefangen wird.
printf 'resolver %s valid=10s ipv6=off;\n' "$resolver" > "$TARGET"

echo "who2be: nginx resolver = $resolver (aus: $source) -> $TARGET"
