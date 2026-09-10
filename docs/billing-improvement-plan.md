# Billing improvement plan

Status: **partially implemented**. Phase 0 and Phase 1 have landed on
`feat/billing-correctness`; Phases 2–4 remain proposals. This document captures
the full external review of Chmaba's billing model and turns it into an
actionable, code-grounded plan. `docs/billing-model.md` is the current source of
truth and is updated as each item lands.

Review rating of the current design: **8.5 / 10**. The architecture is sound;
the work now is making state transitions and recovery behavior bulletproof, not
redesigning from scratch.

---

## 1. Guiding principle

Treat billing as an **entitlement system**, not a payment record. A workspace's
abilities must always be derived from one resolver, never from scattered flags.

The current `app/billing.py::load_entitlement()` is the right shape and should
stay the single entry point. Everything below preserves that.

---

## 2. Target architecture

Four separate concepts, with entitlement largely derived rather than stored:

```
                    ┌─────────────┐
                    │    PLAN     │   "What did Chmaba sell?"
                    └──────┬──────┘
                           │
                           ▼
                 ┌──────────────────┐
                 │   SUBSCRIPTION   │   "Which plan, for what period?"
                 │  plan_code       │
                 │  starts_at       │
                 │  ends_at         │
                 │  scheduled_plan  │
                 └────────┬─────────┘
                          │ checkout
                          ▼
                 ┌──────────────────┐
                 │ BILLING PAYMENT  │   "Did they actually pay?"
                 │  amount          │   (immutable once paid)
                 │  currency        │
                 │  provider_ref    │
                 │  status          │
                 └────────┬─────────┘
                          │ payment confirmed
                          ▼
                ┌────────────────────┐
                │ FULFILLMENT ENGINE │   idempotent + transactional
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │    ENTITLEMENT     │   "What can they do right now?"
                │  stores            │   (derived, not stored)
                │  members           │
                │  transactions      │
                │  capabilities      │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │ CAPACITY ENFORCER  │   pause / restore / keep-list
                └────────────────────┘
```

Mapping to today's code:

| Concept | Today | Notes |
| --- | --- | --- |
| Plan | `Plan` model (`app/models.py:152`) | Has `monthly_price`, `max_stores`, `max_members`, `transaction_limit`, `capabilities`. Keep. |
| Subscription | `Subscription` model (`app/models.py:166`) | Currently carries scheduled change, keep-lists **and** paused snapshots. Split concerns (see §4.2). |
| BillingPayment | `BillingPayment` model (`app/models.py:402`) | Mutable today (status rewritten by webhook). Make immutable once paid (see §3.1). |
| Entitlement | `Entitlement` dataclass (`app/billing.py:53`) | Already derived. Keep as the only gate. |
| Fulfillment | `fulfill_billing_payment()` (`app/api/v1.py:1790`) | Needs hardening + extraction (see §3.2). |
| Capacity Enforcer | `app/services/billing_lifecycle.py` | Works, but has no audit trail (see §4.4). |

---

## 3. The seven must-do improvements

These are the changes to land before calling billing production-ready.

### 3.1 Make payment records immutable and auditable

**Problem.** `BillingPayment` rows are rewritten in place by the webhook
(`app/api/v1.py:1912` sets `status = provider_status`). Billing history must not
depend on the current subscription or on mutable rows.

**Rule.** Once a payment succeeds, never rewrite history. If the customer paid
$4.99 and the price later changes to $7, the old payment must still say $4.99
forever.

**Target schema (append-only `billing_payments`).**

| Column | Purpose |
| --- | --- |
| `id` | PK |
| `subscription_id` | Which subscription it fulfills |
| `company_id` | Denormalized for audit/queries |
| `provider` | `cutluy` today; `card`, `paddle`, `bank` later |
| `provider_payment_id` | Provider's immutable id (unique) |
| `reference_id` | Our checkout reference (unique) |
| `amount` | Charged amount, frozen at creation |
| `currency_code` | Charged currency, frozen at creation |
| `status` | `pending` → `paid` / `failed` / `expired`; terminal states never rewritten |
| `plan_code` | Plan purchased at time of payment (snapshot) |
| `billing_cycle` | Cycle purchased at time of payment (snapshot) |
| `period_start` / `period_end` | Period this payment bought (snapshot) |
| `created_at` / `paid_at` | Timestamps |
| `provider_metadata` | Raw provider payload (JSON) |

