# Offline mode (G9)

Status: Design + **Phase 1 in progress** — a backend idempotency key for order
creation (so a replayed sale never duplicates) plus the design for the POS
offline sale queue. Phases 2–3 are design only.
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

- The POS (`apps/web`) is a thin client: every sale is a `POST /orders`; a failed
  request surfaces an error and the sale is lost.
- `create_order` is already transactional and stock-safe, but has **no idempotency
  key**, so a retried/replayed request creates a duplicate order.
- The in-process worker pattern (e.g. the mailing queue) shows how background work
  is done, but offline persistence is purely client-side.

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

- **Phase 1 — Idempotent sales + offline queue.**
  - Backend: an optional `client_order_id` on `POST /orders`, unique per store;
    replaying the same id returns the existing order instead of creating a second.
  - Web: when a cash sale fails with a network error, store it in `localStorage`
    with its `client_order_id`; retry on reconnect; show an offline banner and a
    pending count.
- **Phase 2 — Read caching.** Cache the catalog/stock/customers so the POS can be
  opened and browsed offline; show last-synced time and disable online-only
  actions (KHQR, refunds, held-order sync).
- **Phase 3 — Conflict resolution.** Surface server rejections (e.g. insufficient
  stock after a replay) with a reconciliation screen; support partial replay and
  manual correction.

## 5. Phase 1 detail

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

## 6. Non-goals / risks

- Offline **refunds**, KHQR and held-order sync are out of scope for Phase 1.
- Stock correctness: a replayed sale may be rejected if stock changed; Phase 1
  surfaces the rejection, Phase 3 adds reconciliation.
- Security: `client_order_id` is server-scoped per store and carries no trust; it
  only prevents duplicate creation.

## 7. Rollout

Phase 1 ships as independent backend (idempotency) and web (queue) changes; the
backend change is backward compatible (`client_order_id` optional).
