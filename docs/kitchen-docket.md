# The kitchen's docket, and what "orders only" would cost

Status: **a decision to take with the evidence in hand**, before the work in
`docs/online-orders.md` step 3 is built. It revises an earlier recommendation of mine, and it
says plainly what the earlier one missed.

## Where things stand

A public order creates two records:

- the **`Order`** — real lines, a `Payment`, `source='online'`, `paid_at`; what reporting reads;
- the **`HeldOrder`** — the kitchen's docket, items as JSON with per-line `fired_at`.

They now point at each other (`held_orders.order_id`), so settlement finds the docket by fact
rather than by guessing on a payment id.

## What I said, and why it was incomplete

I recommended: *the board reads orders, then stop creating storefront tickets.* I checked the
board before building it, and the ticket is **load-bearing in ways the order is not**:

| The kitchen uses | On the ticket | On the order |
|---|---|---|
| per-line **fired** state (`fired_at`) | yes | **no such column** |
| per-line seat / course | yes | yes (`seat`, `course`) |
| **fire** an order's lines | yes | nothing to record it on |
| **split** a bill in two | yes | cart operation |
| **merge** two bills | yes | cart operation |
| **transfer** to another table | yes | cart operation |

The board (`apps/web/src/features/kitchen.jsx`) renders a card per ticket showing which lines
are unfired, and every card opens `TicketDrawer`, which offers fire / split / merge / transfer /
seat / course. Three other surfaces read the same rows: `dining.jsx` (the floor),
`sales.jsx` (the parked-cart modal), and `team.jsx` (which feeds `heldOrders` into
`needsAttention`).

So "orders only" is not a cleanup. It means **moving the kitchen's working state onto orders**:
a migration for `order_items.fired_at`, a `kind` marker so the UI can hide cart-only actions on
an order row, drawer changes, and rewrites of two board tests. Done badly it regresses exactly
the line the kitchen watches — whether the food has started — for every online order in a
restaurant.

## The two options, honestly costed

**A. Orders only (the original decision).**
Stop creating tickets for storefront orders; the board reads orders.

- Needs: migration (`order_items.fired_at`), `kind` in the board response, drawer changes in
  `apps/web`, two board tests rewritten.
- Costs: a selling-surface change spanning API **and** `apps/web`, verified only by CI (I cannot
  run Playwright locally). Restaurant online orders are the population at risk.
- Gains: one record per sale, conceptually clean.

**B. Keep the docket, now explicitly linked (what #846 started).**
The ticket is the kitchen's work item for the order — which is what a kitchen display *is* in
most POS systems. Nothing pretends they are the same thing; the link makes the relationship a
fact, and the sync is no longer a guess.

- Needs: nothing further for parity. The cost is that two records still exist per online sale.
- Gains: no regression to the kitchen, no migration, no client change.
- Cost: the debt stays — but it is now *named* debt with an explicit link, not two records
  kept in step by inference.

## My revised recommendation

**B, and revisit A only if the duplication actually hurts.** Concretely, "hurts" would mean a
report or a screen that cannot tell a docket from an order, or a bug that traces to the two
disagreeing. So far the failures this week traced to the *inference*, which #846 removed — not
to the existence of two records.

The decision to make now is not "clean or not" but **"is the kitchen's state worth migrating
onto orders, at the cost of a selling-surface change, for a concept we can already name
precisely?"**

## If A is chosen, the sequence

1. Commit and re-chain the uncommitted store-chat migration, so `main` has a single head
   (it currently points at `a8f4c2e6b9d3`; the head is now `e3b7c9d1f5a2`).
2. Migration: `order_items.fired_at` (datetime, nullable) — parity with the docket.
3. Board: `GET /held-orders` returns tickets **and** online orders, each row carrying `kind`
   (`ticket` | `order`); regenerate `openapi.json` and the client types.
4. `fire` and `items` accept an order-backed row via `held_orders.order_id`; `split`, `merge`
   and `transfer` refuse one with a clear message, because they are cart operations.
5. `apps/web`: hide the cart-only actions on an order row; keep fire and seat/course.
6. Stop creating the ticket in `_submit_public_order`; rewrite
   `test_board_hides_unpaid_online_order_until_paid` and
   `test_board_shows_pay_at_counter_online_order`.
7. A Playwright spec for the kitchen board, since CI is the only place the web half is verified.

Steps 2–4 are API-only and testable without the UI; step 5 is where the risk lives.
