# Capabilities & gaps

Status: living document — a snapshot of what the POS supports today and the known
gaps, kept as an actionable backlog to work through one item at a time.
Owners: Engineering

Related: `docs/product-model.md` (product/variant/modifier model),
`docs/restaurant-mode.md` (restaurant design), `docs/restaurant-deploy.md`
(deploy runbook), `docs/email-notifications-plan.md` (email inventory + gaps),
`app/verticals.py` (business types + capability packs), `app/features.py`
(plan features).

## 1. How to read this

- A **business type** (`Company.vertical`) is **advisory configuration**, not a
  hard mode. It picks default categories, help content, and the capability packs
  the UI surfaces first. The API accepts every field for every vertical, and a
  store can enable/disable any pack via **Settings → Feature packs**
  (`Store.preferences.capabilities`).
- So "how many businesses we support" = **6 defaults over one shared engine**,
  not six separate products.
- Status words below: **Built**, **Partial**, **Not built**.

## 2. Feature inventory (built)

- **Selling:** products, nested categories, per-product price/cost/tax,
  discounts, tips, tax (inclusive/exclusive, store + per-product), cash + KHQR +
  mixed tenders, change, multi-currency + exchange rates, refunds, held orders,
  shifts, customer records + loyalty points, receipts (templates, print, email),
  customer display, barcode/SKU scan, serial lookup.
- **Catalog depth:** variants (options/values), modifiers with **recipe-based
  ingredient depletion** (the ingredient and quantity are configurable from the
  catalog editor), serials/IMEI with supplier + customer warranty,
  condition grading (used/refurb) + condition history + service tickets,
  **trade-in intake** (a customer device accepted at an assessed value, applied
  to a sale as a credit), a **warranty-claim lifecycle** (file → decide → resolve
  via repair/replace/refund), batches/expiry, unit of measure, barcode, brand,
  JSON attributes.
- **Bundles:** combos / meal deals — fixed bundles and choose-from-a-set groups.
- **Inventory:** per-store balances (product- and variant-level), stock movements
  with frozen unit cost (COGS), restock/adjust/transfer, reorder points,
  suppliers + purchase orders + supplier prices, media library.
- **Restaurant:** order types (dine-in/takeaway/delivery), dining areas + tables,
  Floor view, open tickets (table ↔ held order), Kitchen display + "served",
  merge/split tickets, table snapshotted on the settled order, order type on the
  Orders list, seat/course routing with fire-by-course, **online ordering /
  QR-at-table** (public token + per-table QR, tickets land on the board), POS and
  receipts.
- **Platform:** multi-store, teams + roles/permissions, approval policy,
  audit/activity, plans/subscriptions/billing, notifications, AI help assistant,
  support tickets, reporting (summary, consolidated, margin, condition/graded stock).

## 3. Business types & default packs

| Vertical | Label | Default packs |
|---|---|---|
| `coffee` | Café / coffee shop | variants, modifiers |
| `restaurant` | Restaurant / food service | variants, modifiers, tables |
| `mart` | Mart / grocery | barcode, brand, unit_of_measure, variants, batches |
| `electronics` | Electronics store | barcode, brand, variants, serials |
| `shop` | General retail shop | barcode, variants |
| `general` | Other / general | (core only) |

Capability keys (`app/verticals.py::CAPABILITY_LABELS`): `barcode`, `brand`,
`unit_of_measure`, `variants`, `modifiers`, `tables`, `serials`, `batches`.

Plan features (`app/features.py::FEATURE_CATALOG`): 15 keys, including
`table_management` (Starter and Pro).

## 4. Per-category coverage

| Category | Coverage | Gaps |
|---|---|---|
| **General retail shop** | **Built** — core + barcode + variants | none material |
| **Electronics** | **Built (deepest)** — serials/IMEI, dual warranty, condition grading, service tickets, variants, trade-in/buyback, warranty-claim lifecycle | none material |
| **Mart / grocery** | **Partial** — barcode, brand, UoM entry (decimal at POS), variants, batches/expiry, FEFO consumption | hardware scale integration |
| **Café / coffee** | **Partial** — variants, modifiers, recipe depletion, rich held tickets, combos | — |
| **Restaurant** | **Partial (broad surface)** — floor, tickets, kitchen, split/merge/transfer, served, rich held tickets, table on order, seat/course, combos, online ordering / QR-at-table | no reservations/waitlist or delivery dispatch |
| **General / other** | **Core only**, by design | — |

## 5. Cross-cutting gaps

