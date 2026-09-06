#!/bin/sh
# Schreibt die Runtime-Konfiguration der Web-App (`/config.js`) aus Env.
#
# Laeuft als Teil der nginx-Entrypoint-Kette (/docker-entrypoint.d) bei jedem
# Container-Start — dadurch ist EIN Image fuer localhost, LAN-IP und Domain
# gueltig, ohne Rebuild (frueher waren die VITE_*-Werte Compile-Time gebacken).
#
# Leere Werte werden bewusst als leere Strings geschrieben: src/config.ts
# behandelt "" als „nicht gesetzt" und faellt dann auf den Origin zurueck, von
# dem die App geladen wurde (der nginx unten proxied /v1/ und /auth/v1/).
set -eu

TARGET="${WHO2BE_RUNTIME_CONFIG_PATH:-/usr/share/nginx/html/config.js}"

# Anfuehrungszeichen und Backslashes entfernen — die Werte landen unescaped in
# einem JS-String-Literal; ein Wert mit `"` wuerde die Datei sonst zerlegen.
sanitize() {
  printf '%s' "${1:-}" | tr -d '"\\'
}

# "Wir arbeiten noch"-Modus (Issue #429). Nur "open"/"coming_soon" sind
# gueltig — src/config.ts validiert das ohnehin nochmal fail-open (unbekannte
# Werte -> "open" + console.warn), hier landet der Rohwert unveraendert.
LAUNCH_MODE="${WHO2BE_LAUNCH_MODE:-open}"

# signupDisabled ist wahr, wenn ENTWEDER der neue Launch-Modus ODER der
# Altschalter (WHO2BE_SIGNUP_DISABLED) es verlangt (Weiche 2a) — Compose kann
# keine Variable aus einer anderen berechnen, das holt das hier nach.
if [ "${LAUNCH_MODE}" = "coming_soon" ] || [ "${WHO2BE_SIGNUP_DISABLED:-false}" = "true" ]; then
  SIGNUP_DISABLED_JS=true
else
  SIGNUP_DISABLED_JS=false
fi

# Absolute Obergrenze fuer "Angemeldet bleiben" (Issue #430, ADR-0052). Landet
# unquoted als JS-Zahl-Literal — deshalb hier nur auf "ist eine nicht-leere
# Ziffernfolge" pruefen (sonst zerlegt ein kaputter Wert die generierte
# config.js syntaktisch). Die semantische Grenze (1-24) prueft `src/config.ts`
# ohnehin nochmal fail-closed (Default 12 + `console.warn`) — ein hier
# durchgelassener, aber ausserhalb des Bereichs liegender Wert (z. B. "0" oder
# "999") faellt dort auf den Default zurueck.
SESSION_MAX_AGE_HOURS="${WHO2BE_SESSION_MAX_AGE_HOURS:-12}"
case "${SESSION_MAX_AGE_HOURS}" in
  ''|*[!0-9]*) SESSION_MAX_AGE_HOURS=12 ;;
esac

cat > "${TARGET}" <<EOF
// Generiert beim Container-Start (docker/40-who2be-runtime-config.sh).
// Nicht editieren — Aenderungen ueberleben den naechsten Start nicht.
window.__WHO2BE_CONFIG__ = {
  apiBaseUrl: "$(sanitize "${WHO2BE_API_BASE_URL:-}")",
  mcpUrl: "$(sanitize "${WHO2BE_MCP_URL:-}")",
  supabaseUrl: "$(sanitize "${WHO2BE_SUPABASE_URL:-}")",
  supabaseAnonKey: "$(sanitize "${WHO2BE_SUPABASE_ANON_KEY:-}")",
  signupDisabled: ${SIGNUP_DISABLED_JS},
  launchMode: "$(sanitize "${LAUNCH_MODE}")",
  launchContact: "$(sanitize "${WHO2BE_LAUNCH_CONTACT:-}")",
  sessionMaxAgeHours: ${SESSION_MAX_AGE_HOURS},
}
EOF

echo "[who2be] runtime config written to ${TARGET}"
