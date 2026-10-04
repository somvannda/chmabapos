# Restaurant mode & table management

Status: Implemented — Phases 1–4 shipped, including split/merge; seat/course shipped later (see `docs/seat-course-plan.md`).
Owners: Engineering
Scope: design + shipped reference. §8 tracks what landed; §10 records the decisions taken.

Related: `docs/product-model.md` (vertical field packs), `docs/serial-condition-report.md`
(the "snapshot on sale" precedent), `chmabapos_api/app/verticals.py` (capability packs).

## 1. Goal

A restaurant workspace should run a **dining room**, not a barcode till. Today the
`restaurant` business type only seeds menu categories and shows menu wording — it
changes no behaviour. This document designs the missing surface:

1. A **floor plan** of tables (areas + tables), with availability state.
2. **Open tickets**: start an order against a table, keep adding items, fire to the
   kitchen, and pay at the end (no payment up front).
3. An **order type** (`dine_in | takeaway | delivery`) recorded on every sale.
4. Later: seat/course routing, **split and merge** bills, and a **kitchen display**.

Everything is gated so a retail store never sees it (see §7).

## 2. Where restaurant stands today

Already built and reusable:

| Piece | Where | Notes |
|---|---|---|
| `restaurant` business type | `app/verticals.py` | seed categories, help, checklist wording |
| **Modifiers / add-ons** | `ModifierGroup`, `Modifier`, `Product.modifier_group_id`, `OrderItem.modifiers` | the menu foundation; recipe depletion hook exists |
| **Held orders** | `HeldOrder` (`models.py`) + hold/resume UI in `sales.jsx` | a parked cart; the Hold dialog already uses the example "Table 4 · Pisey waiting" |
| **Tips & tax** | `Order.tip`, `Store.service_tax_rate` | needed for restaurant bills |
| **Real capability packs** | `app/verticals.py::capabilities_for` + `WorkspaceRead.capabilities` | how this feature will be switched on per workspace |

Missing: tables/floor plan, open (unpaid) tickets tied to a table, order type,
seat/course, split/merge, kitchen display.

## 3. Design principles

1. **Configuration, not a fork.** Restaurant mode is a capability pack on the shared
   POS, exactly like serials for electronics or batches for mart. The schema does not
   fork and no second order system is introduced.
2. **Reuse `HeldOrder` as the first open-ticket store.** It already parks a cart on the
   register. MVP attaches a table and an order type. A dedicated ticket table is a
   Phase 3 decision, not a Phase 1 requirement.
3. **Additive migrations.** Every change is a backward-compatible Alembic revision
   chained to the current single head (`alembic heads` must show one).
4. **Snapshot on sale.** Prices, modifiers and names freeze onto `OrderItem` at
   fulfilment, following the existing precedent.
5. **Money only moves at checkout.** Opening a table never touches stock, tax or
   payments; those happen when the ticket is settled — so stock and reporting stay
   correct without a new fulfilment path.

## 4. Data model

### 4.1 Floor plan (Phase 1)

New tables, store-scoped:

- `DiningArea(id, store_id, name, position, created_at)`
  — e.g. "Ground floor", "Terrace", "Private room".
- `DiningTable(id, store_id, area_id, name, seats, status, position, created_at, updated_at)`
  — `status ∈ {available, occupied, reserved, cleaning}`; `name` is the label the
    staff sees ("T1", "Window 3").

`(store_id, name)` is unique. Areas are optional: a table with `area_id = NULL`
belongs to an implicit "Main" group so a small café can skip areas entirely.

`status` is denormalised for a fast floor render; the ticket link (§4.3) is the
source of truth for whether a table is actually busy.

### 4.2 Order type (Phase 1)

Add one nullable column, defaulted so existing rows are unaffected:

- `Order.order_type` — `dine_in | takeaway | delivery`, default `takeaway` (the
  current behaviour is "pay and go").
- `HeldOrder.order_type` — same values, default `takeaway`.

This is the cheapest way to make "dine-in vs takeaway" reportable, and it is useful
to every food-service workspace even before tables exist.

### 4.3 Open tickets (Phase 1, extend `HeldOrder`)

Extend the existing table rather than create a parallel one:

