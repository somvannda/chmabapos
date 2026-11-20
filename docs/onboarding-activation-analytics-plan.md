# Onboarding Activation Analytics — Implementation Plan

Status: Proposed
Owners: Engineering + Product
Scope: Instrument the whole merchant journey — landing → signup → email
verification → workspace setup → first product → first sale — so we can answer
*where* merchants drop off, *why* they drop off, and *which fix* moves the
activation rate. Covers `apps/web` (merchant POS), `apps/storefront`,
`apps/android` and `apps/ios` at milestone level, the API, and a new
`apps/admin` journey explorer.

Related: `docs/activation-intelligence-requirements.md` (master requirements,
delivery WBS and the AI insight layer), `docs/guided-setup-and-onboarding-plan.md`
(the coach this plan measures), `docs/architecture.md`, `docs/system-health.md`,
`docs/support-operations.md`, `chmabapos_api/app/api/admin.py`
(`/admin/funnel`, `/admin/retention`), `chmabapos_api/app/api/v1.py`
(`/auth/register`, `/auth/verify-email`, `/workspaces/setup`,
`/setup/checklist`), `apps/web/src/features/onboarding.jsx`,
`apps/web/src/features/auth.jsx`, `apps/web/src/components/SetupJourney.jsx`.

---

## 1. Verdict

Yes — this is the right thing to build, but **"track every click" is the wrong
first sentence**, and building it naively will produce a database nobody reads.

Three corrections that shape this plan:

1. **Milestones must be server-authoritative.** The browser is an unreliable
   narrator: ad blockers, offline tabs, closed laptops, older app versions. A
   funnel whose stages come only from client events will disagree with the
   ledger and will silently lose the users who gave up. Every conversion number
   comes from a DB-derived server event; client events only explain *why*.
2. **Clicks are cheap, decisions are expensive.** We do not need every click on
   every page. We need every click *inside a funnel step*, plus a small
   autocapture stream for discovery. 60–70 named events, versioned and tested,
   beat 6,000 anonymous `button_click` rows.
3. **"Why" is not in the clickstream.** Drop-off is explained by validation
   errors, API failures, latency, dead/rage clicks, wrong-device verification,
   and confusion. Those need to be recorded *next to* the step, and one
   human-readable signal (a 1-question exit survey, or a 20-second replay) is
   worth more than another chart.

**Recommendation:** build the event pipeline in-house (it fits the existing
self-hosted stack, the admin panel, and the privacy posture), and buy or bolt on
session replay only if the qualitative phase needs it. Do **not** build replay
from scratch.

**North star:** *Activation rate* = % of new signups that record a paid sale
within 7 days. **Speed metric:** median time from signup to first paid sale.
Everything in this document exists to move those two numbers.

---

## 2. What already exists (and why it is not enough)

This is not a greenfield problem. The repo already has four half-pipelines that
should be reused rather than replaced.

| Existing piece | Where | What it gives us | Gap |
|---|---|---|---|
| Activation funnel (5 stages) | `GET /api/v1/admin/funnel`, `AdminFunnel` in `apps/admin/src/App.jsx` | Signed up → verified → workspace → first product → first sale, plus stalled counts, median time to first sale, drip-email lift | **Not a cohort.** Each stage is counted independently over the same window (users in window vs companies created in window), so "conversion from previous" mixes denominators and can exceed 100%. No step below those 5 stages, so "verified → workspace" is a 60% black box. |
| Retention + cohorts | `GET /api/v1/admin/retention`, `AdminRetention` | Weekly active stores, repeat rate, signup cohorts, 28-day activation | Only reaches the *first paid sale*, not the setup path to it. |
| `PlatformActivity` | `chmabapos_api/app/models.py` | Cross-tenant event feed: `user.registered`, `user.email_verified`, `user.logged_in`, sales, refunds, plan payments | Emitted for ops/Telegram, not analysed. No session, route, device, or step context. Not exposed as a funnel. |
| `EmailClickEvent` + Resend webhook | `EmailClickEvent`, `apps/admin` mailing pages | Which links in which emails get clicked | Not joined to the merchant's landing session, so we cannot see "clicked the 'finish setup' email → bounced off the verification wall". |
| `GET /setup/checklist` + `SetupJourney` coach | `v1.py::_build_setup_steps`, `components/SetupJourney.jsx` | The adaptive journey, and the anchor each step wants | No record that a step was *shown*, *shown me clicked*, *dismissed*, or *stuck for 9 minutes*. |
| Support assistant + tickets | `support/*`, `SupportChat` | Free-text evidence of confusion | Not classified into friction themes, not linked to the funnel step the user was on. |
| `AuthSession`, `AuditLog`, `TenantAuditLog` | `models.py` | Server-side auth + action trails | Auth trail is not a product funnel; audit logs are per-tenant, not journey-level. |

**Consequence:** today we can say *"60% of verified users never create a
workspace"*. We cannot say *whether they never opened setup, opened it and quit
on the plan step, hit a 500 on `POST /workspaces/setup`, or opened the
verification email on their phone and the code expired.* That is the gap this
plan closes.

---

## 3. The questions the system must answer

Write the plan backwards from the decision, not from the table.

### Acquisition / signup
1. Which channel (`utm_source`, referrer, email link, guide, QR) produces
   signups that *reach a first sale*, not just signups?
2. Where in the signup form do people stop typing — email, password, or submit?
3. What are the top 5 signup failures (email exists, weak password, Turnstile,
   rate limit, network)?
4. Do Google sign-ups activate faster than email/password? (Google path skips
   verification entirely — `v1.py` Google callback sets `is_email_verified`.)

### Verification (the most under-instrumented wall)
5. What share of registered users never verify within 24 h / 7 d / ever?
6. Of those who try: wrong code, expired code, resend, rate-limited, or
   "confirmed on another device"?
7. How many open the email on a different device than the one they signed up
   on? (Link-in-email → desktop vs mobile split.)
8. Does the drip email actually bring them back, and what do they do in the
   first 60 seconds after clicking it?

### Workspace setup
9. Of users who open `/<username>/setup/company`, what % finish step 1, 2, 3?
10. How long does each step take (median + p90), and where do they press Back?
11. Which plan card gets selected, and what happens next: free → workspace,
    paid → payment page → abandoned / paid / failed?
12. How many `POST /workspaces/setup` calls fail, and with which status/detail?
13. How many create a workspace but never load the dashboard (first
    `/workspaces/current` fails, or the shell throws)?

### First product
14. How many open the product form and abandon it?
15. Which fields cause the most validation errors? Which fields are never
    touched (suggesting the form is too long)?
16. How many use the sample products and never add a real one?
17. Does `import`/`quick add` change the outcome?

### First sale
18. Time from workspace creation to cart start, checkout open, payment, paid.
19. Which payment method is attempted first, and where does payment fail?
20. How many open a shift and then stop?
21. Which users hit the coach, click "Show me", and still don't finish?

### Global "why"
22. API error rate and p95 latency on the exact endpoints the funnel depends on.
23. JS errors and dead clicks on the setup screens.
24. Does language (en/km), currency, country, vertical, or device predict
    failure?
