#!/bin/sh
# Setzt das Passwort der nicht-privilegierten Laufzeit-Rolle `who2be_app`.
#
# Die Rolle selbst legt Migration 0036 an (LOGIN, NOSUPERUSER, NOBYPASSRLS);
# das Passwort gehoert NICHT ins Repo, sondern wird out-of-band gesetzt — in
# Prod aus dem Secret-Manager (Plan §3.3), lokal aus `.env` (APP_DB_PASSWORD).
# Dieser Init-Schritt im cloud-local-Overlay schliesst genau diese Luecke, damit
# die API als `who2be_app` mit aktiver RLS verbinden kann (Plan §3.1, CL1).
#
# Laeuft als Compose-One-Shot NACH `migrate` (Rolle existiert dann garantiert)
# und VOR `api`. Idempotent: ALTER ROLE ... PASSWORD ueberschreibt schadlos.
set -eu

: "${APP_DB_PASSWORD:?APP_DB_PASSWORD muss gesetzt sein (siehe .env / .env.example)}"

# psql liest Host/User/DB aus den PG*-Env-Vars (siehe docker-compose.cloud.yml).
# ON_ERROR_STOP bricht bei fehlender Rolle hart ab — dann lief 0036 nicht.
psql -v ON_ERROR_STOP=1 -c "ALTER ROLE who2be_app WITH PASSWORD '${APP_DB_PASSWORD}';"

echo "who2be_app: Passwort gesetzt — API kann als RLS-Rolle verbinden."
