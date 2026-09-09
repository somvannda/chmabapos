# Chmabapos

Cloud point of sale for independent stores. Monorepo with a FastAPI backend and
two React (Vite) apps sharing one API.

## Repository layout

```
chmabapos_api/        FastAPI backend (PostgreSQL, alembic migrations, pytest)
apps/
  web/                Marketing site + auth + user portal + POS  (served at /)
  admin/              Platform admin control panel               (served at /admin/*)
docs/                 Architecture plan, ADRs, deployment notes
```

The customer-facing site, portal and POS intentionally share one origin and one
credential session. The admin panel is a separate build (and trust domain).

## Quick start (development, no Docker)

1. Backend — see `chmabapos_api/README.md` (venv, `requirements.txt`, Postgres,
   `alembic -c chmabapos_api/alembic.ini upgrade head`, seed).
2. Frontends:

```powershell
# from repo root
Set-Location apps\web; npm install; npm run dev     # http://localhost:5173
Set-Location apps\admin; npm install; npm run dev   # http://localhost:5174
```

Or run everything (MailHog + API + Vite) with:

```powershell
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
```

`VITE_API_URL` defaults to `http://127.0.0.1:8000/api/v1`.

## Docker (self-hosted)

See `docs/deploy.md`. One stack: Postgres + API + nginx serving both apps.

```bash
docker compose up -d --build
```

## Docs

- `docs/architecture.md` — platform structure plan and architecture decision records
- `docs/deploy.md` — deployment topology and configuration
- `chmabapos_api/openapi.json` — committed OpenAPI spec of the API (CI fails on drift)

## License

Private / not yet licensed.
