# Build-Context = Repo-Root (Konsistenz mit apps/api/Dockerfile).
# Aufruf via docker compose:
#   build:
#     context: .
#     dockerfile: apps/web/Dockerfile
# Multi-stage: Vite-Build mit npm, dann statisch via nginx:alpine.
# Die VITE_*-Args sind Compile-Time-Substitution und inzwischen optional:
# ohne sie liest die App ihre URLs zur Laufzeit aus /config.js bzw. faellt auf
# Same-Origin zurueck (src/config.ts, nginx.conf).
FROM node:26-slim AS builder

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json apps/web/.npmrc ./
RUN npm ci

COPY apps/web/ ./

# Die VITE_*-Args sind seit der Runtime-Config OPTIONAL (src/config.ts):
# ungesetzt faellt die App auf `/config.js` (vom Entrypoint aus Env
# geschrieben) bzw. auf den Origin zurueck, von dem sie geladen wurde. Gesetzt
# werden sie nur noch, wenn eine Umgebung die Werte bewusst einbacken will —
# das macht das Image dann aber unbrauchbar fuer jeden anderen Host.
ARG VITE_API_BASE_URL=
ARG VITE_SUPABASE_URL=
ARG VITE_SUPABASE_ANON_KEY=
# Optional: expliziter MCP-Endpoint fuer die Copy-Config. Leer → aus
# VITE_API_BASE_URL abgeleitet (api.→mcp.). Lokal sinnvoll der direkte
# mcp-http-Port (mcp-remote akzeptiert http nur fuer 127.0.0.1/localhost).
ARG VITE_MCP_URL=
# Edition-Flag (ADR-0029): Default `onprem` → Billing-UI wird aus dem Bundle
# tree-shaked. Cloud-Build setzt VITE_WHO2BE_EDITION=cloud.
ARG VITE_WHO2BE_EDITION=onprem
# Signup-Flag: `true` versteckt die Self-Service-Registrierung (Login-Link +
# /signup-Route). Gemeinsam mit dem Backend-GOTRUE_DISABLE_SIGNUP setzen — GoTrue
# ist die echte Durchsetzung, dieses Flag entfernt nur die tote UI.
ARG VITE_WHO2BE_SIGNUP_DISABLED=false
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY \
    VITE_MCP_URL=$VITE_MCP_URL \
    VITE_WHO2BE_EDITION=$VITE_WHO2BE_EDITION \
    VITE_WHO2BE_SIGNUP_DISABLED=$VITE_WHO2BE_SIGNUP_DISABLED

RUN npm run build

# Source-Maps (Stabilitaet A3): `vite build` erzeugt sie versteckt
# (`sourcemap: 'hidden'`, kein Verweis im JS). Mit Token werden sie an den
# Fehler-Tracker (GlitchTip/Sentry, sentry-cli-kompatibel) hochgeladen; die
# Zuordnung laeuft ueber Debug-IDs, die `sourcemaps inject` vorher in JS und
# Map schreibt. OHNE Token (Normalfall, Auto-Deploy) passiert nichts davon —
# der Build laeuft wie bisher, nur ohne Upload. Der Token kommt als
# Build-Secret, nie als ARG (ARGs landen in der Image-Historie):
#   docker build --secret id=sentry_auth_token,env=SENTRY_AUTH_TOKEN \
#     --build-arg SENTRY_URL=https://<DOMAIN>/ --build-arg SENTRY_ORG=<org> \
#     --build-arg SENTRY_PROJECT=<projekt> -f apps/web/Dockerfile .
# Danach werden alle .map-Dateien geloescht, mit und ohne Upload.
ARG SENTRY_URL=
ARG SENTRY_ORG=
ARG SENTRY_PROJECT=
ARG SENTRY_RELEASE=
ARG SENTRY_CLI_VERSION=3.8.1
RUN --mount=type=secret,id=sentry_auth_token,required=false \
    set -eu; \
    if [ -s /run/secrets/sentry_auth_token ]; then \
      echo "[who2be] Source-Maps: Upload zum Fehler-Tracker"; \
      export SENTRY_AUTH_TOKEN="$(cat /run/secrets/sentry_auth_token)"; \
      export SENTRY_URL SENTRY_ORG SENTRY_PROJECT; \
      { npx --yes "@sentry/cli@${SENTRY_CLI_VERSION}" sourcemaps inject dist \
        && npx --yes "@sentry/cli@${SENTRY_CLI_VERSION}" sourcemaps upload \
          ${SENTRY_RELEASE:+--release "$SENTRY_RELEASE"} dist; } \
        || echo "[who2be] WARNUNG: Source-Map-Upload fehlgeschlagen, Build laeuft weiter"; \
    else \
      echo "[who2be] Source-Maps: kein Token, kein Upload"; \
    fi; \
    find dist -type f -name '*.map' -delete

FROM nginx:1.31-alpine AS runtime

RUN apk add --no-cache curl

COPY --from=builder /app/dist /usr/share/nginx/html
# Keine Source-Map im ausgelieferten Image (Stabilitaet A3). Schlaegt nur fehl,
# wenn tatsaechlich eine .map-Datei uebrig ist.
RUN leftover="$(find /usr/share/nginx/html -type f -name '*.map')"; \
    if [ -n "$leftover" ]; then \
      echo "[who2be] FEHLER: Source-Maps im Image:"; echo "$leftover"; exit 1; \
    fi
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
# Schreibt /etc/nginx/resolver.conf bei jedem Container-Start aus der DNS-Adresse
# des Containers (Docker: 127.0.0.11, rootless Podman: eine andere) — nginx.conf
# includiert die Datei statt die Adresse festzuschreiben.
COPY docker/10-who2be-nginx-resolver.sh /docker-entrypoint.d/10-who2be-nginx-resolver.sh
RUN chmod +x /docker-entrypoint.d/10-who2be-nginx-resolver.sh
# Schreibt /config.js bei jedem Container-Start aus Env (nginx fuehrt alles in
# /docker-entrypoint.d aus, bevor es startet).
COPY apps/web/docker/40-who2be-runtime-config.sh /docker-entrypoint.d/40-who2be-runtime-config.sh
RUN chmod +x /docker-entrypoint.d/40-who2be-runtime-config.sh

EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost/healthz || exit 1