25. Which support-chat questions cluster around which step?

---

## 4. Measurement model

### 4.1 Canonical activation funnel (cohort-based)

A **single cohort**: every `User` created in the window. Each subsequent stage
is "how many of *that cohort* have done X by now". A user can only move
forward. This is the fix for the current non-cohort funnel.

| # | Stage key | Definition (authoritative source) | Owner |
|---|---|---|---|
| S0 | `landing_viewed` | first `page.viewed` on `/` (anonymous) | client |
| S1 | `signup_started` | first focus/keystroke in signup form | client |
| S2 | `signup_submitted` | `POST /auth/register` received | server |
| S3 | `account_created` | `User` row committed | server |
| S4 | `verification_requested` | code issued (`EmailVerificationToken`) | server |
| S5 | `verification_link_clicked` | GET with `?token=` on `/` or `/login` | server |
| S6 | `email_verified` | `is_email_verified` flips true | server |
| S7 | `first_login` | first successful `POST /auth/login` **or** Google exchange | server |
| S8 | `setup_opened` | `/<user>/setup/company` mounted | client |
| S9 | `company_details_completed` | step 1 → 2 | client |
| S10 | `questions_completed` | step 2 → 3 | client |
| S11 | `plan_confirmed` | continue pressed on step 3 | client |
| S12 | `workspace_created` | `POST /workspaces/setup` 201 | server |
| S13 | `workspace_loaded` | `GET /workspaces/current` 200 **and** shell rendered | server + client |
| S14 | `first_product_added` | `Product` with `is_sample=false` committed | server |
| S15 | `shift_opened` | first `Shift` row | server |
| S16 | `cart_started` | first item added to cart | client |
| S17 | `checkout_opened` | payment modal opened | client |
| S18 | `first_sale` | first `Order` with `status='paid'` | server |
| S19 | `second_sale_7d` | second paid order within 7 days (habit) | server |

Notes:

- S0–S1 are anonymous. Everything from S2 on is stitched to a `user_id`
  (§7.2), so the whole path is one row per user even across devices.
- Paid plans insert two stages between S11 and S12 that we track separately:
  `payment_page_viewed`, `payment_completed`, `payment_abandoned`,
  `payment_failed` (see §6.4). They must not be folded into S12, or choosing a
  paid plan will look like a setup failure.
- `workspace_loaded` is deliberately split: server success is not proof the
  merchant saw a usable screen.

### 4.2 Micro-funnels

Each canonical stage expands into a small funnel of its own. These are the
screens where the real work happens:

| Micro-funnel | Steps |
|---|---|
| Signup | form viewed → email focused → email valid → password focused → password valid → submit → success/error |
| Verification | confirmation screen → code field focused → code submitted → success / invalid / expired / rate-limited → resend → link clicked |
| Onboarding wizard | step 1 viewed → field edited (per field) → continue → step 2 → per-question answered → continue → step 3 → plan card viewed → plan selected → submit → success/error |
| Product create | modal opened → each field touched → save → validation errors (field, rule) → success / cancel / close |
| KHQR setup | section opened → instructions viewed (scroll) → link pasted → verify → failed(reason) → verified → test scan → success |
| First sale | cart start → item added → checkout → payment method → confirm → paid / failed(reason) |

### 4.3 Guardrail metrics

Track these on the same dashboards so activation gains are not bought by
breaking the product:

- p95 latency of `/workspaces/current`, `/products`, `/orders`, `/setup/checklist`
- client JS error rate per 1,000 sessions
- API 5xx rate per endpoint
- rage-click rate per route
- support tickets per 100 new workspaces
- refund/void rate for new workspaces (a fake "first sale" is not activation)

---

## 5. Architecture

```
apps/web ─┐
apps/storefront ─┤   batch POST /api/v1/telemetry/events
apps/android ─┤   (keepalive / sendBeacon, gzip, ≤ 64 KB)
apps/ios ─┘                │
                           ▼
                 ┌───────────────────────┐
                 │  telemetry router     │  validate → sanitize → rate-limit
                 │  (FastAPI, no auth    │  → resolve identity → insert batch
                 │   required)           │
                 └──────────┬────────────┘
                            │
   server code (register,   │        ┌──────────────────────────────┐
   verify, workspace,       ├───────▶│ analytics_events             │
   product, order, shift)   │        │ (monthly partitions, 90 d)   │
   via analytics.emit()     │        └──────────────┬───────────────┘
                            │                       │ nightly rollup
                            ▼                       ▼
                 analytics_sessions      analytics_daily_rollups (2 y)
                            │                       │
                            └──────────┬────────────┘
                                       ▼
                        GET /api/v1/admin/journeys/*
                                       ▼
                        apps/admin → "Journeys" page
```

Design choices, and why:

- **One collector for all clients.** The event schema and the funnel definition
  live in one place, so web/Android/iOS cannot drift.
- **Postgres, not a new datastore.** The volume (§14) is small enough, the
  team already runs Postgres, and events must join to `users`, `companies`,
  `stores`, `orders`. A separate OLAP store is a later optimization, not a
  phase-1 requirement.
- **Anonymous ingestion allowed.** Pre-signup behaviour is half the question.
  The endpoint is public but aggressively rate-limited and payload-capped, and
  it never reads `Authorization` (it accepts an optional token to attach
  identity, and otherwise trusts nothing).
- **Server emit is a function call, not an HTTP call.** `analytics.emit(db, …)`
  writes one row in the caller's transaction (or an outbox row when the caller
  must not fail). No extra network hop, no lost events on rollback.
- **The admin UI reads aggregated endpoints.** The browser never queries
  `analytics_events` directly, so a heavy query can't take down the panel.

### 5.1 Why not just PostHog?

PostHog (or Amplitude) gives autocapture, funnels, cohorts, and session replay
on day one. It is the faster path to *insight* and the slower path to *control*.
This plan is in-house because:

- The merchant funnel must join to tenant rows (`companies`, `plans`,
  `subscriptions`, `orders`) and be visible inside the existing admin panel.
- The repo is self-hosted with a strict deploy story; a third-party script on
  the POS adds a vendor, a CSP entry, a consent question, and a new failure mode
  on the exact page that must never fail.
- PII: merchant and customer data (names, phones, prices) must not leave the
  deployment by default.

**However:** if the team wants session replay, buy it. Recommended order:
self-hosted PostHog if ops capacity exists, otherwise PostHog Cloud EU with
`person_profiles: "identified_only"`, input masking, and no raw URLs. Replay is
Phase 5 and optional; it is not on the critical path.

---

## 6. Data model

### 6.1 `analytics_sessions`

One row per client session (30-minute inactivity timeout), created from the
first event and updated by heartbeats.

