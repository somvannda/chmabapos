# Restaurant mode & table management

Status: Draft for review
Owners: Engineering
Scope: design only — no code changes in this document's PR.

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

- New **Floor** view in the POS: a grid of tables grouped by area, each tile showing
  name, seats, status, and the open ticket total and age. Tapping an empty table opens
  a ticket; tapping a busy table resumes it.
- The existing register gains a **table selector** when a ticket is open, and the
  existing Hold/Resume modals get a table shown instead of a free-text label.
- Settings → a **Tables** section (add areas/tables), mirroring the existing settings
  cards.
- The POS already supports modifiers, tips and tax, so the menu side needs no change.

## 7. Capability & plan gating

Two independent gates, both already patterned in the codebase:

1. **Capability (business type):** add `"tables"` to `CAPABILITY_LABELS` and to the
   `restaurant` entry of `VERTICAL_CAPABILITIES` in `app/verticals.py`. The floor view
   and table controls then appear for restaurant workspaces (and any store that enables
   the pack via Settings → Feature packs, built in #290).
2. **Plan feature:** add `"table_management"` to `FEATURE_CATALOG` in `app/features.py`
   and gate the dining endpoints with the existing `require_plan_feature`, so the heavy
   feature is not on Free. The owner-facing label: "Table & restaurant mode".

The UI reads capabilities (already available) to decide whether to render the floor;
the API enforces the plan gate. A store can be a restaurant on any plan, but tables
require the plan that includes `table_management`.

## 8. Rollout order (one branch / PR each)

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/restaurant-mode` | this document |
| 1 | `feat/restaurant-order-type` | `Order.order_type` + `HeldOrder.order_type`, schemas, POS selector, reports grouping |
| 2 | `feat/restaurant-tables` | `DiningArea`/`DiningTable`, dining endpoints, floor view, Settings → Tables |
| 3 | `feat/restaurant-open-tickets` | `HeldOrder.table_id`/`status`, open/resume/settle by table, free-table on settle |
| 4 | `feat/restaurant-plan-gate` | `tables` capability + `table_management` plan feature + UI gating |
| 5 | `feat/restaurant-tickets` *(Phase 3)* | dedicated `TableTicket`/`TableTicketItem`, seats, courses, fire-to-kitchen |
| 6 | `feat/restaurant-split-merge` *(Phase 4)* | split and merge operations |
| 7 | `feat/kitchen-display` *(Phase 4)* | read-only KDS screen |

Phases 1–4 deliver "table management". Phases 5–7 are follow-ons and can be
re-prioritised after the MVP is in real use.

## 9. Out of scope

- Reservations, waitlists and deposits.
- Online ordering / QR-at-table ordering (separate customer-facing surface).
- Delivery dispatch and driver tracking (`delivery` is recorded as an order type only).
- Per-table service charges or dynamic pricing.
- Offline mode.

## 10. Open decisions

1. **Open tickets: extend `HeldOrder` or add `TableTicket`?**
   Recommendation: extend `HeldOrder` for Phases 1–4 (fast, reuses hold/resume), and
   only add `TableTicket` when seats/courses/KDS demand real per-line state. Confirm.
2. **Does `Order` keep `order_type` only, or also a `table_id` snapshot?**
   Recommendation: snapshot `table_id`/`table_name` onto the settled `Order` so reports
   and receipts survive table renames. Confirm.
3. **Should the floor view be a new nav item or a mode of the POS?**
   Recommendation: a new **Floor** nav item shown only when the `tables` capability is
   on, keeping the register untouched for retail.
4. **Free plan:** tables are plan-gated. Is `table_management` a Starter feature or
   Pro-only? (Billing decision.)
5. **Tax/service charge:** kept at the existing store-level `service_tax_rate`; a
   per-table or per-order service charge is explicitly out of scope in v1.
