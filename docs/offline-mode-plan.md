# Offline mode (G9)

Status: **Phases 1–2 shipped** (#596, #597, #598), plus the first **Phase 3** slice
(#602: rejected replays are surfaced for review, not dropped). In short: a backend
idempotency key for order creation (a replayed sale never duplicates), the POS
offline sale queue, and a per-store read cache so the POS keeps rendering the
last-known catalogue when the API is unreachable. Phase 3 also ships a review list
for rejected replays with a **Restore to cart** path (#602, #610, #612); full
editable partial replay is designed in §5 but not yet built.
Owners: Engineering
Scope: `docs/capabilities-and-gaps.md` G9 — "large; likely out of scope
near-term". This document scopes it into shippable phases.

Related: `docs/online-ordering-plan.md` (public order submit reuses the held-order
engine), `docs/architecture.md`, `chmabapos_api/app/api/v1.py` (`create_order`),
`chmabapos_api/app/models.py` (`Order`), `apps/web/src/features/sales.jsx` (POS).

## 1. Goal

Keep the store selling when the network or API is unreachable. A cashier should be
able to take a cash sale offline, have it stored locally, and have it sync to the
backend automatically once connectivity returns — exactly once, with correct stock
and serials.

## 2. Current state

- The POS (`apps/web`) is a thin client: every sale is a `POST /orders`. A failed
  request previously surfaced an error and the sale was lost; it now queues the
  sale locally (Phase 1) and falls back to cached reads (Phase 2).
- `create_order` is transactional and stock-safe, and now accepts a
  `client_order_id` so a retried/replayed request returns the existing order
  instead of creating a duplicate (Phase 1).
- The in-process worker pattern (e.g. the mailing queue) shows how background work
  is done, but offline persistence is purely client-side (`localStorage`); the
  server stays the source of truth and validates every replay.

## 3. Design principles

1. **Never lose or duplicate a sale.** Offline sales are queued with a stable
   client-generated id and replayed; the server dedupes on that id.
2. **Cash-first.** Offline sales are cash (KHQR/online need connectivity). The
   queue is cash-only in Phase 1.
3. **Fail loud, recover quiet.** While offline the POS shows a clear banner and
   marks queued sales; syncing is automatic and reported.
4. **The server stays the source of truth.** Stock/serials are validated on sync;
   a rejected replay is surfaced for the cashier to resolve, never silently kept.

## 4. Phased plan

- **Phase 1 — Idempotent sales + offline queue. ✅ Shipped (#596, #597).**
  - Backend: an optional `client_order_id` on `POST /orders`, unique per store;
    replaying the same id returns the existing order instead of creating a second.
  - Web: when a cash sale fails with a network error, store it in `localStorage`
    with its `client_order_id`; retry on reconnect; show an offline banner and a
    pending count.
- **Phase 2 — Read caching. ✅ Shipped (#598).** Products, inventory and combos are
  cached per store; when a read fails with a network error the POS keeps the
  last-known catalogue and the header badge flips to "Offline — cached". Report,
  orders and setup-checklist reads tolerate a network error too. Last-synced time
  and disabling online-only actions (KHQR, refunds, held-order sync) remain
  backlog.
- **Phase 3 — Conflict resolution.** Surface server rejections (e.g. insufficient
  stock after a replay) with a reconciliation screen; support partial replay and
  manual correction. **Shipped:** a rejected replay is filed to a needs-attention
  list shown in the POS for Retry/Dismiss (#602), listing its lines (#610), with a
  **Restore to cart** action that rebuilds the sellable lines for re-checkout
  (#612). Editable partial replay remains.

## 5. Phase 1–3 detail

### Backend
- `orders.client_order_id` (nullable string) with a unique index on
  `(store_id, client_order_id)` (Postgres allows many `NULL`s).
- `OrderCreateRequest.client_order_id: str | None`.
- `create_order`: if `client_order_id` is supplied and an order already exists for
  `(store_id, client_order_id)`, return that order (200-equivalent, same body)
  instead of creating a duplicate. New orders store the id.

### Web
- Generate a `client_order_id` (UUID) per checkout attempt, reused across retries.
- On a network failure (not a 4xx validation error), queue the order payload in
  `localStorage` and mark it pending; retry on `online` and on an interval.
- Banner: "Offline — N sale(s) queued"; on sync, notify success/failure.

### Phase 2 — read cache
- `apps/web/src/lib/readCache.js`: per-store `localStorage` entries keyed
  `chmaba.cache.<storeId>:<name>` holding `{ at, value }`; `loadCache` is
  corrupt-safe.
- `fetchWithCache(storeId, name, loader)`: on success it caches the value and
  returns `{ value, stale: false }`; on a **network** failure (no HTTP status) it
  returns the last cached value with `stale: true`; any other error rethrows, so a
  403/422 is never masked by stale data.
- `refreshOperationalData` (`apps/web/src/features/workspace.jsx`) reads
  products/inventory/combos through it; report, orders and setup-checklist are
  fetched separately and tolerated on a network error. The POS header badge shows
  "Offline — cached" while a cached read is in use, with a one-time
  "Offline — showing the last synced catalogue" notice.
- The cache is best-effort: private-mode/quota failures are swallowed.

### Phase 3 — rejected-sale review + restore (#602, #610, #612)
- `apps/web/src/lib/offlineQueue.js`: a validation failure (4xx) from a replay is
  moved to a needs-attention list (`chmaba.offline.orders.failed`) with its error
  message instead of being dropped. `dismissFailedOrder(key)` removes one;
  `retryFailedOrder(key)` puts it back on the queue.
- The POS status line shows amber "N sale(s) queued offline" or red "N offline
  sale(s) need review"; **Review** opens a modal listing each rejected sale, its
  lines (#610) and the rejection error, with Retry / Dismiss.
- **Restore to cart (#612):** `apps/web/src/lib/offlineReconcile.js` rebuilds the
  still-sellable lines from the loaded catalogue (per-variant price/stock,
  modifiers, quantity capped to stock) and merges them into the cart; combos and
  missing/out-of-stock lines are reported, never silently dropped. The cashier
  re-checks out through the normal flow, so pricing and tax stay correct.

### Phase 3 — editable partial replay (design, not yet built)
Restore-to-cart (#612) already re-applies the sellable lines via a fresh checkout.
What remains is editing a sale in place before re-submit. Goal: when a replay is
rejected because some lines cannot be fulfilled (stock
changed, a serial was sold, etc.), let the cashier keep the sellable lines instead
of losing the whole sale.

- **Backend:** no schema change. `POST /orders` already accepts an arbitrary item
  list and is transactional — it either creates the order fully or not at all — so
  a corrected sale is re-submitted as a normal create.
- **Idempotency:** re-submit the corrected sale with the **same `client_order_id`**.
  Because a rejected create rolls back, no order exists for that key, so the retry
  creates exactly one and a double-tap still dedupes. Drop the failed row only
  after the corrected create succeeds.
- **Web:** the review modal's rows become an editable list — remove an
  unfulfillable line, lower a quantity, then **Re-submit**. Recompute totals
  client-side from the loaded catalogue, but treat the server as the source of
  truth on submit. Removing the last line is equivalent to Dismiss.
- **Never silent:** every adjustment is an explicit cashier action; nothing is
  dropped without confirmation. Serial numbers attached to a removed line are
  released back to the pool.
- **Open questions:** reconcile by editing the queued body vs. writing a fresh
  order with a new key; how reservations / held tickets interact; whether to keep
  an audit record of the original rejected attempt.

## 6. Non-goals / risks

- Offline **refunds**, KHQR and held-order sync are out of scope for Phase 1.
- Stock correctness: a replayed sale may be rejected if stock changed; a rejected
  replay is filed for review with a restore-to-cart path (#602/#612) — in-place
  editing before re-submit is still to come.
- Security: `client_order_id` is server-scoped per store and carries no trust; it
  only prevents duplicate creation.

## 7. Rollout

Phase 1 shipped as independent backend (idempotency) and web (queue) changes; the
backend change is backward compatible (`client_order_id` optional). Phase 2 and the
Phase 3 review/restore work are web-only changes (no schema). Editable partial
replay is designed in §5 but not yet built.
