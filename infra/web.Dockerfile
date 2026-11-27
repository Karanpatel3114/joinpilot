# syntax=docker/dockerfile:1.7
# JoinPilot console: a static Vite build served by unprivileged nginx on port 8080.
#   docker build -f infra/web.Dockerfile --build-arg VITE_API_URL=https://api.example.com -t joinpilot-web .
# infra/nginx.conf's Content-Security-Policy allows API calls to localhost:8000 only;
# change its connect-src when VITE_API_URL points elsewhere.

FROM node:22-alpine AS build
WORKDIR /repo/web
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY web/ ./
# The type check also covers tests, which read the shared contract fixtures.
COPY shared/ /repo/shared/
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
COPY infra/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/web/dist /usr/share/nginx/html
EXPOSE 8080
# Lets `docker compose up --wait` confirm nginx is serving the console.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
