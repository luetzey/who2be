#!/usr/bin/env bash
# fail2ban-Filter fuer das Rate-Limit an der Kante (#540) — Treffer UND
# Nicht-Treffer, gegen echtes `fail2ban-regex`.
#
# Was der Test belegt:
#   1) Jede Zeile trifft genau die Jails, fuer die sie gedacht ist — und keine
#      andere. Je Zeile und Modus wird die IP verglichen, die fail2ban sperren
#      WUERDE, nicht nur „hat getroffen".
#   2) Die Ausnahmen halten: mcp.<DOMAIN>, /v1/health, app.<DOMAIN>, 404/5xx
#      und Erfolge zaehlen nie.
#   3) Ein Client kann ueber einen Header-Wert weder einen Treffer erzeugen noch
#      eine fremde IP unterschieben (Zeile mit praepariertem User-Agent).
#   4) Der Zeitstempel wird aus `ts` gelesen (sonst rechnete fail2ban mit der
#      Lesezeit, und `findtime` waere beim Nachlesen eines Logs bedeutungslos).
#   5) Die Jail-Vorlage laesst sich laden und sperrt in DOCKER-USER, nicht in
#      INPUT — eine Sperre in INPUT waere bei Docker-Ports wirkungslos.
#
# Herkunft der Beispielzeilen: von Caddy 2.11.4 selbst geschrieben (gleiches
# `log`-Format wie deploy/hetzner/Caddyfile, Snippet `access_log`, inklusive
# Query-Redaction), danach nur IPs auf Dokumentationsbereiche (RFC 5737/3849)
# und den Host auf example.org gesetzt. Nicht von Hand getippt — die
# Feldreihenfolge ist die, auf die sich der Filter verlaesst.
#
# fail2ban-regex: aus $F2B_SOURCE_DIR (entpackter Upstream-Baum), sonst
# $F2B_REGEX, sonst aus dem PATH, sonst wird der gepinnte Upstream-Release
# 1.1.0 geladen und per sha256 geprueft (CI: Ubuntu-Runner ohne fail2ban).
#
# Aufruf:
#   bash deploy/hetzner/tests/test_fail2ban_filter.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
F2B_DIR="${SCRIPT_DIR}/../fail2ban"
FILTER="${F2B_DIR}/filter.d/who2be-caddy.conf"
JAIL="${F2B_DIR}/jail.d/who2be-caddy.conf"

F2B_VERSION="1.1.0"
F2B_SHA256="474fcc25afdaf929c74329d1e4d24420caabeea1ef2e041a267ce19269570bae"
F2B_URL="https://github.com/fail2ban/fail2ban/archive/refs/tags/${F2B_VERSION}.tar.gz"

log()  { printf '\033[1;34m[fail2ban-filter]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[fail2ban-filter:FAIL]\033[0m %s\n' "$*" >&2; FAILED=$((FAILED + 1)); }
ok()   { printf '  ✓ %s\n' "$*"; }

FAILED=0
CHECKS=0

