# syntax=docker/dockerfile:1
# Контекст сборки — КОРЕНЬ репозитория: см. docker-compose.yml.

# --- Стадия 1: сборка ---
FROM node:22-alpine AS build
RUN apk add --no-cache libc6-compat && npm install -g pnpm@12.15.0
WORKDIR /app

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
# rewrites в next.config.ts вычисляются при сборке, поэтому адрес backend задаётся здесь
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL \
    NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

# --- Стадия 2: минимальный образ (standalone) ---
FROM node:22-alpine
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app

COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
COPY --from=build --chown=app:app /app/public ./public

USER app
EXPOSE 3000
CMD ["node", "server.js"]
