# Billing model

This document is the single source of truth for how Chmaba plans, upgrades,
downgrades, renewals and expiry behave. Code must match it.

## Core concept

Plans are sold as **prepaid periods**, not recurring subscriptions. There is no
card on file and no auto-rebill; KHQR/CutLuy payments are one-time transfers and
cannot be reversed or partially refunded.

A `Subscription` row with `status = "active"` represents paid time between
`starts_at` and `ends_at`. A workspace always has exactly one **effective plan**:

- its active paid subscription, while `ends_at` has not passed; otherwise
- the **Free** plan.

A single resolver derives the effective plan. Every gate (features, stores,
team, transactions), the workspace API and the admin dashboard use that
resolver — nothing reads a stale `status = "active"` row and ignores `ends_at`.

## Plans

- `free`   — 1 store, 1 member, 3000 tx/period, limited capabilities
- `starter`— 5 stores, 10 members, 15000 tx/period
- `pro`    — 50 stores, 99 members, 1,000,000 tx/period

Free subscriptions have no `ends_at` and never expire.

## Upgrade / re-upgrade / renewal (instant on payment)

- Free → Starter/Pro, Starter → Pro and renewals activate the moment money is
  received. The old period ends that day. There is **no credit or refund** for
  unused time on the previous plan; the checkout confirmation states this
  before the customer pays.
- **Early same-plan renewal is allowed and stacks.** Paying mid-period appends
  the new cycle after the current `ends_at` (a prepaid top-up). The transaction
  quota resets per stacked period.
- Paying while a downgrade/cancel is scheduled **clears the schedule** and its
  keep-lists (money wins).
- Re-upgrading after a fallback **auto-restores** paused stores and members up
  to the new plan's capacity, most-recently-active first; the owner can
  fine-tune afterwards.

### Payment flow guards

- Fulfilling any payment cancels all *other* pending subscriptions.
- Fulfillment is idempotent: a replayed/late webhook cannot double-extend.
- Amount/currency mismatch against the billing record is logged for admin
  review, never silently accepted.
- Checkout copy says "pay exactly {amount}".
- Card purchases go through **Paddle** as merchant of record: Paddle adds
  per-country tax on top of the quoted net price, so its webhook compares the
  net line subtotal (never gross) against the billing record. KHQR (CutLuy)
  payments keep the strict equality check because the QR encodes the exact
  amount. See `docs/paddle-integration.md`.

## Downgrade / cancel (scheduled, never instant, never refunded)

- Pro → Starter, Starter → Free and "cancel" are all one mechanism: **schedule a
  target plan** (`scheduled_plan_code`) on the active subscription, effective at
  `ends_at`.
- The current plan stays fully usable until `ends_at`. No charge is made when
  the change is scheduled.
- Confirmation copy: "No refunds. QR payments are non-refundable. Your plan is
  fully usable until {date}; the change applies then."
- At renewal time the reminder/invoice is for the **target plan's** amount
  (e.g. a Pro → Starter downgrade means renewing Starter, not Pro). Cancelling
  to Free means no renewal invoice is issued.
- When the downgraded plan starts (its renewal is paid, or the scheduled date
  arrives for a cancel):
  - capabilities lock to the target plan immediately;
  - stores beyond `max_stores` and members beyond `max_members` are **auto
    paused/revoked** — keep most-recently-active first, ties keep the oldest;
  - if the session's current store is paused, the app switches to a kept store;
  - at least one `owner` membership always stays active.
- After the change, the owner can **swap** which stores/members are active up to
  the plan's limit, but can never run more than the plan allows while on the
  lower plan (reactivation over the limit is blocked; upgrade first).

## Forgetting to pay / expiry

- At `ends_at` a daily job falls the workspace to **Free**: data is kept, extra
  stores are paused and staff members revoked (non-owner; **all owners stay
  active** so nobody is locked out), one store stays sellable under Free limits.
- Store/member selection is by activity: the **most recently used** store stays
  selling on Free; the exact force-paused stores and revoked members are
  recorded on the Free fallback subscription so a later payment restores
  precisely those.
- The owner logs into a working Free workspace (no lockout) with a clear banner:
  "Your {plan} ended {date}. You're on Free. Renew to restore {N} stores/team."
- No action is required to keep using Free.
- **Auto-restore on re-pay:** when a paid plan is next activated, force-paused
  stores and members return automatically up to the new plan's capacity
  (most-recently-active first); the owner can fine-tune afterwards.
- **Grace window:** a renewal QR stays payable for a short window (~its QR TTL,
  1–3 days) past `ends_at`; a payment inside the window reactivates the plan
  from the payment date. After the window a fresh checkout is required.
- Any unpaid pending checkout is user-cancellable ("Stay on Free / keep current
  plan") and auto-expires after its QR TTL. A pending checkout never traps a
  user on a paywall they cannot dismiss.

## Operations

- Run the daily expiry job once per day
  (`python chmabapos_api/scripts/run_billing_jobs.py`) from a scheduler
  (cron / systemd timer / equivalent). It is idempotent and safe to run more
  often. Each run: expires overdue paid subscriptions, provisions the Free
  fallback, pauses/revokes beyond Free capacity, and clears stale scheduled
  plan changes that were never paid.

## Reminders

In-app + email at **-7 / -3 / -1 days** before `ends_at`, addressed to all
owners, sent from `billing@chmaba.com` (SPF/DKIM/DMARC aligned, reply-to
`support@chmaba.com`). Reminders reference the scheduled/next plan's amount and
carry its renewal QR / checkout link.

## Legal

The Terms state plans are prepaid, renewals are manual, downgrades and
cancellations take effect at the end of the current period, and QR payments are
non-refundable.
