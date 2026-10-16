# Online orders are orders

Status: design agreed, schema landed; the submit path still parks online orders as **held
tickets**. This records what "done" looks like and why, so the remaining steps are mechanical.

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
