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

FROM nginx:1.31-alpine AS runtime

RUN apk add --no-cache curl

COPY --from=builder /app/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
# Schreibt /config.js bei jedem Container-Start aus Env (nginx fuehrt alles in
# /docker-entrypoint.d aus, bevor es startet).
COPY apps/web/docker/40-who2be-runtime-config.sh /docker-entrypoint.d/40-who2be-runtime-config.sh
RUN chmod +x /docker-entrypoint.d/40-who2be-runtime-config.sh

EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost/healthz || exit 1
