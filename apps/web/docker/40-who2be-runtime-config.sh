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
}
EOF

echo "[who2be] runtime config written to ${TARGET}"