```sql
CREATE TABLE analytics_sessions (
  id                uuid PRIMARY KEY,
  anonymous_id      uuid NOT NULL,
  user_id           uuid NULL REFERENCES users(id) ON DELETE SET NULL,
  company_id        uuid NULL REFERENCES companies(id) ON DELETE SET NULL,
  store_id          uuid NULL REFERENCES stores(id) ON DELETE SET NULL,
  source            text NOT NULL,              -- web | storefront | android | ios
  started_at        timestamptz NOT NULL,
  last_seen_at      timestamptz NOT NULL,
  ended_at          timestamptz NULL,
  entry_route       text,
  exit_route        text,
  referrer_host     text,
  utm_source        text,
  utm_medium        text,
  utm_campaign      text,
  utm_content       text,
  utm_term          text,
  app_version       text,
  platform          text,                       -- web | android | ios
  os                text,
  browser           text,
  device_type       text,                       -- desktop | tablet | phone
  locale            text,
  timezone          text,
  is_internal       boolean NOT NULL DEFAULT false,
  ip_hash           text,
  user_agent        text
);
CREATE INDEX ix_sessions_user_time ON analytics_sessions (user_id, started_at DESC);
CREATE INDEX ix_sessions_company_time ON analytics_sessions (company_id, started_at DESC);
CREATE INDEX ix_sessions_anon ON analytics_sessions (anonymous_id);
```

### 6.2 `analytics_events` (monthly range partitions)

```sql
CREATE TABLE analytics_events (
  id            bigint GENERATED ALWAYS AS IDENTITY,
  occurred_at   timestamptz NOT NULL,
  received_at   timestamptz NOT NULL DEFAULT now(),
  event_id      uuid NOT NULL,          -- client-generated; dedupes retries
  session_id    uuid NOT NULL,
  anonymous_id  uuid NOT NULL,
  user_id       uuid NULL,
  company_id    uuid NULL,
  store_id      uuid NULL,
  name          text NOT NULL,
  version       smallint NOT NULL DEFAULT 1,
  source        text NOT NULL,
  route         text,                   -- normalized: /:user/products
  route_key     text,                   -- products | pos | settings.bank-khqr
  element_key   text,                   -- data-track value, e.g. onboarding.plan.continue
  duration_ms   integer,
  properties    jsonb NOT NULL DEFAULT '{}'::jsonb,
  context       jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE UNIQUE INDEX ux_events_event_id ON analytics_events (event_id, occurred_at);
CREATE INDEX ix_events_name_time ON analytics_events (name, occurred_at DESC);
CREATE INDEX ix_events_session ON analytics_events (session_id, occurred_at);
CREATE INDEX ix_events_user_time ON analytics_events (user_id, occurred_at DESC);
CREATE INDEX ix_events_company_time ON analytics_events (company_id, occurred_at DESC);
```

Partition creation is handled by a small `ensure_partitions()` job (same
worker pattern as `SystemHealthCheck`), creating the next month plus a default
partition. `alembic` creates the parent + current/next month.

**Do not** add a GIN index on `properties` in phase 1. It doubles write cost for
queries we can serve from named columns. Add it only if a real report needs it.

### 6.3 Rollups

```sql
CREATE TABLE analytics_daily_rollups (
  day         date NOT NULL,
  name        text NOT NULL,
  route_key   text NOT NULL DEFAULT '',
  source      text NOT NULL DEFAULT '',
  company_id  uuid NULL,
  events      bigint NOT NULL,
  sessions    bigint NOT NULL,
  users       bigint NOT NULL,
  p50_ms      integer NULL,
  p95_ms      integer NULL,
  PRIMARY KEY (day, name, route_key, source, company_id)
);
```

Nightly job recomputes the last 3 days (late events, timezone edges) and keeps
2 years. Raw events expire at 90 days via `DROP PARTITION`, which is cheap and
leaves no vacuum debt.

### 6.4 Payment sub-stages

Billing is a separate state machine (`Subscription`, `BillingPayment`, provider
webhooks). Emit its transitions as events rather than inferring them:

```
billing.checkout_opened     client
billing.payment_created     server  (BillingPayment row)
billing.payment_succeeded   server  (webhook)
billing.payment_failed      server  (webhook / poll timeout)
billing.plan_activated      server  (Subscription.status → active)
```

This is the only way to separate "chose Pro and paid" from "chose Pro and left".

---

## 7. Event taxonomy

Every event name is `domain.object_action`, snake_case, versioned. A registry
file is the single source of truth and **CI fails on an unregistered name**
(same discipline as the OpenAPI drift check).

### 7.1 Registry shape

`chmabapos_api/app/analytics_registry.py`:

```python
EVENTS: dict[str, EventSpec] = {
    "onboarding.step_completed": EventSpec(
        version=1,
        owner="client",
        props={"step": "int", "step_key": "str", "duration_ms": "int"},
        sample=1.0,
    ),
    "sale.completed": EventSpec(
        version=1,
        owner="server",
        props={"order_id": "uuid", "payment_method": "str", "currency": "str"},
        sample=1.0,
    ),
    # ...
}
```

`apps/web/src/lib/analyticsEvents.js` is generated from it (or a shared JSON
file committed in `packages/`), so the client cannot invent names either.

### 7.2 Client events

