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

## 4. Email (Brevo or Resend)

1. Create the domain sender and verify `chmaba.com`.
2. Add the provider's SPF/DKIM records to Cloudflare DNS.

There are two ways to configure sending:

- **From the admin panel (recommended).** Sign in as a platform super admin,
  open **Mailing → Sending**, choose the provider, paste the API key, set the
  from-address/name, and use **Send test** to confirm. Resend is delivered
  through `api.resend.com`; SMTP uses the env relay below. The key is stored
  server-side, masked on read, and reveal is audited.
- **Via environment** (`deploy/.env`), for the SMTP relay: STARTTLS + auth are
  used when `SMTP_USE_TLS=true` (port 587); implicit TLS (port 465) is used when
  `SMTP_USE_SSL=true`.

Set `API_PUBLIC_URL` to the public origin (e.g. `https://chmaba.com`). It is used
to build one-click unsubscribe links and the absolute image URLs embedded in
mailing emails; if it is wrong, those links and images break.

Resend over SMTP is also possible: `SMTP_HOST=smtp.resend.com`, port `587`,
`SMTP_USERNAME=resend`, `SMTP_PASSWORD=<api key>`, `SMTP_USE_TLS=true`.

### Bounces and complaints

In the Resend dashboard add a webhook pointing at
`https://chmaba.com/api/v1/webhooks/resend`, subscribed to at least
`email.bounced` and `email.complained`, then paste its signing secret into
**Settings → Email sending → Resend webhook secret**.

A hard bounce or a spam complaint suppresses that address automatically and
marks the delivery row, so it is never mailed again - which is what protects the
sending domain's reputation. The endpoint is public but every request must carry
a valid Svix signature, so the secret is required before it will accept
anything.

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

## 7. Mailing queue

Mailing sends (manual campaigns and the automated drip) are written to an outbox
and delivered by a worker, so the admin request returns immediately and
transient provider failures are retried with backoff.

**The API drains the queue itself** - an in-process worker runs every
`MAILING_QUEUE_INTERVAL_SECONDS` (default 30s) whenever
`MAILING_QUEUE_WORKER_ENABLED` is true (the default). No external scheduler is
required for manual campaigns.

The cron below is therefore **optional**, but useful as a redundant safety net;
a Postgres advisory lock guarantees the worker and the cron can never send the
same message twice:

```cron
* * * * * cd /srv/chmaba && docker compose -f deploy/docker-compose.prod.yml exec -T api python chmabapos_api/scripts/run_mailing_queue.py >> /var/log/chmaba-mailing.log 2>&1
```

The drip is enqueued far less often (hourly is plenty); it also drains the queue
once when it runs:

```cron
15 * * * * cd /srv/chmaba && docker compose -f deploy/docker-compose.prod.yml exec -T api python chmabapos_api/scripts/run_mailing_drip.py >> /var/log/chmaba-mailing.log 2>&1
```

Running either more often is safe: each queued row is delivered once, and each
(person, drip step) is enqueued at most once. You can also press **Process queue
now** on the admin Mailing page to flush it immediately.

The drip only enqueues inside its configured local send window (default:
weekdays 08:00-20:00 `Asia/Phnom_Penh`), and a per-run cap bounds a burst; both
are editable under **Mailing -> Automated drip**. **Run now** bypasses the
window so an operator can test it at any hour.

## 8. Telegram notifications and daily digest

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