**Acceptance criteria**
- A paid row is never mutated except for a one-way `pending → terminal`
  transition; terminal rows are frozen.
- A payment records the plan/cycle/amount it bought even if `Plan` changes later.
- `GET /billing/payments` returns immutable history ordered by `created_at`.

**Tests**
- Pay → change plan price → old payment still returns the original amount.
- Replayed webhook does not alter a paid row's amount/plan/cycle.

---

### 3.2 Make fulfillment completely idempotent

**Problem.** `fulfill_billing_payment()` (`app/api/v1.py:1790`) already guards
with `if subscription.status != "pending": return True`, and the webhook path
plus `POST /mock/cutluy/{id}/complete` plus (future) polling can all call it. The
guard works only because the subscription row is locked with
`with_for_update()`; this must be explicit and constraint-backed, not incidental.

**Rule.** The same payment arriving via webhook + webhook + poll must activate
exactly once.

**Target design**
- Fulfillment keyed by an immutable provider payment/transaction reference with a
  **unique constraint** at the DB level.
- Wrap fulfillment in a single transaction; on conflict, return success without
  re-applying side effects (extend period, pause/restore).
- Introduce a `billing_fulfillments` ledger (or a unique
  `billing_payments.fulfilled_at` guard) recording that a payment has been
  fulfilled, so double-processing is provably impossible even if the
  subscription state check is bypassed.
- Both webhook and polling must funnel into the same function; mock is just
  another caller (see §3.2.1).

**Acceptance criteria**
- Calling fulfillment N times for one payment produces one activation and one
  period extension.
- Server restart mid-job cannot double-extend or double-provision.

**Tests**
- Deliver the same `paid` webhook three times → one active subscription, one
  extension.
- Deliver webhook then mock-complete for the same payment → one activation.

#### 3.2.1 Provider-agnostic ingestion

KHQR/CutLuy is one provider, not the billing engine. Structure ingestion as:

```
                 Chmaba Billing
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
        KHQR         Card        Paddle
       CutLuy       Provider      etc.
          │            │            │
          └────────────┼────────────┘
                       ▼
                Fulfillment Engine   (idempotent)
                       ▼
                   Entitlement
```

- `fulfill_billing_payment()` must not import or assume CutLuy specifics beyond
  the normalized fields it already receives.
- A provider adapter normalizes `(provider, provider_payment_id, reference_id,
  amount, currency, status, approved_at)` into the fulfillment call.
- Today's provider is hard-coded to `cutluy` (`app/api/v1.py:1596`,
  `app/models.py:407`). Replace with a provider registry / adapter interface so
  Visa/Mastercard/Paddle/bank rails can feed the same engine without touching
  subscription logic.

**Acceptance criteria**
- Adding a second provider requires no changes to subscription/entitlement logic,
  only a new adapter + config.
- Provider is stored per payment; entitlement is provider-agnostic.

---

### 3.3 Add receipt / invoice records

**Problem.** There is no customer-facing receipt object. Payments exist, but the
customer cannot see "Receipt #CHM-2026-000182".

**Target: `BillingReceipt`.**

| Column | Purpose |
| --- | --- |
| `id` | PK |
| `receipt_number` | Human, sequential, e.g. `CHM-2026-000182` |
| `company_id` | Customer |
| `subscription_id` / `billing_payment_id` | Links |
| `plan_code` | Plan purchased |
| `billing_period_start` / `billing_period_end` | Period covered |
| `amount` / `currency_code` | Charged |
| `provider` | KHQR/CutLuy, card, etc. |
| `paid_at` | Payment time |
| `created_at` | Issue time |

**Rule.** A receipt is created **after successful payment** and is immutable.

**Customer-facing shape**
```
Receipt #CHM-2026-000182
Starter
Sep 10 – Oct 10
$5.00
KHQR
Paid
```

