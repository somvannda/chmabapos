# Production deployment (Docker + Cloudflare)

Serves two apps and one API on their own origins behind Cloudflare:

- `https://chmaba.com`          -> apps/web   (marketing + portal + POS)
- `https://admin.chmaba.com`    -> apps/admin (platform control panel)
- `https://chmaba.com/api/v1/*` -> chmabapos_api (FastAPI + PostgreSQL)

The front apps resolve the API to their own origin (`/api/v1`), so nginx proxies
`/api/` to the `api` container on both domains and there are no CORS calls in
production. Cloudflare terminates TLS; the origin serves `deploy/nginx.conf`
with a Cloudflare Origin CA certificate.

## Requirements

- VPS with Docker Engine + Compose v2, ports 80/443 reachable from Cloudflare.
- `chmaba.com` on a Cloudflare zone (DNS proxied, SSL mode **Full (strict)**)
  with A records for `chmaba.com`, `www.chmaba.com` and `admin.chmaba.com`
  pointing at the VPS.
- A transactional SMTP relay (Brevo etc.) for the confirmation/reset emails.

## 1. Prepare config

```bash
cp deploy/.env.example deploy/.env   # then fill secrets (never commit deploy/.env)
```

Variables are documented in `deploy/.env.example`. At minimum set
`POSTGRES_PASSWORD`, `JWT_SECRET`, `SMTP_*`. When live payment credentials are
ready, switch `CUTLUY_MODE=live` and add the Cutluy key/webhook secret.

## 2. Obtain the TLS certificate

Generate a Cloudflare Origin CA certificate covering
`chmaba.com`, `www.chmaba.com`, `admin.chmaba.com` and save it as:

```
deploy/certs/fullchain.pem
deploy/certs/privkey.pem
```

## 3. Start

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --build
docker compose -f deploy/docker-compose.prod.yml ps
```

Migrations run automatically on API container start (`alembic upgrade head`).

Seed an initial platform admin:

```bash
docker compose -f deploy/docker-compose.prod.yml exec api \
  python chmabapos_api/scripts/bootstrap_admin.py
```

## 4. Email (Brevo)

1. Create the domain sender in Brevo and verify `chmaba.com`.
2. Add Brevo's SPF/DKIM records to Cloudflare DNS (Brevo provides the values).
3. Put the SMTP login/key in `deploy/.env`; the API uses STARTTLS + auth when
   `SMTP_USE_TLS=true`.

## 5. Local one-command dev (with MailHog)

```bash
docker compose --profile dev up -d --build
```

or keep the existing `start-dev.ps1` flow (no Docker).
