# Build-Context = Repo-Root (Konsistenz mit apps/api/Dockerfile).
# Aufruf via docker compose:
#   build:
#     context: .
#     dockerfile: apps/web/Dockerfile
# Multi-stage: Vite-Build mit npm, dann statisch via nginx:alpine.
# Die VITE_*-Args sind Compile-Time-Substitution (apps/web/src/config.ts:14-23
# wirft im PROD-Mode bei leer) und MUESSEN per --build-arg gesetzt sein.
FROM node:22-slim AS builder

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web/ ./

ARG VITE_API_BASE_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

RUN npm run build

FROM nginx:1.27-alpine AS runtime

RUN apk add --no-cache curl

COPY --from=builder /app/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost/healthz || exit 1
