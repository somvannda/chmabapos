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
ready, switch `CHAMABAPAY_MODE=live` and add the ChmabaPay key/webhook secret.

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

## 6. Billing job

Plan expiry, renewal reminders and **payment reconciliation** all run from the
billing job. Schedule it **hourly** so a dropped payment webhook self-heals
within the hour; the job is idempotent, so running it more often is safe. Daily
would be the bare minimum for expiry/reminders but leaves reconciliation lagging
up to a day.

```cron
0 * * * * cd /srv/chmaba && docker compose -f deploy/docker-compose.prod.yml exec -T api python chmabapos_api/scripts/run_billing_jobs.py >> /var/log/chmaba-billing.log 2>&1
```

Billing reminder emails are sent from `SMTP_FROM`; set it to
`billing@chmaba.com` in `deploy/.env` and add that address as a verified
Brevo sender so reminders don't land in spam.

## 7. Telegram notifications and daily digest

Every important platform event (signup, email verification, login, Google
sign-in, password reset, plan payment, sale, refund, stock transfer, team
change) is recorded and forwarded to the internal `chmabagroup` Telegram chat.
A once-a-day recap is posted at 22:00 Asia/Phnom_Penh.

1. Create a bot with **@BotFather** and copy its token.
2. Add the bot to `chmabagroup` (grant it permission to post).
3. Find the group chat id: send a message in the group, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and read
   `result[].message.chat.id` (it is negative for groups, e.g. `-1001234567890`).
4. Set `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (and optionally
   `TELEGRAM_DIGEST_TIMEZONE`) in `deploy/.env`, then recreate the API container:

```bash
docker compose -f deploy/docker-compose.prod.yml up -d api
```

Add a daily crontab entry for the digest. The job computes the day boundary in
`TELEGRAM_DIGEST_TIMEZONE`, so schedule it at 22:00 local — if the host clock is
UTC that is `0 15 * * *`:

```cron
0 15 * * * cd /srv/chmaba && docker compose -f deploy/docker-compose.prod.yml exec -T api python chmabapos_api/scripts/run_telegram_digest.py >> /var/log/chmaba-telegram.log 2>&1
```

The job is read-only and idempotent; running it again just re-sends the same
recap. When `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` are blank, all sends are
no-ops and events are still recorded.
