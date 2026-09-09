# Self-hosted deployment (Docker)

Builds three deployables into two containers: a Python API container
(`chmabapos_api`) + Postgres, and an nginx container serving the two Vite apps:

- `http://<host>/`         -> apps/web  (marketing + portal + POS)
- `http://<host>/admin/*`  -> apps/admin (control panel)
- `http://<host>/api/v1/*` -> chmabapos_api
- `http://<host>/docs`     -> FastAPI docs (proxy)

## Requirements

Docker Engine + Compose v2 on a host (VPS) with ports 80 (and 443 when TLS is added).

## 1. Configuration

Create a `.env` at the repo root from `chmabapos_api/.env.example` plus the
variables referenced in `docker-compose.yml` (secrets only, never committed):

```dotenv
POSTGRES_USER=chmaba
POSTGRES_PASSWORD=<strong password>
POSTGRES_DB=chmabapos
JWT_SECRET=<long random string>
CUTLUY_MODE=live
CUTLUY_API_KEY=...
CUTLUY_WEBHOOK_SECRET=...
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_FROM=no-reply@chmaba.com
FRONTEND_URL=https://chmaba.com
CORS_ORIGINS=https://chmaba.com
HTTP_PORT=80
```

> Note: `chmabapos_api/.env` is **not** needed in the container - the API is
> configured through the environment above (pydantic reads env vars).

## 2. Start

```bash
docker compose up -d --build
docker compose ps
```

Migrations run automatically on API container start (`alembic upgrade head`).

Seed an initial platform admin (optional):

```bash
docker compose exec api python chmabapos_api/scripts/bootstrap_admin.py
```

## 3. TLS / domain

Point `chmaba.com` (and `www`) at the host, then put a reverse proxy in front or
use Caddy/nginx on the host to terminate TLS and forward to the container's
HTTP port. The API is reachable on the same origin under `/api/v1`, so the
front-ends need `VITE_API_URL` to match:

- Vercel/other static hosting of `apps/web` + `apps/admin` is possible too:
  set `VITE_API_URL=https://chmaba.com/api/v1` at build time.

## 4. Local one-command dev (with MailHog)

```bash
docker compose --profile dev up -d --build
```

or keep the existing `start-dev.ps1` flow (no Docker).