- `HeldOrder.table_id` — nullable FK to `DiningTable`.
- `HeldOrder.order_type` — see §4.2.
- `HeldOrder.status` — `open | bill_requested` (default `open`).

MVP flow: "Open table" creates a `HeldOrder` with `table_id`, `order_type = dine_in`
and the chosen items; "Resume" (already built) reopens it; checkout settles it into a
real `Order` and clears the held row, freeing the table.

**Phase 3 decision (see §10):** if seat/course routing, merge, or a kitchen display
need richer per-line state than a JSON blob, introduce a dedicated
`TableTicket` + `TableTicketItem` (real FKs, `course`, `seat`, `fired_at`, `status`)
and keep `HeldOrder` for the "park a walk-in cart" use case only.

### 4.4 Seat & course (Phase 3)

Only if Phase 3 moves to a ticket table:

- `TableTicketItem.seat` (int, nullable) — who ordered it.
- `TableTicketItem.course` (`starters | mains | drinks | dessert`, nullable).
- `TableTicketItem.fired_at` / `voided_at` (nullable) — kitchen routing and voids.

### 4.5 Split & merge (Phase 4)

Split: pay a subset of ticket lines, keep the rest open. Merge: move all lines from
one ticket to another and free the emptied table. Both are operations on the Phase 3
ticket table; not attempted on the `HeldOrder` JSON shape.

## 5. API surface

Phase 1 (all store-scoped, role-gated like the rest of the catalog):

| Method | Path | Purpose |
|---|---|---|
| `GET/POST` | `/dining/areas` | list / create areas |
| `PATCH/DELETE` | `/dining/areas/{id}` | rename / remove |
| `GET/POST` | `/dining/tables` | floor list / add a table |
| `PATCH/DELETE` | `/dining/tables/{id}` | edit / remove |
| `POST` | `/dining/tables/{id}/open` | create the open ticket (HeldOrder) for a table |
| `POST` | `/held-orders/{id}/settle` *(or reuse existing order creation)* | turn the ticket into a paid `Order` |
| `GET` | `/dining/floor` | one call returning areas + tables + their ticket totals for the floor view |

`Order.order_type` and `HeldOrder.order_type` ride along in their existing read/write
schemas. Regenerate `chmabapos_api/openapi.json` in the same PR.

## 6. Web UI (`apps/web`)

Phase 1, all behind the `tables` capability (§7):

Shipped, all behind the `tables` capability (§7):

- **Floor** view: a grid of tables grouped by area, each tile showing name, seats,
  status, and the open ticket's item count and total. Tapping an **available** table
  opens the register with that table preselected (dine-in); tapping a **busy** table
  opens that ticket's drawer. (#313, #327, #328, #349)
