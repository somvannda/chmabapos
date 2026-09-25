# ChmabaPay migration plan (retire CutLuy)

Status: Draft for review
Owners: Engineering
Scope: Replace the CutLuy payment provider with ChmabaPay (`https://pay.chmaba.com`)
for both merchant POS KHQR sales and Chmaba's own plan subscriptions. This
document plans the change; it does not implement it.

Related docs:

- `docs/billing-improvement-plan.md` §3.2.1 (provider-agnostic ingestion)
- `docs/billing-model.md` (prepaid plan lifecycle)
- ChmabaPay API reference: `https://pay.chmaba.com/api/docs` and
  `https://pay.chmaba.com/openapi.json`

## 1. Goal

A merchant pastes their **ABA PayWay share link** into Chmaba POS settings and
immediately accepts KHQR payments. The link is validated automatically by
ChmabaPay (no platform-admin manual review), money settles directly into the
merchant's own ABA PayWay account, and Chmaba never holds merchant funds.

CutLuy is retired once the new path is validated end to end.

## 2. Why ChmabaPay fits

ChmabaPay is built on ABA PayWay and its model maps almost 1:1 onto what Chmaba
already stores:

| Chmaba concept | ChmabaPay concept |
|---|---|
| Merchant store (`stores.id`) | ChmabaPay store (`st_…`) with `external_id` |
| `aba_payway_link` | the store's `link.raw_link` + `merchant_account_id` |
| `Payment` / `BillingPayment` (`external_id`) | ChmabaPay payment id |
| `reference_id` / `order_number` | ChmabaPay `reference_id` + `idempotency_key` (in body) |
| `qr_string`, `checkout_url` | returned by `POST /v1/payments` |
| `X-CutLuy-Signature` (HMAC `t`,`v1`) | `X-ChmabaPay-Signature` (same `t`,`v1` HMAC-SHA256 scheme) |

The webhook signature format is identical to the existing verifier
(`chmabapos_api/app/api/v1.py:1776`), so signature handling transfers directly.

Provider advantage over the current CutLuy flow:

- **Self-serve link activation.** `POST /v1/stores` (or
  `PUT /v1/stores/{id}/link`) validates the link and promotes a store to
  `active`, returning `payway_link_invalid` / `payway_link_not_found` on bad
  input. This removes the manual admin review today at
  `chmabapos_api/app/api/admin.py:217`.