| Event | Props | When | Sample |
|---|---|---|---|
| `session.started` | `entry_route`, `referrer_host`, `utm_*` | SDK init | 1.0 |
| `session.heartbeat` | `route_key`, `visible`, `funnel_step` | every 30 s while visible | 1.0 (folded into session row) |
| `session.ended` | `exit_route`, `duration_ms`, `reason` | `pagehide`/30 min idle | 1.0 |
| `page.viewed` | `route`, `route_key`, `title_key` | route change | 1.0 |
| `page.left` | `route_key`, `dwell_ms`, `scroll_pct` | route change/unload | 1.0 |
| `ui.click` | `element_key`, `role`, `label_key`, `route_key` | meaningful click | 1.0 merchant, 0.2 shopper |
| `ui.rage_click` | `element_key`, `route_key`, `clicks` | ≥3 clicks/1 s on same element | 1.0 |
| `ui.dead_click` | `element_key`, `route_key` | click, no DOM/route change in 700 ms | 1.0 |
| `ui.form_field_focused` | `form`, `field` | focus | 1.0 |
| `ui.form_field_completed` | `form`, `field`, `duration_ms` | blur with value | 1.0 |
| `ui.form_validation_failed` | `form`, `field`, `rule` | submit blocked | 1.0 |
| `ui.form_abandoned` | `form`, `last_field`, `filled_fields` | leave with a dirty form | 1.0 |
| `error.client` | `error_key`, `route_key`, `boundary` | error boundary / `window.onerror` | 1.0 |
| `error.network` | `endpoint_key`, `status`, `code`, `retry` | failed fetch | 1.0 |
| `perf.route` | `route_key`, `ttfb_ms`, `dcl_ms`, `lcp_ms` | navigation timing | 0.5 |
| `auth.signup_started` | `mode` | first input | 1.0 |
| `auth.signup_submitted` | `mode`, `turnstile` | submit | 1.0 |
| `auth.signup_failed` | `reason` | API error | 1.0 |
| `auth.verify_submitted` | `method` (`code`/`link`), `device_switch` | submit | 1.0 |
| `auth.verify_failed` | `reason` | error | 1.0 |
| `auth.verify_resent` | — | resend | 1.0 |
| `auth.login_submitted` / `_failed` | `method`, `reason` | submit | 1.0 |
| `onboarding.step_viewed` | `step`, `step_key` | mount | 1.0 |
| `onboarding.step_completed` | `step`, `step_key`, `duration_ms`, `back_count` | continue | 1.0 |
| `onboarding.step_back` | `from_step`, `to_step` | back | 1.0 |
| `onboarding.abandoned` | `step`, `step_key`, `dwell_ms`, `last_field` | unload/heartbeat gap | 1.0 |
| `onboarding.plan_viewed` | `plan_code`, `recommended` | card in viewport ≥1 s | 1.0 |
| `onboarding.plan_selected` | `plan_code`, `recommended` | card click | 1.0 |
| `onboarding.submit_failed` | `status`, `detail_key` | `POST /workspaces/setup` error | 1.0 |
| `product.create_opened` | `entry` (`button`/`import`/`coach`) | modal open | 1.0 |
| `product.create_field_edited` | `field`, `has_value` | blur | 1.0 |
| `product.create_failed` | `field`, `rule` | validation block | 1.0 |
| `product.created` | `entry`, `duration_ms`, `fields_filled` | success (server also emits) | 1.0 |
| `product.import_started` / `_failed` | `rows`, `reason` | import | 1.0 |
| `payments.khqr_section_opened` | `scope` (`company`/`store`) | settings | 1.0 |
| `payments.khqr_link_pasted` | `length_bucket` | paste | 1.0 |
| `payments.khqr_verify_failed` | `reason` | verify error | 1.0 |
| `payments.khqr_verified` | `scope` | success (server also emits) | 1.0 |
| `payments.khqr_test_scan` | `result` | test scan | 1.0 |
| `coach.shown` | `step_id`, `completed`, `total` | render | 1.0 |
| `coach.show_me` | `step_id`, `target_found` | click | 1.0 |
| `coach.dismissed` | `step_id`, `completed` | dismiss | 1.0 |
| `coach.completed` | `days_since_signup` | all steps done | 1.0 |
| `sale.cart_started` | `entry` | first item | 1.0 |
| `sale.checkout_opened` | `items`, `total_bucket`, `currency` | modal | 1.0 |
| `sale.payment_method_selected` | `method` | click | 1.0 |
| `sale.checkout_failed` | `reason`, `method` | error | 1.0 |
| `shift.open_clicked` / `shift.opened` | `opening_float_bucket` | shift | 1.0 |
| `help.article_opened` | `article_id`, `from` | help | 1.0 |
| `support.chat_opened` | `from_route`, `funnel_step` | chat | 1.0 |
| `support.message_sent` | `intent` (classified server-side) | send | 1.0 |
| `storefront.order_started` / `_submitted` | `store_slug`, `items` | shopper | 1.0 |
| `qr.downloaded` / `qr.shared` | `scope`, `format` | QR | 1.0 |
| `invite.link_clicked` / `invite.accepted` | `role` | team | 1.0 |

### 7.3 Server events (authoritative)

Emitted from the API at the same commit point as the business row:

| Event | Hook |
|---|---|
| `user.registered` | `register()` — already has `record_activity` |
| `user.email_verified` | `verify_email()` |
| `user.logged_in` | `login()` / Google exchange |
| `workspace.created` | `setup_workspace()` after commit |
| `workspace.first_loaded` | first `GET /workspaces/current` per company (cache the flag on `Company.settings`) |
| `plan.selected` | `setup_workspace()` (`plan_code`, `billing_cycle`) |
| `product.created` | `create_product()` |
| `inventory.opening_set` | first stock movement that is not `sample_product` |
| `shift.opened` | `open_shift()` |
| `order.paid` | `mark_paid` / payment webhook |
| `order.refunded` | refund endpoint |
| `payment.link_verified` | `sync_aba_payway_link()` |
| `invite.accepted` | invitation accept |
| `storefront.order_received` | public order create |
| `drip.email_sent` / `drip.link_clicked` | mailing service (extends `EmailClickEvent` join) |

Server events carry `properties.authoritative = true` and no client props. They
are the only rows the funnel endpoint counts.

### 7.4 What is explicitly **not** collected

- Input values, passwords, card numbers, QR strings, verification/reset tokens.
- Customer names, phones, emails (only hashed where needed for dedupe).
- Full URLs with query strings on `/reset-password`, `/login`, `/order/:token`,
  or any `#access_token=` fragment.
- Keystrokes, clipboard, screen content, DOM text beyond a truncated label key.
- Anything from `platform_role` users (they are flagged `is_internal` and
  excluded from product funnels; optionally sampled for QA).

---

## 8. Client SDK

One file per client, same public surface: `init`, `identify`, `page`, `track`,
`startStep`, `endStep`, `flush`.

### 8.1 `apps/web/src/lib/analytics.js`

```js
init({ enabled, endpoint, appVersion, sample })
identify({ userId, companyId, storeId, role })   // safe to call repeatedly
page({ routeKey, titleKey })                     // on every screen change
track(name, props)                               // registry-validated in dev
startStep(stepKey, { funnel })                   // marks a funnel step open
endStep(stepKey, { outcome, props })             // closes it, emits duration
flush({ beacon })                                // on pagehide
```

Behaviour:

- **Queue + batch.** 20 events or 5 s, whichever first; `fetch(..., {keepalive:
  true})`; `navigator.sendBeacon` on `pagehide`/`visibilitychange: hidden`.
- **Offline.** Reuse the pattern already in `apps/web/src/lib/offlineQueue.js`:
  persist the last 200 events in `localStorage`, flush on reconnect, drop oldest.
- **Dedupe.** Every event gets a client `uuid`; server upserts on `event_id`.
- **IDs.** `anonymous_id` in `localStorage` (`chmaba.anon_id`, uuid v4, never
  expires); `session_id` in `sessionStorage`, rotated after 30 min inactive.
- **Sampling.** Milestones and step events at 1.0. `ui.click` is **1.0 on all
  merchant routes** — at this volume (see §14) storing every meaningful click is
  affordable, and it is what makes "every click" literally true. Only shopper
  storefront traffic is sampled (0.2), and storefront is not where the activation
  question lives. A step that is open is always 1.0 regardless of source. The
  sampling decision is made once per session, never per click, so a session is
  either fully recorded or not at all (avoids biased funnels).
- **Autocapture.** Global capture listener; keep clicks on
  `button, a, [role=button], [data-track], input[type=checkbox], [role=tab]`,
  and only when the element is inside the app (not the user's own embedded
  content). `element_key` = `data-track` || `role:accessibleName:routeKey`;
  accessible name truncated to 60 chars.
- **Rage/dead click.** 3 clicks in 1 s within 32 px → `ui.rage_click`; a click
  on an interactive element followed by no route change, no modal open, and no
  network request within 700 ms → `ui.dead_click`.
- **Funnel step lifecycle.** `startStep` writes the step key into the session
  heartbeat; the server can therefore mark a step abandoned even if the tab is
  killed (last heartbeat > 2× interval while the step is still open).
- **Performance.** `PerformanceObserver` for LCP + navigation timing, once per
  route, sampled 0.5.
- **Size budget.** ≤ 8 KB min+gzip, zero dependencies, no impact on first
  paint (load after `DOMContentLoaded`, `requestIdleCallback`).

