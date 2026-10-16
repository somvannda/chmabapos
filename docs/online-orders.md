# Online orders are orders

Status: the submit path now creates a real order with its own payment. What landed is
recorded under "Step 1, as landed"; the remaining steps follow it. This document exists so
the rest stays mechanical rather than exploratory.

## The problem, in one line

A shopper's paid order did not appear in Orders or in reporting until a member of staff
settled a parked ticket by hand.

## What was actually wrong

Three things, found by following the flow rather than reading the docs:

1. **`orders.created_by` was NOT NULL** (an FK to `users`), and a shopper on a store page has
   no staff user. That single constraint is why online orders were parked as `held_orders`
   instead of being orders.
2. **A held ticket stores its items as JSON**, not as lines against products. It is a parked
   cart, not an order — so nothing that reads orders (reports, refunds, the shopper's own
   history) can see it.
3. **`order.status` mixes two ideas** — `payment_pending` alongside `pending_pickup` and
   `completed`. Payment and fulfilment are different questions and one field cannot answer
   both.

Note what is *already* right: payment state has its own home, `payments.status`
(`pending`/`paid`/`expired`/`failed`/…). Nothing new is needed for payment truth.

## The model

An order is created **immediately**, whatever the store's payment mode, with the two
questions kept apart:

- **Payment** — from `payments`: none, or `pending` → `paid` | `failed` | `expired` | `refunded`.
- **Fulfilment** — `order.status`, eventually fulfilment-only: `placed` → `accepted` →
  `preparing`/`ready` → `completed` | `cancelled`.

`orders.source` (`pos` | `online`) says where a sale came from, so a report never has to
infer it from whether a user happens to be attached.

## Behaviour by mode

| | Prepaid (`require_online_payment`) | Pay at counter / collect |
|---|---|---|
| Order created | on submit | on submit |
| In Orders and reports | yes, flagged *awaiting payment* | yes, flagged *unpaid* |
| Fired to the kitchen | **only once paid** | immediately |
| Revenue recognised | on `paid_at` | on `paid_at` |
| Never paid | expires → cancelled, stock released | stays as money owed |

The rule the kitchen tests already pin — **an unpaid online order is not put on the board** —
is preserved. What changes is that the *order* is real from the moment it is placed; the
payment only gates **fulfilment**, and that gate is a filter, not a different table.

## Steps

1. **Public submit creates an `Order`**: `source='online'`, `created_by=None`, `public_token`,
   lines against products, and a pending payment attached when the store requires one.
   Stop creating `HeldOrder` for storefront orders.
2. **Gate fulfilment, not visibility**: the kitchen/board filters
   `prepaid ? there is a paid payment : true`.
3. **Settle on payment**: set the payment `paid` with `paid_at`, and for prepaid **fire the
   order to the kitchen at that moment**.
4. **Reports**: revenue on `paid_at`. Unpaid online orders become an *attention* item on the
   dashboard rather than invisible.
5. **Expire unpaid prepaid orders** after a configurable window: cancel, release stock, tell
   the shopper.
6. **Keep `HeldOrder` for its real job** — a cashier parking a cart, splitting, merging,
   transferring to a table.
7. **Storefront**: the confirmation polls the order's token, not the ticket's.

## Implementation notes (read from the code, for the next pass)

- **Reuse the pricing that is already there.** `_submit_public_order` prices everything
  server-side and builds a `snapshot` list whose fields map almost one-to-one onto
  `OrderItem`: `product_id`, `product_name`, `sku`, `variant_id`, `variant_name`,
  `attributes`, `modifiers`, `unit_price`, `quantity`, `line_total`. Do not reprice.
- **The totals are computed there too**: `line_total_sum`, `tax_rate =
  store.service_tax_rate or 10%`, an optional `tax_inclusive` preference, and the resulting
  `order_total`.
- **Order numbers** come from `next_document_number(db, store_id=…, scope=…)`, backed by
  `store_sequences` — the same helper the till uses, so an online order numbers coherently
  with counter sales instead of starting a second series.
- **Create the order** with `created_by=None`, `source="online"`, the ticket's
  `public_token`, a fulfilment value in `status`, then one `OrderItem` per snapshot line.