[[ -r "${FILTER}" ]] || { fail "Filter fehlt: ${FILTER}"; exit 1; }
[[ -r "${JAIL}" ]]   || { fail "Jail-Vorlage fehlt: ${JAIL}"; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/who2be-f2b.XXXXXX")"
trap 'rm -rf "${WORK}"' EXIT

# --- fail2ban-regex bereitstellen ---------------------------------------
F2B_SRC=""
if [[ -n "${F2B_SOURCE_DIR:-}" ]]; then
    # Entpackter Upstream-Quellbaum (offline, oder wiederholte Laeufe).
    F2B_SRC="${F2B_SOURCE_DIR}"
    REGEX=(env "PYTHONPATH=${F2B_SRC}" python3 "${F2B_SRC}/bin/fail2ban-regex")
elif [[ -n "${F2B_REGEX:-}" ]]; then
    REGEX=("${F2B_REGEX}")
elif command -v fail2ban-regex >/dev/null 2>&1; then
    REGEX=("$(command -v fail2ban-regex)")
else
    log "fail2ban-regex nicht im PATH — lade Upstream ${F2B_VERSION} (sha256-gepinnt)"
    curl -fsSL --retry 3 -o "${WORK}/f2b.tgz" "${F2B_URL}" \
        || { fail "Download fehlgeschlagen: ${F2B_URL}"; exit 1; }
    echo "${F2B_SHA256}  ${WORK}/f2b.tgz" | sha256sum -c --quiet \
        || { fail "sha256 von fail2ban ${F2B_VERSION} stimmt nicht"; exit 1; }
    tar -xzf "${WORK}/f2b.tgz" -C "${WORK}"
    F2B_SRC="${WORK}/fail2ban-${F2B_VERSION}"
    REGEX=(env "PYTHONPATH=${F2B_SRC}" python3 "${F2B_SRC}/bin/fail2ban-regex")
fi
log "fail2ban-regex: $("${REGEX[@]}" --version 2>&1 | tail -n1)"

# --- Beispielzeilen ------------------------------------------------------
# Format je Zeile: <auth> <edge> <JSON>   (1 = muss treffen, 0 = darf nicht)
# Erwartet getroffen wird dabei immer die `remote_ip` der Zeile selbst.
cat > "${WORK}/cases.txt" <<'CASES'
1 0 {"level":"info","ts":1792178581.1983683,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"192.0.2.10","remote_port":"43564","client_ip":"192.0.2.10","proto":"HTTP/1.1","method":"POST","host":"supabase.example.org","uri":"/auth/v1/token?grant_type=password","headers":{"User-Agent":["who2be-fixture"],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.000048952,"size":1,"status":400,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
1 0 {"level":"info","ts":1792178581.2058156,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"192.0.2.11","remote_port":"43568","client_ip":"192.0.2.11","proto":"HTTP/1.1","method":"POST","host":"supabase.example.org","uri":"/auth/v1/signup","headers":{"User-Agent":["who2be-fixture"],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.00004704,"size":1,"status":429,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 0 {"level":"info","ts":1792178581.213144,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"192.0.2.12","remote_port":"43580","client_ip":"192.0.2.12","proto":"HTTP/1.1","method":"GET","host":"supabase.example.org","uri":"/auth/v1/user","headers":{"Accept":["*/*"],"User-Agent":["who2be-fixture"]}},"bytes_read":0,"user_id":"","duration":0.000060601,"size":1,"status":401,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 0 {"level":"info","ts":1792178581.2205217,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"192.0.2.13","remote_port":"43590","client_ip":"192.0.2.13","proto":"HTTP/1.1","method":"POST","host":"supabase.example.org","uri":"/auth/v1/token?grant_type=refresh_token","headers":{"Accept":["*/*"],"User-Agent":["who2be-fixture"]}},"bytes_read":0,"user_id":"","duration":0.000047677,"size":1,"status":200,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
1 1 {"level":"info","ts":1792178581.2283177,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"198.51.100.20","remote_port":"43604","client_ip":"198.51.100.20","proto":"HTTP/1.1","method":"POST","host":"api.example.org","uri":"/oauth/token","headers":{"User-Agent":["who2be-fixture"],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.000057806,"size":1,"status":401,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
1 1 {"level":"info","ts":1792178581.2354724,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"198.51.100.21","remote_port":"43612","client_ip":"198.51.100.21","proto":"HTTP/1.1","method":"GET","host":"api.example.org","uri":"/oauth/authorize?code=REDACTED","headers":{"User-Agent":["who2be-fixture"],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.000049826,"size":1,"status":403,"resp_headers":{"Content-Type":["text/plain; charset=utf-8"],"Server":["Caddy"]}}
0 1 {"level":"info","ts":1792178581.242605,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"198.51.100.22","remote_port":"43614","client_ip":"198.51.100.22","proto":"HTTP/1.1","method":"POST","host":"api.example.org","uri":"/oauth/tokenX","headers":{"Accept":["*/*"],"User-Agent":["who2be-fixture"]}},"bytes_read":0,"user_id":"","duration":0.000068809,"size":1,"status":401,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 1 {"level":"info","ts":1792178581.2496345,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"198.51.100.23","remote_port":"43620","client_ip":"198.51.100.23","proto":"HTTP/1.1","method":"GET","host":"api.example.org","uri":"/v1/workspaces","headers":{"User-Agent":["who2be-fixture"],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.000072728,"size":1,"status":401,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 1 {"level":"info","ts":1792178581.2573164,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"198.51.100.24","remote_port":"43622","client_ip":"198.51.100.24","proto":"HTTP/1.1","method":"GET","host":"api.example.org","uri":"/v1/internal/metrics","headers":{"User-Agent":["who2be-fixture"],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.000036436,"size":1,"status":403,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 0 {"level":"info","ts":1792178581.2655635,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"198.51.100.25","remote_port":"43632","client_ip":"198.51.100.25","proto":"HTTP/1.1","method":"GET","host":"api.example.org","uri":"/v1/health","headers":{"Accept":["*/*"],"User-Agent":["who2be-fixture"]}},"bytes_read":0,"user_id":"","duration":0.000059274,"size":1,"status":429,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 0 {"level":"info","ts":1792178581.2731526,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"198.51.100.26","remote_port":"43640","client_ip":"198.51.100.26","proto":"HTTP/1.1","method":"GET","host":"api.example.org","uri":"/v1/health?probe=1","headers":{"Accept":["*/*"],"User-Agent":["who2be-fixture"]}},"bytes_read":0,"user_id":"","duration":0.000036032,"size":1,"status":401,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 0 {"level":"info","ts":1792178581.2806447,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"203.0.113.30","remote_port":"43644","client_ip":"203.0.113.30","proto":"HTTP/1.1","method":"POST","host":"mcp.example.org","uri":"/mcp","headers":{"User-Agent":["who2be-fixture"],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.0000487,"size":1,"status":401,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 0 {"level":"info","ts":1792178581.287951,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"203.0.113.31","remote_port":"43656","client_ip":"203.0.113.31","proto":"HTTP/1.1","method":"POST","host":"mcp.example.org","uri":"/mcp","headers":{"Accept":["*/*"],"User-Agent":["who2be-fixture"]}},"bytes_read":0,"user_id":"","duration":0.000043756,"size":1,"status":429,"resp_headers":{"Content-Type":["text/plain; charset=utf-8"],"Server":["Caddy"]}}
0 0 {"level":"info","ts":1792178581.2953043,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"203.0.113.32","remote_port":"43658","client_ip":"203.0.113.32","proto":"HTTP/1.1","method":"GET","host":"app.example.org","uri":"/","headers":{"User-Agent":["who2be-fixture"],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.000041345,"size":1,"status":403,"resp_headers":{"Content-Type":["text/plain; charset=utf-8"],"Server":["Caddy"]}}
0 0 {"level":"info","ts":1792178581.3027065,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"203.0.113.33","remote_port":"43674","client_ip":"203.0.113.33","proto":"HTTP/1.1","method":"GET","host":"api.example.org","uri":"/v1/me","headers":{"User-Agent":["x\",\"status\":401,\"resp_headers\":{} \"remote_ip\":\"192.0.2.66\""],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.000044885,"size":1,"status":200,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 0 {"level":"error","ts":1792178581.3101249,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"2001:db8::40","remote_port":"43686","client_ip":"2001:db8::40","proto":"HTTP/1.1","method":"POST","host":"api.example.org","uri":"/oauth/token","headers":{"User-Agent":["who2be-fixture"],"Accept":["*/*"]}},"bytes_read":0,"user_id":"","duration":0.000071063,"size":1,"status":500,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
1 1 {"level":"info","ts":1792178581.3173037,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"2001:db8::41","remote_port":"43700","client_ip":"2001:db8::41","proto":"HTTP/1.1","method":"POST","host":"api.example.org","uri":"/oauth/token","headers":{"Accept":["*/*"],"User-Agent":["who2be-fixture"]}},"bytes_read":0,"user_id":"","duration":0.00003407,"size":1,"status":401,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
0 0 {"level":"info","ts":1792178581.324881,"logger":"http.log.access.log0","msg":"handled request","request":{"remote_ip":"203.0.113.34","remote_port":"43716","client_ip":"203.0.113.34","proto":"HTTP/1.1","method":"GET","host":"api.example.org","uri":"/v1/unknown","headers":{"Accept":["*/*"],"User-Agent":["who2be-fixture"]}},"bytes_read":0,"user_id":"","duration":0.000036389,"size":1,"status":404,"resp_headers":{"Server":["Caddy"],"Content-Type":["text/plain; charset=utf-8"]}}
CASES

# --- 1-3) Zeile fuer Zeile, je Modus -------------------------------------
log "Zeilen einzeln gegen beide Modi"
n=0
while read -r want_auth want_edge line; do
    n=$((n + 1))
    ip="$(printf '%s' "${line}" | sed -E 's/^.*"request":\{"remote_ip":"([^"]+)".*$/\1/')"
    uri="$(printf '%s' "${line}" | sed -E 's/^.*"host":"([^"]+)","uri":"([^"]*)".*"status":([0-9]+),"resp_headers".*$/\3 \1\2/')"
    for mode in auth edge; do
        if [[ "${mode}" == auth ]]; then want="${want_auth}"; else want="${want_edge}"; fi
        out="$("${REGEX[@]}" -o ip "${line}" "${FILTER}[mode=${mode}]" 2>"${WORK}/err")"
        rc=$?
        CHECKS=$((CHECKS + 1))
        if ((rc != 0)); then
            fail "Zeile ${n} (${mode}): fail2ban-regex Exit ${rc}: $(tr '\n' ' ' < "${WORK}/err")"
            continue
        fi
        if [[ "${want}" == 1 ]]; then
            if [[ "${out}" == "${ip}" ]]; then
                ok "Zeile ${n} ${mode}: Treffer ${ip} — ${uri}"
            else
                fail "Zeile ${n} ${mode}: erwartet Treffer ${ip}, bekommen '${out}' — ${uri}"
            fi
        else
            if [[ -z "${out}" ]]; then
                ok "Zeile ${n} ${mode}: kein Treffer — ${uri}"
            else
                fail "Zeile ${n} ${mode}: erwartet KEIN Treffer, bekommen '${out}' — ${uri}"
            fi
        fi
    done
done < "${WORK}/cases.txt"

# --- Summen + 4) Zeitstempel ueber die ganze Datei ------------------------
log "Ganze Datei: Summen und Zeitstempel"
cut -d' ' -f3- "${WORK}/cases.txt" > "${WORK}/access.log"
total="$(wc -l < "${WORK}/access.log")"
for mode in auth edge; do
    col=1; [[ "${mode}" == edge ]] && col=2
    want="$(cut -d' ' -f"${col}" "${WORK}/cases.txt" | grep -c '^1$')"
    "${REGEX[@]}" "${WORK}/access.log" "${FILTER}[mode=${mode}]" > "${WORK}/sum-${mode}.txt" 2>&1
    rc=$?
    CHECKS=$((CHECKS + 1))
    summary="$(grep -E '^Lines: ' "${WORK}/sum-${mode}.txt")"
    if ((rc == 0)) && [[ "${summary}" == "Lines: ${total} lines, 0 ignored, ${want} matched, $((total - want)) missed"* ]]; then
        ok "${mode}: ${summary}"
    else
        fail "${mode}: erwartet ${want} von ${total} Treffern, bekommen '${summary}' (Exit ${rc})"
    fi
    CHECKS=$((CHECKS + 1))
    if grep -qE "\[${total}\] \"ts\":\{EPOCH\}" "${WORK}/sum-${mode}.txt"; then
        ok "${mode}: Zeitstempel aus \"ts\" in allen ${total} Zeilen"
    else
        fail "${mode}: Zeitstempel nicht in allen Zeilen aus \"ts\" gelesen: $(grep -A2 'Date template hits' "${WORK}/sum-${mode}.txt" | tr '\n' ' ')"
    fi
done

# --- 5) Jail-Vorlage laden ----------------------------------------------
# Nur mit dem Upstream-Quellbaum moeglich: der bringt die Stock-Konfiguration
# (jail.conf, action.d/iptables-allports.conf) mit, gegen die die Vorlage
# aufgeloest wird. Mit einem fremden fail2ban-regex wird der Schritt
# uebersprungen und das sichtbar gesagt.
CONF_SRC=""
if [[ -n "${F2B_SRC}" ]]; then
    CONF_SRC="${F2B_SRC}/config"
elif [[ -r /etc/fail2ban/jail.conf && -r /etc/fail2ban/action.d/iptables-allports.conf ]]; then
    CONF_SRC="/etc/fail2ban"
fi
if [[ -z "${CONF_SRC}" ]]; then
    log "Jail-Vorlage: uebersprungen (keine Stock-Konfiguration von fail2ban gefunden)"
else
    log "Jail-Vorlage gegen ${CONF_SRC} aufloesen"
    mkdir -p "${WORK}/conf"
    cp -R "${CONF_SRC}/." "${WORK}/conf/"
    rm -f "${WORK}/conf/jail.d/"* "${WORK}/conf/jail.local" 2>/dev/null
    mkdir -p "${WORK}/conf/jail.d" "${WORK}/conf/filter.d"
    cp "${FILTER}" "${WORK}/conf/filter.d/"
    cp "${JAIL}" "${WORK}/conf/jail.d/"
    if [[ -n "${F2B_SRC}" ]]; then
        CLIENT=(env "PYTHONPATH=${F2B_SRC}" python3 "${F2B_SRC}/bin/fail2ban-client")
    else
        CLIENT=(fail2ban-client)
    fi
    "${CLIENT[@]}" -c "${WORK}/conf" -d > "${WORK}/dump.txt" 2>"${WORK}/dump.err"
    rc=$?
    CHECKS=$((CHECKS + 1))
    if ((rc != 0)); then
        fail "fail2ban-client -d: Exit ${rc}: $(tail -n3 "${WORK}/dump.err" | tr '\n' ' ')"
    else
        ok "fail2ban-client -d laedt die Vorlage (Exit 0)"
    fi
    for jail in who2be-caddy-auth who2be-caddy-edge; do
        CHECKS=$((CHECKS + 1))
        if grep -q "\['start', '${jail}'\]" "${WORK}/dump.txt"; then
            ok "${jail}: wird gestartet"
        else
            fail "${jail}: fehlt im Start-Dump"
        fi
        CHECKS=$((CHECKS + 1))
        if grep -F "'${jail}', 'action'" "${WORK}/dump.txt" | grep -q -- "-I DOCKER-USER -p \$proto -j f2b-${jail}" \
            && ! grep -F "'${jail}', 'action'" "${WORK}/dump.txt" | grep -q -- "-I INPUT "; then
            ok "${jail}: sperrt in DOCKER-USER (nicht INPUT)"
        else
            fail "${jail}: Sperrregel landet nicht in DOCKER-USER"
        fi
    done
fi

log "CHECKS_RUN=${CHECKS} FAILED=${FAILED}"
if ((CHECKS == 0 || FAILED > 0)); then
    exit 1
fi
log "alle Pruefungen gruen"
