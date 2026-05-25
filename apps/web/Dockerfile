# Build-Context = Repo-Root (Konsistenz mit apps/api/Dockerfile).
# Aufruf via docker compose:
#   build:
#     context: .
#     dockerfile: apps/web/Dockerfile
FROM node:22-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV HOST=0.0.0.0

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web/ ./

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
