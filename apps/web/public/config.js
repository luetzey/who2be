// Runtime-Konfiguration der Web-App (siehe src/config.ts).
//
// Diese Datei ist der DEV-Platzhalter: leer, damit `npm run dev` kein 404 auf
// `/config.js` liefert und die Vite-Env-Variablen greifen. Im Container
// ueberschreibt sie der nginx-Entrypoint (`docker/40-who2be-runtime-config.sh`)
// mit den Werten aus `WHO2BE_API_BASE_URL` & Co. Nicht mit Werten einchecken.
window.__WHO2BE_CONFIG__ = {}
