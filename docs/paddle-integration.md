# Paddle card checkout integration

Paddle is integrated as an **alternative, hosted card checkout** for plan
purchases. The core billing model is unchanged: plans are **prepaid periods** —
a customer pays once for a fixed period, there is no card on file and no
auto-rebill (see `docs/billing-model.md`). Paddle acts purely as the payment
channel and is the **merchant of record** for card payments: it collects
country tax, sends the receipt and handles disputes.

- KHQR (Bakong, via CutLuy) stays the default method.
- Card uses **Paddle Checkout** (hosted) for a one-time transaction.
- A `transaction.completed` webhook fulfils the exact same prepaid
  `Subscription` that the CutLuy webhook fulfils (`fulfill_billing_payment`),
  so the two channels share one idempotent fulfilment path.

## How it works

1. Owner opens **Billing & plans** and picks a method: KHQR or Card.
2. `POST /api/v1/billing/checkout` with `payment_method: "card"` creates a
   **pending** subscription and a `BillingPayment` row with
   `provider = "paddle"`. The API creates a one-time Paddle transaction for the
   plan's catalog price id and returns `checkout.url`.
3. The app opens Paddle's hosted checkout in a new tab.
4. When the card is charged Paddle sends `transaction.completed` to
   `/api/v1/webhooks/paddle`. After signature verification the reference id
   (`custom_data.reference_id`) is matched to the `BillingPayment`, and the
   subscription is activated from the payment date — identical to a KHQR
   payment. `Payment required` / the billing page polls and unlocks the plan.

No subscription object is created in Paddle — each purchase is one transaction.

## Configuration

Both environment variables and admin-overridable platform settings are
supported (the admin rows fall back to env). See `chmabapos_api/.env.example`:

| Setting               | Meaning                                                     |
| --------------------- | ----------------------------------------------------------- |
| `PADDLE_MODE`         | `mock` (default), `sandbox`, or `live`                      |
| `PADDLE_API_URL`      | Override; defaults: `sandbox` → `sandbox-api.paddle.com`, `live` → `api.paddle.com` |
| `PADDLE_API_KEY`      | Server-side API key (`pdl_sdbx_apikey_…` / `pdl_live_apikey_…`) |
| `PADDLE_WEBHOOK_SECRET` | Notification destination secret (`pdl_ntfset_…`)           |
| `PADDLE_PRICE_IDS`    | JSON mapping. One-time prepaid: `"<plan>:<billing_cycle>" → price_id` (e.g. `"pro:annual"`). Auto-renew recurring uses `"recurring:<plan>:<billing_cycle>" → recurring price_id`. See `docs/paddle-recurring.md`. |
| `PADDLE_CHECKOUT_SUCCESS_URL` / `…_FAILURE_URL` | Optional return URLs passed to checkout |

Platform admins can edit the same values live under
`GET/PATCH /api/v1/admin/paddle-settings` (no admin UI yet — see “Roadmap”).

## Paddle dashboard setup (sandbox first)

1. Create products/prices matching Chmaba plans and cycles (starter/pro ×
   monthly/semi_annual/annual). One price id per combination. Prices are **net**,
   one-time (no subscription billing mode).
2. `Developer tools → Authentication`: create a **server API key**.
3. `Developer tools → Notifications`: create a URL destination for
   `https://<your-host>/api/v1/webhooks/paddle` subscribed to
   `transaction.completed`. Copy its secret.
4. Configure the values above, then complete a sandbox checkout with test card
   `4242 4242 4242 4242`.

## Mock mode (development / CI)

With `PADDLE_MODE=mock` no API key or price ids are needed:

- Checkout returns `checkout_url` pointing at
  `/api/v1/mock/paddle/<id>/complete`.
- `POST /api/v1/mock/paddle/<id>/complete` marks the payment paid and activates
  the plan (mirrors the CutLuy mock helper, and the billing UI’s
  “Simulate paid in development” button calls it).
- The webhook signature check is bypassed only when no secret is configured and
  the environment is not production (same behaviour as CutLuy).

## Verification & amount policy

Paddle is merchant of record and adds per-country tax on top of the quoted net
price, so the webhook compares the **net line subtotal** (`details.totals.subtotal`)
against the billing record — never the gross total. A mismatch or currency
mismatch is rejected with a non-2xx so Paddle retries and the row is left for
admin review (never silently accepted).

## Files touched

- `chmabapos_api/app/config.py` — Paddle settings
- `chmabapos_api/app/services/paddle.py` — client + signature verification
- `chmabapos_api/app/services/platform_config.py` — platform settings load/save
- `chmabapos_api/app/api/v1.py` — checkout `payment_method`, paddle webhook, mock complete
- `chmabapos_api/app/api/admin.py` — `paddle-settings` read/update
- `chmabapos_api/app/schemas.py` — request/read/webhook models
- `apps/web/src/features/team.jsx`, `apps/web/src/features/workspace.jsx` — billing UI

## Roadmap

- Admin UI for Paddle settings next to the CutLuy integration tab.
- Optional `PADDLE_CHECKOUT_SUCCESS_URL` handling (redirect back to billing).
- Replace the “pay exactly {amount}” copy with “quoted plan price; final total
  includes local tax charged by Paddle”.
- Handle Paddle refunds: subscribe the webhook destination to
  `adjustment.created` / `adjustment.updated`, and when an `action` of `refund`
  or `chargeback` reaches `status = "approved"`, mark the matching
  `BillingPayment` refunded and end the prepaid period it covered (fall back to
  Free). Paddle represents refunds as adjustments, not transaction events. The
  public Refund Policy (marketing `/refund-policy`) is already live; card
  purchases carry a 30-day money-back guarantee while KHQR stays
  non-refundable.