### 8.2 Route instrumentation

`apps/web` does not use React Router for screens; it derives `screen` and
`activeView` from `parseRoute()` (`apps/web/src/routing.js`). Hook the existing
`useEffect` on `location.pathname` and on `setScreen`, and emit `page.viewed`
with a normalized `route_key` (`dashboard`, `pos`, `products`, `settings.bank-khqr`,
`setup.company`, …). Do not emit raw paths: usernames are PII-ish and slugs
change.

### 8.3 Where the SDK must be called explicitly

| Screen | Instrumentation |
|---|---|
| `features/auth.jsx` | form start, submit, error reason, verification code submit/resend, "confirmed on another device" |
| `features/onboarding.jsx` | step view/complete/back/abandon, per-field edits, plan view/select, submit error; `onboarding.step_completed.duration_ms` from step start |
| `features/catalog.jsx` | product modal open, per-field edit, validation failures, save success, import |
| `features/settings.jsx` (`BankKhqrPane`) | section open, paste, verify error reason, verified, test scan result |
| `features/sales.jsx` | cart start, checkout open, payment method, paid/failed |
| `features/team.jsx` + `SetupJourney` | coach shown/show-me/dismiss/complete, invite flow |
| `features/help.jsx`, `supportChat.jsx` | article opened, chat opened with `funnel_step`, message intent |
| `features/storeQr.jsx` | QR download/share |
| `App.jsx` | `identify()` after `/auth/me`, after login, after Google callback; `page()` on screen change; global error handlers |

`data-track` attributes (one per meaningful control) are the stable contract for
autocapture. Suggested convention: `area.action[.qualifier]`, e.g.
`onboarding.company.continue`, `onboarding.plan.card.pro`,
`catalog.product.save`, `settings.khqr.verify`, `pos.checkout.pay`.

### 8.4 Storefront and mobile

- **Storefront** (`apps/storefront`): same SDK file (or a shared package), but
  the funnel is shopper-side (`storefront.menu_viewed` → `order_started` →
  `order_submitted` → `payment_started` → `paid`). It matters for merchants
  because "your online store got 40 visits and 0 orders" is a setup-quality
  signal.
- **Android/iOS**: milestone events only, emitted through the API (they already
  talk to the same endpoints). No autocapture, no replay. Add `source=android`
  / `ios` and `app_version` so we can separate mobile activation failures.

---

## 9. Server-side emit

### 9.1 `chmabapos_api/app/analytics.py`

```python
async def emit(
    db: AsyncSession,
    name: str,
    *,
    user: User | None = None,
    company_id: UUID | None = None,
    store_id: UUID | None = None,
    session_id: UUID | None = None,
    properties: dict | None = None,
) -> None:
    """Insert one authoritative event in the caller's transaction."""
```

- Validates `name` against the registry (raises in dev/test, drops in prod).
- Caps `properties` at 4 KB and strips unknown keys.
- Never raises into the caller: wrap in `try/except` + log, because analytics
  must not break a sale. (Test this explicitly.)
- Uses `db.add()` so the event commits atomically with the business row. For
  endpoints where a rollback is likely (payment webhooks), write through a tiny
  outbox (`analytics_outbox`) flushed after commit.

### 9.2 Hook points (minimal diff)

| Function | Event |
|---|---|
| `register` | `user.registered` (+ `auth.signup_submitted` already client-side) |
| `verify_email` | `user.email_verified` |
| `login`, Google callback | `user.logged_in` with `method` |
| `setup_workspace` | `workspace.created`, `plan.selected` |
| `current_workspace` | `workspace.first_loaded` once per company |
| `create_product` | `product.created` (`is_sample=false`) |
| `open_shift` | `shift.opened` |
| `mark_paid`, payment webhook | `order.paid` |
| `refund` | `order.refunded` |
| `sync_aba_payway_link` | `payment.link_verified` |
| invitation accept | `invite.accepted` |
| public order create | `storefront.order_received` |

### 9.3 Identity resolution at ingest

1. If `Authorization` is present and valid → `user_id`.
2. Else if body has `session_id` already linked → reuse mapping.
3. Else `user_id = NULL` (anonymous).
4. `company_id`/`store_id` are **server-derived** from the membership, never
   trusted from the client body (prevents cross-tenant event injection).
5. `is_internal` = user has `platform_role` or email domain is the company's own.

---

## 10. Collector API

### 10.1 `POST /api/v1/telemetry/events`

```jsonc
{
  "source": "web",
  "app_version": "2.4.1",
  "sent_at": "2026-11-20T09:14:22Z",
  "session": {
    "id": "…uuid…",
    "anonymous_id": "…uuid…",
    "started_at": "…",
    "entry_route": "/",
    "referrer_host": "google.com",
    "utm": { "source": "facebook", "campaign": "khmer-new-year" },
    "device": { "os": "Android", "browser": "Chrome", "type": "phone" },
    "locale": "km",
    "timezone": "Asia/Phnom_Penh"
  },
  "events": [
    {
      "id": "…uuid…",
      "name": "onboarding.step_completed",
      "occurred_at": "…",
      "route_key": "setup.questions",
      "element_key": "onboarding.questions.continue",
      "duration_ms": 41230,
      "props": { "step": 2, "step_key": "questions" }
    }
  ]
}
```

Rules:

- Max 100 events/request, 64 KB body, 4 KB/event properties.
- 204 on success (no echo), 400 on malformed, 429 with `Retry-After` beyond
  `600 events/min/session` or `10,000/min/IP` (sized for unsampled click
  capture; a normal session emits far less).
- `occurred_at` more than 7 days in the future or 30 days in the past is
  clamped; the original is kept in `context.skew_ms`.
- CORS: allow the storefront host and app host only.
- No auth required, but a bearer token (when present) links the session to the
  user. Invalid/expired token → treat as anonymous, never 401 (a 401 would
  break the POS).
- Bot filter: reject `navigator.webdriver`, known crawler UAs, and requests
  with no `Origin`/`Referer` from an allowed host. Record rejected counts as a
  platform metric.

### 10.2 Admin read endpoints

```
GET /api/v1/admin/journeys/funnel?days=30&cohort=signup
GET /api/v1/admin/journeys/funnel/stage/{stage}?days=30&breakdown=vertical
GET /api/v1/admin/journeys/sessions?stage=verified&outcome=dropped&limit=50
GET /api/v1/admin/journeys/sessions/{session_id}          # timeline
GET /api/v1/admin/journeys/why?stage=workspace&days=30
GET /api/v1/admin/journeys/health                          # ingest volume, rejects, lag
GET /api/v1/admin/journeys/export.csv?...                  # ops/analyst
```

Response shapes (all `platform admin` only):

```jsonc
// funnel
{
  "cohort": "signup",
  "window_days": 30,
  "stages": [
    { "key": "account_created", "label": "Account created", "count": 812,
      "from_previous": 1.0, "from_start": 1.0,
      "median_seconds": 0, "p90_seconds": 0, "stalled": 0 }
  ]
}

// why
{
  "stage": "workspace",
  "top_errors": [{ "key": "validation.currency_unsupported", "count": 31 }],
  "top_api_failures": [{ "endpoint": "/workspaces/setup", "status": 500, "count": 12 }],
  "median_dwell_seconds": 184,
  "p90_dwell_seconds": 1204,
  "dead_click_rate": 0.08,
  "rage_click_rate": 0.03,
  "abandon_survey": [{ "answer": "plan too expensive", "count": 7 }]
}
```