1. **Held/ticket lines carry variants + modifiers** — built (#368): lines snapshot
   the variant and add-ons and are keyed by product + variant + modifier set.
   Serials are still not parked on a ticket.
2. **Combos / bundles / meal deals** — built: fixed bundles (#376/#380),
   choose-from-a-set groups (#386/#387) and combo reporting (#389).
3. **Weight / measure entry at the POS** is built (the cart shows a decimal
   quantity input for `kg`/`g`/`l`/`ml`); only **hardware scale integration** is
   missing (out of scope).
4. **FEFO batch consumption at checkout** — built (`services/orders.py`) and covered by a test.
5. **Trade-in / buyback and warranty claims** — built: a customer device is taken
   into stock at an assessed value and can settle a sale (#401/#402/#404); claims
   run file → decide → resolve via repair/replace/refund (#408/#411/#413), with
   intake value and claim cost reported (#404/#413).
6. **Online ordering / QR-at-table** — built: a public tokenised menu and order
   submit feed the held-ticket engine; staff toggle it and get a per-table QR
   (#423/#426/#429), and online/QR tickets are badged on the Kitchen and Floor
   (#430). Pay-at-counter; online KHQR is a later phase.
7. **No offline mode.**
8. **Restaurant extras** still out of scope: reservations/waitlist and delivery
   dispatch (order type is recorded only).

## 6. Backlog (work one at a time)

Each item is intended to ship as its own PR, worktree off `origin/main`, green CI
as the gate.

### Product gaps

- [x] **G1 — Held tickets carry variants + modifiers** *(restaurant, café, all)* — shipped (#368)
  Add `variant_id` and `modifiers` to `HeldItemRequest`, the held-order item
  snapshot, and the Floor/Kitchen/POS hold-resume flow; keep split/merge working
  with the richer lines. **Recommended next: highest impact, small scope.**
- [x] **G2 — Seat / course routing** *(restaurant)* — shipped: per-line seat/course
  + fire-by-course (#392), Kitchen grouping/fire + drawer controls (#393), POS seat
  chips (#394).
- [x] **G3 — Table transfer** *(restaurant)* Move an open ticket to another table
  (frees the old table, occupies the new). Shipped.
- [x] **G4 — Combos / meal deals** *(café, restaurant, mart)* — shipped: fixed
  bundles and choose-from-a-set groups (#376/#380/#386/#387) plus reporting (#389).
- [x] **G5 — Weight / measure entry at the POS** *(mart)* — already built: the
  cart shows a decimal quantity input (step 0.001) for `kg`/`g`/`l`/`ml`
  products. Hardware scale integration remains (out of scope).
- [x] **G6 — FEFO batch consumption at checkout** *(mart)* — already built
  (`services/orders.py`, earliest-expiry-first, nulls last); a test now guards it.
- [x] **G7 — Trade-in / buyback** *(electronics)* — shipped: device intake at an
  assessed value, applied to a sale as a credit, with reporting (#401/#402/#404).
- [x] **G8 — Warranty claim lifecycle** *(electronics)* — shipped: file → decide →
  resolve (repair/replace/refund) with an event log and cost reporting
  (#408/#411/#413).
- [ ] **G9 — Offline mode** *(all)* Large; likely out of scope near-term.

### Restaurant follow-ons (currently out of scope)

- [ ] **G10 — Reservations / waitlist** *(restaurant)*
- [x] **G11 — Online ordering / QR-at-table** *(restaurant)* — shipped: public
  tokenised menu + order submit feeding the ticket engine, settings toggle with
  per-table QR, a public customer page, and Online/QR staff badges
  (#419/#423/#426/#429/#430). Online KHQR remains a later phase.
- [ ] **G12 — Delivery dispatch** *(restaurant)* beyond recording the order type

### Retail follow-ons

- [x] **G13 — Deposit reservations / layaway** *(electronics, mart, all retail)* —
  shipped (backend): a customer pays a deposit on an order, stock can be held off
  the shelf so it cannot be sold twice, and the balance is collected when they
  return. An order with `pickup_at` and a partial deposit becomes `pending_pickup`;
  `POST /orders/{id}/collect` settles the balance and completes the sale, while
  cancel/`reservation_expired` return held stock. Deposit and balance are cash or
  trade-in credit (KHQR balance collection is a later phase). **POS screens for
  taking a deposit / collecting a balance are a follow-up.**

### Operational / housekeeping

- [x] **O1 — Deploy restaurant mode to production** *(ops)* Follow
  `docs/restaurant-deploy.md`. Decision: `table_management` is granted back to
  **Starter** — Starter and Pro include it; only Free is blocked.
- [x] **O2 — One DB per worktree** — documented in `CONTRIBUTING.md`.
- [~] **O3 — Email & notification gaps** *(all)* — inventoried and sequenced in
  `docs/email-notifications-plan.md`. All P0 items shipped: online/QR order alert
  (#442), billing receipt (#444), payment-failed (#446), password-changed (#445),
  new-device sign-in (#449), customer refund confirmation (#448), and online-order
  acknowledgement (#462). All P1 shipped: shift-close summary (#454), mail
  dead-letter alert (#453), weekly (#455) and monthly (#461) summaries, the
  operations digest (#458), quota/limit warnings (#467), and warranty-expiry
  reminders (in review, #469). Remaining: service-ticket updates and loyalty (P2).
  One PR per item.

## 7. Suggested order

1. ✅ **G1** (held tickets carry variants/modifiers) — shipped (#368).
2. ✅ **G3** (table transfer) — shipped.
3. ✅ **G6** (FEFO) and ✅ **G5** (weight/measure entry) — both already built, now confirmed; only hardware scale integration remains.
4. ✅ **G4** (combos) — shipped: fixed bundles, choose-from-a-set groups, reporting.
5. ✅ **G2** (seat/course) — shipped.
6. ✅ **G7/G8** (trade-in, warranty claims) — shipped.
7. ✅ **G11** (online ordering / QR-at-table) — shipped (pay-at-counter; online KHQR later).
8. ✅ **G13** (deposit reservations / layaway) — backend shipped; POS screens pending.
9. **G10/G12/G9** — restaurant reservations, delivery dispatch, offline mode; large and as demand appears.
