# ChmabaPay go-live runbook

Status: Ready for validation
Related: `docs/chamabapay-migration-plan.md` (§14 validation checklist)

This runbook takes Chmaba from "ChmabaPay code merged, CutLuy still the default"
to "ChmabaPay live for merchants". Do it in order. CutLuy is only removed in
Phase E, so the rollback at the end works throughout.

## 0. Prerequisites

- A ChmabaPay account on the **Pro** plan (50 stores, 1,000,000 payments/month).
- Chmaba's own ABA PayWay share link, for the **platform internal store** that
  collects Chmaba plan fees.
- At least one merchant with an ABA PayWay share link.
- Access to `deploy/.env` (or the admin API) to set secrets.

There is **no sandbox**: every live key moves real money. Validate with $0.01.

## 1. Create the ChmabaPay workspace, key and webhook

1. Sign in to `https://pay.chmaba.com`, create the workspace.
2. **API keys -> Create key**. Copy `ck_live_...` (shown once).
3. **Webhooks -> Add endpoint**. You supply the URL — it is *your* Chmaba POS
   endpoint, e.g. `https://chmaba.com/api/v1/webhooks/chamabapay` — and
   subscribe to `*`. ChmabaPay then generates the `signing_secret` (shown once).
   **You must set that same secret on Chmaba** as `CHAMABAPAY_WEBHOOK_SECRET`;
   if the two do not match, every delivery is rejected with
   `400 Invalid ChmabaPay signature`.
4. **Stores -> Create store** for Chmaba's own ABA link (the internal store that
   collects plan fees). Copy its `st_...` id. This is
   `CHAMABAPAY_PLATFORM_STORE_ID`.

## 2. Configure Chmaba

Either set env (recommended for production) in `deploy/.env`:

```
PAYMENTS_PROVIDER=chamabapay
CHAMABAPAY_MODE=live
CHAMABAPAY_API_URL=https://pay.chmaba.com
CHAMABAPAY_API_KEY=ck_live_...
CHAMABAPAY_WEBHOOK_SECRET=whsec_...
CHAMABAPAY_PLATFORM_STORE_ID=st_...
```

or, without a redeploy, via the admin API as a platform admin:

```http
PATCH /api/v1/admin/chamabapay-settings
Authorization: Bearer <platform-admin-token>

{"mode":"live","api_url":"https://pay.chmaba.com","api_key":"ck_live_...","webhook_secret":"whsec_...","platform_store_id":"st_..."}
```

DB overrides win over env; clearing a field falls back to the env default.
Then restart the API if env was changed.

> **No admin UI yet.** Until Phase E there is no ChmabaPay settings panel in the
> admin app (it still shows the CutLuy integration), so configure ChmabaPay with
> env + restart, or the `PATCH` call above using a platform-admin token.

## 3. Verify the webhook signature pipeline

First confirm the endpoint is publicly reachable. An unsigned POST should be
rejected by our verifier, which proves the route is proxied to the API:

```bash
curl -i -X POST https://chmaba.com/api/v1/webhooks/chamabapay \
  -H "Content-Type: application/json" -d '{}'
# expected: HTTP 400 {"detail":"Invalid ChmabaPay signature: the signature header is missing"}
```

Then send a synthetic signed event from the dashboard or:

```bash
curl -X POST "$CHMABA_API/v1/webhooks/<endpoint_id>/test" -H "Authorization: Bearer $CHMABA_KEY"
```

Confirm:
- No `Invalid ChmabaPay signature` (the `t,v1` HMAC-SHA256 scheme must match and
  the header must be `X-ChmabaPay-Signature`; the legacy `X-ChamabaPay-Signature`
  spelling is also accepted).
- The `data.payment.*` field names line up with `ChmabaPayWebhook*` in
  `chmabapos_api/app/schemas.py`; adjust the schema if ChmabaPay differs.

## 4. Validate a $0.01 live payment (platform fees)

1. Mint a payment for the platform store:

```bash
curl -X POST "$CHMABA_API/v1/payments" \
  -H "Authorization: Bearer $CHMABA_KEY" -H "Content-Type: application/json" \
  -d '{"amount":0.01,"reference_id":"golive-1","store":"st_..."}'
```

2. Scan and pay the returned `qr_string` with a real wallet.
3. Confirm `payment.completed` arrives and verifies; confirm the ABA balance.
4. In Chmaba, run a plan checkout as an owner and confirm the subscription
   activates (`GET /api/v1/billing/subscription` -> `active`) and a receipt is
   issued.

## 5. Validate merchant linking

1. As a merchant owner, save an ABA PayWay link in Settings.
2. `PATCH /api/v1/company` returns `aba_payway_status: "active"` (auto-validated;
   no admin review). A bad link returns `error`.
3. Confirm the merchant's ChmabaPay store appears in the platform dashboard.

## 6. Validate POS KHQR end to end

1. Ring up a KHQR sale in the POS; the order is `payment_pending`.
2. Scan and pay; the webhook (or the 3s POS poll / reconciliation) completes the
   order and deducts stock.
3. Late payment: let a QR expire, pay it anyway, confirm the order still
   completes on the next read.
4. Reversal: record a reversal in ChmabaPay; confirm a POS refund is recorded and
   stock returns.

## 7. Troubleshooting

- `400 Invalid ChmabaPay signature: <reason>` on a real delivery: the endpoint is
  reachable and our verifier ran. The `reason` says which check failed:
  - `the webhook secret is not configured` — set `CHAMABAPAY_WEBHOOK_SECRET`
    (env or admin panel) and restart.
  - `the signature header is missing` / `malformed` / `invalid timestamp` /
    `stale` — the `X-ChmabaPay-Signature` header is missing or not the expected
    `t=…,v1=…` form.
  - `does not match the configured secret` — the secret is wrong. Check that
    `CHAMABAPAY_WEBHOOK_SECRET` equals this endpoint's current `signing_secret`
    (watch for trailing spaces/newlines) and restart.

  The dashboard's "Verified against this endpoint's secret" only means ChmabaPay
  signed correctly; Chmaba must hold the same secret. The endpoint accepts both
  `X-ChmabaPay-Signature` and the legacy `X-ChamabaPay-Signature` spelling.
- `404` on the reachability curl: nginx is not proxying `/api/v1/*` to the API.
- `502`/`504` on the reachability curl: nginx cannot reach the API container.
- Rotating secrets: if the API key or webhook secret is ever exposed, revoke or
  rotate it in ChmabaPay, then update `CHAMABAPAY_API_KEY` /
  `CHAMABAPAY_WEBHOOK_SECRET` and restart. Rotating the webhook secret makes
  deliveries signed with the old secret fail until Chmaba is updated.

## 8. Rollback

Set `PAYMENTS_PROVIDER=cutluy` (and `CUTLUY_MODE=mock` or live creds) and
restart. No schema change is required.

## 9. Then Phase E

Only after steps 3-6 pass, run Phase E to delete the CutLuy code paths and make
ChmabaPay the sole provider. See `docs/chamabapay-migration-plan.md` §14.