---

## 11. The admin "Journeys" page

New `journeys` entry in `ADMIN_PAGES` (`apps/admin/src/routing.js`) and
`ADMIN_NAV_GROUPS` (`App.jsx`), rendered like `AdminFunnel` but with drilldowns.

Sections:

1. **Header** — date range, cohort selector (signups in window), source filter,
   "internal excluded" badge.
2. **Stage table** — one row per S0–S19: count, % from previous, % from start,
   median + p90 time, stalled count. Clicking a row opens the drilldown.
3. **Drilldown drawer**
   - Breakdown bars: vertical, country, currency, plan, language, device,
     browser, channel.
   - "Why" panel: top validation errors, top API failures, median dwell,
     dead/rage clicks, survey answers.
   - "Sessions that stopped here" table: user, company, started, last route,
     last action, dwell, error, support ticket, link to timeline.
4. **Timeline view** — one session: page views, step events, clicks (only
   meaningful ones), API failures, errors, heartbeat gaps. This is the "replay
   lite" that answers most "why" questions without a video.
5. **Cohort heatmap** — signup week × stage reached, showing whether a fix
   actually moved the cohort.
6. **Alerts** — daily digest to the ops chat: stage conversion WoW change
   > ±15%, ingest lag > 10 min, reject rate > 5%, `/workspaces/setup` 5xx > 1%.

Implementation notes:

- Reuse `AdminPageHeader` for the title row (per `AGENTS.md`).
- Charts: the admin currently uses inline bars; keep that, no chart dependency.
- Query budget: funnel endpoint ≤ 300 ms at 30 days with 5M events. If it
  isn't, serve it from `analytics_daily_rollups` and keep raw only for the
  timeline.

---

## 12. Qualitative layer (the part that actually explains "why")

Quantitative data tells you *where*; three cheap mechanisms tell you *why*.

### 12.1 Abandon survey (highest ROI, ~1 day)

When a funnel step is open and the user has been idle for 45 s, or when they
press Back out of setup, show a single non-blocking line above the footer:

