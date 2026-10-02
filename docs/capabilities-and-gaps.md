# Capabilities & gaps

Status: living document — a snapshot of what the POS supports today and the known
gaps, kept as an actionable backlog to work through one item at a time.
Owners: Engineering

Related: `docs/product-model.md` (product/variant/modifier model),
`docs/restaurant-mode.md` (restaurant design), `docs/restaurant-deploy.md`
(deploy runbook), `app/verticals.py` (business types + capability packs),
`app/features.py` (plan features).

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
  ingredient depletion**, serials/IMEI with supplier + customer warranty,
  condition grading (used/refurb) + condition history + service tickets,
  batches/expiry, unit of measure, barcode, brand, JSON attributes.
- **Inventory:** per-store balances (product- and variant-level), stock movements
  with frozen unit cost (COGS), restock/adjust/transfer, reorder points,
  suppliers + purchase orders + supplier prices, media library.
- **Restaurant:** order types (dine-in/takeaway/delivery), dining areas + tables,
  Floor view, open tickets (table ↔ held order), Kitchen display + "served",
  merge/split tickets, table snapshotted on the settled order, order type on the
  Orders list, POS and receipts.
- **Platform:** multi-store, teams + roles/permissions, approval policy,
  audit/activity, plans/subscriptions/billing, notifications, AI help assistant,
  support tickets, reporting (summary, consolidated, margin).

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
`table_management` (**Pro-only**).

## 4. Per-category coverage

| Category | Coverage | Gaps |
|---|---|---|
| **General retail shop** | **Built** — core + barcode + variants | none material |
| **Electronics** | **Built (deepest)** — serials/IMEI, dual warranty, condition grading, service tickets, variants | trade-in/buyback; formal warranty-claim lifecycle |
| **Mart / grocery** | **Partial** — barcode, brand, UoM field, variants, batches/expiry | no scale/weight capture; FEFO consumption at checkout unverified |
| **Café / coffee** | **Partial** — variants, modifiers, recipe depletion | held tickets drop modifiers/variants; no combos/meal deals |
| **Restaurant** | **Partial (broad surface)** — floor, tickets, kitchen, split/merge, served, table on order | held tickets drop modifiers/variants; no seat/course; no table transfer; no reservations/online ordering/delivery dispatch |
| **General / other** | **Core only**, by design | — |

## 5. Cross-cutting gaps

1. **Held/ticket lines are product + quantity only** — no variant, modifiers, or
   serials (`schemas.py::HeldItemRequest`). Undercuts restaurant/café (a parked
   "large, oat-milk latte" loses its size/milk) and any held sale with variants.
2. **No combos / bundles / meal deals** (product model excludes composites beyond
   recipe depletion).
3. **No scale/weight capture at the POS** (weight sales rely on manual quantity).
4. **FEFO batch consumption at checkout** not verified.
5. **No offline mode.**
6. **Restaurant extras** out of scope today: reservations/waitlist, online
   ordering / QR-at-table, delivery dispatch (order type is recorded only).

## 6. Backlog (work one at a time)

Each item is intended to ship as its own PR, worktree off `origin/main`, green CI
as the gate.

### Product gaps

- [ ] **G1 — Held tickets carry variants + modifiers** *(restaurant, café, all)*
  Add `variant_id` and `modifiers` to `HeldItemRequest`, the held-order item
  snapshot, and the Floor/Kitchen/POS hold-resume flow; keep split/merge working
  with the richer lines. **Recommended next: highest impact, small scope.**
- [ ] **G2 — Seat / course routing** *(restaurant)* Per-line `seat` and `course`,
  fire-by-course to the Kitchen. Schema + UI; larger.
- [ ] **G3 — Table transfer** *(restaurant)* Move an open ticket to another table
  (frees the old table, occupies the new). Small, backend + drawer action.
- [ ] **G4 — Combos / meal deals** *(café, restaurant, mart)* Bundle a set of
  products at a set price. New model + UI; medium.
- [ ] **G5 — Scale / weight capture** *(mart)* Enter weight at the POS for
  `unit_of_measure` products (e.g. per kg). Medium.
- [ ] **G6 — FEFO batch consumption at checkout** *(mart)* Consume batches
  first-expiry-first-out when selling batch-tracked products; confirm or build.
- [ ] **G7 — Trade-in / buyback** *(electronics)* Record a customer device taken
  in against a sale. Medium.
- [ ] **G8 — Warranty claim lifecycle** *(electronics)* Formalise claims on top
  of serials/service tickets. Medium.
- [ ] **G9 — Offline mode** *(all)* Large; likely out of scope near-term.

### Restaurant follow-ons (currently out of scope)

- [ ] **G10 — Reservations / waitlist** *(restaurant)*
- [ ] **G11 — Online ordering / QR-at-table** *(restaurant)*
- [ ] **G12 — Delivery dispatch** *(restaurant)* beyond recording the order type

### Operational / housekeeping

- [ ] **O1 — Deploy restaurant mode to production** *(ops)* Follow
  `docs/restaurant-deploy.md`; decide whether `table_management` stays Pro-only
  or is granted back to Starter (`scripts/set_plan_capability.py`).
- [x] **O2 — One DB per worktree** — documented in `CONTRIBUTING.md`.

## 7. Suggested order

1. **G1** (held tickets carry variants/modifiers) — smallest, highest impact.
2. **G3** (table transfer) — small restaurant win.
3. **G6** (FEFO) then **G5** (scale) — mart depth.
4. **G4** (combos) — café/restaurant depth.
5. **G2** (seat/course) — the remaining big restaurant feature.
6. **G7/G8** — electronics depth, as demand appears.
