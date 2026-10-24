# Platform health monitoring

Chmaba's `/api/v1/health` only ever answered for the database. A payment
provider that stopped issuing KHQR codes, a mail relay that refused mail or a
storefront that was down all looked exactly like a quiet afternoon: the API was
up, cashiers got a 502, and the platform team found out when a merchant called.

This document describes the self-monitoring that closes that gap: what is
checked, how a failure becomes an alert, and what an operator sees.

## What is checked

A single in-process sweep probes every dependency the product sells through. A
check is one row in `system_health_checks`, rewritten by each sweep.

| Check | Severity | What it proves |
| --- | --- | --- |
| `database` | critical | The API can run a query, and it is not pathologically slow. |
| `khqr_generation` | critical | A cashier can mint a KHQR right now: live mode, API key, ChmabaPay reachable and authenticating, at least one merchant with an active link, and no recent failed QR attempts. |
| `khqr_links` | warning | No merchant link is sitting in `error`. Links `pending` activation are normal onboarding and are reported, not alarmed. |
| `email_outbound` | warning | The selected transport accepts us: Resend answers an authenticated request, or the SMTP relay accepts a TCP connection. |
| `media_storage` | warning | A product image can be written to and deleted from the media root. |
| `storefront` | warning | The configured storefront host answers `/healthz`. Skipped when `STOREFRONT_URL` is blank. |
| `pos_web` | warning | The web POS origin answers. Skipped when `FRONTEND_URL` is blank. |
| `telegram` | info | The bot token is accepted. Skipped when Telegram is not configured. |
| `ai_assistant` | info | An AI provider and key are configured. Never calls the paid provider. |

`khqr_generation` is the check that matters most, and it is deliberately judged
from two sides:

1. **Actively** — the sweep calls ChmabaPay, so a provider outage or a revoked
   key is noticed without waiting for a merchant to try.
2. **Passively** — every failed `create_payment` in the POS, storefront and
   billing checkout paths is recorded through `record_khqr_success()` /
   `record_khqr_failure()` in `app/services/health.py`. One failure in the window
   reads `degraded`; two or more read `down`. This is what catches the case the
   provider itself reports as healthy while cashiers still cannot sell.

A check that is deliberately not running reports `skipped`, never `down`: mock
payments, an unconfigured storefront host and a missing Telegram bot are valid
configurations, not outages.

## How a failure becomes an alert

- The worker (`_run_health_sweep` in `app/main.py`) sweeps on
  `HEALTH_CHECK_INTERVAL_SECONDS`, and immediately on startup.
- A check must fail `HEALTH_CHECK_ALERT_AFTER_FAILURES` sweeps in a row before it
  pages. With the defaults that is about four minutes, which ignores a single
  blip.
- `critical` checks page while `degraded`; `warning` checks only page when fully
  `down`; `info` checks never page. Everything is still visible on the admin page.
- A dependency that stays down pages at most once per
  `HEALTH_CHECK_ALERT_COOLDOWN_MINUTES`.
- One aggregated Telegram message describes the whole sweep, not one message per
  check. When everything returns to `ok`, a single recovery message is sent.
- Only a scheduled sweep alerts. The admin "Run checks now" button probes without
  paging anyone.

Every state change is appended to `system_health_events`, so the admin page can
show the incident history ("KHQR checkout down 14:02 → recovered 14:09").
Retention is `HEALTH_CHECK_EVENT_RETENTION_DAYS`.

## What an operator sees

- **Admin → System health** (`/health`): the overall state, every check with its
  summary, latency and consecutive failures, and the recent transitions. The
  "Run checks now" button forces a sweep; it is audited as
  `system_health.run`.
- **Admin → Overview**: the badge used to say "All systems operational" no
  matter what. It now reads the last sweep, turns yellow or red when a dependency
  is degraded or down, and links to the health page.
- **Admin → Needs attention**: a `system_health` item is prepended only while
  something is unhealthy, so a healthy platform adds no noise.
- **`GET /api/v1/health`**: adds a `dependencies` summary (`overall`, `down`,
  `degraded`, `checks`) without naming anything, because the route is public. It
  still answers `200` when a dependency is down: the container healthcheck polls
  it every 10 seconds, and a red dependency must page a human rather than restart
  the API in a loop.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `HEALTH_CHECK_WORKER_ENABLED` | `true` | Turn the in-process sweep off, e.g. when an external monitor replaces it. |
| `HEALTH_CHECK_INTERVAL_SECONDS` | `120` | Sweep cadence. |
| `HEALTH_CHECK_TIMEOUT_SECONDS` | `12` | Per-probe ceiling; a hanging provider is reported as down. |
| `HEALTH_CHECK_ALERT_AFTER_FAILURES` | `2` | Consecutive bad sweeps before paging. |
| `HEALTH_CHECK_ALERT_COOLDOWN_MINUTES` | `30` | Minimum gap between pages for one check. |
| `HEALTH_CHECK_EVENT_RETENTION_DAYS` | `90` | Transition history kept. |
| `HEALTH_CHECK_KHQR_FAILURE_WINDOW_MINUTES` | `15` | How far back a failed QR request counts. |
| `HEALTH_CHECK_SLOW_QUERY_MS` | `1500` | Database latency that reads `degraded`. |
| `PLATFORM_ADMIN_URL` | blank | Deep link appended to alerts, e.g. `https://admin.chmaba.com`. |

The sweep runs in-process, like the billing and mailing workers. The production
container starts a single uvicorn process, so one sweep runs per deployment. If
the API is ever scaled to multiple replicas, each replica would sweep and page;
guard the sweep with a Postgres advisory lock (the billing lifecycle in
`app/main.py` shows the pattern) before scaling.

## Adding a check

Add a probe to `CHECKS` in `app/services/health.py`:

```python
async def _probe_documents(db: AsyncSession) -> CheckResult:
    ...
    return CheckResult(STATUS_OK, "summary for the admin page", "optional detail")


CHECKS = (
    ...,
    Check("documents", "Document rendering", "delivery", "warning", _probe_documents),
)
```

Rules that keep the board honest:

- Never raise for an expected failure; return `STATUS_DOWN` with a summary a
  non-engineer can act on. A raised exception is caught and reported as down, but
  the operator loses the reason.
- Return `STATUS_SKIPPED` when the feature is not configured, so an optional
  integration never looks broken.
- Keep the probe cheap. It runs every two minutes for the life of the process.
- Prefer an authenticated, side-effect-free request. Do not create real payments,
  send real mail or charge a provider to prove it works.

The sweep serialises probes because they share one `AsyncSession`; a probe that
needs a long call should still respect `HEALTH_CHECK_TIMEOUT_SECONDS`.