> "Stuck? What's stopping you?" → [Nothing, just thinking] [I don't understand
> this step] [Something is broken] [It's too expensive] [Other…]

Store as `onboarding.abandon_survey` with the step key. One free-text field,
capped at 280 chars, explicitly opt-in (they typed it), excluded from exports.
Even 20 answers per week will beat any chart.

### 12.2 Session replay (optional, Phase 5)

If bought: PostHog/OpenReplay, `person_profiles: identified_only`, mask all
inputs, block `/reset-password`, `/login`, billing and payment screens, 10%
sampling, 30-day retention, `session_id` as the join key to our events.
If built: rrweb + gzip batches to object storage, 10% sampling, same masking,
30 days. **Estimate 2–3 weeks** for a safe build — do not start it before the
quantitative funnel is live and trusted.

### 12.3 Support-intent classification

The support assistant already stores conversations. Add a nightly job that
classifies each merchant message into a fixed set of themes (`verification`,
`plan/billing`, `product entry`, `payment link`, `printing`, `stock`,
`other`) with the existing AI stack, stores only the label + confidence, and
joins it to the user's current funnel stage. Then the "Why" panel can say
"*31% of users stuck at workspace setup asked about plan pricing*" — which is
an actionable sentence.

---

## 13. Privacy, security, compliance

The product handles merchant and shopper PII, so tracking is a data-processing
decision, not just a dev task.

### 13.1 Position: full-coverage, content-minimised

As the service provider, we **do** have a legitimate basis to observe how our
own product is used in order to operate and improve it. That covers clicks,
navigation, timing, errors, and flow completion — on our own surfaces, with our
own accounts. This plan is deliberately **not** restrictive about *coverage*: on
the merchant app every meaningful click is captured (1.0, unsampled). The limits
are about *content*, not reach.

The distinction that matters:

| We record | We never record |
|---|---|
| Which control was clicked, on which route, at what time | What the user typed into it |
| How long a step took, and where it was abandoned | Passwords, codes, tokens, card numbers |
| That a field failed validation, and which rule | The field's value |
| That a request failed, endpoint + status | Request bodies or response bodies |
| Screen-level replay with inputs masked (if enabled) | Screen contents without masking |

Why this is the right line for a POS specifically:

- **Merchant accounts are business data; shoppers are consumers.** The merchant
  is our customer and can be told plainly what we measure. A shopper in the
  storefront may be in a jurisdiction with stricter rules, so shopper analytics
  stays aggregate and non-identifying.
- **We may be a processor for the merchant's workspace data.** Behavioural
  telemetry about how the merchant's own staff use the product is a different
  processing purpose from storing their sales; the privacy policy and the
  merchant agreement must say so, and the data must be separable and deletable
  per workspace.
- **Secrets are not "usage data".** Verification tokens, reset tokens, ABA PayWay
  links, and QR strings sit in URLs on this exact flow. They are the highest-risk
  thing an over-eager click tracker would capture, which is why §6.4/§13 make
  URL redaction a hard requirement rather than a nice-to-have.
- **Staff monitoring is not the goal.** A merchant's cashier is an employee of
  the merchant, not of Chmaba. Per-user click data is for product diagnosis, not
  performance scoring; exports exclude shopper PII and are platform-admin only.

Practical obligations that make the position defensible: disclose it in the
privacy policy in plain language ("we record how the product is used so we can
fix it"), keep raw data 90 days, honour deletion, restrict access, and never
sell or share it. If we later add session replay, that is the one feature that
needs an explicit notice because it is qualitatively different from a click
count.

| Rule | Implementation |
|---|---|
| No secrets in events | Server-side key allowlist; drop `password`, `token`, `authorization`, `card`, `qr_string`, `aba_payway_link`, `phone`, `email` |
| URLs are sanitized | Strip query + hash on `/reset-password`, `/login`, `/order/*`, and any `#access_token=`; keep only `utm_*` from a fixed list |
| Tokens never leak | Verification/reset links carry `?token=`; the SDK must not read `location.search` on those routes. Redact before `page.viewed`. |
| IP | Salted hash (per-deployment salt in `config`), never raw; retention 90 days |
| Deletion | Merchant account deletion + `DELETE /admin/users/{id}/telemetry` purge by `user_id`/`anonymous_id`; document in the privacy page |
| Retention | Raw 90 days, rollups 24 months, replay 30 days |
| Access | Platform-admin only; every read endpoint audited in `AuditLog` |
| Consent | First-party product telemetry disclosed in the privacy policy; no ad/third-party pixels; storefront shoppers get the same treatment (no cross-site identity) |
| Internal users | `platform_role` set → `is_internal=true`, excluded from all funnel queries |

Cambodia's PDPA and the app's own privacy page both require a lawful basis and a
deletion path. Because this is first-party, non-advertising, and minimised, the
practical requirements are disclosure + retention + erasure, all covered above.

---

## 14. Volume, cost, performance

Assumptions (deliberately conservative): 2,000 monthly active merchant users,
1,500 sessions/day, 120 events/session after sampling.

- **Events:** ~180k/day, ~5.4M/month, ~16M in the 90-day window.
- **Clicks, unsampled:** ~150 meaningful clicks/session × 1,500 sessions/day ≈
  225k clicks/day, ~6.8M/month. This is why 1.0 sampling on merchant routes is
  affordable: the total is ~400k rows/day, well inside a single Postgres
  instance with partitioned inserts.
- **Storage:** ~0.5–1 KB/row → 8–16 GB raw, plus indexes. Comfortable for the
  existing Postgres instance; check disk headroom before Phase 3.
- **Write path:** one batched `INSERT … VALUES` per request (20 events). The
  collector should sustain 50 req/s on a single worker.
- **Client cost:** < 2 ms main-thread per event, < 8 KB gzip, no blocking
  network on navigation (`keepalive`/beacon).
- **Query cost:** funnel from rollups; raw table only for timelines and
  drilldowns with `LIMIT`.

If volume is 10× the estimate, the answer is sampling (already in the registry)
and moving raw events to ClickHouse/Timescale — not redesigning the funnel.

---

## 15. Delivery plan

One branch / one PR per phase, green CI as the gate (`AGENTS.md`). Estimates
assume one engineer; parallelizing phases 1 and 2 is safe.

### Phase 0 — Measurement design (2–3 days)

- Branch: `docs/onboarding-activation-analytics-plan`
- Deliverable: this document + `docs/analytics-event-taxonomy.md` (registry
  table, owner, sample, PII class) + baseline numbers from existing tables.
- Baseline SQL (run now, before any code): cohort sizes for the current 5-stage
  funnel, with a true cohort definition, so we have a "before" number.
- Exit criteria: product + engineering agree on S0–S19, the 25 must-have events,
  and the retention/privacy rules.

### Phase 1 — Collector and schema (3–5 days)

- Branch: `feat/analytics-collector`
- Files: `models.py` (`AnalyticsSession`, `AnalyticsEvent`, `AnalyticsDailyRollup`),
  one Alembic revision chained to the current single head
  (`alembic heads` must show exactly one), `app/analytics.py`,
  `app/analytics_registry.py`, `app/api/telemetry.py`, `main.py` router include.
- `POST /telemetry/events` with validation, sanitization, rate limit, dedupe.
- `ensure_partitions()` worker + nightly rollup job (reuse the health-worker
  loop pattern in `main.py`).
- Tests: valid batch, oversized payload, unknown event dropped, PII stripped,
  cross-tenant `company_id` ignored, invalid token → anonymous, duplicate
  `event_id` ignored.
- Exit criteria: curl a batch, see rows; funnel endpoint returns raw counts.

### Phase 2 — Canonical funnel endpoint (2–3 days)

- Branch: `feat/analytics-funnel-api`
- `GET /admin/journeys/funnel` cohort-based, from server events; keep the old
  `/admin/funnel` untouched until the new one is trusted, then deprecate it.
- Backfill: derive S3/S6/S7/S12/S14/S15/S18 from existing rows at query time
  (not stored events) so the first chart is useful on day one.
- Tests: cohort semantics, stage monotonicity (no stage > previous), window
  boundaries, admin-only.
- Exit criteria: numbers reconcile with `PlatformActivity` within 1%.

### Phase 3 — Web SDK + step instrumentation (4–6 days)

- Branch: `feat/analytics-web-sdk`
- `apps/web/src/lib/analytics.js` + tests (pure batching, sampling, sanitizer).
- Wire `App.jsx` (screen/page, identify, global errors), auth, onboarding,
  catalog, settings (KHQR), sales, team/coach, help/support, QR.
- Add `data-track` attributes to the funnel controls.
- Feature flag `VITE_ANALYTICS_ENABLED`; default on in prod, off in tests
  unless a test opts in.
- Tests: `node --test` for the SDK; Playwright asserts the onboarding events
  fire (mock the endpoint) and that no event contains a token/password field.
- Exit criteria: manual signup → setup → product → sale produces a complete
  timeline in the admin drawer.

### Phase 4 — Journeys admin page (5–7 days)

- Branch: `feat/admin-journeys`
- Backend: `/admin/journeys/stage/{stage}`, `/sessions`, `/sessions/{id}`,
  `/why`, `/health`.
- Frontend: new page, drilldown drawer, session timeline, cohort heatmap,
  `AdminPageHeader`, nav entry.
- Tests: endpoint contracts (pytest), admin routing (`ADMIN_PAGES`), component
  smoke via the existing admin build.
- Exit criteria: an engineer can answer all 25 questions in §3 without SQL.

### Phase 5 — Storefront + mobile milestones (2–3 days)

- Branch: `feat/analytics-storefront-mobile`
- Storefront shopper funnel; Android/iOS milestone events through the API.
- Exit criteria: source breakdown works; mobile activation is measurable.

### Phase 6 — Qualitative layer (3–5 days, replay extra)

- Branch: `feat/analytics-abandon-survey` then `feat/support-intent-tags`
- Exit criteria: "Why" panel shows survey answers + support themes per stage.

### Phase 7 — Alerts and ritual (1–2 days)

- Branch: `feat/analytics-alerts`
- Daily digest to the ops chat, anomaly thresholds, a weekly activation review
  doc template.

### Total

~20–30 engineering days for phases 0–5, plus 3–10 for qualitative/replay.
The first *useful* chart (cohort funnel) lands on day ~7.

---

## 16. What we will probably find (and should pre-plan fixes for)

These are hypotheses from reading the code, not conclusions. The instrument
should confirm or kill each one.

1. **The verification wall is the biggest leak.** Login is hard-blocked until
   `is_email_verified` (`v1.py::login`), and the app also issues a 6-digit code
   *and* a link. Merchants who sign up on a phone, then open email on a
   desktop, land in a "confirm your email" loop with no "I confirmed on another
   device" affordance. **Fix candidate:** a "I've confirmed" button that calls
   `/auth/me` and auto-signs-in when verified; show the code on the same screen
   as the link; surface the dev-friendly "open mail app" deep link.
2. **Onboarding asks for a plan before showing value.** Free → workspace is
   one click, but a paid recommendation sends the merchant to a payment page
   *before they have ever seen the POS*. **Fix candidate:** default the
   recommendation to Free during setup, upsell after the first sale; or let
   paid plans "start trial without payment".
3. **`POST /workspaces/setup` fails on edge inputs.** Currency is restricted to
   seeded `Currency` rows; a country/currency mismatch or an unsupported
   currency returns a 400 with a detail the UI shows as a red paragraph. **Fix
   candidate:** pre-validate client-side from `/currencies`, and make the error
   field-specific.
4. **The product form is too big for a first product.** ~20 labelled fields,
   plus variants/serials/batches/suppliers. **Fix candidate:** a "quick add"
   (name, price, stock) that opens the full form after save; measure with
   `product.create_field_edited`.
5. **The workspace shell is heavy on first load.** Many parallel requests
   (`workspace.jsx` + `team.jsx` loaders). A slow first paint reads as "it's
   broken". **Fix candidate:** skeleton + a single `/workspaces/bootstrap`
   endpoint; measure `workspace_loaded` vs `workspace.created` gap.
6. **KHQR setup is the hardest non-selling task.** It needs an ABA PayWay link,
   verification, and a test scan. **Fix candidate:** a guided 3-step wizard with
   "where do I find this link?" screenshots, and a "skip for now" that the coach
   revisits after the first cash sale.
7. **The coach competes with the POS.** It is fixed bottom-left, 300 px, over
   the register on small screens. **Fix candidate:** collapse to a pill inside
   the POS view; measure `coach.dismissed` vs completion.
8. **Language and device gaps.** Khmer users on low-end Android phones may hit
   slower routes and longer forms. Break every stage down by `locale` and
   `device_type` from day one, or we will "fix" the wrong segment.

Each fix becomes a small PR with a before/after cohort chart in the description.

---

## 17. Working agreement for the data

- **One definition per metric.** The funnel definition lives in code
  (`analytics_registry` / `admin/journeys`), not in a dashboard tool.
- **No metric without an owner and a decision.** Every chart on the page must
  answer a question in §3; delete the rest.
- **Trust is earned.** Run the new funnel in parallel with the old
  `/admin/funnel` for two weeks and reconcile before removing the old one.
- **Every experiment states the stage it targets and the expected delta.**
- **Weekly ritual (30 min):** look at the cohort heatmap, pick the single
  largest drop, read 3 session timelines + survey answers, write one hypothesis,
  ship one fix.

Targets (set after 2 weeks of baseline, not before):

| Metric | Baseline | 90-day target |
|---|---|---|
| signup → email verified (24 h) | measure | +10 pp |
| verified → workspace created | measure | +15 pp |
| workspace → first product (24 h) | measure | +15 pp |
| median time to first sale | measure | −40% |
| 7-day activation rate | measure | +10 pp |

---

## 18. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Event sprawl / nobody reads it | Registry + CI validation; cap at ~70 events; every chart tied to a question |
| Client events untrusted | Server events are authoritative; client events never counted in conversion |
| Analytics breaks a sale | `emit()` and the SDK never throw into product code; collector never returns 5xx that the POS handles |
| Ad blockers / offline | Server-side milestones + offline queue + beacon |
| PII leak | Allowlist, URL sanitizer, input masking, token-route blocklist, internal filter |
| Postgres write pressure | Batch inserts, monthly partitions, 90-day raw retention, sampling |
| Duplicate/out-of-order events | Client `event_id` + `occurred_at` clamp + `received_at` |
| Cross-tenant contamination | Server derives `company_id`/`store_id`; client values ignored |
| Cost of replay | Optional, sampled, masked, 30 days; buy before build |
| Team bandwidth vs 9-job CI | Phases are independently shippable; nothing blocks a release |

---

## 19. Open decisions (need a call before Phase 1)

1. **Replay:** none / PostHog Cloud / self-hosted PostHog / rrweb build. This is
   the only decision that changes the architecture.
2. **Consent:** is first-party telemetry disclosed-only (recommended) or opt-in
   for merchants? Affects ingest defaults.
3. **Mobile scope:** milestones only (recommended) or full autocapture in
   Android/iOS.
4. **Free-text survey:** allow a 280-char "other" answer (recommended) or
   fixed options only.
5. **Retention:** 90 days raw / 24 months rollups (recommended) vs longer.
6. **Who owns the weekly review:** product or support lead.

---

## 20. Appendix

### A. Baseline cohort SQL (run today, before instrumentation)

```sql
WITH cohort AS (
  SELECT id, created_at
  FROM users
  WHERE created_at >= now() - interval '30 days'
    AND platform_role IS NULL
),
verified AS (
  SELECT c.id FROM cohort c JOIN users u ON u.id = c.id
  WHERE u.is_email_verified
),
workspace AS (
  SELECT DISTINCT c.id
  FROM cohort c
  JOIN memberships m ON m.user_id = c.id
  JOIN companies co ON co.id = m.company_id
),
product AS (
  SELECT DISTINCT c.id
  FROM cohort c
  JOIN memberships m ON m.user_id = c.id
  JOIN products p ON p.company_id = m.company_id AND p.is_sample = false
),
sale AS (
  SELECT DISTINCT c.id
  FROM cohort c
  JOIN memberships m ON m.user_id = c.id
  JOIN stores s ON s.company_id = m.company_id
  JOIN orders o ON o.store_id = s.id AND o.status = 'paid'
)
SELECT
  (SELECT count(*) FROM cohort)    AS signups,
  (SELECT count(*) FROM verified)  AS verified,
  (SELECT count(*) FROM workspace) AS workspace,
  (SELECT count(*) FROM product)   AS first_product,
  (SELECT count(*) FROM sale)      AS first_sale;
```

This corrects the current per-stage denominators and gives the "before" number
for every later comparison.

### B. Event registry example (client)

```js
// apps/web/src/lib/analyticsEvents.js (generated from the Python registry)
export const EVENTS = {
  "onboarding.step_completed": {
    version: 1,
    props: { step: "number", step_key: "string", duration_ms: "number", back_count: "number" },
  },
  "payments.khqr_verify_failed": {
    version: 1,
    props: { reason: "string" },
  },
};
```

### C. SDK call sites (diff sketch)

```jsx
// features/onboarding.jsx
useEffect(() => { analytics.startStep(`onboarding.${step}`); }, [step]);
const next = () => { analytics.endStep(`onboarding.${step}`, { outcome: "completed" }); setStep(step + 1); };

// features/settings.jsx (BankKhqrPane)
analytics.track("payments.khqr_verify_failed", { reason: normalizeError(err) });
```

### D. Admin endpoint → question map

| Endpoint | Answers |
|---|---|
| `/journeys/funnel` | Q1, Q5, Q9, Q14, Q18, Q25 |
| `/journeys/funnel/stage/{stage}?breakdown=` | Q2, Q3, Q10, Q15, Q19, Q24 |
| `/journeys/sessions?outcome=dropped` | Q6, Q7, Q11, Q16, Q20 |
| `/journeys/sessions/{id}` | Q6, Q7, Q11, Q21 |
| `/journeys/why` | Q3, Q12, Q15, Q22, Q23, Q25 |
| `/journeys/health` | data-quality guardrails |

### E. Known pitfalls to test for explicitly

- A verification link opened in a new browser: `anonymous_id` differs, but the
  token resolves `user_id` server-side. The funnel must still join to the right
  user.
- The Google OAuth fragment (`#access_token=…`) is stripped before any event is
  read/written.
- A user who signs up, verifies, and never logs in is *not* a workspace
  dropout; it is a login dropout. Keep S6 → S7 separate.
- A merchant invited into an existing workspace never has a `workspace.created`
  event. Activation must be counted per **company**, then attributed to the
  owner, or invited staff will poison the denominator.
- The sample products (`is_sample=true`) must never count as `first_product`.
- A refunded/voided first sale should still count as activation, but a *voided
  before payment* order must not.