**Acceptance criteria**
- Every paid `BillingPayment` has exactly one receipt.
- Receipt numbers are unique and monotonic per year.
- The Billing page lists receipts (read-only, downloadable/printable later).

**Tests**
- Fulfilling a payment creates exactly one receipt (idempotent with §3.2).
- Receipt amount/period match the payment snapshot, not the current plan.

---

### 3.4 Track capacity pause/restore explicitly and reversibly

**Problem.** Paused stores/members are stored as JSON arrays
(`Subscription.paused_store_ids` / `paused_member_ids`,
`app/models.py:180-181`) and mutated by
`app/services/billing_lifecycle.py`. There is no independent audit trail of who
was paused, why, and when they were restored.

**Rule.** Never delete resources. Pause them, record the action, and make it
reversible.

**Target: `SubscriptionCapacityAction`.**

| Column | Purpose |
| --- | --- |
| `id` | PK |
| `subscription_id` | Subscription whose limits forced the action |
| `company_id` | Customer |
| `resource_type` | `store` \| `member` |
| `resource_id` | The store/membership id |
| `action` | `pause` \| `restore` |
| `reason` | e.g. `downgrade`, `expiry`, `upgrade`, `manual` |
| `created_at` | When |
| `restored_at` | When reversed (null if still paused) |

**Acceptance criteria**
- Every forced pause/restore writes a row.
- The current paused set is reconstructable from the audit table (JSON snapshot
  becomes a cache/optimization, not the source of truth).
- Restoring is exact: only items this subscription paused come back.

**Tests**
- Expiry pauses stores/members → one `pause` row each with `reason=expiry`.
- Re-pay restores them → matching `restore` rows, `restored_at` set.
- Manual keep-list swap produces `pause` + `restore` rows.

---

### 3.5 Prioritize user keep-lists before automatic activity ranking

**Problem.** Selection is currently "most recently active first" with an owner
preference (`billing_lifecycle.py:63-121`). Chmaba decides for the merchant.

**Target hierarchy (highest priority first)**
1. Owner's store/workspace → always retained.
2. User-selected keep list (`keep_store_ids` / `keep_member_ids`).
3. Most recently active.
4. Everything else → paused.

**Rule.** The merchant should know exactly what will happen before it happens.

**UI sketch**
```
Your Free plan allows 1 store.

Keep active
☑ Phnom Penh Main Store
☐ Siem Reap Store
☐ Warehouse
☐ Kampot Store
```

**Acceptance criteria**
- Keep-lists are honoured exactly, then remaining capacity is filled by activity.
- The schedule confirmation and the expiry warning both show which items will be
  paused.
- Default selection (when the user does not choose) is still activity-ranked.

**Tests**
- Keep-list chosen → exactly those kept (within plan limit).
- No keep-list → most-recently-active kept (existing behavior preserved).

---

### 3.6 Add a grace period (24–72 hours)

**Problem.** A plan that expires at 23:59 makes the store disappear the next
morning if the merchant forgot to pay — a bad POS experience.

**Target**
```
Sep 10   Plan expires
Sep 10–12 Grace period (limited warnings)
Sep 13   Free fallback
```

- Configurable, e.g. `billing_grace_hours` (default 48).
- During grace, the workspace keeps its paid entitlements (optionally blocking
  only *new* paid-feature creation if desired).
- The renewal QR remains payable during grace; a payment inside grace reactivates
  from the payment date with no gap.
- After grace, existing Free-fallback behavior applies.