- **Funds route correctly.** Each ChmabaPay store is one ABA link, so merchant
  POS sales settle to the merchant. Chmaba's own plan fees use ChmabaPay's
  `is_internal` store (funds to Chmaba's ABA account).
- **Reconciliation.** `GET /v1/transactions/check-status/{id}` and
  `POST /v1/payments/{id}/reissue` cover QR expiry and late settlement, which
  the current CutLuy integration has no answer for.

## 3. Target architecture

```
Chmaba POS API
  ├─ services/payments/registry.py        # provider selection (env/flag)
  ├─ services/payments/base.py            # PaymentProvider protocol + normalized result
  ├─ services/payments/chamabapay.py      # ChmabaPayClient (live + local mock)
  └─ services/payments/cutluy.py          # legacy, deleted in the final phase
                                              │
  ingest (webhook or reconcile poll) ─────────┤
                                              ▼
                             fulfill_billing_payment() / complete_order()
                                   (unchanged, provider-agnostic)
```

Two independent money flows, now split across two providers/accounts:

1. **Merchant POS sales** → the merchant's ChmabaPay store (their ABA link).
2. **Chmaba plan subscriptions** → Chmaba's internal ChmabaPay store.

## 4. Data model changes

Additive migration only (safe rollback). New alembic revision chained to the
current single head `e5f6a7b8c9d0` (`alembic heads` must stay at one).

Proposed columns:

| Table | Column | Type | Purpose |
|---|---|---|---|
| `stores` | `chamabapay_store_id` | String(40), nullable, indexed | `st_…` for this merchant store |
| `companies` | `chamabapay_store_id` | String(40), nullable | `st_…` for the company-level fallback link |
| `payments` | `provider` | existing String(30) | new value `chamabapay`; `cutluy` kept for history |
| `billing_payments` | `provider` | existing String(30) | same |

Notes:

- Keep `aba_payway_link` / `aba_payway_status` — they remain the merchant's
  bank destination and lifecycle state. `aba_payway_status` lifecycle is
  widened to `none | pending | active | error` (add `error` for a rejected
  link with a reason).
- `Payment.status` and `BillingPayment.status` remain free strings; ingestion
  recognises `pending, scanned, paid, expired, failed, superseded, reversed`.
- Terminal billing statuses (`app/api/v1.py:1792`) gain `superseded` and
  `reversed` so a late event can never rewrite a settled payment.
- **Decision needed:** whether the company-level link is a real fallback or is
  removed in favour of per-store links. If kept, mirror the store flow for
  `companies` (its own ChmabaPay store + `external_id`).

## 5. Configuration and platform settings

Rename/replace the `CUTLUY_*` surface:

```
PAYMENTS_PROVIDER=chamabapay        # cutluy | chamabapay (rollback switch)
CHAMABAPAY_MODE=mock                # mock (local fake) | live
CHAMABAPAY_API_URL=https://pay.chmaba.com
CHAMABAPAY_API_KEY=                 # ck_live_…, one key for all stores
CHAMABAPAY_WEBHOOK_SECRET=          # whsec_… from the registered webhook endpoint
CHAMABAPAY_PLATFORM_STORE_ID=       # st_… Chmaba's own internal store (plan fees)
```

Files to update:

- `chmabapos_api/app/config.py:28-31`
- `chmabapos_api/app/services/platform_config.py` (keys + defaults; admin-managed
  overrides in `PlatformSetting`)
- `chmabapos_api/.env.example:19-22`
- `deploy/.env.example:22-26`
- `docker-compose.yml:26-29`
- `deploy/docker-compose.prod.yml:45-48`

`CHAMABAPAY_MODE=mock` is a **local fake client** (mirroring today's
`CutLuyClient` mock at `app/services/cutluy.py:23`) used by dev and tests, since
ChmabaPay has no sandbox. Only `live` calls `pay.chmaba.com`.

Admin settings API (`app/api/admin.py:240-276`) becomes
`GET/PATCH /admin/chamabapay-settings` exposing: mode, api_url, platform store
id, api key set/unset, webhook secret set/unset. The old `/admin/cutluy-settings`
is removed with the provider in the final phase.

## 6. Backend changes

### 6.1 Provider adapter (do first, no behaviour change)

Per `docs/billing-improvement-plan.md` §3.2.1:

- `services/payments/base.py`: a `PaymentProvider` protocol with
  `create_payment(amount, reference_id, idempotency_key, store_ref, metadata)`
  returning a normalized result `(provider_payment_id, status, amount, currency,
  reference_id, qr_string, checkout_url, expires_at)`.
- `services/payments/registry.py`: reads `PAYMENTS_PROVIDER` and returns the
  active client.
- `services/payments/chamabapay.py`: `ChmabaPayClient` implementing:
  - `ensure_store(external_id, aba_link)` → `POST /v1/stores`, else
    `PUT /v1/stores/{id}/link`; returns `st_…` and link status.
  - `create_payment(...)` → `POST /v1/payments` with `idempotency_key` **in the
    body** (note: current CutLuy code sends it as a header, see
    `app/services/cutluy.py:40`).
  - `reconcile(provider_payment_id)` → `GET /v1/transactions/check-status/{id}`.
  - `reissue(provider_payment_id)` → `POST /v1/payments/{id}/reissue`.
- Replace `cutluy_client_for()` (`app/api/v1.py:375`) with
  `payment_provider_for(db)`.

### 6.2 Merchant linking (self-serve)

Replace `apply_aba_payway_link()` (`app/api/v1.py:357`):

1. Merchant saves a link via `PATCH /company` (`v1.py:703`) or
   `PATCH /stores/{id}` (`v1.py:756`).
2. Backend calls `ChmabaPayClient.ensure_store(external_id=<store|company id>,
   aba_link)`.
3. On success: persist `chamabapay_store_id`, set `aba_payway_status = "active"`.
4. On `payway_link_invalid` / `payway_link_not_found`: set status `error` and
   return a field-level message the settings UI can show.
5. Store registration is idempotent — re-saving the same link does not create a
   duplicate ChmabaPay store.

This eliminates the admin activation step but the admin
`/admin/payment-links` view (`admin.py:180-237`) stays as read/override support.

### 6.3 POS KHQR order

In `create_order` (`app/api/v1.py:1196-1312`):

- Keep the v1 guard: one exact USD KHQR tender equal to the total
  (`v1.py:1252`).
- Resolve the merchant link as today (store, else company, `v1.py:1254-1261`).
- Call `payment_provider_for(db).create_payment(...)` with `store_ref` and
  `metadata` including `type: "pos_order"`, `store_id`, `reference_id =
  order_number`.
- Persist `Payment(provider="chamabapay", external_id, qr_string,
  checkout_url, ...)`.

### 6.4 Plan subscription checkout

In `create_billing_checkout` (`app/api/v1.py:1557-1597`):

- Create the `pending` `Subscription` + `BillingPayment` as today.
- Use the **platform internal store** (`CHAMABAPAY_PLATFORM_STORE_ID`) as the
  destination, so Chmaba's plan fees settle to Chmaba's ABA account.
- Set `provider = "chamabapay"`.
- `fulfill_billing_payment()` (`v1.py:1829`) stays unchanged and
  provider-agnostic.

### 6.5 Webhook

- New `POST /api/v1/webhooks/chamabapay`, header `X-ChamabaPay-Signature`.
- Reuse `signature_is_valid()` (`v1.py:1776`) — same `t`,`v1` HMAC-SHA256 scheme.
  Secret comes from the registered ChmabaPay webhook endpoint
  (`/v1/webhooks/{id}` `signing_secret`, shown once).
- Event types: `payment.completed`, `payment.expired`, `payment.superseded`,
  `payment.reversed`; branch on `data.payment.status`, not on the event name.
- Replace `CutLuyWebhookEvent` (`app/schemas.py:1046-1063`) with
  `ChmabaPayWebhookEvent`. **Action item:** obtain the exact payload shape via
  `POST /v1/webhooks/{endpoint_id}/test` (synthetic signed event) during
  Phase A, before finalizing the schema.
- Suggested new remote route: `POST /api/v1/webhooks/chamabapay/reconcile`
  (bearer/internal) for backfill, or rely on the scheduled job in 6.6.
- Remove `POST /mock/cutluy/{id}/complete` (`v1.py:2002`) or rename to a
  provider-neutral dev endpoint.

### 6.6 Reconciliation and status model

Because QR codes expire in ~180s but a "late" payment can still settle,
expiry must not be terminal:

- **POS:** on `GET /orders/{id}` (`v1.py:1324`) or the POS poll, if a KHQR
  `Payment` is stale `pending`/`expired`, call ChmabaPay
  `check-status`; if `PAID`, run `complete_order`. Throttle per order.
- **Billing:** add `GET /billing/checkout/status` (or reconcile inside
  `GET /billing/subscription`, `v1.py:1493`) that calls `check-status` and,
  when paid, runs `fulfill_billing_payment`.
- Map ChmabaPay statuses:
  - `paid` → complete order / fulfill billing.
  - `expired`, `failed`, `superseded` → `order.status = payment_expired/...`
    (non-terminal for reconciliation; a later `paid` still wins).
  - `reversed` → booking-only reversal: for POS, record a `Refund` (or mark the
    payment reversed); for billing, leave entitlement unchanged and flag for
    admin review. Never mutate or delete the original payment.
- A scheduled reconcile job (alongside `scripts/run_billing_jobs.py`) sweeps
  open payments, mirroring the webhook path.

### 6.7 Errors and rate limits

- Branch on ChmabaPay machine tokens (`store_disabled`,
  `payment_link_disabled`, `quota_exceeded`, `amount_too_low`/`high`,
  `payway_hosted_error`) and surface a merchant-readable message.
- Respect 429 (`Retry-After`, `payment_create` 60/min per key) with a bounded
  retry on idempotent mints.

## 7. Frontend changes

Merchant app (`apps/web`):

- `features/settings.jsx:74` `BankKhqrPane`: change copy from "submitted for
  review" to automatic validation; show `active` / `error` states and the
  ChmabaPay link status; keep the ABA link input.
- `features/sales.jsx:10` `POSPaymentModal`: QR rendering unchanged; update
  "Powered by" copy.
- `features/workspace.jsx:107`, `features/team.jsx:291`: replace
  "Powered by cutluy.com" with ChmabaPay copy.

Admin app (`apps/admin`):

- `src/api.js:158-159`: `chamabapaySettings` / `updateChamabapaySettings`.
- `src/App.jsx:126,190,215,220`: rename CutLuy references and settings labels.
- Keep payment-links monitoring (`src/api.js:155-157`).

## 8. Cutover and rollback

ChmabaPay has **no sandbox**; every live key moves real money.

- Keep `PAYMENTS_PROVIDER` as the rollback switch. `cutluy` remains the default
  until the final phase; DB changes are additive.
- Phase A: point a ChmabaPay store at a Chmaba-owned ABA link and mint a
  `$0.01` payment; pay it from a wallet; verify the `payment.completed` webhook
  signature and payload. This is the critical path.
- Phase B (lowest risk): switch **plan subscriptions** to ChmabaPay using
  Chmaba's internal store first.
- Phase C: enable merchant self-serve linking and POS KHQR for a pilot
  merchant, then roll out.
- Phase D: run reconciliation for a full QR-expiry window in parallel with
  CutLuy to compare outcomes.
- Phase E (retire): remove `services/cutluy.py`, `CUTLUY_*` config/env, the
  `/webhooks/cutluy` and `/mock/cutluy` routes, `CutLuy*` schemas, and update
  every doc/openapi entry listed in §9.
- Rollback before Phase E: set `PAYMENTS_PROVIDER=cutluy`; no schema revert
  required.

## 9. Docs, CI, and generated artifacts

- `chmabapos_api/openapi.json`: regenerate with
  `python chmabapos_api/scripts/export_openapi.py` and commit (CI fails on drift,
  `.github/workflows/ci.yml`).
- `chmabapos_api/README.md:13,67-69,110`
- `docs/architecture.md:132,134,139,172`
- `docs/billing-model.md:9,12,82`
- `docs/billing-improvement-plan.md:107,135,166-190,650`
- `docs/deploy.md:30`

## 10. Test plan

- `tests/test_billing_entitlement.py:187-200`: replace
  `test_khqr_checkout_stays_on_cutluy_provider` with a ChmabaPay provider test
  (update the monkeypatched factory to the registry).
- Webhook signature: valid, stale timestamp (`>300s`), wrong secret, malformed
  header.
- Idempotency: replay `payment.completed` N times → one activation; webhook +
  reconcile race → one activation.
- Status handling: `paid`, `expired-late-paid`, `failed`, `superseded`,
  `reversed`.
- Merchant linking: valid link → `active`; `payway_link_invalid` /
  `payway_link_not_found` → `error`; re-save same link is idempotent.
- POS: insufficient stock on late completion still returns 409 and does not
  deduct twice.
- OpenAPI drift check passes.

## 11. Phased task breakdown

1. **Phase A — adapter + client.** Payment provider protocol/registry,
   `ChmabaPayClient` (mock + live), config/env, capture a synthetic webhook
   payload, unit tests. No behaviour change (`PAYMENTS_PROVIDER=cutluy`).
2. **Phase B — billing subscriptions.** Admin settings, platform internal
   store, wire `create_billing_checkout` + webhook fulfillment, reconcile poll.
3. **Phase C — merchant linking + POS.** Self-serve `ensure_store`, auto
   activation/error states, POS order via ChmabaPay, settings/POS UI.
4. **Phase D — reconciliation + reversals.** `check-status` polling, late
   payment handling, `reversed` bookkeeping, scheduled sweep.
5. **Phase E — retire CutLuy.** Remove client/config/routes/schemas/UI copy,
   update docs, regenerate openapi, drop `cutluy` provider references.

Each phase is its own PR (branch, Conventional Commits, green CI) per
`AGENTS.md`.

## 12. Decisions

Resolved:

1. **Company vs store link — keep the company fallback.** Each Chmaba store and
   each company registers its own ChmabaPay store (`chamabapay_store_id`); a
   store with no link of its own may fall back to the company link.
2. **ChmabaPay plan for the platform — Pro.** Up to 50 stores and 1,000,000
   payments/month; the platform needs one customer store per merchant plus its
   own internal store for plan fees.
3. **Reversal policy — auto-record a POS refund.** On `payment.reversed`, create
   a POS `Refund` and return items to stock. Billing entitlement is unchanged
   (recorded for admin review only).
4. **Keep CutLuy? — remove entirely in Phase E.** Only ChmabaPay remains after
   Phase E; the legacy CutLuy path is deleted, not kept dormant.

Still open:

5. **Exact webhook payload.** Confirm field names via the synthetic test event
   (`POST /v1/webhooks/{endpoint_id}/test`) before freezing the Pydantic schema
   and `financial` handling.
6. **Currency.** Confirm every merchant ABA link is USD (current v1 KHQR rule)
   and how a non-USD link should be rejected.

## 13. Phase status

- Phase A (provider adapter + `ChmabaPayClient`) — merged (PR #45).
- Phase B (plan billing via the provider) — merged (PR #46).
- Phase C (self-serve merchant linking + POS KHQR) — merged (PR #48).
- Phase D (reconciliation + webhook + reversals) — merged (PR #50, PR #53).
- Frontend copy/status updates — merged (PR #54).
- Admin ChmabaPay settings panel — merged (PR #63).
- Phase E (retire CutLuy) — **removed** (ChmabaPay is the only provider); validate
  per §14 and deploy before merchant rollout.

## 14. Before Phase E (validation checklist)

The CutLuy code is intentionally kept as a fallback until these are done:

1. Capture a synthetic ChmabaPay webhook (`POST /v1/webhooks/{endpoint_id}/test`)
   and confirm the `data.payment.*` field names against
   `ChmabaPayWebhook*` schemas; adjust if needed.
2. Provision the platform ChmabaPay Pro account and its internal store, set
   `CHAMABAPAY_PLATFORM_STORE_ID`, and run a `$0.01` live payment end to end
   (create -> pay -> signed `payment.completed` -> fulfillment/order complete).
3. Exercise the dev mock flow with
   `POST /api/v1/mock/chamabapay/{payment_id}/complete`.
4. Only then run Phase E: delete `services/cutluy.py` and
   `services/payments/cutluy.py`, remove `CutLuy*` schemas and the
   `/webhooks/cutluy` and `/mock/cutluy` routes, drop `CUTLUY_*` config/env,
   rename the admin settings endpoint to ChmabaPay, rewrite the tests that
   patch `cutluy_client_for`, regenerate `openapi.json`, and update docs/README.


