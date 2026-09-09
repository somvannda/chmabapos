# Paddle auto-renew (recurring) billing model

Chmaba can now sell the **same plans** two ways, and a workspace picks one at a
time — it never pays two providers for the same period:

| | Prepaid (default) | Paddle auto-renew (opt-in) |
| --- | --- | --- |
| Payment | KHQR (CutLuy) or one-time card via Paddle | Recurring card via Paddle |
| Renewal | Manual — owner pays each period | Automatic — Paddle bills the card |
| Downgrade / cancel | Scheduled in Chmaba, takes effect at `ends_at` | Managed in Paddle (customer portal), effective at period end |
| Stored where | `subscriptions` (unchanged) | `recurring_subscriptions` |
| Governing source | `load_entitlement` → prepaid in force | `load_entitlement` → Paddle row in force (takes precedence) |

Prepaid (KHQR + one-time card) billing is **untouched**. This document covers
only the recurring path; see `docs/billing-model.md` for the shared rules and
`docs/paddle-integration.md` for the Paddle one-time card channel.

## Data model

New table `recurring_subscriptions` mirrors Paddle subscription state and is
owned by webhook sync:

```
id, company_id, paddle_subscription_id (unique), paddle_customer_id, price_id,
plan_code, billing_cycle, status, starts_at, ends_at,
scheduled_action, scheduled_effective_at,        -- cancel/pause scheduled in Paddle
scheduled_store_ids, scheduled_member_ids,       -- (reserved, capacity)
paused_store_ids, paused_member_ids,             -- capacity snapshot while inactive
created_at, updated_at
```

`companies.paddle_customer_id` links the workspace to its Paddle customer.

## Entitlement — one effective plan

`load_entitlement` (`chmabapos_api/app/billing.py`) is the single resolver and
now considers both tables:

1. a `RecurringSubscription` that is **in force** (status `active`/`trialing`/
   `past_due` and `starts_at <= now < ends_at`) → its plan governs;
2. otherwise the in-force prepaid `Subscription` governs;
3. otherwise **Free**.

`Entitlement.recurring` is set when Paddle auto-renew governs and
`Entitlement.is_recurring` is the convenience flag every endpoint/UI uses. All
feature/store/team/transaction gates keep reading the same `plan` object.

## Switching models

* **Prepaid → auto-renew.** `POST /billing/recurring/checkout` returns a Paddle
  checkout URL (Payment Link for the recurring price). While prepaid time
  remains, the day the subscription activates the remaining prepaid period is
  **forfeited** (`_takeover_prepaid`) — the same no-credit rule as an upgrade.
  The Free fallback row is left in place and only governs again if the
  recurring plan later ends.
* **Auto-renew → prepaid.** Not directly: prepaid checkout and in-app
  downgrade/cancel are blocked (`409`/`400`) while Paddle governs. The owner
  cancels in Paddle; when the cancellation takes effect the workspace falls to
  Free and can buy prepaid again.

Plan upgrades/downgrades **while on auto-renew** happen inside Paddle (proration
is Paddle's job); the resulting `subscription.updated` event re-maps
`price_id → plan_code` and re-enforces store/team capacity.

## Webhooks = source of truth

`POST /api/v1/webhooks/paddle` dispatches `subscription.created / activated /
updated / past_due / paused / resumed / canceled` to
`apply_paddle_event` → `sync_subscription_state` (idempotent upsert keyed on
`paddle_subscription_id`). Renewals are **not** fulfilled from
`transaction.completed` — only the subscription events drive state, so a
replayed or late renewal can never double-extend. The existing
`transaction.completed` handler is untouched and simply never matches recurring
checkouts (no prepaid `reference_id`).

* New customers are bridged by Paddle customer id → `companies.paddle_customer_id`,
  falling back to a customer-email match against an active owner, then a Paddle
  `GET /customers/{id}` lookup for the email.
* `scheduled_change` (`cancel`/`pause`) is stored and surfaced in the UI.
* A terminal `subscription.canceled`/`expired` (or `paused`) event retires the
  workspace to Free immediately using the same force-pause + Free-fallback
  helpers as prepaid expiry (`_ensure_free_fallback`). A *pending* cancel first
  arrives as an active status with `scheduled_change` and stays governing until
  the period ends.

## Capacity

`_provision_plan` reuses the prepaid lifecycle helpers
(`restore_capacity` + `enforce_plan_capacity`) so activating, upgrading or
downgrading a recurring plan restores/pauses stores and team exactly like a
prepaid fulfilment, most-recently-active first.

## Endpoints

| Method & path | Auth | Purpose |
| --- | --- | --- |
| `GET /billing/subscription` | member | existing shape; returns the governing plan (recurring mapped) |
| `GET /billing/recurring` | member | current/latest recurring row or `null` |
| `POST /billing/recurring/checkout` | owner | hosted checkout URL to start auto-renew |
| `POST /billing/recurring/portal` | owner | Paddle customer portal URL (self-service) |
| `POST /billing/recurring/mock-activate` | owner | dev/test only (`PADDLE_MODE=mock`) |
| `PUT/DELETE /billing/schedule` | owner | blocked while Paddle governs |
| `POST /billing/checkout` | owner | blocked while Paddle governs |

## Configuration

Reuse the existing `paddle_price_ids` mapping. Auto-renew needs **recurring**
(not one-time) price ids configured in the Paddle dashboard, stored under a
`recurring:`-prefixed key so they can differ from the one-time prepaid price for
the same plan/cycle:

```json
{
  "pro:monthly": "pri_one-time-prepad...",
  "recurring:pro:monthly": "pri_recurring..."
}
```

The `recurring:` prefix is stripped when a webhook maps `price_id → plan`. No new
settings keys were added. See `chmabapos_api/.env.example`.

## Operations notes

* The prepaid daily expiry job (`run_billing_jobs.py`) and the -7/-3/-1
  reminders only scan `subscriptions` (prepaid), so auto-renew customers are
  never nudged to renew manually.
* Admin: recurring rows live in `recurring_subscriptions` (a subscriptions admin
  listing screen is a follow-up).

## Sandbox validation checklist

1. Create recurring prices in the Paddle sandbox and set `PADDLE_PRICE_IDS`.
2. Turn on auto-renew → complete checkout with `4242 4242 4242 4242`.
3. Confirm `subscription.created` creates the row, forfeits prepaid, and the
   workspace shows the plan under **Auto-renew**.
4. Cancel via the portal → confirm a scheduled-change state, then at period end
   `subscription.canceled` falls the workspace back to Free with stores/team
   paused to Free capacity.
5. Simulator: fire `subscription.updated` with a `past_due` status → plan keeps
   governing with a banner; with `paused` → drops to Free.