**Acceptance criteria**
- `is_in_force()` / expiry job respect the grace window.
- A payment during grace restores the paid plan without a Free interval.
- Grace is visible in the UI ("Your Pro plan expired Oct 14; renew within 2 days
  to avoid pausing 3 stores").

**Tests**
- Subscription just past `ends_at` is still entitled during grace, Free after.
- Payment during grace does not create a Free fallback first.

---

### 3.7 Use calendar-month periods instead of fixed 30-day cycles

**Problem.** Current cycles are fixed day counts:
`{"monthly": 30, "semi_annual": 182, "annual": 365}` (`app/api/v1.py:1807`).
Customers understand "one calendar month", not "30 days".

**Target**
- Monthly: `Jan 10 → Feb 10`, `Feb 10 → Mar 10` (clamp day-of-month for short
  months).
- Annual: `Jan 10 2026 → Jan 10 2027`.
- Keep fixed-day cycles only if deliberately chosen; if so, state it explicitly
  in Terms/UI.

**Rule.** Compute period boundaries with a calendar helper, not
`timedelta(days=30)`.

**Acceptance criteria**
- Monthly renewal on Jan 31 clamps to Feb 28/29 and the following period returns
  to the 28th/29th or the intended anchor.
- Reminder dates and `ends_at` display match customer expectations.

**Tests**
- Month-end renewal boundaries.
- Annual period lands on the same calendar date next year.

---

## 4. Additional required work (from the review)

### 4.1 Separate the four concepts in the schema

Reduce `Subscription`'s responsibilities:

| Field today | Belongs to | Change |
| --- | --- | --- |
| `plan_code`, `status`, `starts_at`, `ends_at` | Subscription | Keep |
| `scheduled_plan_code` | Subscription (scheduled change) | Rename semantics to **scheduled plan change**, not "downgrade" |
| `scheduled_store_ids` / `scheduled_member_ids` | Scheduled change | Keep but treat generically |
| `paused_store_ids` / `paused_member_ids` | Capacity actions | Migrate to `SubscriptionCapacityAction` (§3.4) |
| — | BillingPayment | Immutable snapshot fields (§3.1) |
| — | Entitlement | Keep derived |

### 4.2 Model scheduled changes generically, not as "downgrade"

**Problem.** `PUT/DELETE /billing/schedule` (`app/api/v1.py:1506`, `1547`) and
`schedule_plan_change()` assume the scheduled change is always a downgrade
(`target.monthly_price >= ent.plan.monthly_price` is rejected,
`app/api/v1.py:1515`).

**Target.** Support every transition:
`Pro → Starter`, `Pro → Free`, `Starter → Free`, `Starter → Pro`, and
`Pro → Pro` (billing changes).

- Model `scheduled_plan_code` + `scheduled_effective_at` (currently effective
  time is implicitly `ends_at`).
- Rename UI/copy from "downgrade" to **"scheduled plan change"**.
- Keep the rule that a paid upgrade is immediate (money wins), but a scheduled
  change is the general mechanism.

**Acceptance criteria**
- Any plan→plan schedule is representable; validation reflects business rules
  (e.g. upgrade is checkout, not schedule) without hard-coding "downgrade".
- The reminder/invoice references the scheduled target plan.

### 4.3 Clarify downgrade UI copy

Scheduled downgrade must be explicit to eliminate confusion:
```
Your Pro plan remains active until September 30.
Starter will begin automatically on October 1.
You won't be charged until you complete payment.
```
And for cancel-to-Free:
```
No refunds. QR payments are non-refundable.
Your plan is fully usable until {date}; the change applies then.
```

### 4.4 Derive prices from a single canonical monthly price

**Problem.** `Plan.monthly_price` exists, but cycle discounts are re-derived in
multiple places (`app/api/v1.py:1584-1591`, `app/services/reminders.py:37-40`)
and could drift.

**Target**
```
monthly      = monthly_price
semi_annual  = monthly_price × 6 × 0.85
annual       = monthly_price × 12 × 0.80
```
- One shared pricing helper used by checkout, reminders, and receipts.
- Store the **actual charged amount** on the checkout/payment record (already
  partially done) so later price changes never rewrite history.

Current seed prices (`scripts/seed.py:22-50`): free `$0.00`, starter `$0.99`,
pro `$4.99` monthly.

**Acceptance criteria**
- Checkout, reminder, and receipt amounts are computed by the same function.
- Changing `monthly_price` affects only new checkouts.

### 4.5 Refund records (even though refunds are rare)

**Problem.** Policy is prepaid / non-refundable, but the schema has no concept of
a correction.

**Target.** Distinguish:
- **Customer cancellation** → no automatic refund.
- **Genuine billing error** → support may issue refund/credit.

Add a `BillingRefund` concept:
`payment_id`, `amount`, `reason`, `refunded_at`, `refunded_by`, `provider_ref`.

**Acceptance criteria**
- Accounting can correct an error without deleting/mutating the original payment.
- Refunds never silently change entitlement unless explicitly applied.

### 4.6 Owner vs workspace vs stores vs staff

**Problem.** "owners always stay active" is right for membership, but must not
imply the owner's 20 stores all stay active.

**Rule.** Explicitly separate:
- **Owner account** → always accessible regardless of subscription.
- **Workspace** → remains accessible (read/export) on Free.
- **Stores** → subject to plan capacity.
- **Staff members** → subject to plan capacity.

Free fallback keeps the owner login working; it does not keep every store
sellable.

### 4.7 Strengthen payment matching

**Problem.** The webhook checks amount/currency equality only
(`app/api/v1.py:1909`).

**Target.** Match on:
- `provider`
- merchant/account (when the provider supplies it)
- payment reference
- amount
- currency
- status

And associate each payment with a **specific pending subscription/checkout**.
Never activate merely because "we received $5" — it must be the exact payment for
that checkout.

**Acceptance criteria**
- A payment with no matching pending checkout is logged for admin review, not
  fulfilled.
- Amount/currency mismatch is rejected (existing) and surfaced in admin.

### 4.8 Reminder improvements

Current: `-7 / -3 / -1` (`app/services/reminders.py:24`), once per
`(subscription, days_before)`.

Add:
- **Expiration day**: "Your Pro plan expires today."
- **After expiry**: "Your Pro plan has expired. Your workspace is still available
  on Free."
- **Capacity warning** (before expiry): "Your Free plan supports 1 store. If you
  don't renew, 4 stores will be paused." This is the most important addition.

**Acceptance criteria**
- Capacity warning lists the actual stores/members that will be paused.
- Each new reminder type fires at most once, recorded in `billing_reminders`.

### 4.9 Free fallback messaging

The owner must land in a working Free workspace with a clear, reassuring banner:
```
Your Pro plan expired Oct 14.

3 stores are paused
4 staff members are paused

Your data is safe.
Upgrade to restore them.
```
"Your data is safe." is mandatory copy — it reduces panic and support load.

---

## 5. Billing UX to build

> **Illustrative only.** The mockups below use placeholder values (`$19`,
> `10 stores`, `20 members`, `3 stores paused`, `Oct 14`, …). None of these are
> hardcoded. Every value is rendered from live data:
>
> - plan name, price and limits → the `Plan` row (`GET /plans`),
> - "Active until" → `Subscription.ends_at` (grace-adjusted when §3.6 lands),
> - "Scheduled … / Starts …" → `scheduled_plan_code` + effective date,
> - paused counts → `SubscriptionCapacityAction` / the paused set (§3.4),
> - capability checkmarks → `Plan.capabilities` via `features.py`.
>
> These numbers do not match current seed data (pro is `$4.99`, 50 stores, 99
> members — `scripts/seed.py:41-49`), which is the point: the UI must never
> hardcode plan values.

**Active plan**
```
┌──────────────────────────────────────┐
│ PRO                                  │
│ $19 / month                          │
│                                      │
│ Active until Oct 14, 2026            │
│                                      │
│ ✓ 10 stores                          │
│ ✓ 20 members                         │
│ ✓ Unlimited transactions             │
│                                      │
│ [ Renew Pro ]                        │
└──────────────────────────────────────┘
```

**Scheduled change**
```
┌──────────────────────────────────────┐
│ PRO                                  │
│ Active until Oct 14                  │
│                                      │
│ Scheduled: STARTER                   │
│ Starts Oct 15                        │
│                                      │
│ [ Keep Pro ] [ Change plan ]         │
└──────────────────────────────────────┘
```

**Expired / Free**
```
┌──────────────────────────────────────┐
│ FREE                                 │
│                                      │
│ Your Pro plan expired Oct 14.        │
│                                      │
│ 3 stores are paused                  │
│ 4 staff members are paused           │
│                                      │
│ Your data is safe.                   │
│ Upgrade to restore them.             │
│                                      │
│ [ Upgrade ]                          │
└──────────────────────────────────────┘
```

Frontend touch points: `apps/web/src/features/team.jsx` (`LiveBillingView`,
`PlanScheduleModal`), `apps/web/src/features/workspace.jsx`
(`PaymentRequiredView`, billing handlers), `apps/web/src/features/settings.jsx`
(workspace overview rows), `apps/web/src/features/onboarding.jsx` (plan picker).

---

## 6. Phased rollout

Ordered to de-risk the highest-severity issues first.

### Phase 0 — Guardrails and docs  ✅ landed
- Freeze this plan; align `docs/billing-model.md` with it as items land.
- Add a pricing helper and route checkout + reminders + receipts through it
  (§4.4). **Done:** `app/services/pricing.py`; checkout and reminders now use it.
- Add integration tests that replay webhooks and run jobs twice (§3.2, §3.4).
  **Done:** `tests/test_billing_immutability.py`.

### Phase 1 — Correctness (must-have before production)  ✅ landed
1. Immutable `BillingPayment` snapshots + terminal-state freeze (§3.1).
   **Done:** snapshot columns + `fulfilled_at`; webhook freezes terminal status.
2. Explicit idempotent fulfillment ledger (§3.2). **Done:** row-locked
   `fulfilled_at` guard + `(provider, external_id)` unique constraint.
3. `SubscriptionCapacityAction` audit trail; JSON snapshots become cache (§3.4).
   **Done:** `subscription_capacity_actions` written on every pause/restore.
4. Idempotency tests for expiry job and fulfillment. **Done:** replay/re-run
   regression tests in `tests/test_billing_immutability.py`.

Migration `c3d4e5f6a7b8` carries the Phase 1 schema changes.

### Phase 2 — Customer trust
5. `BillingReceipt` + Billing-page receipt list (§3.3).
6. Keep-list priority hierarchy + pre-expiry capacity warning UI (§3.5, §4.8).
7. Explicit scheduled-change UI copy (§4.3).

### Phase 3 — Policy and periods
8. Grace period (§3.6).
9. Calendar-month / calendar-year periods (§3.7).
10. Refund records (§4.5).
11. Reminder additions: expiry day, after-expiry, capacity warning (§4.8).

### Phase 4 — Provider abstraction
12. Provider adapter/registry; stop hard-coding `cutluy` (§3.2.1).
13. Scheduled plan changes generalized beyond downgrade (§4.2).

---

## 7. Open questions / decisions needed

1. **Grace period length**: 24h, 48h, or 72h? Configurable default?
2. **Grace semantics**: full paid access, or read-only + no new paid features?
3. **Calendar periods**: adopt calendar-month, or intentionally keep fixed 30-day
   and document it in Terms?
4. **Receipt numbering**: global `CHM-YYYY-NNNNNN`, or per-company?
5. **Refunds**: which roles can issue? Any automatic path, or support-only?
6. **Provider abstraction timing**: build the adapter interface now, or when the
   second provider lands?
7. **Semi-annual**: keep 182-day fixed, or move to 6 calendar months?
8. **Pause semantics on Free**: does a paused store block sales entirely, or stay
   readable/reportable?
9. **Transaction quota**: resets per stacked prepaid period today — confirm this
   remains the desired behavior with calendar periods.

---

## 8. Explicitly keep (do not change)

These current decisions are strong and should survive the improvements:

- Prepaid KHQR subscriptions with manual renewal; no card on file.
- **Early same-plan renewal stacks** (pay mid-period → new cycle appended after
  `ends_at`), never resetting the current period.
- **Free fallback instead of account lockout**; data is never deleted.
- **Automatic restoration** of paused stores/members on re-pay.
- **Downgrade/cancel never immediate** — the paid period is always fully usable.
- A single entitlement resolver (`load_entitlement`) as the only gate.
- Non-refundable QR payments as policy (with a support correction path).

---

## 9. Source of truth

- Current spec: `docs/billing-model.md`.
- This plan: `docs/billing-improvement-plan.md`.
- Once an item lands, update `docs/billing-model.md` and remove the item from the
  relevant phase here.