- **Kitchen** view: open tickets newest-first with age and line items; tapping a
  ticket opens the same drawer. (#330)
- **Ticket drawer** (shared by Floor and Kitchen): split quantities onto a new ticket
  (optionally another table), merge a ticket into another, and mark it served or
  reopen it. (#336, #338, #340, #342, #349)
- The register gains a **table selector** next to the order type (choosing one sets
  dine-in); held tickets carry the table, and the settled `Order` snapshots it.
  (#302, #321, #333)
- The Orders list shows a **dine-in / delivery** badge for non-takeaway sales. (#347)
- Settings → **Tables** (add areas/tables). (#307)
- The POS already supports modifiers, tips and tax, so the menu side needs no change.

## 7. Capability & plan gating

Two independent gates, both already patterned in the codebase:

1. **Capability (business type):** add `"tables"` to `CAPABILITY_LABELS` and to the
   `restaurant` entry of `VERTICAL_CAPABILITIES` in `app/verticals.py`. The floor view
   and table controls then appear for restaurant workspaces (and any store that enables
   the pack via Settings → Feature packs, built in #290).
2. **Plan feature:** `"table_management"` in `FEATURE_CATALOG` (`app/features.py`)
   gates the dining endpoints via the existing `require_plan_feature`. It is
   included on **Starter and Pro**; only **Free** is blocked (Starter regained it
   in the O1 decision). The owner-facing label: "Table & restaurant mode".

The UI reads capabilities (already available) to decide whether to render the floor;
the API enforces the plan gate. A store can be a restaurant on any plan, but tables
require the plan that includes `table_management`.

## 8. Rollout order (one branch / PR each)

| # | PR | Scope | Status |
|---|---|---|---|
| 0 | `docs/restaurant-mode` (#293) | this document | ✅ shipped |
| 1 | `feat/restaurant-order-type` (#297) | `Order.order_type` + `HeldOrder.order_type`, schemas | ✅ shipped |
| 1a | `feat/restaurant-order-type-ui` (#302) | POS order-type selector | ✅ shipped |
| 2 | `feat/restaurant-tables` (#304) | `DiningArea`/`DiningTable`, dining endpoints | ✅ shipped |
| 2a | `feat/restaurant-tables-ui` (#307) | Settings → Tables | ✅ shipped |
| 2b | `feat/restaurant-tables-capability` (#309) | `tables` capability | ✅ shipped |
| 3 | `feat/restaurant-open-tickets` (#317) | `HeldOrder.table_id`/`status`; free the table on settle | ✅ shipped |
| 3a | `feat/restaurant-ticket-ui` (#321) | POS Table selector (table → held ticket) | ✅ shipped |
| 4 | `feat/restaurant-plan-gate` (#325) | `table_management` plan feature + endpoint gate | ✅ shipped |
| 5 | `feat/restaurant-floor` (#313) | Floor view (tables by area, ticket totals) | ✅ shipped |
| 5a | `feat/restaurant-floor-order` (#328) | open a ticket from a Floor tile | ✅ shipped |
| 5b | `feat/restaurant-floor-tickets` (#327) | show a ticket's items/total on the Floor | ✅ shipped |
| 6 | `feat/restaurant-kitchen` (#330) | kitchen display | ✅ shipped |
| 6a | `feat/restaurant-kitchen-served` (#342) | mark a ticket served | ✅ shipped |
| 7 | `feat/restaurant-order-table` (#333) | snapshot `table_id` onto the settled order | ✅ shipped |
| 8 | `feat/restaurant-merge-tickets` (#336) | merge held tickets | ✅ shipped |
| 8a | `feat/restaurant-split-bill` (#338) | split a held ticket | ✅ shipped |
| 8b | `feat/restaurant-ticket-actions` (#340) | split/merge from the Kitchen board | ✅ shipped |
| 8c | `feat/restaurant-floor-ticket-drawer` (#349) | shared ticket drawer (Floor + Kitchen) | ✅ shipped |

Everything above is on `main`: table management is complete, including split/merge
(backend + UI) and the kitchen "served" bump. Seat/course routing and richer per-line
ticket state can follow on the `HeldOrder`-based tickets if real use calls for it.

## 9. Out of scope

- Reservations, waitlists and deposits.
- Online ordering / QR-at-table ordering (separate customer-facing surface).
- Delivery dispatch and driver tracking (`delivery` is recorded as an order type only).
- Per-table service charges or dynamic pricing.
- Offline mode.

## 10. Decisions (taken)

1. **Open tickets extend `HeldOrder`, not a new `TableTicket`.**
   Shipped: `HeldOrder` gained `table_id` and `status` (#317). A `TableTicket` will only
   be introduced if seat/course routing or per-line kitchen state is needed.
2. **The settled `Order` snapshots `table_id`.**
   Shipped (#333), nullable with `ON DELETE SET NULL`, so attribution survives table
   renames/deletes. `table_name` is not duplicated — the table row stays the source.
3. **The Floor is a nav item**, shown only when the `tables` capability is on (#313);
   the register is untouched for retail. A **Kitchen** nav item follows the same rule
   (#330).
4. **`table_management` is on Starter and Pro** (`DEFAULT_FEATURES_BY_PLAN`). It was
   briefly Pro-only (#353) and granted back to Starter by the O1 decision; only
   **Free** gets a 403 from the dining endpoints.
5. **Tax/service charge:** kept at the existing store-level `service_tax_rate`; per-table
   or per-order service charges remain out of scope.
6. **Split & merge are shipped** (#336/#338, with a shared Floor/Kitchen drawer in
   #349). Seat/course routing shipped later (#392/#393/#394); see `docs/seat-course-plan.md`.
