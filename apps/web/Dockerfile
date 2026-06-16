# Build-Context = Repo-Root (Konsistenz mit apps/api/Dockerfile).
# Aufruf via docker compose:
#   build:
#     context: .
#     dockerfile: apps/web/Dockerfile
# Multi-stage: Vite-Build mit npm, dann statisch via nginx:alpine.
# Die VITE_*-Args sind Compile-Time-Substitution (apps/web/src/config.ts:14-23
# wirft im PROD-Mode bei leer) und MUESSEN per --build-arg gesetzt sein.
FROM node:26-slim AS builder

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json apps/web/.npmrc ./
RUN npm ci

COPY apps/web/ ./

ARG VITE_API_BASE_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
# Optional: expliziter MCP-Endpoint fuer die Copy-Config. Leer → aus
# VITE_API_BASE_URL abgeleitet (api.→mcp.). Lokal sinnvoll der direkte
# mcp-http-Port (mcp-remote akzeptiert http nur fuer 127.0.0.1/localhost).
ARG VITE_MCP_URL=
# Edition-Flag (ADR-0029): Default `onprem` → Billing-UI wird aus dem Bundle
# tree-shaked. Cloud-Build setzt VITE_WHO2BE_EDITION=cloud.
ARG VITE_WHO2BE_EDITION=onprem
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY \
    VITE_MCP_URL=$VITE_MCP_URL \
    VITE_WHO2BE_EDITION=$VITE_WHO2BE_EDITION

RUN npm run build

FROM nginx:1.31-alpine AS runtime

RUN apk add --no-cache curl

COPY --from=builder /app/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost/healthz || exit 1