- **Attach the payment to the order as well — this is the part that must not be skipped.**
  Today the public path keeps the provider payment on the held ticket only and creates **no
  `Payment` row at all** (the completion endpoint has a branch for that). An order created
  without one would look unpaid, and would be absent from tender reporting and refunds. Read
  the `Payment` model before wiring it.
- **Then decide the ticket's fate**: stop creating it for storefront orders, or keep it
  strictly as the kitchen's work item. Two live order concepts is the worst outcome, so pick
  one and write it down.
- **Storefront follow-on**: the confirmation currently polls the ticket's id. Once the order
  exists, it should poll the order's `public_token`, so a paid order is tracked by the thing
  that reports treat as the sale.

## Traps already paid for

- **An inner join on `users` would hide every online order** from the till's list. Checked:
  none exist today, and the held-order list outer-joins. A test that lists orders with one
  online order present would keep it that way.
- **Never sum the cart in the browser.** The storefront did, and silently omitted service
  tax — a shopper was quoted $2.50 for something the till charged $2.75.
- **A payment's state must never be cacheable.** The status route sent no `Cache-Control` at
  all, so a poll could keep reading `pending` after a payment had gone through.


## Step 1, as landed

`_submit_public_order` creates an `Order` (source `online`, `created_by` NULL, the ticket's
`public_token`, `status="payment_pending"`), one `OrderItem` per line, and — when the store
requires online payment — a `Payment` carrying the provider's `external_id`. The basket is
priced once, before the payment branch, and both records use those figures.

Two things this cost, both worth knowing before touching it again:

- **The webhook's amount check woke up.** No `payments` row existed for a public order
  before, so `payment.amount != provider_payment.amount` never applied. Three tests were
  sending a placeholder `3.00` against a real total of `3.30` and had been passing on that
  technicality. The events now carry the recorded amount, and a new test pins the refusal.
- **The mock completion had to learn to keep the ticket in step.** It returns as soon as it
  finds a `Payment`, so settling only the order left the ticket — which the storefront's
  confirmation polls — reporting `pending` over a paid sale. It now marks its twin paid
  too. The ticket needs keeping in step for as long as it remains the board's record: the
  merchant's list reads `payment_status` from the ticket, so a paid sale would otherwise sit
  on the board marked unpaid.

Verified: the whole API suite is green (520 passed). The one failure seen in a full run,
`test_drip_respects_the_send_window_unless_forced`, also fails on a clean tree and passes
with this change: it is flaky, not a regression.

Three things checked rather than assumed, which changed the plan:

- **Tenders are not needed.** `amount_paid` sums `payments` and `balance_due = total -
  amount_paid`, so a paid public order already reads as fully settled, and **no report
  aggregates `OrderTender` at all** — the reports are reservations, summary, margin and
  condition. An earlier note here claimed a missing tender would show a paid sale as owing.
  That was wrong. Leaving them out is right for a QR payment, where nothing was handed over
  a counter.
- **There is precedent for this shape.** The till's own combined cash + KHQR checkout
  already writes a `Payment` onto the order carrying the provider's `external_id`, so
  attaching one at submit follows what the system does rather than inventing a new path.
- **One inconsistency to tidy.** That precedent sets `reference_id` from the provider
  (`provider_payment.reference_id or reference`) while this change uses the ticket's id. The
  webhook matches on `external_id` first so nothing breaks today, but the two should agree.

## Things to decide or watch

- **Existing held tickets**: convert them, or leave them to be settled once and stop creating
  new ones. Two live order concepts is the worst outcome.
- **Order numbers**: online orders should draw from the same per-store sequence as counter
  sales, so a shop's numbering stays coherent.
- **Attribution**: an online order has no staff user; attach the shopper account where there
  is one, and keep `customer_name` for guests.
- **Queries that join `users`**: an inner join would hide every online order. The held-order
  list already outer-joins and is the pattern to copy; a test that lists orders with one
  online order present would catch a regression here.
- **Tax**: online totals must be priced by the same server-side path as a counter sale. The
  storefront must never sum the cart itself — it did, and quietly omitted service tax.
